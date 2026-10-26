# Codebook

Every data file the pipeline makes, column by column. Simulated versions are in `data/00-simulated_data/`,
real versions in `data/02-analysis_data/`, with the same names and columns. Each file is a parquet, with a
readable CSV next to it: `<name>.csv` in full for small files, `samp_<name>.csv` (25 rows) for large ones.

**Missing values.** A column marked "yes" under *Missing* can be empty (null); its description says what that
means. Every other column is never empty: the scripts check this before saving (`save_data()` in `save.py`).

**Transformations.** Each description says where the column comes from and anything we changed, such as CES
categories we combined.

This file is written by `scripts/write_codebook.py` from `src/senate_forecast_2026/schemas.py`. Edit the
schemas, not this file, then run the script.

## `personas`

One row per persona (a real CES respondent). Made by #4 from the 2024 CES: 30 picked at random (seeded) in each of the 35 race states, from respondents who took the post-election survey. Respondents missing any detail but `vote_2024` were dropped before picking, because every other detail goes in the prompt (51 of the 31,451 post-election respondents in the race states).

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `persona_id` | Int64 | no | ≥ 0, unique | Our id for each persona, from 0 up. Links responses to personas. |
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code. Only the 35 states with a 2026 Senate race. From CES `inputstate`, a US Census state number (FIPS code, e.g. 1 = Alabama). |
| `age_group` | String | no | 18-29, 30-44, 45-64, 65+ | Age in the survey's year, in four bands: 2024 minus CES `birthyr` for personas, 2022 minus `birthyr` for the frame. |
| `gender` | String | no | Man, Woman, Non-binary, Other | CES `gender4`, unchanged. |
| `race` | String | no | White, Black, Hispanic, Asian, Native American, Middle Eastern, Two or more races, Other | CES `race`, unchanged (Hispanic is one of its categories). |
| `education` | String | no | No HS, High school graduate, Some college, 2-year, 4-year, Post-grad | CES `educ`, unchanged. |
| `income` | String | no | Under $30K, $30K-$50K, $50K-$70K, $70K-$100K, $100K-$150K, $150K+, Prefer not to say | CES `faminc_new`: its 16 brackets combined into 6, plus "Prefer not to say". |
| `party_id` | String | no | Strong Democrat, Not very strong Democrat, Lean Democrat, Independent, Lean Republican, Not very strong Republican, Strong Republican, Not sure | CES `pid7` (7-point party ID), unchanged. |
| `ideology` | String | no | Very liberal, Liberal, Moderate, Conservative, Very conservative, Not sure | CES `ideo5`, unchanged. |
| `religion` | String | no | Protestant, Roman Catholic, Mormon, Eastern or Greek Orthodox, Jewish, Muslim, Buddhist, Hindu, Atheist, Agnostic, Nothing in particular, Something else | CES `religpew`, unchanged. |
| `marital_status` | String | no | Married, Separated, Divorced, Widowed, Never married, Domestic / civil partnership | CES `marstat`, unchanged. |
| `sexuality` | String | no | Heterosexual / straight, Lesbian / gay woman, Gay man, Bisexual, Other, Prefer not to say | CES `sexuality`, unchanged. |
| `registered` | String | no | Yes, No, Don't know | CES `votereg` (registered to vote), unchanged. |
| `vote_2024` | String | yes | Kamala Harris, Donald Trump, Robert F. Kennedy, Jr., Jill Stein, Cornel West, Chase Oliver, Other, Did not vote for President | CES `CC24_410`, 2024 presidential vote. For reference only, never in the prompt. Missing if the respondent was not asked (they did not say they definitely voted, in CES `CC24_401`) or did not answer. |
| `weight` | Float64 | no | > 0 | CES `commonpostweight`: how many people the persona stands for, relative to an average respondent. The CES guide says to use it with any post-election question, and `vote_2024` is one. It exists only for respondents who took the post-election wave (`tookpost`), so only they can be personas. |

## `candidates`

