#### Preamble ####
# Purpose: The forecast (task #8): fit the MRP model (mrp.py) to the LLM answers, post-stratify it with the frame to
#          get each candidate's vote share in each state, then simulate the election many times with the Monte Carlo
#          in senate_simulation.py, whose state error includes the model's own uncertainty. Saves forecast (both
#          runs together, as the plan says) and forecast_versions: the same forecast from each approach's answers
#          alone and from each model's answers alone, so the website can compare them (#12).
# Author: Furkan Danisman
# Date: 24 October 2026; versions by approach and model 25 October 2026
# Pre-requisites: personas, candidates, frame (scripts/08-build_frame.py) and responses
# Run: uv run scripts/08-forecast.py (or PyCharm's run button)
#      --responses <file> reads the answers from another file, e.g. one model's answers before the runs are combined

import argparse
from pathlib import Path

import numpy as np
import polars as pl

from senate_forecast_2026.mrp import PARTIES, design_matrix, fit, poststratify
from senate_forecast_2026.paths import ANALYSIS_DATA
from senate_forecast_2026.queries import alaska_final_candidates
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import NON_CANDIDATE_ANSWERS, PARTY_GROUP_OF, Forecast, ForecastVersions
from senate_forecast_2026.senate_simulation import combined_state_error_sd, count_seats, simulate_races

N_SIMS = 10_000  # simulated elections, as in the simulated forecast (#1)
N_MODEL_DRAWS = 1_000  # draws of the model's coefficients, to measure its uncertainty
MODEL_DRAW_SEED = 2026

parser = argparse.ArgumentParser(description="Fit the MRP model, post-stratify, and simulate the election.")
parser.add_argument("--responses", type=Path, default=ANALYSIS_DATA / "responses.parquet", help="the answers to use")
arguments = parser.parse_args()


#### Read data ####
personas = pl.read_parquet(ANALYSIS_DATA / "personas.parquet")
candidates = pl.read_parquet(ANALYSIS_DATA / "candidates.parquet")
frame = pl.read_parquet(ANALYSIS_DATA / "frame.parquet").filter(pl.col("count") > 0)  # empty cells add nothing
responses = pl.read_parquet(arguments.responses)
print(f"Read {responses.height:,} answers from {arguments.responses.name}: models {responses['model'].unique().sort().to_list()}")

# The candidates each race is decided between: in Alaska, its ranked-choice final round (the Democrat against the
# incumbent), elsewhere everyone on the ballot. Each race has at most one candidate per party.
race_candidates = pl.concat([
    candidates.filter(pl.col("state") != "AK"),
    alaska_final_candidates(candidates.filter(pl.col("state") == "AK")),
])
deciding_question = pl.when(pl.col("state") == "AK").then(pl.lit("alaska_final")).otherwise(pl.lit("senate"))


