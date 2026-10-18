# Senate Forecast: Project Plan v2

Oct 18, 2026 · @Sean, @Furkan

We forecast all 35 Senate races in 2026 using an LLM silicon sample, then compare it with real polling and Polymarket. The website freezes at end of day November 2.

v2 records the decisions from Furkan's comments on v1 and Sean's reply.

## Approach

1. **Personas:** real respondents from the 2024 CES. Built once, then fixed and shared by both of us.
2. **Queries:** LLMs from at least two providers via OpenRouter, naming the actual candidates in each race, with repeated runs. Each of us experiments with our own choice of models and prompts on the same personas. We present one main approach in the paper and put the others in an appendix.
3. **Adjustment:** MRP, post-stratified to 2022 CES validated voters (a midterm electorate), with 2024 voters as a sensitivity check.
4. **Forecast:** simulate many elections with a shared national error to get vote shares per race, a seat distribution, and the chance of Democratic control (51 seats needed). Saved as a parquet.
5. **Comparison:** silicon estimates vs. polling averages and vs. Polymarket, in the discussion section. Polls and Polymarket are comparisons only and do not feed into the forecast.

## Decisions

| Question from v1 | Decision |
|---|---|
| Do polls feed into the forecast, or are they only a comparison? | Comparison only. |
| Include a Polymarket comparison, or skip it? | Include it, as a comparison. |
| Skip the optional extras (GitHub Actions, media-diet experiments)? | GitHub Actions if there is time. Media-diet experiments are deferred: ask Rohan in office hours whether they are required or extra. |
| Split the work by pipeline half or by layer? | Neither, exactly. Sean builds the personas first. Then we both experiment with models and prompts on the same personas and compare results. |
| How to handle unusual races (strong independents, Louisiana, Alaska)? | Still open. We will work it out as we go. |

## Who does what

| Task | Owner | When |
|---|---|---|
| Personas from the 2024 CES | Sean | Oct 19 |
| Model and prompt experiments | Sean and Furkan, each separately | After personas are fixed |
| Polls comparison | Furkan | |
| Polymarket comparison | Furkan | |
| Ask Rohan about media-diet experiments | Sean | Next office hours |
| GitHub Actions (optional) | Sean | If time |

Furkan takes the polls and Polymarket comparisons to balance the workload, since Sean builds the personas.

## Still open

- How to handle unusual races: strong independents, Louisiana, Alaska.
- How we choose the main approach from our two sets of experiments, and by when.

## Fixed requirements

One public repo, a GitHub Pages site, and each person's PRs reviewed and merged by the other. Missing the Python citation or the README AI-usage statement gives the whole assignment a 0.
