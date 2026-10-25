#### Preamble ####
# Purpose: Compute everything the website shows and save it as small summary files in data/03-summary_data/
#          (task #12). The website (Quarto) only reads these files; no analysis happens there.
#          So far: the polling average of each race, for every on/off combination of the weighting rules, and each
#          poll's influence; Polymarket's daily prices and each candidate's latest price. The forecast and past
#          results parts come later.
# Author: Furkan Danisman
# Date: 24 October 2026
# Pre-requisites: polls from scripts/10-clean_polls.py; polymarket from scripts/11-clean_polymarket.py
# Run: uv run scripts/12-summarize_results.py (or PyCharm's run button)

import polars as pl

from senate_forecast_2026.paths import ANALYSIS_DATA, SUMMARY_DATA
from senate_forecast_2026.poll_average import RULE_COMBINATIONS, poll_influence, race_averages, without_undecided
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import PollAverages, PollInfluence, PolymarketLatest, PolymarketPrices

#### Read data ####
# Each poll's shares are scaled to add up to 100% among its candidates: the undecided are left out, as in our
# forecast, so the two can be compared.
polls = without_undecided(pl.read_parquet(ANALYSIS_DATA / "polls.parquet"))
polymarket = pl.read_parquet(ANALYSIS_DATA / "polymarket.parquet")


#### Polling average ####
# Every race's average runs to the same last day: the latest poll in any race. Using a date from the data rather
# than today's date means a rerun on the same polls gives the same files.
last_day = polls["date"].max()
print(f"Polling averages for {polls['state'].n_unique()} races and {len(RULE_COMBINATIONS)} rule combinations, "
      f"up to {last_day}", flush=True)

average_rows = []
influence_rows = []
for state, race_polls in polls.group_by("state", maintain_order=True):
    for rules in RULE_COMBINATIONS:
        labels = {"state": state[0], **rules}
        average_rows += [{**labels, **row} for row in race_averages(race_polls, last_day, rules)]
        influence_rows += [{**labels, **row} for row in poll_influence(race_polls, last_day, rules)]

columns = ["state", *RULE_COMBINATIONS[0]]
poll_averages = (
    pl.DataFrame(average_rows)
    .with_columns(pl.col("average", "spread").round(4))
    .select(*columns, "date", "candidate", "average", "spread")
    .sort(*columns, "candidate", "date", descending=[False, True, True, True, True, False, False])
)
poll_influence_table = (
    pl.DataFrame(influence_rows)
    .with_columns(pl.col("influence").round(4))
    .select("state", "poll_id", *columns[1:], "influence")
    .sort("state", "poll_id", *columns[1:], descending=[False, False, True, True, True, True])
)


#### Show and save ####
everything_on = poll_averages.filter(pl.all_horizontal(columns[1:]), pl.col("date") == last_day)
print("Averages on the last day, with every rule on:")
with pl.Config(tbl_rows=80):
    print(everything_on.select("state", "candidate", "average", "spread"))

save_data(poll_averages, PollAverages, SUMMARY_DATA, "poll_averages")
save_data(poll_influence_table, PollInfluence, SUMMARY_DATA, "poll_influence")


#### Polymarket ####
# The prices need no calculation: the chart shows them as they are, and the headline numbers are each candidate's
# latest price.
polymarket_prices = polymarket.sort("state", "candidate", "date")
polymarket_latest = polymarket_prices.group_by("state", "candidate", maintain_order=True).last()
save_data(polymarket_prices, PolymarketPrices, SUMMARY_DATA, "polymarket_prices")
save_data(polymarket_latest, PolymarketLatest, SUMMARY_DATA, "polymarket_latest")
