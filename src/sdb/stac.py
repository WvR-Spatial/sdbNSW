"""Sentinel-2 scene discovery for satellite-derived bathymetry.

Finds candidate L2A scenes near a lidar capture date, scores them on the things
that actually decide whether SDB will work, and writes a table for a human to
choose from. It downloads no imagery.

The score is a sort order, not a verdict. Every component is reported in its own
column so the ranking can be argued with. Two of the four inputs -- cloud over
the AOI, and glint -- cannot be settled from metadata alone and must be
confirmed by looking at the scene.

Network access is confined to `search_scenes`. Everything else is pure and
tested against known answers in tests/test_stac.py.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

# --------------------------------------------------------------------------
# Constants, with reasons
# --------------------------------------------------------------------------

#: Sentinel-2 L2A products built with processing baseline >= 04.00 carry a
#: BOA_ADD_OFFSET of -1000 DN that must be applied before scaling to
#: reflectance. Mixing baselines without harmonising produces a constant
#: reflectance shift -- which in a band-ratio bathymetry model becomes a depth
#: bias that looks entirely plausible. Surfaced per scene so the decision is
#: explicit rather than accidental.
BASELINE_OFFSET_FROM = 4.00

#: Facet tilt (degrees) below which sun glint is a live risk for near-nadir
#: viewing. Heuristic, not a threshold from the literature: glint depends on
#: surface roughness (wind) which no scene metadata records. Treated as a flag
#: for visual inspection, never as a rejection.
GLINT_FACET_WARN_DEG = 15.0
GLINT_FACET_SEVERE_DEG = 10.0

#: Below this solar elevation the water-leaving signal in blue/green gets thin
#: and the path length through the water column grows. Above ~60 deg, glint
#: risk climbs instead. Neither is fatal; both are reported.
SUN_ELEV_MIN_DEG = 25.0
SUN_ELEV_GLINT_DEG = 60.0


@dataclass(frozen=True)
class Site:
    """A study site. bbox is [west, south, east, north] in EPSG:4326."""

    name: str
    label: str
    bbox: tuple[float, float, float, float]
    capture_dates: tuple[date, ...]

    def __post_init__(self) -> None:
        w, s, e, n = self.bbox
        if not (w < e and s < n):
            raise ValueError(f"{self.name}: bbox is not west,south,east,north: {self.bbox}")
        if not self.capture_dates:
            raise ValueError(f"{self.name}: no reference capture dates")


# --------------------------------------------------------------------------
# Pure geometry and scoring
# --------------------------------------------------------------------------


def specular_facet_angle(
    sun_zenith_deg: float,
    view_zenith_deg: float = 0.0,
    relative_azimuth_deg: float = 0.0,
) -> float:
    """Tilt a water facet must have to reflect the sun into the sensor.

    Returns the angle in degrees between the required facet normal and the
    vertical. A *small* angle means gently-tilted facets would glint, so glint
    is likely even in light wind. A large angle means only steep facets glint,
    which needs strong wind.

    For nadir viewing this reduces to half the solar zenith angle, so a high sun
    is the risky case -- the opposite of the intuition that bright is good.

    Geometry. Let s be the unit vector from the target toward the sun and v the
    unit vector from the target toward the sensor, both with zenith measured
    from vertical and azimuth from north. Specular reflection requires the facet
    normal to bisect s and v, so n is parallel to s + v, and the tilt is the
    angle between that bisector and the vertical.

    `relative_azimuth_deg` is the sensor azimuth minus the solar azimuth. At
    0 degrees the sensor looks from the same side as the sun, which requires
    retro-reflection and therefore a *large* tilt; at 180 degrees the sensor
    sits in the mirror direction and a flat surface suffices.

    Note the closed form `cos(2w) = cos(ts)cos(tv) - sin(ts)sin(tv)cos(dphi)`
    is NOT this quantity. It agrees inside the principal plane and diverges off
    it -- by about 0.8 degrees at ts=20, tv=30, dphi=90. Sentinel-2 views within
    ~11 degrees of nadir so the difference is immaterial here, but the closed
    form is wrong and is not used.
    """
    ts, tv = math.radians(sun_zenith_deg), math.radians(view_zenith_deg)
    dphi = math.radians(relative_azimuth_deg)

    sx, sy, sz = math.sin(ts), 0.0, math.cos(ts)
    vx, vy, vz = (math.sin(tv) * math.cos(dphi),
                  math.sin(tv) * math.sin(dphi),
                  math.cos(tv))
    nx, ny, nz = sx + vx, sy + vy, sz + vz
    mag = math.sqrt(nx * nx + ny * ny + nz * nz)
    if mag < 1e-12:          # sun and sensor exactly opposed on the horizon
        return 90.0
    return math.degrees(math.acos(max(-1.0, min(1.0, nz / mag))))


def glint_flag(facet_angle_deg: float) -> str:
    """Label the glint risk implied by a facet angle. Heuristic; see constants."""
    if facet_angle_deg < GLINT_FACET_SEVERE_DEG:
        return "severe"
    if facet_angle_deg < GLINT_FACET_WARN_DEG:
        return "watch"
    return "ok"


def days_from_reference(scene_dt: datetime, capture_dates: Sequence[date]) -> int:
    """Whole days from the scene to the nearest lidar capture date.

    This is the seabed-change term in the error budget: every day between the
    survey and the image is time for sand to move.
    """
    d = scene_dt.astimezone(timezone.utc).date()
    return min(abs((d - c).days) for c in capture_dates)


def needs_boa_offset(processing_baseline: str | float | None) -> bool | None:
    """True if this product needs the -1000 DN BOA offset applied.

    None when the baseline is absent from the metadata, which is itself worth
    knowing -- it means harmonisation cannot be decided from the catalogue.
    """
    if processing_baseline is None:
        return None
    try:
        return float(processing_baseline) >= BASELINE_OFFSET_FROM
    except (TypeError, ValueError):
        return None


def score_scene(
    days_off: int,
    cloud_pct: float,
    facet_angle_deg: float,
    sun_elev_deg: float,
    *,
    weights: dict[str, float] | None = None,
) -> float:
    """Composite sort key in [0, 1]; higher is a better candidate.

    Deliberately simple and fully decomposed -- the caller reports every input
    alongside the score so a human can disagree with the weighting. It exists to
    order a shortlist, not to pick the scene.
    """
    w = {"date": 0.40, "cloud": 0.30, "glint": 0.20, "sun": 0.10}
    if weights:
        w.update(weights)

    date_s = math.exp(-days_off / 30.0)                     # ~0.72 at 10 d, ~0.37 at 30 d
    cloud_s = max(0.0, 1.0 - cloud_pct / 100.0)
    glint_s = min(1.0, facet_angle_deg / GLINT_FACET_WARN_DEG)

    if sun_elev_deg < SUN_ELEV_MIN_DEG:
        sun_s = max(0.0, sun_elev_deg / SUN_ELEV_MIN_DEG)
    elif sun_elev_deg > SUN_ELEV_GLINT_DEG:
        sun_s = max(0.0, 1.0 - (sun_elev_deg - SUN_ELEV_GLINT_DEG) / 30.0)
    else:
        sun_s = 1.0

    total = sum(w.values())
    return (w["date"] * date_s + w["cloud"] * cloud_s
            + w["glint"] * glint_s + w["sun"] * sun_s) / total


def summarise_item(item_props: dict[str, Any], item_id: str, capture_dates: Sequence[date]) -> dict[str, Any]:
    """Reduce one STAC item's properties to the fields the choice turns on.

    Pure: takes a plain dict, so it is testable without a network call.
    """
    dt = datetime.fromisoformat(str(item_props["datetime"]).replace("Z", "+00:00"))

    sun_elev = float(item_props.get("view:sun_elevation", float("nan")))
    sun_az = float(item_props.get("view:sun_azimuth", float("nan")))
    # Sentinel-2 views within ~11 deg of nadir. Earth Search rarely carries a
    # per-scene view angle, so nadir is assumed and the assumption is recorded.
    view_zen = float(item_props.get("view:off_nadir", 0.0) or 0.0)
    view_az = float(item_props.get("view:azimuth", sun_az) or sun_az)

    sun_zen = 90.0 - sun_elev if sun_elev == sun_elev else float("nan")
    if sun_zen == sun_zen:
        rel_az = ((view_az - sun_az + 180.0) % 360.0) - 180.0 if view_az == view_az else 0.0
        facet = specular_facet_angle(sun_zen, view_zen, rel_az)
    else:
        facet = float("nan")

    cloud = float(item_props.get("eo:cloud_cover", float("nan")))
    nodata = float(item_props.get("s2:nodata_pixel_percentage", 0.0) or 0.0)
    baseline = item_props.get("s2:processing_baseline")
    days_off = days_from_reference(dt, capture_dates)

    return {
        "id": item_id,
        "datetime_utc": dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "days_from_lidar": days_off,
        "cloud_pct": round(cloud, 1),
        "nodata_pct": round(nodata, 1),
        "sun_elev_deg": round(sun_elev, 1),
        "sun_az_deg": round(sun_az, 1),
        "glint_facet_deg": round(facet, 1),
        "glint_flag": glint_flag(facet) if facet == facet else "unknown",
        "view_zenith_assumed_nadir": view_zen == 0.0,
        "processing_baseline": baseline,
        "needs_boa_offset": needs_boa_offset(baseline),
        "platform": item_props.get("platform"),
        "mgrs_tile": "".join(str(item_props.get(k, "")) for k in
                             ("s2:mgrs_tile",)) or None,
        "score": round(score_scene(days_off, cloud if cloud == cloud else 100.0,
                                   facet if facet == facet else 0.0,
                                   sun_elev if sun_elev == sun_elev else 0.0), 3),
    }


def filter_candidates(rows: Iterable[dict[str, Any]], *, max_cloud: float,
                      max_nodata: float) -> list[dict[str, Any]]:
    """Drop scenes that cannot be used, keep everything else for human review."""
    keep = []
    for r in rows:
        if r["cloud_pct"] == r["cloud_pct"] and r["cloud_pct"] > max_cloud:
            continue
        if r["nodata_pct"] > max_nodata:
            continue
        keep.append(r)
    return sorted(keep, key=lambda r: (-r["score"], r["days_from_lidar"]))


# --------------------------------------------------------------------------
# The only function that touches the network
# --------------------------------------------------------------------------


def search_scenes(site: Site, *, stac_url: str, collection: str,
                  window_days: int) -> list[dict[str, Any]]:
    """Query the STAC API and return summarised rows. Downloads no pixels."""
    from pystac_client import Client  # imported here so the pure code needs no deps

    lo = min(site.capture_dates)
    hi = max(site.capture_dates)
    start = (datetime.combine(lo, datetime.min.time()) - _days(window_days)).date()
    end = (datetime.combine(hi, datetime.min.time()) + _days(window_days)).date()

    client = Client.open(stac_url)
    search = client.search(
        collections=[collection],
        bbox=list(site.bbox),
        datetime=f"{start.isoformat()}/{end.isoformat()}",
    )
    return [summarise_item(it.properties, it.id, site.capture_dates)
            for it in search.items()]


def _days(n: int):
    from datetime import timedelta
    return timedelta(days=n)


# --------------------------------------------------------------------------
# Config and CLI
# --------------------------------------------------------------------------


def load_site(config_path: Path, site_key: str) -> tuple[Site, dict[str, Any]]:
    import yaml

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    defaults = cfg.get("defaults", {})
    raw = cfg["sites"][site_key]
    if not raw.get("bbox"):
        raise SystemExit(f"site '{site_key}' has no bbox yet -- measure it from the "
                         f"coverage index before searching")
    site = Site(
        name=site_key,
        label=raw.get("label", site_key),
        bbox=tuple(raw["bbox"]),
        capture_dates=tuple(date.fromisoformat(d) for d in raw["capture_dates"]),
    )
    return site, defaults


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--site", default="jervis_bay")
    p.add_argument("--config", type=Path, default=Path("config/sites.yml"))
    p.add_argument("--window-days", type=int, default=None)
    p.add_argument("--max-cloud", type=float, default=None)
    p.add_argument("--max-nodata", type=float, default=None)
    p.add_argument("--out", type=Path, default=Path("outputs"))
    p.add_argument("--top", type=int, default=15, help="rows to print")
    a = p.parse_args(argv)

    site, defaults = load_site(a.config, a.site)
    window = a.window_days or defaults.get("window_days", 45)
    max_cloud = a.max_cloud if a.max_cloud is not None else defaults.get("max_cloud", 40)
    max_nodata = a.max_nodata if a.max_nodata is not None else defaults.get("max_nodata", 5)

    print(f"{site.label}  bbox={site.bbox}")
    print(f"reference capture: {', '.join(d.isoformat() for d in site.capture_dates)}"
          f"   window: +/-{window} d   cloud<={max_cloud}%  nodata<={max_nodata}%\n")

    rows = search_scenes(site, stac_url=defaults.get("stac_url"),
                         collection=defaults.get("collection", "sentinel-2-l2a"),
                         window_days=window)
    print(f"{len(rows)} scenes in window")
    kept = filter_candidates(rows, max_cloud=max_cloud, max_nodata=max_nodata)
    print(f"{len(kept)} pass the hard filters\n")

    if not kept:
        print("Nothing passed. Widen --window-days or raise --max-cloud before "
              "concluding anything about the site.")
        return 1

    cols = ["datetime_utc", "days_from_lidar", "cloud_pct", "sun_elev_deg",
            "glint_facet_deg", "glint_flag", "processing_baseline",
            "needs_boa_offset", "score", "id"]
    try:
        import pandas as pd
        df = pd.DataFrame(kept)
        a.out.mkdir(parents=True, exist_ok=True)
        csv = a.out / f"candidates_{site.name}.csv"
        df.to_csv(csv, index=False)
        print(df[cols].head(a.top).to_string(index=False))
        print(f"\nfull table -> {csv}")
    except ImportError:
        for r in kept[:a.top]:
            print({k: r[k] for k in cols})

    baselines = {r["processing_baseline"] for r in kept}
    if len(baselines) > 1:
        print(f"\nNOTE  mixed processing baselines in the shortlist: {sorted(map(str, baselines))}."
              f"\n      Products at baseline >= {BASELINE_OFFSET_FROM:.2f} need the -1000 DN BOA"
              f"\n      offset applied before scaling. Harmonise before comparing scenes.")
    print("\nCloud percentage is scene-wide and a poor proxy for cloud over a small"
          "\nAOI; glint is a geometry heuristic that ignores wind. Neither is settled"
          "\nuntil you have looked at the scene. Shortlist, then look.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
