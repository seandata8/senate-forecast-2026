#### Preamble ####
# Purpose: Tests for the simulated data in data/00-simulated_data/: each file against its agreed schema,
#          and the files against each other (ids match, answers are real candidates, shares sum to 1, ...).
#          #9 writes the same checks for the real data in a separate file, as the rubric asks.
# Author: Sean Murphy
# Date: 21 October 2026
# Pre-requisites: uv run scripts/00-simulate_data.py
# Run from the repo root: uv run pytest


import polars as pl
import pytest
from scipy.stats import chisquare

from senate_forecast_2026.paths import SIMULATED_DATA
from senate_forecast_2026.schemas import (
    AGE_GROUPS,
    EDUCATION,
    FILE_SCHEMAS,
    GENDERS,
    GENERIC_ANSWERS,
    NON_CANDIDATE_ANSWERS,
    PARTY_GROUP_OF,
    PARTY_GROUPS,
    PARTY_IDS,
    RACES,
    STATES,
)
from senate_forecast_2026.senate_simulation import (
    SEATS_FOR_CONTROL,
    SEATS_NOT_UP,
    STATE_ERROR_SD,
    combined_state_error_sd,
    count_seats,
)
from senate_forecast_2026.simulation_settings import PERSONA_SHARES

DATA_FOLDER = SIMULATED_DATA
RESPONSE_FILES = ["responses_sean", "responses_furkan", "responses"]  # same columns, so they get the same checks


@pytest.fixture(scope="module")
def data():
    """All six files, read once for the whole module."""
    return {name: pl.read_parquet(DATA_FOLDER / f"{name}.parquet") for name in FILE_SCHEMAS}


def share_of(table, group_column, group, outcome_column, outcomes):
    """One cell of a cross-tab: among rows where `group_column` is `group`, the share whose `outcome_column` is in `outcomes`."""
    in_group = table.filter(pl.col(group_column) == group)
    return in_group[outcome_column].is_in(outcomes).mean()


@pytest.fixture(scope="module")
def seats(data):
    """Seats per caucus in each simulated election."""
    return count_seats(data["forecast"], data["candidates"])


#### Each file against its schema ####

@pytest.mark.parametrize("name", FILE_SCHEMAS)
def test_matches_schema(data, name):
    # Columns, types and allowed values; lazy=True lists every failure, not just the first.
    FILE_SCHEMAS[name].validate(data[name], lazy=True)


#### Personas and candidates ####

def test_every_state_has_personas_and_candidates(data):
    assert set(data["personas"]["state"]) == set(STATES)
    assert set(data["candidates"]["state"]) == set(STATES)


def test_same_number_of_personas_per_state(data):
    personas_per_state = data["personas"]["state"].value_counts()["count"]
    assert personas_per_state.min() == personas_per_state.max()


def test_every_race_has_a_republican_and_a_challenger(data):
    # seats.simulate_races moves vote share between Republicans and everyone else, so both sides must exist.
    sides = data["candidates"].group_by("state").agg(
        republicans=(pl.col("party") == "Republican").sum(),
        challengers=(pl.col("party") != "Republican").sum(),
    )
    assert (sides["republicans"] >= 1).all()
    assert (sides["challengers"] >= 1).all()


def test_at_most_one_incumbent_per_state(data):
    incumbents_per_state = data["candidates"].group_by("state").agg(pl.col("incumbent").sum())["incumbent"]
    assert incumbents_per_state.max() <= 1


def test_caucus_probability_matches_party(data):
    # Democrats always caucus with the Democrats (1) and Republicans never (0); only others are in between.
    candidates = data["candidates"]
    assert (candidates.filter(pl.col("party") == "Democrat")["dem_caucus_probability"] == 1).all()
    assert (candidates.filter(pl.col("party") == "Republican")["dem_caucus_probability"] == 0).all()


#### Responses ####

@pytest.mark.parametrize("name", RESPONSE_FILES)
def test_responses_belong_to_known_personas(data, name):
    # Every answer comes from a persona in personas.parquet, in that persona's own state.
    persona_states = data["personas"].select("persona_id", persona_state="state")
    responses = data[name].join(persona_states, on="persona_id", how="left", validate="m:1")
    assert responses.height == data[name].height  # the join neither lost nor duplicated rows
    assert responses["persona_state"].null_count() == 0
    assert (responses["state"] == responses["persona_state"]).all()


