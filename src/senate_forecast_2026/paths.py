#### Preamble ####
# Purpose: The project's folders, worked out from where this file is rather than from where a script is run.
#          A path like Path("data") only works when run from the repo root; PyCharm's run button runs a script
#          from its own folder, which once sent a download to scripts/data/. These paths work from anywhere.
#          Used by every script and test that reads or writes data.
# Author: Sean Murphy
# Date: 22 October 2026
# Pre-requisites: none

from pathlib import Path

# This file is src/senate_forecast_2026/paths.py, so the repo root is two folders above its folder.
REPO_ROOT = Path(__file__).resolve().parents[2]

DATA = REPO_ROOT / "data"
SIMULATED_DATA = DATA / "00-simulated_data"
RAW_DATA = DATA / "01-raw_data"
ANALYSIS_DATA = DATA / "02-analysis_data"
CODEBOOK = DATA / "codebook.md"
