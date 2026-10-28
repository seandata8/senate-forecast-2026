#### Preamble ####
# Purpose: Compute everything the website shows and save it as small summary files in data/03-summary_data/
#          (task #12). The website (Quarto) only reads these files; no analysis happens there.
#          The polling average of each race, for every on/off combination of the weighting rules, and each poll's
#          influence; Polymarket's daily prices and each candidate's latest price; the forecast (both runs together,
#          and each approach and model alone): chance of control, seats, each candidate's vote share and chance of
#          winning next to the polls and Polymarket; the chance of control from the polls, Polymarket and the Silver
#          Bulletin, next to ours; the forecast with the 2022 midterm's turnout; what the models answered; the personas; the run costs; past results next to the
#          forecast; the instructor's checks on the models.
# Author: Furkan Danisman
# Date: 24 October 2026; forecast, answers, personas and costs 25 October 2026; 2022 turnout 28 October 2026
# Pre-requisites: polls from scripts/10-clean_polls.py; polymarket and polymarket_control from
#                 scripts/11-clean_polymarket.py; data/01-raw_data/silver_bulletin_senate_control.csv (typed in);
#                 forecast, forecast_versions and forecast_errors from scripts/08-forecast.py (without them, the
#                 forecast part is skipped); forecast_2022 from scripts/08-forecast.py --turnout 2022 (without
#                 it, the turnout comparison is skipped); personas, candidates and responses; model_checks_<approach> from
#                 scripts/06-check_models.py
# Run: uv run scripts/12-summarize_results.py (or PyCharm's run button)

import sys

import polars as pl

from senate_forecast_2026.forecast_summary import (
    answer_weights,
    race_summary,
    seat_summary,
    weighted_shares,
    with_versions,
)
from senate_forecast_2026.paths import ANALYSIS_DATA, DATA, RAW_SILVER_BULLETIN, SUMMARY_DATA
from senate_forecast_2026.poll_average import (
    RULE_COMBINATIONS,
    poll_influence,
    poll_interval,
    poll_state_shares,
    race_averages,
    without_undecided,
)
from senate_forecast_2026.queries import (
    APPROACH_SETTINGS,
    CHART_START,
    DECISION_MODELS,
    STATE_NAMES,
    alaska_final_candidates,
    draws_by_model,
)
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import (
    CheckAnswers,
    CheckResults,
    ControlComparison,
    Costs,
    Crosstabs,
    ForecastControl,
    ForecastRaces,
    ForecastSeats,
    ModelAnswers,
    Models,
    PastComparison,
    PersonaComposition,
    PollAverages,
    PollInfluence,
    PollTable,
    PolymarketLatest,
    PolymarketPrices,
    TurnoutComparison,
)
from senate_forecast_2026.senate_simulation import simulate_races

#### Read data ####
# Each poll's shares are scaled to add up to 100% among its candidates: the undecided are left out, as in our
# forecast, so the two can be compared.
reported_polls = pl.read_parquet(ANALYSIS_DATA / "polls.parquet")
polls = without_undecided(reported_polls)
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
    .with_columns(**dict(zip(["lower", "upper"], poll_interval("average", "spread"), strict=True)))
    .with_columns(pl.col("average", "spread", "lower", "upper").round(4))
    .select(*columns, "date", "candidate", "average", "spread", "lower", "upper")
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

# Only the days the charts show (from CHART_START); the averages before then still count towards the later ones,
# because each day's average draws on earlier polls.
save_data(poll_averages.filter(pl.col("date") >= CHART_START), PollAverages, SUMMARY_DATA, "poll_averages")
save_data(poll_influence_table, PollInfluence, SUMMARY_DATA, "poll_influence")

# The website's table of polls under each race's chart: every poll in today's average (every rule on), with its
# weight and each candidate's share as the poll reported it (undecided included), and the leader's lead in points.
poll_table = (
    poll_influence_table.filter(pl.all_horizontal(columns[1:])).select("state", "poll_id", "influence")
    .join(reported_polls.drop("state"), on="poll_id")
    .with_columns(rank=pl.col("share").rank("ordinal", descending=True).over("poll_id"))
    .with_columns(
        leader=pl.col("candidate").filter(pl.col("rank") == 1).first().over("poll_id"),
        lead=(pl.col("share").filter(pl.col("rank") == 1).first() - pl.col("share").filter(pl.col("rank") == 2).first())
        .over("poll_id").fill_null(pl.col("share")).round(4),
    )
    .select("state", "poll_id", "pollster", "start_date", "date", "sample_size", "population", "influence",
            "candidate", "share", "leader", "lead")
    .sort("state", "influence", "poll_id", "share", descending=[False, True, False, True])
)
save_data(poll_table, PollTable, SUMMARY_DATA, "poll_table", sample_groups=["poll_id"])