@pytest.mark.parametrize("name", RESPONSE_FILES)
def test_one_answer_per_persona_model_draw_question(data, name):
    one_answer_each = ["approach", "persona_id", "model", "draw", "question"]
    assert data[name].select(one_answer_each).is_duplicated().sum() == 0


@pytest.mark.parametrize("name", RESPONSE_FILES)
def test_every_persona_answered_by_every_model_and_draw(data, name):
    # For the Senate question, each approach and model has exactly one row per persona per draw.
    senate = data[name].filter(pl.col("question") == "senate")
    expected_rows = data["personas"].height * senate["draw"].n_unique()
    rows_per_model = senate.group_by("approach", "model").len()["len"]
    assert (rows_per_model == expected_rows).all()


@pytest.mark.parametrize("name", RESPONSE_FILES)
def test_senate_answers_are_candidates_in_that_state(data, name):
    # A Senate answer must be a candidate on that persona's ballot, undecided, would not vote, or missing.
    candidate_answers = data[name].filter(
        (pl.col("question") == "senate")
        & pl.col("answer").is_not_null()
        & ~pl.col("answer").is_in(NON_CANDIDATE_ANSWERS)
    )
    ballot = data["candidates"].select("state", answer="candidate")
    not_on_ballot = candidate_answers.join(ballot, on=["state", "answer"], how="anti")
    assert not_on_ballot.height == 0, not_on_ballot.head()


@pytest.mark.parametrize("name", RESPONSE_FILES)
def test_generic_answers_are_parties(data, name):
    generic = data[name].filter((pl.col("question") == "generic") & pl.col("answer").is_not_null())
    assert generic["answer"].is_in(GENERIC_ANSWERS).all()


@pytest.mark.parametrize("name", RESPONSE_FILES)
def test_alaska_final_round_only_in_alaska(data, name):
    final_round = data[name].filter(pl.col("question") == "alaska_final")
    assert (final_round["state"] == "AK").all()


@pytest.mark.parametrize("name", RESPONSE_FILES)
def test_few_missing_answers(data, name):
    # Missing answers are kept (as null) and counted, not silently dropped. More than 5% would mean a broken run.
    assert data[name]["answer"].null_count() / data[name].height < 0.05


def test_each_run_is_one_persons_approach(data):
    assert set(data["responses_sean"]["approach"]) == {"sean"}
    assert set(data["responses_furkan"]["approach"]) == {"furkan"}


def test_responses_are_both_runs_stacked(data):
    # responses (#7) must be exactly the two runs together: nothing lost, added or changed.
    responses = data["responses"]
    runs = pl.concat([data["responses_sean"], data["responses_furkan"]])
    assert responses.height == runs.height
    # nulls_equal: a missing answer must match a missing answer.
    assert responses.join(runs, on=responses.columns, how="anti", nulls_equal=True).height == 0
    assert runs.join(responses, on=responses.columns, how="anti", nulls_equal=True).height == 0


#### Cross-tabs: variables relate the way they should ####

def test_party_id_matches_2024_vote(data):
    # Among personas who voted for Harris or Trump, party ID should mostly predict which.
    two_party_voters = data["personas"].filter(pl.col("vote_2024").is_in(["Kamala Harris", "Donald Trump"]))
    assert share_of(two_party_voters, "party_id", "Strong Democrat", "vote_2024", ["Kamala Harris"]) > 0.8
    assert share_of(two_party_voters, "party_id", "Strong Republican", "vote_2024", ["Donald Trump"]) > 0.8


def test_party_id_matches_ideology(data):
    personas = data["personas"]
    liberal, conservative = ["Very liberal", "Liberal"], ["Conservative", "Very conservative"]
    assert share_of(personas, "party_id", "Strong Democrat", "ideology", liberal) > 0.5
    assert share_of(personas, "party_id", "Strong Republican", "ideology", conservative) > 0.5


def test_party_id_matches_senate_choice(data):
    # Cross-tab of the persona's party ID against the party of the candidate they chose.
    chosen = (
        data["responses"]
        .filter(pl.col("question") == "senate")
        .join(data["personas"].select("persona_id", "party_id"), on="persona_id", validate="m:1")
        .join(data["candidates"].select(answer="candidate", chosen_party="party"), on="answer", validate="m:1")
    )
    assert share_of(chosen, "party_id", "Strong Democrat", "chosen_party", ["Democrat", "Independent"]) > 0.8
    assert share_of(chosen, "party_id", "Strong Republican", "chosen_party", ["Republican"]) > 0.8


