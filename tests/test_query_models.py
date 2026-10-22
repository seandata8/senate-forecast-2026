#### Preamble ####
# Purpose: Tests of the query-models code (task #5) on the simulated personas and candidates, with a fake model,
#          so they make no API calls and cost nothing.
# Author: Furkan Danisman
# Date: 22 October 2026
# Pre-requisites: uv run scripts/00-simulate_data.py

import random
from pathlib import Path

import polars as pl
import pytest

from senate_forecast_2026.queries import (
    QUESTION_WORDINGS,
    STATE_NAMES,
    V2_PAST_ELECTIONS,
    persona_to_prompt,
    query_personas,
    questions_for_state,
)
from senate_forecast_2026.schemas import GENERIC_ANSWERS, NON_CANDIDATE_ANSWERS, STATES, Responses

SIMULATED = Path("data/00-simulated_data")
MODELS = ["provider-1/model-x", "provider-2/model-y"]
DRAWS = 2


@pytest.fixture(scope="module")
def personas():
    return pl.read_parquet(SIMULATED / "personas.parquet")


@pytest.fixture(scope="module")
def candidates():
    return pl.read_parquet(SIMULATED / "candidates.parquet")


def fake_ask(model, persona, question, options, temperature, draw):
    """Stands in for silicon.ask: a random option, or no usable answer 5% of the time, as a failed call is."""
    random_generator = random.Random(f"{model}|{draw}|{persona}|{question}")
    answer = None if random_generator.random() < 0.05 else random_generator.choice(options)
    return {"answer": answer, "input_tokens": 300, "output_tokens": 10, "cost": 0.0001}


@pytest.fixture(scope="module", params=list(QUESTION_WORDINGS))
def responses(request, personas, candidates):
    return query_personas(personas, candidates, "furkan", MODELS, DRAWS, 1.0, request.param, fake_ask)


def test_prompt_has_the_persona_but_not_the_reference_columns(personas):
    persona = personas.row(0, named=True)
    prompt = persona_to_prompt(persona)
    assert STATE_NAMES[persona["state"]] in prompt
    assert persona["party_id"] in prompt
    assert persona["vote_2024"] is None or persona["vote_2024"] not in prompt
    assert str(persona["weight"]) not in prompt


@pytest.mark.parametrize("wording", QUESTION_WORDINGS)
def test_every_state_has_a_senate_and_a_generic_question(candidates, wording):
    for state in STATES:
        questions = [question["question"] for question in questions_for_state(state, candidates, wording)]
        expected = ["senate", "generic"] + (["alaska_final"] if state == "AK" else [])
        assert questions == expected


@pytest.mark.parametrize("wording", QUESTION_WORDINGS)
def test_senate_options_are_the_states_own_candidates(candidates, wording):
    for state in STATES:
        senate = questions_for_state(state, candidates, wording)[0]
        own_candidates = candidates.filter(pl.col("state") == state)["candidate"].to_list()
        assert senate["options"] == own_candidates + NON_CANDIDATE_ANSWERS
        for candidate in own_candidates:
            assert candidate in senate["text"]


@pytest.mark.parametrize("wording", QUESTION_WORDINGS)
def test_generic_options(candidates, wording):
    generic = questions_for_state("TX", candidates, wording)[1]
    assert generic["options"] == GENERIC_ANSWERS


@pytest.mark.parametrize("wording", QUESTION_WORDINGS)
def test_alaska_final_round_is_the_democrat_against_the_incumbent(candidates, wording):
    final_round = questions_for_state("AK", candidates, wording)[2]
    alaska = candidates.filter(pl.col("state") == "AK")
    democrat = alaska.filter(pl.col("party") == "Democrat")["candidate"].item()
    incumbent = alaska.filter(pl.col("incumbent"))["candidate"].item()
    assert final_round["options"] == [democrat, incumbent] + NON_CANDIDATE_ANSWERS


def test_wordings_differ_only_in_text(candidates):
    """v1 and v2 ask the same questions with the same options; only v2 has the past-elections sentence."""
    for state in STATES:
        v1 = questions_for_state(state, candidates, "v1")
        v2 = questions_for_state(state, candidates, "v2")
        assert [question["options"] for question in v1] == [question["options"] for question in v2]
        assert all(V2_PAST_ELECTIONS in question["text"] for question in v2)
        assert not any(V2_PAST_ELECTIONS in question["text"] for question in v1)


def test_responses_match_the_schema(responses):
    Responses.validate(responses, lazy=True)


def test_one_answer_per_persona_question_model_and_draw(responses, personas):
    n_alaska = personas.filter(pl.col("state") == "AK").height
    expected = (personas.height * 2 + n_alaska) * len(MODELS) * DRAWS
    assert responses.height == expected
    assert responses.select("persona_id", "model", "draw", "question").is_duplicated().sum() == 0


def test_answers_are_from_the_personas_own_ballot(responses, candidates):
    senate = responses.filter((pl.col("question") == "senate") & ~pl.col("answer").is_in(NON_CANDIDATE_ANSWERS))
    candidate_states = senate.join(candidates.select("candidate", pl.col("state").alias("candidate_state")),
                                   left_on="answer", right_on="candidate")
    assert candidate_states.height == senate.drop_nulls("answer").height
    assert (candidate_states["state"] == candidate_states["candidate_state"]).all()


def test_missing_answers_are_kept(responses):
    assert responses["answer"].null_count() > 0
