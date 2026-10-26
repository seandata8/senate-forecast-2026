#### Preamble ####
# Purpose: Turn personas into prompts, build each persona's questions with the candidates on their own ballot,
#          and ask every question, collecting the answers in the format of the Responses schema.
#          No API calls happen here: the function that calls a model (`ask` in silicon.py) is passed in,
#          so the tests can use a fake one that costs nothing.
# Author: Furkan Danisman
# Date: 22 October 2026; draws per model and run costs added 24 October 2026; approach settings moved here from
#       scripts/05-query_models.py 25 October 2026
# Pre-requisites: uv sync

import polars as pl

from senate_forecast_2026.schemas import GENERIC_ANSWERS, NON_CANDIDATE_ANSWERS

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AR": "Arkansas", "CO": "Colorado", "DE": "Delaware", "FL": "Florida",
    "GA": "Georgia", "ID": "Idaho", "IL": "Illinois", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "ME": "Maine", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MT": "Montana", "NE": "Nebraska", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NC": "North Carolina", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "VA": "Virginia", "WV": "West Virginia", "WY": "Wyoming",
}

# CES education labels that are unclear on their own, written out for the prompt. Others are used as they are.
EDUCATION_WORDING = {
    "No HS": "Did not finish high school",
    "2-year": "2-year college degree",
    "4-year": "4-year college degree",
    "Post-grad": "Postgraduate degree",
}

# The persona columns that go into the prompt, and how each is labelled. Left out on purpose: persona_id (ours,
# not the respondent's), vote_2024 (reference only, never in the prompt) and weight (used in #8, not by the model).
PERSONA_LINES = {
    "state": "State",
    "age_group": "Age",
    "gender": "Gender",
    "race": "Race or ethnicity",
    "education": "Education",
    "income": "Family income",
    "party_id": "Party identification",
    "ideology": "Political views",
    "religion": "Religion",
    "marital_status": "Marital status",
    "sexuality": "Sexual orientation",
    "registered": "Registered to vote",
}

ELECTION_DATE = "3 November 2026"


def persona_to_prompt(persona):
    """The system message for one persona (a dict with the Personas columns): who the model is answering as."""
    values = dict(persona)
    values["state"] = STATE_NAMES[values["state"]]
    values["education"] = EDUCATION_WORDING.get(values["education"], values["education"])
    lines = [f"- {label}: {values[column]}" for column, label in PERSONA_LINES.items()]
    return (
        "You are taking part in a survey of American voters. Answer every question as the person described below "
        "would, based on who they are.\n\nAbout you:\n" + "\n".join(lines)
    )


def candidate_list(state_candidates, wording):
    """The candidates as they appear in a question. v1: "A (Democrat), B (Republican)".
    v2: "A (Democrat) and B (Republican)", or "A (Democrat), B (Republican) and C (Independent)" for three or more."""
    names = [f"{row['candidate']} ({row['party']})" for row in state_candidates.iter_rows(named=True)]
    if wording == "v1" or len(names) == 1:
        return ", ".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def alaska_final_candidates(alaska_candidates):
    """The two candidates in Alaska's ranked-choice final round: the Democrat and the incumbent (a Republican)."""
    final_round = alaska_candidates.filter((pl.col("party") == "Democrat") | pl.col("incumbent"))
    if final_round.height != 2:
        raise ValueError(f"Expected 2 candidates in Alaska's final round, found {final_round.height}")
    return final_round


# The two wordings of each question. The answer options are the same in both; only the text differs.
# v1 lists "Undecided" and "Would not vote" as plain instructions after the question.
# v2 is a robustness check: LLMs tend to pick a candidate whenever one is offered, so v2 says that some people
# find it hard to decide or do not vote, and offers both answers before asking, as normal answers rather than
# fallbacks. Comparing the two shows how much the answers depend on that framing.
# Placeholders: {state_name}, {date}, {candidates}.
V1_CHOOSE_NOTE = 'If you have not decided, answer "Undecided". If you will not vote, answer "Would not vote".'
V2_PAST_ELECTIONS = (
    "In past elections, some people found it hard to make up their minds, and some of them decided not to vote at all."
)
QUESTION_WORDINGS = {
    "v1": {
        "senate": "The election for US Senate in {state_name} is on {date}. The candidates on your ballot are: "
        "{candidates}. Who will you vote for? " + V1_CHOOSE_NOTE,
        "generic": "In the election for the US House of Representatives on {date}, which party's candidate will you "
        'vote for? Answer "Democrat", "Republican" or "Other". ' + V1_CHOOSE_NOTE,
        "alaska_final": "Alaska uses ranked-choice voting. Suppose that in the final round of the US Senate election "
        "on {date}, only these two candidates are left: {candidates}. Which of the two will you vote for? "
        + V1_CHOOSE_NOTE,
    },
    "v2": {
        "senate": "The US Senate election in {state_name} is on {date}, and the candidates on your ballot are "
        "{candidates}. " + V2_PAST_ELECTIONS + " If you're not sure who you'd pick, say \"Undecided\". "
        "If you probably won't vote, say \"Would not vote\". Otherwise, who will you vote for?",
        "generic": "On {date} there is an election for the US House of Representatives. Which party's candidate will "
        'you vote for: "Democrat", "Republican" or "Other"? ' + V2_PAST_ELECTIONS + " If you're not sure, "
        "say \"Undecided\". If you probably won't vote, say \"Would not vote\".",
        "alaska_final": "Alaska uses ranked-choice voting. Suppose that in the final round of the US Senate election "
        "on {date}, only two candidates are left: {candidates}. " + V2_PAST_ELECTIONS + " If you can't choose "
        "between them, say \"Undecided\". If you probably won't vote, say \"Would not vote\". Otherwise, which "
        "of the two would you vote for?",
    },
}


