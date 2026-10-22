#### Preamble ####
# Purpose: Ask LLMs every persona's questions (their own Senate race, the generic ballot, and Alaska's final
#          round for Alaska personas), with one approach's models and settings, and save the answers as
#          responses_sean or responses_furkan (task #5; the full runs are #6).
# Author: Furkan Danisman
# Date: 22 October 2026
# Pre-requisites: uv sync; OPENROUTER_API_KEY in .env (not needed with --dry-run).
#                 Simulated data from scripts/00-simulate_data.py, or the real personas and candidates (#3, #4).
# Usage: uv run scripts/05-query_models.py --approach furkan --data simulated --personas-per-state 1 --dry-run
#        Add --wording v2 to try the experimental question wording instead of the approach's own (v1).
#        Makes paid API calls unless --dry-run is given. Answers already in cache/ are free.

import argparse
import sys
from pathlib import Path

import polars as pl

from senate_forecast_2026.queries import QUESTION_WORDINGS, persona_to_prompt, query_personas, questions_for_state
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import Responses

DATA_FOLDERS = {"simulated": Path("data/00-simulated_data"), "real": Path("data/02-analysis_data")}

# Each of us sets our own approach here for #6: models from at least two providers, repeated draws, and the
# question wording (see QUESTION_WORDINGS in queries.py). v1 is the default; v2 is the experimental wording,
# run with --wording v2 to check how much the answers depend on it.
APPROACH_SETTINGS = {
    "sean": {
        "models": ["deepseek/deepseek-v4-flash-0731", "z-ai/glm-5.3-flash"], "draws": 3, "temperature": 1.0, "wording": "v1",
    },
    "furkan": {
        "models": ["deepseek/deepseek-v4-flash-0731", "z-ai/glm-5.3-flash"], "draws": 3, "temperature": 1.0, "wording": "v1",
    },
}

parser = argparse.ArgumentParser(description="Ask LLMs every persona's questions and save the answers.")
parser.add_argument("--approach", choices=APPROACH_SETTINGS, required=True, help="whose models and settings to use")
parser.add_argument("--data", choices=DATA_FOLDERS, default="real", help="read the simulated or the real files")
parser.add_argument(
    "--personas-per-state", type=int, default=None,
    help="only ask this many personas in each state (a small slice for trying things out); default: all",
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

n_questions = sum(len(questions_for_state(state, candidates, wording)) for state in personas["state"])
n_calls = n_questions * len(settings["models"]) * settings["draws"]
print(
    f"{personas.height:,} personas, {len(settings['models'])} models, {settings['draws']} draws, "
    f"wording {wording}: {n_calls:,} calls"
)

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

responses = query_personas(
    personas, candidates, arguments.approach, settings["models"], settings["draws"], settings["temperature"], wording, ask
)
print(f"{responses.height:,} answers, {responses['answer'].null_count():,} missing; ${total_spent():.4f} spent this run")
print(responses.group_by("model", "question", "answer").len().sort("model", "question", "len", descending=[False, False, True]))

#### Save ####
# Only a full run on the real data, in the approach's own wording, is saved. Simulated data, slices and the other
# wording stay in cache/ (as the plan says for #6's tries), so they never overwrite the simulated responses from #1
# or a real full run. (Responses has no wording column, so a saved file must have one wording.)
if arguments.data == "real" and arguments.personas_per_state is None and wording == settings["wording"]:
    save_data(
        responses, Responses, DATA_FOLDERS["real"], f"responses_{arguments.approach}",
        sample_groups=["approach", "persona_id", "model", "draw"], also_sample_where=pl.col("state") == "AK",
    )
else:
    print("Not saved: only a full run on the real data, in the approach's own wording, is saved. The answers are in cache/.")
