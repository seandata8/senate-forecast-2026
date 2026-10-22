# AGENTS.md

University of Toronto data science course project (Sean Murphy and Furkan Danisman): a forecast of all 35 US Senate races in 2026 from an LLM "silicon sample". Personas are real 2024 CES respondents; LLMs are queried via OpenRouter with the actual candidates in each race; answers are adjusted with MRP and simulated into vote shares per race, a seat distribution, and the chance of Democratic control. Polls and Polymarket are comparisons only, not inputs. The website freezes at end of day 2 November 2026. The plan and who does what are in `instructions/Project_Plan_v4.md`, which is local only (gitignored); Sean and Furkan share it directly.

## Setup / run
- Python 3.14, managed with `uv` (`uv sync`; add deps with `uv add`).
- Tests: `uv run pytest` (run `uv run scripts/00-simulate_data.py` first; it writes `data/00-simulated_data/`). Lint: `uv run ruff check` (line length 120). No CI yet.
- Run scripts with `uv run <script>.py` or PyCharm's run button; either works from any folder. Never write `Path("data/...")`: use the folders in `senate_forecast_2026/paths.py` (`RAW_DATA`, `SIMULATED_DATA`, `ANALYSIS_DATA`, `CODEBOOK`), which are worked out from the repo's location. `silicon.py` keeps `cache/` next to itself, and loads `.env` by searching upward from its folder.
- Requires `OPENROUTER_API_KEY` in `.env` (gitignored). Never print or commit it. `silicon.py` raises `KeyError` on import without it.
- Running scripts makes paid API calls, so don't run them casually.

## Team workflow
- Never commit directly to `main`. Work on a branch, open a PR, and the other person reviews and merges it.
- The repo is public. Check `git status` before every commit and push.
- Two requirements give the whole assignment a 0 if missing: the Python citation, and the AI-usage statement in `README.md`. Do not remove either.

## Architecture
- Shared code lives in the `senate_forecast_2026` package (`src/`): `schemas.py` holds the agreed columns of every data file as pandera schemas, `senate_simulation.py` the Monte Carlo race and seat simulation, `save.py` the one way to save a data file. Scripts and tests import from it.
- `scripts/` holds the numbered pipeline scripts; `tests/` the pytest suites (simulated data now, real data in a separate file later).
- The codebook, `data/codebook.md`, is written from the schemas: give every column a `description=` in `schemas.py` (source, transformations, what missing means), then run `uv run scripts/write_codebook.py`. Never edit the codebook by hand; `tests/test_codebook.py` fails if it is out of date.
- Every script that writes a parquet to `data/` also writes a readable CSV next to it, so the data can be read in an editor or on GitHub: `<name>.csv` with every row for files of up to 100 rows, otherwise `samp_<name>.csv` with 25 random rows, seeded. Use `save_data()` from `senate_forecast_2026/save.py`, which also checks the schema first.
- `silicon.py` is the shared module for scripts. It holds the OpenRouter client (OpenAI SDK with `base_url`), a local Ollama client, `MODELS` and `EXTRA_MODELS`, the JSON `SCHEMA`, the `BUDGET_USD` guard, and `ask(model, persona, question, temperature, draw)`.
- `silicon.py` is still the worksheet version. `OPTIONS` and `SCHEMA` are the generic ballot (Democratic / Republican / Other / Would not vote) and must become per-race candidate lists; `MODELS` is a placeholder.
- Scripts do `from silicon import *`. Because of that, use `total_spent()` rather than the `spent` global, which `import *` copies once.
- Models prefixed `ollama/` are routed to a local Ollama server at `localhost:11434`; their cost is recorded as 0.

## Code style
- Keep it simple: human-readable and understandable is better than clever.
- Use descriptive variable names; longer is fine.
- Write once, use many: code used in more than one place goes in a function, shared across scripts in the `senate_forecast_2026` package.
- Do the data analysis in scripts, not in the Quarto file that builds the website (course instruction, 21 October 2026). Scripts compute results and save them to `data/`; the `.qmd` only reads those results and shows them as graphs, tables and numbers.
- Every script starts with the `#### Preamble ####` block (purpose, author, date, pre-requisites), as in `silicon.py`.

## Gotchas
- `ask()` caches to `cache/<sha256>.json`, keyed on model, temperature, draw, persona and question. Any change to those creates a new, billed call. For repeated samples of the same persona and question, vary `draw`.
- `cache/` is committed to git so results are reproducible without new API calls. Commit new cache files along with the scripts that made them.
- Failed or unparseable answers are cached as `{"vote": None, "confidence": None}` and are not retried. Delete the cache file to retry.
- `BUDGET_USD` (2.00) is per process, not persistent. Cache hits are free and don't count toward it.
- `instructions/` holds course materials. It is gitignored, so treat it as the assignment spec and don't modify it.
- Model IDs in `MODELS` are OpenRouter slugs. Check they exist before changing them.
