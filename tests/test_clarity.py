"""Phase 4 clarity analysis: every statistic against a known answer."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from sdb import clarity as C
from sdb.reference import Grid


# --- ranks and Spearman ------------------------------------------------------

def test_ranks_share_ties():
    assert C._ranks(np.array([10.0, 20.0, 20.0, 30.0])).tolist() == [1.0, 2.5, 2.5, 4.0]


def test_spearman_known_answers():
    x = np.arange(10.0)
    assert C.spearman(x, x ** 3) == pytest.approx(1.0)          # monotone, not linear
    assert C.spearman(x, -x) == pytest.approx(-1.0)
    assert np.isnan(C.spearman(x, np.ones(10)))                  # constant: undefined
    assert np.isnan(C.spearman(x[:2], x[:2]))                    # too few points


def test_spearman_matches_scipy_with_ties():
    stats = pytest.importorskip("scipy.stats")
    rng = np.random.default_rng(3)
    x, y = rng.integers(0, 5, 40).astype(float), rng.integers(0, 5, 40).astype(float)
    assert C.spearman(x, y) == pytest.approx(stats.spearmanr(x, y).statistic, abs=1e-12)


def test_spearman_ci_is_reproducible_and_brackets_a_strong_trend():
    x = np.arange(20.0)
    y = x + np.random.default_rng(1).normal(0, 2, 20)
    a = C.spearman_ci(x, y, n_boot=200, rng=np.random.default_rng(5))
    b = C.spearman_ci(x, y, n_boot=200, rng=np.random.default_rng(5))
    assert a == b
    assert a["lo"] <= a["rho"] <= a["hi"] and a["lo"] > 0 and a["n_blocks"] == 20


def test_mean_within_site_ignores_a_site_offset():
    """The design's reason: one murkier, worse site must not make a correlation."""
    rng = np.random.default_rng(0)
    clear = (rng.uniform(0.002, 0.003, 30), rng.uniform(1.0, 2.0, 30))
    murky = (rng.uniform(0.008, 0.009, 30), rng.uniform(4.0, 5.0, 30))
    pooled = C.spearman(np.r_[clear[0], murky[0]], np.r_[clear[1], murky[1]])
    within = C.mean_within_site({"a": clear, "b": murky}, n_boot=200,
                                rng=np.random.default_rng(1))
    assert pooled > 0.7                                   # pooling across sites invents it
    assert abs(within["mean_rho"]) < 0.3 and within["lo"] < 0 < within["hi"]


# --- pixels, blocks, site metric ---------------------------------------------------

def test_clarity_pixels_are_assessed_and_10_to_20_m_inclusive():
    depth = np.array([9.99, 10.0, 15.0, 20.0, 20.01, np.nan])
    assessed = np.array([True, True, True, True, True, True])
    assert C.clarity_pixels(depth, assessed).tolist() == [False, True, True, True, False, False]
    assert not C.clarity_pixels(depth, ~assessed).any()


def test_block_table_medians_rmse_and_minimum_count():
    red = np.array([[0.002, 0.004, 0.010], [0.003, 0.005, 0.010]])
    resid = {"stumpf": np.array([[1.0, -1.0, 3.0], [1.0, -1.0, 3.0]])}
    blocks = np.array([[0, 0, 1], [0, 0, 1]])
    sel = np.ones_like(red, bool)
    tab = C.block_table(red, resid, sel, blocks, min_px=3)
    assert len(tab) == 1                                  # block 1 has 2 pixels: dropped
    t = tab[0]
    assert t["n"] == 4 and t["clarity"] == pytest.approx(0.0035)
    assert t["rmse"]["stumpf"] == pytest.approx(1.0)


