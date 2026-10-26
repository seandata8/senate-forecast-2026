#### Preamble ####
# Purpose: Download every 2026 US Senate poll from the VoteHub API into data/01-raw_data/, unchanged (task #10).
#          scripts/10-clean_polls.py turns them into polls. Polls are a comparison on the website, not a forecast input.
# Author: Furkan Danisman
# Date: 23 October 2026
# Pre-requisites: uv sync. No API key or login needed.
# Run: uv run scripts/10-download_polls.py (or PyCharm's run button)
#      Each run replaces the saved file with the latest polls, so rerun it to update them.

import json
from datetime import UTC, datetime

from senate_forecast_2026.download import fetch_json
from senate_forecast_2026.paths import RAW_POLLS

# VoteHub, "Polls API" (beta), https://votehub.com/polls/api/. Licence: CC BY 4.0, so the website credits VoteHub.
# poll_type=us-senator: every Senate poll VoteHub has, general elections and primaries, in every state.
# 10-clean_polls.py keeps the general-election polls of our candidates.
POLLS_URL = "https://api.votehub.com/polls?poll_type=us-senator"

polls = fetch_json(POLLS_URL)

# The API has no versions: it always gives the latest polls. So the file records where and when it was downloaded,
# and keeps VoteHub's answer under "polls" exactly as it came.
downloaded = {
    "source": POLLS_URL,
    "downloaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
    "polls": polls,
}
RAW_POLLS.parent.mkdir(parents=True, exist_ok=True)
RAW_POLLS.write_text(json.dumps(downloaded, indent=1))
print(f"Done: {RAW_POLLS} ({len(polls):,} polls, downloaded {downloaded['downloaded_at']}).", flush=True)
