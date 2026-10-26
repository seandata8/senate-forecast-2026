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
