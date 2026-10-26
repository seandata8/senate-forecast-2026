#### Preamble ####
# Purpose: Tests for the real data in data/02-analysis_data/ and data/03-summary_data/ (#9): each file against its
#          agreed schema, the files against each other (ids match, answers are real candidates, shares sum to 1, ...),
#          and the personas and frame against the real 2024 results. The same kinds of checks as
#          tests/test_simulated_data.py, in a separate file as the rubric asks. A file that has not been made yet
#          (e.g. responses_sean before Sean's full run, or the forecast before #7) is skipped, not failed, so these
#          tests check it as soon as it exists.
# Author: Sean Murphy
# Date: 26 October 2026
# Pre-requisites: the real data files, made by the numbered scripts (most are committed)
# Run from the repo root: uv run pytest

from datetime import date

import polars as pl
import pytest
from helpers import share_of
from scipy.stats import pearsonr

from senate_forecast_2026.paths import ANALYSIS_DATA, DATA, RAW_PRESIDENT_RESULTS, SUMMARY_DATA
from senate_forecast_2026.queries import APPROACH_SETTINGS, draws_by_model
from senate_forecast_2026.schemas import (
    AGE_GROUPS,
    EDUCATION,
    FILE_SCHEMAS,
    GENDERS,
    GENERIC_ANSWERS,
    NON_CANDIDATE_ANSWERS,
    PARTY_GROUPS,
    RACES,
    STATES,
    RunCosts,
)
from senate_forecast_2026.senate_simulation import SEATS_FOR_CONTROL, count_seats

DATA_FOLDERS = [ANALYSIS_DATA, SUMMARY_DATA]
# run_costs is a CSV log in data/, not a parquet, so it has its own test.
REAL_FILES = [name for name in FILE_SCHEMAS if name != "run_costs"]
RESPONSE_FILES = ["responses_sean", "responses_furkan", "responses"]  # same columns, so they get the same checks
APPROACH_OF = {"responses_sean": "sean", "responses_furkan": "furkan"}
PERSONA_FILES = [*RESPONSE_FILES, "model_checks_sean", "model_checks_furkan"]  # files with a persona_id and state
FREEZE_DATE = date(2026, 11, 2)  # the website freezes at the end of this day, so no data can be from later


@pytest.fixture(scope="module")
def data():
    """Every real file that exists so far, read once for the whole module."""
    files = {}
    for name in REAL_FILES:
        for folder in DATA_FOLDERS:
            if (folder / f"{name}.parquet").exists():
                files[name] = pl.read_parquet(folder / f"{name}.parquet")
    return files


def file_or_skip(data, name):
    """The file called `name`, or skip the test if it has not been made yet."""
    if name not in data:
        pytest.skip(f"{name} has not been made yet")
    return data[name]


#### Each file against its schema ####

@pytest.mark.parametrize("name", REAL_FILES)
def test_matches_schema(data, name):
    # Columns, types and allowed values; lazy=True lists every failure, not just the first.
    FILE_SCHEMAS[name].validate(file_or_skip(data, name), lazy=True)


def test_run_costs_match_schema():
    RunCosts.validate(pl.read_csv(DATA / "run_costs.csv"), lazy=True)


#### Personas and candidates ####

def test_every_state_has_personas_and_candidates(data):
    assert set(file_or_skip(data, "personas")["state"]) == set(STATES)
    assert set(file_or_skip(data, "candidates")["state"]) == set(STATES)


def test_30_personas_per_state(data):
    # 04-build_personas.py takes 30 respondents from each state; fewer would mean the full CES file was not used.
    personas_per_state = file_or_skip(data, "personas")["state"].value_counts()["count"]
    assert (personas_per_state == 30).all()


def test_each_persona_once(data):
    assert file_or_skip(data, "personas")["persona_id"].is_duplicated().sum() == 0


def test_every_race_has_a_republican_and_a_challenger(data):
    # senate_simulation moves vote share between Republicans and everyone else, so both sides must exist.
    sides = file_or_skip(data, "candidates").group_by("state").agg(
        republicans=(pl.col("party") == "Republican").sum(),
        challengers=(pl.col("party") != "Republican").sum(),
    )
    assert (sides["republicans"] >= 1).all()
    assert (sides["challengers"] >= 1).all()


def test_each_candidate_once_per_state(data):
    assert file_or_skip(data, "candidates").select("state", "candidate").is_duplicated().sum() == 0


def test_at_most_one_incumbent_per_state(data):
    incumbents_per_state = file_or_skip(data, "candidates").group_by("state").agg(pl.col("incumbent").sum())["incumbent"]
    assert incumbents_per_state.max() <= 1


