#### Preamble ####
# Purpose: Compute everything the website shows and save it as small summary files in data/03-summary_data/
#          (task #12). The website (Quarto) only reads these files; no analysis happens there.
#          The polling average of each race, for every on/off combination of the weighting rules, and each poll's
#          influence; Polymarket's daily prices and each candidate's latest price; the forecast (both runs together,
#          and each approach and model alone): chance of control, seats, each candidate's vote share and chance of
#          winning next to the polls and Polymarket; what the models answered; the personas; the run costs; past
#          results next to the forecast.
# Author: Furkan Danisman
# Date: 24 October 2026; forecast, answers, personas and costs 25 October 2026
# Pre-requisites: polls from scripts/10-clean_polls.py; polymarket from scripts/11-clean_polymarket.py;
#                 forecast and forecast_versions from scripts/08-forecast.py (without them, the forecast part is
#                 skipped); personas, candidates and responses
# Run: uv run scripts/12-summarize_results.py (or PyCharm's run button)

import sys

import polars as pl

from senate_forecast_2026.forecast_summary import answer_weights, race_summary, seat_summary, weighted_shares
from senate_forecast_2026.paths import ANALYSIS_DATA, DATA, SUMMARY_DATA
from senate_forecast_2026.poll_average import RULE_COMBINATIONS, poll_influence, race_averages, without_undecided
from senate_forecast_2026.queries import alaska_final_candidates
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import (
    Costs,
    Crosstabs,
    ForecastControl,
    ForecastRaces,
    ForecastSeats,
    ModelAnswers,
    PastComparison,
    PersonaComposition,
    PollAverages,
    PollInfluence,
    PolymarketLatest,
    PolymarketPrices,
)

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


#### Forecast ####
# Both runs together (version_type "all") and each approach and model alone, made by 08-forecast.py.
if not (ANALYSIS_DATA / "forecast.parquet").exists():
    sys.exit("No forecast yet (run scripts/08-forecast.py): the forecast part is skipped.")
candidates = pl.read_parquet(ANALYSIS_DATA / "candidates.parquet")
forecast = pl.read_parquet(ANALYSIS_DATA / "forecast.parquet")
versions = [(("all", "all"), forecast)]
if (ANALYSIS_DATA / "forecast_versions.parquet").exists():
    forecast_versions = pl.read_parquet(ANALYSIS_DATA / "forecast_versions.parquet")
    versions += [(key, part.drop("version_type", "version"))
                 for key, part in forecast_versions.group_by("version_type", "version", maintain_order=True)]

control_rows, seat_rows, race_rows = [], [], []
for (version_type, version), version_forecast in versions:
    labels = {"version_type": version_type, "version": version}
    control, distribution = seat_summary(version_forecast, candidates)
    control_rows.append(control.with_columns(**{k: pl.lit(v) for k, v in labels.items()}))
    seat_rows.append(distribution.with_columns(**{k: pl.lit(v) for k, v in labels.items()}))
    race_rows.append(race_summary(version_forecast).with_columns(**{k: pl.lit(v) for k, v in labels.items()}))
label_columns = ["version_type", "version"]
forecast_control = pl.concat(control_rows).select(*label_columns, "dem_control", "seats", "seats_lower", "seats_upper")
forecast_seats = pl.concat(seat_rows).select(*label_columns, "dem_seats", "simulations", "share")

# Next to each candidate: today's poll average with every rule on (polls without the undecided, as above), and
# Polymarket's latest price, scaled to add up to 100% among the race's candidates (Alaska: the final round's two).
poll_now = everything_on.select("state", "candidate", poll_average="average", poll_spread="spread")
race_candidates = pl.concat([
    candidates.filter(pl.col("state") != "AK"),
    alaska_final_candidates(candidates.filter(pl.col("state") == "AK")),
]).select("state", "candidate")
polymarket_now = (
    polymarket_latest.join(race_candidates, on=["state", "candidate"], how="semi")
    .select("state", "candidate", polymarket_chance=pl.col("price") / pl.col("price").sum().over("state"))
)
forecast_races = (
    pl.concat(race_rows)
    .join(poll_now, on=["state", "candidate"], how="left")
    .join(polymarket_now, on=["state", "candidate"], how="left")
    .select(*label_columns, "state", "candidate", "party", "share", "share_lower", "share_upper", "chance_of_winning",
            "poll_average", "poll_spread", "polymarket_chance")
)
print("Forecast, every version:")
print(forecast_control)
save_data(forecast_control, ForecastControl, SUMMARY_DATA, "forecast_control")
save_data(forecast_seats, ForecastSeats, SUMMARY_DATA, "forecast_seats")
save_data(forecast_races, ForecastRaces, SUMMARY_DATA, "forecast_races")


