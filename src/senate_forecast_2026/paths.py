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

# Raw files, as saved by scripts/01-download_election_data.py, which also records where each one comes from.
RAW_CES_2024 = RAW_DATA / "CCES24_Common_OUTPUT_vv_topost_final.csv"  # the names Dataverse gives the CES files
RAW_CES_2022 = RAW_DATA / "CCES22_Common_OUTPUT_vv_topost.csv"
RAW_CANDIDATES_PAGE = RAW_DATA / "wikipedia_2026_senate_elections.txt"
RAW_SENATE_RESULTS = RAW_DATA / "1976-2024-senate-state.csv"
RAW_PRESIDENT_RESULTS = RAW_DATA / "1976-2024-president.csv"
RAW_POLLS = RAW_DATA / "votehub_senate_polls.json"  # saved by scripts/10-download_polls.py
RAW_POLYMARKET = RAW_DATA / "polymarket_senate_prices.json"  # saved by scripts/11-download_polymarket.py

# The full CES files are too big for GitHub, so small samples of them are committed instead: the same file names
# and every column, so the scripts that read the CES can run without the full files. See the README.
CES_SAMPLES = RAW_DATA / "ces_samples"
SAMPLE_CES_2024 = CES_SAMPLES / RAW_CES_2024.name
SAMPLE_CES_2022 = CES_SAMPLES / RAW_CES_2022.name


def full_file_or_sample(full_path, sample_path):
    """The full raw file if it has been downloaded, otherwise its small committed sample, with a warning:
    results from the sample only show that the code runs."""
    if full_path.exists():
        return full_path
    print(
        f"WARNING: {full_path.name} is not downloaded, so using the small sample in {sample_path.parent.name}/. "
        "Run scripts/01-download_election_data.py for the full file.",
        flush=True,
    )
    return sample_path