def test_caucus_probability_matches_party(data):
    # Democrats always caucus with the Democrats (1) and Republicans never (0); only others are in between.
    candidates = file_or_skip(data, "candidates")
    assert (candidates.filter(pl.col("party") == "Democrat")["dem_caucus_probability"] == 1).all()
    assert (candidates.filter(pl.col("party") == "Republican")["dem_caucus_probability"] == 0).all()


#### Responses and model checks ####

@pytest.mark.parametrize("name", PERSONA_FILES)
def test_answers_belong_to_known_personas(data, name):
    # Every answer comes from a persona in personas.parquet, in that persona's own state.
    answers = file_or_skip(data, name)
    persona_states = file_or_skip(data, "personas").select("persona_id", persona_state="state")
    joined = answers.join(persona_states, on="persona_id", how="left", validate="m:1")
    assert joined.height == answers.height  # the join neither lost nor duplicated rows
    assert joined["persona_state"].null_count() == 0
    assert (joined["state"] == joined["persona_state"]).all()


@pytest.mark.parametrize("name", RESPONSE_FILES)
def test_one_answer_per_persona_model_draw_question(data, name):
    one_answer_each = ["approach", "persona_id", "model", "draw", "question"]
    assert file_or_skip(data, name).select(one_answer_each).is_duplicated().sum() == 0


@pytest.mark.parametrize("name", RESPONSE_FILES)
def test_every_persona_answered_by_every_model_and_draw(data, name):
    # Each model has its own number of draws (Jev has 10), so each approach and model is checked on its own: one row
    # per persona per draw for the Senate and generic questions, and per Alaska persona for Alaska's final round.
    responses, personas = file_or_skip(data, name), file_or_skip(data, "personas")
    alaska_personas = personas.filter(pl.col("state") == "AK").height
    rows = responses.group_by("approach", "model").agg(
        draws=pl.col("draw").n_unique(),
        senate=(pl.col("question") == "senate").sum(),
        generic=(pl.col("question") == "generic").sum(),
        alaska_final=(pl.col("question") == "alaska_final").sum(),
    )
    assert (rows["senate"] == rows["draws"] * personas.height).all()
    assert (rows["generic"] == rows["draws"] * personas.height).all()
    assert (rows["alaska_final"] == rows["draws"] * alaska_personas).all()


@pytest.mark.parametrize("name", ["responses_sean", "responses_furkan"])
def test_each_run_uses_its_approach_settings(data, name):
    # A full run has the approach's models, each with its number of draws, as set in queries.py.
    responses = file_or_skip(data, name)
    approach = APPROACH_OF[name]
    settings = APPROACH_SETTINGS[approach]
    assert set(responses["approach"]) == {approach}
    draws = responses.group_by("model").agg(pl.col("draw").n_unique())
    assert dict(draws.iter_rows()) == draws_by_model(settings["models"], settings["draws"])


@pytest.mark.parametrize("name", RESPONSE_FILES)
def test_senate_answers_are_candidates_in_that_state(data, name):
    # A Senate answer must be a candidate on that persona's ballot, undecided, would not vote, or missing.
    candidate_answers = file_or_skip(data, name).filter(
        (pl.col("question") == "senate")
        & pl.col("answer").is_not_null()
        & ~pl.col("answer").is_in(NON_CANDIDATE_ANSWERS)
    )
    ballot = file_or_skip(data, "candidates").select("state", answer="candidate")
    not_on_ballot = candidate_answers.join(ballot, on=["state", "answer"], how="anti")
    assert not_on_ballot.height == 0, not_on_ballot.head()


@pytest.mark.parametrize("name", RESPONSE_FILES)
def test_generic_answers_are_parties(data, name):
    generic = file_or_skip(data, name).filter((pl.col("question") == "generic") & pl.col("answer").is_not_null())
    assert generic["answer"].is_in(GENERIC_ANSWERS).all()


@pytest.mark.parametrize("name", RESPONSE_FILES)
def test_alaska_final_round_only_in_alaska(data, name):
    final_round = file_or_skip(data, name).filter(pl.col("question") == "alaska_final")
    assert (final_round["state"] == "AK").all()


@pytest.mark.parametrize("name", RESPONSE_FILES)
def test_few_missing_answers(data, name):
    # Missing answers are kept (as null) and counted, not silently dropped. More than 5% would mean a broken run.
    responses = file_or_skip(data, name)
    assert responses["answer"].null_count() / responses.height < 0.05


