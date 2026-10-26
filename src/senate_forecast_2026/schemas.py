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


class ModelChecks(pa.DataFrameModel):
    """One row per answer in the instructor's checks on an approach's models, on a small slice of personas. Made by
    #6 scripts/06-check_models.py as model_checks_sean or model_checks_furkan."""

    approach: str = pa.Field(description="Whose models and settings (`sean` or `furkan`).")
    persona_id: int = pa.Field(ge=0, description=PERSONA_ID)
    state: str = pa.Field(isin=STATES, description="The persona's state. " + STATE)
    model: str = pa.Field(description="OpenRouter model id.")
    draw: int = pa.Field(ge=0, description="Repeat number, from 0 up, as in responses.")
    check: str = pa.Field(isin=["persona_state", "no_party_id"], description='"persona_state": asked which state '
                          'they live in. "no_party_id": asked their usual questions without the party ID line.')
    question: str = pa.Field(isin=["state", *QUESTIONS], description='"state" for persona_state; otherwise the '
                             "question, as in responses.")
    answer: str = pa.Field(nullable=True, description="A state name (persona_state) or an answer as in responses. "
                           "Missing when the model gave no usable answer.")
    input_tokens: int = pa.Field(ge=0, description="Tokens sent to the model, as reported by OpenRouter.")
    output_tokens: int = pa.Field(ge=0, description="Tokens the model returned, as reported by OpenRouter.")
    cost: float = pa.Field(ge=0, description="Dollar cost of the call, as reported by OpenRouter.")

    class Config:
        strict = True


class Frame(pa.DataFrameModel):
    """Number of voters in each state and demographic cell, for post-stratification. Made by #8 from 2024 CES
    validated voters (the same survey as the personas): each cell's share of its state's voters, times the state's
    2024 vote total."""

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
    count: int = pa.Field(
        ge=0, description="Number of voters in the cell: the cell's share of its state's validated 2024 CES voters "
        "(weighted with `vvweight`), times the state's 2024 total votes for President (MIT Election Lab). Zero if the "
        "cell has none.",
    )

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


class ForecastVersions(Forecast):
    """The forecast made from part of the answers: each approach's run alone, and each model's answers alone. Made by
    #8 the same way as forecast, so the website can compare them. One row per version, simulated election, state and
    candidate."""

    version_type: str = pa.Field(isin=["approach", "model"], description="Whether the version is one approach's "
                                 "run or one model's answers.")
    version: str = pa.Field(description="The approach (as in responses' `approach`) or the model (its OpenRouter "
                            "identifier, as in responses' `model`).")

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
    lower: float = pa.Field(
        ge=0, le=1, description="Lower end of the polls' 95% interval: average - 1.96 x spread, at least 0. Where 95% "
        "of the polls would fall if spread like a normal distribution; not a margin of error.",
    )
    upper: float = pa.Field(ge=0, le=1, description="Upper end of the polls' 95% interval: average + 1.96 x spread, "
                            "at most 1.")

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


class PollTable(pa.DataFrameModel):
    """One row per poll in today's average (every weighting rule on) and candidate: the website's table of polls
    under each race's chart. Made by #12 into data/03-summary_data/ from polls and poll_influence."""

    state: str = pa.Field(isin=STATES, description=STATE)
    poll_id: str = pa.Field(description="VoteHub's id for the poll, as in polls.")
    pollster: str = pa.Field(description="As in polls.")
    start_date: datetime.date = pa.Field(description="As in polls.")
    date: datetime.date = pa.Field(description="As in polls: the poll's last day of interviews.")
    sample_size: int = pa.Field(nullable=True, description="As in polls.")
    population: str = pa.Field(nullable=True, description="As in polls.")
    influence: float = pa.Field(ge=0, description="The poll's weight in today's average with every rule on, as in "
                                "poll_influence.")
    candidate: str = pa.Field(description="As in polls.")
    share: float = pa.Field(ge=0, le=1, description="The candidate's share as the poll reported it (undecided "
                            "included, so the shares can add up to less than 1).")
    leader: str = pa.Field(description="The candidate with the poll's highest share.")
    lead: float = pa.Field(ge=0, le=1, description="The leader's share minus the second candidate's (or the leader's "
                           "share when the poll asked about one candidate).")

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
VERSION_TYPE = 'Which answers the forecast is made from: "all" (both runs together, the forecast), "approach" (one ' \
    'approach\'s run) or "model" (one model\'s answers).'
VERSION = '"all", the approach (as in responses\' `approach`) or the model (its OpenRouter identifier).'
MODEL_OR_AVERAGE = 'The model (its OpenRouter identifier), or "average": the models counted equally.'