#### What the models answered ####
# Each model's answers to the Senate question (grouped by the chosen candidate's party) and the House question,
# weighted by the personas' CES weights; each persona's draws from one model count once in total. "average" is the
# models counted equally, as on the instructor's site.
personas = pl.read_parquet(ANALYSIS_DATA / "personas.parquet")
# Both runs combined (#7), or until then each person's run that exists.
if (ANALYSIS_DATA / "responses.parquet").exists():
    responses = pl.read_parquet(ANALYSIS_DATA / "responses.parquet")
else:
    responses = pl.concat([pl.read_parquet(path) for path in sorted(ANALYSIS_DATA.glob("responses_*.parquet"))])
weighted = answer_weights(responses, personas).with_columns(pl.col("answer").fill_null("Missing"))
senate = (
    weighted.filter(pl.col("question") == "senate")
    .join(candidates.select("state", pl.col("candidate").alias("answer"), "party"), on=["state", "answer"], how="left")
    .with_columns(answer=pl.coalesce("party", "answer"))
)
house = weighted.filter(pl.col("question") == "generic")
per_model = pl.concat([weighted_shares(senate, ["model", "question"]), weighted_shares(house, ["model", "question"])])
average = (
    per_model.group_by("question", "answer").agg(share=pl.col("share").sum() / per_model["model"].n_unique())
    .with_columns(model=pl.lit("average"))
)
model_answers = pl.concat([per_model, average.select(per_model.columns)]).sort("question", "model", "answer")
save_data(model_answers, ModelAnswers, SUMMARY_DATA, "model_answers")


#### Cross-tabs ####
# The Democratic share of the two-party House vote in each group of personas, per model, and the models' average.
CROSSTAB_VARIABLES = ["gender", "race", "age_group", "education", "party_id", "ideology", "income", "religion",
                      "marital_status", "sexuality", "registered", "state"]
two_party = house.filter(pl.col("answer").is_in(["Democrat", "Republican"])).join(
    personas.drop("state", "weight"), on="persona_id"
)
crosstab_rows = []
for variable in CROSSTAB_VARIABLES:
    by_model = two_party.group_by(pl.col(variable).alias("group"), "model").agg(
        democratic_share=(pl.col("weight") * (pl.col("answer") == "Democrat")).sum() / pl.col("weight").sum(),
        personas=pl.col("persona_id").n_unique(),
    )
    by_average = by_model.group_by("group").agg(
        pl.col("democratic_share").mean(), pl.col("personas").min(), model=pl.lit("average")
    )
    crosstab_rows += [by_model.with_columns(variable=pl.lit(variable)),
                      by_average.select(by_model.columns).with_columns(variable=pl.lit(variable))]
crosstabs = pl.concat(crosstab_rows).select("variable", "group", "model", "democratic_share", pl.col("personas").cast(pl.Int64)).sort(
    "variable", "group", "model"
)
save_data(crosstabs, Crosstabs, SUMMARY_DATA, "crosstabs")


#### The personas ####
persona_composition = pl.concat([
    personas.group_by(pl.col(variable).alias("group")).len("personas").with_columns(variable=pl.lit(variable))
    for variable in [*CROSSTAB_VARIABLES, "vote_2024"]
]).with_columns(pl.col("group").fill_null("Missing"), pl.col("personas").cast(pl.Int64)).select(
    "variable", "group", "personas"
).sort("variable", "group")
save_data(persona_composition, PersonaComposition, SUMMARY_DATA, "persona_composition")


#### Costs ####
# Each approach's latest full run (every persona) from the run cost log, per model and in total.
run_costs = pl.read_csv(DATA / "run_costs.csv")
full_runs = run_costs.filter((pl.col("data") == "real") & (pl.col("personas") == personas.height))
costs = (
    full_runs.filter(pl.col("run_at") == pl.col("run_at").max().over("approach"))
    .select("approach", "run_at", "model", "calls", "personas", "total_cost", "cost_per_persona")
    .sort("approach", "model")
)
save_data(costs, Costs, SUMMARY_DATA, "costs")


#### Past results ####
# Each race's Republican share in the 2024 presidential election and the last election for the seat (of all votes
# cast, from past_results), next to our 2026 estimate for the Republican candidate (both runs together, of the votes
# for the race's candidates, with its 95% interval). A comparison on the website, not a forecast input.
past_results = pl.read_parquet(ANALYSIS_DATA / "past_results.parquet")
our_estimate = forecast_races.filter((pl.col("version_type") == "all") & (pl.col("party") == "Republican")).select(
    "state", election=pl.lit("forecast_2026"), republican_share="share", lower="share_lower", upper="share_upper"
)
past_comparison = pl.concat([
    past_results.select("state", "election", republican_share="rep_share",
                        lower=pl.lit(None, pl.Float64), upper=pl.lit(None, pl.Float64)),
    our_estimate,
]).sort("state", "election")
save_data(past_comparison, PastComparison, SUMMARY_DATA, "past_comparison")