def test_white_personas_lean_more_republican_than_black_personas(data):
    # The simulation gives Black personas a strong Democratic effect; it should show up in party ID.
    republican = ["Strong Republican", "Not very strong Republican", "Lean Republican"]
    personas = data["personas"]
    assert share_of(personas, "race", "White", "party_id", republican) > share_of(personas, "race", "Black", "party_id", republican)


#### Goodness of fit: simulated shares match what the simulation was given ####

# Gender and race are left out: some of their categories are so small (e.g. 0.2% "Other" gender) that fewer than
# 5 personas are expected in them, and the chi-square test is not reliable below that.
@pytest.mark.parametrize("column", ["age_group", "education", "income", "religion", "marital_status", "sexuality", "registered"])
def test_persona_shares_fit_the_intended_shares(data, column):
    categories, intended_shares = PERSONA_SHARES[column]
    counts = data["personas"][column].value_counts()
    observed = [counts.filter(pl.col(column) == category)["count"].sum() for category in categories]
    total = sum(observed)
    expected = [share / sum(intended_shares) * total for share in intended_shares]
    assert min(expected) >= 5  # the chi-square test needs at least 5 expected in every category
    # A p-value below 0.001 would mean the simulated shares are very unlikely to come from the intended ones.
    assert chisquare(observed, expected).pvalue > 0.001


#### Frame ####

def test_frame_has_every_cell_once(data):
    frame = data["frame"]
    cell_columns = ["state", "age_group", "gender", "race", "education", "party_group"]
    assert frame.height == len(STATES) * len(AGE_GROUPS) * len(GENDERS) * len(RACES) * len(EDUCATION) * len(PARTY_GROUPS)
    assert frame.select(cell_columns).is_duplicated().sum() == 0


def test_every_party_id_has_a_party_group():
    # #8 collapses each persona's party_id to a frame party_group, so every party ID needs one.
    assert set(PARTY_GROUP_OF) == set(PARTY_IDS)
    assert set(PARTY_GROUP_OF.values()) == set(PARTY_GROUPS)


def test_every_state_has_voters(data):
    voters_per_state = data["frame"].group_by("state").agg(pl.col("count").sum())["count"]
    assert (voters_per_state > 0).all()


#### Forecast ####

def test_forecast_candidates_are_on_the_ballot(data):
    forecast_candidates = data["forecast"].select("state", "candidate", "party").unique()
    assert forecast_candidates.join(data["candidates"], on=["state", "candidate", "party"], how="anti").height == 0


def test_shares_sum_to_one_in_each_race(data):
    race_totals = data["forecast"].group_by("sim_id", "state").agg(pl.col("share").sum())["share"]
    assert ((race_totals - 1).abs() < 1e-9).all()


def test_one_winner_per_race_with_the_highest_share(data):
    races = data["forecast"].group_by("sim_id", "state").agg(
        winners=pl.col("winner").sum(),
        winner_share=pl.col("share").filter(pl.col("winner")).max(),
        highest_share=pl.col("share").max(),
    )
    assert (races["winners"] == 1).all()
    assert (races["winner_share"] == races["highest_share"]).all()


def test_every_simulation_has_every_race(data):
    states_per_simulation = data["forecast"].group_by("sim_id").agg(pl.col("state").n_unique())["state"]
    assert (states_per_simulation == len(STATES)).all()


def test_seats_add_up_to_100(data, seats):
    assert sum(SEATS_NOT_UP.values()) + len(STATES) == 100
    assert seats.height == data["forecast"]["sim_id"].n_unique()
    assert (seats["dem_seats"] + seats["rep_seats"] == 100).all()  # every seat goes to one side


def test_combined_error_adds_the_models_uncertainty():
    # With no model uncertainty the error is the polling-sized one; any model uncertainty makes it bigger.
    assert combined_state_error_sd(0) == STATE_ERROR_SD
    assert combined_state_error_sd(0.03) == pytest.approx(0.05)  # sqrt(0.04^2 + 0.03^2)


def test_democratic_control_means_51_seats(seats):
    assert (seats["dem_control"] == (seats["dem_seats"] >= SEATS_FOR_CONTROL)).all()