def make_forecast(responses, label):
    """The forecast from `responses`: fit the model, post-stratify, simulate. Returns the simulated elections
    (as in the Forecast schema) and prints a summary under `label`."""
    print(f"\n#### {label}: {responses.height:,} answers from {', '.join(responses['model'].unique().sort())} ####")
    # -- The answers the model learns from --
    # Each persona's answers to their deciding question. Undecided, would not vote and missing answers are left out,
    # as in the forecast's shares. Each persona's draws from one model share a weight of 1 (10 draws count 0.1 each),
    # because a persona's repeated answers are not independent, as in the simulated forecast (#1).
    votes = (
        responses.filter(pl.col("question") == deciding_question)
        .with_columns(weight=1 / pl.col("draw").n_unique().over("model"))
        .filter(pl.col("answer").is_not_null() & ~pl.col("answer").is_in(NON_CANDIDATE_ANSWERS))
        .join(race_candidates.select("state", pl.col("candidate").alias("answer"), "party"), on=["state", "answer"], validate="m:1")
        .join(personas.select("persona_id", "age_group", "gender", "race", "education", "party_id"), on="persona_id", validate="m:1")
        .with_columns(party_group=pl.col("party_id").replace_strict(PARTY_GROUP_OF))
    )
    print(f"{votes.height:,} answers for a candidate, from {votes['persona_id'].n_unique():,} personas")
    print(votes.group_by("party").agg(pl.col("weight").sum().round(1)).sort("party"))


    # -- Fit the model --
    on_ballot = set(race_candidates.select("state", "party").iter_rows())
    available = np.array([[float((state, party) in on_ballot) for party in PARTIES] for state in votes["state"]])
    chosen = np.column_stack([(votes["party"] == party).to_numpy().astype(float) for party in PARTIES])
    mode, covariance = fit(design_matrix(votes), chosen, available, votes["weight"].to_numpy())
    print("Model fitted", flush=True)


    # -- Post-stratify: each candidate's vote share in each state --
    def candidate_shares(coefficients):
        """Each candidate's share in each state, from the model's coefficients and the frame."""
        return poststratify(coefficients, frame, race_candidates).join(
            race_candidates.select("state", "party", "candidate"), on=["state", "party"], validate="1:1"
        )


    state_shares = candidate_shares(mode).select("state", "candidate", "party", "share")

    # The model's uncertainty: post-stratify with many draws of its coefficients, and take each state's standard
    # deviation of the leading candidate's share. The typical (median) state's goes into the Monte Carlo's state error.
    random_generator = np.random.default_rng(MODEL_DRAW_SEED)
    coefficient_draws = random_generator.multivariate_normal(mode.ravel(order="F"), covariance, N_MODEL_DRAWS)
    leading = state_shares.sort("share", descending=True).group_by("state", maintain_order=True).first()
    draw_shares = pl.concat([
        candidate_shares(draw.reshape(mode.shape, order="F")).with_columns(model_draw=pl.lit(i))
        for i, draw in enumerate(coefficient_draws)
    ]).join(leading.select("state", "candidate"), on=["state", "candidate"])
    standard_errors = draw_shares.group_by("state").agg(pl.col("share").std().alias("standard_error"))
    typical_standard_error = standard_errors["standard_error"].median()
    state_error_sd = combined_state_error_sd(typical_standard_error)
    print(f"Model standard error: typical state {typical_standard_error:.3f} "
          f"(from {standard_errors['standard_error'].min():.3f} to {standard_errors['standard_error'].max():.3f}); "
          f"state error in the simulation {state_error_sd:.3f}")


    # -- Simulate the election --
    forecast = simulate_races(state_shares, n_sims=N_SIMS, state_error_sd=state_error_sd)
    seats = count_seats(forecast, candidates)

    summary = (
        forecast.group_by("state", "candidate", "party")
        .agg(pl.col("share").mean().alias("vote_share"), pl.col("winner").mean().alias("chance_of_winning"))
        .join(standard_errors, on="state")
        .sort("state", "vote_share", descending=[False, True])
    )
    with pl.Config(tbl_rows=100):
        print(summary.with_columns(pl.col("vote_share", "chance_of_winning", "standard_error").round(3)))
    print(f"Democratic control in {seats['dem_control'].mean():.1%} of {N_SIMS:,} simulated elections; "
          f"Democratic-caucus seats: {seats['dem_seats'].median():.0f} "
          f"[{seats['dem_seats'].quantile(0.025):.0f}, {seats['dem_seats'].quantile(0.975):.0f}] 95% interval")
    return forecast


#### Every version ####
# Both runs together is the forecast (as the plan says). Each approach alone and each model alone are versions of
# it, made the same way, for the website's comparison. An approach is skipped if it is the only one (it would be the
# same as both runs together), and so is a model if it is the only one.
forecast = make_forecast(responses, "Both runs together")
versions = []
groups = [("approach", approach) for approach in responses["approach"].unique().sort()]
groups += [("model", model) for model in responses["model"].unique().sort()]
for version_type, version in groups:
    if responses[version_type].n_unique() == 1:
        continue
    version_forecast = make_forecast(responses.filter(pl.col(version_type) == version), f"{version_type}: {version}")
    versions.append(version_forecast.with_columns(version_type=pl.lit(version_type), version=pl.lit(version)))
if not versions:
    raise SystemExit("Only one approach and one model: there are no versions to compare")
forecast_versions = pl.concat(versions).select("version_type", "version", *forecast.columns)


#### Save ####
save_data(forecast, Forecast, ANALYSIS_DATA, "forecast", sample_groups=["sim_id"])
# The versions' shares are rounded to 4 decimals (0.01 points), which makes the file about a third of the size.
forecast_versions = forecast_versions.with_columns(pl.col("share").round(4))
save_data(forecast_versions, ForecastVersions, ANALYSIS_DATA, "forecast_versions", sample_groups=["version", "sim_id"])
