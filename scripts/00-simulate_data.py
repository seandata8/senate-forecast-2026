#### Preamble ####
# Purpose: Simulate every file the pipeline will produce, so later scripts and tests can be written before real data exists:
#          personas, candidates, responses_sean, responses_furkan, responses, frame and forecast, in data/00-simulated_data/.
# Author: Sean Murphy
# Date: 21 October 2026
# Pre-requisites: uv sync. No API calls; nothing here costs money.
# Run from the repo root: uv run scripts/00-simulate_data.py

from itertools import product
from pathlib import Path

import numpy as np
import polars as pl

from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import (
    AGE_GROUPS,
    EDUCATION,
    GENDERS,
    IDEOLOGIES,
    NON_CANDIDATE_ANSWERS,
    PARTY_GROUPS,
    RACES,
    STATES,
    Candidates,
    Forecast,
    Frame,
    Personas,
    Responses,
)
from senate_forecast_2026.senate_simulation import (
    INDEPENDENT_DEM_CAUCUS_PROBABILITY,
    combined_state_error_sd,
    count_seats,
    simulate_races,
)
from senate_forecast_2026.simulation_settings import PERSONA_SHARES, STATE_LEAN

OUTPUT_FOLDER = Path("data/00-simulated_data")
random_generator = np.random.default_rng(853)

PERSONAS_PER_STATE = 30
# Each of us runs our own approach in #6, with models from at least two providers, as the instructions require.
APPROACH_MODELS = {
    "sean": ["provider-1/model-x", "provider-2/model-y"],
    "furkan": ["provider-1/model-x", "provider-3/model-z"],
}
DRAWS_PER_PERSONA = 3
N_SIMS = 10_000


def draw_categories(options, probabilities, count):
    """Draw `count` values from `options`, each with its probability (rescaled to sum to 1)."""
    probabilities = np.asarray(probabilities, dtype=float)
    return random_generator.choice(options, size=count, p=probabilities / probabilities.sum())


def draw_one(options, probabilities):
    """Draw a single value from `options`, each with its probability."""
    return draw_categories(options, probabilities, 1)[0]


#### Candidates ####
# Fake names, but each race has its real structure, so the code has to handle the unusual races from the start.
# Each candidate is (name after the state, party). Most races are a Democrat against a Republican.
print("Simulating candidates...", flush=True)
USUAL_RACE = [("Democrat", "Democrat"), ("Republican", "Republican")]
UNUSUAL_RACES = {
    "NE": [("Independent", "Independent"), ("Republican", "Republican")],  # no Democrat
    "ID": [("Independent", "Independent"), ("Republican", "Republican")],  # no Democrat
    "MT": [("Democrat", "Democrat"), ("Republican", "Republican"), ("Independent", "Independent")],
    "AK": [  # ranked choice, with three Republicans on the ballot
        ("Democrat", "Democrat"), ("Republican", "Republican"),
        ("Republican 2", "Republican"), ("Republican 3", "Republican"),
    ],
}
DEM_CAUCUS_PROBABILITY_BY_PARTY = {"Democrat": 1.0, "Republican": 0.0}  # independents: see senate_simulation.py
candidate_rows = []
for state in STATES:
    incumbent_party = "Democrat" if STATE_LEAN[state] > 0.5 else "Republican"
    for name, party in UNUSUAL_RACES.get(state, USUAL_RACE):
        if party == "Independent":
            dem_caucus_probability = INDEPENDENT_DEM_CAUCUS_PROBABILITY[state]
        else:
            dem_caucus_probability = DEM_CAUCUS_PROBABILITY_BY_PARTY[party]
        candidate_rows.append({
            "state": state,
            "candidate": f"{state} {name}",  # e.g. "TX Democrat", "AK Republican 2"
            "party": party,
            "incumbent": name == incumbent_party,  # the main candidate of the state's leading party
            "dem_caucus_probability": dem_caucus_probability,
        })
candidates = pl.DataFrame(candidate_rows)


#### Personas ####
# Demographics are drawn independently. Party ID then depends on the state's lean and on race, education and age,
# and ideology and 2024 vote depend on party ID, so the variables relate to each other the way they do in real data.
print("Simulating personas...", flush=True)
n_personas = len(STATES) * PERSONAS_PER_STATE
persona_columns = {
    "persona_id": np.arange(n_personas),
    "state": np.repeat(STATES, PERSONAS_PER_STATE),
}
# Each demographic column drawn with the shares in simulation_settings.py (the tests check them against these).
for column, (categories, shares) in PERSONA_SHARES.items():
    persona_columns[column] = draw_categories(categories, shares, n_personas)
