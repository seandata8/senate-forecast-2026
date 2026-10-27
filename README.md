# Senate Forecast 2026

**Work in progress.** This README is a placeholder and will be expanded as the project develops.

A forecast of all 35 US Senate races on 3 November 2026, built from a silicon sample: synthetic responses from large language models (LLMs). Each persona is a real respondent from the 2024 Cooperative Election Study (CES). For each race, we query LLMs through OpenRouter with that race's actual candidates, adjust the answers with multilevel regression and post-stratification (MRP), and simulate vote shares per race, a distribution of Senate seats, and the probability of Democratic control. Polls and Polymarket prices are shown for comparison only; they are not inputs to the forecast.

The forecast website will be deployed with GitHub Pages and frozen at the end of day on 2 November 2026.

## Data

`uv run scripts/01-download_election_data.py` downloads the CES, Wikipedia and MIT files into `data/01-raw_data/`, unchanged; the polls and Polymarket files come from their own download scripts (see the table). No login or API key is needed. Each Dataverse file is checked against its published checksum, and files already downloaded are not downloaded again. The script's comments give the full citation and licence of each source.

| Raw file | Source | In the repo? |
|---|---|---|
| `CCES24_Common_OUTPUT_vv_topost_final.csv` | 2024 Cooperative Election Study, [doi:10.7910/DVN/X11EP6](https://doi.org/10.7910/DVN/X11EP6), version 9 | No (184 MB); a sample is |
| `CCES22_Common_OUTPUT_vv_topost.csv` | 2022 Cooperative Election Study, [doi:10.7910/DVN/PR4L8P](https://doi.org/10.7910/DVN/PR4L8P), version 4 | No (193 MB); a sample is |
| `wikipedia_2026_senate_elections.txt` | Wikipedia, "2026 United States Senate elections", revision 1381380271 | Yes |
| `1976-2024-senate-state.csv` | MIT Election Data and Science Lab, [doi:10.7910/DVN/PEJ5QU](https://doi.org/10.7910/DVN/PEJ5QU), version 8 | Yes |
| `1976-2024-president.csv` | MIT Election Data and Science Lab, [doi:10.7910/DVN/42MVDX](https://doi.org/10.7910/DVN/42MVDX), version 10.1 | Yes |
| `votehub_senate_polls.json` | VoteHub Polls API, [votehub.com/polls/api](https://votehub.com/polls/api/), CC BY 4.0; downloaded by `scripts/10-download_polls.py`, which replaces it with the latest polls on each run | Yes |
| `polymarket_senate_prices.json` | Polymarket, [polymarket.com](https://polymarket.com), the "Senate Election Winner" market of each race and the "Which party will win the Senate in 2026?" market, with their daily prices (Gamma and CLOB APIs); downloaded by `scripts/11-download_polymarket.py`, which replaces it with the latest prices on each run | Yes |
| `silver_bulletin_senate_control.csv` | Silver Bulletin, [2026 Senate Forecast](https://www.natesilver.net/p/nate-silver-2026-midterm-election-senate-model), the chance of Democratic control of the Senate (subscription required), typed in by hand with the day it was read | Yes |

**The CES files.** Both are over GitHub's 100 MB file limit, so they are gitignored and not in the repo. To get them, run the download script above. To download them by hand instead, open the DOI link, download the CSV file named in the table (on Dataverse, choose "Original File Format" if offered), and save it in `data/01-raw_data/` under that name.

**The CES samples.** `data/01-raw_data/ces_samples/` holds a small sample of each CES file, with the same file name and every column: 20 random respondents from each state, 1,020 in all. The download script writes them, seeded, so they are the same every time. Scripts that read the CES use the full file if it is there, and otherwise the sample, with a warning. So the code runs without the full files, but results from the samples are only a check that the code works, not a forecast.

**Wedgewood Polls.** On 20 October 2026, Wedgewood Polls admitted that most of its election polls were fabricated ([CryptoSlate](https://cryptoslate.com/kalshi-election-betting-rules-expose-a-data-integrity-question-after-fake-poll-scandal/)). VoteHub still lists 6 of its Senate polls (Georgia, Kansas, Maine, Mississippi, Ohio and Texas), and we keep them in `polls` for now.

## Website

The website is one page, `index.qmd`, built with Quarto into `docs/` for GitHub Pages: `uv sync --group website`, then `uv run quarto render` from the repo root (Quarto must be installed). It only reads the summary files in `data/03-summary_data/`, made by `scripts/12-summarize_results.py`; no analysis is done in the page.

**Daily update.** Until the freeze, a GitHub Actions workflow (`.github/workflows/daily-update.yml`) downloads the latest polls and Polymarket prices every evening, reruns the summaries and republishes the website. The Silver Bulletin number is typed in by hand: add a row to `data/01-raw_data/silver_bulletin_senate_control.csv` on the `silver-bulletin` branch (on GitHub, without a PR), and the next run uses it. It asks no models, so the forecast does not change. It stops by itself after 2 November, and we turn it off before the deadline.

## Authors

Sean Murphy and Furkan Danisman, University of Toronto.

## Statement on AI usage

We used Claude Code, with Claude Opus 5.5 (`claude-opus-5-5`), for the work listed below, one line per piece of work, and reviewed everything it wrote. We write the website's text ourselves. This statement will be updated as the project continues.

- 18 October 2026: set up the repository: the `uv` project, `.gitignore`, `silicon.py` (adapted from our course worksheet), and `AGENTS.md`; drafted this README, which we then edited.
- 21 October 2026: the simulation (`scripts/00-simulate_data.py`), the data schemas, seat simulation and file saving (`src/senate_forecast_2026/schemas.py`, `senate_simulation.py`, `save.py`, `simulation_settings.py`), the codebook generator (`src/senate_forecast_2026/codebook.py`, `scripts/write_codebook.py`), the tests (`tests/test_simulated_data.py`, `tests/test_codebook.py`), and the personas script (`scripts/04-build_personas.py`).
- 22 October 2026: the CES download code and shared folder paths (`src/senate_forecast_2026/download.py`, `paths.py`, `scripts/01-download_election_data.py`), the cleaning scripts for candidates and past results (`scripts/02-clean_candidates.py`, `scripts/03-clean_past_results.py`), the CES samples and the Data section of this README, and the query-models code (`scripts/05-query_models.py`, `src/senate_forecast_2026/queries.py`, the per-question answer options and token counts in `silicon.py`) and its tests (`tests/test_query_models.py`).
- 23 and 24 October 2026: the polls download and cleaning scripts (`scripts/10-download_polls.py`, `scripts/10-clean_polls.py`), the `Polls` schema, and `fetch_json()` in `src/senate_forecast_2026/download.py`.
- 24 October 2026: the Polymarket download and cleaning scripts (`scripts/11-download_polymarket.py`, `scripts/11-clean_polymarket.py`) and the `Polymarket` schema.
- 24 October 2026: the polling average (`src/senate_forecast_2026/poll_average.py`) and its tests (`tests/test_poll_average.py`), and the first part of the summary script (`scripts/12-summarize_results.py`).
- 24 October 2026: decision models (Jev) in `silicon.py`, and draws per model, the `--personas` option and the run-cost log in `scripts/05-query_models.py` and `src/senate_forecast_2026/queries.py`, with tests (`tests/test_silicon.py`, `tests/test_query_models.py`).
- 24 and 25 October 2026: the `--models` option in `scripts/05-query_models.py`, the shared CES codes moved to `src/senate_forecast_2026/ces_codes.py`, the weighting frame script (`scripts/08-build_frame.py`), the MRP model (`src/senate_forecast_2026/mrp.py`) and its tests (`tests/test_mrp.py`), and the forecast script (`scripts/08-forecast.py`).
- 25 October 2026: the polling average changed to leave out the undecided (`without_undecided()` in `src/senate_forecast_2026/poll_average.py`), the forecast script made to also produce a version from each approach and each model, and the forecast's summary code (`src/senate_forecast_2026/forecast_summary.py`, the new parts of `scripts/12-summarize_results.py` and their schemas) and its tests (`tests/test_forecast_summary.py`).
- 25 October 2026: the past-results and checks summaries in `scripts/12-summarize_results.py` and their schemas, the checks script (`scripts/06-check_models.py`, with `without_party_id()` and the state question in `src/senate_forecast_2026/queries.py`) and its test, and the approach settings moved from `scripts/05-query_models.py` to `queries.py`.
- 25 and 26 October 2026: the website (`index.qmd`, `_quarto.yml`, `style.scss` and `src/senate_forecast_2026/website.py`), the polls' 95% interval (`poll_interval()` in `src/senate_forecast_2026/poll_average.py`), the summaries for every version, the Senate cross-tabs and the polls and models tables in `scripts/12-summarize_results.py`, `with_versions()` in `src/senate_forecast_2026/forecast_summary.py`, `DECISION_MODELS` in `src/senate_forecast_2026/queries.py`, their schemas and their tests.
- 26 October 2026: the tests on the real data (`tests/test_real_data.py`, with `share_of()` moved to `tests/helpers.py`).
- 26 October 2026: the script that combines both runs into one file (`scripts/07-combine_responses.py`).
- 25 and 26 October 2026: Sean's model trial (`scripts/06-trial_models_sean.py`), the progress report during a run (`scripts/watch_progress.py`, with `cache_key()` and `cache_path()` in `silicon.py`), and the analysis of the trial's results.
- 26 October 2026: the daily update of polls, Polymarket and the website (`.github/workflows/daily-update.yml`) and its note in this README.
- 27 October 2026: the chance of control from the polls, Polymarket and the Silver Bulletin next to ours: the Senate-control market in `scripts/11-download_polymarket.py` and `scripts/11-clean_polymarket.py`, the polls' seat simulation (`poll_state_shares()` in `src/senate_forecast_2026/poll_average.py`) and its test, the comparison in `scripts/12-summarize_results.py`, their schemas, and the chart in `index.qmd`; and the daily update moved to 7:37 pm Toronto time.
- 27 October 2026: the size of the simulation's errors saved by `scripts/08-forecast.py` (`forecast_errors`) and added to `forecast_control` by `scripts/12-summarize_results.py`, with their schemas; and the numbers and references inserted into our own text in `index.qmd` as inline code, with corrections to its description of the model and the errors.
- 26 October 2026: the website's "Blue Wave" design (`style.scss`, the colours and font in `src/senate_forecast_2026/website.py`, the fonts loaded in `_quarto.yml`, and the footer wave), the charts of the polls and Polymarket from 1 August to election day (`CHART_START` and `ELECTION_DAY` in `src/senate_forecast_2026/queries.py`), the slanted labels in the forecast panels (`index.qmd`), and the headline seats as the most common number (`seat_summary()` in `src/senate_forecast_2026/forecast_summary.py`).

The LLMs queried to produce the silicon sample are part of the method, not help with the work; they will be listed with their OpenRouter identifiers in the methods section of the website.

## References

Python Software Foundation. 2025. *Python*, version 3.14. https://www.python.org.