def test_block_table_leaves_out_pixels_with_no_red_value():
    """One missing red value must not make the block's median NaN (Northern Beaches)."""
    red = np.array([[0.002, 0.004, np.nan], [0.003, 0.005, 0.010]])
    resid = {"stumpf": np.array([[1.0, -1.0, 9.0], [1.0, -1.0, 3.0]])}
    blocks = np.zeros_like(red, int)
    tab = C.block_table(red, resid, np.ones_like(red, bool), blocks, min_px=5)
    assert len(tab) == 1 and tab[0]["n"] == 5             # the NaN pixel is not counted
    assert tab[0]["clarity"] == pytest.approx(0.004)
    assert tab[0]["rmse"]["stumpf"] == pytest.approx(np.sqrt(13 / 5))   # nor in the RMSE
    depth = np.array([[10.0, 12.0, 99.0], [14.0, 16.0, 18.0]])
    with_depth = C.block_table(red, resid, np.ones_like(red, bool), blocks, min_px=5, depth=depth)
    assert with_depth[0]["mean_depth_m"] == pytest.approx(14.0) and "mean_depth_m" not in tab[0]
    assert C.block_table(red, resid, np.ones_like(red, bool), blocks, min_px=6) == []


def test_spearman_refuses_values_it_cannot_rank():
    with pytest.raises(ValueError, match="non-finite"):
        C.spearman(np.array([1.0, np.nan, 3.0, 4.0]), np.array([1.0, 2.0, 3.0, 4.0]))


def test_site_clarity_is_the_median_of_selected_finite_pixels():
    red = np.array([0.001, 0.002, 0.003, np.nan, 0.9])
    sel = np.array([True, True, True, True, False])
    assert C.site_clarity(red, sel) == {"median_red": pytest.approx(0.002), "n": 3}


def test_monotonic():
    assert C.monotonic([0.003, 0.002, 0.005], [2.7, 2.5, 3.1]) is True
    assert C.monotonic([0.003, 0.002, 0.005], [2.4, 2.5, 3.1]) is False
    assert C.monotonic([0.003, None], [1, 2]) is None


# --- the registered predictions ------------------------------------------------

def _site(red, rmse, rho, lo, hi, d, dlo, dhi):
    return {"clarity": {"median_red": red}, "stumpf": {"rmse": rmse},
            "within": {"stumpf": {"rho": rho, "lo": lo, "hi": hi}},
            "gbm_vs_stumpf": {"point": d, "lo": dlo, "hi": dhi}}


def test_predictions_all_held():
    s = {C.JB: _site(0.003, 2.68, 0.1, -0.3, 0.5, -0.80, -1.06, -0.57),
         C.NB: _site(0.004, 3.20, 0.2, -0.2, 0.6, -0.60, -0.90, -0.30),
         C.BB: _site(0.006, 3.50, 0.6, 0.20, 0.8, -0.40, -0.70, -0.10)}
    assert [p["result"] for p in C.evaluate_predictions(s)] == ["held"] * 4


def test_predictions_fail_as_written():
    s = {C.JB: _site(0.007, 2.68, 0.1, -0.3, 0.5, -0.80, -1.06, -0.57),
         C.NB: _site(0.004, 2.50, 0.2, -0.2, 0.6, -0.60, -0.90, -0.30),
         C.BB: _site(0.006, 3.50, 0.3, -0.1, 0.6, -0.90, -1.20, -0.60)}
    res = {p["prediction"]: p["result"] for p in C.evaluate_predictions(s)}
    assert res[1] == "failed"                              # Jervis Bay has the highest red
    assert res[2] == "failed"                              # Northern Beaches beat Jervis Bay
    assert res[3].startswith("not supported")              # positive, interval includes 0
    assert res[4] == "failed"                              # advantage larger at Batemans Bay


def test_predictions_not_evaluated_without_sites():
    assert all(p["result"] == "not evaluated" for p in C.evaluate_predictions({}))


def test_compare_records_is_other_minus_primary():
    prim = {"pooled": {"rmse": 2.0, "bias": -0.1}, "depth_balanced_rmse": 1.8,
            "by_band_lidar_depth": [{"group": "0-2", "rmse": 1.0}],
            "strata": {"relief_tercile": {"edges_m": [0.1, 0.2],
                                          "groups": [{"group": "low", "rmse": 1.5}]}}}
    other = {"pooled": {"rmse": 2.1, "bias": -0.05}, "depth_balanced_rmse": 1.9,
             "by_band_lidar_depth": [{"group": "0-2", "rmse": 1.3}],
             "strata": {"relief_tercile": {"edges_m": [0.05, 0.1],
                                           "groups": [{"group": "low", "rmse": 1.4}]}}}
    d = C.compare_records(prim, other)
    assert d["pooled_rmse"] == pytest.approx(0.1) and d["pooled_bias"] == pytest.approx(0.05)
    assert d["rmse_by_band"]["0-2"] == pytest.approx(0.3)
    assert d["rmse_by_relief_tercile"]["low"] == pytest.approx(-0.1)


