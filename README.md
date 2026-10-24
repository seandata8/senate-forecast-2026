# Senate Forecast 2026

**Work in progress.** This README is a placeholder and will be expanded as the project develops.

A forecast of all 35 US Senate races on 3 November 2026, built from a silicon sample: synthetic responses from large language models (LLMs). Each persona is a real respondent from the 2024 Cooperative Election Study (CES). For each race, we query LLMs through OpenRouter with that race's actual candidates, adjust the answers with multilevel regression and post-stratification (MRP), and simulate vote shares per race, a distribution of Senate seats, and the probability of Democratic control. Polls and Polymarket prices are shown for comparison only; they are not inputs to the forecast.

The forecast website will be deployed with GitHub Pages and frozen at the end of day on 2 November 2026.

## Data

`uv run scripts/01-download_election_data.py` downloads every raw file into `data/01-raw_data/`, unchanged. No login or API key is needed. Each Dataverse file is checked against its published checksum, and files already downloaded are not downloaded again. The script's comments give the full citation and licence of each source.

| Raw file | Source | In the repo? |
|---|---|---|
| `CCES24_Common_OUTPUT_vv_topost_final.csv` | 2024 Cooperative Election Study, [doi:10.7910/DVN/X11EP6](https://doi.org/10.7910/DVN/X11EP6), version 9 | No (184 MB); a sample is |
| `CCES22_Common_OUTPUT_vv_topost.csv` | 2022 Cooperative Election Study, [doi:10.7910/DVN/PR4L8P](https://doi.org/10.7910/DVN/PR4L8P), version 4 | No (193 MB); a sample is |
| `wikipedia_2026_senate_elections.txt` | Wikipedia, "2026 United States Senate elections", revision 1381380271 | Yes |
| `1976-2024-senate-state.csv` | MIT Election Data and Science Lab, [doi:10.7910/DVN/PEJ5QU](https://doi.org/10.7910/DVN/PEJ5QU), version 8 | Yes |
| `1976-2024-president.csv` | MIT Election Data and Science Lab, [doi:10.7910/DVN/42MVDX](https://doi.org/10.7910/DVN/42MVDX), version 10.1 | Yes |
| `votehub_senate_polls.json` | VoteHub Polls API, [votehub.com/polls/api](https://votehub.com/polls/api/), CC BY 4.0; downloaded by `scripts/10-download_polls.py`, which replaces it with the latest polls on each run | Yes |

**The CES files.** Both are over GitHub's 100 MB file limit, so they are gitignored and not in the repo. To get them, run the download script above. To download them by hand instead, open the DOI link, download the CSV file named in the table (on Dataverse, choose "Original File Format" if offered), and save it in `data/01-raw_data/` under that name.

**The CES samples.** `data/01-raw_data/ces_samples/` holds a small sample of each CES file, with the same file name and every column: 20 random respondents from each state, 1,020 in all. The download script writes them, seeded, so they are the same every time. Scripts that read the CES use the full file if it is there, and otherwise the sample, with a warning. So the code runs without the full files, but results from the samples are only a check that the code works, not a forecast.

## Authors

Sean Murphy and Furkan Danisman, University of Toronto.

## Statement on AI usage

We used Claude Code, with Claude Opus 5.5 (`claude-opus-5-5`), on 18 October 2026 to set up the repository: the `uv` project, `.gitignore`, `silicon.py` (adapted from our course worksheet), and `AGENTS.md`. Claude Code with Claude Opus 5.5 also drafted this README on 18 October 2026, which we then edited. On 21 October 2026, Claude Code with Claude Opus 5.5 wrote the simulation (`scripts/00-simulate_data.py`), the data schemas, seat simulation and file saving (`src/senate_forecast_2026/schemas.py`, `senate_simulation.py`, `save.py`, `simulation_settings.py`), the codebook generator (`src/senate_forecast_2026/codebook.py`, `scripts/write_codebook.py`), and the tests (`tests/test_simulated_data.py`, `tests/test_codebook.py`), and the personas script (scripts/04-build_personas.py) which we reviewed. On 22 October 2026, Claude Code with Claude Opus 5.5 wrote the CES download code and shared folder paths (`src/senate_forecast_2026/download.py`, `paths.py`, `scripts/01-download_election_data.py`), the cleaning scripts for candidates and past results (`scripts/02-clean_candidates.py`, `scripts/03-clean_past_results.py`), the CES samples and the Data section of this README, the query-models code (`scripts/05-query_models.py`, `src/senate_forecast_2026/queries.py`, the per-question answer options and token counts in `silicon.py`) and its tests (`tests/test_query_models.py`), which we reviewed. This statement will be updated as the project continues.

The LLMs queried to produce the silicon sample are part of the method, not help with the work; they will be listed with their OpenRouter identifiers in the methods section of the website.
