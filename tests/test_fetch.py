"""Tests for AOI reads, reflectance scaling and the water plausibility check.

The integration tests build a synthetic Sentinel-2 granule on disk -- 10 m bands
and a 20 m SCL sharing an upper-left corner, digital numbers encoded exactly as
a baseline >= 04.00 product -- and read it back through the same code path that
reads https hrefs. Only the network transfer is untested, and that is GDAL's job.
"""
from __future__ import annotations

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin  # noqa: E402
from rasterio.warp import transform_bounds  # noqa: E402

from sdb.fetch import (  # noqa: E402
    GRID_MULTIPLE,
    SCL_WATER,
    Scaling,
    aligned_window,
    apply_scaling,
    offset_plausibility,
    read_aoi_stack,
    reflectance_scaling,
    scl_stats,
    upsample_exact,
    water_stretch,
)

CRS = "EPSG:32756"                       # WGS84 / UTM 56S, as Sentinel-2 ships
E0, N0 = 290_000.0, 6_120_000.0          # upper-left, inside Jervis Bay
N10 = 600                                # 6 km square at 10 m
TRUTH = {"blue": 0.05, "green": 0.04, "red": 0.010, "nir": 0.005}
BASE4 = Scaling(1e-4, -0.1, "test: baseline >= 04.00", True)
BASE2 = Scaling(1e-4, 0.0, "test: baseline < 04.00", True)


def _bbox_utm(e0, n0, e1, n1):
    return transform_bounds(CRS, "EPSG:4326", e0, n0, e1, n1, densify_pts=21)


INNER_BBOX = _bbox_utm(291_013, 6_116_007, 293_021, 6_118_011)   # deliberately off-grid