One row per candidate on the November ballot. Made by #3.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code. Only the 35 states with a 2026 Senate race. |
| `candidate` | String | no | unique | Candidate's name as on the ballot. |
| `party` | String | no | Democrat, Republican, Independent, Libertarian, Green, Other | Party label on the ballot, used in the prompt, e.g. "Smith (Democrat)". |
| `incumbent` | Boolean | no | any | True for whoever holds the seat now. |
| `dem_caucus_probability` | Float64 | no | ≥ 0, ≤ 1 | Chance the candidate caucuses with the Democrats if they win: 1 for Democrats, 0 for Republicans, our rough guess for independents (`INDEPENDENT_DEM_CAUCUS_PROBABILITY` in senate_simulation.py). |

## `responses_sean`, `responses_furkan`, `responses`

One row per LLM answer. responses_sean and responses_furkan are each person's full run in #6; responses is the two stacked together in #7, and is what the forecast uses.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `approach` | String | no | any | Whose run produced the answer (`sean` or `furkan`): their models and prompt. |
| `persona_id` | Int64 | no | ≥ 0 | Our id for each persona, from 0 up. Links responses to personas. |
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | The persona's state. Two-letter state code. Only the 35 states with a 2026 Senate race. |
| `model` | String | no | any | OpenRouter model id. |
| `draw` | Int64 | no | ≥ 0 | Repeat number, from 0 up: the same persona asked the same question again. |
| `question` | String | no | senate, generic, alaska_final | `senate`: the persona's own Senate race. `generic`: which party they would vote for. `alaska_final`: Alaska's ranked-choice final round (Alaska personas only). |
| `answer` | String | yes | any | A candidate on the persona's ballot (for `senate` and `alaska_final`), a party (for `generic`), "Undecided" or "Would not vote". Missing when the model gave no usable answer: kept and counted, never dropped or filled in. |
| `input_tokens` | Int64 | no | ≥ 0 | Tokens sent to the model, as reported by OpenRouter. |
| `output_tokens` | Int64 | no | ≥ 0 | Tokens the model returned, as reported by OpenRouter. |
| `cost` | Float64 | no | ≥ 0 | Dollar cost of the call, as reported by OpenRouter. |

## `frame`

Number of voters in each state and demographic cell, for post-stratification. Made by #8 from 2024 CES validated voters (the same survey as the personas): each cell's share of its state's voters, times the state's 2024 vote total.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code. Only the 35 states with a 2026 Senate race. From CES `inputstate`, a US Census state number (FIPS code, e.g. 1 = Alabama). |
| `age_group` | String | no | 18-29, 30-44, 45-64, 65+ | Age in the survey's year, in four bands: 2024 minus CES `birthyr` for personas, 2022 minus `birthyr` for the frame. |
| `gender` | String | no | Man, Woman, Non-binary, Other | CES `gender4`, unchanged. |
| `race` | String | no | White, Black, Hispanic, Asian, Native American, Middle Eastern, Two or more races, Other | CES `race`, unchanged (Hispanic is one of its categories). |
| `education` | String | no | No HS, High school graduate, Some college, 2-year, 4-year, Post-grad | CES `educ`, unchanged. |
| `party_group` | String | no | Democrat, Independent or other, Republican | CES `pid7` collapsed to 3 groups with `PARTY_GROUP_OF` in schemas.py: strong, not very strong and leaning partisans count with their party; independents and not sure are "Independent or other". In #8 the `party_id` in personas is collapsed the same way. |
| `count` | Int64 | no | ≥ 0 | Number of voters in the cell: the cell's share of its state's validated 2024 CES voters (weighted with `vvweight`), times the state's 2024 total votes for President (MIT Election Lab). Zero if the cell has none. |

## `forecast`

One row per simulated election, state and candidate. Made by #8 with the Monte Carlo in senate_simulation.py.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `sim_id` | Int64 | no | ≥ 0 | Simulated election number, from 0 up. |
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code. Only the 35 states with a 2026 Senate race. |
| `candidate` | String | no | any | Candidate's name, as in candidates. |
| `party` | String | no | Democrat, Republican, Independent, Libertarian, Green, Other | Candidate's party, as in candidates. |
| `share` | Float64 | no | ≥ 0, ≤ 1 | Candidate's share of the votes for candidates in this simulated election (undecided, would not vote and missing answers are left out). Alaska: the final ranked-choice round. |
| `winner` | Boolean | no | any | True for the candidate with the highest share. |

