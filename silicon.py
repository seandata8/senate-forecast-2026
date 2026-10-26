#### Preamble ####
# Purpose: Client, models, and one cached structured call, shared by the scripts that query models
# Author: Sean Murphy; per-question answer options, token counts and decision models added by Furkan Danisman
# Date: 7 October 2026; updated 22 and 24 October 2026
# Pre-requisites: uv add openai python-dotenv polars numpy; OPENROUTER_API_KEY in .env

import hashlib
import json
import os
import random
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
    timeout=60,
    max_retries=2,
)
# Local models served by Ollama's OpenAI-compatible API. Ollama ignores the key but the library requires one.
# Longer timeout because a local model on a laptop can be slow.
local_client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama", timeout=300, max_retries=2)

MODELS = ["deepseek/deepseek-v4-flash-0731", "z-ai/glm-5.3-flash", "meta/muse-glimmer-30b"]
# Not part of the worksheet; run deliberately for comparison. The "ollama/" prefix routes a model to local_client.
EXTRA_MODELS = ["ollama/gemma4:12b"]

# Decision models do not write text: given the options, they return a probability for each. OpenRouter serves them
# at a separate address. Each call's answer is a random pick weighted by those probabilities (not the most likely
# option), so repeated draws can differ the way a chat model's do at temperature 1.0.
DECISION_MODELS = ["typesafe/jev-1.14"]
DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"


def answer_schema(options):
    """The JSON the model must return: one answer, from `options`. The options differ by question and race
    (each state's own candidates), so the schema is built for each call."""
    return {
        "type": "object",
        "properties": {"answer": {"type": "string", "enum": options}},
        "required": ["answer"],
        "additionalProperties": False,
    }


BUDGET_USD = 5.00
CACHE = Path(__file__).parent / "cache"  # next to this file, wherever a script is run from
CACHE.mkdir(exist_ok=True)
spent = 0.0


def total_spent():
    """Dollars spent so far in this run. Call this rather than reading `spent`, which `import *` copies once."""
    return spent


def cache_key(model, persona, question, options, temperature=1.0, draw=0):
    """Every input to ask() that can change the answer, in one string. Change any one of them (even one character of
    the persona, or one answer option) and it is a new call."""
    return f"{model}|{temperature}|{draw}|{persona}|{question}|{json.dumps(options)}"


def cache_path(model, persona, question, options, temperature=1.0, draw=0):
    """The cache file of one call to ask(), named by its hashed cache key: it exists once that call has been answered."""
    raw = cache_key(model, persona, question, options, temperature, draw)
    return CACHE / (hashlib.sha256(raw.encode()).hexdigest() + ".json")


def ask(model, persona, question, options, temperature=1.0, draw=0):
    """One structured answer, chosen from `options`. Cached on everything that determines it, so a rerun costs nothing.
    `draw` lets you ask the same persona the same question more than once."""
    global spent  # we add to the module-level total below, not a local copy

    raw = cache_key(model, persona, question, options, temperature, draw)
    path = cache_path(model, persona, question, options, temperature, draw)
    if path.exists():
        return json.loads(path.read_text())  # cache hit: no API call, no cost

    # Checked before each call, so a run can overshoot by at most one call's cost.
    if spent >= BUDGET_USD:
        raise RuntimeError(f"Budget of ${BUDGET_USD} reached")

    if model in DECISION_MODELS:
        answer, model_answered, usage, probabilities = ask_decision_model(model, persona, question, options, raw)
        input_tokens, output_tokens, cost = usage["input_tokens"], usage["output_tokens"], usage.get("cost") or 0.0
    else:
        answer, model_answered, usage = ask_chat_model(model, persona, question, options, temperature)
        input_tokens, output_tokens = usage.prompt_tokens, usage.completion_tokens
        cost = getattr(usage, "cost", 0.0)  # OpenRouter reports the dollar cost of each call; Ollama does not (it is free)
        probabilities = None
    spent += cost

    # Save the inputs alongside the answer so each cache file is self-describing, then write it.
    # Failed answers are cached too, so a rerun will not retry them.
    record = {
        "model_requested": model,
        "model_answered": model_answered,
        "temperature": temperature,
        "draw": draw,
        "persona": persona,
        "question": question,
        "options": options,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
        "answer": answer,
    }
    if probabilities is not None:
        record["probabilities"] = probabilities  # a decision model's probability for each option
    path.write_text(json.dumps(record))
    return record


def ask_chat_model(model, persona, question, options, temperature):
    """One answer from a chat model: the answer (None if unusable), the model that answered, and the usage."""
    # Persona goes in the system message (who the model is), question in the user message (what it is asked).
    # response_format with strict=True asks the provider to return JSON matching the answer schema.
    # The full model string (with any "ollama/" prefix) stays in the cache key; only the API sees the bare name.
    if model.startswith("ollama/"):
        api, name = local_client, model.removeprefix("ollama/")
    else:
        api, name = client, model
    response = api.chat.completions.create(
        model=name,
        messages=[{"role": "system", "content": persona}, {"role": "user", "content": question}],
        temperature=temperature,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "answer", "strict": True, "schema": answer_schema(options)},
        },
    )
    # Strict mode is not guaranteed by every provider, so parse defensively and keep only an answer from `options`.
    try:
        answer = json.loads(response.choices[0].message.content)["answer"]
    except (TypeError, ValueError, KeyError):
        answer = None  # no answer, or not the shape we asked for
    if answer not in options:
        answer = None  # an answer that is not one of the options counts as no usable answer
    return answer, response.model, response.usage


def ask_decision_model(model, persona, question, options, cache_key):
    """One answer from a decision model: a random pick weighted by its probability for each option.

    The persona is the "state" and the question the "instructions"; each option is described by its own name.
    Decision models have no temperature. The pick is seeded from `cache_key`, so a rerun gives the same answer.
    Returns the answer, the model that answered, the usage (tokens and cost) and the probabilities."""
    request = {
        "model": model,
        "state": persona,
        "questions": {"answer": {"type": "choice", "instructions": question, "criteria": {o: o for o in options}}},
    }
    call = urllib.request.Request(
        DECISIONS_URL, data=json.dumps(request).encode(), method="POST",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(call, timeout=60) as response:
        reply = json.loads(response.read())
    probabilities = reply["answers"]["answer"]["probabilities"]
    weights = [max(probabilities.get(option, 0.0), 0.0) for option in options]
    if sum(weights) == 0:
        return None, reply["model"], reply["usage"], probabilities  # no usable probabilities
    seed = int(hashlib.sha256(cache_key.encode()).hexdigest(), 16)
    answer = random.Random(seed).choices(options, weights=weights)[0]  # choices() rescales weights to sum to 1
    return answer, reply["model"], reply["usage"], probabilities