@pytest.fixture
def granule(tmp_path):
    """Write a synthetic granule; return {band: path}."""
    paths = {}
    for band, refl in TRUTH.items():
        dn = np.full((N10, N10), round((refl + 0.1) * 10_000), dtype="uint16")
        dn[:12, :12] = 0                                   # a nodata corner
        p = tmp_path / f"{band}.tif"
        with rasterio.open(p, "w", driver="GTiff", width=N10, height=N10, count=1,
                           dtype="uint16", crs=CRS, transform=from_origin(E0, N0, 10, 10),
                           nodata=0) as d:
            d.write(dn, 1)
        paths[band] = str(p)

    scl = np.full((N10 // 2, N10 // 2), SCL_WATER, dtype="uint8")
    scl[100:110, 100:110] = 9                              # a cloud patch
    p = tmp_path / "scl.tif"
    with rasterio.open(p, "w", driver="GTiff", width=N10 // 2, height=N10 // 2, count=1,
                       dtype="uint8", crs=CRS, transform=from_origin(E0, N0, 20, 20),
                       nodata=0) as d:
        d.write(scl, 1)
    paths["scl"] = str(p)
    return paths


# --- SCL statistics --------------------------------------------------------

def test_scl_stats_counts_cloud_and_water_over_valid_pixels_only():
    scl = np.array([[0, 0, 6, 6],
                    [6, 9, 9, 4]], dtype="uint8")          # 2 nodata, 3 water, 2 cloud, 1 veg
    st = scl_stats(scl)
    assert st["aoi_valid_pct"] == pytest.approx(75.0)
    assert st["aoi_water_pct"] == pytest.approx(50.0)       # 3 of 6 valid
    assert st["aoi_cloud_pct"] == pytest.approx(100 * 2 / 6, abs=0.01)


def test_scl_stats_all_nodata_is_not_reported_as_clear():
    st = scl_stats(np.zeros((4, 4), dtype="uint8"))
    assert st["aoi_valid_pct"] == 0.0
    assert st["aoi_cloud_pct"] != st["aoi_cloud_pct"]       # NaN, not 0


# --- scaling decisions -----------------------------------------------------

def test_declared_offset_agrees_with_a_collection1_baseline():
    s = reflectance_scaling([{"scale": 0.0001, "offset": -0.1}], "05.00")
    assert (s.scale, s.offset, s.agrees_with_baseline) == (0.0001, -0.1, True)


def test_declared_zero_offset_on_a_new_baseline_is_flagged_not_hidden():
    s = reflectance_scaling([{"scale": 0.0001, "offset": 0.0}], "05.00")
    assert s.offset == 0.0 and s.agrees_with_baseline is False


def test_scaling_falls_back_to_the_baseline_rule():
    assert reflectance_scaling(None, "05.00").offset == pytest.approx(-0.1)
    assert reflectance_scaling([], "02.07").offset == 0.0


def test_scaling_refuses_to_guess():
    with pytest.raises(ValueError):
        reflectance_scaling(None, None)


def test_apply_scaling_maps_nodata_to_nan():
    out = apply_scaling(np.array([0, 1100], dtype="uint16"), BASE4)
    assert np.isnan(out[0]) and out[1] == pytest.approx(0.01, abs=1e-6)


# --- the water plausibility check -----------------------------------------

def _water(red, nir, n=5000):
    return np.full(n, red, "float32"), np.full(n, nir, "float32"), np.ones(n, bool)


def test_plausibility_passes_physically_sensible_water():
    assert offset_plausibility(*_water(0.01, 0.005))["verdict"] == "pass"


def test_plausibility_catches_a_missing_offset():
    v = offset_plausibility(*_water(0.11, 0.105))
    assert v["verdict"] == "fail" and "MISSING" in v["reason"]


def test_plausibility_catches_an_offset_applied_twice():
    v = offset_plausibility(*_water(-0.09, -0.095))
    assert v["verdict"] == "fail" and "TWICE" in v["reason"]


def test_plausibility_declines_to_judge_on_too_little_water():
    assert offset_plausibility(*_water(0.01, 0.005, n=50))["verdict"] == "insufficient"


# --- grid alignment --------------------------------------------------------

def test_window_is_snapped_to_the_coarsest_band_and_contains_the_aoi():
    t = from_origin(E0, N0, 10, 10)
    w, clipped = aligned_window(N10, N10, t, CRS, INNER_BBOX)
    assert not clipped
    for v in (w.col_off, w.row_off, w.width, w.height):
        assert v % GRID_MULTIPLE == 0
    l, b, r, top = transform_bounds("EPSG:4326", CRS, *INNER_BBOX, densify_pts=21)
    # north-up, no rotation: pixel -> map by hand, avoiding affine's deprecated `*`
    wl, wt = t.c + w.col_off * t.a, t.f + w.row_off * t.e
    wr, wb = t.c + (w.col_off + w.width) * t.a, t.f + (w.row_off + w.height) * t.e
    assert wl <= l and wr >= r and wb <= b and wt >= top


def test_window_reports_when_the_aoi_runs_off_the_tile():
    t = from_origin(E0, N0, 10, 10)
    off = _bbox_utm(E0 - 2000, N0 - 3000, E0 + 2000, N0 - 1000)
    _, clipped = aligned_window(N10, N10, t, CRS, off)
    assert clipped


def test_upsample_exact_replicates_without_invention():
    a = np.array([[1, 2], [3, 4]], dtype="uint8")
    u = upsample_exact(a, 2)
    assert u.shape == (4, 4)
    assert set(np.unique(u)) == {1, 2, 3, 4}
    assert (u[:2, :2] == 1).all() and (u[2:, 2:] == 4).all()


def test_water_stretch_spends_the_range_on_water():
    rgb = np.stack([np.linspace(10, 40, 100).reshape(10, 10)] * 3)
    rgb[:, :2, :] = 250                                     # bright land rows
    water = np.ones((10, 10), bool); water[:2, :] = False
    out = water_stretch(rgb, water)
    assert out.min() >= 0 and out.max() <= 1
    assert np.ptp(out[0, 2:][water[2:]]) > 0.9             # water uses ~full range
    assert (out[:, :2, :] == 1).all()                       # land saturates


# --- end to end, through the same reader that reads https hrefs -----------

def test_stack_reads_back_true_reflectance(granule):
    s = read_aoi_stack(granule, INNER_BBOX, {b: BASE4 for b in TRUTH})
    assert s["shape"][0] % GRID_MULTIPLE == 0 and s["shape"][1] % GRID_MULTIPLE == 0
    for band, refl in TRUTH.items():
        assert s[band].shape == s["shape"]
        assert np.nanmedian(s[band]) == pytest.approx(refl, abs=1e-5)
    assert s["scl"].shape == s["shape"]


def test_scl_is_aligned_pixel_for_pixel_with_the_10m_grid(granule):
    """The cloud patch is 20 m pixels 100-109; at 10 m that is 200-219 in tile
    coordinates. Its position in the window must match exactly."""
    s = read_aoi_stack(granule, _bbox_utm(E0 + 1500, N0 - 2500, E0 + 2500, N0 - 1500),
                       {b: BASE4 for b in TRUTH})
    t = s["transform"]
    col0 = int(round((t.c - E0) / 10)); row0 = int(round((N0 - t.f) / 10))
    cloud = np.argwhere(s["scl"] == 9)
    assert cloud.size, "window should include the cloud patch"
    assert cloud[:, 0].min() + row0 == 200 and cloud[:, 0].max() + row0 == 219
    assert cloud[:, 1].min() + col0 == 200 and cloud[:, 1].max() + col0 == 219


def test_end_to_end_plausibility_catches_the_wrong_scaling(granule):
    right = read_aoi_stack(granule, INNER_BBOX, {b: BASE4 for b in TRUTH})
    wrong = read_aoi_stack(granule, INNER_BBOX, {b: BASE2 for b in TRUTH})
    water = right["scl"] == SCL_WATER
    assert offset_plausibility(right["red"], right["nir"], water)["verdict"] == "pass"
    assert offset_plausibility(wrong["red"], wrong["nir"], water)["verdict"] == "fail"
