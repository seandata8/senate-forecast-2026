#### Preamble ####
# Purpose: Tests for the forecast's website numbers (src/senate_forecast_2026/forecast_summary.py), on small made-up
#          simulations and answers whose results can be worked out by hand.
# Author: Furkan Danisman
# Date: 25 October 2026
# Pre-requisites: none
# Run from the repo root: uv run pytest

import polars as pl
import pytest

from senate_forecast_2026.forecast_summary import (
    answer_weights,
    race_summary,
    seat_summary,
    weighted_shares,
    with_versions,
)
from senate_forecast_2026.senate_simulation import SEATS_NOT_UP

CANDIDATES = pl.DataFrame({"candidate": ["Dee", "Ray"], "dem_caucus_probability": [1.0, 0.0]})


def one_race(democrat_wins):
    """Simulated elections of one race between Dee (Democrat) and Ray (Republican), one per item of `democrat_wins`."""
    rows = []
    for sim_id, dee_wins in enumerate(democrat_wins):
        dee = 0.55 if dee_wins else 0.45
        rows += [{"sim_id": sim_id, "state": "AL", "candidate": "Dee", "party": "Democrat", "share": dee, "winner": dee_wins},
                 {"sim_id": sim_id, "state": "AL", "candidate": "Ray", "party": "Republican", "share": 1 - dee,
                  "winner": not dee_wins}]
    return pl.DataFrame(rows)


def test_seat_summary_counts_the_seats_in_each_simulation():
    control, distribution = seat_summary(one_race([True, False, False, False]), CANDIDATES)
    seats = SEATS_NOT_UP["D"]  # the Democrats' seats not up in 2026; Dee adds one when she wins
    assert distribution.rows() == [(seats, 3, 0.75), (seats + 1, 1, 0.25)]
    assert control["seats"][0] == seats
    assert control["dem_control"][0] == 0  # 34 or 35 seats is never 51


def test_race_summary_gives_the_mean_share_and_the_chance_of_winning():
    races = race_summary(one_race([True, False, False, False]))
    dee = races.filter(pl.col("candidate") == "Dee").row(0, named=True)
    assert dee["share"] == pytest.approx((0.55 + 3 * 0.45) / 4)
    assert dee["chance_of_winning"] == pytest.approx(0.25)
    assert dee["share_lower"] == pytest.approx(0.45)
    assert dee["share_upper"] == pytest.approx(0.55)


def test_each_personas_draws_from_one_model_count_once():
    responses = pl.DataFrame({"persona_id": [1, 1, 1, 2], "model": ["jev", "jev", "kimi", "kimi"],
                              "draw": [0, 1, 0, 0], "answer": ["Democrat", "Republican", "Democrat", "Republican"]})
    personas = pl.DataFrame({"persona_id": [1, 2], "weight": [2.0, 1.0]})
    weighted = answer_weights(responses, personas)
    # Jev asked twice (draws 0 and 1), so each of persona 1's Jev answers counts half of their weight of 2.
    assert weighted.filter(pl.col("model") == "jev")["weight"].to_list() == [1.0, 1.0]
    shares = weighted_shares(weighted, ["model"]).sort("model", "answer")
    # Kimi: persona 1 (weight 2) says Democrat, persona 2 (weight 1) Republican, so Democrat has 2/3.
    assert shares.filter(pl.col("model") == "kimi")["share"].to_list() == pytest.approx([2 / 3, 1 / 3])
    assert shares.filter(pl.col("model") == "jev")["share"].to_list() == pytest.approx([0.5, 0.5])


def test_with_versions_averages_the_models_for_all_and_for_each_approach():
    per_model = pl.DataFrame({"approach": ["a", "a", "b"], "model": ["m1", "m2", "m3"], "answer": ["D", "D", "D"],
                              "share": [0.2, 0.4, 0.9]})
    versions = with_versions(per_model, ["answer"], ["share"])
    average = versions.filter(pl.col("model") == "average").sort("version_type", "version")
    assert average.select("version_type", "version").rows() == [("all", "all"), ("approach", "a"), ("approach", "b")]
    assert average["share"].to_list() == pytest.approx([0.5, 0.3, 0.9])
    assert versions.filter(pl.col("version_type") == "model").height == 3


def test_with_versions_has_no_approach_versions_with_one_approach():
    per_model = pl.DataFrame({"approach": ["a", "a"], "model": ["m1", "m2"], "answer": ["D", "D"], "share": [0.2, 0.4]})
    assert set(with_versions(per_model, ["answer"], ["share"])["version_type"]) == {"all", "model"}


def test_with_versions_can_count_a_missing_answer_as_zero():
    per_model = pl.DataFrame({"approach": ["a", "a", "a"], "model": ["m1", "m2", "m1"], "answer": ["D", "D", "Other"],
                              "share": [0.5, 0.7, 0.5]})
    versions = with_versions(per_model, ["answer"], ["share"], missing_is_zero=True)
    other = versions.filter((pl.col("version") == "all") & (pl.col("answer") == "Other"))
    assert other["share"].to_list() == pytest.approx([0.25])