class ForecastControl(pa.DataFrameModel):
    """One row per forecast version: the chance of Democratic control and the Democratic-caucus seats. Made by #12
    into data/03-summary_data/ from forecast and forecast_versions."""

    version_type: str = pa.Field(isin=["all", "approach", "model"], description=VERSION_TYPE)
    version: str = pa.Field(description=VERSION)
    dem_control: float = pa.Field(ge=0, le=1, description="Share of the simulated elections with 51 or more "
                                  "Democratic-caucus seats (at 50-50 the Republican Vice President breaks the tie).")
    seats: float = pa.Field(ge=0, le=100, description="Democratic-caucus seats: the median of the simulated elections.")
    seats_lower: float = pa.Field(ge=0, le=100, description="Lower end of the 95% interval of the seats (2.5% of "
                                  "simulations have fewer).")
    seats_upper: float = pa.Field(ge=0, le=100, description="Upper end of the 95% interval of the seats (2.5% of "
                                  "simulations have more).")

    class Config:
        strict = True


class ForecastSeats(pa.DataFrameModel):
    """One row per forecast version and number of Democratic-caucus seats: how many simulated elections ended with
    it (the seat distribution chart). Made by #12 into data/03-summary_data/."""

    version_type: str = pa.Field(isin=["all", "approach", "model"], description=VERSION_TYPE)
    version: str = pa.Field(description=VERSION)
    dem_seats: int = pa.Field(ge=0, le=100, description="Democratic-caucus seats.")
    simulations: int = pa.Field(ge=1, description="Number of simulated elections with that many seats.")
    share: float = pa.Field(ge=0, le=1, description="Share of the simulated elections with that many seats.")

    class Config:
        strict = True


class ForecastRaces(pa.DataFrameModel):
    """One row per forecast version and candidate: their vote share and chance of winning, next to the polls and
    Polymarket (the race-by-race comparison). Made by #12 into data/03-summary_data/. Alaska: the final round."""

    version_type: str = pa.Field(isin=["all", "approach", "model"], description=VERSION_TYPE)
    version: str = pa.Field(description=VERSION)
    state: str = pa.Field(isin=STATES, description=STATE)
    candidate: str = pa.Field(description="Candidate's name, as in candidates.")
    party: str = pa.Field(isin=PARTIES, description="Candidate's party, as in candidates.")
    share: float = pa.Field(ge=0, le=1, description="Our estimate of the candidate's vote share: the mean across the "
                            "simulated elections (undecided left out).")
    share_lower: float = pa.Field(ge=0, le=1, description="Lower end of the 95% interval of the vote share.")
    share_upper: float = pa.Field(ge=0, le=1, description="Upper end of the 95% interval of the vote share.")
    chance_of_winning: float = pa.Field(ge=0, le=1, description="Share of the simulated elections the candidate wins.")
    poll_average: float = pa.Field(ge=0, le=1, nullable=True, description="Today's polling average with every rule "
                                   "on (undecided left out), as in poll_averages. Missing if the race has no polls.")
    poll_spread: float = pa.Field(ge=0, nullable=True, description="The polls' spread around that average, as in "
                                  "poll_averages. Not a margin of error.")
    poll_lower: float = pa.Field(ge=0, le=1, nullable=True, description="Lower end of the polls' 95% interval, as in "
                                 "poll_averages. Missing if the race has no polls.")
    poll_upper: float = pa.Field(ge=0, le=1, nullable=True, description="Upper end of the polls' 95% interval, as in "
                                 "poll_averages. Missing if the race has no polls.")
    polymarket_chance: float = pa.Field(ge=0, le=1, nullable=True, description="Polymarket's latest price, scaled to "
                                        "add up to 1 among the race's candidates. Missing if there is no price.")

    class Config:
        strict = True


ANSWER_VERSION_TYPE = 'Which version of the website it belongs to, as in forecast_versions: "model" (one model), ' \
    '"all" (the average of every model) or "approach" (the average of one approach\'s models).'
ANSWER_APPROACH = "The approach of the model, or of the approach's average (as in responses); missing for the " \
    'average of every model.'


