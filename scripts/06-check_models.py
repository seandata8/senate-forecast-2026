#### Preamble ####
# Purpose: Two of the instructor's checks on an approach's models, on a small slice of personas (task #6):
#          1. Persona attention: "Which state do you live in?" Does the model give the persona's own state?
#          2. Party drop: the persona's questions again, without its party ID line. Do the answers change? The
#             answers with party ID are the approach's full run (responses_<approach>).
#          Same models, draws, temperature and wording as the full run. Saves model_checks_<approach>; the summary
#          for the website is made by #12. The instructor's other checks do not apply: our personas get no news, and
#          every question is already asked in its own call.
# Author: Furkan Danisman
# Date: 25 October 2026
# Pre-requisites: personas, candidates; OPENROUTER_API_KEY in .env. Answers already in cache/ are free.
# Usage: uv run scripts/06-check_models.py --approach furkan
#        Makes paid API calls for answers not in cache/ (about $0.20 for 10 personas with Furkan's models).

import argparse
import sys
from pathlib import Path

import polars as pl

from senate_forecast_2026.paths import ANALYSIS_DATA
from senate_forecast_2026.queries import (
    APPROACH_SETTINGS,
    STATE_OPTIONS,
    STATE_QUESTION,
    draws_by_model,
    persona_to_prompt,
    questions_for_state,
    without_party_id,
)
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import ModelChecks

parser = argparse.ArgumentParser(description="Run the persona-attention and party-drop checks on an approach's models.")
parser.add_argument("--approach", choices=APPROACH_SETTINGS, required=True, help="whose models and settings to use")
parser.add_argument("--personas", type=int, default=10, help="how many personas, each from a different state")
arguments = parser.parse_args()
settings = APPROACH_SETTINGS[arguments.approach]
draws = draws_by_model(settings["models"], settings["draws"])

#### Read data ####
# The first persona of each state, by persona_id, then the first `--personas` of those: the same slice as
# 05-query_models.py --personas.
personas = pl.read_parquet(ANALYSIS_DATA / "personas.parquet").sort("persona_id")
personas = personas.group_by("state", maintain_order=True).head(1).head(arguments.personas)
candidates = pl.read_parquet(ANALYSIS_DATA / "candidates.parquet")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from silicon import ask, total_spent

#### Ask ####
rows = []
for model, model_draws in draws.items():
    for persona in personas.iter_rows(named=True):
        prompt = persona_to_prompt(persona)
        asked = [("persona_state", "state", prompt, STATE_QUESTION, STATE_OPTIONS)]
        asked += [("no_party_id", q["question"], without_party_id(prompt), q["text"], q["options"])
                  for q in questions_for_state(persona["state"], candidates, settings["wording"])]
        for check, question, persona_prompt, text, options in asked:
            for draw in range(model_draws):
                result = ask(model, persona_prompt, text, options, settings["temperature"], draw)
                rows.append({
                    "approach": arguments.approach, "persona_id": persona["persona_id"], "state": persona["state"],
                    "model": model, "draw": draw, "check": check, "question": question, "answer": result["answer"],
                    "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"],
                    "cost": result["cost"],
                })
    print(f"{model} done", flush=True)

model_checks = pl.DataFrame(rows, schema_overrides={"answer": pl.String, "cost": pl.Float64})
print(f"{model_checks.height:,} answers, {model_checks['answer'].null_count():,} missing; ${total_spent():.4f} spent "
      f"this run; ${model_checks['cost'].sum():.4f} in total (answers from cache/ count at their first cost)")

#### Save ####
save_data(model_checks, ModelChecks, ANALYSIS_DATA, f"model_checks_{arguments.approach}")
