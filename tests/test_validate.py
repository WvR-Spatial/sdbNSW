"""Tests for out-of-fold validation: folds, statistics, breakdown depth, correlogram, CLI.

Includes the leakage demonstration: a model that memorises location looks
excellent under a random split and is exposed by blocked folds, while a
two-parameter global line scores the same either way.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from scipy import ndimage
from scipy.spatial import cKDTree

from sdb import validate as V
from sdb.validate import (band_labels, block_bootstrap, block_folds, block_ids, breakdown_depth,
                          correlation_range, correlogram, cross_validate, depth_balanced_rmse,
                          depth_curve, exclusions_by_band, metrics, random_folds)


def test_constants_are_the_preregistered_ones():
    """Changing any of these is a deviation from the committed protocol (PROJECT_BRIEF.md)."""
    assert (V.BLOCK_M, V.N_FOLDS, V.N_REPEATS, V.N_BOOT) == (2000.0, 5, 10, 1000)
    assert V.BLOCK_CURVE_M == (0.0, 500.0, 1000.0, 2000.0, 4000.0)
    assert V.CATZOC == {"C": (2.0, 0.05), "B": (1.0, 0.02)}
    assert V.CORR_RANGE_R == 0.1 and V.GATE_RMSE_M == 4.0
    assert V.DIST_EDGES_M == (0.0, 50.0, 100.0, 200.0, 500.0, 1000.0, float("inf"))


# --- folds ---------------------------------------------------------------------

def test_block_ids_group_pixels_in_the_same_square():
    rows = np.array([0, 199, 0, 200, 399])
    cols = np.array([0, 199, 200, 0, 399])
    b = block_ids(rows, cols, block_px=200)
    assert b[0] == b[1] and len({b[0], b[2], b[3], b[4]}) == 4


def test_block_folds_never_split_a_block_and_balance_block_counts():
    rows, cols = np.divmod(np.arange(115 * 20), 115)          # 20 x 115 pixels
    blocks = block_ids(rows, cols, block_px=5)                 # 4 x 23 = 92 blocks
    f = block_folds(blocks, 5, np.random.default_rng(0))
    for b in np.unique(blocks):
        assert np.unique(f[blocks == b]).size == 1
    per_fold = [np.unique(blocks[f == k]).size for k in range(5)]
    assert sorted(per_fold) == [18, 18, 18, 19, 19]
    np.testing.assert_array_equal(f, block_folds(blocks, 5, np.random.default_rng(0)))
    assert not np.array_equal(f, block_folds(blocks, 5, np.random.default_rng(1)))


def test_block_folds_refuse_too_few_blocks():
    with pytest.raises(ValueError, match="blocks"):
        block_folds(np.array([1, 1, 2]), 5, np.random.default_rng(0))


def test_random_folds_are_balanced():
    f = random_folds(103, 5, np.random.default_rng(0))
    assert sorted(np.bincount(f)) == [20, 20, 21, 21, 21]


# --- statistics ------------------------------------------------------------------

def test_metrics_against_hand_values():
    m = metrics(np.array([1.0, 2, 3, 4]), np.array([1.0, 1, 4, 4]))   # e = 0, 1, -1, 0
    assert m["n"] == 4 and m["bias"] == 0.0
    assert m["rmse"] == pytest.approx(np.sqrt(0.5)) and m["mae"] == 0.5
    assert m["median_abs"] == 0.5 and m["p95_abs"] == pytest.approx(1.0)
    assert m["r2"] == pytest.approx(1 - 2 / 9)               # SST = 4 x 1.5^2


def test_band_labels_include_20_m_and_open_ends_for_predictions():
    lab, names = band_labels(np.array([0.0, 1.99, 2.0, 20.0, 20.01, -1.0]))
    assert lab.tolist() == [0, 0, 1, 4, -1, -1] and names[-1] == "15-20"
    lab, names = band_labels(np.array([-1.0, 0.5, 20.0, 25.0]), open_ends=True)
    assert [names[i] for i in lab] == ["<0", "0-2", "15-20", ">20"]


def test_depth_balanced_rmse_weights_bands_equally():
    true = np.r_[np.full(10, 1.0), np.full(1000, 12.0)]
    pred = true + np.r_[np.full(10, 1.0), np.full(1000, 3.0)]
    assert depth_balanced_rmse(pred, true) == pytest.approx(2.0)      # (1 + 3) / 2
    assert metrics(pred, true)["rmse"] == pytest.approx(np.sqrt((10 + 9000) / 1010))


def test_bootstrap_point_is_the_direct_statistic_and_the_interval_brackets_it():
    rng = np.random.default_rng(0)
    true = rng.uniform(0, 20, 5_000)
    pred = true + rng.normal(0.3, 1.0, true.size)
    blocks = rng.integers(0, 40, true.size)
    ci = block_bootstrap(pred, true, blocks, n_boot=300, rng=np.random.default_rng(1))
    m = metrics(pred, true)
    for k in ("bias", "rmse", "mae", "r2"):
        assert ci[k]["point"] == pytest.approx(m[k])
        assert ci[k]["lo"] <= m[k] <= ci[k]["hi"]


def test_bootstrap_resamples_blocks_not_pixels():
    """Errors shared within a block: the honest interval is set by the number of blocks."""
    rng = np.random.default_rng(2)
    blocks = np.repeat(np.arange(30), 200)
    pred = rng.normal(0, 1, 30)[blocks]                      # one error per block
    true = np.zeros_like(pred)
    wide = block_bootstrap(pred, true, blocks, n_boot=500, rng=np.random.default_rng(3))
    narrow = block_bootstrap(pred, true, np.arange(pred.size), n_boot=500,
                             rng=np.random.default_rng(3))
    w = wide["bias"]["hi"] - wide["bias"]["lo"]
    n = narrow["bias"]["hi"] - narrow["bias"]["lo"]
    assert w > 8 * n                                         # sqrt(200) ~ 14 in expectation


# --- breakdown depth -------------------------------------------------------------

def _planted_curve(slope):
    return [{"lo": float(k), "hi": k + 1.0, "n": 100, "p95_abs": slope * (k + 0.5)}
            for k in range(20)]


def test_breakdown_depth_on_planted_error_curves():
    # p95 = 0.2 d:  C when 0.2 d > 2 + 0.05 d, d > 13.33 -> bin [13, 14)
    #               B when 0.2 d > 1 + 0.02 d, d > 5.56  -> bin [6, 7)
    assert breakdown_depth(_planted_curve(0.2), *V.CATZOC["C"]) == 13.0
    assert breakdown_depth(_planted_curve(0.2), *V.CATZOC["B"]) == 6.0
    # p95 = 0.1 d never exceeds C within 20 m (crossing at 40 m)
    assert breakdown_depth(_planted_curve(0.1), *V.CATZOC["C"]) is None


def test_depth_curve_bins_by_lidar_depth():
    true = np.array([0.2, 0.8, 5.5, 20.0])
    c = depth_curve(true + np.array([1.0, -1.0, 2.0, 0.5]), true)
    assert c[0]["n"] == 2 and c[0]["bias"] == 0.0 and c[0]["rmse"] == 1.0
    assert c[5]["bias"] == 2.0 and c[19]["n"] == 1 and len(c) == 20


# --- correlogram ---------------------------------------------------------------------

def test_white_noise_has_no_range_and_a_smooth_field_has_its_known_one():
    rng = np.random.default_rng(4)
    white = rng.normal(0, 1, (300, 300))
    cw = correlogram(white, pixel_m=10, lags_m=(10, 50, 200), rng=np.random.default_rng(5))
    assert all(abs(row["r"]) < 0.05 for row in cw)
    assert correlation_range(cw) == 10
    # Gaussian-filtered noise, sigma 20 px: r(h) = exp(-h^2 / (4 sigma^2)) -> r < 0.1 beyond ~61 px
    smooth = ndimage.gaussian_filter(rng.normal(0, 1, (600, 600)), 20)
    cs = correlogram(smooth, pixel_m=10, lags_m=(200, 500, 1000, 2000), rng=np.random.default_rng(6))
    by = {row["lag_m"]: row["r"] for row in cs}
    assert 0.6 < by[200] < 0.9                                 # theory 0.78
    assert 0.1 < by[500] < 0.35                                # theory 0.21
    assert correlation_range(cs) == 1000


# --- exclusions -----------------------------------------------------------------------

def test_exclusions_count_reasons_within_reference_water():
    flags = np.array([0, 0, V.FLAG_CLOUD, V.FLAG_BRIGHT_WATER | V.FLAG_CLOUD, V.FLAG_LAND,
                      V.FLAG_DEPTH], dtype=np.uint8)
    depth = np.array([1.0, 1.5, 1.0, 1.2, 1.0, 25.0])
    ok = np.array([True, False, True, True, True, True])
    row = exclusions_by_band(flags, depth, ok)[0]
    assert row["reference_px"] == 4 and row["assessed_px"] == 1
    assert (row["cloud_or_shadow"], row["bright_nir"], row["ratio_undefined"]) == (2, 1, 1)


# --- leakage: what blocked folds are for ---------------------------------------------------

class _Knn:
    """Predicts from the 5 nearest training pixels in space: memorises location."""

    def __init__(self, X, y):
        self.tree, self.y = cKDTree(X), y

    def predict(self, X):
        return self.y[self.tree.query(X, k=5)[1]].mean(axis=1)


class _Line:
    def __init__(self, x, y):
        self.m1, self.c = np.polyfit(x, y, 1)

    def predict(self, x):
        return self.m1 * x + self.c


def test_blocked_folds_expose_a_model_that_memorises_location():
    rng = np.random.default_rng(8)
    field = ndimage.gaussian_filter(rng.normal(0, 1, (120, 120)), 8)
    y = (field / field.std() * 4 + 10).ravel()               # a smooth "depth" surface
    rows, cols = np.divmod(np.arange(y.size), 120)
    xy = np.c_[rows, cols].astype(float)
    signal = y + rng.normal(0, 1.5, y.size)                   # a noisy, location-free predictor
    rand = random_folds(y.size, 5, np.random.default_rng(0))
    blk = block_folds(block_ids(rows, cols, block_px=24), 5, np.random.default_rng(0))
    rmse = lambda p: np.sqrt(np.mean((p - y) ** 2))  # noqa: E731
    fit_knn = lambda X, t, _r: _Knn(X, t)  # noqa: E731
    fit_line = lambda X, t, _r: _Line(X, t)  # noqa: E731
    knn_rand = rmse(cross_validate(xy, y, rand, fit_knn, rng)[0])
    knn_blk = rmse(cross_validate(xy, y, blk, fit_knn, rng)[0])
    line_rand = rmse(cross_validate(signal, y, rand, fit_line, rng)[0])
    line_blk = rmse(cross_validate(signal, y, blk, fit_line, rng)[0])
    assert knn_rand < 0.3 * knn_blk                          # random split flatters it badly
    assert line_blk / line_rand == pytest.approx(1.0, abs=0.05)   # a global line: no difference


# --- CLI end to end ----------------------------------------------------------------------

def _scene(root, n=150, wl=-0.4):
    import rasterio
    import yaml

    from sdb.reference import Grid

    sd = root / "data" / "raw" / "scenes" / "S"
    sd.mkdir(parents=True)
    g = Grid(300000.0, 6120000.0, 10.0, 10.0, n, n)
    rows, cols = np.divmod(np.arange(n * n), n)
    depth = (0.5 + 18.5 * (cols + rows / n) / n).reshape(n, n)
    ratio = (np.minimum(depth, 12.0) + 38.0) / 40.0          # depth = 40 r - 38 to 12 m, then saturated
    green = np.full((n, n), 0.02)
    blue = np.exp(ratio * np.log(1000 * 0.02)) / 1000        # inverts the Stumpf ratio exactly
    prof = dict(driver="GTiff", width=n, height=n, crs="EPSG:32756", transform=g.transform(),
                dtype="float32")
    with rasterio.open(sd / "reflectance.tif", "w", count=4, **prof) as dst:
        for i, (nm, v) in enumerate((("blue", blue), ("green", green), ("red", green / 4),
                                     ("nir", green / 10)), 1):
            dst.write(v.astype(np.float32), i)
            dst.set_band_description(i, nm)
    flags = np.zeros((n, n), np.uint8)
    flags[:, :2] = V.FLAG_LAND
    flags[40:45, 60:70] = V.FLAG_CLOUD
    land = (flags & V.FLAG_LAND) > 0
    rel = np.random.default_rng(0).uniform(0, 0.2, (n, n))
    layers = {"z_mean": wl - depth, "coverage": np.ones((n, n)), "relief": rel,
              "land_frac": land.astype(float)}
    with rasterio.open(sd / "reference.tif", "w", count=4, **prof) as dst:
        for i, nm in enumerate(layers, 1):
            dst.write(layers[nm].astype(np.float32), i)
            dst.set_band_description(i, nm)
    with rasterio.open(sd / "mask.tif", "w", count=1, **{**prof, "dtype": "uint8"}) as dst:
        dst.write(flags, 1)
    out = root / "outputs"
    out.mkdir()
    (out / "reference_S.json").write_text(json.dumps(
        {"water_level_m_ahd": wl, "water_level_source": "test"}))
    cfg = root / "sites.yml"
    half = [[300000, 6120000], [300750, 6120000], [300750, 6118500], [300000, 6118500]]
    cfg.write_text(yaml.safe_dump({"sites": {"t": {"strata": {"inside_bay": {
        "epsg": 32756, "polygon": half}}}}}))
    return cfg, out, sd


def test_cli_end_to_end(tmp_path):
    import rasterio

    cfg, out, sd = _scene(tmp_path)
    rc = V.main(["--site", "t", "--config", str(cfg), "--scene", "S", "--root", str(tmp_path),
                 "--out", str(out), "--block-m", "300", "--curve-blocks", "0,300",
                 "--repeats", "2", "--boot", "50"])
    assert rc == 0
    rec = json.loads((out / "sdb_S.json").read_text())
    assert rec["deviations"] and rec["protocol_commit"] is None
    assert rec["pixels"]["assessed"] == 150 * 148 - 50
    assert 11.0 <= rec["saturation_depth_d_cal_m"]["median"] <= 13.0
    assert rec["all_data_calibration"]["m1"] == pytest.approx(40.0, rel=0.02)
    assert rec["gate"]["result"] == "pass" and rec["pooled"]["rmse"] < 4
    # below saturation the line is exact; beyond it SDB is stuck at ~12 m and reads too shallow
    shallow = [row for row in rec["by_band_lidar_depth"] if row["group"] in ("0-2", "2-5", "5-10")]
    assert all(abs(row["bias"]) < 0.05 for row in shallow)
    assert rec["by_band_lidar_depth"][-1]["bias"] < -3
    assert rec["breakdown_depth_m"]["CATZOC_C"] in (13.0, 14.0, 15.0)
    groups = {g["group"] for g in rec["strata"]["inside_bay_vs_open_coast"]}
    assert groups == {"inside bay", "open coast"}
    assert [c["block_m"] for c in rec["block_size_curve"]] == [0.0, 300.0]
    assert rec["exclusions_by_band"][2]["cloud_or_shadow"] > 0
    assert len(rec["figures"]) == 3 and all(Path(f).exists() for f in rec["figures"])
    with rasterio.open(sd / "sdb.tif") as s:
        assert s.descriptions == ("oof_depth", "residual") and s.count == 2


def test_cli_refuses_without_a_reference_record(tmp_path):
    cfg, out, _ = _scene(tmp_path)
    (out / "reference_S.json").unlink()
    assert V.main(["--site", "t", "--config", str(cfg), "--scene", "S", "--root", str(tmp_path),
                   "--out", str(out), "--no-figures"]) == 2


def test_protocol_commit_is_the_one_that_introduced_the_protocol(tmp_path):
    """Not the latest edit to the brief: results committed later must not move it."""
    import shutil
    import subprocess

    if shutil.which("git") is None:
        pytest.skip("git not installed")
    git = lambda *a: subprocess.run(["git", "-C", str(tmp_path), *a], check=True,  # noqa: E731
                                    capture_output=True, text=True).stdout.strip()
    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    brief = tmp_path / "PROJECT_BRIEF.md"
    brief.write_text("# brief\n")
    git("add", "."), git("commit", "-qm", "start")
    brief.write_text("# brief\n## Phase 2 protocol - pre-registered 27 Sep 2026\n")
    git("commit", "-qam", "pre-register")
    first = git("rev-parse", "HEAD")
    brief.write_text(brief.read_text() + "results\n")
    git("commit", "-qam", "results")
    assert V._git_commit(tmp_path, "PROJECT_BRIEF.md")["commit"] == first
