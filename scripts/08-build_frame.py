#### Preamble ####
# Purpose: Build frame, in data/02-analysis_data/: the weighted number of voters in each state and demographic cell
#          (age group x gender x race x education x party group), from the 2024 CES validated voters (task #8).
#          With --turnout 2022, builds frame_2022 instead, from the 2022 CES validated voters (the last midterm), to
#          see how much the forecast depends on whose turnout it uses.
#          The forecast weights each cell's model estimate by this count (post-stratification). The CES gives each
#          cell's share of a state's voters; each state's count is its actual 2024 vote total, from the MIT
#          Election Lab, as in the simulated frame (#1).
# Author: Furkan Danisman
# Date: 24 October 2026; --turnout 2022 added 28 October 2026
# Pre-requisites: uv run scripts/01-download_election_data.py (without the full CES file, the committed sample is used)
#                 for the CES and the MIT presidential results
# Run: uv run scripts/08-build_frame.py (or PyCharm's run button); add --turnout 2022 for frame_2022

import argparse
import itertools

import polars as pl

from senate_forecast_2026.ces_codes import (
    EDUCATION_OF_CES_CODE,
    GENDER_OF_CES_CODE,
    PARTY_ID_OF_CES_CODE,
    RACE_OF_CES_CODE,
    STATE_OF_CES_CODE,
    age_group,
)
from senate_forecast_2026.paths import (
    ANALYSIS_DATA,
    RAW_CES_2022,
    RAW_CES_2024,
    RAW_PRESIDENT_RESULTS,
    SAMPLE_CES_2022,
    SAMPLE_CES_2024,
    full_file_or_sample,
)
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import (
    AGE_GROUPS,
    EDUCATION,
    GENDERS,
    PARTY_GROUP_OF,
    PARTY_GROUPS,
    RACES,
    STATES,
    Frame,
)

# The CES columns the frame is built from. The demographic codes are in ces_codes.py, shared with the personas.
CES_COLUMNS = [
    "inputstate",  # state they live in
    "birthyr",  # year of birth
    "gender4",  # gender
    "race",  # race, with Hispanic as one of its categories
    "educ",  # highest level of education
    "pid7",  # party ID on a 7-point scale
    "vvweight",  # weight for respondents matched to a voter registration record
]
# Each turnout year's CES (the full file and its committed sample), and the frame it makes.
CES_OF_TURNOUT = {2024: (RAW_CES_2024, SAMPLE_CES_2024), 2022: (RAW_CES_2022, SAMPLE_CES_2022)}
FRAME_OF_TURNOUT = {2024: "frame", 2022: "frame_2022"}
# TS_g2024 (TS_g2022 in the 2022 CES, with the same codes), from the CES 2024 guide: 1 absentee, 2 early, 3 mail, 4 polling place, 5 provisional, 6 voted by unknown
# method, 7 did not vote; missing if not matched to the voter file. "Any non-missing value below 7" is a validated
# vote record (the guide), and the guide recommends vvweight for describing voters.
VOTED_CODES = ["1", "2", "3", "4", "5", "6"]
CELL = ["state", "age_group", "gender", "race", "education", "party_group"]

parser = argparse.ArgumentParser(description="Build the post-stratification frame from the CES validated voters.")
parser.add_argument("--turnout", type=int, choices=sorted(CES_OF_TURNOUT), default=2024,
                    help="whose turnout: the 2024 voters (the forecast's frame) or the 2022 midterm voters")
arguments = parser.parse_args()
turnout_year = arguments.turnout
voted_column = f"TS_g{turnout_year}"  # how they voted in that general election, from the voter file (TargetSmart)


#### Read the CES ####
full_file, sample_file = CES_OF_TURNOUT[turnout_year]
ces_path = full_file_or_sample(full_file, sample_file)
# Read as text: the CES stores answers as codes ("1", "2", ...). "NA" means no answer, so it is read as missing.
ces = pl.read_csv(ces_path, columns=CES_COLUMNS + [voted_column], infer_schema_length=0, null_values="NA")
voters = ces.filter(pl.col(voted_column).is_in(VOTED_CODES), pl.col("inputstate").is_in(list(STATE_OF_CES_CODE)))
print(f"Read {ces.height:,} CES respondents; {voters.height:,} are validated {turnout_year} voters in the 35 race "
      "states", flush=True)


#### Turn the CES codes into the personas' groups ####
# The same tables as the personas, so each persona falls in exactly one cell. A code missing from its table stops
# the script with an error, so a coding mistake cannot slip through. Party ID is collapsed to 3 groups. Ages are
# in the survey's year, as the schema says.
voters = voters.with_columns(
    state=pl.col("inputstate").replace_strict(STATE_OF_CES_CODE),
    age_group=age_group(pl.col("birthyr"), survey_year=turnout_year),
    gender=pl.col("gender4").replace_strict(GENDER_OF_CES_CODE),
    race=pl.col("race").replace_strict(RACE_OF_CES_CODE),
    education=pl.col("educ").replace_strict(EDUCATION_OF_CES_CODE),
    party_group=pl.col("pid7").replace_strict(PARTY_ID_OF_CES_CODE).replace_strict(PARTY_GROUP_OF),
    weight=pl.col("vvweight").cast(pl.Float64),
)
missing = voters.select(CELL + ["weight"]).null_count()
print("Missing answers:", {column: missing[column][0] for column in CELL + ["weight"]}, flush=True)
voters = voters.drop_nulls(subset=CELL + ["weight"])


#### Count the voters in each cell ####
# Every possible cell, so cells with no voters are in the frame with count 0, as the schema says.
all_cells = pl.DataFrame(
    list(itertools.product(STATES, AGE_GROUPS, GENDERS, RACES, EDUCATION, PARTY_GROUPS)), schema=CELL, orient="row"
)
# The CES weights add up to about the number of respondents, so a cell's weight is tiny and would round to 0. Each
# cell's share of its state's weight is kept instead, times the state's actual number of 2024 voters (the total
# votes for President, MIT Election Lab), so the counts are numbers of voters, as in the simulated frame. The 2022
# frame keeps the 2024 totals too: each race depends only on the shares within its state.
president_2024 = pl.read_csv(RAW_PRESIDENT_RESULTS, infer_schema_length=10_000).filter(pl.col("year") == 2024)
state_voters = president_2024.group_by(pl.col("state_po").alias("state")).agg(pl.col("totalvotes").first())
weighted_counts = (
    voters.group_by(CELL)
    .agg(pl.col("weight").sum())
    .with_columns(state_share=pl.col("weight") / pl.col("weight").sum().over("state"))
    .join(state_voters, on="state")
    .with_columns(voters=pl.col("state_share") * pl.col("totalvotes"))
)
frame = (
    all_cells.join(weighted_counts.select(CELL + ["voters"]), on=CELL, how="left")
    .with_columns(count=pl.col("voters").fill_null(0).round(0).cast(pl.Int64))
    .drop("voters")
)
print(f"{frame.height:,} cells, {frame.filter(pl.col('count') > 0).height:,} with voters", flush=True)
print("Voters (weighted) in each state:")
print(frame.group_by("state").agg(pl.col("count").sum()).sort("state").transpose(include_header=False))


#### Save ####
if ces_path == sample_file:
    # A frame from the small sample only shows that the code runs, so it is checked but not saved.
    Frame.validate(frame, lazy=True)
    print("Built from the CES sample, so checked against the schema but not saved.")
else:
    save_data(frame, Frame, ANALYSIS_DATA, FRAME_OF_TURNOUT[turnout_year])
