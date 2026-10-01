"""Tests for the pure parts of scene selection.

Every assertion is against an analytically known answer or a documented
invariant. Nothing here touches the network.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone

import pytest

from sdb.stac import (
    GLINT_FACET_SEVERE_DEG,
    GLINT_FACET_WARN_DEG,
    Site,
    days_from_reference,
    filter_candidates,
    glint_flag,
    needs_boa_offset,
    score_scene,
    specular_facet_angle,
    summarise_item,
)

# --- specular geometry -----------------------------------------------------

def test_nadir_view_gives_half_the_solar_zenith():
    """At nadir the facet normal bisects sun and view, so omega = theta_s / 2."""
    for sun_zenith in (0.0, 20.0, 45.0, 70.0):
        assert specular_facet_angle(sun_zenith, 0.0, 0.0) == pytest.approx(sun_zenith / 2.0, abs=1e-9)


def test_sun_at_zenith_viewed_from_nadir_is_the_worst_case():
    """Sun overhead, sensor overhead: a flat surface reflects straight back."""
    assert specular_facet_angle(0.0, 0.0, 0.0) == pytest.approx(0.0, abs=1e-9)


def test_mirror_geometry_needs_a_flat_surface():
    """Sensor in the sun's mirror direction: a flat facet already reflects into it."""
    assert specular_facet_angle(30.0, 30.0, 180.0) == pytest.approx(0.0, abs=1e-9)


def test_sensor_on_the_sun_side_needs_retroreflection():
    """Same zenith AND azimuth means the light must come straight back, so the
    facet has to face the sun -- a large tilt, not a small one."""
    assert specular_facet_angle(30.0, 30.0, 0.0) == pytest.approx(30.0, abs=1e-9)


def _omega_reference(ts_deg, tv_deg, dphi_deg):
    """Independent restatement of the geometry, written from vectors."""
    ts, tv, dp = map(math.radians, (ts_deg, tv_deg, dphi_deg))
    s = (math.sin(ts), 0.0, math.cos(ts))
    v = (math.sin(tv) * math.cos(dp), math.sin(tv) * math.sin(dp), math.cos(tv))
    n = tuple(a + b for a, b in zip(s, v))
    mag = math.sqrt(sum(c * c for c in n))
    if mag < 1e-12:
        return 90.0
    return math.degrees(math.acos(max(-1.0, min(1.0, n[2] / mag))))


def test_matches_an_independent_derivation_off_the_principal_plane():
    """The closed form cos(2w)=... agrees only in the principal plane. This is
    the test that caught it, so it stays."""
    for ts in range(0, 86, 5):
        for tv in range(0, 61, 5):
            for dphi in range(-180, 181, 15):
                assert specular_facet_angle(ts, tv, dphi) == pytest.approx(
                    _omega_reference(ts, tv, dphi), abs=1e-9
                )


def test_facet_angle_is_symmetric_in_relative_azimuth():
    a = specular_facet_angle(40.0, 8.0, +70.0)
    b = specular_facet_angle(40.0, 8.0, -70.0)
    assert a == pytest.approx(b, abs=1e-9)


def test_facet_angle_never_leaves_its_range():
    for sz in range(0, 90, 7):
        for vz in range(0, 12, 3):
            for dphi in range(-180, 181, 45):
                w = specular_facet_angle(sz, vz, dphi)
                assert 0.0 <= w <= 90.0


def test_glint_flags_use_the_documented_thresholds():
    assert glint_flag(GLINT_FACET_SEVERE_DEG - 0.1) == "severe"
    assert glint_flag(GLINT_FACET_SEVERE_DEG + 0.1) == "watch"
    assert glint_flag(GLINT_FACET_WARN_DEG + 0.1) == "ok"


# --- date proximity --------------------------------------------------------

CAPTURES = (date(2018, 9, 8), date(2018, 9, 9))


def test_days_from_reference_picks_the_nearest_capture():
    dt = datetime(2018, 9, 12, 23, 59, tzinfo=timezone.utc)
    assert days_from_reference(dt, CAPTURES) == 3     # nearest is the 9th


def test_days_from_reference_is_zero_on_the_day():
    assert days_from_reference(datetime(2018, 9, 8, 0, 5, tzinfo=timezone.utc), CAPTURES) == 0