class ModelAnswers(pa.DataFrameModel):
    """One row per version, question and answer: the weighted share of answers, for each model and for the models'
    average (all of them, and each approach's). Made by #12 into data/03-summary_data/. Senate answers are grouped by
    the chosen candidate's party."""

    version_type: str = pa.Field(isin=["all", "approach", "model"], description=ANSWER_VERSION_TYPE)
    version: str = pa.Field(description=VERSION)
    approach: str = pa.Field(nullable=True, description=ANSWER_APPROACH)
    model: str = pa.Field(description=MODEL_OR_AVERAGE)
    question: str = pa.Field(isin=["senate", "generic"], description='"senate" (the race we forecast) or "generic" '
                             "(the House question, a benchmark).")
    answer: str = pa.Field(description="The party of the chosen candidate (Senate), the party (House), Undecided, "
                           "Would not vote or Missing.")
    share: float = pa.Field(ge=0, le=1, description="Share of the answers, weighted by the personas' CES weights; "
                            "each persona's draws from one model count once in total. For an average, a model that "
                            "never gave the answer counts as 0.")

    class Config:
        strict = True


class Crosstabs(pa.DataFrameModel):
    """One row per version, question, persona detail, group and party: the party's share of the group's answers for
    a party. Made by #12 into data/03-summary_data/."""

    version_type: str = pa.Field(isin=["all", "approach", "model"], description=ANSWER_VERSION_TYPE)
    version: str = pa.Field(description=VERSION)
    approach: str = pa.Field(nullable=True, description=ANSWER_APPROACH)
    model: str = pa.Field(description=MODEL_OR_AVERAGE)
    question: str = pa.Field(isin=["senate", "generic"], description='"senate" or "generic" (House), as in '
                             "model_answers.")
    variable: str = pa.Field(description="The persona detail, as in personas (e.g. gender).")
    group: str = pa.Field(description="The group (e.g. Woman).")
    party: str = pa.Field(isin=["Democrat", "Independent", "Republican"], description="Democrat, Independent (Senate "
                          "only: an independent candidate) or Republican.")
    share: float = pa.Field(ge=0, le=1, description="The party's share of the group's answers for a party (Undecided, "
                            "Would not vote and the House's Other left out), weighted as in model_answers. For an "
                            "average, the models that have answers in the group, counted equally.")
    personas: int = pa.Field(ge=1, description="Number of personas in the group with an answer for a party (for an "
                             "average, the models' numbers averaged).")

    class Config:
        strict = True


class PersonaComposition(pa.DataFrameModel):
    """One row per persona detail and group: how many personas are in it. Made by #12 into data/03-summary_data/."""

    variable: str = pa.Field(description="The persona detail, as in personas (e.g. gender).")
    group: str = pa.Field(description="The group (e.g. Woman), or Missing.")
    personas: int = pa.Field(ge=1, description="Number of personas in the group.")

    class Config:
        strict = True


class PastComparison(pa.DataFrameModel):
    """One row per race and election (and, for our 2026 estimate, per version): the Republican share in past
    elections next to our estimate. Made by #12 into data/03-summary_data/ from past_results and forecast_races."""

    version_type: str = pa.Field(isin=["all", "approach", "model"], nullable=True, description=VERSION_TYPE + " "
                                 "Missing for past elections, which are the same in every version.")
    version: str = pa.Field(nullable=True, description=VERSION + " Missing for past elections.")
    state: str = pa.Field(isin=STATES, description=STATE)
    election: str = pa.Field(description='As in past_results ("president_2024", "senate_2020", ...), or '
                             '"forecast_2026": our estimate.')
    republican_share: float = pa.Field(ge=0, le=1, description="Republican share: of all votes cast in past "
                                       "elections (as in past_results); of the votes for the race's candidates in "
                                       "our estimate (undecided left out).")
    lower: float = pa.Field(ge=0, le=1, nullable=True, description="Our estimate: lower end of its 95% interval. "
                            "Missing for past elections.")
    upper: float = pa.Field(ge=0, le=1, nullable=True, description="Our estimate: upper end of its 95% interval. "
                            "Missing for past elections.")

    class Config:
        strict = True


class Models(pa.DataFrameModel):
    """One row per approach and model: how the model was asked and what came back. Made by #12 into
    data/03-summary_data/ from the approach settings (src/senate_forecast_2026/queries.py) and responses."""

    approach: str = pa.Field(description="As in responses.")
    model: str = pa.Field(description="The model's OpenRouter identifier, as in responses.")
    kind: str = pa.Field(isin=["chat model", "decision model"], description="A chat model writes its answer; a "
                         "decision model gives a probability for each option, and each draw is a random pick from them.")
    draws: int = pa.Field(ge=1, description="How many times the model was asked each question.")
    temperature: float = pa.Field(ge=0, nullable=True, description="The sampling temperature. Missing for a decision "
                                  "model, which has none.")
    wording: str = pa.Field(description="The question wording, as in queries.py (v1 or v2).")
    personas: int = pa.Field(ge=1, description="Number of personas the model answered as.")
    answers: int = pa.Field(ge=1, description="Number of answers (rows of responses).")
    missing: int = pa.Field(ge=0, description="Answers that failed or were not one of the options.")
    input_tokens: int = pa.Field(ge=0, description="Total input tokens, as in responses.")
    output_tokens: int = pa.Field(ge=0, description="Total output tokens, as in responses.")
    cost: float = pa.Field(ge=0, description="Total cost in US dollars, as OpenRouter reported it.")

    class Config:
        strict = True