personas = pl.DataFrame(persona_columns)


def effect_of(column, effects):
    """Each persona's effect from `effects` ({category: effect}), or 0 for a category not listed."""
    return personas[column].replace_strict(effects, default=0.0).to_numpy()


# How Democratic each persona leans, on the log-odds scale: the state's lean, plus group effects, plus individual noise.
# The group effects are centered (average 0), so each state still averages out near its STATE_LEAN.
state_lean = personas["state"].replace_strict(STATE_LEAN).to_numpy()
group_effect = (
    effect_of("race", {"Black": 2.0, "Hispanic": 0.6, "Asian": 0.6})
    + effect_of("education", {"Post-grad": 0.5, "4-year": 0.3, "No HS": -0.2})
    + effect_of("age_group", {"18-29": 0.4, "65+": -0.1})
)
group_effect = group_effect - group_effect.mean()
democratic_leaning = np.log(state_lean / (1 - state_lean)) + group_effect + random_generator.normal(0, 1.5, n_personas)

# Party ID: cut the leaning into seven bands, from most Republican to most Democratic, then mark 2% "Not sure".
PARTY_IDS_REPUBLICAN_TO_DEMOCRAT = [
    "Strong Republican", "Not very strong Republican", "Lean Republican", "Independent",
    "Lean Democrat", "Not very strong Democrat", "Strong Democrat",
]
BAND_EDGES = [-2.0, -1.0, -0.4, 0.4, 1.0, 2.0]  # 6 edges make 7 bands
band = np.digitize(democratic_leaning, BAND_EDGES)  # 0 below the first edge, 6 above the last
party_id = np.array(PARTY_IDS_REPUBLICAN_TO_DEMOCRAT)[band].astype(object)
party_id[random_generator.random(n_personas) < 0.02] = "Not sure"

# Ideology follows party ID, with some spread: Democrats lean liberal, Republicans conservative.
IDEOLOGY_PROBABILITIES = {  # Very liberal, Liberal, Moderate, Conservative, Very conservative, Not sure
    "Strong Democrat": [0.35, 0.40, 0.20, 0.03, 0.01, 0.01],
    "Not very strong Democrat": [0.10, 0.40, 0.40, 0.07, 0.01, 0.02],
    "Lean Democrat": [0.15, 0.40, 0.35, 0.06, 0.01, 0.03],
    "Independent": [0.03, 0.10, 0.55, 0.15, 0.04, 0.13],
    "Lean Republican": [0.01, 0.04, 0.35, 0.45, 0.12, 0.03],
    "Not very strong Republican": [0.01, 0.05, 0.35, 0.45, 0.12, 0.02],
    "Strong Republican": [0.01, 0.02, 0.10, 0.45, 0.41, 0.01],
    "Not sure": [0.03, 0.07, 0.35, 0.10, 0.05, 0.40],
}
ideology = [draw_one(IDEOLOGIES, IDEOLOGY_PROBABILITIES[party]) for party in party_id]

# Probability of voting for the Democratic side, by party ID. Used for the 2024 vote here and for the answers below.
DEMOCRATIC_PROBABILITY = {
    "Strong Democrat": 0.97, "Not very strong Democrat": 0.88, "Lean Democrat": 0.85, "Independent": 0.50,
    "Lean Republican": 0.15, "Not very strong Republican": 0.12, "Strong Republican": 0.03, "Not sure": 0.50,
}
democratic_probability = np.array([DEMOCRATIC_PROBABILITY[party] for party in party_id])

# 2024 vote: Harris or Trump by party ID, then 6% did not vote, 3% voted third party and 3% left it blank.
# dtype=object so the array can hold names of any length and None (a plain numpy string array cannot).
vote_2024 = np.where(random_generator.random(n_personas) < democratic_probability, "Kamala Harris", "Donald Trump").astype(object)
roll = random_generator.random(n_personas)
did_not_vote = roll < 0.06
voted_third_party = (roll >= 0.06) & (roll < 0.09)
left_blank = (roll >= 0.09) & (roll < 0.12)
vote_2024[did_not_vote] = "Did not vote for President"
vote_2024[voted_third_party] = draw_categories(
    ["Robert F. Kennedy, Jr.", "Jill Stein", "Cornel West", "Chase Oliver", "Other"], [1] * 5, voted_third_party.sum()
)
vote_2024[left_blank] = None

