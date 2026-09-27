"""Wind-aware sun-glint index for Sentinel-2 scene selection.

`stac.glint_facet_deg` is geometry only: how steep a wave facet must be to
reflect the sun into the sensor. Whether facets that steep exist depends on the
sea surface, which depends on wind. This module adds that half using the
Cox & Munk (1954) slope distribution, driven by ERA5 10 m wind.

Speed and direction both matter. Cox-Munk slopes are anisotropic: in real
wind they are steeper along the wind axis than across it. Glint at nadir needs
facets tilted toward the sun, so the same wind produces more glint when the
wind axis lines up with the solar azimuth, and more wind produces more glint
whenever the required facet is steep.

The reported index is `glint_sigma`: how many standard deviations of the
Cox-Munk slope distribution the glinting facet sits out. Lower means more
glint-prone. Glint probability scales as exp(-sigma^2 / 2), so a step from 5 to
4 sigma is ~30x and from 4 to 3 another ~30x. At Jervis Bay the one scene with
visible glint streaks (12 Sep 2018) sat at 3.7-3.9 sigma; the clean scenes at
4.5-6.4. That is one discriminating observation, not a calibration.

What the index is and is not.
  * A RANKING index. It is reported in sigma rather than as a reflectance or a
    ratio because the Gaussian tail is least reliable exactly where glint
    samples it: near calm the modelled reflectance falls to ~1e-16, and ratios
    of such numbers run to millions without meaning anything.
  * Driven by one 0.25 deg (~25 km) ERA5 cell at the nearest hour. Local gusts,
    wind slicks, fetch-limited bay seas and swell are all invisible to it.
  * Only as good as the wind. Around a transition (the morning offshore flow
    dying, a sea breeze arriving) sources disagree several-fold: at the 7 Sep
    2018 overpass ERA5 gave 0.86 m/s and ECMWF IFS 9 km 3.58 m/s, moving sigma
    from 6.4 to 4.5. Scenes closer than that spread are indistinguishable.
    scripts/check_wind_sources.py compares sources for any such case.
  * Meaningful while the glinting facet is steep (glint_facet_deg >~ 10). For
    near-flat facets the sun's mirror image is in view and sigma is ~0 in any
    wind -- the geometry flag already says "severe" there.
  * Not a glint correction. Never subtract it from imagery.

Network access is confined to `fetch_era5_wind`. Everything else is pure and
tested in tests/test_glint.py.

References
  Cox, C. & Munk, W. (1954) Measurement of the roughness of the sea surface
    from photographs of the sun's glitter. J. Opt. Soc. Am. 44(11), 838-850.
  Hersbach, H. et al. (2020) The ERA5 global reanalysis. Q. J. R. Meteorol.
    Soc. 146, 1999-2049.  Accessed via Open-Meteo (open-meteo.com), CC BY 4.0.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping, Sequence

# --------------------------------------------------------------------------
# Constants, with reasons
# --------------------------------------------------------------------------

#: Refractive index of sea water in the visible/NIR. Varies by <1% across
#: salinity, temperature and the S2 bands used; immaterial for a ranking index.
N_WATER = 1.34

#: Cox-Munk regressed slope variance on wind measured at 12.5 m (41 ft), not
#: 10 m. Converted with a neutral log profile over roughness length Z0_M; the
#: factor is ~1.02 and is kept so the published coefficients are used as
#: published.
CM_REF_HEIGHT_M = 12.5
Z0_M = 1e-4

#: Wind range Cox-Munk actually observed. Outside it the linear fits are
#: extrapolation. Below ~2.4 m/s the fits even give crosswind variance larger
#: than upwind, which is a fitting artefact, not physics. Below the lower bound
#: the model is evaluated AT the bound: the real surface was smoother, so the
#: reported glint_sigma is then a lower bound (glint was, if anything, less
#: likely). It also keeps a 0.0 m/s reanalysis value from dividing by zero.
CM_VALID_WIND_MS = (1.0, 14.0)

#: Largest gap (minutes) between scene time and the nearest hourly wind value.
#: ERA5 is hourly; beyond half an hour something has gone wrong with the match.
MAX_WIND_GAP_MIN = 30

OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
WIND_SOURCE = "ERA5 (Hersbach et al. 2020) via Open-Meteo, CC BY 4.0"


# --------------------------------------------------------------------------
# Specular geometry
# --------------------------------------------------------------------------


def specular_facet(sun_zenith_deg: float, view_zenith_deg: float = 0.0,
                   relative_azimuth_deg: float = 0.0) -> tuple[float, float, float]:
    """Facet that reflects the sun into the sensor.

    Returns (tilt, normal_azimuth, incidence), all in degrees:
      tilt            angle of the facet normal from vertical
      normal_azimuth  azimuth of the tilt, relative to the SOLAR azimuth,
                      clockwise positive (0 = tilted toward the sun)
      incidence       angle of incidence of sunlight on that facet

    Unit vectors s (to sun) and v (to sensor) are written in a frame whose x
    axis points along the solar azimuth. The facet normal bisects them, so it is
    parallel to s + v, and since the angle between s and v is twice the
    incidence angle, |s + v| = 2 cos(incidence).
    `relative_azimuth_deg` is sensor azimuth minus solar azimuth.
    """
    ts, tv = math.radians(sun_zenith_deg), math.radians(view_zenith_deg)
    dphi = math.radians(relative_azimuth_deg)

    nx = math.sin(ts) + math.sin(tv) * math.cos(dphi)
    ny = math.sin(tv) * math.sin(dphi)
    nz = math.cos(ts) + math.cos(tv)
    mag = math.sqrt(nx * nx + ny * ny + nz * nz)
    if mag < 1e-12:          # sun and sensor exactly opposed on the horizon
        return 90.0, 0.0, 90.0

    tilt = math.degrees(math.acos(max(-1.0, min(1.0, nz / mag))))
    azimuth = math.degrees(math.atan2(ny, nx)) if (nx or ny) else 0.0
    incidence = math.degrees(math.acos(max(-1.0, min(1.0, mag / 2.0))))
    return tilt, azimuth, incidence


def wind_axis_angle(sun_azimuth_deg: float, wind_from_deg: float) -> float:
    """Angle in [0, 90] between the solar azimuth and the wind AXIS.

    The Gaussian slope model is symmetric along the axis, so wind from 29 deg
    and wind from 209 deg are the same case. 0 is the bad case (wind axis
    through the sun), 90 the good one.
    """
    return abs((sun_azimuth_deg - wind_from_deg + 90.0) % 180.0 - 90.0)


# --------------------------------------------------------------------------
# Sea surface and reflection
# --------------------------------------------------------------------------


def fresnel_reflectance(incidence_deg: float, n: float = N_WATER) -> float:
    """Fresnel reflectance of unpolarised light, air to water."""
    i = math.radians(incidence_deg)
    ci = math.cos(i)
    st = math.sin(i) / n
    ct = math.sqrt(max(0.0, 1.0 - st * st))
    rs = (ci - n * ct) / (ci + n * ct)
    rp = (n * ci - ct) / (n * ci + ct)
    return 0.5 * (rs * rs + rp * rp)


def wind_at_cm_height(u10_ms: float) -> float:
    """10 m wind converted to the 12.5 m height Cox-Munk regressed against."""
    return u10_ms * math.log(CM_REF_HEIGHT_M / Z0_M) / math.log(10.0 / Z0_M)


def cox_munk_variances(u10_ms: float) -> tuple[float, float]:
    """(upwind, crosswind) slope variances, Cox & Munk (1954) clean surface.

    Their sum, 0.003 + 5.08e-3 U, agrees to within 1% with the isotropic
    mean-square slope Cox-Munk fitted separately (0.003 + 5.12e-3 U). The two
    are independent regressions, so exact equality is not expected.
    """
    u = wind_at_cm_height(max(0.0, u10_ms))
    return 3.16e-3 * u, 0.003 + 1.92e-3 * u


def cox_munk_pdf(slope_upwind: float, slope_crosswind: float, u10_ms: float) -> float:
    """Gaussian probability density of surface slope components.

    Cox-Munk also fitted Gram-Charlier skewness/peakedness terms. They are
    omitted: they barely move the core and are unreliable in the far tail
    where glint lives -- the same reason the output is used only for ranking.
    """
    su2, sc2 = cox_munk_variances(u10_ms)
    q = slope_upwind ** 2 / su2 + slope_crosswind ** 2 / sc2
    return math.exp(-0.5 * q) / (2.0 * math.pi * math.sqrt(su2 * sc2))


def model_wind(wind_ms: float) -> float:
    """Wind the slope model is evaluated at: floored at the Cox-Munk lower bound."""
    return max(float(wind_ms), CM_VALID_WIND_MS[0])


def required_slope(sun_zenith_deg: float, sun_azimuth_deg: float, wind_from_deg: float, *,
                   view_zenith_deg: float = 0.0,
                   relative_azimuth_deg: float = 0.0) -> tuple[float, float, float, float]:
    """Slope of the glinting facet resolved along and across the wind axis.

    Returns (slope_upwind, slope_crosswind, tilt_deg, incidence_deg).
    """
    tilt, normal_az, incidence = specular_facet(sun_zenith_deg, view_zenith_deg,
                                                relative_azimuth_deg)
    slope = math.tan(math.radians(tilt))
    # Direction of the facet tilt relative to the wind axis. Both angles are
    # clockwise from the solar azimuth, so the difference is frame-free.
    off_axis = math.radians(normal_az - (wind_from_deg - sun_azimuth_deg))
    return slope * math.cos(off_axis), slope * math.sin(off_axis), tilt, incidence


def glint_sigma(sun_zenith_deg: float, sun_azimuth_deg: float,
                wind_ms: float, wind_from_deg: float, *,
                view_zenith_deg: float = 0.0,
                relative_azimuth_deg: float = 0.0) -> float:
    """How far out in the Cox-Munk slope distribution the glinting facet lies.

    The Mahalanobis distance of the required slope under the anisotropic
    Gaussian: sqrt(zu^2/var_up + zc^2/var_cross). Lower = more glint-prone.
    This is the quantity scenes are ranked on.
    """
    zu, zc, _, _ = required_slope(sun_zenith_deg, sun_azimuth_deg, wind_from_deg,
                                  view_zenith_deg=view_zenith_deg,
                                  relative_azimuth_deg=relative_azimuth_deg)
    su2, sc2 = cox_munk_variances(model_wind(wind_ms))
    return math.sqrt(zu * zu / su2 + zc * zc / sc2)


def glint_reflectance(sun_zenith_deg: float, sun_azimuth_deg: float,
                      wind_ms: float, wind_from_deg: float, *,
                      view_zenith_deg: float = 0.0,
                      relative_azimuth_deg: float = 0.0) -> float:
    """Modelled sun-glint reflectance (Cox & Munk).

        rho_g = pi * R(incidence) * p(zu, zc) / (4 cos ts cos tv cos^4 tilt)

    The full model, kept for physics checks. Not reported: see the module
    docstring for why sigma is the reported index.
    """
    zu, zc, tilt, incidence = required_slope(sun_zenith_deg, sun_azimuth_deg, wind_from_deg,
                                             view_zenith_deg=view_zenith_deg,
                                             relative_azimuth_deg=relative_azimuth_deg)
    p = cox_munk_pdf(zu, zc, model_wind(wind_ms))
    denom = (4.0 * math.cos(math.radians(sun_zenith_deg))
             * math.cos(math.radians(view_zenith_deg))
             * math.cos(math.radians(tilt)) ** 4)
    return math.pi * fresnel_reflectance(incidence) * p / denom


# --------------------------------------------------------------------------
# Wind series handling (pure)
# --------------------------------------------------------------------------

WindSeries = dict[datetime, tuple[float, float]]


def parse_open_meteo(payload: Mapping[str, Any]) -> WindSeries:
    """Open-Meteo hourly JSON -> {utc datetime: (speed m/s, from deg)}.

    Refuses anything not in m/s. The API's default unit is km/h, so a dropped or
    misspelled unit parameter would otherwise pass silently as 3.6x the wind.
    Hours with a missing value are skipped rather than filled.
    """
    units = payload.get("hourly_units", {})
    if units.get("wind_speed_10m") != "m/s":
        raise ValueError(f"wind speed unit is {units.get('wind_speed_10m')!r}, expected 'm/s'")
    h = payload["hourly"]
    out: WindSeries = {}
    for t, spd, dirn in zip(h["time"], h["wind_speed_10m"], h["wind_direction_10m"]):
        if spd is None or dirn is None:
            continue
        ts = datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
        out[ts] = (float(spd), float(dirn))
    return out


def nearest_wind(series: WindSeries, when: datetime,
                 max_gap_min: float = MAX_WIND_GAP_MIN) -> tuple[float, float] | None:
    """Wind at the hour nearest `when`, or None if nothing within the gap."""
    if not series:
        return None
    when = when.astimezone(timezone.utc) if when.tzinfo else when.replace(tzinfo=timezone.utc)
    hour = (when + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
    if hour in series and abs((hour - when).total_seconds()) <= max_gap_min * 60:
        return series[hour]
    return None


def attach_glint(rows: Iterable[dict[str, Any]], series: WindSeries) -> list[dict[str, Any]]:
    """Add wind and the Cox-Munk glint index to scene rows.

    Adds: wind_ms, wind_from_deg, sun_wind_axis_deg, glint_sigma. Rows without
    wind or geometry get None, never a guess.

    Expects the row fields written by stac.summarise_item.
    """
    out = []
    for r in rows:
        r = dict(r, wind_ms=None, wind_from_deg=None, sun_wind_axis_deg=None, glint_sigma=None)
        when = datetime.strptime(r["datetime_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        w = nearest_wind(series, when)
        if w is not None:
            spd, dirn = w
            r.update(wind_ms=round(spd, 2), wind_from_deg=round(dirn))
            elev, az = r.get("sun_elev_deg"), r.get("sun_az_deg")
            if _finite(elev) and _finite(az):
                sig = glint_sigma(90.0 - elev, az, spd, dirn,
                                  view_zenith_deg=r.get("view_zen_deg") or 0.0,
                                  relative_azimuth_deg=r.get("view_rel_az_deg") or 0.0)
                r.update(sun_wind_axis_deg=round(wind_axis_angle(az, dirn), 1),
                         glint_sigma=round(sig, 1))
        out.append(r)
    return out


def outside_fit_range(rows: Iterable[dict[str, Any]]) -> dict[str, list[str]]:
    """Ids of rows whose wind lies below / above the range Cox-Munk observed."""
    lo, hi = CM_VALID_WIND_MS
    rows = [r for r in rows if r.get("wind_ms") is not None]
    return {"below": [r["id"] for r in rows if r["wind_ms"] < lo],
            "above": [r["id"] for r in rows if r["wind_ms"] > hi]}


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and x == x and abs(x) != float("inf")


# --------------------------------------------------------------------------
# The only function that touches the network
# --------------------------------------------------------------------------


def fetch_era5_wind(lat: float, lon: float, start: date, end: date, *,
                    timeout: float = 30.0,
                    get: Callable[..., Any] | None = None) -> tuple[WindSeries, tuple[float, float]]:
    """Hourly ERA5 10 m wind for one point, one request for the whole window.

    Returns (series, (grid_lat, grid_lon)) -- the second item is the ERA5 cell
    Open-Meteo actually used, which is worth printing: it can sit several km
    from the AOI centre, and over land rather than water.
    """
    if get is None:
        import requests
        get = requests.get
    params = {
        "latitude": round(lat, 4), "longitude": round(lon, 4),
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "hourly": "wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "ms", "models": "era5", "timezone": "GMT",
    }
    resp = get(OPEN_METEO_ARCHIVE, params=params, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    return parse_open_meteo(payload), (payload.get("latitude"), payload.get("longitude"))


def window_dates(datetimes_utc: Sequence[str]) -> tuple[date, date]:
    """Request range covering every scene, plus a day so a 23:50 overpass can
    reach the next day's 00:00 value."""
    days = [datetime.strptime(d, "%Y-%m-%d %H:%M").date() for d in datetimes_utc]
    return min(days), max(days) + timedelta(days=1)
