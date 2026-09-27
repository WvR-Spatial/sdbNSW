"""Tests for putting the lidar on the scene grid.

Aggregation is checked against functions whose area-weighted mean is known in
closed form: a plane averages to its value at the pixel centre, a step to the
area fraction on one side. The grids are offset by the real Jervis Bay offset
(0.454, 1.421) m so partial cells are exercised everywhere.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from sdb.reference import (
    FLAG_BRIGHT_WATER, FLAG_CLOUD, FLAG_DEPTH, FLAG_LAND, FLAG_NO_IMAGE, FLAG_NO_LIDAR,
    Grid, LandFractionField, aggregate_dem, analysis_mask, land_fraction, overlap_matrix,
    plane_translation, summarise,
)

# 5 m lidar offset from a 10 m scene grid exactly as at Jervis Bay
SRC = Grid(x0=1000.454, y0=9000.0 + 1.421, dx=5.0, dy=5.0, nx=80, ny=80)
DST = Grid(x0=1020.0, y0=8980.0, dx=10.0, dy=10.0, nx=30, ny=30)   # well inside SRC


def _field(fn, grid=SRC):
    x, y = grid.centres()
    X, Y = np.meshgrid(x, y)
    return fn(X, Y).astype(np.float64)


# --- grid ------------------------------------------------------------------

def test_grid_round_trips_an_affine_transform():
    g = Grid.from_transform([10.0, 0.0, 285960.0, 0.0, -10.0, 6128380.0], (2292, 1962))
    assert (g.x0, g.y0, g.dx, g.dy, g.nx, g.ny) == (285960.0, 6128380.0, 10.0, 10.0, 1962, 2292)
    assert list(g.transform())[:6] == [10.0, 0.0, 285960.0, 0.0, -10.0, 6128380.0]


def test_grid_refuses_rotation_and_south_up():
    with pytest.raises(ValueError):
        Grid.from_transform([10.0, 0.5, 0.0, 0.0, -10.0, 0.0], (5, 5))
    with pytest.raises(ValueError):
        Grid.from_transform([10.0, 0.0, 0.0, 0.0, 10.0, 0.0], (5, 5))


def test_window_and_shift_move_the_origin_only():
    w = DST.window(3, 4, 5, 6)
    assert (w.x0, w.y0, w.nx, w.ny) == (DST.x0 + 40, DST.y0 - 30, 6, 5)
    s = DST.shifted(-18.5, -11.1)
    assert (s.x0, s.y0) == (DST.x0 - 18.5, DST.y0 - 11.1)


# --- overlap matrix --------------------------------------------------------

def test_overlaps_sum_to_the_destination_cell_when_fully_covered():
    W = overlap_matrix(SRC.x_edges(), DST.x_edges()).toarray()
    assert np.allclose(W.sum(axis=1), 10.0)


def test_overlap_is_partial_at_the_source_edge():
    src = np.array([0.0, 5.0, 10.0])
    dst = np.array([-3.0, 7.0, 17.0])
    W = overlap_matrix(src, dst).toarray()
    assert np.allclose(W, [[5.0, 2.0], [0.0, 3.0]])


def test_overlap_handles_arbitrary_ratios():
    src = np.linspace(0, 30, 8)          # 4.2857 m cells
    dst = np.array([1.0, 11.0, 21.0])
    W = overlap_matrix(src, dst).toarray()
    assert np.allclose(W.sum(axis=1), 10.0)


# --- aggregation, against closed forms -------------------------------------

def test_a_plane_averages_to_its_value_at_the_pixel_centre():
    """Holds only if partial cells are weighted by their true overlap AND the
    y axis runs the right way. Either mistake shows up here."""
    a, b, c = 0.03, -0.07, -12.0
    z = _field(lambda X, Y: a * (X - 1000) + b * (Y - 9000) + c)
    ref = aggregate_dem(z, np.ones_like(z, bool), SRC, DST)
    xc, yc = DST.centres()
    X, Y = np.meshgrid(xc, yc)
    assert np.allclose(ref["z_mean"], a * (X - 1000) + b * (Y - 9000) + c, atol=1e-4)
    assert np.allclose(ref["coverage"], 1.0)


def test_relief_of_a_plane_on_aligned_grids_is_known():
    """Four 5 m cells per 10 m pixel: values z0 +/- 2.5a +/- 2.5b, so the
    standard deviation is 2.5 * sqrt(a^2 + b^2)."""
    src = Grid(0.0, 100.0, 5.0, 5.0, 20, 20)
    dst = Grid(0.0, 100.0, 10.0, 10.0, 10, 10)
    a, b = 0.4, -0.3
    z = _field(lambda X, Y: a * X + b * Y, src)
    ref = aggregate_dem(z, np.ones_like(z, bool), src, dst)
    assert np.allclose(ref["relief"], 2.5 * math.hypot(a, b), atol=1e-5)


def test_a_step_averages_to_the_area_fraction():
    """A cliff at x = 1027.954 m lies inside destination pixel [1020, 1030] at
    source-cell boundary; the area-weighted mean is the fraction east of it."""
    x_step = SRC.x0 + 5.0 * 5            # a source cell edge: 1025.454
    z = _field(lambda X, Y: np.where(X > x_step, 10.0, 0.0))
    ref = aggregate_dem(z, np.ones_like(z, bool), SRC, DST)
    col = 0                              # [1020, 1030]
    assert ref["z_mean"][5, col] == pytest.approx(10.0 * (1030 - x_step) / 10.0, abs=1e-6)


def test_voids_reduce_coverage_and_are_ignored_by_the_mean():
    z = _field(lambda X, Y: np.full_like(X, -7.0))
    valid = np.ones_like(z, bool)
    valid[:, :30] = False                # a void over the west of the grid
    ref = aggregate_dem(z, valid, SRC, DST)
    cov = ref["coverage"]
    assert cov.min() == pytest.approx(0.0) and cov.max() == pytest.approx(1.0)
    partial = (cov > 0) & (cov < 1)
    assert partial.any()
    assert np.allclose(ref["z_mean"][cov > 0], -7.0)
    assert np.isnan(ref["z_mean"][cov == 0]).all()


def test_land_fraction_follows_the_water_level():
    z = _field(lambda X, Y: 0.05 * (X - 1150))          # shoreline at x = 1150 for wl 0
    v = np.ones_like(z, bool)
    lf0 = aggregate_dem(z, v, SRC, DST, water_level=0.0)["land_frac"]
    lf1 = aggregate_dem(z, v, SRC, DST, water_level=1.0)["land_frac"]   # shore moves 20 m east
    assert lf1.sum() == pytest.approx(lf0.sum() - 20.0 / 10.0 * DST.ny, rel=0.02)


def test_aggregating_onto_a_shifted_grid_equals_translating_the_field():
    a, b = 0.02, 0.05
    z = _field(lambda X, Y: a * X + b * Y)
    v = np.ones_like(z, bool)
    base = aggregate_dem(z, v, SRC, DST)["z_mean"]
    moved = aggregate_dem(z, v, SRC, DST.shifted(-18.47, -11.11))["z_mean"]
    assert np.allclose(moved - base, a * -18.47 + b * -11.11, atol=1e-4)


def test_cached_field_matches_the_one_shot_function():
    z = _field(lambda X, Y: 0.05 * (X - 1150) + 0.01 * (Y - 8900))
    v = np.ones_like(z, bool)
    f = LandFractionField(z, v, SRC, 0.3)
    for s in [(0, 0), (3.3, -7.1)]:
        a1, c1 = f.on(DST.shifted(*s))
        a2, c2 = land_fraction(z, v, SRC, DST.shifted(*s), 0.3)
        assert np.allclose(a1, a2, equal_nan=True) and np.allclose(c1, c2)


# --- datum -----------------------------------------------------------------

G = Grid(286500.454, 6127921.421, 5.0, 5.0, 3714, 4405)   # the real DEM grid


def test_gda2020_to_wgs84_utm_is_the_same_plane():
    (tx, ty), info = plane_translation("EPSG:7856", "EPSG:32756", G)
    assert math.hypot(tx, ty) < 0.01
    assert info["nonuniformity_m"] < 0.001


def test_gda94_to_gda2020_is_a_measurable_uniform_translation():
    """The ~1.5 m continental shift, near-uniform over 20 km: detected and returned."""
    (tx, ty), info = plane_translation("EPSG:28356", "EPSG:7856", G)
    assert 1.0 < math.hypot(tx, ty) < 2.5
    assert info["nonuniformity_m"] < 0.01


def test_a_different_utm_zone_is_refused():
    with pytest.raises(ValueError):
        plane_translation("EPSG:7856", "EPSG:7855", G)


# --- masks and summary -----------------------------------------------------

def _ref(z_mean, coverage=1.0, land=0.0, relief=0.05):
    shape = np.shape(z_mean)
    return {"z_mean": np.asarray(z_mean, np.float32),
            "coverage": np.full(shape, coverage, np.float32),
            "land_frac": np.full(shape, land, np.float32),
            "relief": np.full(shape, relief, np.float32)}


def test_mask_flags_each_reason_independently():
    ref = _ref([[-5.0, -5.0, -25.0, -5.0, -5.0, -5.0, 3.0]])
    ref["coverage"][0, 1] = 0.5
    ref["land_frac"][0, 6] = 1.0
    scl = np.array([[6, 6, 6, 9, 0, 6, 6]])
    nir = np.array([[0.003, 0.003, 0.003, 0.003, 0.003, 0.2, 0.3]], np.float32)
    f = analysis_mask(ref, scl=scl, nir=nir)[0]
    assert f[0] == 0
    assert f[1] & FLAG_NO_LIDAR
    assert f[2] & FLAG_DEPTH
    assert f[3] & FLAG_CLOUD
    assert f[4] & FLAG_NO_IMAGE
    assert f[5] & FLAG_BRIGHT_WATER
    assert f[6] & FLAG_LAND and not f[6] & FLAG_BRIGHT_WATER   # bright land is just land


def test_depth_window_is_relative_to_the_water_level():
    ref = _ref([[-0.3, -0.3]])
    assert analysis_mask(ref, water_level=0.0)[0, 0] == 0
    assert analysis_mask(ref, water_level=-0.5)[0, 0] & FLAG_DEPTH     # dry at low tide


def test_summary_bands_partition_the_usable_pixels():
    z = -np.array([[0.5, 1.5, 3.0, 7.0, 12.0, 18.0, 20.0, 25.0]])
    ref = _ref(z)
    flags = analysis_mask(ref)
    s = summarise(ref, flags, pixel_area_m2=100.0)
    assert s["pixels_usable"] == 7
    assert sum(b["pixels"] for b in s["by_depth_band"]) == 7        # 20.0 falls in the last band
    assert s["flagged_any"]["outside depth window"] == 1


# --- I/O round trip --------------------------------------------------------

def test_layers_round_trip_through_geotiff(tmp_path):
    import rasterio
    from sdb.reference import write_layers

    ref = _ref(np.full((4, 5), -3.0))
    write_layers(tmp_path / "r.tif", ref, Grid(0.0, 40.0, 10.0, 10.0, 5, 4), "EPSG:32756",
                 ("z_mean", "coverage", "relief", "land_frac"))
    with rasterio.open(tmp_path / "r.tif") as s:
        assert s.count == 4 and s.descriptions[0] == "z_mean"
        assert np.allclose(s.read(1), -3.0)
        assert s.transform.c == 0.0 and s.transform.f == 40.0