# Each of us sets our own approach here for #6 (used by scripts/05-query_models.py): models from at least two providers, repeated draws, and the
# question wording (see QUESTION_WORDINGS above). v1 is the default; v2 is the experimental wording,
# run with --wording v2 to check how much the answers depend on it. `draws` is one number for every model, or a
# number per model.
APPROACH_SETTINGS = {
    "sean": {
        "models": ["deepseek/deepseek-v4-flash-0731", "z-ai/glm-5.3-flash"], "draws": 3, "temperature": 1.0, "wording": "v1",
    },
    # Jev is a decision model (see DECISION_MODELS in silicon.py): it has no temperature, and each of its 10 draws
    # is a separate call whose answer is a random pick weighted by its probabilities. Kimi K3 is a chat model.
    "furkan": {
        "models": ["typesafe/jev-1.14", "moonshotai/kimi-k3"],
        "draws": {"typesafe/jev-1.14": 10, "moonshotai/kimi-k3": 3},
        "temperature": 1.0,
        "wording": "v1",
    },
}


def questions_for_state(state, candidates, wording):
    """The questions every persona in `state` is asked, in `wording` ("v1" or "v2", see QUESTION_WORDINGS):
    a list of dicts with `question` (as in the Responses schema), `text` (what the model reads) and
    `options` (the answers it may give)."""
    templates = QUESTION_WORDINGS[wording]
    state_candidates = candidates.filter(pl.col("state") == state)
    if state_candidates.height == 0:
        raise ValueError(f"No candidates for {state}")

    def question(name, question_candidates, options):
        text = templates[name].format(
            state_name=STATE_NAMES[state], date=ELECTION_DATE,
            candidates=candidate_list(question_candidates, wording) if question_candidates is not None else "",
        )
        return {"question": name, "text": text, "options": options}

    questions = [
        question("senate", state_candidates, state_candidates["candidate"].to_list() + NON_CANDIDATE_ANSWERS),
        question("generic", None, GENERIC_ANSWERS),
    ]
    if state == "AK":
        final_round = alaska_final_candidates(state_candidates)
        questions.append(question("alaska_final", final_round, final_round["candidate"].to_list() + NON_CANDIDATE_ANSWERS))
    return questions


def draws_by_model(models, draws):
    """How many times each model asks each question: `draws` is one number for every model, or a dict giving each
    model its own number (e.g. a decision model asked more often than a chat model)."""
    return draws if isinstance(draws, dict) else dict.fromkeys(models, draws)


def query_personas(personas, candidates, approach, models, draws, temperature, wording, ask):
    """Ask every persona every question in their state, in `wording` ("v1" or "v2"), with each model, `draws` times
    (one number, or a number per model: see draws_by_model()).

    `ask(model, persona, question, options, temperature, draw)` returns a dict with `answer`, `input_tokens`,
    `output_tokens` and `cost` (silicon.ask, or a fake one in the tests). Returns one row per answer, with the
    columns of the Responses schema. Answers that failed are kept as missing, never dropped."""
    questions_by_state = {state: questions_for_state(state, candidates, wording) for state in personas["state"].unique()}
    rows = []
    # Every combination of model, draw and persona.
    combinations = [
        (model, draw, persona)
        for model, model_draws in draws_by_model(models, draws).items()
        for draw in range(model_draws)
        for persona in personas.iter_rows(named=True)
    ]
    for model, draw, persona in combinations:
        persona_prompt = persona_to_prompt(persona)
        for question in questions_by_state[persona["state"]]:
            result = ask(model, persona_prompt, question["text"], question["options"], temperature, draw)
            rows.append({
                "approach": approach,
                "persona_id": persona["persona_id"],
                "state": persona["state"],
                "model": model,
                "draw": draw,
                "question": question["question"],
                "answer": result["answer"],
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "cost": result["cost"],
            })
    return pl.DataFrame(rows, schema_overrides={"answer": pl.String, "cost": pl.Float64})


def run_costs(responses):
    """What a run's answers cost, per model and in total: calls, personas, total cost and average cost per persona.

    `responses` is query_personas()'s result. The cost of an answer is what it cost when it was first asked, so
    answers taken from the cache count at their original cost: this is the cost of producing the run's answers."""
    per_model = responses.group_by("model").agg(
        pl.len().alias("calls"),
        pl.col("persona_id").n_unique().alias("personas"),
        pl.col("cost").sum().alias("total_cost"),
    )
    total = responses.select(
        pl.lit("all models").alias("model"),
        pl.len().alias("calls"),
        pl.col("persona_id").n_unique().alias("personas"),
        pl.col("cost").sum().alias("total_cost"),
    )
    return (
        pl.concat([per_model.sort("model"), total], how="vertical_relaxed")
        .with_columns(pl.col("calls", "personas").cast(pl.Int64))
        .with_columns(cost_per_persona=pl.col("total_cost") / pl.col("personas"))
    )
