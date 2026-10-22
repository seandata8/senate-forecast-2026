#### Preamble ####
# Purpose: Save a data file the same way in every script: check it against its schema, write the parquet,
#          and write a small readable sample CSV next to it.
# Author: Sean Murphy
# Date: 21 October 2026
# Pre-requisites: uv add polars "pandera[polars]"

import polars as pl

SAMPLE_SIZE = 25
EXTRA_SAMPLE_SIZE = 2  # groups added by `also_sample_where`
SAMPLE_SEED = 853  # fixed, so the sample is the same on every run and only changes when the data does


def save_data(data, schema, folder, name, sample_groups=None, also_sample_where=None):
    """Check `data` against `schema`, then write folder/name.parquet and folder/samp_name.csv.

    The check comes first, so a file that breaks the agreed format is never written.
    The sample is random rather than the first rows, which are often all one state or one simulation.
    `sample_groups` lists columns whose rows belong together, e.g. one persona's answers to every question.
    If given, the sample is 25 random groups with all their rows, instead of 25 random rows.
    `also_sample_where` (used with `sample_groups`) is a filter for rows that should always show up, e.g. Alaska
    personas: 2 random groups matching it are added to the sample."""
    schema.validate(data, lazy=True)  # lazy: report every problem at once, not just the first
    folder.mkdir(parents=True, exist_ok=True)
    # save the parquet file
    data.write_parquet(folder / f"{name}.parquet")

    if sample_groups is None:
        sample = data.sample(n=min(SAMPLE_SIZE, data.height), seed=SAMPLE_SEED)
    else:
        # Sorted first, so the same groups are picked on every run.
        groups = data.select(sample_groups).unique().sort(sample_groups)
        chosen_groups = groups.sample(n=min(SAMPLE_SIZE, groups.height), seed=SAMPLE_SEED)
        if also_sample_where is not None:
            matching_groups = data.filter(also_sample_where).select(sample_groups).unique().sort(sample_groups)
            extra_groups = matching_groups.sample(n=min(EXTRA_SAMPLE_SIZE, matching_groups.height), seed=SAMPLE_SEED)
            chosen_groups = pl.concat([chosen_groups, extra_groups]).unique()  # unique: in case a group was picked twice
        sample = data.join(chosen_groups, on=sample_groups, how="semi")  # semi: keep the rows of the chosen groups
    sample.write_csv(folder / f"samp_{name}.csv")
    print(f"  wrote {name}.parquet ({data.height:,} rows) and samp_{name}.csv", flush=True)
