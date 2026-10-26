#### Preamble ####
# Purpose: The agreed columns, types and allowed values of each data file, as pandera schemas.
#          The simulation (#1) and the real data (#4, #7, #8) must both pass these, so code written on one works on the other.
# Author: Sean Murphy
# Date: 21 October 2026
# Pre-requisites: uv add "pandera[polars]"

import datetime

import pandera.polars as pa

# The 35 states with a Senate race in 2026 (33 regular seats, plus the Ohio and Florida specials).
STATES = [
    "AL", "AK", "AR", "CO", "DE", "FL", "GA", "ID", "IL", "IA", "KS", "KY", "LA", "ME", "MA", "MI", "MN", "MS",
    "MT", "NE", "NH", "NJ", "NM", "NC", "OH", "OK", "OR", "RI", "SC", "SD", "TN", "TX", "VA", "WV", "WY",
]

# State names (as the CES and Wikipedia write them) and their codes, for the 35 race states.
STATE_CODES = {
    "Alabama": "AL", "Alaska": "AK", "Arkansas": "AR", "Colorado": "CO", "Delaware": "DE", "Florida": "FL",
    "Georgia": "GA", "Idaho": "ID", "Illinois": "IL", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY",
    "Louisiana": "LA", "Maine": "ME", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Montana": "MT", "Nebraska": "NE", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
    "North Carolina": "NC", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Rhode Island": "RI",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Virginia": "VA",
    "West Virginia": "WV", "Wyoming": "WY",
}
assert sorted(STATE_CODES.values()) == sorted(STATES)

# Persona categories, collapsed from the 2024 CES codebook (variable names in comments).
AGE_GROUPS = ["18-29", "30-44", "45-64", "65+"]  # from birthyr
GENDERS = ["Man", "Woman", "Non-binary", "Other"]  # gender4
RACES = ["White", "Black", "Hispanic", "Asian", "Native American", "Middle Eastern", "Two or more races", "Other"]  # race
EDUCATION = ["No HS", "High school graduate", "Some college", "2-year", "4-year", "Post-grad"]  # educ
INCOMES = ["Under $30K", "$30K-$50K", "$50K-$70K", "$70K-$100K", "$100K-$150K", "$150K+", "Prefer not to say"]  # faminc_new
PARTY_IDS = [
    "Strong Democrat", "Not very strong Democrat", "Lean Democrat", "Independent",
    "Lean Republican", "Not very strong Republican", "Strong Republican", "Not sure",
]  # pid7
# Party ID in 3 groups, for the post-stratification frame (as in the 2015 Xbox paper): all 8 categories would
# multiply the frame's cells by 8, most of them empty. Leaners count with the party they lean to, because they
# vote almost like partisans (Keith et al., The Myth of the Independent Voter).
PARTY_GROUPS = ["Democrat", "Independent or other", "Republican"]
PARTY_GROUP_OF = {
    "Strong Democrat": "Democrat",
    "Not very strong Democrat": "Democrat",
    "Lean Democrat": "Democrat",
    "Independent": "Independent or other",
    "Lean Republican": "Republican",
    "Not very strong Republican": "Republican",
    "Strong Republican": "Republican",
    "Not sure": "Independent or other",
}
IDEOLOGIES = ["Very liberal", "Liberal", "Moderate", "Conservative", "Very conservative", "Not sure"]  # ideo5
RELIGIONS = [
    "Protestant", "Roman Catholic", "Mormon", "Eastern or Greek Orthodox", "Jewish", "Muslim", "Buddhist",
    "Hindu", "Atheist", "Agnostic", "Nothing in particular", "Something else",
]  # religpew
MARITAL_STATUSES = ["Married", "Separated", "Divorced", "Widowed", "Never married", "Domestic / civil partnership"]  # marstat
SEXUALITIES = ["Heterosexual / straight", "Lesbian / gay woman", "Gay man", "Bisexual", "Other", "Prefer not to say"]  # sexuality
REGISTERED = ["Yes", "No", "Don't know"]  # votereg
VOTES_2024 = [
    "Kamala Harris", "Donald Trump", "Robert F. Kennedy, Jr.", "Jill Stein", "Cornel West", "Chase Oliver",
    "Other", "Did not vote for President",
]  # CC24_410

