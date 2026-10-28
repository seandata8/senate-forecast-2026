#### Preamble ####
# Purpose: The 2024 CES codes and their labels that more than one script needs: the state, gender, race, education
#          and party ID tables, and age groups. Used by #4 scripts/04-build_personas.py (the personas) and #8
#          scripts/08-build_frame.py (the weighting frame), so both describe people in exactly the same groups.
# Author: Sean Murphy (the tables, from scripts/04-build_personas.py); moved here by Furkan Danisman
# Date: 22 October 2026; moved 24 October 2026
# Pre-requisites: none

import polars as pl

# The CES codes of the 35 race states in `inputstate`: the US Census state numbers (FIPS codes), e.g. 1 = Alabama.
# Checked against the respondent counts per state in the CES 2024 guide.
STATE_OF_CES_CODE = {
    "1": "AL", "2": "AK", "5": "AR", "8": "CO", "10": "DE", "12": "FL", "13": "GA", "16": "ID", "17": "IL",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "30": "MT", "31": "NE", "33": "NH", "34": "NJ", "35": "NM", "37": "NC", "39": "OH", "40": "OK", "41": "OR",
    "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "51": "VA", "54": "WV", "56": "WY",
}

SURVEY_YEAR = 2024  # personas are described as they were when surveyed, so age = 2024 - birth year


def age_group(birth_year, survey_year=SURVEY_YEAR):
    """The age group (as in AGE_GROUPS in schemas.py) of a polars expression of birth years, in `survey_year`."""
    age = survey_year - birth_year.cast(pl.Int64)
    return (
        pl.when(age < 30)
        .then(pl.lit("18-29"))
        .when(age < 45)
        .then(pl.lit("30-44"))
        .when(age < 65)
        .then(pl.lit("45-64"))
        .otherwise(pl.lit("65+"))
    )


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