def test_days_from_reference_is_unsigned():
    before = days_from_reference(datetime(2018, 9, 3, tzinfo=timezone.utc), CAPTURES)
    after = days_from_reference(datetime(2018, 9, 14, tzinfo=timezone.utc), CAPTURES)
    assert before == 5 and after == 5


# --- BOA offset ------------------------------------------------------------

@pytest.mark.parametrize("baseline,expected", [
    ("02.07", False), ("03.01", False), ("04.00", True), ("05.11", True),
    (4.0, True), (None, None), ("", None), ("not-a-number", None),
])
def test_boa_offset_decision(baseline, expected):
    assert needs_boa_offset(baseline) is expected


# --- scoring ---------------------------------------------------------------

def test_score_is_bounded():
    for d in (0, 5, 30, 120):
        for c in (0.0, 50.0, 100.0):
            for f in (0.0, 12.0, 40.0):
                for s in (5.0, 45.0, 85.0):
                    assert 0.0 <= score_scene(d, c, f, s) <= 1.0


def test_closer_in_time_scores_higher_all_else_equal():
    near = score_scene(2, 10.0, 25.0, 45.0)
    far = score_scene(40, 10.0, 25.0, 45.0)
    assert near > far


def test_less_cloud_scores_higher_all_else_equal():
    assert score_scene(5, 5.0, 25.0, 45.0) > score_scene(5, 60.0, 25.0, 45.0)


def test_severe_glint_geometry_scores_lower_all_else_equal():
    assert score_scene(5, 10.0, 30.0, 45.0) > score_scene(5, 10.0, 4.0, 45.0)


def test_a_perfect_scene_scores_one():
    assert score_scene(0, 0.0, GLINT_FACET_WARN_DEG, 45.0) == pytest.approx(1.0, abs=1e-9)


# --- item summarising ------------------------------------------------------

def _props(**over):
    p = {
        "datetime": "2018-09-11T00:02:11Z",
        "eo:cloud_cover": 3.4,
        "s2:nodata_pixel_percentage": 0.0,
        "view:sun_elevation": 45.0,
        "view:sun_azimuth": 35.0,
        "s2:processing_baseline": "02.07",
        "platform": "sentinel-2a",
    }
    p.update(over)
    return p


def test_summarise_item_reports_the_decision_fields():
    r = summarise_item(_props(), "S2A_TEST", CAPTURES)
    assert r["id"] == "S2A_TEST"
    assert r["days_from_lidar"] == 2
    assert r["cloud_pct"] == 3.4
    # nadir assumed -> omega = (90 - 45) / 2
    assert r["glint_facet_deg"] == pytest.approx(22.5, abs=0.05)
    assert r["glint_flag"] == "ok"
    assert r["needs_boa_offset"] is False
    assert r["view_zenith_assumed_nadir"] is True


def test_summarise_item_survives_missing_optional_metadata():
    p = _props()
    del p["view:sun_elevation"], p["view:sun_azimuth"], p["s2:processing_baseline"]
    r = summarise_item(p, "S2B_SPARSE", CAPTURES)
    assert r["glint_flag"] == "unknown"
    assert r["needs_boa_offset"] is None
    assert 0.0 <= r["score"] <= 1.0


def test_high_sun_is_flagged_as_glint_risk_not_rewarded():
    """A near-overhead sun is the dangerous case, not the good one."""
    low = summarise_item(_props(**{"view:sun_elevation": 45.0}), "a", CAPTURES)
    high = summarise_item(_props(**{"view:sun_elevation": 84.0}), "b", CAPTURES)
    assert high["glint_facet_deg"] < low["glint_facet_deg"]
    assert high["glint_flag"] in ("watch", "severe")


# --- filtering -------------------------------------------------------------

def test_filter_drops_cloud_and_nodata_then_sorts_by_score():
    rows = [
        summarise_item(_props(**{"eo:cloud_cover": 90.0}), "cloudy", CAPTURES),
        summarise_item(_props(**{"s2:nodata_pixel_percentage": 40.0}), "edge", CAPTURES),
        summarise_item(_props(**{"eo:cloud_cover": 1.0}), "good", CAPTURES),
        summarise_item(_props(**{"eo:cloud_cover": 20.0, "datetime": "2018-10-20T00:02:11Z"}), "late", CAPTURES),
    ]
    kept = filter_candidates(rows, max_cloud=40, max_nodata=5)
    assert [r["id"] for r in kept] == ["good", "late"]
    assert kept[0]["score"] >= kept[1]["score"]


# --- site validation -------------------------------------------------------

