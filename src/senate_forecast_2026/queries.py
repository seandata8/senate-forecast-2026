#### Preamble ####
# Purpose: Turn personas into prompts, build each persona's questions with the candidates on their own ballot,
#          and ask every question, collecting the answers in the format of the Responses schema.
#          No API calls happen here: the function that calls a model (`ask` in silicon.py) is passed in,
#          so the tests can use a fake one that costs nothing.
# Author: Furkan Danisman
# Date: 22 October 2026
# Pre-requisites: uv sync

from itertools import product

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


def candidate_list(state_candidates):
    """The candidates as they appear in a question, e.g. "Jane Smith (Democrat), John Doe (Republican)"."""
    return ", ".join(f"{row['candidate']} ({row['party']})" for row in state_candidates.iter_rows(named=True))


def alaska_final_candidates(alaska_candidates):
    """The two candidates in Alaska's ranked-choice final round: the Democrat and the incumbent (a Republican)."""
    final_round = alaska_candidates.filter((pl.col("party") == "Democrat") | pl.col("incumbent"))
    if final_round.height != 2:
        raise ValueError(f"Expected 2 candidates in Alaska's final round, found {final_round.height}")
    return final_round


# The wording of each question, by version. Placeholders: {state_name}, {date}, {candidates}.
# v1 lists "Undecided" and "Would not vote" as plain instructions after the question.
V1_CHOOSE_NOTE = 'If you have not decided, answer "Undecided". If you will not vote, answer "Would not vote".'
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
}


def questions_for_state(state, candidates, wording):
    """The questions every persona in `state` is asked, in `wording` (a key of QUESTION_WORDINGS):
    a list of dicts with `question` (as in the Responses schema), `text` (what the model reads) and
    `options` (the answers it may give)."""
    templates = QUESTION_WORDINGS[wording]
    state_candidates = candidates.filter(pl.col("state") == state)
    if state_candidates.height == 0:
        raise ValueError(f"No candidates for {state}")

    def question(name, question_candidates, options):
        text = templates[name].format(
            state_name=STATE_NAMES[state], date=ELECTION_DATE,
            candidates=candidate_list(question_candidates) if question_candidates is not None else "",
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


def query_personas(personas, candidates, approach, models, draws, temperature, wording, ask):
    """Ask every persona every question in their state, in `wording` (a key of QUESTION_WORDINGS), with each model, `draws` times.

    `ask(model, persona, question, options, temperature, draw)` returns a dict with `answer`, `input_tokens`,
    `output_tokens` and `cost` (silicon.ask, or a fake one in the tests). Returns one row per answer, with the
    columns of the Responses schema. Answers that failed are kept as missing, never dropped."""
    questions_by_state = {state: questions_for_state(state, candidates, wording) for state in personas["state"].unique()}
    rows = []
    # product() loops over every combination of model, draw and persona.
    for model, draw, persona in product(models, range(draws), personas.iter_rows(named=True)):
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
