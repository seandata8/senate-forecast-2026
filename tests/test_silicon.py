#### Preamble ####
# Purpose: Tests of the decision-model answers in silicon.py (Jev): each call's answer is a random pick weighted by
#          the model's probabilities, the same on a rerun. The API is replaced by a fake reply, so no calls are made.
# Author: Furkan Danisman
# Date: 24 October 2026
# Pre-requisites: uv sync

import io
import json
import os
import sys
from collections import Counter
from pathlib import Path

import pytest

os.environ.setdefault("OPENROUTER_API_KEY", "not-a-real-key")  # silicon reads a key on import; no call is made
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import silicon

OPTIONS = ["James Talarico", "Ken Paxton", "Undecided", "Would not vote"]
PROBABILITIES = {"James Talarico": 0.7, "Ken Paxton": 0.2, "Undecided": 0.1, "Would not vote": 0}


@pytest.fixture
def fake_decisions(monkeypatch):
    """Replace the decisions API with one that always returns PROBABILITIES, and record each request."""
    requests = []

    def fake_urlopen(call, timeout):
        requests.append(json.loads(call.data))
        reply = {
            "model": "typesafe/jev-1.14-test",
            "answers": {"answer": {"type": "choice", "choice": "James Talarico", "probabilities": PROBABILITIES}},
            "usage": {"input_tokens": 500, "output_tokens": 50, "cost": 0.00002},
        }
        return io.BytesIO(json.dumps(reply).encode())

    monkeypatch.setattr(silicon.urllib.request, "urlopen", fake_urlopen)
    return requests


def test_request_has_the_persona_question_and_options(fake_decisions):
    silicon.ask_decision_model("typesafe/jev-1.14", "a persona", "a question", OPTIONS, "key")
    request = fake_decisions[0]
    assert request["state"] == "a persona"
    assert request["questions"]["answer"]["instructions"] == "a question"
    assert list(request["questions"]["answer"]["criteria"]) == OPTIONS


def test_answers_are_weighted_random_picks_not_always_the_most_likely(fake_decisions):
    answers = Counter(
        silicon.ask_decision_model("typesafe/jev-1.14", "p", "q", OPTIONS, f"key {i}")[0] for i in range(2000)
    )
    assert answers["Would not vote"] == 0  # probability 0 is never picked
    assert answers["James Talarico"] / 2000 == pytest.approx(0.7, abs=0.04)
    assert answers["Ken Paxton"] / 2000 == pytest.approx(0.2, abs=0.04)
    assert answers["Undecided"] / 2000 == pytest.approx(0.1, abs=0.03)


def test_the_same_call_gives_the_same_answer(fake_decisions):
    first = silicon.ask_decision_model("typesafe/jev-1.14", "p", "q", OPTIONS, "same key")[0]
    assert all(silicon.ask_decision_model("typesafe/jev-1.14", "p", "q", OPTIONS, "same key")[0] == first for _ in range(20))


def test_usage_and_probabilities_are_returned(fake_decisions):
    _, model, usage, probabilities = silicon.ask_decision_model("typesafe/jev-1.14", "p", "q", OPTIONS, "key")
    assert model == "typesafe/jev-1.14-test"
    assert usage["cost"] == 0.00002
    assert probabilities == PROBABILITIES


def test_the_decision_models_listed_in_queries_match_silicon():
    from senate_forecast_2026.queries import DECISION_MODELS
    assert DECISION_MODELS == silicon.DECISION_MODELS