# Candidates and answers.
PARTIES = ["Democrat", "Republican", "Independent", "Libertarian", "Green", "Other"]
QUESTIONS = ["senate", "generic", "alaska_final"]  # alaska_final: the ranked-choice final round, Alaska personas only
NON_CANDIDATE_ANSWERS = ["Undecided", "Would not vote"]  # allowed for every question, alongside the candidates
GENERIC_ANSWERS = ["Democrat", "Republican", "Other"] + NON_CANDIDATE_ANSWERS

# Who a poll asked, as VoteHub's `population` codes lv, rv and a.
POLL_POPULATIONS = ["Likely voters", "Registered voters", "Adults"]


# Descriptions of columns that appear in more than one file, written once.
# The codebook (data/codebook.md) is written from these descriptions by scripts/write_codebook.py.
PERSONA_ID = "Our id for each persona, from 0 up. Links responses to personas."
STATE = "Two-letter state code. Only the 35 states with a 2026 Senate race."
CES_STATE = STATE + " From CES `inputstate`, a US Census state number (FIPS code, e.g. 1 = Alabama)."
AGE_GROUP = "Age in the survey's year, in four bands: 2024 minus CES `birthyr` for personas, 2022 minus `birthyr` for the frame."
GENDER = "CES `gender4`, unchanged."
RACE = "CES `race`, unchanged (Hispanic is one of its categories)."
EDUCATION_LEVEL = "CES `educ`, unchanged."


# pa is the panderas.polars package
class Personas(pa.DataFrameModel):
    """One row per persona (a real CES respondent). Made by #4 from the 2024 CES: 30 picked at random (seeded) in
    each of the 35 race states, from respondents who took the post-election survey. Respondents missing any detail
    but `vote_2024` were dropped before picking, because every other detail goes in the prompt (51 of the 31,451
    post-election respondents in the race states)."""

    persona_id: int = pa.Field(ge=0, unique=True, description=PERSONA_ID)
    state: str = pa.Field(isin=STATES, description=CES_STATE)
    age_group: str = pa.Field(isin=AGE_GROUPS, description=AGE_GROUP)
    gender: str = pa.Field(isin=GENDERS, description=GENDER)
    race: str = pa.Field(isin=RACES, description=RACE)
    education: str = pa.Field(isin=EDUCATION, description=EDUCATION_LEVEL)
    income: str = pa.Field(isin=INCOMES, description='CES `faminc_new`: its 16 brackets combined into 6, plus "Prefer not to say".')
    party_id: str = pa.Field(isin=PARTY_IDS, description="CES `pid7` (7-point party ID), unchanged.")
    ideology: str = pa.Field(isin=IDEOLOGIES, description="CES `ideo5`, unchanged.")
    religion: str = pa.Field(isin=RELIGIONS, description="CES `religpew`, unchanged.")
    marital_status: str = pa.Field(isin=MARITAL_STATUSES, description="CES `marstat`, unchanged.")
    sexuality: str = pa.Field(isin=SEXUALITIES, description="CES `sexuality`, unchanged.")
    registered: str = pa.Field(isin=REGISTERED, description="CES `votereg` (registered to vote), unchanged.")
    vote_2024: str = pa.Field(
        isin=VOTES_2024, nullable=True,
        description="CES `CC24_410`, 2024 presidential vote. For reference only, never in the prompt. Missing if the "
        "respondent was not asked (they did not say they definitely voted, in CES `CC24_401`) or did not answer.",
    )
    weight: float = pa.Field(
        gt=0,
        description="CES `commonpostweight`: how many people the persona stands for, relative to an average respondent. "
        "The CES guide says to use it with any post-election question, and `vote_2024` is one. It exists only for "
        "respondents who took the post-election wave (`tookpost`), so only they can be personas.",
    )

    class Config:
        strict = True  # no extra or missing columns


