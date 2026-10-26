#### Preamble ####
# Purpose: Show how far a full run of scripts/05-query_models.py has got, while it runs: for each of the approach's
#          models, the share of its calls already answered, how long it has left, and what its answers cost. It only
#          looks in cache/ for the answer files the run will write, so it makes no API calls and does not slow the run
#          down.
# Author: Sean Murphy
# Date: 26 October 2026
# Pre-requisites: personas, candidates; OPENROUTER_API_KEY in .env (silicon.py needs it on import, but no calls are made)
# Usage: uv run scripts/watch_progress.py --approach sean
#        In a second terminal tab, next to the run. Prints every 5 minutes (change it with --every) until every
#        model is done; stop it any time with Ctrl+C.

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import polars as pl

from senate_forecast_2026.paths import ANALYSIS_DATA
from senate_forecast_2026.queries import APPROACH_SETTINGS, draws_by_model, persona_to_prompt, questions_for_state

parser = argparse.ArgumentParser(description="Show a full run's progress for each model, from cache/.")
parser.add_argument("--approach", choices=APPROACH_SETTINGS, required=True, help="whose run to watch")
parser.add_argument("--every", type=float, default=5, help="minutes between updates")
arguments = parser.parse_args()
settings = APPROACH_SETTINGS[arguments.approach]

# silicon.py is in the repo root, not in scripts/, so the root is added to where Python looks for modules.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from silicon import cache_path

#### The run's calls ####
# The same calls as query_personas() in a full run: every model, draw, persona and question, in the approach's
# own wording. Each one's cache file is where its answer will be saved.
personas = pl.read_parquet(ANALYSIS_DATA / "personas.parquet")
candidates = pl.read_parquet(ANALYSIS_DATA / "candidates.parquet")
questions_by_state = {
    state: questions_for_state(state, candidates, settings["wording"]) for state in personas["state"].unique()
}
cache_files = {}  # model -> the cache files of all its calls
for model, model_draws in draws_by_model(settings["models"], settings["draws"]).items():
    cache_files[model] = [
        cache_path(model, persona_to_prompt(persona), question["text"], question["options"], settings["temperature"], draw)
        for draw in range(model_draws)
        for persona in personas.iter_rows(named=True)
        for question in questions_by_state[persona["state"]]
    ]


#### Watch ####
RUN_GAP = 10 * 60  # seconds: a pause this long between two answers means they came from different runs


def answered_files(files):
    """The cache files that exist so far, out of `files`."""
    return [path for path in files if path.exists()]


def hours_left(done, total_calls):
    """Hours until a model finishes, at its average speed in the current run; None if it isn't answering now.

    Each cache file's time is when its answer was saved. The current run's answers are those after the last pause
    longer than RUN_GAP, so answers from before (e.g. the trial's) don't count as fast work."""
    times = sorted(path.stat().st_mtime for path in done)
    if not times or time.time() - times[-1] > RUN_GAP:
        return None  # not answering at the moment: not started yet, or stopped
    run_start = 0
    for i in range(1, len(times)):
        if times[i] - times[i - 1] > RUN_GAP:
            run_start = i
    run_times = times[run_start:]
    if len(run_times) < 10:
        return None  # too few answers yet to tell its speed
    calls_per_second = (len(run_times) - 1) / (run_times[-1] - run_times[0])
    return (total_calls - len(done)) / calls_per_second / 3600


while True:
    print(f"\n{datetime.now():%H:%M}", flush=True)
    total_done = 0
    total_estimate = 0.0
    for model, files in cache_files.items():
        done = answered_files(files)
        cost = sum(json.loads(path.read_text())["cost"] for path in done)
        # The cost of all its calls, at the average cost per call so far.
        estimate = cost / len(done) * len(files) if done else 0.0
        total_done += len(done)
        total_estimate += estimate

        hours = hours_left(done, len(files))
        if len(done) == len(files):
            time_left = "done"
        elif hours is None:
            time_left = "time left TBD"
        else:
            time_left = f"about {hours:.1f} hours left"
        print(f"  {model:32s} {len(done) / len(files):6.1%}  ({len(done):,} of {len(files):,} calls; {time_left})",
              flush=True)
        print(f"  {'':32s} ${cost:.2f} so far; about ${estimate:.2f} when done", flush=True)
    print(f"  About ${total_estimate:.2f} for the whole run, at each model's cost per call so far", flush=True)

    total_calls = sum(len(files) for files in cache_files.values())
    if total_done == total_calls:
        print("  All done.", flush=True)
        break
    time.sleep(arguments.every * 60)
