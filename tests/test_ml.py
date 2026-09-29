"""Tests for v2: features, the fixed model, and that it learns what a straight line cannot."""
from __future__ import annotations

import numpy as np
import pytest

from sdb import ml
from sdb.ml import SPECTRAL, XY, features, fit_gbm, spectral_features


def test_constants_are_the_preregistered_ones():
    """Changing any of these is a deviation from the committed v2 protocol (PROJECT_BRIEF.md)."""
    assert ml.HGB_PARAMS == {"loss": "squared_error", "max_iter": 300, "learning_rate": 0.1,
                             "max_leaf_nodes": 31, "min_samples_leaf": 100, "early_stopping": False}
    assert SPECTRAL == ("ln_blue", "ln_green", "ln_red", "ln_nir", "psdb_green", "psdb_red")
    assert ml.MODELS == {"gbm": SPECTRAL, "gbm_xy": SPECTRAL + XY} and ml.DEMONSTRATIONS == ("gbm_xy",)


def test_spectral_features_by_hand():
    F = spectral_features(np.array([0.02]), np.array([0.01]), np.array([0.004]), np.array([0.002]))
    assert F.shape == (1, 6)
    np.testing.assert_allclose(F[0], [np.log(20), np.log(10), np.log(4), np.log(2),
                                      np.log(20) / np.log(10), np.log(20) / np.log(4)], rtol=1e-6)


def test_undefined_logs_are_missing_not_errors():
    F = spectral_features(np.array([0.02]), np.array([0.01]), np.array([0.0005]), np.array([0.0]))
    assert np.isnan(F[0, 3]) and np.isnan(F[0, 5])          # ln(0) and a negative red log
    assert np.isfinite(F[0, 4])                              # the Stumpf ratio is still defined


def test_coordinates_only_for_the_demonstration_model():
    b = np.full(3, 0.02)
    assert features("gbm", b, b, b, b).shape == (3, 6)
    F = features("gbm_xy", b, b, b, b, x=np.array([300000.0, 301000, 302000]), y=np.zeros(3))
    assert F.shape == (3, 8) and F[:, 6].tolist() == [300.0, 301.0, 302.0]
    with pytest.raises(ValueError, match="coordinates"):
        features("gbm_xy", b, b, b, b)
    with pytest.raises(ValueError, match="unknown"):
        features("rf", b, b, b, b)


def _two_water_types(n=40_000, seed=0):
    """Depth from a saturating ratio, with a second water type that saturates earlier."""
    rng = np.random.default_rng(seed)
    d = rng.uniform(0, 20, n)
    open_coast = rng.random(n) < 0.3
    k = np.where(open_coast, 0.15, 0.06)
    ratio = 1.3 - 0.35 * np.exp(-k * d) + rng.normal(0, 0.005, n)
    tint = np.where(open_coast, 0.8, 1.0)                    # the water types differ in colour
    green = 0.02 * tint * np.ones(n)
    blue = np.exp(ratio * np.log(1000 * green)) / 1000
    return d, blue, green, open_coast


def test_the_fixed_model_learns_what_a_straight_line_cannot():
    from sdb.sdb import fit_linear, predict

    d, blue, green, _ = _two_water_types()
    red, nir = green / 4, green / 10
    X = spectral_features(blue, green, red, nir)
    tr, te = np.arange(d.size) < 30_000, np.arange(d.size) >= 30_000
    m = fit_gbm(X[tr], d[tr], np.random.default_rng(1))
    gbm_rmse = np.sqrt(np.mean((m.predict(X[te]) - d[te]) ** 2))
    m1, m0 = fit_linear(X[tr, 4], d[tr])
    line_rmse = np.sqrt(np.mean((predict(X[te, 4], m1, m0) - d[te]) ** 2))
    assert gbm_rmse < 0.5 * line_rmse
    assert m.summary()["n_iter"] == 300 and m.n_sample <= 20 * 5000


def test_the_fit_is_reproducible_from_the_seed():
    d, blue, green, _ = _two_water_types(5_000)
    X = spectral_features(blue, green, green / 4, green / 10)
    a = fit_gbm(X, d, np.random.default_rng(3)).predict(X[:50])
    b = fit_gbm(X, d, np.random.default_rng(3)).predict(X[:50])
    np.testing.assert_array_equal(a, b)