def test_responses_are_both_runs_stacked(data):
    # responses (#7) must be exactly the two runs together: nothing lost, added or changed.
    responses = file_or_skip(data, "responses")
    runs = pl.concat([file_or_skip(data, "responses_sean"), file_or_skip(data, "responses_furkan")])
    assert responses.height == runs.height
    # nulls_equal: a missing answer must match a missing answer.
    assert responses.join(runs, on=responses.columns, how="anti", nulls_equal=True).height == 0
    assert runs.join(responses, on=responses.columns, how="anti", nulls_equal=True).height == 0


#### Cross-tabs: variables relate the way they should ####

def test_party_id_matches_2024_vote(data):
    # Among personas who voted for Harris or Trump, party ID should mostly predict which.
    two_party_voters = file_or_skip(data, "personas").filter(pl.col("vote_2024").is_in(["Kamala Harris", "Donald Trump"]))
    assert share_of(two_party_voters, "party_id", "Strong Democrat", "vote_2024", ["Kamala Harris"]) > 0.8
    assert share_of(two_party_voters, "party_id", "Strong Republican", "vote_2024", ["Donald Trump"]) > 0.8


def test_party_id_matches_ideology(data):
    personas = file_or_skip(data, "personas")
    liberal, conservative = ["Very liberal", "Liberal"], ["Conservative", "Very conservative"]
    assert share_of(personas, "party_id", "Strong Democrat", "ideology", liberal) > 0.5
    assert share_of(personas, "party_id", "Strong Republican", "ideology", conservative) > 0.5


@pytest.mark.parametrize("name", RESPONSE_FILES)
def test_party_id_matches_senate_choice(data, name):
    # Cross-tab of the persona's party ID against the party of the candidate the model chose for them, for each
    # model: a model that ignores the persona would fail this.
    chosen = (
        file_or_skip(data, name)
        .filter(pl.col("question") == "senate")
        .join(file_or_skip(data, "personas").select("persona_id", "party_id"), on="persona_id", validate="m:1")
        .join(file_or_skip(data, "candidates").select("state", answer="candidate", chosen_party="party"), on=["state", "answer"])
    )
    for model in chosen["model"].unique():
        by_model = chosen.filter(pl.col("model") == model)
        assert share_of(by_model, "party_id", "Strong Democrat", "chosen_party", ["Democrat", "Independent"]) > 0.8
        assert share_of(by_model, "party_id", "Strong Republican", "chosen_party", ["Republican"]) > 0.8


#### Against the real 2024 results ####

@pytest.fixture(scope="module")
def harris_share_2024(data):
    """Harris's share of the Harris and Trump vote in each state in 2024, from the real results."""
    return file_or_skip(data, "past_results").filter(pl.col("election") == "president_2024").select(
        "state", actual=pl.col("dem_share") / (pl.col("dem_share") + pl.col("rep_share"))
    )


def test_personas_vote_follows_the_real_2024_result(data, harris_share_2024):
    # Each state's weighted Harris share among the personas who voted Harris or Trump, against the real result. With
    # 30 personas a state each share is noisy, so this only asks that the states rise and fall together: a positive
    # correlation that is very unlikely to be chance (p < 0.01).
    two_party_voters = file_or_skip(data, "personas").filter(pl.col("vote_2024").is_in(["Kamala Harris", "Donald Trump"]))
    personas_share = two_party_voters.group_by("state").agg(
        personas=((pl.col("vote_2024") == "Kamala Harris") * pl.col("weight")).sum() / pl.col("weight").sum()
    )
    shares = personas_share.join(harris_share_2024, on="state", validate="1:1")
    correlation = pearsonr(shares["personas"], shares["actual"])
    assert correlation.statistic > 0 and correlation.pvalue < 0.01


def test_frame_party_mix_follows_the_real_2024_result(data, harris_share_2024):
    # The frame's Democrats as a share of Democrats and Republicans in each state should track Harris's real share
    # closely, because it is built from thousands of weighted CES voters, not 30.
    party_mix = file_or_skip(data, "frame").group_by("state").agg(
        democrats=pl.col("count").filter(pl.col("party_group") == "Democrat").sum(),
        republicans=pl.col("count").filter(pl.col("party_group") == "Republican").sum(),
    )
    shares = party_mix.join(harris_share_2024, on="state", validate="1:1").with_columns(
        frame=pl.col("democrats") / (pl.col("democrats") + pl.col("republicans"))
    )
    assert pearsonr(shares["frame"], shares["actual"]).statistic > 0.9


