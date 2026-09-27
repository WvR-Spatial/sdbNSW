"""Tests for the wind-aware glint index.

Physics tests check known answers and invariants. One test encodes the Jervis
Bay observation (three scenes, ranked by eye) -- it guards the implementation
against regressions; it does not validate the model.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone

import pytest

from sdb.glint import (
    CM_VALID_WIND_MS,
    N_WATER,
    attach_glint,
    cox_munk_pdf,
    cox_munk_variances,
    fetch_era5_wind,
    fresnel_reflectance,
    glint_reflectance,
    glint_sigma,
    nearest_wind,
    outside_fit_range,
    parse_open_meteo,
    required_slope,
    specular_facet,
    wind_at_cm_height,
    wind_axis_angle,
    window_dates,
)
from sdb.stac import specular_facet_angle

# --- geometry --------------------------------------------------------------

def test_nadir_facet_tilts_toward_the_sun_by_half_the_zenith():
    for sz in (10.0, 30.0, 48.5, 70.0):
        tilt, az, inc = specular_facet(sz, 0.0, 0.0)
        assert tilt == pytest.approx(sz / 2, abs=1e-9)
        assert inc == pytest.approx(sz / 2, abs=1e-9)
        assert az == pytest.approx(0.0, abs=1e-9)


def test_mirror_geometry_is_a_flat_facet_at_the_view_angle():
    tilt, _, inc = specular_facet(30.0, 30.0, 180.0)
    assert tilt == pytest.approx(0.0, abs=1e-9)
    assert inc == pytest.approx(30.0, abs=1e-9)


def test_stac_uses_the_same_geometry():
    """One implementation, two callers: they must never drift apart."""
    for ts, tv, dp in [(20, 0, 0), (40, 8, 70), (55, 11, -120), (30, 30, 180)]:
        assert specular_facet_angle(ts, tv, dp) == pytest.approx(specular_facet(ts, tv, dp)[0])


@pytest.mark.parametrize("sun_az,wind_from,expected", [
    (38.0, 300.0, 82.0),     # 7 Sep 2018: wind nearly across the sun line
    (38.8, 29.0, 9.8),       # 12 Sep: wind axis almost through the sun
    (39.6, 17.0, 22.6),      # 17 Sep
    (38.0, 218.0, 0.0),      # opposite direction, same axis
    (0.0, 90.0, 90.0),
])
def test_wind_axis_angle(sun_az, wind_from, expected):
    assert wind_axis_angle(sun_az, wind_from) == pytest.approx(expected, abs=1e-9)


def test_wind_axis_angle_stays_in_range():
    for s in range(0, 360, 17):
        for w in range(0, 360, 13):
            assert 0.0 <= wind_axis_angle(s, w) <= 90.0


# --- Fresnel ---------------------------------------------------------------

def test_fresnel_at_normal_incidence():
    assert fresnel_reflectance(0.0) == pytest.approx(((N_WATER - 1) / (N_WATER + 1)) ** 2, rel=1e-12)


def test_fresnel_rises_to_one_at_grazing():
    assert fresnel_reflectance(89.99) > 0.99
    assert fresnel_reflectance(20.0) < fresnel_reflectance(60.0) < fresnel_reflectance(85.0)


# --- Cox-Munk --------------------------------------------------------------

def test_height_conversion_is_small_and_upward():
    assert 1.0 < wind_at_cm_height(5.0) / 5.0 < 1.05


def test_directional_fits_agree_with_the_separate_isotropic_fit():
    """Cox-Munk fitted upwind, crosswind and total slope variance independently.
    The directional pair must reproduce the total to within 1%."""
    for u in (1.0, 5.0, 10.0, 14.0):
        up, cross = cox_munk_variances(u)
        assert up + cross == pytest.approx(0.003 + 5.12e-3 * wind_at_cm_height(u), rel=0.01)


def test_pdf_integrates_to_one():
    u, h, lim = 7.0, 0.005, 1.2
    n = int(2 * lim / h)
    total = sum(cox_munk_pdf(-lim + (i + .5) * h, -lim + (j + .5) * h, u)
                for i in range(n) for j in range(n)) * h * h
    assert total == pytest.approx(1.0, abs=1e-3)


def test_steep_slopes_are_likelier_along_the_wind_than_across_it():
    assert cox_munk_pdf(0.4, 0.0, 8.0) > cox_munk_pdf(0.0, 0.4, 8.0)


# --- glint -----------------------------------------------------------------

def test_glint_is_worse_when_the_wind_axis_points_at_the_sun():
    aligned = glint_reflectance(48.0, 38.0, 4.0, 38.0)
    across = glint_reflectance(48.0, 38.0, 4.0, 128.0)
    assert aligned > 3 * across


def test_more_wind_means_more_glint_for_steep_facets_and_less_for_flat_ones():
    """Wind spreads the glitter pattern: it lights steep facets and dims the
    mirror spot. Both halves must hold or the model is wired backwards."""
    assert glint_reflectance(50.0, 0.0, 8.0, 90.0) > glint_reflectance(50.0, 0.0, 3.0, 90.0)
    assert glint_reflectance(4.0, 0.0, 8.0, 90.0) < glint_reflectance(4.0, 0.0, 3.0, 90.0)


# --- the reported index ---------------------------------------------------

def test_sigma_is_the_exponent_of_the_slope_density():
    """The reported index and the model must be the same thing:
    p = exp(-sigma^2 / 2) / (2 pi sqrt(var_up var_cross))."""
    for geom in [(48.0, 38.0, 4.0, 300.0), (40.0, 10.0, 7.5, 25.0), (55.0, 50.0, 2.0, 140.0)]:
        sz, sa, u, wf = geom
        zu, zc, _, _ = required_slope(sz, sa, wf)
        su2, sc2 = cox_munk_variances(u)
        sig = glint_sigma(*geom)
        expected = math.exp(-0.5 * sig ** 2) / (2 * math.pi * math.sqrt(su2 * sc2))
        assert cox_munk_pdf(zu, zc, u) == pytest.approx(expected, rel=1e-12)


def test_sigma_falls_as_wind_rises_for_a_steep_facet():
    s = [glint_sigma(48.0, 38.0, u, 300.0) for u in (1.5, 3.0, 6.0, 10.0)]
    assert s == sorted(s, reverse=True)


def test_sigma_is_lower_when_the_wind_axis_points_at_the_sun():
    assert glint_sigma(48.0, 38.0, 4.0, 38.0) < glint_sigma(48.0, 38.0, 4.0, 128.0)


def test_calm_is_floored_not_divided_by():
    """A 0.0 m/s reanalysis value must not crash, and sub-1 m/s winds are
    evaluated at the Cox-Munk lower bound (so sigma is a lower bound)."""
    assert glint_sigma(48.0, 38.0, 0.0, 300.0) == glint_sigma(48.0, 38.0, 1.0, 300.0)
    assert glint_reflectance(48.0, 38.0, 0.0, 300.0) >= 0.0


def test_twelve_september_is_the_most_glint_prone_under_either_wind_pull():
    """The one discriminating observation: 12 Sep showed glint streaks, 7 and
    17 Sep did not. Two wind pulls disagree on speed (see PROJECT_BRIEF); the
    ranking of 12 Sep must hold under both. The order of 7 vs 17 Sep is NOT
    tested -- both were clean, so the eye cannot separate them."""
    geom = {"0907": (90 - 41.5, 38.0), "0912": (90 - 43.3, 38.8), "0917": (90 - 45.2, 39.6)}
    pulls = {"first":  {"0907": (3.58, 300), "0912": (3.76, 29), "0917": (2.40, 17)},
             "stac":   {"0907": (0.86, 306), "0912": (4.37, 16), "0917": (1.87, 16)}}
    for wind in pulls.values():
        sig = {k: glint_sigma(*geom[k], *wind[k]) for k in geom}
        assert min(sig, key=sig.get) == "0912"


# --- wind series -----------------------------------------------------------

def _payload(times, speeds, dirs, unit="m/s"):
    return {"latitude": -35.0, "longitude": 150.75,
            "hourly_units": {"time": "iso8601", "wind_speed_10m": unit,
                             "wind_direction_10m": "°"},
            "hourly": {"time": times, "wind_speed_10m": speeds, "wind_direction_10m": dirs}}


def test_parse_reads_utc_hours():
    s = parse_open_meteo(_payload(["2018-09-07T00:00", "2018-09-07T01:00"], [3.58, 4.0], [300, 310]))
    assert s[datetime(2018, 9, 7, 0, tzinfo=timezone.utc)] == (3.58, 300.0)


def test_parse_refuses_the_default_kmh_unit():
    """The API defaults to km/h; a dropped parameter must fail, not pass as 3.6x wind."""
    with pytest.raises(ValueError):
        parse_open_meteo(_payload(["2018-09-07T00:00"], [12.9], [300], unit="km/h"))


def test_parse_skips_missing_hours():
    s = parse_open_meteo(_payload(["2018-09-07T00:00", "2018-09-07T01:00"], [None, 4.0], [300, 310]))
    assert len(s) == 1


def test_nearest_wind_matches_an_overpass_to_its_hour():
    s = parse_open_meteo(_payload(["2018-09-12T00:00", "2018-09-12T01:00"], [3.76, 5.0], [29, 40]))
    assert nearest_wind(s, datetime(2018, 9, 12, 0, 6, tzinfo=timezone.utc)) == (3.76, 29.0)
    assert nearest_wind(s, datetime(2018, 9, 12, 0, 40, tzinfo=timezone.utc)) == (5.0, 40.0)


def test_nearest_wind_returns_none_rather_than_a_distant_value():
    s = parse_open_meteo(_payload(["2018-09-12T00:00"], [3.76], [29]))
    assert nearest_wind(s, datetime(2018, 9, 12, 3, 0, tzinfo=timezone.utc)) is None
    assert nearest_wind({}, datetime(2018, 9, 12, tzinfo=timezone.utc)) is None


def test_window_reaches_the_next_day_for_late_overpasses():
    assert window_dates(["2018-09-07 00:02", "2018-09-17 23:50"]) == (date(2018, 9, 7), date(2018, 9, 18))


# --- attaching to candidate rows -------------------------------------------

def _row(ident, when, elev, az):
    return {"id": ident, "datetime_utc": when, "sun_elev_deg": elev, "sun_az_deg": az,
            "view_zen_deg": 0.0, "view_rel_az_deg": 0.0}


JB_ROWS = [_row("0907", "2018-09-07 00:02", 41.5, 38.0),
           _row("0912", "2018-09-12 00:06", 43.3, 38.8),
           _row("0917", "2018-09-17 00:02", 45.2, 39.6)]
JB_WIND = parse_open_meteo(_payload(
    ["2018-09-07T00:00", "2018-09-12T00:00", "2018-09-17T00:00"],
    [3.58, 3.76, 2.40], [300, 29, 17]))


def test_attach_adds_wind_and_sigma():
    out = {r["id"]: r for r in attach_glint(JB_ROWS, JB_WIND)}
    assert out["0907"]["wind_ms"] == 3.58 and out["0907"]["wind_from_deg"] == 300
    assert out["0907"]["sun_wind_axis_deg"] == pytest.approx(82.0)
    assert out["0912"]["glint_sigma"] == min(r["glint_sigma"] for r in out.values())


def test_attach_leaves_gaps_empty_instead_of_guessing():
    out = attach_glint(JB_ROWS + [_row("nowind", "2018-10-01 00:02", 50.0, 40.0),
                                  _row("nogeom", "2018-09-07 00:02", float("nan"), 38.0)],
                       JB_WIND)
    by = {r["id"]: r for r in out}
    assert by["nowind"]["wind_ms"] is None and by["nowind"]["glint_sigma"] is None
    assert by["nogeom"]["wind_ms"] == 3.58           # wind is still reported...
    assert by["nogeom"]["glint_sigma"] is None       # ...but no geometry, no index


def test_attach_with_no_wind_at_all_changes_nothing_but_adds_empty_columns():
    out = attach_glint(JB_ROWS, {})
    assert all(r["glint_sigma"] is None and r["wind_ms"] is None for r in out)


def test_flags_winds_outside_the_cox_munk_range():
    rows = [{"id": "a", "wind_ms": 0.4}, {"id": "b", "wind_ms": 6.0},
            {"id": "c", "wind_ms": 18.0}, {"id": "d", "wind_ms": None}]
    assert outside_fit_range(rows) == {"below": ["a"], "above": ["c"]}
    assert CM_VALID_WIND_MS == (1.0, 14.0)


# --- the network function, without the network -----------------------------

class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


def test_fetch_asks_for_era5_in_metres_per_second():
    seen = {}

    def fake_get(url, params, timeout):
        seen.update(params)
        return _Resp(_payload(["2018-09-07T00:00"], [3.58], [300]))

    series, cell = fetch_era5_wind(-35.06, 150.73, date(2018, 9, 7), date(2018, 9, 8), get=fake_get)
    assert seen["wind_speed_unit"] == "ms" and seen["models"] == "era5"
    assert seen["hourly"] == "wind_speed_10m,wind_direction_10m"
    assert cell == (-35.0, 150.75)
    assert len(series) == 1
