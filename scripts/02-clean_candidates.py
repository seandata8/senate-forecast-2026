#### Preamble ####
# Purpose: Turn the saved Wikipedia page (the "Race summary" tables) into candidates: the main candidates in
#          each of the 35 races, with party, incumbent and dem_caucus_probability, in data/02-analysis_data/.
#          Main candidates: every Democrat and Republican, plus the four main independents (Idaho, Montana,
#          Nebraska, South Dakota). Minor-party candidates are left out; personas can still answer "someone else".
# Author: Sean Murphy
# Date: 22 October 2026
# Pre-requisites: uv run scripts/01-download_election_data.py
# Run: uv run scripts/02-clean_candidates.py (or PyCharm's run button)

import re

import polars as pl

from senate_forecast_2026.paths import ANALYSIS_DATA, RAW_CANDIDATES_PAGE
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import STATE_CODES, Candidates
from senate_forecast_2026.senate_simulation import INDEPENDENT_DEM_CAUCUS_PROBABILITY

# The independents we count as main candidates. Idaho has a second independent, and other states have minor ones.
MAIN_INDEPENDENTS = ["Todd Achilles", "Seth Bodnar", "Dan Osborn", "Brian Bengs"]  # Idaho, Montana, Nebraska, South Dakota

# Wikipedia's party labels, as our party names. Minnesota's Democrats are the DFL (Democratic-Farmer-Labor).
# Labels not listed here are minor parties.
OUR_PARTY_NAMES = {"Democratic": "Democrat", "DFL": "Democrat", "Republican": "Republican", "Independent": "Independent"}

# Where the "Senator" column writes the incumbent differently from the ballot.
INCUMBENT_NAMES_ON_BALLOT = {"Dan Sullivan": "Dan S. Sullivan"}  # Alaska, where another Dan Sullivan is running

# Seats up in 2026 by the incumbent's party: 22 Republican, 13 Democratic. This is what SEATS_NOT_UP in
# senate_simulation.py assumes (53 Republicans and 47 in the Democratic caucus now), so check it here.
EXPECTED_SEATS_UP = {"Republican": 22, "Democrat": 13}


def remove_wiki_markup(text):
    """The visible text of a piece of wikitext: references and templates removed, links replaced by their text."""
    text = re.sub(r"<ref[^>]*/>", "", text)  # <ref name="x" />
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text)  # <ref>...</ref>
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)  # {{Party stripe|...}} and other templates
    text = re.sub(r"\[\[[^\]|]*\|([^\]]+)\]\]", r"\1", text)  # [[Page|shown text]] -> shown text
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)  # [[Page]] -> Page
    return text.strip()


def state_of(race):
    """The race's state code, from its first cell, e.g. "! [[2026 United States Senate election in Texas|Texas]]".
    None for rows that are not races (the table headers)."""
    state_link = re.search(r"^! \[\[2026 United States Senate[^|\]]*\|([^\]]+)\]\]", race, re.MULTILINE)
    if state_link is None:
        return None
    return STATE_CODES[state_link.group(1)]


def incumbent_of(race):
    """The current senator's name, written as "{{sortname|First|Last}}" or "[[Name]]"."""
    sortname = re.search(r"^\| \{\{sortname\|([^|}]+)\|([^|}]+)", race, re.MULTILINE)
    if sortname:
        name = f"{sortname.group(1)} {sortname.group(2)}"
    else:
        name = re.search(r"^\| \[\[([^\]|]+)", race, re.MULTILINE).group(1)
    return INCUMBENT_NAMES_ON_BALLOT.get(name, name)


def incumbent_party_of(race):
    """The current senator's party, from the cell after their name, e.g. "| {{Party shading/Republican}} | Republican"."""
    return re.search(r"^\| \{\{Party shading/[^}]*\}\} \| (\w+)", race, re.MULTILINE).group(1)


def candidates_of(race):
    """(name, Wikipedia party) for each candidate line, e.g. "*{{Party stripe|...}}[[Jon Ossoff]] (Democratic)<ref .../>".
    The markup is removed first: a link can itself contain brackets, like "[[Jack Reed (Rhode Island politician)|Jack Reed]]"."""
    candidates = []
    for line in race.split("\n"):
        if "{{Party stripe" in line:
            # Start at the "{{Party stripe": the first candidate can share a line with the start of the list,
            # as in Georgia's "| nowrap | {{Plainlist |*{{Party stripe|...".
            candidate_text = line[line.index("{{Party stripe") :]
            text = remove_wiki_markup(candidate_text)  # e.g. "Jon Ossoff (Democratic)"
            name, party = re.fullmatch(r"(.+) \((.+)\)", text).groups()
            candidates.append((name, party))
    return candidates


#### Read the two "Race summary" tables ####
# They sit between the "Race summary" and "Elections" headings. Each race is one table row; rows are separated by "|-".
page = RAW_CANDIDATES_PAGE.read_text()
race_summary = page[page.index("== Race summary ==") : page.index("== Elections ==")]
races = [race for race in race_summary.split("\n|-\n") if state_of(race) is not None]
print(f"Read {len(races)} races from {RAW_CANDIDATES_PAGE.name}", flush=True)

seats_up = {"Republican": 0, "Democrat": 0}
candidate_rows = []
for race in races:
    state = state_of(race)
    incumbent = incumbent_of(race)
    seats_up[OUR_PARTY_NAMES[incumbent_party_of(race)]] += 1
    for name, wikipedia_party in candidates_of(race):
        party = OUR_PARTY_NAMES.get(wikipedia_party)  # None for a minor party
        is_main = party in ("Democrat", "Republican") or name in MAIN_INDEPENDENTS
        if not is_main:
            continue
        if party == "Democrat":
            dem_caucus_probability = 1.0
        elif party == "Republican":
            dem_caucus_probability = 0.0
        else:
            dem_caucus_probability = INDEPENDENT_DEM_CAUCUS_PROBABILITY[state]
        candidate_rows.append({
            "state": state,
            "candidate": name,
            "party": party,
            "incumbent": name == incumbent,
            "dem_caucus_probability": dem_caucus_probability,
        })

candidates = pl.DataFrame(candidate_rows).sort("state", "candidate")


#### Check, show and save ####
print(f"Seats up by incumbent's party: {seats_up}", flush=True)
if seats_up != EXPECTED_SEATS_UP:
    raise ValueError(f"Expected {EXPECTED_SEATS_UP} seats up; SEATS_NOT_UP in senate_simulation.py needs checking.")

# Every race and its candidates, so the list can be read through by eye. * marks the incumbent.
for (state,), race_candidates in candidates.group_by("state", maintain_order=True):
    names = ", ".join(
        f"{row['candidate']}{'*' if row['incumbent'] else ''} ({row['party']})" for row in race_candidates.iter_rows(named=True)
    )
    print(f"  {state}: {names}")

save_data(candidates, Candidates, ANALYSIS_DATA, "candidates")
