# AGENTS.md

University of Toronto data science course project (Sean Murphy and Furkan Danisman): a forecast of all 35 US Senate races in 2026 from an LLM "silicon sample". Personas are real 2024 CES respondents; LLMs are queried via OpenRouter with the actual candidates in each race; answers are adjusted with MRP and simulated into vote shares per race, a seat distribution, and the chance of Democratic control. Polls and Polymarket are comparisons only, not inputs. The website freezes at end of day 2 November 2026. The plan and who does what are in `instructions/Project_Plan_v3.md`, which is local only (gitignored); Sean and Furkan share it directly.

## Setup / run
- Python 3.14, managed with `uv` (`uv sync`; add deps with `uv add`). No tests, linter, or CI configured yet.
- Run scripts from the repo root with `uv run <script>.py`. `silicon.py` uses `cache/` relative to the cwd, and loads `.env` by searching upward from `silicon.py`'s folder.
- Requires `OPENROUTER_API_KEY` in `.env` (gitignored). Never print or commit it. `silicon.py` raises `KeyError` on import without it.
- Running scripts makes paid API calls, so don't run them casually.

## Team workflow
- Never commit directly to `main`. Work on a branch, open a PR, and the other person reviews and merges it.
- The repo is public. Check `git status` before every commit and push.
- Two requirements give the whole assignment a 0 if missing: the Python citation, and the AI-usage statement in `README.md`. Do not remove either.

## Architecture
- `silicon.py` is the shared module for scripts. It holds the OpenRouter client (OpenAI SDK with `base_url`), a local Ollama client, `MODELS` and `EXTRA_MODELS`, the JSON `SCHEMA`, the `BUDGET_USD` guard, and `ask(model, persona, question, temperature, draw)`.
- `silicon.py` is still the worksheet version. `OPTIONS` and `SCHEMA` are the generic ballot (Democratic / Republican / Other / Would not vote) and must become per-race candidate lists; `MODELS` is a placeholder.
- Scripts do `from silicon import *`. Because of that, use `total_spent()` rather than the `spent` global, which `import *` copies once.
- Models prefixed `ollama/` are routed to a local Ollama server at `localhost:11434`; their cost is recorded as 0.

## Gotchas
- `ask()` caches to `cache/<sha256>.json`, keyed on model, temperature, draw, persona and question. Any change to those creates a new, billed call. For repeated samples of the same persona and question, vary `draw`.
- `cache/` is committed to git so results are reproducible without new API calls. Commit new cache files along with the scripts that made them.
- Failed or unparseable answers are cached as `{"vote": None, "confidence": None}` and are not retried. Delete the cache file to retry.
- `BUDGET_USD` (2.00) is per process, not persistent. Cache hits are free and don't count toward it.
- `instructions/` holds course materials. It is gitignored, so treat it as the assignment spec and don't modify it.
- Model IDs in `MODELS` are OpenRouter slugs. Check they exist before changing them.
