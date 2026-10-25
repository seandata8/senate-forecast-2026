#### Preamble ####
# Purpose: Tests for the polling average (src/senate_forecast_2026/poll_average.py): each weighting rule does what
#          the website says it does, on small made-up polls whose answers can be worked out by hand.
# Author: Furkan Danisman
# Date: 25 October 2026
# Pre-requisites: none
# Run from the repo root: uv run pytest

from datetime import date

import numpy as np
import polars as pl
import pytest

from senate_forecast_2026.poll_average import (
    RULE_COMBINATIONS,
    RULES,
    poll_influence,
    poll_weights,
    race_averages,
    weighted_average,
)

ALL_OFF = dict.fromkeys(RULES, False)


def only(rule):
    """The rules with just `rule` switched on."""
    return {**ALL_OFF, rule: True}


def test_there_are_16_distinct_combinations():
    assert len(RULE_COMBINATIONS) == 16
    assert len({tuple(rules.values()) for rules in RULE_COMBINATIONS}) == 16


def test_with_every_rule_off_each_finished_poll_counts_the_same():
    weights = poll_weights([0, 5, 10], [400, 1000, None], ["A", "A", "B"], ["Likely voters", None, "Adults"], 7, ALL_OFF)
    assert list(weights) == [1, 1, 0]  # the third poll ends after day 7, so it does not count yet


def test_recency_halves_the_weight_every_14_days():
    weights = poll_weights([0, 14, 28], [None] * 3, ["A", "B", "C"], [None] * 3, 28, only("by_recency"))
    assert weights == pytest.approx([0.25, 0.5, 1])


def test_sample_size_weight_grows_with_its_square_root():
    weights = poll_weights([0, 0, 0, 0], [600, 2400, None, 10_000], ["A", "B", "C", "D"], [None] * 4, 0,
                           only("by_sample_size"))
    # 4 times as many people count twice as much; unknown counts as 600; above 5,000 counts as 5,000.
    assert weights == pytest.approx([1, 2, 1, np.sqrt(5000 / 600)])


def test_a_pollsters_recent_polls_share_their_weight():
    weights = poll_weights([0, 10, 20, 20], [None] * 4, ["A", "A", "A", "B"], [None] * 4, 20, only("by_pollster"))
    assert weights == pytest.approx([1 / np.sqrt(3)] * 3 + [1])


def test_polls_older_than_60_days_do_not_count_towards_a_pollsters_number():
    weights = poll_weights([0, 70], [None] * 2, ["A", "A"], [None] * 2, 70, only("by_pollster"))
    assert weights[1] == pytest.approx(1)  # the day-0 poll is 70 days old, outside the window


def test_population_weights():
    weights = poll_weights([0] * 4, [None] * 4, ["A", "B", "C", "D"],
                           ["Likely voters", "Registered voters", "Adults", None], 0, only("by_population"))
    assert weights == pytest.approx([1, 0.8, 0.6, 0.8])


def test_weighted_average_and_spread():
    average, spread = weighted_average(np.array([0.4, 0.6]), np.array([3.0, 1.0]))
    assert average == pytest.approx(0.45)
    assert spread == pytest.approx(np.sqrt(0.75 * 0.05**2 + 0.25 * 0.15**2))
    assert weighted_average(np.array([0.5]), np.array([0.0])) is None


def make_polls(rows):
    """A tiny polls table: (poll_id, pollster, end date, sample size, population, candidate, share) per row."""
    return pl.DataFrame(rows, schema=["poll_id", "pollster", "date", "sample_size", "population", "candidate", "share"],
                        orient="row")


def test_race_average_steps_on_poll_days_and_uses_only_polls_that_asked_about_the_candidate():
    polls = make_polls([
        ("p1", "A", date(2026, 10, 1), 600, "Likely voters", "Smith", 0.50),
        ("p1", "A", date(2026, 10, 1), 600, "Likely voters", "Jones", 0.40),
        ("p2", "B", date(2026, 10, 3), 600, "Likely voters", "Smith", 0.40),
        ("p2", "B", date(2026, 10, 3), 600, "Likely voters", "Jones", 0.50),
        ("p2", "B", date(2026, 10, 3), 600, "Likely voters", "Brown", 0.05),
    ])
    rows = pl.DataFrame(race_averages(polls, date(2026, 10, 3), ALL_OFF))
    smith = rows.filter(pl.col("candidate") == "Smith").sort("date")
    assert smith["average"].to_list() == pytest.approx([0.5, 0.5, 0.45])  # p2 counts from 3 October
    brown = rows.filter(pl.col("candidate") == "Brown")
    assert brown["date"].to_list() == [date(2026, 10, 3)]  # only p2 asked about Brown
    assert brown["average"][0] == pytest.approx(0.05)


def test_influence_is_the_poll_weight_on_the_last_day():
    polls = make_polls([
        ("p1", "A", date(2026, 10, 8), 2400, "Likely voters", "Smith", 0.5),
        ("p2", "B", date(2026, 10, 22), 600, "Registered voters", "Smith", 0.5),
    ])
    rules = dict.fromkeys(RULES, True)
    influence = {row["poll_id"]: row["influence"] for row in poll_influence(polls, date(2026, 10, 22), rules)}
    assert influence["p1"] == pytest.approx(0.5 * 2)  # 14 days old, 4 times the reference sample size
    assert influence["p2"] == pytest.approx(0.8)  # new, 600 people, registered voters