#### Frame ####

def test_frame_has_every_cell_once(data):
    frame = file_or_skip(data, "frame")
    cell_columns = ["state", "age_group", "gender", "race", "education", "party_group"]
    assert frame.height == len(STATES) * len(AGE_GROUPS) * len(GENDERS) * len(RACES) * len(EDUCATION) * len(PARTY_GROUPS)
    assert frame.select(cell_columns).is_duplicated().sum() == 0


def test_frame_counts_add_up_to_each_states_2024_voters(data):
    # 08-build_frame.py scales each state's cells to its real number of 2024 voters (the total votes for President).
    # Each cell is rounded to a whole voter, so a state's total can be off by at most half a voter per cell.
    frame = file_or_skip(data, "frame")
    president_2024 = pl.read_csv(RAW_PRESIDENT_RESULTS, infer_schema_length=10_000).filter(pl.col("year") == 2024)
    actual_voters = president_2024.group_by(pl.col("state_po").alias("state")).agg(pl.col("totalvotes").first())
    totals = frame.group_by("state").agg(pl.col("count").sum(), cells=pl.len()).join(actual_voters, on="state")
    assert totals.height == len(STATES)
    assert ((totals["count"] - totals["totalvotes"]).abs() <= totals["cells"] / 2).all()


#### Past results, polls and Polymarket ####

def test_past_results_have_president_2024_for_every_state(data):
    president_2024 = file_or_skip(data, "past_results").filter(pl.col("election") == "president_2024")
    assert set(president_2024["state"]) == set(STATES)


def test_past_results_shares_add_up_to_at_most_one(data):
    # Other candidates get the rest, so Democratic plus Republican can be less than 1 but never more.
    past_results = file_or_skip(data, "past_results")
    assert (past_results["dem_share"] + past_results["rep_share"] <= 1).all()


@pytest.mark.parametrize("name", ["polls", "polymarket"])
def test_candidates_are_on_the_ballot(data, name):
    # Polls and markets about primary candidates who lost would not compare with our forecast.
    asked_about = file_or_skip(data, name).select("state", "candidate").unique()
    not_on_ballot = asked_about.join(file_or_skip(data, "candidates"), on=["state", "candidate"], how="anti")
    assert not_on_ballot.height == 0, not_on_ballot


@pytest.mark.parametrize("name", ["polls", "polymarket"])
def test_nothing_after_the_freeze(data, name):
    assert file_or_skip(data, name)["date"].max() <= FREEZE_DATE


def test_polls_end_after_they_start(data):
    polls = file_or_skip(data, "polls")
    assert (polls["start_date"] <= polls["date"]).all()


def test_poll_shares_add_up_to_at_most_one(data):
    # Undecided and others take the rest; up to 1.02 allows for each candidate's share being rounded.
    poll_totals = file_or_skip(data, "polls").group_by("poll_id").agg(pl.col("share").sum())["share"]
    assert (poll_totals <= 1.02).all()


#### Forecast ####

def test_forecast_candidates_are_on_the_ballot(data):
    forecast_candidates = file_or_skip(data, "forecast").select("state", "candidate", "party").unique()
    assert forecast_candidates.join(file_or_skip(data, "candidates"), on=["state", "candidate", "party"], how="anti").height == 0


def test_shares_sum_to_one_in_each_race(data):
    race_totals = file_or_skip(data, "forecast").group_by("sim_id", "state").agg(pl.col("share").sum())["share"]
    assert ((race_totals - 1).abs() < 1e-9).all()


def test_one_winner_per_race_with_the_highest_share(data):
    races = file_or_skip(data, "forecast").group_by("sim_id", "state").agg(
        winners=pl.col("winner").sum(),
        winner_share=pl.col("share").filter(pl.col("winner")).max(),
        highest_share=pl.col("share").max(),
    )
    assert (races["winners"] == 1).all()
    assert (races["winner_share"] == races["highest_share"]).all()


def test_every_simulation_has_every_race(data):
    states_per_simulation = file_or_skip(data, "forecast").group_by("sim_id").agg(pl.col("state").n_unique())["state"]
    assert (states_per_simulation == len(STATES)).all()


def test_seats_add_up_to_100_and_control_means_51(data):
    seats = count_seats(file_or_skip(data, "forecast"), file_or_skip(data, "candidates"))
    assert (seats["dem_seats"] + seats["rep_seats"] == 100).all()  # every seat goes to one side
    assert (seats["dem_control"] == (seats["dem_seats"] >= SEATS_FOR_CONTROL)).all()
