#### Preamble ####
# Purpose: Turn the saved VoteHub Senate polls into polls, in data/02-analysis_data/ (task #10): one row per
#          candidate in each general-election poll that asked about our candidates. A comparison on the website,
#          not a forecast input.
# Author: Furkan Danisman
# Date: 23 October 2026
# Pre-requisites: uv run scripts/10-download_polls.py; candidates from scripts/02-clean_candidates.py
# Run: uv run scripts/10-clean_polls.py (or PyCharm's run button)

import json
from collections import Counter
from datetime import date

import polars as pl

from senate_forecast_2026.paths import ANALYSIS_DATA, RAW_POLLS
from senate_forecast_2026.queries import alaska_final_candidates
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import STATE_CODES, Polls

# Where VoteHub spells a candidate differently from candidates, by (state, VoteHub's name).
NAME_CORRECTIONS = {
    ("AK", "Dan Sullivan"): "Dan S. Sullivan",  # the incumbent; another Dan Sullivan (Dan J.) is also running
    ("NH", "John Sununu"): "John E. Sununu",
}

# VoteHub's population codes, written out.
POPULATIONS = {"lv": "Likely voters", "rv": "Registered voters", "a": "Adults"}


def required_candidates(state, state_candidates):
    """The candidates a poll must include to count as a poll of the race as it is now: all of our candidates in
    the state, so early polls of other possible nominees (e.g. before a primary) are left out. Alaska is the
    exception: polls there ask about the likely final round, the Democrat against the incumbent, not the two
    other Republicans on the ballot."""
    if state == "AK":
        return set(alaska_final_candidates(state_candidates)["candidate"])
    return set(state_candidates["candidate"])


#### Read data ####
raw = json.loads(RAW_POLLS.read_text())
candidates = pl.read_parquet(ANALYSIS_DATA / "candidates.parquet")
print(f"Read {len(raw['polls']):,} polls from {RAW_POLLS.name}, downloaded {raw['downloaded_at']}", flush=True)


#### Keep the general-election polls of our candidates ####
dropped = Counter()  # why each left-out poll was left out, shown below
poll_rows = []
for poll in raw["polls"]:
    # General-election polls are "2026 Texas"; primaries are "2026 Texas Democratic", which is not a state name.
    state_name = poll["subject"].removeprefix("2026 ")
    if state_name not in STATE_CODES:
        dropped["primary"] += 1
        continue

    state = STATE_CODES[state_name]
    state_candidates = candidates.filter(pl.col("state") == state)
    answers = {NAME_CORRECTIONS.get((state, answer["choice"]), answer["choice"]): answer["pct"] for answer in poll["answers"]}
    if not required_candidates(state, state_candidates) <= answers.keys():
        dropped["not our candidates"] += 1
        continue

    # One row per candidate of ours. Minor candidates in the poll are not in candidates, so they are left out.
    for candidate in state_candidates["candidate"]:
        if candidate in answers:
            poll_rows.append({
                "poll_id": poll["id"],
                "state": state,
                "pollster": poll["pollster"],
                "start_date": date.fromisoformat(poll["start_date"]),
                "date": date.fromisoformat(poll["end_date"]),
                "sample_size": poll["sample_size"],
                "population": POPULATIONS.get(poll["population"]),
                "candidate": candidate,
                "share": round(answers[candidate] / 100, 4),  # rounded, so 43.8 is 0.438, not 0.43799999999999994
            })

polls = pl.DataFrame(poll_rows, schema_overrides={"sample_size": pl.Int64}).sort("state", "date", "poll_id", "candidate")


#### Show and save ####
print(f"Kept {polls['poll_id'].n_unique():,} polls; left out: {dict(dropped)}", flush=True)
polls_per_state = polls.group_by("state").agg(pl.col("poll_id").n_unique().alias("polls"), pl.col("date").max().alias("latest"))
print(f"{polls_per_state.height} of 35 states have polls:", flush=True)
for row in polls_per_state.sort("state").iter_rows(named=True):
    print(f"  {row['state']}: {row['polls']} polls, latest {row['latest']}")
print(f"No polls: {', '.join(sorted(set(candidates['state']) - set(polls['state'])))}", flush=True)

save_data(polls, Polls, ANALYSIS_DATA, "polls", sample_groups=["poll_id"])