# Survey weights: positive and skewed (lognormal), then divided by the state's average so they average 1 within each state.
personas = personas.with_columns(
    party_id=pl.Series(party_id, dtype=pl.String),
    ideology=pl.Series(ideology, dtype=pl.String),
    vote_2024=pl.Series(vote_2024, dtype=pl.String),
    weight=pl.Series(random_generator.lognormal(0, 0.5, n_personas)),
).with_columns(
    weight=pl.col("weight") / pl.col("weight").mean().over("state"),
).select(Personas.to_schema().columns.keys())  # columns in the agreed order


#### Responses ####
# One answer per model, draw, persona and question, for each of our two runs. The answer depends on the persona's
# party ID, with a small push one way or the other for each model and extra noise in Furkan's run, so the runs differ.
print("Simulating responses...", flush=True)
MODEL_SHIFT = {"provider-1/model-x": 0.0, "provider-2/model-y": 0.03, "provider-3/model-z": -0.02}
APPROACH_NOISE = {"sean": 0.0, "furkan": 0.08}


def candidate_probabilities(state, democratic_side):
    """{candidate: probability of choosing them} in this state, for someone with this Democratic-side probability."""
    republican_side = 1 - democratic_side
    if state in ("NE", "ID"):  # the independent picks up Democratic-side voters and a few Republicans
        return {f"{state} Independent": democratic_side + 0.05 * republican_side, f"{state} Republican": 0.95 * republican_side}
    if state == "MT":
        return {
            "MT Democrat": 0.7 * democratic_side,
            "MT Republican": 0.9 * republican_side,
            "MT Independent": 0.3 * democratic_side + 0.1 * republican_side,
        }
    if state == "AK":
        return {
            "AK Democrat": democratic_side,
            "AK Republican": 0.8 * republican_side,
            "AK Republican 2": 0.15 * republican_side,
            "AK Republican 3": 0.05 * republican_side,
        }
    return {f"{state} Democrat": democratic_side, f"{state} Republican": republican_side}


def simulate_answer(state, question, democratic_side):
    """One answer: 2% missing (None), 2% would not vote, 4% undecided, otherwise a choice."""
    roll = random_generator.random()
    if roll < 0.02:
        return None
    if roll < 0.04:
        return "Would not vote"
    if roll < 0.08:
        return "Undecided"
    if question == "generic":
        choices = {"Democrat": democratic_side, "Republican": 1 - democratic_side, "Other": 0.03}
    elif question == "alaska_final":
        choices = {"AK Democrat": democratic_side, "AK Republican": 1 - democratic_side}
    else:
        choices = candidate_probabilities(state, democratic_side)
    return draw_one(list(choices.keys()), list(choices.values()))


def simulate_run(approach):
    """One person's full run (#6): every persona answers every question with each of their models, DRAWS_PER_PERSONA times."""
    rows = []
    # product() loops over every combination of model and draw.
    for model, draw in product(APPROACH_MODELS[approach], range(DRAWS_PER_PERSONA)):
        for persona_id, state, persona_democratic_probability in zip(personas["persona_id"], personas["state"], democratic_probability):
            noise = random_generator.normal(0, APPROACH_NOISE[approach])
            democratic_side = float(np.clip(persona_democratic_probability + MODEL_SHIFT[model] + noise, 0.01, 0.99))
            questions = ["senate", "generic"] + (["alaska_final"] if state == "AK" else [])
            for question in questions:
                input_tokens = int(random_generator.normal(350, 30))
                output_tokens = int(random_generator.normal(25, 5))
                rows.append({
                    "approach": approach,
                    "persona_id": int(persona_id),
                    "state": state,
                    "model": model,
                    "draw": draw,
                    "question": question,
                    "answer": simulate_answer(state, question, democratic_side),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost": (input_tokens * 0.20 + output_tokens * 0.80) / 1_000_000,  # $0.20 and $0.80 per million tokens
                })
    return pl.DataFrame(rows, schema_overrides={"answer": pl.String})


responses_sean = simulate_run("sean")
responses_furkan = simulate_run("furkan")
# #7: stack the two runs into the one file the forecast, tests and website use.
responses = pl.concat([responses_sean, responses_furkan])
print(f"  {responses.height:,} answers", flush=True)


#### Frame ####
# Number of voters in every state x age x gender x race x education cell: each state's voter count times the
# national share of each category, with Poisson noise so some small cells come out as zero (as in real data).
print("Simulating frame...", flush=True)


