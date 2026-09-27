"""Tests for measuring image-to-lidar misregistration.

Synthetic scenes are built the way the real one behaves: NIR is a linear mix of
land and water in proportion to the land fraction the sensor actually saw --
the lidar aggregated onto the scene grid displaced by a KNOWN shift -- plus
noise and a little blur for the sensor's point-spread function. The estimator
must recover the shift, with the right sign, and must refuse when it cannot.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import ndimage

from sdb.coreg import (
    Segment, estimate_shift, slope_and_normal, solve_shift, steep_shore_segments, verdict,
    waterline_cells,
)
from sdb.reference import Grid, land_fraction

SRC = Grid(1000.454, 9001.421, 5.0, 5.0, 640, 640)      # 3.2 km of 5 m lidar
DST = Grid(1000.0, 9000.0, 10.0, 10.0, 320, 320)


def _centres(grid):
    x, y = grid.centres()
    return np.meshgrid(x, y)


def _island(profile):
    """Radially symmetric island around the grid centre; profile(r) -> z."""
    X, Y = _centres(SRC)
    r = np.hypot(X - (SRC.x0 + 1600), Y - (SRC.y0 - 1600))
    return profile(r).astype(np.float32), np.ones(X.shape, bool)


def _image(z, valid, shift, *, water_level=0.0, noise=0.004, seed=0):
    """NIR the sensor would record if each pixel really saw ground at nominal + shift."""
    rng = np.random.default_rng(seed)
    lf, cov = land_fraction(z, valid, SRC, DST.shifted(*shift), water_level)
    nir = 0.003 + 0.25 * np.nan_to_num(lf) + rng.normal(0, noise, lf.shape)
    nir = ndimage.gaussian_filter(nir, 0.4).astype(np.float32)
    nir[cov < 0.999] = np.nan
    return nir


CLIFF = _island(lambda r: np.clip(620.0 - r, -15, 20))           # 45 degree shore at r = 620


# --- pieces ----------------------------------------------------------------

def test_slope_and_normal_of_a_plane():
    g = Grid(0.0, 500.0, 5.0, 5.0, 60, 60)
    X, Y = _centres(g)
    z = (0.3 * X - 0.4 * Y).astype(np.float32)                    # rises east, falls north
    slope, ne, nn = slope_and_normal(z, np.ones_like(z, bool), g)
    assert np.nanmedian(slope) == pytest.approx(math.degrees(math.atan(0.5)), abs=1e-3)
    assert np.nanmedian(ne) == pytest.approx(0.6, abs=1e-5)       # uphill = east and south
    assert np.nanmedian(nn) == pytest.approx(-0.8, abs=1e-5)


def test_waterline_is_the_land_edge():
    z = np.array([[-1, -1, 2, 3], [-1, 1, 2, 3]], np.float32)
    wl = waterline_cells(z, np.ones_like(z, bool), 0.0)
    assert wl.tolist() == [[False, False, True, False], [False, True, False, False]]


def test_segments_cover_all_facings_of_a_round_island():
    z, v = CLIFF
    segs = steep_shore_segments(z, v, SRC, DST, water_level=0.0)
    facings = sorted(round(s.facing_deg / 45) % 8 for s in segs)
    assert facings == list(range(8))


def test_segment_facing_is_seaward():
    s = Segment(0, np.array([0]), np.array([0]), normal=(1.0, 0.0), centroid=(0.0, 0.0))
    assert s.facing_deg == pytest.approx(270.0)                   # land to the east faces west


# --- recovery ---------------------------------------------------------------

@pytest.mark.parametrize("shift", [(7.3, -4.1), (-18.5, -11.1), (0.0, 12.0)])
def test_recovers_a_known_shift_with_the_right_sign(shift):
    z, v = CLIFF
    nir = _image(z, v, shift)
    rec = estimate_shift(z, v, SRC, DST, nir, np.isfinite(nir))
    assert rec["shift_m"]["east"] == pytest.approx(shift[0], abs=0.5)
    assert rec["shift_m"]["north"] == pytest.approx(shift[1], abs=0.5)
    assert rec["verdict"] == "apply"
    assert rec["cross_check"]["agrees"]


def test_no_shift_is_reported_as_negligible():
    z, v = CLIFF
    nir = _image(z, v, (0.0, 0.0))
    rec = estimate_shift(z, v, SRC, DST, nir, np.isfinite(nir))
    assert rec["magnitude_m"] < 0.6
    assert rec["verdict"] == "negligible"


def test_applying_the_estimate_aligns_lidar_and_image():
    """End-to-end sign check: aggregating the lidar onto the grid translated by
    the estimate must make it agree with the image better than not doing so."""
    z, v = CLIFF
    nir = _image(z, v, (-18.5, -11.1))
    rec = estimate_shift(z, v, SRC, DST, nir, np.isfinite(nir), cross_check=False)
    s = (rec["shift_m"]["east"], rec["shift_m"]["north"])
    ok = np.isfinite(nir)

    def r(shift):
        lf, _ = land_fraction(z, v, SRC, DST.shifted(*shift), 0.0)
        m = ok & np.isfinite(lf)
        return np.corrcoef(nir[m], lf[m])[0, 1]

    assert r(s) > r((0.0, 0.0)) + 0.01
    assert r(s) > r((-s[0], -s[1]))


# --- why steep shores only ---------------------------------------------------

def _cliffs_and_beaches():
    """Cliffs on three quadrants; a gentle 1:20 beach faces south-east."""
    X, Y = _centres(SRC)
    cx, cy = SRC.x0 + 1600, SRC.y0 - 1600
    dx, dy = X - cx, Y - cy
    r = np.hypot(dx, dy)
    beach_side = (dx > 0) & (dy < 0)
    steep = np.clip(620.0 - r, -15, 20)
    gentle = np.clip((620.0 - r) / 20.0, -15, 20)
    return np.where(beach_side, gentle, steep).astype(np.float32), np.ones(X.shape, bool)


def test_steep_shores_resist_a_tide_error_that_biases_beaches():
    """True water level -0.6 m, assumed 0.0 m. On a 1:20 beach that moves the
    waterline 12 m; on a 45 degree cliff 0.6 m."""
    z, v = _cliffs_and_beaches()
    true = (7.3, -4.1)
    nir = _image(z, v, true, water_level=-0.6)
    ok = np.isfinite(nir)
    steep = estimate_shift(z, v, SRC, DST, nir, ok, water_level=0.0, min_slope=30, min_px=10,
                           cross_check=False)
    anyshore = estimate_shift(z, v, SRC, DST, nir, ok, water_level=0.0, min_slope=0, min_px=10,
                              cross_check=False)
    err_steep = math.hypot(steep["shift_m"]["east"] - true[0], steep["shift_m"]["north"] - true[1])
    err_any = math.hypot(anyshore["shift_m"]["east"] - true[0], anyshore["shift_m"]["north"] - true[1])
    assert err_steep < 1.5
    assert err_any > 3 * err_steep


# --- refusing to answer -----------------------------------------------------

def test_a_straight_coast_cannot_fix_the_along_shore_component():
    X, Y = _centres(SRC)
    z = np.clip((X - 2600.0), -15, 20).astype(np.float32)        # one straight N-S cliff
    v = np.ones_like(z, bool)
    nir = _image(z, v, (5.0, 5.0))
    rec = estimate_shift(z, v, SRC, DST, nir, np.isfinite(nir))
    assert rec["verdict"] == "insufficient"


def _res(normal, offset, n=40, seg=0):
    return {"segment": seg, "normal": list(normal), "offset_m": offset, "n_px": n, "status": "ok"}


def test_solver_recovers_a_shift_from_normal_offsets_and_drops_an_outlier():
    s = np.array([-18.0, -6.0])
    normals = [(math.sin(math.radians(a)), math.cos(math.radians(a))) for a in range(0, 360, 45)]
    rows = [_res(n, float(np.dot(n, s)), seg=i) for i, n in enumerate(normals)]
    rows[3]["offset_m"] += 25.0                                   # one biased segment
    sol = solve_shift(rows)
    assert sol["shift_m"]["east"] == pytest.approx(-18.0, abs=1e-6)
    assert sol["shift_m"]["north"] == pytest.approx(-6.0, abs=1e-6)
    assert sol["segments_dropped"] == [3]


def test_solver_refuses_too_few_or_parallel_segments():
    assert solve_shift([_res((1, 0), 3.0), _res((0, 1), 2.0)])["verdict"] == "insufficient"
    par = [_res((1, 0), 3.0, seg=i) for i in range(5)]
    assert solve_shift(par)["verdict"] == "insufficient"


def test_verdict_rules():
    base = {"shift_m": {"east": -18.5, "north": -11.1}, "stderr_m": {"east": 2.9, "north": 5.8},
            "magnitude_m": 21.6, "residual_rms_m": 4.8}
    assert verdict(base)[0] == "apply"
    assert verdict({**base, "residual_rms_m": 7.0})[0] == "inconsistent"
    assert verdict({**base, "magnitude_m": 1.5})[0] == "negligible"
    assert verdict({**base, "magnitude_m": 9.0})[0] == "negligible"          # < 2 x stderr (13 m)
    assert verdict(base, {"agrees": False, "reason": "x"})[0] == "inconsistent"
    assert verdict({"verdict": "insufficient", "reason": "few"})[0] == "insufficient"