## `forecast_versions`

The forecast made from part of the answers: each approach's run alone, and each model's answers alone. Made by #8 the same way as forecast, so the website can compare them. One row per version, simulated election, state and candidate.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `sim_id` | Int64 | no | ≥ 0 | Simulated election number, from 0 up. |
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code. Only the 35 states with a 2026 Senate race. |
| `candidate` | String | no | any | Candidate's name, as in candidates. |
| `party` | String | no | Democrat, Republican, Independent, Libertarian, Green, Other | Candidate's party, as in candidates. |
| `share` | Float64 | no | ≥ 0, ≤ 1 | Candidate's share of the votes for candidates in this simulated election (undecided, would not vote and missing answers are left out). Alaska: the final ranked-choice round. |
| `winner` | Boolean | no | any | True for the candidate with the highest share. |
| `version_type` | String | no | approach, model | Whether the version is one approach's run or one model's answers. |
| `version` | String | no | any | The approach (as in responses' `approach`) or the model (its OpenRouter identifier, as in responses' `model`). |

## `past_results`

Earlier results in each race state: the last Senate election for the seat up in 2026, and the 2024 presidential election. Made by #3 from the MIT Election Lab. A comparison on the website, not a forecast input.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code. Only the 35 states with a 2026 Senate race. |
| `election` | String | no | any | Which election: "senate_2020", "senate_2022" or "senate_2024_special" (the last election for the seat, from MIT `year` and `special`; Georgia 2020 uses its January runoff, which decided the seat), or "president_2024". |
| `dem_share` | Float64 | no | ≥ 0, ≤ 1 | Democratic share of all votes cast in the race (MIT `party_simplified` DEMOCRAT, which includes Minnesota's DFL), so the two shares need not sum to 1. |
| `rep_share` | Float64 | no | ≥ 0, ≤ 1 | Republican share of all votes cast in the race. |

## `polls`

One row per candidate in each general-election poll of a 2026 Senate race. Made by #10 from the VoteHub polls API (CC BY 4.0). A comparison on the website, not a forecast input.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `poll_id` | String | no | any | VoteHub's id for the poll. Links the rows (one per candidate) of one poll. |
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code. Only the 35 states with a 2026 Senate race. From VoteHub `subject`, e.g. "2026 Texas". |
| `pollster` | String | no | any | VoteHub `pollster`, unchanged. |
| `start_date` | Date | no | any | The poll's first day of interviews (VoteHub `start_date`). |
| `date` | Date | no | any | The poll's last day of interviews (VoteHub `end_date`). |
| `sample_size` | Int64 | yes | > 0 | Number of people interviewed (VoteHub `sample_size`). Missing if VoteHub has none. |
| `population` | String | yes | Likely voters, Registered voters, Adults | Who was interviewed: VoteHub `population` lv, rv and a, written out. Missing if VoteHub has none. |
| `candidate` | String | no | any | Candidate's name, as in candidates (VoteHub's spelling corrected where it differs). |
| `share` | Float64 | no | ≥ 0, ≤ 1 | Candidate's share of everyone asked (VoteHub `pct` / 100). Undecided and other candidates are not rows, so a poll's shares usually sum to less than 1. |

## `polymarket`

One row per candidate per day: the Polymarket price of a share that pays $1 if the candidate wins their 2026 Senate race. Made by #11 from Polymarket's "<State> Senate Election Winner" markets. A comparison on the website, not a forecast input.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code. Only the 35 states with a 2026 Senate race. |
| `date` | Date | no | any | The day (UTC) of the price. The last price of each day is kept. |
| `candidate` | String | no | any | Candidate's name, as in candidates (Polymarket's market title without its party letter, corrected where it differs). |
| `price` | Float64 | no | ≥ 0, ≤ 1 | Price in dollars of a share that pays $1 if the candidate wins: roughly the market's chance that they win. A race's prices sum to about 1. |

## `poll_averages`

