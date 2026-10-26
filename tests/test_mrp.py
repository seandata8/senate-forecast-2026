#### Preamble ####
# Purpose: Tests for the forecast's model (src/senate_forecast_2026/mrp.py): the design matrix, the choice
#          probabilities, the fit and post-stratification, on small made-up data whose answers are known.
# Author: Furkan Danisman
# Date: 25 October 2026
# Pre-requisites: none
# Run from the repo root: uv run pytest

import numpy as np
import polars as pl
import pytest

from senate_forecast_2026.mrp import (
    PARTIES,
    PREDICTORS,
    available_parties,
    choice_probabilities,
    design_matrix,
    fit,
    poststratify,
)

ALL_PARTIES = np.ones((1, len(PARTIES)))
NO_INDEPENDENT = np.array([[1.0, 1.0, 0.0]])


def people(n, **values):
    """`n` identical people: the first category of every predictor, unless `values` gives another."""
    row = {predictor: categories[0] for predictor, categories in PREDICTORS.items()} | values
    return pl.DataFrame([row] * n)


def two_party_data(n, democrat_share, state="AK"):
    """`n` people in `state` choosing between a Democrat and a Republican, `democrat_share` of them the Democrat."""
    n_democrat = round(n * democrat_share)
    x = design_matrix(people(n, state=state))
    chosen = np.zeros((n, len(PARTIES)))
    chosen[:n_democrat, PARTIES.index("Democrat")] = 1
    chosen[n_democrat:, PARTIES.index("Republican")] = 1
    return x, chosen, np.repeat(NO_INDEPENDENT, n, axis=0), np.ones(n)


def test_design_matrix_has_an_intercept_and_one_column_per_category():
    x = design_matrix(people(3))
    assert x.shape == (3, 1 + sum(len(categories) for categories in PREDICTORS.values()))
    assert (x[:, 0] == 1).all()
    assert (x.sum(axis=1) == 1 + len(PREDICTORS)).all()  # each person is in exactly one category of each predictor


def test_with_zero_coefficients_every_available_party_is_equally_likely():
    x = design_matrix(people(1))
    coefficients = np.zeros((x.shape[1], 2))
    assert choice_probabilities(coefficients, x, ALL_PARTIES) == pytest.approx(np.array([[1 / 3, 1 / 3, 1 / 3]]))
    assert choice_probabilities(coefficients, x, NO_INDEPENDENT) == pytest.approx(np.array([[0.5, 0.5, 0.0]]))


def test_a_democrat_coefficient_of_log_3_gives_the_democrat_three_quarters():
    x = design_matrix(people(1))
    coefficients = np.zeros((x.shape[1], 2))
    coefficients[0, 0] = np.log(3)  # the intercept for Democrat: odds of 3 to 1 against the Republican
    assert choice_probabilities(coefficients, x, NO_INDEPENDENT)[0] == pytest.approx([0.75, 0.25, 0.0])


def test_available_parties_follows_the_ballot():
    candidates = pl.DataFrame({"state": ["AK", "AK", "NE", "NE"], "party": ["Democrat", "Republican", "Republican", "Independent"]})
    assert available_parties(["AK", "NE"], candidates).tolist() == [[1, 1, 0], [0, 1, 1]]


def test_fit_recovers_the_share_in_the_data():
    x, chosen, available, weights = two_party_data(2000, 0.7)
    mode, _ = fit(x, chosen, available, weights)
    assert choice_probabilities(mode, x[:1], available[:1])[0, 0] == pytest.approx(0.7, abs=0.01)


def test_more_data_means_less_uncertainty():
    variances = []
    for n in [200, 2000]:
        mode, covariance = fit(*two_party_data(n, 0.6))
        assert covariance.shape == (mode.size, mode.size)
        assert np.all(np.linalg.eigvalsh(covariance) > 0)  # a proper covariance
        variances.append(covariance[0, 0])
    assert variances[1] < variances[0]


def test_weights_count_as_answers():
    # 100 answers for the Democrat at weight 3 and 100 for the Republican at weight 1 are like 300 against 100.
    x, chosen, available, _ = two_party_data(200, 0.5)
    weights = np.where(chosen[:, 0] == 1, 3.0, 1.0)
    mode, _ = fit(x, chosen, available, weights)
    assert choice_probabilities(mode, x[:1], available[:1])[0, 0] == pytest.approx(0.75, abs=0.01)


def test_poststratify_weights_cells_by_their_voters():
    # Two cells in one state, men and women: the Democrat gets 3/4 of the men and 1/2 of the women.
    # With 300 men and 100 women, the Democrat's share is (300 * 3/4 + 100 * 1/2) / 400 = 0.6875.
    man, woman = PREDICTORS["gender"][:2]
    frame = pl.concat([people(1, state="AK", gender=man), people(1, state="AK", gender=woman)]).with_columns(
        count=pl.Series([300, 100])
    )
    coefficients = np.zeros((design_matrix(frame).shape[1], 2))
    gender_columns = 1 + len(PREDICTORS["age_group"])  # the first gender column, after the intercept and the ages
    coefficients[gender_columns, 0] = np.log(3)  # the first gender (Man): odds of 3 to 1 for the Democrat
    candidates = pl.DataFrame({"state": ["AK", "AK"], "party": ["Democrat", "Republican"]})
    shares = poststratify(coefficients, frame, candidates)
    assert shares["party"].to_list() == ["Democrat", "Republican"]  # no Independent on this ballot
    assert shares["share"].to_list() == pytest.approx([0.6875, 0.3125])
