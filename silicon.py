#### Preamble ####
# Purpose: Client, models, and one cached structured call, shared by the scripts that query models
# Author: Sean Murphy; per-question answer options and token counts added by Furkan Danisman
# Date: 7 October 2026; updated 22 October 2026
# Pre-requisites: uv add openai python-dotenv polars numpy; OPENROUTER_API_KEY in .env

import hashlib
import json
import os
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


def answer_schema(options):
    """The JSON the model must return: one answer, from `options`. The options differ by question and race
    (each state's own candidates), so the schema is built for each call."""
    return {
        "type": "object",
        "properties": {"answer": {"type": "string", "enum": options}},
        "required": ["answer"],
        "additionalProperties": False,
    }


BUDGET_USD = 2.00
CACHE = Path("cache")
CACHE.mkdir(exist_ok=True)
spent = 0.0


def total_spent():
    """Dollars spent so far in this run. Call this rather than reading `spent`, which `import *` copies once."""
    return spent


def ask(model, persona, question, options, temperature=1.0, draw=0):
    """One structured answer, chosen from `options`. Cached on everything that determines it, so a rerun costs nothing.
    `draw` lets you ask the same persona the same question more than once."""
    global spent  # we add to the module-level total below, not a local copy

    # Cache key: every input that can change the answer, hashed into a fixed-length filename.
    # Change any one of them (even one character of the persona, or one answer option) and it is a new call.
    raw = f"{model}|{temperature}|{draw}|{persona}|{question}|{json.dumps(options)}"
    path = CACHE / (hashlib.sha256(raw.encode()).hexdigest() + ".json")
    if path.exists():
        return json.loads(path.read_text())  # cache hit: no API call, no cost

    # Checked before each call, so a run can overshoot by at most one call's cost.
    if spent >= BUDGET_USD:
        raise RuntimeError(f"Budget of ${BUDGET_USD} reached")

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
    cost = getattr(response.usage, "cost", 0.0)  # OpenRouter reports the dollar cost of each call; Ollama does not (it is free)
    spent += cost

    # Strict mode is not guaranteed by every provider, so parse defensively and keep only an answer from `options`.
    try:
        answer = json.loads(response.choices[0].message.content)["answer"]
    except (TypeError, ValueError, KeyError):
        answer = None  # no answer, or not the shape we asked for
    if answer not in options:
        answer = None  # an answer that is not one of the options counts as no usable answer

    # Save the inputs alongside the answer so each cache file is self-describing, then write it.
    # Failed answers are cached too, so a rerun will not retry them.
    record = {
        "model_requested": model,
        "model_answered": response.model,
        "temperature": temperature,
        "draw": draw,
        "persona": persona,
        "question": question,
        "options": options,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "cost": cost,
        "answer": answer,
    }
    path.write_text(json.dumps(record))
    return record