def category_shares(column, categories, shares):
    """A small table of one column's categories and their national shares, e.g. age_group and age_group_share."""
    return pl.DataFrame({column: categories, f"{column}_share": shares})


frame = (
    pl.DataFrame({"state": STATES, "voters": random_generator.integers(250_000, 12_000_000, len(STATES))})
    .join(category_shares("age_group", AGE_GROUPS, [0.13, 0.24, 0.36, 0.27]), how="cross")
    .join(category_shares("gender", GENDERS, [0.47, 0.525, 0.004, 0.001]), how="cross")
    .join(category_shares("race", RACES, [0.72, 0.11, 0.09, 0.03, 0.01, 0.003, 0.025, 0.012]), how="cross")
    .join(category_shares("education", EDUCATION, [0.03, 0.25, 0.23, 0.11, 0.23, 0.15]), how="cross")
    .join(category_shares("party_group", PARTY_GROUPS, [0.45, 0.15, 0.40]), how="cross")
)
expected_count = (
    frame["voters"] * frame["age_group_share"] * frame["gender_share"] * frame["race_share"] * frame["education_share"]
    * frame["party_group_share"]
)
frame = frame.with_columns(count=pl.Series(random_generator.poisson(expected_count.to_numpy())))
frame = frame.select(Frame.to_schema().columns.keys())


#### Forecast ####
# Stand-in for #8: each candidate's weighted share of the answers, over all models and draws, then the Monte Carlo
# simulation. Alaska is decided by its ranked-choice final round, every other state by the Senate question.
# #8 will replace the weighted share with MRP, and the standard error below with the model's.
print(f"Simulating {N_SIMS:,} elections...", flush=True)
deciding_question = pl.when(pl.col("state") == "AK").then(pl.lit("alaska_final")).otherwise(pl.lit("senate"))
votes = (
    responses
    .filter(pl.col("question") == deciding_question)
    .filter(pl.col("answer").is_not_null() & ~pl.col("answer").is_in(NON_CANDIDATE_ANSWERS))
    .join(personas.select("persona_id", "weight"), on="persona_id", validate="m:1")  # m:1: each persona once in personas
)
state_shares = (
    votes.group_by("state", "answer").agg(pl.col("weight").sum())
    .with_columns(share=pl.col("weight") / pl.col("weight").sum().over("state"))
    .rename({"answer": "candidate"})
    .join(candidates.select("candidate", "party"), on="candidate", validate="m:1")
    .select("state", "candidate", "party", "share")
)
# Stand-in for the model's standard error: the standard error of each state's leading share, sqrt(p(1 - p) / n),
# with n the number of personas (a persona's repeated answers are not independent, so answers are not counted).
# The typical (median) state's standard error goes into the Monte Carlo's state error, as #8 will do.
leading_shares = state_shares.group_by("state").agg(pl.col("share").max())["share"]
standard_errors = (leading_shares * (1 - leading_shares) / PERSONAS_PER_STATE).sqrt()
typical_standard_error = standard_errors.median()
state_error_sd = combined_state_error_sd(typical_standard_error)
print(f"  state error {state_error_sd:.3f} (polling-sized 0.04 plus a standard error of {typical_standard_error:.3f})", flush=True)
forecast = simulate_races(state_shares, n_sims=N_SIMS, state_error_sd=state_error_sd)


#### Save ####
save_data(personas, Personas, OUTPUT_FOLDER, "personas")
save_data(candidates, Candidates, OUTPUT_FOLDER, "candidates")
# In the response samples, keep each persona's answers to every question together (one model and draw),
# and always add two Alaska personas, so the alaska_final question shows up too.
ONE_PERSONAS_ANSWERS = ["approach", "persona_id", "model", "draw"]
ALASKA = pl.col("state") == "AK"
for run_name, run in [("responses_sean", responses_sean), ("responses_furkan", responses_furkan), ("responses", responses)]:
    save_data(run, Responses, OUTPUT_FOLDER, run_name, sample_groups=ONE_PERSONAS_ANSWERS, also_sample_where=ALASKA)
save_data(frame, Frame, OUTPUT_FOLDER, "frame")
save_data(forecast, Forecast, OUTPUT_FOLDER, "forecast")

seats = count_seats(forecast, candidates)
print(f"Democratic control in {seats['dem_control'].mean():.1%} of simulations; "
      f"median Democratic-caucus seats {seats['dem_seats'].median():.0f}")