One row per race, on/off combination of the weighting rules, day and candidate: the polling average. Made by #12 into data/03-summary_data/ for the website's polls chart. Days run from the race's first poll to the latest poll in any race.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code. Only the 35 states with a 2026 Senate race. |
| `by_recency` | Boolean | no | any | Whether newer polls count more (weight halves every 14 days). |
| `by_sample_size` | Boolean | no | any | Whether polls that asked more people count more (by the square root of the sample size). |
| `by_pollster` | Boolean | no | any | Whether a pollster's recent polls share one weight (each divided by the square root of their number). |
| `by_population` | Boolean | no | any | Whether likely voters count more than registered voters (x0.8) and adults (x0.6). |
| `date` | Date | no | any | The day of the average. It uses the polls that finished by then. |
| `candidate` | String | no | any | Candidate's name, as in candidates. |
| `average` | Float64 | no | ≥ 0, ≤ 1 | Weighted mean of the candidate's share in the polls that asked about them. Each poll's shares are first scaled to add up to 1 among its candidates, so undecided voters are left out. |
| `spread` | Float64 | no | ≥ 0 | Weighted standard deviation of those shares around the average: how much the polls disagree. Not a margin of error. |

## `poll_influence`

One row per poll and on/off combination of the weighting rules: the poll's weight in its race's average on the last day. Made by #12 into data/03-summary_data/ for the website's polls table.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code. Only the 35 states with a 2026 Senate race. |
| `poll_id` | String | no | any | VoteHub's id for the poll, as in polls. |
| `by_recency` | Boolean | no | any | Whether newer polls count more (weight halves every 14 days). |
| `by_sample_size` | Boolean | no | any | Whether polls that asked more people count more (by the square root of the sample size). |
| `by_pollster` | Boolean | no | any | Whether a pollster's recent polls share one weight (each divided by the square root of their number). |
| `by_population` | Boolean | no | any | Whether likely voters count more than registered voters (x0.8) and adults (x0.6). |
| `influence` | Float64 | no | ≥ 0 | The poll's weight: the rules switched on, multiplied together. 1 is a typical poll: a 600-person likely-voter poll that ended that day, its pollster's only recent poll of the race. |

## `polymarket_prices`

One row per candidate per day: the Polymarket price, as in polymarket. Made by #12 into data/03-summary_data/ for the website's Polymarket chart.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code. Only the 35 states with a 2026 Senate race. |
| `date` | Date | no | any | The day (UTC) of the price. The last price of each day is kept. |
| `candidate` | String | no | any | Candidate's name, as in candidates (Polymarket's market title without its party letter, corrected where it differs). |
| `price` | Float64 | no | ≥ 0, ≤ 1 | Price in dollars of a share that pays $1 if the candidate wins: roughly the market's chance that they win. A race's prices sum to about 1. |

## `polymarket_latest`

One row per candidate: their latest Polymarket price and its day. Made by #12 into data/03-summary_data/ for the website's "Traders give ... a ...% chance to win" numbers.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code. Only the 35 states with a 2026 Senate race. |
| `date` | Date | no | any | The day (UTC) of the price. The last price of each day is kept. |
| `candidate` | String | no | any | Candidate's name, as in candidates (Polymarket's market title without its party letter, corrected where it differs). |
| `price` | Float64 | no | ≥ 0, ≤ 1 | Price in dollars of a share that pays $1 if the candidate wins: roughly the market's chance that they win. A race's prices sum to about 1. |

## `run_costs`

