#### Preamble ####
# Purpose: Sean's model trial for #6, made to run unattended: each of the 15 models tried (13 now, see
#          TRIAL_MODELS) answers a small slice of personas in both question wordings, with the draws and temperature
#          of Sean's approach (APPROACH_SETTINGS in queries.py), to compare the models' cost and how often they give
#          a usable answer before choosing the two for the full run (Cohere Command A+ and Claude Haiku 5.5).
#          It does not stop on errors: a failed call is retried, then counted as an error, and a model whose calls
#          keep failing is skipped. Each model can spend at most COST_CAP_PER_MODEL, half for each wording; when it
#          reaches that, the script moves on to the next model.
#          The answers stay in cache/ and are not saved as a data file, as the plan says for #6's tries. A rerun is
#          free for everything already answered, so rerunning it just prints the summary again.
# Author: Sean Murphy
# Date: 25 October 2026
# Pre-requisites: personas, candidates; OPENROUTER_API_KEY in .env
# Usage: caffeinate -i uv run scripts/06-trial_models_sean.py
#        (caffeinate keeps the Mac awake until the script ends). Makes paid API calls, at most COST_CAP_PER_MODEL
#        for each model. Add --models to try only some of them, or --personas to change the slice.

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

import openai
import polars as pl

from senate_forecast_2026.paths import ANALYSIS_DATA
from senate_forecast_2026.queries import APPROACH_SETTINGS, QUESTION_WORDINGS, query_personas, questions_for_state
from senate_forecast_2026.schemas import NON_CANDIDATE_ANSWERS, PARTY_GROUP_OF

APPROACH = "sean"
# The cheap models tried, from 10 makers (the list the trial ran on 25 October).
TRIAL_MODELS = [
    "cohere/command-r7b-12-2024",
    "cohere/command-r-08-2024",
    "cohere/command-a-plus",
    "openai/gpt-oss-20b",
    "openai/gpt-6-luna",
    "google/gemma-4-26b-a4b-it",
    "google/gemini-2.5-flash-lite",
    "anthropic/claude-haiku-5.5",
    "mistralai/mistral-small-3.2-24b-instruct",
    "meta-llama/llama-3.3-70b-instruct",
    # "meta/muse-spark-1.3-contributor",
    # Every call failed: its only provider trains on prompts, which our OpenRouter settings block.
    # "qwen/qwen3.5-flash-02-23",
    # Every call failed: its provider wants the word "json" in the prompt for our answer format.
    "microsoft/phi-4",
    "nvidia/nemotron-3.5-lightning",
    "z-ai/glm-5.3-flash",
]
COST_CAP_PER_MODEL = 0.25  # dollars for each model, for both wordings together
COST_CAP_PER_WORDING = COST_CAP_PER_MODEL / len(QUESTION_WORDINGS)
# Errors that may go away if we wait (too many requests, a provider down, the internet down): wait this many seconds
# before each retry. After the last one, the call counts as an error.
RETRY_WAITS = [10, 60, 300, 900]
# Errors that will not go away (e.g. the model does not accept our JSON answer format): not retried.
PERMANENT_ERRORS = (
    openai.BadRequestError,
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
    openai.UnprocessableEntityError,
)
GIVE_UP_AFTER = 5  # a model whose calls fail this many times in a row is skipped
NO_ANSWER = {"answer": None, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}  # a call that was skipped or failed

parser = argparse.ArgumentParser(description="Try each of Sean's candidate models on a few personas, in both wordings.")
parser.add_argument("--personas", type=int, default=25, help="how many personas, each from a different state")
parser.add_argument("--models", nargs="+", default=None, help="only these of TRIAL_MODELS; default: all")
arguments = parser.parse_args()

settings = APPROACH_SETTINGS[APPROACH]
models = arguments.models or TRIAL_MODELS
unknown = set(models) - set(TRIAL_MODELS)
if unknown:
    raise SystemExit(f"Not one of the trial's models: {', '.join(sorted(unknown))}")