#### Polymarket ####
# The prices need no calculation: the chart shows them as they are, and the headline numbers are each candidate's
# latest price.
polymarket_prices = polymarket.sort("state", "candidate", "date")
polymarket_latest = polymarket_prices.group_by("state", "candidate", maintain_order=True).last()
save_data(polymarket_prices.filter(pl.col("date") >= CHART_START), PolymarketPrices, SUMMARY_DATA, "polymarket_prices")
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
# With the size of each version's errors in the simulation, for the website's text.
forecast_errors = pl.read_parquet(ANALYSIS_DATA / "forecast_errors.parquet")
forecast_control = (
    pl.concat(control_rows)
    .join(forecast_errors, on=label_columns, how="left", validate="1:1")
    .select(*label_columns, "dem_control", "seats", "seats_lower", "seats_upper", "model_standard_error",
            "polling_state_error_sd", "state_error_sd", "national_error_sd")
)
forecast_seats = pl.concat(seat_rows).select(*label_columns, "dem_seats", "simulations", "share")

# Next to each candidate: today's poll average with every rule on (polls without the undecided, as above), and
# Polymarket's latest price, scaled to add up to 100% among the race's candidates (Alaska: the final round's two).
poll_now = everything_on.select("state", "candidate", poll_average="average", poll_spread="spread",
                                poll_lower="lower", poll_upper="upper")
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
            "poll_average", "poll_spread", "poll_lower", "poll_upper", "polymarket_chance")
)
print("Forecast, every version:")
print(forecast_control)
save_data(forecast_control, ForecastControl, SUMMARY_DATA, "forecast_control")
save_data(forecast_seats, ForecastSeats, SUMMARY_DATA, "forecast_seats")
save_data(forecast_races, ForecastRaces, SUMMARY_DATA, "forecast_races")


#### Other forecasts of control ####
# Next to our chance of Democratic control on the website:
# - the polls: the same seat simulation as our forecast (10,000 elections, the same national error and polling-sized
#   state error; ours also adds the models' own uncertainty), run on today's poll averages instead of the models'
#   answers; races without polls use the 2024 presidential result;
# - Polymarket: the latest price of its "Which party will win the Senate in 2026?" market for the Democrats;
# - the Silver Bulletin: the latest number in the file we type in by hand from its forecast page.
poll_shares = poll_state_shares(poll_now.rename({"poll_average": "average"}),
                                race_candidates.join(candidates.select("state", "candidate", "party"),
                                                     on=["state", "candidate"]),
                                pl.read_parquet(ANALYSIS_DATA / "past_results.parquet"))
poll_control, _ = seat_summary(simulate_races(poll_shares), candidates)
polymarket_control = pl.read_parquet(ANALYSIS_DATA / "polymarket_control.parquet").sort("date")
silver_bulletin = pl.read_csv(RAW_SILVER_BULLETIN, try_parse_dates=True).sort("date")
control_comparison = pl.DataFrame([
    {"source": "polls", "dem_control": poll_control["dem_control"][0], "date": last_day},
    {"source": "polymarket", "dem_control": polymarket_control["price"][-1], "date": polymarket_control["date"][-1]},
    {"source": "silver_bulletin", "dem_control": silver_bulletin["dem_control"][-1],
     "date": silver_bulletin["date"][-1]},
])
print("Chance of Democratic control, other forecasts:")
print(control_comparison)
save_data(control_comparison, ControlComparison, SUMMARY_DATA, "control_comparison")