class Candidates(pa.DataFrameModel):
    """One row per candidate on the November ballot. Made by #3."""

    state: str = pa.Field(isin=STATES, description=STATE)
    candidate: str = pa.Field(unique=True, description="Candidate's name as on the ballot.")
    party: str = pa.Field(isin=PARTIES, description='Party label on the ballot, used in the prompt, e.g. "Smith (Democrat)".')
    incumbent: bool = pa.Field(description="True for whoever holds the seat now.")
    dem_caucus_probability: float = pa.Field(
        ge=0, le=1,
        description="Chance the candidate caucuses with the Democrats if they win: 1 for Democrats, 0 for Republicans, "
        "our rough guess for independents (`INDEPENDENT_DEM_CAUCUS_PROBABILITY` in senate_simulation.py).",
    )

    class Config:
        strict = True


class Responses(pa.DataFrameModel):
    """One row per LLM answer. responses_sean and responses_furkan are each person's full run in #6;
    responses is the two stacked together in #7, and is what the forecast uses."""

    approach: str = pa.Field(description="Whose run produced the answer (`sean` or `furkan`): their models and prompt.")
    persona_id: int = pa.Field(ge=0, description=PERSONA_ID)
    state: str = pa.Field(isin=STATES, description="The persona's state. " + STATE)
    model: str = pa.Field(description="OpenRouter model id.")
    draw: int = pa.Field(ge=0, description="Repeat number, from 0 up: the same persona asked the same question again.")
    question: str = pa.Field(
        isin=QUESTIONS,
        description="`senate`: the persona's own Senate race. `generic`: which party they would vote for. "
        "`alaska_final`: Alaska's ranked-choice final round (Alaska personas only).",
    )
    answer: str = pa.Field(
        nullable=True,
        description="A candidate on the persona's ballot (for `senate` and `alaska_final`), a party (for `generic`), "
        '"Undecided" or "Would not vote". Missing when the model gave no usable answer: kept and counted, '
        "never dropped or filled in.",
    )
    input_tokens: int = pa.Field(ge=0, description="Tokens sent to the model, as reported by OpenRouter.")
    output_tokens: int = pa.Field(ge=0, description="Tokens the model returned, as reported by OpenRouter.")
    cost: float = pa.Field(ge=0, description="Dollar cost of the call, as reported by OpenRouter.")

    class Config:
        strict = True


class Frame(pa.DataFrameModel):
    """Number of voters in each state and demographic cell, for post-stratification. Made by #8 from 2022 CES
    validated voters (a midterm electorate)."""

    state: str = pa.Field(isin=STATES, description=CES_STATE)
    age_group: str = pa.Field(isin=AGE_GROUPS, description=AGE_GROUP)
    gender: str = pa.Field(isin=GENDERS, description=GENDER)
    race: str = pa.Field(isin=RACES, description=RACE)
    education: str = pa.Field(isin=EDUCATION, description=EDUCATION_LEVEL)
    party_group: str = pa.Field(
        isin=PARTY_GROUPS,
        description="CES `pid7` collapsed to 3 groups with `PARTY_GROUP_OF` in schemas.py: strong, not very strong and "
        'leaning partisans count with their party; independents and not sure are "Independent or other". '
        "In #8 the `party_id` in personas is collapsed the same way.",
    )
    count: int = pa.Field(ge=0, description="Weighted number of validated voters in the cell. Zero if the cell has none.")

    class Config:
        strict = True


class Forecast(pa.DataFrameModel):
    """One row per simulated election, state and candidate. Made by #8 with the Monte Carlo in senate_simulation.py."""

    sim_id: int = pa.Field(ge=0, description="Simulated election number, from 0 up.")
    state: str = pa.Field(isin=STATES, description=STATE)
    candidate: str = pa.Field(description="Candidate's name, as in candidates.")
    party: str = pa.Field(isin=PARTIES, description="Candidate's party, as in candidates.")
    share: float = pa.Field(
        ge=0, le=1,
        description="Candidate's share of the votes for candidates in this simulated election (undecided, "
        "would not vote and missing answers are left out). Alaska: the final ranked-choice round.",
    )
    winner: bool = pa.Field(description="True for the candidate with the highest share.")

    class Config:
        strict = True


