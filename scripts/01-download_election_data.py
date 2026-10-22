#### Preamble ####
# Purpose: Download the election data for #3 into data/01-raw_data/, unchanged:
#            - 2024 Cooperative Election Study (CES): personas are built from it in #4
#            - 2022 CES: its validated voters make the post-stratification frame in #8
#            - the 2026 Senate candidate list: one fixed revision of a Wikipedia page
#            - (to add) past results from the MIT Election Lab
#          Polls and Polymarket prices are downloaded separately (#10, #11).
#          Cleaning happens in separate scripts, so it can be rerun without downloading again.
# Author: Sean Murphy
# Date: 22 October 2026
# Pre-requisites: uv sync. No API key or login needed. Rerunning is free: intact files are not downloaded again.
# Run: uv run scripts/01-download_election_data.py (or PyCharm's run button)

from senate_forecast_2026.download import download_dataverse_file, download_wikipedia_revision
from senate_forecast_2026.paths import RAW_CANDIDATES_PAGE, RAW_CES_2022, RAW_CES_2024

#### CES 2024 ####
# Schaffner, Shih, Ansolabehere and Pope, "Cooperative Election Study Common Content, 2024", doi:10.7910/DVN/X11EP6,
# version 9 (September 2025). Licence: CC0 1.0 (public domain). The file is 184 MB, over GitHub's 100 MB limit,
# so it is gitignored. File ID and checksum are from the dataset's Dataverse page: the CSV version of the data
# (the .dta Stata version is the same data, 994 MB).
CES_2024_FILE_ID = 12050325
CES_2024_MD5 = "b740b9305fee50e1a34656b513f55c57"

download_dataverse_file(CES_2024_FILE_ID, CES_2024_MD5, RAW_CES_2024)


#### CES 2022 ####
# Schaffner, Ansolabehere and Shih, "Cooperative Election Study Common Content, 2022", doi:10.7910/DVN/PR4L8P,
# version 4 (April 2024). Licence: CC0 1.0 (public domain). The vote-validated ("vv") CSV, 193 MB, also gitignored.
# It has what the frame needs: validated 2022 turnout (TS_g2022), vvweight_post, and the same demographics as 2024.
CES_2022_FILE_ID = 10140882
CES_2022_MD5 = "0819d70f07dbf2978e3df2496097773a"

download_dataverse_file(CES_2022_FILE_ID, CES_2022_MD5, RAW_CES_2022)


#### 2026 Senate candidates ####
# Wikipedia, "2026 United States Senate elections", revision 1381380271 (22 October 2026). Checked against
# Silver Bulletin's candidate list: every Democrat's and Republican's last name matched.
# A fixed revision, so later edits to the page cannot change our data. Licence: CC BY-SA 4.0. Small, so committed.
# scripts/02-clean_candidates.py turns its "Race summary" tables into candidates.
# To switch to a different revision, change the number and delete the saved file: an existing file is not replaced.
CANDIDATES_PAGE_REVISION = 1381380271

download_wikipedia_revision(CANDIDATES_PAGE_REVISION, RAW_CANDIDATES_PAGE)
