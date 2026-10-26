#### Preamble ####
# Purpose: The forecast's numbers for the website: the chance of control and the seats (with their 95% interval),
#          the seat distribution, each candidate's vote share and chance of winning, and what the models answered.
#          Used by #12 scripts/12-summarize_results.py.
# Author: Furkan Danisman
# Date: 25 October 2026
# Pre-requisites: forecast and forecast_versions from scripts/08-forecast.py

import polars as pl

from senate_forecast_2026.senate_simulation import count_seats

# The 95% interval: the middle 95% of the simulated elections.
LOWER, UPPER = 0.025, 0.975


def seat_summary(forecast, candidates):
    """Democratic-caucus seats in each simulated election of `forecast`, summarized.

    Returns (control, distribution): control is one row with dem_control (the share of simulations with 51 or more
    Democratic-caucus seats), seats (the most common number, the tallest bar of the distribution; the lower one if two
    tie), seats_lower and seats_upper (the 95% interval); distribution has one row per number of seats, with the
    number and share of simulations that ended with it."""
    seats = count_seats(forecast, candidates)
    control = seats.select(
        dem_control=pl.col("dem_control").mean(),
        seats=pl.col("dem_seats").mode().min().cast(pl.Float64),
        seats_lower=pl.col("dem_seats").quantile(LOWER),
        seats_upper=pl.col("dem_seats").quantile(UPPER),
    )
    distribution = (
        seats.group_by("dem_seats").len("simulations")
        .with_columns(pl.col("dem_seats", "simulations").cast(pl.Int64), share=pl.col("simulations") / seats.height)
        .sort("dem_seats")
    )
    return control, distribution


def race_summary(forecast):
    """Each candidate's vote share across the simulated elections of `forecast` (the mean and the 95% interval) and
    their chance of winning (the share of simulations they win)."""
    return (
        forecast.group_by("state", "candidate", "party")
        .agg(
            share=pl.col("share").mean(),
            share_lower=pl.col("share").quantile(LOWER),
            share_upper=pl.col("share").quantile(UPPER),
            chance_of_winning=pl.col("winner").mean(),
        )
        .sort("state", "share", descending=[False, True])
    )


def answer_weights(responses, personas):
    """`responses` with a `weight` column: the persona's CES weight, divided by the number of draws of their model,
    so each persona's answers to one question from one model count as much as the persona."""
    return responses.join(personas.select("persona_id", pl.col("weight").alias("persona_weight")), on="persona_id").with_columns(
        weight=pl.col("persona_weight") / pl.col("draw").n_unique().over("model")
    )


def weighted_shares(rows, by, answer="answer"):
    """The weighted share of each `answer` within each group of `by` (rows need a `weight` column)."""
    return (
        rows.group_by(*by, answer).agg(pl.col("weight").sum())
        .with_columns(share=pl.col("weight") / pl.col("weight").sum().over(by))
        .drop("weight")
    )


def with_versions(per_model, by, values, missing_is_zero=False):
    """`per_model` (one row per approach, model and `by`, with the `values` columns) as the website's versions, like
    the forecast's: each model alone ("model"), and the models counted equally ("average") for all of them ("all")
    and for each approach ("approach", when there is more than one). With `missing_is_zero`, a model without a row
    counts as 0 (an answer it never gave); otherwise the average is of the models that have one. Returns version_type,
    version, approach, model, *by, *values."""
    def average(rows, version_type, version, approach):
        models = rows["model"].n_unique()
        mean = pl.col(values).sum() / models if missing_is_zero else pl.col(values).mean()
        return rows.group_by(*by).agg(mean).with_columns(
            version_type=pl.lit(version_type), version=pl.lit(version), approach=pl.lit(approach, pl.String),
            model=pl.lit("average"),
        )

    parts = [per_model.with_columns(version_type=pl.lit("model"), version=pl.col("model"))]
    parts.append(average(per_model, "all", "all", None))
    if per_model["approach"].n_unique() > 1:
        parts += [average(rows, "approach", approach, approach)
                  for (approach,), rows in per_model.group_by("approach", maintain_order=True)]
    columns = ["version_type", "version", "approach", "model", *by, *values]
    return pl.concat([part.select(columns) for part in parts])