class PastResults(pa.DataFrameModel):
    """Earlier results in each race state: the last Senate election for the seat up in 2026, and the 2024
    presidential election. Made by #3 from the MIT Election Lab. A comparison on the website, not a forecast input."""

    state: str = pa.Field(isin=STATES, description=STATE)
    election: str = pa.Field(
        description='Which election: "senate_2020", "senate_2022" or "senate_2024_special" (the last election for the '
        'seat, from MIT `year` and `special`; Georgia 2020 uses its January runoff, which decided the seat), or '
        '"president_2024".',
    )
    dem_share: float = pa.Field(
        ge=0, le=1,
        description="Democratic share of all votes cast in the race (MIT `party_simplified` DEMOCRAT, which includes "
        "Minnesota's DFL), so the two shares need not sum to 1.",
    )
    rep_share: float = pa.Field(ge=0, le=1, description="Republican share of all votes cast in the race.")

    class Config:
        strict = True


class Polls(pa.DataFrameModel):
    """One row per candidate in each general-election poll of a 2026 Senate race. Made by #10 from the VoteHub
    polls API (CC BY 4.0). A comparison on the website, not a forecast input."""

    poll_id: str = pa.Field(description="VoteHub's id for the poll. Links the rows (one per candidate) of one poll.")
    state: str = pa.Field(isin=STATES, description=STATE + " From VoteHub `subject`, e.g. \"2026 Texas\".")
    pollster: str = pa.Field(description="VoteHub `pollster`, unchanged.")
    start_date: datetime.date = pa.Field(description="The poll's first day of interviews (VoteHub `start_date`).")
    date: datetime.date = pa.Field(description="The poll's last day of interviews (VoteHub `end_date`).")
    sample_size: int = pa.Field(
        gt=0, nullable=True, description="Number of people interviewed (VoteHub `sample_size`). Missing if VoteHub has none.",
    )
    population: str = pa.Field(
        isin=POLL_POPULATIONS, nullable=True,
        description="Who was interviewed: VoteHub `population` lv, rv and a, written out. Missing if VoteHub has none.",
    )
    candidate: str = pa.Field(description="Candidate's name, as in candidates (VoteHub's spelling corrected where it differs).")
    share: float = pa.Field(
        ge=0, le=1,
        description="Candidate's share of everyone asked (VoteHub `pct` / 100). Undecided and other candidates are "
        "not rows, so a poll's shares usually sum to less than 1.",
    )

    class Config:
        strict = True


class Polymarket(pa.DataFrameModel):
    """One row per candidate per day: the Polymarket price of a share that pays $1 if the candidate wins their 2026
    Senate race. Made by #11 from Polymarket's "<State> Senate Election Winner" markets. A comparison on the
    website, not a forecast input."""

    state: str = pa.Field(isin=STATES, description=STATE)
    date: datetime.date = pa.Field(description="The day (UTC) of the price. The last price of each day is kept.")
    candidate: str = pa.Field(
        description="Candidate's name, as in candidates (Polymarket's market title without its party letter, "
        "corrected where it differs).",
    )
    price: float = pa.Field(
        ge=0, le=1,
        description="Price in dollars of a share that pays $1 if the candidate wins: roughly the market's chance "
        "that they win. A race's prices sum to about 1.",
    )

    class Config:
        strict = True


# Whether each poll-weighting rule was used (see poll_average.py), for the summary files below.
RULE_DESCRIPTIONS = {
    "by_recency": "Whether newer polls count more (weight halves every 14 days).",
    "by_sample_size": "Whether polls that asked more people count more (by the square root of the sample size).",
    "by_pollster": "Whether a pollster's recent polls share one weight (each divided by the square root of their number).",
    "by_population": "Whether likely voters count more than registered voters (x0.8) and adults (x0.6).",
}