class Costs(pa.DataFrameModel):
    """One row per approach and model (and "all models"): what each approach's latest full run cost. Made by #12 into
    data/03-summary_data/ from the run cost log, data/run_costs.csv."""

    approach: str = pa.Field(description="Whose approach, as in responses.")
    run_at: str = pa.Field(description="When the run finished, as in run_costs.")
    model: str = pa.Field(description='The model\'s OpenRouter identifier, or "all models".')
    calls: int = pa.Field(ge=0, description="Number of answers.")
    personas: int = pa.Field(ge=1, description="Number of personas asked.")
    total_cost: float = pa.Field(ge=0, description="Total cost in US dollars, as OpenRouter charged it.")
    cost_per_persona: float = pa.Field(ge=0, description="Total cost divided by the number of personas.")

    class Config:
        strict = True


class CheckResults(pa.DataFrameModel):
    """One row per approach, model and check: the result of the instructor's checks. Made by #12 into
    data/03-summary_data/ from model_checks_sean and model_checks_furkan."""

    approach: str = pa.Field(description="Whose models and settings (`sean` or `furkan`).")
    model: str = pa.Field(description="OpenRouter model id.")
    check: str = pa.Field(isin=["persona_state", "no_party_id"], description="As in model_checks.")
    personas: int = pa.Field(ge=1, description="Number of personas checked.")
    count: int = pa.Field(ge=0, description="persona_state: personas who named their own state in every draw. "
                          "no_party_id: personas whose most common answer to at least one question changed without "
                          "the party ID line (a tie between answers counts as a change if the tied answers differ).")
    cost: float = pa.Field(ge=0, description="Dollar cost of the check's answers, as first charged.")

    class Config:
        strict = True


class CheckAnswers(pa.DataFrameModel):
    """One row per approach, model, persona, check, question, prompt and answer: how many draws gave it (the
    checks' table on the website). Made by #12 into data/03-summary_data/."""

    approach: str = pa.Field(description="Whose models and settings (`sean` or `furkan`).")
    model: str = pa.Field(description="OpenRouter model id.")
    persona_id: int = pa.Field(ge=0, description=PERSONA_ID)
    state: str = pa.Field(isin=STATES, description="The persona's state. " + STATE)
    party_id: str = pa.Field(description="The persona's party ID, as in personas.")
    check: str = pa.Field(isin=["persona_state", "no_party_id"], description="As in model_checks.")
    question: str = pa.Field(isin=["state", *QUESTIONS], description="As in model_checks.")
    prompt: str = pa.Field(isin=["as asked", "with party ID", "without party ID"], description='"as asked" for '
                           'persona_state; for no_party_id, "with party ID" (the full run) or "without party ID".')
    answer: str = pa.Field(description="The answer, or Missing.")
    draws: int = pa.Field(ge=1, description="Number of draws that gave this answer.")

    class Config:
        strict = True


FILE_SCHEMAS = {
    "personas": Personas,
    "candidates": Candidates,
    "responses_sean": Responses,
    "responses_furkan": Responses,
    "responses": Responses,
    "frame": Frame,
    "forecast": Forecast,
    "forecast_versions": ForecastVersions,
    "past_results": PastResults,
    "polls": Polls,
    "polymarket": Polymarket,
    "poll_averages": PollAverages,
    "poll_influence": PollInfluence,
    "polymarket_prices": PolymarketPrices,
    "polymarket_latest": PolymarketLatest,
    "run_costs": RunCosts,
    "forecast_control": ForecastControl,
    "forecast_seats": ForecastSeats,
    "forecast_races": ForecastRaces,
    "model_answers": ModelAnswers,
    "crosstabs": Crosstabs,
    "persona_composition": PersonaComposition,
    "costs": Costs,
    "past_comparison": PastComparison,
    "model_checks_sean": ModelChecks,
    "model_checks_furkan": ModelChecks,
    "check_results": CheckResults,
    "check_answers": CheckAnswers,
}
# The files the simulation (#1) makes; the others exist only as real data.
SIMULATED_FILES = ["personas", "candidates", "responses_sean", "responses_furkan", "responses", "frame", "forecast"]
