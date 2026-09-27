"""Tests for the Stumpf transform and its pre-registered calibration rule.

Expected values are worked out by hand from each construction.
"""
from __future__ import annotations

import numpy as np
import pytest

from sdb import sdb as S
from sdb.sdb import (balanced_sample, binned_medians, calibrate, fit_linear, predict,
                     running_median, saturation_depth, stumpf_ratio)


def _depths(n=40_000, top=20.0, seed=0):
    return np.random.default_rng(seed).uniform(0, top, n)


def test_constants_are_the_preregistered_ones():
    """Changing any of these is a deviation from the committed protocol (PROJECT_BRIEF.md)."""
    assert (S.N_SCALE, S.BIN_M, S.MAX_DEPTH_M, S.MIN_BIN_COUNT, S.SMOOTH_BINS,
            S.RISE_FRACTION, S.PER_BIN_CAP) == (1000.0, 1.0, 20.0, 200, 3, 0.95, 5000)


# --- the transform -----------------------------------------------------------

def test_ratio_is_the_log_ratio():
    assert stumpf_ratio(np.array([0.02]), np.array([0.01]))[0] == pytest.approx(np.log(20) / np.log(10))


def test_ratio_is_undefined_where_a_log_is_not_positive():
    blue = np.array([0.02, 0.0005, 0.02, np.nan])
    green = np.array([0.01, 0.01, 0.001, 0.01])        # 1000 * 0.001 = 1 -> ln = 0
    r = stumpf_ratio(blue, green)
    assert np.isfinite(r[0]) and np.isnan(r[1:]).all()


def test_ratio_rises_with_depth_when_green_attenuates_faster():
    """Two-band exponential attenuation over a bright seabed -- the physics the ratio relies on."""
    z = np.linspace(0, 15, 16)
    blue = 0.017 + (0.08 - 0.017) * np.exp(-2 * 0.05 * z)
    green = 0.009 + (0.09 - 0.009) * np.exp(-2 * 0.12 * z)
    assert np.all(np.diff(stumpf_ratio(blue, green)) > 0)


# --- the line --------------------------------------------------------------------

def test_fit_recovers_an_exact_line():
    r = np.linspace(1.0, 1.4, 50)
    m1, m0 = fit_linear(r, 40.0 * r - 38.0)
    assert (m1, m0) == (pytest.approx(40.0), pytest.approx(38.0))
    assert predict(np.array([1.2]), m1, m0)[0] == pytest.approx(10.0)


def test_fit_refuses_a_constant_ratio():
    with pytest.raises(ValueError, match="spread"):
        fit_linear(np.full(5, 1.1), np.arange(5.0))


# --- binning and smoothing ------------------------------------------------------

def test_binned_medians_and_counts():
    d = np.array([0.5, 0.6, 1.5, 19.99, 20.0, 20.5, -0.1])
    r = np.array([1.0, 3.0, 2.0, 5.0, 7.0, 9.0, 9.0])
    med, n = binned_medians(d, r, min_count=1)
    assert (med[0], n[0]) == (2.0, 2)
    assert (med[1], n[1]) == (2.0, 1)
    assert (med[19], n[19]) == (6.0, 2)                 # exactly 20 m joins the top bin
    assert n.sum() == 5                                 # 20.5 and -0.1 are outside 0-20


def test_bins_below_the_minimum_count_are_ignored():
    med, _ = binned_medians(np.array([0.5, 0.6, 1.5]), np.array([1.0, 2.0, 3.0]), min_count=2)
    assert med[0] == 1.5 and np.isnan(med[1])


def test_running_median_uses_finite_neighbours_only():
    out = running_median(np.array([1, 5, 2, 8, np.nan, 3.0]))
    np.testing.assert_allclose(out, [3, 2, 5, 5, np.nan, 3])


# --- the saturation rule ------------------------------------------------------------