#### Read data ####
# The first persona of each state, then the first `--personas` of those: the same slice as 05-query_models.py
# --personas, so the answers are shared through cache/.
personas = pl.read_parquet(ANALYSIS_DATA / "personas.parquet")
personas = personas.group_by("state", maintain_order=True).head(1).head(arguments.personas)
candidates = pl.read_parquet(ANALYSIS_DATA / "candidates.parquet")
all_personas = pl.read_parquet(ANALYSIS_DATA / "personas.parquet")
# Calls one model makes in a full run (every persona, every question, the approach's draws), for the cost estimate.
full_run_calls = settings["draws"] * sum(
    len(questions_for_state(state, candidates, settings["wording"])) for state in all_personas["state"]
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import silicon

# silicon.py stops a run at $5 (BUDGET_USD). Here the caps per model are the limit, so the overall budget is all of
# them together; it only matters if the caps somehow fail.
silicon.BUDGET_USD = COST_CAP_PER_MODEL * len(models)
# A call that hangs gives up after 2 minutes instead of the default 10, and is then retried below.
silicon.client = silicon.client.with_options(timeout=120)


#### Ask, without stopping on errors ####
spent = Counter()  # (model, wording) -> dollars of this model's answers so far, including answers from cache/
failures_in_a_row = Counter()  # model -> calls that failed one after another
outcomes = Counter()  # (model, wording, outcome) -> number of calls


def ask_with_limits(model, persona, question, options, temperature, draw, wording):
    """silicon.ask(), made safe to leave running: skipped once the model reaches its cap for this wording or keeps
    failing, and retried when an error may be temporary. Returns ask()'s answer, or NO_ANSWER."""
    if spent[model, wording] >= COST_CAP_PER_WORDING:
        outcomes[model, wording, "skipped: cost cap"] += 1
        return NO_ANSWER
    if failures_in_a_row[model] >= GIVE_UP_AFTER:
        outcomes[model, wording, "skipped: errors"] += 1
        return NO_ANSWER

    for wait in [*RETRY_WAITS, None]:
        try:
            result = silicon.ask(model, persona, question, options, temperature, draw)
        except PERMANENT_ERRORS as error:
            print(f"  {model}: {type(error).__name__}: {str(error)[:300]}", flush=True)
            break
        except openai.OpenAIError as error:  # other API errors may be temporary
            if wait is None:
                print(f"  {model}: {type(error).__name__}, still failing after {len(RETRY_WAITS)} retries", flush=True)
                break
            print(f"  {model}: {type(error).__name__}: {str(error)[:200]}; retrying in {wait} s", flush=True)
            time.sleep(wait)
        except Exception as error:  # anything else, e.g. a reply with nothing in it: not retried
            if silicon.total_spent() >= silicon.BUDGET_USD:
                raise  # silicon's overall budget was reached, which the caps should prevent: stop
            print(f"  {model}: {type(error).__name__}: {str(error)[:300]}", flush=True)
            break
        else:
            failures_in_a_row[model] = 0
            spent[model, wording] += result["cost"]
            outcomes[model, wording, "answered" if result["answer"] is not None else "unusable"] += 1
            return result

    failures_in_a_row[model] += 1
    outcomes[model, wording, "error"] += 1
    if failures_in_a_row[model] == GIVE_UP_AFTER:
        print(f"  {model}: {GIVE_UP_AFTER} calls in a row failed, so the rest of its calls are skipped", flush=True)
    return NO_ANSWER


trial_answers = []
for number, model in enumerate(models, start=1):
    for wording in QUESTION_WORDINGS:
        print(f"[{number}/{len(models)}] {model}, wording {wording}", flush=True)
        responses = query_personas(
            personas, candidates, APPROACH, [model], settings["draws"], settings["temperature"], wording,
            lambda *call, wording=wording: ask_with_limits(*call, wording=wording),
        )
        trial_answers.append(responses.with_columns(wording=pl.lit(wording)))
        print(f"  ${spent[model, wording]:.4f}; ${silicon.total_spent():.4f} spent in this run so far", flush=True)


#### Summary ####
# For each model and wording: what happened to its calls, what they cost, an estimate of a full run's cost, how
# often it answered Undecided or Would not vote, and how often Democratic and Republican personas chose their own
# party's candidate in the Senate race (a check that the model follows the persona).
answers = (
    pl.concat(trial_answers)
    .join(candidates.select("state", pl.col("candidate").alias("answer"), pl.col("party").alias("answer_party")),
          on=["state", "answer"], how="left")
    .join(personas.select("persona_id", persona_party=pl.col("party_id").replace_strict(PARTY_GROUP_OF)), on="persona_id")
)
by_model = answers.group_by("model", "wording").agg(
    cost=pl.col("cost").sum(),
    undecided_or_not_voting=pl.col("answer").is_in(NON_CANDIDATE_ANSWERS).sum() / pl.col("answer").is_not_null().sum(),
    own_party=(pl.col("answer_party") == pl.col("persona_party"))
    .filter((pl.col("question") == "senate") & pl.col("persona_party").is_in(["Democrat", "Republican"])
            & pl.col("answer_party").is_not_null())
    .mean(),
)
outcome_counts = (
    pl.DataFrame([{"model": m, "wording": w, "outcome": o, "calls": n} for (m, w, o), n in outcomes.items()])
    .pivot(on="outcome", index=["model", "wording"], values="calls")
    .fill_null(0)
)
for outcome in ["answered", "unusable", "error", "skipped: cost cap", "skipped: errors"]:
    if outcome not in outcome_counts.columns:
        outcome_counts = outcome_counts.with_columns(pl.lit(0).alias(outcome))
summary = (
    outcome_counts.join(by_model, on=["model", "wording"])
    .with_columns(
        usable=pl.col("answered") / (pl.col("answered") + pl.col("unusable") + pl.col("error")),
        cost_per_call=pl.col("cost") / (pl.col("answered") + pl.col("unusable")),
    )
    .with_columns(full_run_cost=pl.col("cost_per_call") * full_run_calls)
    .select("model", "wording", "answered", "unusable", "error", "skipped: cost cap", "skipped: errors", "usable",
            "cost", "full_run_cost", "undecided_or_not_voting", "own_party")
    .sort("model", "wording")
)
print(f"\nTrial: {personas.height} personas, {settings['draws']} draws, both wordings. "
      f"full_run_cost: one model's cost for a full run ({full_run_calls:,} calls), at its cost per call here.")
with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=250, float_precision=3):
    print(summary)
print(f"${silicon.total_spent():.4f} spent in this run (answers from cache/ are free)")
