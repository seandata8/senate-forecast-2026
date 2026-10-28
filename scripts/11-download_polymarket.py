#### Preamble ####
# Purpose: Download Polymarket's "<State> Senate Election Winner" market for each of the 35 races, and the daily
#          price history of each candidate in it, into data/01-raw_data/, unchanged (task #11). Also the
#          "Which party will win the Senate in 2026?" market and its price history, for the chance of control.
#          scripts/11-clean_polymarket.py turns them into polymarket. Prices are a comparison on the website,
#          not a forecast input.
# Author: Furkan Danisman
# Date: 24 October 2026
# Pre-requisites: uv sync. No API key or login needed.
# Run: uv run scripts/11-download_polymarket.py (or PyCharm's run button)
#      Each run replaces the saved file with the latest prices, so rerun it to update them.

import json
from datetime import UTC, datetime

from senate_forecast_2026.download import fetch_json
from senate_forecast_2026.paths import RAW_POLYMARKET
from senate_forecast_2026.queries import STATE_NAMES

# Polymarket, https://polymarket.com. Two public APIs, see https://docs.polymarket.com:
# - Gamma: each race is an "event" holding one Yes/No market per candidate ("Will James Talarico win?").
# - CLOB: the price history of a market's Yes share, one price a day (fidelity=1440 minutes), as far back as it goes.
EVENT_URL = "https://gamma-api.polymarket.com/events?slug={slug}"
PRICES_URL = "https://clob.polymarket.com/prices-history?market={token_id}&interval=max&fidelity=1440"

# Each race's event, by its address on polymarket.com: "texas-senate-election-winner" and so on.
# Alabama's has a number added, as Polymarket's address for it is taken by an older market.
SLUGS = {state: name.lower().replace(" ", "-") + "-senate-election-winner" for state, name in STATE_NAMES.items()}
SLUGS["AL"] = "alabama-senate-election-winner-154"
# The market on which party controls the Senate after the election, one Yes/No market per party.
CONTROL_SLUG = "which-party-will-win-the-senate-in-2026"


def event_with_prices(slug):
    """Polymarket's event called `slug`, and the price history of the Yes share of each of its markets, by token id."""
    found = fetch_json(EVENT_URL.format(slug=slug))
    if len(found) != 1:
        raise RuntimeError(f"Expected one Polymarket event called {slug}, found {len(found)}.")
    # Unused places in an event ("Candidate C", "Party A", "Other") have no prices; every other market gets its history.
    histories = {}
    for market in found[0]["markets"]:
        if market.get("outcomePrices"):
            yes_token = json.loads(market["clobTokenIds"])[0]  # the first token is "Yes", the second "No"
            histories[yes_token] = fetch_json(PRICES_URL.format(token_id=yes_token))["history"]
    return found[0], histories


events = {}
price_history = {}
for state, slug in SLUGS.items():
    events[state], histories = event_with_prices(slug)
    price_history.update(histories)
control_event, histories = event_with_prices(CONTROL_SLUG)
price_history.update(histories)

# The APIs have no versions: they always give the latest prices. So the file records when it was downloaded, and
# keeps each API's answer exactly as it came: the events by state, the control event, and each Yes token's prices
# by token id.
downloaded = {
    "source": "https://polymarket.com (Gamma and CLOB APIs)",
    "downloaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
    "events": events,
    "control_event": control_event,
    "price_history": price_history,
}
RAW_POLYMARKET.parent.mkdir(parents=True, exist_ok=True)
RAW_POLYMARKET.write_text(json.dumps(downloaded, indent=1))
print(
    f"Done: {RAW_POLYMARKET} ({len(events)} races and the control market, {len(price_history)} markets with prices, "
    f"downloaded {downloaded['downloaded_at']}).",
    flush=True,
)
