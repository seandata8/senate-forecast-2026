#### Preamble ####
# Purpose: Download the election data for #3 into data/01-raw_data/, unchanged:
#            - 2024 Cooperative Election Study (CES): personas are built from it in #4
#            - 2022 CES: its validated voters make the post-stratification frame in #8
#            - (to add) the 2026 Senate candidate list
#            - (to add) past results from the MIT Election Lab
#          Polls and Polymarket prices are downloaded separately (#10, #11).
#          Cleaning happens in separate scripts, so it can be rerun without downloading again.
# Author: Sean Murphy
# Date: 22 October 2026
# Pre-requisites: uv sync. No API key or login needed. Rerunning is free: intact files are not downloaded again.
# Run: uv run scripts/01-download_election_data.py (or PyCharm's run button)

from senate_forecast_2026.download import download_dataverse_file
from senate_forecast_2026.paths import RAW_DATA

#### CES 2024 ####
# Schaffner, Shih, Ansolabehere and Pope, "Cooperative Election Study Common Content, 2024", doi:10.7910/DVN/X11EP6,
# version 9 (September 2025). Licence: CC0 1.0 (public domain). The file is 184 MB, over GitHub's 100 MB limit,
# so it is gitignored. File ID and checksum are from the dataset's Dataverse page: the CSV version of the data
# (the .dta Stata version is the same data, 994 MB).
CES_2024_FILE_ID = 12050325
CES_2024_MD5 = "b740b9305fee50e1a34656b513f55c57"
CES_2024_PATH = RAW_DATA / "CCES24_Common_OUTPUT_vv_topost_final.csv"  # the name Dataverse gives it

download_dataverse_file(CES_2024_FILE_ID, CES_2024_MD5, CES_2024_PATH)


#### CES 2022 ####
# Schaffner, Ansolabehere and Shih, "Cooperative Election Study Common Content, 2022", doi:10.7910/DVN/PR4L8P,
# version 4 (April 2024). Licence: CC0 1.0 (public domain). The vote-validated ("vv") CSV, 193 MB, also gitignored.
# It has what the frame needs: validated 2022 turnout (TS_g2022), vvweight_post, and the same demographics as 2024.
CES_2022_FILE_ID = 10140882
CES_2022_MD5 = "0819d70f07dbf2978e3df2496097773a"
CES_2022_PATH = RAW_DATA / "CCES22_Common_OUTPUT_vv_topost.csv"  # the name Dataverse gives it

download_dataverse_file(CES_2022_FILE_ID, CES_2022_MD5, CES_2022_PATH)
