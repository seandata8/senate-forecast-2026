#### Preamble ####
# Purpose: Build personas, in data/02-analysis_data/: PERSONAS_PER_STATE real respondents from the 2024 CES in each
#          of the 35 race states, with the details the prompt describes them by. They are picked at random from the
#          respondents who took the post-election survey, because their weight (commonpostweight) comes from it.
# Author: Sean Murphy
# Date: 22 October 2026
# Pre-requisites: uv run scripts/01-download_election_data.py (without the full CES file, the committed sample is used)
# Run: uv run scripts/04-build_personas.py (or PyCharm's run button)

import polars as pl

from senate_forecast_2026.paths import ANALYSIS_DATA, RAW_CES_2024, SAMPLE_CES_2024, full_file_or_sample
from senate_forecast_2026.save import save_data
from senate_forecast_2026.schemas import Personas

PERSONAS_PER_STATE = 30  # 35 states x 30 = 1,050 personas, as in the simulated data
PERSONA_SEED = 853

# The CES columns the personas are built from. Each one's codes are in the CES 2024 guide.
CES_COLUMNS = [
    "caseid",  # the CES's id for each respondent
    "tookpost",  # whether they took the post-election survey
    "inputstate",  # state they live in
    "birthyr",  # year of birth
    "gender4",  # gender
    "race",  # race, with Hispanic as one of its categories
    "educ",  # highest level of education
    "faminc_new",  # family income bracket
    "pid7",  # party ID on a 7-point scale, from Strong Democrat to Strong Republican
    "ideo5",  # ideology on a 5-point scale, from Very liberal to Very conservative
    "religpew",  # religion
    "marstat",  # marital status
    "sexuality",  # sexual orientation
    "votereg",  # registered to vote
    "CC24_410",  # 2024 presidential vote
    "commonpostweight",  # survey weight for the post-election survey
]
TOOK_POST_SURVEY = "2"  # tookpost: 1 = No, 2 = Yes

# The CES codes of the 35 race states in `inputstate`: the US Census state numbers (FIPS codes), e.g. 1 = Alabama.
# Checked against the respondent counts per state in the CES 2024 guide.
STATE_OF_CES_CODE = {
    "1": "AL", "2": "AK", "5": "AR", "8": "CO", "10": "DE", "12": "FL", "13": "GA", "16": "ID", "17": "IL",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "30": "MT", "31": "NE", "33": "NH", "34": "NJ", "35": "NM", "37": "NC", "39": "OH", "40": "OK", "41": "OR",
    "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "51": "VA", "54": "WV", "56": "WY",
}

SURVEY_YEAR = 2024  # personas are described as they were when surveyed, so age = 2024 - birth year

