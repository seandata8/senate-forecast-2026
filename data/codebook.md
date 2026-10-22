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

One row per persona (a real CES respondent). Made by #4 from the 2024 CES.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `persona_id` | Int64 | no | ≥ 0, unique | Our id for each persona, from 0 up. Links responses to personas. |
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code, from CES `inputstate` (state name). Only the 35 states with a 2026 Senate race. |
| `age_group` | String | no | 18-29, 30-44, 45-64, 65+ | Age from CES `birthyr`, grouped into four bands. |
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
| `vote_2024` | String | yes | Kamala Harris, Donald Trump, Robert F. Kennedy, Jr., Jill Stein, Cornel West, Chase Oliver, Other, Did not vote for President | CES `CC24_410`, 2024 presidential vote. For reference only, never in the prompt. Missing if the respondent did not answer. |
| `weight` | Float64 | no | > 0 | CES `commonpostweight`: how many people the persona stands for, relative to an average respondent. The CES guide says to use it with any post-election question, and `vote_2024` is one. It exists only for respondents who took the post-election wave (`tookpost`), so only they can be personas. |

## `candidates`

One row per candidate on the November ballot. Made by #3.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code, from CES `inputstate` (state name). Only the 35 states with a 2026 Senate race. |
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
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | The persona's state. Two-letter state code, from CES `inputstate` (state name). Only the 35 states with a 2026 Senate race. |
| `model` | String | no | any | OpenRouter model id. |
| `draw` | Int64 | no | ≥ 0 | Repeat number, from 0 up: the same persona asked the same question again. |
| `question` | String | no | senate, generic, alaska_final | `senate`: the persona's own Senate race. `generic`: which party they would vote for. `alaska_final`: Alaska's ranked-choice final round (Alaska personas only). |
| `answer` | String | yes | any | A candidate on the persona's ballot (for `senate` and `alaska_final`), a party (for `generic`), "Undecided" or "Would not vote". Missing when the model gave no usable answer: kept and counted, never dropped or filled in. |
| `input_tokens` | Int64 | no | ≥ 0 | Tokens sent to the model, as reported by OpenRouter. |
| `output_tokens` | Int64 | no | ≥ 0 | Tokens the model returned, as reported by OpenRouter. |
| `cost` | Float64 | no | ≥ 0 | Dollar cost of the call, as reported by OpenRouter. |

## `frame`

Number of voters in each state and demographic cell, for post-stratification. Made by #8 from 2022 CES validated voters (a midterm electorate).

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code, from CES `inputstate` (state name). Only the 35 states with a 2026 Senate race. |
| `age_group` | String | no | 18-29, 30-44, 45-64, 65+ | Age from CES `birthyr`, grouped into four bands. |
| `gender` | String | no | Man, Woman, Non-binary, Other | CES `gender4`, unchanged. |
| `race` | String | no | White, Black, Hispanic, Asian, Native American, Middle Eastern, Two or more races, Other | CES `race`, unchanged (Hispanic is one of its categories). |
| `education` | String | no | No HS, High school graduate, Some college, 2-year, 4-year, Post-grad | CES `educ`, unchanged. |
| `party_group` | String | no | Democrat, Independent or other, Republican | CES `pid7` collapsed to 3 groups with `PARTY_GROUP_OF` in schemas.py: strong, not very strong and leaning partisans count with their party; independents and not sure are "Independent or other". In #8 the `party_id` in personas is collapsed the same way. |
| `count` | Int64 | no | ≥ 0 | Weighted number of validated voters in the cell. Zero if the cell has none. |

## `forecast`

One row per simulated election, state and candidate. Made by #8 with the Monte Carlo in senate_simulation.py.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `sim_id` | Int64 | no | ≥ 0 | Simulated election number, from 0 up. |
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code, from CES `inputstate` (state name). Only the 35 states with a 2026 Senate race. |
| `candidate` | String | no | any | Candidate's name, as in candidates. |
| `party` | String | no | Democrat, Republican, Independent, Libertarian, Green, Other | Candidate's party, as in candidates. |
| `share` | Float64 | no | ≥ 0, ≤ 1 | Candidate's share of the votes for candidates in this simulated election (undecided, would not vote and missing answers are left out). Alaska: the final ranked-choice round. |
| `winner` | Boolean | no | any | True for the candidate with the highest share. |

## `past_results`

Earlier results in each race state: the last Senate election for the seat up in 2026, and the 2024 presidential election. Made by #3 from the MIT Election Lab. A comparison on the website, not a forecast input.

| Column | Type | Missing | Allowed values | Description |
|---|---|---|---|---|
| `state` | String | no | AL, AK, AR, CO, DE, FL, GA, ID, IL, IA, KS, KY, LA, ME, MA, MI, MN, MS, MT, NE, NH, NJ, NM, NC, OH, OK, OR, RI, SC, SD, TN, TX, VA, WV, WY | Two-letter state code, from CES `inputstate` (state name). Only the 35 states with a 2026 Senate race. |
| `election` | String | no | any | Which election: "senate_2020", "senate_2022" or "senate_2024_special" (the last election for the seat, from MIT `year` and `special`; Georgia 2020 uses its January runoff, which decided the seat), or "president_2024". |
| `dem_share` | Float64 | no | ≥ 0, ≤ 1 | Democratic share of all votes cast in the race (MIT `party_simplified` DEMOCRAT, which includes Minnesota's DFL), so the two shares need not sum to 1. |
| `rep_share` | Float64 | no | ≥ 0, ≤ 1 | Republican share of all votes cast in the race. |
