#### Preamble ####
# Purpose: The polling average shown on the website: each poll gets a weight from four rules, and a candidate's
#          average on a day is the weighted mean of their share in the polls finished by then. Shares are first
#          scaled to leave out the undecided (without_undecided), so the average compares with our forecast. Each rule can be
#          turned on or off, so the website can show how much each one moves the average.
#          Used by #12 scripts/12-summarize_results.py, which saves the average for every on/off combination.
# Author: Furkan Danisman
# Date: 24 October 2026; undecided left out 25 October 2026; 95% interval 26 October 2026
# Pre-requisites: polls from scripts/10-clean_polls.py

import itertools
from datetime import timedelta

import numpy as np
import polars as pl

# The four weighting rules, in the order of the columns that say whether each was used.
RULES = ["by_recency", "by_sample_size", "by_pollster", "by_population"]
# Every on/off combination of the rules: 2 x 2 x 2 x 2 = 16.
RULE_COMBINATIONS = [dict(zip(RULES, on, strict=True)) for on in itertools.product([True, False], repeat=len(RULES))]

# Recency: a poll's weight halves every 14 days after its last day of interviews.
HALF_LIFE_DAYS = 14
# Sample size: weight grows with the square root of the number of people asked. Dividing by a 600-person poll only
# makes a typical poll's weight about 1; it does not change the average. Polls above 5,000 people count as 5,000,
# and polls without a sample size as 600.
REFERENCE_SAMPLE_SIZE = 600
MAX_SAMPLE_SIZE = 5000
# Pollster: a firm with k polls of the race in the last 60 days has each of its polls divided by the square root of k.
POLLSTER_WINDOW_DAYS = 60
# Population: likely voters count fully, registered voters and adults less. These numbers are our own choice,
# not taken from data or another source. Polls that do not say who they asked count as registered voters.
POPULATION_WEIGHTS = {"Likely voters": 1.0, "Registered voters": 0.8, "Adults": 0.6}
MISSING_POPULATION_WEIGHT = 0.8


def without_undecided(polls):
    """Each poll's shares scaled to add up to 1 among the candidates it asked about, so undecided voters (and anyone
    not named) are left out, as in our forecast. E.g. a poll with 45% and 45% becomes 50% and 50%.

    `polls` has the polls columns, one row per candidate per poll."""
    return polls.with_columns(pl.col("share") / pl.col("share").sum().over("poll_id"))


# The polls' 95% interval: the average ± 1.96 spreads, where 95% of the polls would fall if their shares were spread
# like a normal distribution around the average. It shows how much the polls disagree, not a margin of error.
SPREADS_FOR_95_PERCENT = 1.96


def poll_interval(average, spread):
    """The lower and upper ends of the polls' 95% interval, as polars expressions, kept between 0 and 1."""
    lower = (pl.col(average) - SPREADS_FOR_95_PERCENT * pl.col(spread)).clip(0, 1)
    upper = (pl.col(average) + SPREADS_FOR_95_PERCENT * pl.col(spread)).clip(0, 1)
    return lower, upper


def poll_weights(end_days, sample_sizes, pollsters, populations, day, rules):
    """Each poll's weight in the average on `day`, from the rules switched on in `rules`.

    The first four arguments describe one race's polls, one value per poll: the last day of interviews (as a day
    number), the number of people asked (None if unknown), the pollster and who was asked. A poll that had not
    finished by `day` gets weight 0."""
    end_days = np.asarray(end_days)
    finished = end_days <= day
    weights = finished.astype(float)
    if rules["by_recency"]:
        weights *= 0.5 ** ((day - end_days) / HALF_LIFE_DAYS)
    if rules["by_sample_size"]:
        sizes = np.array([REFERENCE_SAMPLE_SIZE if n is None else min(n, MAX_SAMPLE_SIZE) for n in sample_sizes])
        weights *= np.sqrt(sizes / REFERENCE_SAMPLE_SIZE)
    if rules["by_pollster"]:
        pollsters = np.asarray(pollsters)
        recent = finished & (end_days > day - POLLSTER_WINDOW_DAYS)
        same_pollster = pollsters[:, None] == pollsters[None, :]
        np.fill_diagonal(same_pollster, False)
        polls_by_same_pollster = 1 + (same_pollster & recent[None, :]).sum(axis=1)  # this poll plus the others
        weights /= np.sqrt(polls_by_same_pollster)
    if rules["by_population"]:
        weights *= np.array([POPULATION_WEIGHTS.get(p, MISSING_POPULATION_WEIGHT) for p in populations])
    return weights


def weighted_average(shares, weights):
    """The weighted mean of `shares` and their weighted standard deviation around it (the spread of the polls).
    Polls with weight 0 do not count. None if no poll counts."""
    if weights.sum() == 0:
        return None
    average = np.average(shares, weights=weights)
    spread = np.sqrt(np.average((shares - average) ** 2, weights=weights))
    return average, spread


def race_averages(race_polls, last_day, rules):
    """One race's average for each candidate on each day, from its first poll to `last_day`.

    `race_polls` has the polls columns, one row per candidate per poll. Returns rows of date, candidate, average and
    spread. A candidate's average uses only the polls that asked about them."""
    polls = race_polls.group_by("poll_id", maintain_order=True).agg(
        pl.col("date", "sample_size", "population", "pollster").first(), pl.col("candidate", "share"),
    )
    first_day = polls["date"].min()
    end_days = np.array([(d - first_day).days for d in polls["date"]])
    shares = {}  # candidate -> (share in each poll, whether the poll asked about them)
    for candidate in race_polls["candidate"].unique().sort():
        in_poll = [dict(zip(c, s, strict=True)).get(candidate) for c, s in zip(polls["candidate"], polls["share"], strict=True)]
        shares[candidate] = (np.array([s or 0.0 for s in in_poll]), np.array([s is not None for s in in_poll]))

    rows = []
    for day in range((last_day - first_day).days + 1):
        weights = poll_weights(end_days, polls["sample_size"].to_list(), polls["pollster"].to_numpy(),
                               polls["population"].to_list(), day, rules)
        for candidate, (candidate_shares, asked) in shares.items():
            result = weighted_average(candidate_shares, weights * asked)
            if result is not None:
                rows.append({"date": first_day + timedelta(days=day), "candidate": candidate,
                             "average": result[0], "spread": result[1]})
    return rows


def poll_influence(race_polls, day, rules):
    """Each poll's weight in a race's average on `day` (its "influence"), as rows of poll_id and influence."""
    polls = race_polls.group_by("poll_id", maintain_order=True).agg(pl.col("date", "sample_size", "population", "pollster").first())
    end_days = np.array([(d - day).days for d in polls["date"]])
    weights = poll_weights(end_days, polls["sample_size"].to_list(), polls["pollster"].to_numpy(),
                           polls["population"].to_list(), 0, rules)
    return [{"poll_id": p, "influence": w} for p, w in zip(polls["poll_id"], weights, strict=True)]