def test_site_rejects_a_transposed_bbox():
    with pytest.raises(ValueError):
        Site("x", "X", (150.8, -34.9, 150.6, -35.1), (date(2018, 9, 8),))


def test_site_rejects_missing_capture_dates():
    with pytest.raises(ValueError):
        Site("x", "X", (150.6, -35.1, 150.8, -34.9), ())


def test_jervis_bay_bbox_matches_the_measured_block():
    """Guards against the indicative bbox creeping back in."""
    s = Site("jervis_bay", "Jervis Bay", (150.6607, -35.1504, 150.8083, -34.9735), CAPTURES)
    w, so, e, n = s.bbox
    assert (e - w) * 111.0 * math.cos(math.radians(-35.06)) == pytest.approx(13.5, abs=1.0)  # km
    assert (n - so) * 111.0 == pytest.approx(19.7, abs=1.0)                                   # km


# --- MGRS tile parsing -----------------------------------------------------

from sdb.stac import (  # noqa: E402
    MIN_AOI_COVERAGE_PCT,
    aoi_coverage_pct,
    dedupe_acquisitions,
    mgrs_tile,
)

JB_BBOX = (150.6607, -35.1504, 150.8083, -34.9735)


@pytest.mark.parametrize("props,expected", [
    ({"grid:code": "MGRS-56HKG"}, "56HKG"),
    ({"grid:code": "mgrs-56hlg"}, "56HLG"),
    ({"s2:mgrs_tile": "56HKG"}, "56HKG"),
    ({"mgrs:utm_zone": 56, "mgrs:latitude_band": "H", "mgrs:grid_square": "KG"}, "56HKG"),
    ({"mgrs:utm_zone": 5, "mgrs:latitude_band": "H", "mgrs:grid_square": "KG"}, "05HKG"),
    ({}, None),
])
def test_mgrs_tile_reads_every_spelling(props, expected):
    """The empty-column bug: reading only one key hides a two-tile AOI."""
    assert mgrs_tile(props) == expected


# --- AOI coverage ----------------------------------------------------------

def _poly(w, s, e, n):
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def test_footprint_enclosing_the_aoi_covers_all_of_it():
    assert aoi_coverage_pct(_poly(150.0, -36.0, 151.5, -34.0), JB_BBOX) == pytest.approx(100.0, abs=1e-6)


def test_footprint_missing_the_aoi_covers_none_of_it():
    assert aoi_coverage_pct(_poly(151.5, -36.0, 152.0, -34.0), JB_BBOX) == pytest.approx(0.0, abs=1e-9)


def test_half_the_aoi_reads_as_half():
    mid = (JB_BBOX[0] + JB_BBOX[2]) / 2
    assert aoi_coverage_pct(_poly(mid, -36.0, 152.0, -34.0), JB_BBOX) == pytest.approx(50.0, abs=1e-6)


def test_missing_geometry_is_nan_not_zero():
    """Unknown coverage must not masquerade as no coverage."""
    assert aoi_coverage_pct(None, JB_BBOX) != aoi_coverage_pct(None, JB_BBOX)  # NaN


def test_partial_coverage_is_rejected_not_merely_penalised():
    good = summarise_item(_props(), "full", CAPTURES,
                          item_geometry=_poly(150.0, -36.0, 151.5, -34.0), aoi_bbox=JB_BBOX)
    part = summarise_item(_props(), "sliver", CAPTURES,
                          item_geometry=_poly(150.79, -36.0, 152.0, -34.0), aoi_bbox=JB_BBOX)
    assert part["score"] == good["score"]          # scoring cannot see coverage
    kept = filter_candidates([good, part], max_cloud=40, max_nodata=5,
                             min_coverage=MIN_AOI_COVERAGE_PCT)
    assert [r["id"] for r in kept] == ["full"]     # the filter must


# --- deduplication ---------------------------------------------------------

def _row(tile, day, baseline, ident):
    p = _props(**{"datetime": f"{day}T00:02:11Z", "s2:processing_baseline": baseline,
                  "grid:code": f"MGRS-{tile}"})
    return summarise_item(p, ident, CAPTURES, item_geometry=_poly(150.0, -36.0, 151.5, -34.0),
                          aoi_bbox=JB_BBOX)


