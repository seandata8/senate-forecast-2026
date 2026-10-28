#### Preamble ####
# Purpose: Price check for the website's costs section: what our forecast would have cost with the most expensive
#          models on OpenRouter. Asks each of PRICE_CHECK_MODELS one question (the Senate race, for the trial's first
#          persona, with Sean's settings) a few times, through silicon.ask(), and saves the answers with their tokens
#          and cost as price_check, in data/02-analysis_data/. scripts/12-summarize_results.py turns them into the
#          cost of a full run. Not part of the forecast.
# Author: Sean Murphy
# Date: 28 October 2026
# Pre-requisites: personas, candidates; OPENROUTER_API_KEY in .env
# Usage: uv run scripts/06-price_check.py
#        Makes paid API calls the first time (about $1.40, almost all GPT-5.5 Pro); answers are cached in cache/, so a
#        rerun is free. GPT-5.5 Pro thinks for up to about 3 minutes per answer, so the run takes about 10 minutes.

import sys
from pathlib import Path

import polars as pl

from senate_forecast_2026.paths import ANALYSIS_DATA
from senate_forecast_2026.queries import APPROACH_SETTINGS, persona_to_prompt, questions_for_state
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import PriceCheck

# The most expensive models on OpenRouter on 28 October 2026 that accept our answer format, in dollars per million
# input / output tokens: GPT-5.5 Pro ($30 / $180; it also bills its hidden reasoning as output) and Claude Fable 5.1
# ($10 / $50, the most expensive Claude that accepts the format; Claude Opus 4.1 costs more but does not).
PRICE_CHECK_MODELS = ["openai/gpt-5.5-pro", "anthropic/claude-fable-5.1"]
DRAWS = 3  # answers per model: enough for an average cost per call
APPROACH = "sean"  # the settings the question is asked with (temperature and wording)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import silicon

# GPT-5.5 Pro can take about 3 minutes to answer, longer than silicon.py's 60-second timeout. Waiting up to 15
# minutes, without retries (a retried call could be billed twice).
silicon.client = silicon.client.with_options(timeout=900, max_retries=0)


#### The question ####
# The trial's first persona (scripts/06-trial_models_sean.py: the first persona of each state, then the first of
# those) and its Senate question.
personas = pl.read_parquet(ANALYSIS_DATA / "personas.parquet")
persona = personas.group_by("state", maintain_order=True).head(1).row(0, named=True)
candidates = pl.read_parquet(ANALYSIS_DATA / "candidates.parquet")
settings = APPROACH_SETTINGS[APPROACH]
question = next(q for q in questions_for_state(persona["state"], candidates, settings["wording"])
                if q["question"] == "senate")
print(f"Persona {persona['persona_id']} ({persona['state']}), the Senate question, wording {settings['wording']}, "
      f"temperature {settings['temperature']}", flush=True)


#### Ask ####
rows = []
for model in PRICE_CHECK_MODELS:
    for draw in range(DRAWS):
        result = silicon.ask(model, persona_to_prompt(persona), question["text"], question["options"],
                             settings["temperature"], draw)
        print(f"  {model}, draw {draw}: {result['answer']}, {result['input_tokens']} input and "
              f"{result['output_tokens']} output tokens, ${result['cost']:.4f}", flush=True)
        rows.append({"model": model, "draw": draw, "answer": result["answer"],
                     "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"],
                     "cost": result["cost"]})
print(f"${silicon.total_spent():.4f} spent in this run (answers from cache/ are free)")


#### Save ####
price_check = pl.DataFrame(rows, schema_overrides={"answer": pl.String, "cost": pl.Float64})
save_data(price_check, PriceCheck, ANALYSIS_DATA, "price_check")
