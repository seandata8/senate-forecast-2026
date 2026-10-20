# Senate Forecast 2026

**Work in progress.** This README is a placeholder and will be expanded as the project develops.

A forecast of all 35 US Senate races on 3 November 2026, built from a silicon sample: synthetic responses from large language models (LLMs). Each persona is a real respondent from the 2024 Cooperative Election Study (CES). For each race, we query LLMs through OpenRouter with that race's actual candidates, adjust the answers with multilevel regression and post-stratification (MRP), and simulate vote shares per race, a distribution of Senate seats, and the probability of Democratic control. Polls and Polymarket prices are shown for comparison only; they are not inputs to the forecast.

The forecast website will be deployed with GitHub Pages and frozen at the end of day on 2 November 2026.

## Authors

Sean Murphy and Furkan Danisman, University of Toronto.

## Statement on AI usage

We used Claude Code, with Claude Opus 5.5 (`claude-opus-5-5`), on 18 October 2026 to set up the repository: the `uv` project, `.gitignore`, `silicon.py` (adapted from our course worksheet), and `AGENTS.md`. Claude Code with Claude Opus 5.5 also drafted this README on 18 October 2026, which we then edited. This statement will be updated as the project continues.

The LLMs queried to produce the silicon sample are part of the method, not help with the work; they will be listed with their OpenRouter identifiers in the methods section of the website.
