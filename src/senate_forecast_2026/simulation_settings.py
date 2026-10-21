#### Preamble ####
# Purpose: The made-up numbers the simulation (#1) is built from. Kept here, not in the script, because the
#          simulated-data tests also need them: they check the simulated personas came out with these shares.
# Author: Sean Murphy
# Date: 21 October 2026
# Pre-requisites: none

from senate_forecast_2026.schemas import (
    AGE_GROUPS,
    EDUCATION,
    GENDERS,
    INCOMES,
    MARITAL_STATUSES,
    RACES,
    REGISTERED,
    RELIGIONS,
    SEXUALITIES,
    STATES,
)

# Rough Democratic share of the two-party vote in each state, typed in by hand (roughly the 2024 presidential result).
# Only needs to be plausible; the real past results come from #3, e.g. the Harvard Dataverse.
STATE_LEAN = {
    "AL": 0.35, "AK": 0.44, "AR": 0.34, "CO": 0.56, "DE": 0.58, "FL": 0.43, "GA": 0.49, "ID": 0.31, "IL": 0.56,
    "IA": 0.43, "KS": 0.42, "KY": 0.34, "LA": 0.39, "ME": 0.53, "MA": 0.63, "MI": 0.49, "MN": 0.52, "MS": 0.38,
    "MT": 0.39, "NE": 0.40, "NH": 0.51, "NJ": 0.53, "NM": 0.53, "NC": 0.49, "OH": 0.44, "OK": 0.32, "OR": 0.56,
    "RI": 0.57, "SC": 0.41, "SD": 0.35, "TN": 0.35, "TX": 0.43, "VA": 0.53, "WV": 0.29, "WY": 0.27,
}
assert sorted(STATE_LEAN) == sorted(STATES)

# For each persona column drawn at random: (categories, the share of personas meant to fall in each).
PERSONA_SHARES = {
    "age_group": (AGE_GROUPS, [0.15, 0.25, 0.35, 0.25]),
    "gender": (GENDERS, [0.46, 0.53, 0.008, 0.002]),
    "race": (RACES, [0.70, 0.12, 0.09, 0.03, 0.01, 0.003, 0.03, 0.017]),
    "education": (EDUCATION, [0.04, 0.27, 0.23, 0.11, 0.22, 0.13]),
    "income": (INCOMES, [0.25, 0.16, 0.14, 0.15, 0.13, 0.11, 0.06]),
    "religion": (RELIGIONS, [0.32, 0.18, 0.01, 0.005, 0.02, 0.01, 0.01, 0.005, 0.07, 0.08, 0.21, 0.08]),
    "marital_status": (MARITAL_STATUSES, [0.47, 0.02, 0.12, 0.06, 0.28, 0.05]),
    "sexuality": (SEXUALITIES, [0.87, 0.015, 0.03, 0.055, 0.015, 0.015]),
    "registered": (REGISTERED, [0.90, 0.09, 0.01]),
}
