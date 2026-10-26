#### Preamble ####
# Purpose: The model behind the forecast (multilevel regression and post-stratification, MRP). A persona's answer
#          is a choice among the parties on their state's ballot (Democrat, Republican, Independent), predicted from
#          their age group, gender, race, education, party group and state. Every group's effect has a normal prior
#          centred on 0, so a group with few personas is pulled towards the average: that is the "multilevel" part.
#          The model is fit by finding the most likely coefficients (the posterior mode) and approximating its
#          uncertainty with a normal distribution around them (Laplace approximation). Post-stratification then
#          weights each frame cell's predicted choice by its number of voters.
#          Used by #8 scripts/08-forecast.py.
# Author: Furkan Danisman
# Date: 24 October 2026
# Pre-requisites: frame from scripts/08-build_frame.py; personas, candidates and responses

import numpy as np
import polars as pl
from scipy.optimize import minimize

from senate_forecast_2026.schemas import AGE_GROUPS, EDUCATION, GENDERS, PARTY_GROUPS, RACES, STATES

# The predictors and their categories. Each category gets its own coefficient for each party.
PREDICTORS = {
    "age_group": AGE_GROUPS,
    "gender": GENDERS,
    "race": RACES,
    "education": EDUCATION,
    "party_group": PARTY_GROUPS,
    "state": STATES,
}
# The choices. Republican is the reference: its utility is 0, and the other parties' coefficients are relative to it.
PARTIES = ["Democrat", "Republican", "Independent"]
MODELLED_PARTIES = ["Democrat", "Independent"]
# Prior standard deviations, on the log-odds scale. Group effects: 1, so a group's effect is usually within about
# +-2 log-odds (odds multiplied or divided by up to about 7) unless the data say otherwise. Intercepts: 5, so they are
# barely pulled at all. These are our own choices; a full multilevel model would estimate the group spread.
GROUP_PRIOR_SD = 1.0
INTERCEPT_PRIOR_SD = 5.0


def design_matrix(rows):
    """One row per person or cell: an intercept, then a 0/1 column for each category of each predictor."""
    columns = [np.ones(rows.height)]
    for predictor, categories in PREDICTORS.items():
        values = rows[predictor].to_numpy()
        columns += [(values == category).astype(float) for category in categories]
    return np.column_stack(columns)


def prior_sds():
    """The prior standard deviation of each column of design_matrix(): the intercept's, then the groups'."""
    n_group_columns = sum(len(categories) for categories in PREDICTORS.values())
    return np.array([INTERCEPT_PRIOR_SD] + [GROUP_PRIOR_SD] * n_group_columns)


def available_parties(states, candidates):
    """A 0/1 matrix, one row per state in `states` and one column per party in PARTIES: whether the party has a
    candidate in the state's race (in Alaska, the final round: the Democrat against the incumbent)."""
    on_ballot = set(candidates.select("state", "party").iter_rows())
    return np.array([[float((state, party) in on_ballot) for party in PARTIES] for state in states])


def choice_probabilities(coefficients, x, available):
    """The probability of each party (columns in PARTIES order) for each row of `x`, among the parties available.

    `coefficients` has one column per party in MODELLED_PARTIES; the Republican utility is 0."""
    utilities = np.zeros((x.shape[0], len(PARTIES)))
    for column, party in enumerate(MODELLED_PARTIES):
        utilities[:, PARTIES.index(party)] = x @ coefficients[:, column]
    utilities = np.where(available > 0, utilities, -np.inf)  # a party not on the ballot can't be chosen
    utilities -= utilities.max(axis=1, keepdims=True)
    exponentials = np.exp(utilities)
    return exponentials / exponentials.sum(axis=1, keepdims=True)


def fit(x, chosen, available, weights):
    """Fit the model: the posterior mode of the coefficients and their covariance (Laplace approximation).

    `chosen` is each answer's party as a 0/1 row over PARTIES; `weights` is how much each answer counts.
    Returns (mode, covariance), the mode as a (columns of x, MODELLED_PARTIES) array."""
    n_columns = x.shape[1]
    precision = 1 / prior_sds() ** 2
    modelled = [PARTIES.index(party) for party in MODELLED_PARTIES]

    def negative_log_posterior(flat):
        coefficients = flat.reshape(n_columns, len(MODELLED_PARTIES), order="F")
        probabilities = choice_probabilities(coefficients, x, available)
        log_likelihood = np.sum(weights * np.log(np.sum(chosen * probabilities, axis=1)))
        log_prior = -0.5 * np.sum(precision[:, None] * coefficients**2)
        # Gradient: for each modelled party, the weighted (chosen - probability) times x, minus the prior's pull.
        residuals = (chosen - probabilities)[:, modelled] * weights[:, None]
        gradient = x.T @ residuals - precision[:, None] * coefficients
        return -(log_likelihood + log_prior), -gradient.ravel(order="F")

    start = np.zeros(n_columns * len(MODELLED_PARTIES))
    result = minimize(negative_log_posterior, start, jac=True, method="L-BFGS-B", options={"maxiter": 5000})
    if not result.success:
        raise RuntimeError(f"The model did not converge: {result.message}")
    mode = result.x.reshape(n_columns, len(MODELLED_PARTIES), order="F")

    # Hessian of the negative log posterior at the mode: for each pair of modelled parties (a, b), the weighted
    # x' diag(p_a (1[a=b] - p_b)) x, plus the prior precision on the diagonal.
    probabilities = choice_probabilities(mode, x, available)
    size = n_columns * len(MODELLED_PARTIES)
    hessian = np.zeros((size, size))
    for a, party_a in enumerate(modelled):
        for b, party_b in enumerate(modelled):
            p_a, p_b = probabilities[:, party_a], probabilities[:, party_b]
            curvature = weights * p_a * ((party_a == party_b) - p_b)
            hessian[a * n_columns:(a + 1) * n_columns, b * n_columns:(b + 1) * n_columns] = x.T @ (curvature[:, None] * x)
    hessian += np.diag(np.tile(precision, len(MODELLED_PARTIES)))
    return mode, np.linalg.inv(hessian)


def poststratify(coefficients, frame, candidates):
    """Each state's party shares: every frame cell's predicted choice, weighted by its number of voters.
    Returns one row per state and party on the ballot: state, party, share (summing to 1 in each state)."""
    x = design_matrix(frame)
    probabilities = choice_probabilities(coefficients, x, available_parties(frame["state"].to_list(), candidates))
    counts = frame["count"].to_numpy().astype(float)
    shares = (
        pl.DataFrame({"state": frame["state"], **{party: probabilities[:, i] * counts for i, party in enumerate(PARTIES)}})
        .group_by("state")
        .agg(pl.col(PARTIES).sum())
        .unpivot(index="state", variable_name="party", value_name="voters")
        .with_columns(share=pl.col("voters") / pl.col("voters").sum().over("state"))
    )
    on_ballot = candidates.select("state", "party").unique()
    return shares.join(on_ballot, on=["state", "party"]).select("state", "party", "share").sort("state", "party")