def test_same_acquisition_two_baselines_collapses_to_one():
    rows = [_row("56HLG", "2018-09-08", "00.01", "v0"),
            _row("56HLG", "2018-09-08", "05.00", "v1")]
    out = dedupe_acquisitions(rows)
    assert len(out) == 1
    assert out[0]["id"] == "v1"            # highest baseline by default
    assert out[0]["n_versions"] == 2


def test_dedupe_can_prefer_the_older_processing():
    rows = [_row("56HLG", "2018-09-08", "00.01", "v0"),
            _row("56HLG", "2018-09-08", "05.00", "v1")]
    out = dedupe_acquisitions(rows, prefer="lowest_baseline")
    assert out[0]["id"] == "v0"


def test_dedupe_keeps_different_tiles_and_different_dates_apart():
    rows = [_row("56HLG", "2018-09-08", "05.00", "a"),
            _row("56HKG", "2018-09-08", "05.00", "b"),
            _row("56HLG", "2018-09-13", "05.00", "c")]
    assert len(dedupe_acquisitions(rows)) == 3


def test_dedupe_records_how_many_versions_were_seen():
    rows = [_row("56HKG", "2018-09-12", b, f"v{i}") for i, b in enumerate(("00.01", "05.00"))]
    assert dedupe_acquisitions(rows)[0]["n_versions"] == 2


# --- rejection trail -------------------------------------------------------

from sdb.stac import classify_candidates  # noqa: E402


def test_rejected_rows_are_kept_with_a_reason():
    good = summarise_item(_props(), "full", CAPTURES,
                          item_geometry=_poly(150.0, -36.0, 151.5, -34.0), aoi_bbox=JB_BBOX)
    part = summarise_item(_props(), "sliver", CAPTURES,
                          item_geometry=_poly(150.79, -36.0, 152.0, -34.0), aoi_bbox=JB_BBOX)
    cloudy = summarise_item(_props(**{"eo:cloud_cover": 80.0}), "cloudy", CAPTURES,
                            item_geometry=_poly(150.0, -36.0, 151.5, -34.0), aoi_bbox=JB_BBOX)
    out = classify_candidates([part, cloudy, good], max_cloud=40, max_nodata=5)
    status = {r["id"]: r["status"] for r in out}
    assert status["full"] == "kept"
    assert status["sliver"].startswith("rejected: covers")
    assert status["cloudy"].startswith("rejected: scene cloud")
    assert out[0]["id"] == "full"          # kept rows lead the table


# --- scene nodata is a proxy, coverage decides --------------------------------

from sdb.stac import rejection_tally  # noqa: E402


def test_full_coverage_beats_scene_nodata():
    """Batemans Bay 2018-08-18: the AOI was whole, the tile was cut elsewhere."""
    whole = summarise_item(_props(**{"s2:nodata_pixel_percentage": 15.2}), "edge_tile", CAPTURES,
                           item_geometry=_poly(150.0, -36.0, 151.5, -34.0), aoi_bbox=JB_BBOX)
    assert whole["aoi_coverage_pct"] == pytest.approx(100.0)
    out = classify_candidates([whole], max_cloud=40, max_nodata=5)
    assert out[0]["status"] == "kept"


def test_scene_nodata_still_applies_without_a_footprint():
    blind = summarise_item(_props(**{"s2:nodata_pixel_percentage": 40.0}), "no_geom", CAPTURES)
    out = classify_candidates([blind], max_cloud=40, max_nodata=5)
    assert out[0]["status"].startswith("rejected: nodata")


def test_rejection_tally_counts_every_outcome():
    full = _poly(150.0, -36.0, 151.5, -34.0)
    rows = [
        summarise_item(_props(), "good", CAPTURES, item_geometry=full, aoi_bbox=JB_BBOX),
        summarise_item(_props(), "sliver", CAPTURES,
                       item_geometry=_poly(150.79, -36.0, 152.0, -34.0), aoi_bbox=JB_BBOX),
        summarise_item(_props(**{"eo:cloud_cover": 80.0}), "cloudy", CAPTURES,
                       item_geometry=full, aoi_bbox=JB_BBOX),
        summarise_item(_props(**{"s2:nodata_pixel_percentage": 40.0}), "blind", CAPTURES),
    ]
    tally = rejection_tally(classify_candidates(rows, max_cloud=40, max_nodata=5))
    assert tally == {"kept": 1, "coverage": 1, "cloud": 1, "nodata": 1}


def test_rejection_tally_refuses_an_unknown_status():
    with pytest.raises(ValueError):
        rejection_tally([{"status": "rejected: something new"}])