# Each CES code and its label in schemas.py. The codes are from the CES 2024 guide, checked by matching its
# respondent counts for each label to the counts of each code in the data (the guide does not list them in code order).
GENDER_OF_CES_CODE = {"1": "Man", "2": "Woman", "3": "Non-binary", "4": "Other"}  # gender4
RACE_OF_CES_CODE = {  # race
    "1": "White",
    "2": "Black",
    "3": "Hispanic",
    "4": "Asian",
    "5": "Native American",
    "6": "Two or more races",
    "7": "Other",
    "8": "Middle Eastern",
}
EDUCATION_OF_CES_CODE = {  # educ
    "1": "No HS",
    "2": "High school graduate",
    "3": "Some college",
    "4": "2-year",
    "5": "4-year",
    "6": "Post-grad",
}
INCOME_OF_CES_CODE = {  # faminc_new: its 16 brackets combined into 6
    "1": "Under $30K",  # less than $10,000
    "2": "Under $30K",  # $10,000 - $19,999
    "3": "Under $30K",  # $20,000 - $29,999
    "4": "$30K-$50K",  # $30,000 - $39,999
    "5": "$30K-$50K",  # $40,000 - $49,999
    "6": "$50K-$70K",  # $50,000 - $59,999
    "7": "$50K-$70K",  # $60,000 - $69,999
    "8": "$70K-$100K",  # $70,000 - $79,999
    "9": "$70K-$100K",  # $80,000 - $99,999
    "10": "$100K-$150K",  # $100,000 - $119,999
    "11": "$100K-$150K",  # $120,000 - $149,999
    "12": "$150K+",  # $150,000 - $199,999
    "13": "$150K+",  # $200,000 - $249,999
    "14": "$150K+",  # $250,000 - $349,999
    "15": "$150K+",  # $350,000 - $499,999
    "16": "$150K+",  # $500,000 or more
    "97": "Prefer not to say",
}
PARTY_ID_OF_CES_CODE = {  # pid7
    "1": "Strong Democrat",
    "2": "Not very strong Democrat",
    "3": "Lean Democrat",
    "4": "Independent",
    "5": "Lean Republican",
    "6": "Not very strong Republican",
    "7": "Strong Republican",
    "8": "Not sure",
}
IDEOLOGY_OF_CES_CODE = {  # ideo5
    "1": "Very liberal",
    "2": "Liberal",
    "3": "Moderate",
    "4": "Conservative",
    "5": "Very conservative",
    "6": "Not sure",
}
RELIGION_OF_CES_CODE = {  # religpew
    "1": "Protestant",
    "2": "Roman Catholic",
    "3": "Mormon",
    "4": "Eastern or Greek Orthodox",
    "5": "Jewish",
    "6": "Muslim",
    "7": "Buddhist",
    "8": "Hindu",
    "9": "Atheist",
    "10": "Agnostic",
    "11": "Nothing in particular",
    "12": "Something else",
}
MARITAL_STATUS_OF_CES_CODE = {  # marstat
    "1": "Married",
    "2": "Separated",
    "3": "Divorced",
    "4": "Widowed",
    "5": "Never married",
    "6": "Domestic / civil partnership",
}
SEXUALITY_OF_CES_CODE = {  # sexuality
    "1": "Heterosexual / straight",
    "2": "Lesbian / gay woman",
    "3": "Gay man",
    "4": "Bisexual",
    "5": "Other",
    "6": "Prefer not to say",
}
REGISTERED_OF_CES_CODE = {"1": "Yes", "2": "No", "3": "Don't know"}  # votereg
VOTE_2024_OF_CES_CODE = {  # CC24_410 (there is no code 7)
    "1": "Kamala Harris",
    "2": "Donald Trump",
    "3": "Robert F. Kennedy, Jr.",
    "4": "Jill Stein",
    "5": "Cornel West",
    "6": "Chase Oliver",
    "8": "Other",
    "9": "Did not vote for President",
}


#### Read the CES ####
ces_path = full_file_or_sample(RAW_CES_2024, SAMPLE_CES_2024)
# Read as text: the CES stores answers as codes ("1", "2", ...), which are looked up as text below.
# "NA" means the respondent did not answer, so it is read as missing.
ces = pl.read_csv(ces_path, columns=CES_COLUMNS, infer_schema_length=0, null_values="NA")
post_survey_respondents = ces.filter(pl.col("tookpost") == TOOK_POST_SURVEY)
print(f"Read {ces.height:,} CES respondents; {post_survey_respondents.height:,} took the post-election survey", flush=True)


#### State and age group ####
# Keep only the 35 states with a Senate race, and turn the state's number into its two-letter code.
race_state_respondents = post_survey_respondents.filter(pl.col("inputstate").is_in(list(STATE_OF_CES_CODE)))
age = SURVEY_YEAR - pl.col("birthyr").cast(pl.Int64)
race_state_respondents = race_state_respondents.with_columns(
    state=pl.col("inputstate").replace_strict(STATE_OF_CES_CODE),
    age_group=pl.when(age < 30)
    .then(pl.lit("18-29"))
    .when(age < 45)
    .then(pl.lit("30-44"))
    .when(age < 65)
    .then(pl.lit("45-64"))
    .otherwise(pl.lit("65+")),
)
print(f"{race_state_respondents.height:,} of them live in the 35 race states", flush=True)
print(race_state_respondents.group_by("age_group").len().sort("age_group"))


