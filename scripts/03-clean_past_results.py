#### Preamble ####
# Purpose: Turn the MIT Election Lab results into past_results, in data/02-analysis_data/: for each of the 35 race
#          states, the last Senate election for the seat up in 2026 and the 2024 presidential election, as the
#          Democratic and Republican shares of all votes. A comparison for the website, not a forecast input.
# Author: Sean Murphy
# Date: 22 October 2026
# Pre-requisites: uv run scripts/01-download_election_data.py
# Run: uv run scripts/03-clean_past_results.py (or PyCharm's run button)

import polars as pl

from senate_forecast_2026.paths import ANALYSIS_DATA, RAW_PRESIDENT_RESULTS, RAW_SENATE_RESULTS
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import STATES, PastResults

# The last election for each seat up in 2026, as (year, special election?). Most seats were last up in 2020.
LAST_SENATE_ELECTION = {state: (2020, False) for state in STATES}
LAST_SENATE_ELECTION["OH"] = (2022, False)  # the seat JD Vance won in 2022
LAST_SENATE_ELECTION["FL"] = (2022, False)  # the seat Marco Rubio won in 2022
LAST_SENATE_ELECTION["NE"] = (2024, True)  # Pete Ricketts won a special election for this seat in 2024

# Errors in the MIT data: both main candidates in Wyoming 2020 are labelled "OTHER".
PARTY_CORRECTIONS = {
    ("WY", 2020, "CYNTHIA M. LUMMIS"): "REPUBLICAN",
    ("WY", 2020, "MERAV BEN DAVID"): "DEMOCRAT",
}

# Rows that count ballots, not votes for a candidate (Wyoming lists them).
NOT_CANDIDATES = ["OVER VOTES", "UNDER VOTES"]


def read_mit_results(path):
    """An MIT Election Lab file, with numbers as numbers, stage in lower case (it is written both "gen" and "GEN"),
    the party corrections applied, and the over and under vote rows removed."""
    results = pl.read_csv(path, infer_schema_length=0)  # all text first: some columns mix formats across years
    results = results.filter(~pl.col("candidate").is_in(NOT_CANDIDATES) | pl.col("candidate").is_null())
    for (state, year, candidate), party in PARTY_CORRECTIONS.items():
        is_this_candidate = (
            (pl.col("state_po") == state) & (pl.col("year") == str(year)) & (pl.col("candidate") == candidate)
        )
        results = results.with_columns(
            party_simplified=pl.when(is_this_candidate).then(pl.lit(party)).otherwise(pl.col("party_simplified"))
        )
    return results.with_columns(
        year=pl.col("year").cast(pl.Int64),
        candidatevotes=pl.col("candidatevotes").cast(pl.Float64),
        stage=pl.col("stage").str.to_lowercase() if "stage" in results.columns else pl.lit("gen"),
    )


def party_shares(race):
    """(Democratic share, Republican share) of all votes in one race: every candidate's row in that race.
    The total is the sum of the candidates' votes, so ballot counts (over and under votes) are left out."""
    total_votes = race["candidatevotes"].sum()
    democratic_votes = race.filter(pl.col("party_simplified") == "DEMOCRAT")["candidatevotes"].sum()
    republican_votes = race.filter(pl.col("party_simplified") == "REPUBLICAN")["candidatevotes"].sum()
    return democratic_votes / total_votes, republican_votes / total_votes


senate = read_mit_results(RAW_SENATE_RESULTS)
president = read_mit_results(RAW_PRESIDENT_RESULTS)

rows = []
for state in STATES:
    #### Last Senate election for this seat ####
    year, special = LAST_SENATE_ELECTION[state]
    race = senate.filter(
        (pl.col("state_po") == state) & (pl.col("year") == year) & (pl.col("special") == str(special))
    )
    # If the race went to a runoff, the runoff decided the seat, so use it. A runoff after New Year is recorded
    # in the next year (Georgia's 2020 runoff, on 5 January 2021), so look there too.
    runoff = senate.filter(
        (pl.col("state_po") == state)
        & pl.col("year").is_in([year, year + 1])
        & (pl.col("special") == str(special))
        & pl.col("stage").str.contains("runoff")
    )
    race = runoff if runoff.height > 0 else race.filter(pl.col("stage") == "gen")
    dem_share, rep_share = party_shares(race)
    election = f"senate_{year}" + ("_special" if special else "")
    rows.append({"state": state, "election": election, "dem_share": dem_share, "rep_share": rep_share})

    #### 2024 presidential election ####
    dem_share, rep_share = party_shares(president.filter((pl.col("state_po") == state) & (pl.col("year") == 2024)))
    rows.append({"state": state, "election": "president_2024", "dem_share": dem_share, "rep_share": rep_share})

past_results = pl.DataFrame(rows).sort("state", "election")

# Every state and election, so the numbers can be read through by eye.
for row in past_results.iter_rows(named=True):
    print(f"  {row['state']} {row['election']:<20} D {row['dem_share']:6.1%}  R {row['rep_share']:6.1%}")

save_data(past_results, PastResults, ANALYSIS_DATA, "past_results")