class PollAverages(pa.DataFrameModel):
    """One row per race, on/off combination of the weighting rules, day and candidate: the polling average.
    Made by #12 into data/03-summary_data/ for the website's polls chart. Days run from the race's first poll to
    the latest poll in any race."""

    state: str = pa.Field(isin=STATES, description=STATE)
    by_recency: bool = pa.Field(description=RULE_DESCRIPTIONS["by_recency"])
    by_sample_size: bool = pa.Field(description=RULE_DESCRIPTIONS["by_sample_size"])
    by_pollster: bool = pa.Field(description=RULE_DESCRIPTIONS["by_pollster"])
    by_population: bool = pa.Field(description=RULE_DESCRIPTIONS["by_population"])
    date: datetime.date = pa.Field(description="The day of the average. It uses the polls that finished by then.")
    candidate: str = pa.Field(description="Candidate's name, as in candidates.")
    average: float = pa.Field(
        ge=0, le=1, description="Weighted mean of the candidate's share in the polls that asked about them. Each poll's "
        "shares are first scaled to add up to 1 among its candidates, so undecided voters are left out.",
    )
    spread: float = pa.Field(
        ge=0, description="Weighted standard deviation of those shares around the average: how much the polls "
        "disagree. Not a margin of error.",
    )

    class Config:
        strict = True


class PollInfluence(pa.DataFrameModel):
    """One row per poll and on/off combination of the weighting rules: the poll's weight in its race's average on
    the last day. Made by #12 into data/03-summary_data/ for the website's polls table."""

    state: str = pa.Field(isin=STATES, description=STATE)
    poll_id: str = pa.Field(description="VoteHub's id for the poll, as in polls.")
    by_recency: bool = pa.Field(description=RULE_DESCRIPTIONS["by_recency"])
    by_sample_size: bool = pa.Field(description=RULE_DESCRIPTIONS["by_sample_size"])
    by_pollster: bool = pa.Field(description=RULE_DESCRIPTIONS["by_pollster"])
    by_population: bool = pa.Field(description=RULE_DESCRIPTIONS["by_population"])
    influence: float = pa.Field(
        ge=0, description="The poll's weight: the rules switched on, multiplied together. 1 is a typical poll: "
        "a 600-person likely-voter poll that ended that day, its pollster's only recent poll of the race.",
    )

    class Config:
        strict = True


class PolymarketPrices(Polymarket):
    """One row per candidate per day: the Polymarket price, as in polymarket. Made by #12 into data/03-summary_data/
    for the website's Polymarket chart."""


class PolymarketLatest(Polymarket):
    """One row per candidate: their latest Polymarket price and its day. Made by #12 into data/03-summary_data/ for
    the website's "Traders give ... a ...% chance to win" numbers."""


class RunCosts(pa.DataFrameModel):
    """One row per model, and one for all models, for each run of scripts/05-query_models.py that asked the models:
    what the run's answers cost. Each run adds its rows to data/run_costs.csv, so earlier runs are kept."""

    run_at: str = pa.Field(description="When the run finished, in UTC (ISO 8601).")
    approach: str = pa.Field(isin=["sean", "furkan"], description="Whose approach the run used.")
    data: str = pa.Field(isin=["simulated", "real"], description="Whether the run asked the simulated or the real personas.")
    wording: str = pa.Field(isin=["v1", "v2"], description="The question wording (see QUESTION_WORDINGS in queries.py).")
    model: str = pa.Field(description="OpenRouter model id, or \"all models\" for the run's total.")
    calls: int = pa.Field(ge=0, description="Number of answers: personas x questions x draws.")
    personas: int = pa.Field(ge=0, description="Number of personas asked.")
    total_cost: float = pa.Field(
        ge=0, description="Dollars the answers cost (OpenRouter's reported cost). Answers taken from the cache count "
        "at what they cost when first asked.",
    )
    cost_per_persona: float = pa.Field(ge=0, description="total_cost / personas: the average cost of one persona.")

    class Config:
        strict = True


# Each data file and the schema it must match. Used by the tests and the codebook.
FILE_SCHEMAS = {
    "personas": Personas,
    "candidates": Candidates,
    "responses_sean": Responses,
    "responses_furkan": Responses,
    "responses": Responses,
    "frame": Frame,
    "forecast": Forecast,
    "past_results": PastResults,
    "polls": Polls,
    "polymarket": Polymarket,
    "poll_averages": PollAverages,
    "poll_influence": PollInfluence,
    "polymarket_prices": PolymarketPrices,
    "polymarket_latest": PolymarketLatest,
    "run_costs": RunCosts,
}
# The files the simulation (#1) makes; the others exist only as real data.
SIMULATED_FILES = ["personas", "candidates", "responses_sean", "responses_furkan", "responses", "frame", "forecast"]