#### With the 2022 midterm's turnout ####
# The combined forecast with the 2024 voters (the forecast) and with the 2022 midterm's voters, for the website's text.
if (ANALYSIS_DATA / "forecast_2022.parquet").exists():
    control_2022, _ = seat_summary(pl.read_parquet(ANALYSIS_DATA / "forecast_2022.parquet"), candidates)
    control_2024 = forecast_control.filter(pl.col("version_type") == "all").select(control_2022.columns)
    turnout_comparison = pl.concat([
        control_2024.with_columns(turnout=pl.lit(2024, dtype=pl.Int64)),
        control_2022.with_columns(turnout=pl.lit(2022, dtype=pl.Int64)),
    ]).select("turnout", *control_2022.columns)
    print("The combined forecast with each election's voters:")
    print(turnout_comparison)
    save_data(turnout_comparison, TurnoutComparison, SUMMARY_DATA, "turnout_comparison")
else:
    print("No forecast_2022 (run scripts/08-forecast.py --turnout 2022): the turnout comparison is skipped.")


#### What the models answered ####
# Each model's answers to the Senate question (grouped by the chosen candidate's party) and the House question,
# weighted by the personas' CES weights; each persona's draws from one model count once in total. Then the website's
# versions: each model, and the models counted equally ("average") for all of them and for each approach.
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
by_model = ["approach", "model", "question"]
per_model = pl.concat([weighted_shares(senate, by_model), weighted_shares(house, by_model)])
model_answers = with_versions(per_model, ["question", "answer"], ["share"], missing_is_zero=True).sort(
    "question", "version_type", "version", "model", "answer"
)
save_data(model_answers, ModelAnswers, SUMMARY_DATA, "model_answers")


#### Cross-tabs ####
# In each group of personas, the share of each party among the answers for a party: the Senate question (Democrat,
# Independent or Republican candidate) and the House question (Democrat or Republican; the few "Other" answers are
# left out). Per model, then the versions as above.
CROSSTAB_VARIABLES = ["gender", "race", "age_group", "education", "party_id", "ideology", "income", "religion",
                      "marital_status", "sexuality", "registered", "state"]
party_answers = pl.concat([
    senate.filter(pl.col("answer").is_in(["Democrat", "Independent", "Republican"])),
    house.filter(pl.col("answer").is_in(["Democrat", "Republican"])),
], how="diagonal_relaxed").join(personas.drop("state", "weight"), on="persona_id")
crosstab_rows = []
for variable in CROSSTAB_VARIABLES:
    rows = party_answers.with_columns(group=pl.col(variable).cast(pl.String), variable=pl.lit(variable))
    by = ["approach", "model", "question", "variable", "group"]
    shares = weighted_shares(rows, by).rename({"answer": "party"})
    sizes = rows.group_by(by).agg(personas=pl.col("persona_id").n_unique().cast(pl.Float64))
    crosstab_rows.append(shares.join(sizes, on=by))