#### Turn the CES codes into labels ####
# Each code becomes its label from the tables above. A code missing from its table stops the script with an error,
# so a coding mistake cannot slip through. A missing answer stays missing.
race_state_respondents = race_state_respondents.with_columns(
    gender=pl.col("gender4").replace_strict(GENDER_OF_CES_CODE),
    race=pl.col("race").replace_strict(RACE_OF_CES_CODE),
    education=pl.col("educ").replace_strict(EDUCATION_OF_CES_CODE),
    income=pl.col("faminc_new").replace_strict(INCOME_OF_CES_CODE),
    party_id=pl.col("pid7").replace_strict(PARTY_ID_OF_CES_CODE),
    ideology=pl.col("ideo5").replace_strict(IDEOLOGY_OF_CES_CODE),
    religion=pl.col("religpew").replace_strict(RELIGION_OF_CES_CODE),
    marital_status=pl.col("marstat").replace_strict(MARITAL_STATUS_OF_CES_CODE),
    sexuality=pl.col("sexuality").replace_strict(SEXUALITY_OF_CES_CODE),
    registered=pl.col("votereg").replace_strict(REGISTERED_OF_CES_CODE),
    vote_2024=pl.col("CC24_410").replace_strict(VOTE_2024_OF_CES_CODE),
    weight=pl.col("commonpostweight").cast(pl.Float64),
)
# Missing answers in each column, so they can be seen before they are dealt with.
PERSONA_DETAILS = [
    "state", "age_group", "gender", "race", "education", "income", "party_id", "ideology", "religion",
    "marital_status", "sexuality", "registered", "vote_2024", "weight",
]
missing_answers = race_state_respondents.select(PERSONA_DETAILS).null_count()
print("Missing answers:", flush=True)
for column in PERSONA_DETAILS:
    print(f"  {column:<15} {missing_answers[column][0]:>6,}", flush=True)


#### Drop respondents with a missing detail ####
# Every detail but vote_2024 goes in the prompt, so a persona needs all of them. vote_2024 may be missing: it is
# for reference only (most of those missing were probably not asked, having said they did not vote).
DETAILS_NEEDED = [column for column in PERSONA_DETAILS if column != "vote_2024"]
complete_respondents = race_state_respondents.drop_nulls(subset=DETAILS_NEEDED)
dropped = race_state_respondents.height - complete_respondents.height
print(f"Dropped {dropped} respondents with a missing detail; {complete_respondents.height:,} are left", flush=True)

# How many are left in each state, most to least, 7 states to a line, so a state too small for PERSONAS_PER_STATE stands out. Need at least 30.
STATES_PER_LINE = 7
respondents_per_state = complete_respondents.group_by("state").len().sort("len", "state", descending=[True, False])
state_counts = [f"{state}: {count:>5,}" for state, count in respondents_per_state.iter_rows()]
print("Respondents left in each state:", flush=True)
for first in range(0, len(state_counts), STATES_PER_LINE):
    print("  " + "    ".join(state_counts[first : first + STATES_PER_LINE]), flush=True)


#### Pick the personas ####
# PERSONAS_PER_STATE at random from each state: shuffle everyone (seeded, so it picks the same personas every run),
# then keep the first PERSONAS_PER_STATE in each state. A state with fewer keeps all it has, which only happens with
# the small CES sample.
shuffled_respondents = complete_respondents.sample(fraction=1.0, shuffle=True, seed=PERSONA_SEED)
personas = shuffled_respondents.group_by("state", maintain_order=True).head(PERSONAS_PER_STATE)
# Ids from 0 up, in order of state and then the CES's id.
personas = (
    personas.sort("state", pl.col("caseid").cast(pl.Int64))
    .with_row_index("persona_id")
    .with_columns(pl.col("persona_id").cast(pl.Int64))
)
print(f"Picked {personas.height:,} personas", flush=True)
short_states = personas.group_by("state").len().filter(pl.col("len") < PERSONAS_PER_STATE)
if short_states.height > 0:
    print(f"WARNING: {short_states.height} states have fewer than {PERSONAS_PER_STATE} personas", flush=True)


#### Save ####
# Keep only the columns in the Personas schema, in its order. save_data() checks the schema first.
personas = personas.select(["persona_id"] + PERSONA_DETAILS)
if ces_path == SAMPLE_CES_2024:
    # Personas from the small sample only show that the code runs. Saving them would replace the real personas,
    # so they are checked against the schema but not saved.
    Personas.validate(personas, lazy=True)
    print("Built from the CES sample, so checked against the schema but not saved; the real personas are kept.")
else:
    save_data(personas, Personas, ANALYSIS_DATA, "personas")
