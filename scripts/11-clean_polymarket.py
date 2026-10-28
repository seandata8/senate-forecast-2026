#### Preamble ####
# Purpose: Turn the saved Polymarket markets and prices into polymarket, in data/02-analysis_data/ (task #11): one
#          row per candidate of ours per day, with the price of a "Yes, they win" share; and polymarket_control: one
#          row per day, with the price of a "Yes, the Democrats control the Senate" share. Comparisons on the
#          website, not forecast inputs.
# Author: Furkan Danisman
# Date: 24 October 2026
# Pre-requisites: uv run scripts/11-download_polymarket.py; candidates from scripts/02-clean_candidates.py
# Run: uv run scripts/11-clean_polymarket.py (or PyCharm's run button)

import json
import re
from datetime import UTC, datetime

import polars as pl

from senate_forecast_2026.paths import ANALYSIS_DATA, RAW_POLYMARKET
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import Polymarket, PolymarketControl

# Where Polymarket names a market differently from candidates, by (state, Polymarket's name without its party
# letter). Some races have a market per party rather than per person; it is matched to our candidate of that party.
NAME_CORRECTIONS = {
    ("AK", "Sen. Dan Sullivan"): "Dan S. Sullivan",
    ("AK", "Daniel J. Sullivan Jr."): "Dan J. Sullivan",
    ("OK", "N’Kiyla “Jasmine” Thomas"): "N'Kiyla Jasmine Thomas",
    ("SC", "Darline Graham Nordone"): "Darline Graham",
    ("DE", "Democrat"): "Chris Coons",
    ("DE", "Republican"): "Michael Katz",
    ("MT", "Independent"): "Seth Bodnar",
    ("NE", "Independent"): "Dan Osborn",
}


def candidate_name(state, market_title):
    """Our name for the candidate of a market: Polymarket's title ("James Talarico (D)") without its party letter,
    corrected where it differs from candidates."""
    name = re.sub(r"\s*\((D|R|I)\)\s*$", "", market_title.strip())
    return NAME_CORRECTIONS.get((state, name), name)


#### Read data ####
raw = json.loads(RAW_POLYMARKET.read_text())
candidates = pl.read_parquet(ANALYSIS_DATA / "candidates.parquet")
print(f"Read {len(raw['events'])} Polymarket races from {RAW_POLYMARKET.name}, downloaded {raw['downloaded_at']}")


#### One row per candidate of ours per day ####
price_rows = []
left_out = []  # markets for people who are not our candidates, shown below
for state, event in raw["events"].items():
    ours = set(candidates.filter(pl.col("state") == state)["candidate"])
    for market in event["markets"]:
        if not market.get("outcomePrices"):
            continue  # an unused place in the event ("Candidate C", "Other"), with no prices
        candidate = candidate_name(state, market["groupItemTitle"])
        if candidate not in ours:
            left_out.append(f"{state} {market['groupItemTitle'].strip()}")
            continue
        yes_token = json.loads(market["clobTokenIds"])[0]
        for point in raw["price_history"][yes_token]:
            price_rows.append({
                "state": state,
                "date": datetime.fromtimestamp(point["t"], UTC).date(),  # the day, in UTC, the price was taken
                "candidate": candidate,
                "price": point["p"],
                "t": point["t"],
            })

# The history has one price a day, plus the latest price on the download day; keep the last price of each day.
polymarket = (
    pl.DataFrame(price_rows)
    .sort("t")
    .group_by("state", "date", "candidate", maintain_order=True)
    .last()
    .drop("t")
    .sort("state", "candidate", "date")
)


#### Senate control: one row per day ####
# The control event has a market per party; the Democrats' market is the one shown (the Republicans' is about 1
# minus it).
democratic_market = [market for market in raw["control_event"]["markets"]
                     if market["groupItemTitle"].strip() == "Democratic Party"]
if len(democratic_market) != 1:
    raise RuntimeError(f"Expected one Democratic Party market in the control event, found {len(democratic_market)}.")
yes_token = json.loads(democratic_market[0]["clobTokenIds"])[0]
polymarket_control = (
    pl.DataFrame([{"date": datetime.fromtimestamp(point["t"], UTC).date(), "price": point["p"], "t": point["t"]}
                  for point in raw["price_history"][yes_token]])
    .sort("t")
    .group_by("date", maintain_order=True)
    .last()
    .drop("t")
    .sort("date")
)


#### Show and save ####
print(f"Left out {len(left_out)} markets for people not in candidates: {', '.join(left_out)}")
no_market = candidates.join(polymarket.select("state", "candidate").unique(), on=["state", "candidate"], how="anti")
print(f"Candidates with no market: {', '.join(f'{r[0]} {r[1]}' for r in no_market.select('state', 'candidate').rows())}")
latest = polymarket.group_by("state", "candidate").agg(pl.col("date").min().alias("first"), pl.col("date", "price").last())
with pl.Config(tbl_rows=80):
    print(latest.sort("state", "candidate"))

save_data(polymarket, Polymarket, ANALYSIS_DATA, "polymarket")
print(f"Senate control: the Democrats at {polymarket_control['price'][-1]:.1%} on {polymarket_control['date'][-1]}")
save_data(polymarket_control, PolymarketControl, ANALYSIS_DATA, "polymarket_control")
