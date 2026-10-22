#### Preamble ####
# Purpose: Shared functions and numbers for simulating the Senate election: the Monte Carlo simulation of the
#          35 races (simulate_races), its state error (combined_state_error_sd), the seat count (count_seats),
#          and the seat constants.
#          Used by:
#            #1  scripts/00-simulate_data.py: combined_state_error_sd(), simulate_races() and count_seats() on made-up shares
#            #1  tests/test_simulated_data.py: count_seats(), combined_state_error_sd() and the seat constants
#            #3  the candidates script: INDEPENDENT_DEM_CAUCUS_PROBABILITY for the independents
#            #8  the forecast script: combined_state_error_sd() and simulate_races() on the real post-stratified shares
#            #9  the real-data tests: count_seats(), to check seat totals
#            #12 the summary script: count_seats() for the seat distribution and chance of Democratic control
# Author: Sean Murphy
# Date: 21 October 2026
# Pre-requisites: uv add polars numpy

import numpy as np
import polars as pl

# Seats not up in 2026, by caucus. The 35 races decide the other 35 of the 100.
# Current Senate: 53 Republican, 47 in the Democratic caucus (45 Democrats plus King and Sanders, who are not up).
# Up in 2026: 22 Republican-held, 13 Democratic-held. Check against the real candidate list in #3.
SEATS_NOT_UP = {"D": 34, "R": 31}
SEATS_FOR_CONTROL = 51  # Democrats need 51; at 50-50 the Vice President (a Republican) breaks ties

# Sean: an independent has to choose a caucus to get committee assignments (Osborn has said so), and every
# independent senator of the last two decades has caucused with the Democrats. So each independent gets a
# probability of caucusing with the Democrats if they win, and every seat ends up Democratic or Republican.
# Rough guesses, by state:
INDEPENDENT_DEM_CAUCUS_PROBABILITY = {
    "ID": 0.80,  # Todd Achilles
    "MT": 0.70,  # Seth Bodnar
    "NE": 0.60,  # Dan Osborn
    "SD": 0.70,  # Brian Bengs
}

# Size of the polling-style error added in each simulated election, in vote share.
# The national error moves every state the same way (polls tend to miss in the same direction);
# the state error is separate for each race.
# These are polling-sized. The state error passed to simulate_races() also includes the model's own uncertainty:
# see combined_state_error_sd() below.
SHARE_DECIMALS = 10  # see simulate_races()
NATIONAL_ERROR_SD = 0.03
STATE_ERROR_SD = 0.04


def combined_state_error_sd(model_standard_error):
    """The state error for simulate_races(): the polling-sized STATE_ERROR_SD combined with the model's own
    uncertainty, `model_standard_error` (a typical standard error of the model's state vote shares).
    Independent errors combine as the square root of the sum of their squares."""
    return (STATE_ERROR_SD**2 + model_standard_error**2) ** 0.5


def simulate_races(state_shares, n_sims=10_000, national_error_sd=NATIONAL_ERROR_SD, state_error_sd=STATE_ERROR_SD, seed=2026):
    """Simulate every race `n_sims` times.

    `state_shares` has one row per candidate: state, candidate, party, share (shares sum to 1 within each state).
    Returns one row per simulated election, state and candidate: sim_id, state, candidate, party, share, winner.

    In each simulated election, the national error plus the state's own error is the "swing": that much vote share
    moves from the Republican candidate(s) to everyone else (a negative swing moves it the other way). Within each
    side, candidates keep their relative sizes, so the shares still sum to 1. The winner has the highest share.
    This also covers Georgia's runoff: the top two would meet again, and the leader of the two also wins that.
    """
    # Round the starting shares to 10 decimal places. Polars adds numbers up in parallel, so the shares that come
    # in can differ in their last digit from one run to the next; rounding makes every rerun give identical files.
    state_shares = state_shares.with_columns(pl.col("share").round(SHARE_DECIMALS))
    random_generator = np.random.default_rng(seed)

    # One national error per simulated election, shared by every state.
    elections = pl.DataFrame({
        "sim_id": np.arange(n_sims),
        "national_error": random_generator.normal(0, national_error_sd, n_sims),
    })

    # Every state in every simulated election, each with its own error.
    states = pl.DataFrame({"state": state_shares["state"].unique().sort()})
    swings = elections.join(states, how="cross")
    swings = swings.with_columns(
        state_error=pl.Series(random_generator.normal(0, state_error_sd, swings.height)),
    ).with_columns(swing=pl.col("national_error") + pl.col("state_error"))

    # Each state's Republican total before and after the swing. Kept between 1% and 99% so no side disappears.
    republican_totals = state_shares.group_by("state").agg(
        republican_total=pl.col("share").filter(pl.col("party") == "Republican").sum(),
    )
    swings = swings.join(republican_totals, on="state", validate="m:1").with_columns(
        new_republican_total=(pl.col("republican_total") - pl.col("swing")).clip(0.01, 0.99),
    )

    # Every candidate in every simulated election. Republicans are scaled to the new Republican total,
    # everyone else to what is left, so each candidate keeps their size relative to their own side.
    is_republican = pl.col("party") == "Republican"
    republican_scale = pl.col("new_republican_total") / pl.col("republican_total")
    others_scale = (1 - pl.col("new_republican_total")) / (1 - pl.col("republican_total"))
    # Many-to-many on purpose: each candidate row meets every simulated election in its state.
    forecast = state_shares.join(swings, on="state").with_columns(
        share=pl.col("share") * pl.when(is_republican).then(republican_scale).otherwise(others_scale),
    )

    forecast = forecast.with_columns(winner=pl.col("share") == pl.col("share").max().over("sim_id", "state"))
    return forecast.select("sim_id", "state", "candidate", "party", "share", "winner").sort("sim_id", "state", "candidate")


def count_seats(forecast, candidates, seed=2026):
    """Seats per caucus in each simulated election: sim_id, dem_seats, rep_seats, dem_control.

    In each simulated election, every winner joins the Democrats with their `dem_caucus_probability` from
    `candidates`: always for a Democrat (1), never for a Republican (0), and by chance for an independent.
    Seats not up in 2026 are added to each side, so dem_seats + rep_seats is always 100.
    The draw is seeded, so the same forecast always gives the same seat counts."""
    random_generator = np.random.default_rng(seed)
    winners = (
        forecast.filter(pl.col("winner"))
        .join(candidates.select("candidate", "dem_caucus_probability"), on="candidate", validate="m:1")
        .sort("sim_id", "state")  # a fixed row order, so the seeded draw below lands on the same rows every time
    )
    # A random number below the probability means the winner joins the Democrats: always for 1, never for 0.
    winners = winners.with_columns(
        joins_democrats=pl.Series(random_generator.random(winners.height)) < pl.col("dem_caucus_probability"),
    )
    seats = winners.group_by("sim_id").agg(
        dem_seats=pl.col("joins_democrats").sum() + SEATS_NOT_UP["D"],
        rep_seats=(~pl.col("joins_democrats")).sum() + SEATS_NOT_UP["R"],
    )
    return seats.with_columns(dem_control=pl.col("dem_seats") >= SEATS_FOR_CONTROL).sort("sim_id")
