#### Preamble ####
# Purpose: Combine both full runs, responses_sean and responses_furkan, into responses (task #7): the one file the
#          forecast (#8), the tests (#9) and the summaries (#12) read. The runs are stacked as they are, with no
#          answers chosen or dropped, as we agreed before seeing the results; the forecast weights each model equally.
# Author: Sean Murphy
# Date: 26 October 2026
# Pre-requisites: responses_sean and responses_furkan from scripts/05-query_models.py (#6)
# Usage: uv run scripts/07-combine_responses.py

import polars as pl

from senate_forecast_2026.paths import ANALYSIS_DATA
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import Responses

RUNS = ["responses_sean", "responses_furkan"]

#### Read data ####
# Each run that exists so far. Until both do, the combined file has only one run, so it is for trying the next
# scripts out, not for the forecast.
runs = {}
for name in RUNS:
    path = ANALYSIS_DATA / f"{name}.parquet"
    if path.exists():
        runs[name] = pl.read_parquet(path)
        models = ", ".join(sorted(runs[name]["model"].unique()))
        print(f"{name}: {runs[name].height:,} answers from {models}")
    else:
        print(f"{name}: not made yet")

if not runs:
    raise SystemExit("Neither run has been made yet, so there is nothing to combine.")


#### Combine and save ####
# The runs stacked as they are: same columns, nothing chosen or dropped. save_data() checks the Responses schema
# first, then writes a readable sample CSV next to the parquet: all of one persona's answers from one model and draw
# together, with an Alaska persona always included (the same sample as 05-query_models.py).
responses = pl.concat(runs.values())
print(f"responses: {responses.height:,} answers from {responses['model'].n_unique()} models")
save_data(
    responses, Responses, ANALYSIS_DATA, "responses",
    sample_groups=["approach", "persona_id", "model", "draw"], also_sample_where=pl.col("state") == "AK",
)