One row per model, and one for all models, for each run of scripts/05-query_models.py that asked the models: what the run's answers cost. Each run adds its rows to data/run_costs.csv, so earlier runs are kept.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `run_at` | String | no | any | When the run finished, in UTC (ISO 8601). |
| `approach` | String | no | sean, furkan | Whose approach the run used. |
| `data` | String | no | simulated, real | Whether the run asked the simulated or the real personas. |
| `wording` | String | no | v1, v2 | The question wording (see QUESTION_WORDINGS in queries.py). |
| `model` | String | no | any | OpenRouter model id, or "all models" for the run's total. |
| `calls` | Int64 | no | ≥ 0 | Number of answers: personas x questions x draws. |
| `personas` | Int64 | no | ≥ 0 | Number of personas asked. |
| `total_cost` | Float64 | no | ≥ 0 | Dollars the answers cost (OpenRouter's reported cost). Answers taken from the cache count at what they cost when first asked. |
| `cost_per_persona` | Float64 | no | ≥ 0 | total_cost / personas: the average cost of one persona. |

## `forecast_control`

One row per forecast version: the chance of Democratic control and the Democratic-caucus seats. Made by #12 into data/03-summary_data/ from forecast and forecast_versions.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `version_type` | String | no | all, approach, model | Which answers the forecast is made from: "all" (both runs together, the forecast), "approach" (one approach's run) or "model" (one model's answers). |
| `version` | String | no | any | "all", the approach (as in responses' `approach`) or the model (its OpenRouter identifier). |
| `dem_control` | Float64 | no | ≥ 0, ≤ 1 | Share of the simulated elections with 51 or more Democratic-caucus seats (at 50-50 the Republican Vice President breaks the tie). |
| `seats` | Float64 | no | ≥ 0, ≤ 100 | Democratic-caucus seats: the median of the simulated elections. |
| `seats_lower` | Float64 | no | ≥ 0, ≤ 100 | Lower end of the 95% interval of the seats (2.5% of simulations have fewer). |
| `seats_upper` | Float64 | no | ≥ 0, ≤ 100 | Upper end of the 95% interval of the seats (2.5% of simulations have more). |

## `forecast_seats`

One row per forecast version and number of Democratic-caucus seats: how many simulated elections ended with it (the seat distribution chart). Made by #12 into data/03-summary_data/.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `version_type` | String | no | all, approach, model | Which answers the forecast is made from: "all" (both runs together, the forecast), "approach" (one approach's run) or "model" (one model's answers). |
| `version` | String | no | any | "all", the approach (as in responses' `approach`) or the model (its OpenRouter identifier). |
| `dem_seats` | Int64 | no | ≥ 0, ≤ 100 | Democratic-caucus seats. |
| `simulations` | Int64 | no | ≥ 1 | Number of simulated elections with that many seats. |
| `share` | Float64 | no | ≥ 0, ≤ 1 | Share of the simulated elections with that many seats. |

## `forecast_races`

One row per forecast version and candidate: their vote share and chance of winning, next to the polls and Polymarket (the race-by-race comparison). Made by #12 into data/03-summary_data/. Alaska: the final round.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `version_type` | String | no | all, approach, model | Which answers the forecast is made from: "all" (both runs together, the forecast), "approach" (one approach's run) or "model" (one model's answers). |
| `version` | String | no | any | "all", the approach (as in responses' `approach`) or the model (its OpenRouter identifier). |
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code. Only the 35 states with a 2026 Senate race. |
| `candidate` | String | no | any | Candidate's name, as in candidates. |
| `party` | String | no | Democrat, Republican, Independent, Libertarian, Green, Other | Candidate's party, as in candidates. |
| `share` | Float64 | no | ≥ 0, ≤ 1 | Our estimate of the candidate's vote share: the mean across the simulated elections (undecided left out). |
| `share_lower` | Float64 | no | ≥ 0, ≤ 1 | Lower end of the 95% interval of the vote share. |
| `share_upper` | Float64 | no | ≥ 0, ≤ 1 | Upper end of the 95% interval of the vote share. |
| `chance_of_winning` | Float64 | no | ≥ 0, ≤ 1 | Share of the simulated elections the candidate wins. |
| `poll_average` | Float64 | yes | ≥ 0, ≤ 1 | Today's polling average with every rule on (undecided left out), as in poll_averages. Missing if the race has no polls. |
| `poll_spread` | Float64 | yes | ≥ 0 | The polls' spread around that average, as in poll_averages. Not a margin of error. |
| `polymarket_chance` | Float64 | yes | ≥ 0, ≤ 1 | Polymarket's latest price, scaled to add up to 1 among the race's candidates. Missing if there is no price. |

## `model_answers`

One row per model, question and answer: the weighted share of answers. Made by #12 into data/03-summary_data/. Senate answers are grouped by the chosen candidate's party.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `model` | String | no | any | The model (its OpenRouter identifier), or "average": the models counted equally. |
| `question` | String | no | senate, generic | "senate" (the race we forecast) or "generic" (the House question, a benchmark). |
| `answer` | String | no | any | The party of the chosen candidate (Senate), the party (House), Undecided, Would not vote or Missing. |
| `share` | Float64 | no | ≥ 0, ≤ 1 | Share of the answers, weighted by the personas' CES weights; each persona's draws from one model count once in total. |

## `crosstabs`

One row per persona detail, group and model: the Democratic share of the two-party House vote. Made by #12 into data/03-summary_data/.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `variable` | String | no | any | The persona detail, as in personas (e.g. gender). |
| `group` | String | no | any | The group (e.g. Woman). |
| `model` | String | no | any | The model (its OpenRouter identifier), or "average": the models counted equally. |
| `democratic_share` | Float64 | no | ≥ 0, ≤ 1 | Democratic share among the group's Democratic and Republican House answers, weighted as in model_answers. |
| `personas` | Int64 | no | ≥ 1 | Number of personas in the group with a two-party answer (for "average", the smaller of the models' numbers). |

## `persona_composition`

One row per persona detail and group: how many personas are in it. Made by #12 into data/03-summary_data/.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `variable` | String | no | any | The persona detail, as in personas (e.g. gender). |
| `group` | String | no | any | The group (e.g. Woman), or Missing. |
| `personas` | Int64 | no | ≥ 1 | Number of personas in the group. |

## `costs`

One row per approach and model (and "all models"): what each approach's latest full run cost. Made by #12 into data/03-summary_data/ from the run cost log, data/run_costs.csv.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `approach` | String | no | any | Whose approach, as in responses. |
| `run_at` | String | no | any | When the run finished, as in run_costs. |
| `model` | String | no | any | The model's OpenRouter identifier, or "all models". |
| `calls` | Int64 | no | ≥ 0 | Number of answers. |
| `personas` | Int64 | no | ≥ 1 | Number of personas asked. |
| `total_cost` | Float64 | no | ≥ 0 | Total cost in US dollars, as OpenRouter charged it. |
| `cost_per_persona` | Float64 | no | ≥ 0 | Total cost divided by the number of personas. |

## `past_comparison`

One row per race and election: the Republican share in past elections next to our 2026 estimate. Made by #12 into data/03-summary_data/ from past_results and the forecast (both runs together).

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code. Only the 35 states with a 2026 Senate race. |
| `election` | String | no | any | As in past_results ("president_2024", "senate_2020", ...), or "forecast_2026": our estimate. |
| `republican_share` | Float64 | no | ≥ 0, ≤ 1 | Republican share: of all votes cast in past elections (as in past_results); of the votes for the race's candidates in our estimate (undecided left out). |
| `lower` | Float64 | yes | ≥ 0, ≤ 1 | Our estimate: lower end of its 95% interval. Missing for past elections. |
| `upper` | Float64 | yes | ≥ 0, ≤ 1 | Our estimate: upper end of its 95% interval. Missing for past elections. |

## `model_checks_sean`, `model_checks_furkan`

One row per answer in the instructor's checks on an approach's models, on a small slice of personas. Made by #6 scripts/06-check_models.py as model_checks_sean or model_checks_furkan.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `approach` | String | no | any | Whose models and settings (`sean` or `furkan`). |
| `persona_id` | Int64 | no | ≥ 0 | Our id for each persona, from 0 up. Links responses to personas. |
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | The persona's state. Two-letter state code. Only the 35 states with a 2026 Senate race. |
| `model` | String | no | any | OpenRouter model id. |
| `draw` | Int64 | no | ≥ 0 | Repeat number, from 0 up, as in responses. |
| `check` | String | no | persona_state, no_party_id | "persona_state": asked which state they live in. "no_party_id": asked their usual questions without the party ID line. |
| `question` | String | no | state, senate, generic, alaska_final | "state" for persona_state; otherwise the question, as in responses. |
| `answer` | String | yes | any | A state name (persona_state) or an answer as in responses. Missing when the model gave no usable answer. |
| `input_tokens` | Int64 | no | ≥ 0 | Tokens sent to the model, as reported by OpenRouter. |
| `output_tokens` | Int64 | no | ≥ 0 | Tokens the model returned, as reported by OpenRouter. |
| `cost` | Float64 | no | ≥ 0 | Dollar cost of the call, as reported by OpenRouter. |