# --- the analysis on synthetic sites -------------------------------------------

def _synthetic(red_slope: float, offset: float, n: int = 600, seed: int = 0):
    """A 6 km square of 10 m pixels; block RMSE in 10-20 m tracks block red if slope > 0."""
    rng = np.random.default_rng(seed)
    g = Grid(300000.0, 6120000.0, 10.0, 10.0, n, n)
    rows, cols = np.indices((n, n))
    blk = (rows // 200) * 3 + cols // 200                     # 9 blocks of 2 km
    red = 0.003 + 0.0005 * blk + offset
    depth = np.full((n, n), 15.0)
    depth[:, :20] = 5.0                                       # outside the clarity range
    scale = 1.0 + red_slope * blk + rng.uniform(0, 0.05, 9)[blk]
    e = rng.normal(0, 1, (n, n)) * scale
    return {"scene": "S", "grid": g, "red": red, "depth": depth,
            "assessed": np.ones((n, n), bool),
            "resid": {"stumpf": e, "gbm": 0.7 * e},
            "records": {"stumpf": {"pooled": {"rmse": float(np.sqrt(np.mean(e ** 2))),
                                              "bias": 0.0}},
                        "gbm": {"pooled": {"rmse": float(np.sqrt(np.mean((0.7 * e) ** 2))),
                                           "bias": 0.0},
                                "vs_stumpf": {"pooled": {"rmse_diff": {"point": -0.5, "lo": -0.7,
                                                                       "hi": -0.3}}}}},
            "water_level_m_ahd": 0.0}


def test_analyse_recovers_a_within_site_trend():
    res = C.analyse({"t": _synthetic(0.3, 0.0)}, n_boot=200)
    s = res["sites"]["t"]
    assert s["blocks_used"] == 9
    assert s["within"]["stumpf"]["rho"] > 0.8 and s["within"]["stumpf"]["lo"] > 0
    assert s["within"]["gbm"]["rho"] == pytest.approx(s["within"]["stumpf"]["rho"])
    assert s["clarity"]["n"] == 600 * 580


def test_analyse_finds_nothing_where_there_is_nothing():
    res = C.analyse({"t": _synthetic(0.0, 0.0, seed=4)}, n_boot=200)
    w = res["sites"]["t"]["within"]["stumpf"]
    assert w["lo"] < 0 < w["hi"]


# --- end to end through the validate CLI -----------------------------------------

def test_cli_end_to_end(tmp_path):
    import rasterio

    from sdb import validate as V
    from test_validate import _scene

    cfg, out, sd = _scene(tmp_path)
    with rasterio.open(sd / "reflectance.tif", "r+") as dst:      # red varies across blocks
        red = dst.read(3)
        dst.write((red * (1 + np.arange(red.shape[1]) / red.shape[1])).astype(np.float32), 3)
    common = ["--site", "t", "--config", str(cfg), "--scene", "S", "--root", str(tmp_path),
              "--out", str(out), "--block-m", "300", "--curve-blocks", "0,300",
              "--repeats", "2", "--boot", "20", "--no-figures"]
    assert V.main(common) == 0
    assert V.main(common + ["--model", "gbm"]) == 0
    assert C.main(["--run", "t=S", "--root", str(tmp_path), "--out", str(out),
                   "--boot", "50"]) == 0
    rec = json.loads((out / "phase4" / "clarity.json").read_text())
    assert rec["deviations"] == [*C.DEVIATIONS, "boot=50 (protocol 1000)"]
    assert rec["sites"]["t"]["clarity"]["n"] > 0
    assert set(rec["sites"]["t"]["within"]) == {"stumpf", "gbm"}
    assert Path(rec["figures"][0]).exists()