crosstabs = with_versions(
    pl.concat(crosstab_rows), ["question", "variable", "group", "party"], ["share", "personas"], missing_is_zero=False
).with_columns(pl.col("personas").round(0).cast(pl.Int64)).sort(
    "variable", "group", "question", "version_type", "version", "model", "party"
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


#### Models ####
# Each model of each approach: how it was asked (its settings in queries.py) and what came back.
settings = pl.DataFrame([
    {"approach": approach, "model": model, "draws": draws,
     "kind": "decision model" if model in DECISION_MODELS else "chat model",
     "temperature": None if model in DECISION_MODELS else float(approach_settings["temperature"]),
     "wording": approach_settings["wording"]}
    for approach, approach_settings in APPROACH_SETTINGS.items()
    for model, draws in draws_by_model(approach_settings["models"], approach_settings["draws"]).items()
], schema_overrides={"temperature": pl.Float64})
models = (
    responses.group_by("approach", "model").agg(
        personas=pl.col("persona_id").n_unique().cast(pl.Int64), answers=pl.len().cast(pl.Int64),
        missing=pl.col("answer").null_count().cast(pl.Int64), input_tokens=pl.col("input_tokens").sum(),
        output_tokens=pl.col("output_tokens").sum(), cost=pl.col("cost").sum(),
    )
    .join(settings, on=["approach", "model"], how="left")
    .select("approach", "model", "kind", "draws", "temperature", "wording", "personas", "answers", "missing",
            "input_tokens", "output_tokens", "cost")
    .sort("approach", "model")
)
save_data(models, Models, SUMMARY_DATA, "models")


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
# cast, from past_results), next to our 2026 estimate for the Republican candidate (of the votes for the race's
# candidates, with its 95% interval, in every version). A comparison on the website, not a forecast
# input.
past_results = pl.read_parquet(ANALYSIS_DATA / "past_results.parquet")
our_estimate = forecast_races.filter(pl.col("party") == "Republican").select(
    "version_type", "version", "state", election=pl.lit("forecast_2026"), republican_share="share",
    lower="share_lower", upper="share_upper",
)
past_comparison = pl.concat([
    past_results.select(version_type=pl.lit(None, pl.String), version=pl.lit(None, pl.String), state="state",
                        election="election", republican_share="rep_share",
                        lower=pl.lit(None, pl.Float64), upper=pl.lit(None, pl.Float64)),
    our_estimate,
]).sort("state", "election", "version_type", "version")
save_data(past_comparison, PastComparison, SUMMARY_DATA, "past_comparison")


#### The instructor's checks ####
# For each check, how many draws gave each answer: the state question as asked; the usual questions with party ID
# (the approach's full run) and without it. Then each model's result: personas who named their own state in every
# draw, and personas whose most common answer to a question changed without party ID.
check_runs = sorted(ANALYSIS_DATA.glob("model_checks_*.parquet"))
if check_runs:
    model_checks = pl.concat([pl.read_parquet(path) for path in check_runs]).with_columns(pl.col("answer").fill_null("Missing"))
    checked = model_checks.select("approach", "persona_id", "model").unique()
    with_party = (
        responses.join(checked, on=["approach", "persona_id", "model"], how="semi")
        .with_columns(check=pl.lit("no_party_id"), prompt=pl.lit("with party ID"), answer=pl.col("answer").fill_null("Missing"))
    )
    asked = model_checks.with_columns(
        prompt=pl.when(pl.col("check") == "persona_state").then(pl.lit("as asked")).otherwise(pl.lit("without party ID"))
    )
    keys = ["approach", "model", "persona_id", "state", "check", "question", "prompt", "answer"]
    check_answers = (
        pl.concat([asked.select(keys), with_party.select(keys)])
        .group_by(keys).len("draws")
        .join(personas.select("persona_id", "party_id"), on="persona_id")
        .with_columns(pl.col("draws").cast(pl.Int64))
        .select("approach", "model", "persona_id", "state", "party_id", "check", "question", "prompt", "answer", "draws")
        .sort("approach", "model", "persona_id", "check", "question", "prompt", "answer")
    )

    # Persona attention: every draw named the persona's own state.
    state_names = pl.DataFrame({"state": list(STATE_NAMES), "state_name": list(STATE_NAMES.values())})
    attention = (
        model_checks.filter(pl.col("check") == "persona_state").join(state_names, on="state")
        .group_by("approach", "model", "persona_id").agg(right=(pl.col("answer") == pl.col("state_name")).all())
        .group_by("approach", "model").agg(personas=pl.len(), count=pl.col("right").sum())
        .with_columns(check=pl.lit("persona_state"))
    )
    # Party drop: the most common answers (all of them, if tied) with and without party ID differ, on any question.
    most_common = (
        check_answers.filter(pl.col("check") == "no_party_id")
        .filter(pl.col("draws") == pl.col("draws").max().over("approach", "model", "persona_id", "question", "prompt"))
        .group_by("approach", "model", "persona_id", "question", "prompt").agg(pl.col("answer").sort())
    )
    changed = (
        most_common.filter(pl.col("prompt") == "with party ID")
        .join(most_common.filter(pl.col("prompt") == "without party ID"), on=["approach", "model", "persona_id", "question"])
        .group_by("approach", "model", "persona_id").agg(changed=(pl.col("answer") != pl.col("answer_right")).any())
        .group_by("approach", "model").agg(personas=pl.len(), count=pl.col("changed").sum())
        .with_columns(check=pl.lit("no_party_id"))
    )
    check_costs = model_checks.group_by("approach", "model", "check").agg(pl.col("cost").sum())
    check_results = (
        pl.concat([attention, changed])
        .join(check_costs, on=["approach", "model", "check"])
        .with_columns(pl.col("personas", "count").cast(pl.Int64))
        .select("approach", "model", "check", "personas", "count", "cost")
        .sort("approach", "model", "check")
    )
    print("The instructor's checks:")
    print(check_results)
    save_data(check_results, CheckResults, SUMMARY_DATA, "check_results")
    save_data(check_answers, CheckAnswers, SUMMARY_DATA, "check_answers")
