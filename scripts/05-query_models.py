#### Preamble ####
# Purpose: Ask LLMs every persona's questions (their own Senate race, the generic ballot, and Alaska's final
#          round for Alaska personas), with one approach's models and settings, and save the answers as
#          responses_sean or responses_furkan (task #5; the full runs are #6).
# Author: Furkan Danisman
# Date: 22 October 2026; updated 24 October 2026 (draws per model, --personas, run costs)
# Pre-requisites: uv sync; OPENROUTER_API_KEY in .env (not needed with --dry-run).
#                 Simulated data from scripts/00-simulate_data.py, or the real personas and candidates (#3, #4).
# Usage: uv run scripts/05-query_models.py --approach furkan --data simulated --personas-per-state 1 --dry-run
#        Add --wording v2 to try the experimental question wording instead of the approach's own (v1).
#        Makes paid API calls unless --dry-run is given. Answers already in cache/ are free.
#        Every run that asks the models adds its costs (per model and in total) to data/run_costs.csv.

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from senate_forecast_2026.paths import DATA
from senate_forecast_2026.queries import (
    APPROACH_SETTINGS,
    QUESTION_WORDINGS,
    draws_by_model,
    persona_to_prompt,
    query_personas,
    questions_for_state,
    run_costs,
)
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import Responses, RunCosts

DATA_FOLDERS = {"simulated": Path("data/00-simulated_data"), "real": Path("data/02-analysis_data")}

parser = argparse.ArgumentParser(description="Ask LLMs every persona's questions and save the answers.")
parser.add_argument("--approach", choices=APPROACH_SETTINGS, required=True, help="whose models and settings to use")
parser.add_argument("--data", choices=DATA_FOLDERS, default="real", help="read the simulated or the real files")
parser.add_argument(
    "--personas-per-state", type=int, default=None,
    help="only ask this many personas in each state (a small slice for trying things out); default: all",
)
parser.add_argument(
    "--personas", type=int, default=None,
    help="only ask this many personas, each from a different state (a small slice for checking cost); default: all",
)
parser.add_argument(
    "--models", nargs="+", default=None,
    help="only ask these of the approach's models (e.g. to run one model first); the answers are not saved, "
    "because the saved file needs every model, but they stay in cache/",
)
parser.add_argument(
    "--wording", choices=QUESTION_WORDINGS, default=None,
    help="question wording to use instead of the approach's own (for comparing v1 and v2); not saved",
)
parser.add_argument("--dry-run", action="store_true", help="show the number of calls and an example prompt; no API calls")
arguments = parser.parse_args()
settings = APPROACH_SETTINGS[arguments.approach]
wording = arguments.wording or settings["wording"]

#### Read data ####
input_folder = DATA_FOLDERS[arguments.data]
personas = pl.read_parquet(input_folder / "personas.parquet").sort("persona_id")
candidates = pl.read_parquet(input_folder / "candidates.parquet")
if arguments.personas_per_state is not None:
    # The first personas in each state by persona_id, so the same slice is picked on every run.
    personas = personas.group_by("state", maintain_order=True).head(arguments.personas_per_state)
if arguments.personas is not None:
    # The first persona of each state, by persona_id, then the first `--personas` of those: one per state.
    personas = personas.group_by("state", maintain_order=True).head(1).head(arguments.personas)

n_questions = sum(len(questions_for_state(state, candidates, wording)) for state in personas["state"])
draws = draws_by_model(settings["models"], settings["draws"])
if arguments.models is not None:
    unknown = set(arguments.models) - set(draws)
    if unknown:
        raise SystemExit(f"Not one of the {arguments.approach} approach's models: {', '.join(sorted(unknown))}")
    draws = {model: n for model, n in draws.items() if model in arguments.models}
n_calls = n_questions * sum(draws.values())
print(f"{personas.height:,} personas, draws per model {draws}, wording {wording}: {n_calls:,} calls")

if arguments.dry_run:
    # An Alaska persona if there is one, because Alaska has all three questions.
    alaska_personas = personas.filter(pl.col("state") == "AK")
    example = (alaska_personas if alaska_personas.height > 0 else personas).row(0, named=True)
    print("\nExample system message:\n" + persona_to_prompt(example))
    for question in questions_for_state(example["state"], candidates, wording):
        print(f"\nQuestion ({question['question']}):\n{question['text']}\nOptions: {question['options']}")
    raise SystemExit

#### Ask the models ####
# Imported here, not at the top, because silicon.py needs the API key as soon as it is imported.
# silicon.py is in the repo root, not in scripts/, so the root is added to where Python looks for modules.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from silicon import ask, total_spent

responses = query_personas(personas, candidates, arguments.approach, list(draws), draws, settings["temperature"], wording, ask)
print(f"{responses.height:,} answers, {responses['answer'].null_count():,} missing; ${total_spent():.4f} spent this run")
print(responses.group_by("model", "question", "answer").len().sort("model", "question", "len", descending=[False, False, True]))

#### Costs ####
# Every run adds its costs to data/run_costs.csv, one row per model and one for all models, so the cost of each try
# and of the full run is kept even when the answers are not saved.
costs = run_costs(responses).with_columns(
    run_at=pl.lit(datetime.now(UTC).isoformat(timespec="seconds")),
    approach=pl.lit(arguments.approach),
    data=pl.lit(arguments.data),
    wording=pl.lit(wording),
).select("run_at", "approach", "data", "wording", "model", "calls", "personas", "total_cost", "cost_per_persona")
RunCosts.validate(costs, lazy=True)
print(costs.select("model", "calls", "personas", "total_cost", "cost_per_persona"))
cost_log = DATA / "run_costs.csv"
if cost_log.exists():
    costs = pl.concat([pl.read_csv(cost_log), costs], how="vertical_relaxed")
costs.write_csv(cost_log)
print(f"Costs added to {cost_log}")

#### Save ####
# Only a full run on the real data, in the approach's own wording, is saved. Simulated data, slices and the other
# wording stay in cache/ (as the plan says for #6's tries), so they never overwrite the simulated responses from #1
# or a real full run. (Responses has no wording column, so a saved file must have one wording.)
is_full_run = arguments.personas_per_state is None and arguments.personas is None and arguments.models is None
if arguments.data == "real" and is_full_run and wording == settings["wording"]:
    save_data(
        responses, Responses, DATA_FOLDERS["real"], f"responses_{arguments.approach}",
        sample_groups=["approach", "persona_id", "model", "draw"], also_sample_where=pl.col("state") == "AK",
    )
else:
    print("Not saved: only a full run on the real data, in the approach's own wording, is saved. The answers are in cache/.")