@pytest.mark.parametrize("shape, expected, rule", [
    ("plateau", 12.0, "95% of rise"),     # linear to 12 m, flat beyond
    ("peak", 10.0, "95% of rise"),        # linear to 10 m, falling beyond (blue still dimming)
    ("steady", 20.0, "rises throughout"),  # the protocol's exception, as written
])
def test_saturation_depth_on_planted_curves(shape, expected, rule):
    d = _depths()
    r = {"plateau": 1 + 0.02 * np.minimum(d, 12),
         "peak": np.where(d <= 10, 1 + 0.02 * d, 1.2 - 0.01 * (d - 10)),
         "steady": 1 + 0.02 * d}[shape]
    d_cal, info = saturation_depth(d, r)
    assert d_cal == expected and info["rule"] == rule and not info["degenerate"]


def test_saturation_is_robust_to_pixel_noise():
    """Noise of 0.02 in the ratio is ~1 m of depth per pixel; bin medians shrug it off."""
    d = _depths(200_000)
    r = 1 + 0.02 * np.minimum(d, 12) + np.random.default_rng(1).normal(0, 0.02, d.size)
    assert saturation_depth(d, r)[0] in (12.0, 13.0)


def test_a_ratio_that_never_rises_is_degenerate():
    d = _depths()
    d_cal, info = saturation_depth(d, np.full(d.size, 1.1))
    assert info["degenerate"] and d_cal == 1.0


def test_saturation_refuses_when_no_bin_is_populated():
    with pytest.raises(ValueError, match="D_cal"):
        saturation_depth(np.array([1.0, 2.0]), np.array([1.0, 1.1]))


# --- the depth-balanced sample -------------------------------------------------------

def test_balanced_sample_caps_each_bin_and_stops_at_d_cal():
    d = np.r_[np.full(50, 0.5), np.full(10_000, 1.5), np.full(3, 5.5), np.full(100, 12.5)]
    idx = balanced_sample(d, d_max=12.0, rng=np.random.default_rng(0), cap=100)
    assert idx.size == 50 + 100 + 3
    assert np.all(d[idx] < 12.0) and np.unique(idx).size == idx.size


def test_balanced_sample_is_reproducible():
    d = _depths(5_000)
    a = balanced_sample(d, d_max=15, rng=np.random.default_rng(3), cap=50)
    b = balanced_sample(d, d_max=15, rng=np.random.default_rng(3), cap=50)
    np.testing.assert_array_equal(a, b)


# --- calibration end to end ------------------------------------------------------------

def _line_then_plateau(d):
    return (np.minimum(d, 12.0) + 38.0) / 40.0          # depth = 40 r - 38 up to 12 m


def test_calibrate_recovers_the_line_below_saturation():
    d = _depths()
    cal = calibrate(d, _line_then_plateau(d), np.random.default_rng(0))
    assert cal.d_cal == 12.0 and not cal.degenerate
    assert (cal.m1, cal.m0) == (pytest.approx(40.0), pytest.approx(38.0))
    assert cal.n_sample == np.sum(d < 12.0)             # every bin under the 5,000 cap


def test_fitting_through_the_plateau_would_distort_the_line():
    """Why D_cal exists: saturated pixels (ratio stuck, depth still increasing) steepen the fit."""
    d = _depths()
    m1_all, _ = fit_linear(_line_then_plateau(d), d)
    assert abs(m1_all - 40.0) / 40.0 > 0.2


# --- water level: the claim that Phase 2 need not wait for the gauge ---------------------

def test_a_constant_water_level_error_moves_only_the_intercept():
    rng = np.random.default_rng(5)
    r = rng.uniform(1.0, 1.4, 5_000)
    d = 40 * r - 38 + rng.normal(0, 0.5, r.size)
    delta, wl = 0.37, -0.496
    m1, m0 = fit_linear(r, d)
    m1b, m0b = fit_linear(r, d + delta)                 # water level wrong by delta
    assert m1b == pytest.approx(m1) and m0b == pytest.approx(m0 - delta)
    np.testing.assert_allclose(predict(r, m1b, m0b) - (d + delta), predict(r, m1, m0) - d, atol=1e-9)
    # ...and the bathymetry in AHD, z = WL - depth, is identical
    np.testing.assert_allclose((wl + delta) - predict(r, m1b, m0b), wl - predict(r, m1, m0), atol=1e-9)
