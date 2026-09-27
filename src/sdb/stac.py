"""Sentinel-2 scene discovery for satellite-derived bathymetry.

Finds candidate L2A scenes near a lidar capture date, scores them on the things
that actually decide whether SDB will work, and writes a table for a human to
choose from. It downloads no imagery.

The score is a sort order, not a verdict. Every component is reported in its own
column so the ranking can be argued with. Two of the four inputs -- cloud over
the AOI, and glint -- cannot be settled from metadata alone and must be
confirmed by looking at the scene.

Optionally (on by default) each row also gets ERA5 wind and a Cox-Munk glint
index from `glint.py`. It is reported, not scored: see that module for why.

Network access is confined to `search_scenes` and `glint.fetch_era5_wind`.
Everything else is pure and tested in tests/test_stac.py and test_glint.py.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from sdb.glint import (WIND_SOURCE, attach_glint, fetch_era5_wind, outside_fit_range,
                       specular_facet, window_dates)

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

#: A scene that does not cover the whole AOI cannot validate the whole AOI.
#: Sentinel-2 tiles are 109.8 km and overlap by ~10 km, so an AOI near a
#: 100 km grid boundary is routinely split -- and the partial tile still comes
#: back from a bbox search looking like a perfectly good candidate.
MIN_AOI_COVERAGE_PCT = 99.0

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

    The vector implementation lives in `glint.specular_facet`, shared with the
    wind-aware glint model so the two can never disagree.
    """
    return specular_facet(sun_zenith_deg, view_zenith_deg, relative_azimuth_deg)[0]


def glint_flag(facet_angle_deg: float) -> str:
    """Label the glint risk implied by a facet angle. Heuristic; see constants."""
    if facet_angle_deg < GLINT_FACET_SEVERE_DEG:
        return "severe"
    if facet_angle_deg < GLINT_FACET_WARN_DEG:
        return "watch"
    return "ok"


def mgrs_tile(props: dict[str, Any]) -> str | None:
    """Pull the MGRS tile id out of whichever key the catalogue happens to use.

    Earth Search v1 publishes `grid:code` as "MGRS-56HKG"; older items and other
    catalogues use `s2:mgrs_tile` or the three `mgrs:*` fields. Reading only one
    of them returns an empty column, which silently hides the fact that a search
    spans two tiles.
    """
    code = props.get("grid:code")
    if isinstance(code, str) and code:
        return code.split("-", 1)[-1].upper()
    tile = props.get("s2:mgrs_tile")
    if tile:
        return str(tile).upper()
    z, b, sq = (props.get("mgrs:utm_zone"), props.get("mgrs:latitude_band"),
                props.get("mgrs:grid_square"))
    if z and b and sq:
        return f"{int(z):02d}{b}{sq}".upper()
    return None


def aoi_coverage_pct(item_geometry: dict[str, Any] | None,
                     aoi_bbox: Sequence[float]) -> float:
    """Percentage of the AOI that this item's footprint actually covers.

    Computed on lon/lat as a plain area ratio. Over a bay-sized AOI the
    convergence of meridians cancels between numerator and denominator, so the
    ratio is accurate to far better than the 1% that the decision turns on.
    """
    if not item_geometry:
        return float("nan")
    from shapely.geometry import box, shape

    aoi = box(*aoi_bbox)
    if aoi.area <= 0:
        return float("nan")
    return 100.0 * shape(item_geometry).intersection(aoi).area / aoi.area


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


def summarise_item(item_props: dict[str, Any], item_id: str, capture_dates: Sequence[date],
                   *, item_geometry: dict[str, Any] | None = None,
                   aoi_bbox: Sequence[float] | None = None) -> dict[str, Any]:
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
    rel_az = ((view_az - sun_az + 180.0) % 360.0) - 180.0 if view_az == view_az else 0.0
    facet = specular_facet_angle(sun_zen, view_zen, rel_az) if sun_zen == sun_zen else float("nan")

    coverage = (aoi_coverage_pct(item_geometry, aoi_bbox)
                if aoi_bbox is not None else float("nan"))
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
        "view_zen_deg": round(view_zen, 1),
        "view_rel_az_deg": round(rel_az, 1),
        "processing_baseline": baseline,
        "needs_boa_offset": needs_boa_offset(baseline),
        "platform": item_props.get("platform"),
        "mgrs_tile": mgrs_tile(item_props),
        "aoi_coverage_pct": round(coverage, 1) if coverage == coverage else None,
        "score": round(score_scene(days_off, cloud if cloud == cloud else 100.0,
                                   facet if facet == facet else 0.0,
                                   sun_elev if sun_elev == sun_elev else 0.0), 3),
    }


def dedupe_acquisitions(rows: Iterable[dict[str, Any]], *,
                        prefer: str = "highest_baseline") -> list[dict[str, Any]]:
    """Collapse the same acquisition appearing under several processing baselines.

    Earth Search carries both ESA's reprocessed Collection-1 products and older
    processings of the same datatake. They are not independent observations, and
    left alone they consume the top of the shortlist twice over.

    Default keeps the highest baseline: Collection-1 is consistently reprocessed
    across the archive, which is what a validation study wants. The cost is that
    it needs the BOA offset, which is reported per row.
    """
    best: dict[tuple[str | None, str], dict[str, Any]] = {}
    for r in rows:
        key = (r.get("mgrs_tile"), r["datetime_utc"][:10])
        cur = best.get(key)
        if cur is None:
            best[key] = dict(r, n_versions=1)
            continue
        cur["n_versions"] += 1

        def _b(x):
            try:
                return float(x.get("processing_baseline") or -1)
            except (TypeError, ValueError):
                return -1.0

        take = _b(r) > _b(cur) if prefer == "highest_baseline" else _b(r) < _b(cur)
        if take:
            n = cur["n_versions"]
            best[key] = dict(r, n_versions=n)
    return list(best.values())


def classify_candidates(rows: Iterable[dict[str, Any]], *, max_cloud: float,
                        max_nodata: float,
                        min_coverage: float = MIN_AOI_COVERAGE_PCT) -> list[dict[str, Any]]:
    """Give every row a `status`: "kept", or "rejected: <reason>".

    Rejected rows are retained, not dropped, so the decision trail survives into
    the written table. The first question anyone asks of a scene choice is why
    the obvious candidate was not used.

    Partial AOI coverage is a hard rejection, not a penalty. A scene covering a
    quarter of the bay cannot validate the bay, however clear and however close
    in time -- and it would otherwise sit at the top of the list looking ideal.
    """
    out = []
    for r in rows:
        r = dict(r)
        cov = r.get("aoi_coverage_pct")
        if cov is not None and cov == cov and cov < min_coverage:
            r["status"] = f"rejected: covers {cov:.1f}% of AOI"
        elif r["cloud_pct"] == r["cloud_pct"] and r["cloud_pct"] > max_cloud:
            r["status"] = f"rejected: scene cloud {r['cloud_pct']:.1f}%"
        elif r["nodata_pct"] > max_nodata:
            r["status"] = f"rejected: nodata {r['nodata_pct']:.1f}%"
        else:
            r["status"] = "kept"
        out.append(r)
    kept = sorted((r for r in out if r["status"] == "kept"),
                  key=lambda r: (-r["score"], r["days_from_lidar"]))
    rej = sorted((r for r in out if r["status"] != "kept"),
                 key=lambda r: (-r["score"], r["days_from_lidar"]))
    return kept + rej


def filter_candidates(rows: Iterable[dict[str, Any]], *, max_cloud: float,
                      max_nodata: float,
                      min_coverage: float = MIN_AOI_COVERAGE_PCT) -> list[dict[str, Any]]:
    """The kept subset of `classify_candidates`, best first."""
    return [r for r in classify_candidates(rows, max_cloud=max_cloud,
                                           max_nodata=max_nodata,
                                           min_coverage=min_coverage)
            if r["status"] == "kept"]


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
    return [summarise_item(it.properties, it.id, site.capture_dates,
                           item_geometry=it.geometry, aoi_bbox=site.bbox)
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
    p.add_argument("--min-coverage", type=float, default=MIN_AOI_COVERAGE_PCT,
                   help="reject scenes covering less than this %% of the AOI")
    p.add_argument("--keep-duplicates", action="store_true",
                   help="do not collapse the same acquisition across baselines")
    p.add_argument("--no-wind", action="store_true",
                   help="skip the ERA5 wind lookup and Cox-Munk glint index")
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
    print(f"{len(rows)} items in window")
    tiles = sorted({r["mgrs_tile"] for r in rows if r["mgrs_tile"]})
    if len(tiles) > 1:
        print(f"AOI spans {len(tiles)} MGRS tiles: {', '.join(tiles)}")
        for t in tiles:
            covs = [r["aoi_coverage_pct"] for r in rows
                    if r["mgrs_tile"] == t and r["aoi_coverage_pct"] is not None]
            if covs:
                print(f"   {t}: covers {max(covs):.1f}% of the AOI")

    if not a.keep_duplicates:
        before = len(rows)
        rows = dedupe_acquisitions(rows)
        print(f"{before - len(rows)} duplicate processings collapsed "
              f"-> {len(rows)} unique acquisitions")

    have_wind = False
    if not a.no_wind and rows:
        rows, have_wind = _add_wind(rows, site)

    allrows = classify_candidates(rows, max_cloud=max_cloud, max_nodata=max_nodata,
                                  min_coverage=a.min_coverage)
    kept = [r for r in allrows if r["status"] == "kept"]
    print(f"{len(kept)} pass the hard filters "
          f"(coverage >= {a.min_coverage}%, cloud <= {max_cloud}%, nodata <= {max_nodata}%)\n")

    if not kept:
        print("Nothing passed. Widen --window-days or raise --max-cloud before "
              "concluding anything about the site.")
        return 1

    # Console shows kept rows only, so tile and coverage (always >= the filter)
    # are left to the CSV; short headers keep the table inside a normal
    # terminal. The CSV keeps every column under its full name.
    cols = ["datetime_utc", "days_from_lidar", "cloud_pct", "sun_elev_deg",
            "glint_facet_deg", "glint_flag", "processing_baseline", "needs_boa_offset",
            "score", "id"]
    if have_wind:
        cols[cols.index("glint_flag") + 1:cols.index("glint_flag") + 1] = [
            "wind_ms", "wind_from_deg", "sun_wind_axis_deg", "glint_sigma"]
    short = {"datetime_utc": "utc", "days_from_lidar": "days", "cloud_pct": "cloud",
             "sun_elev_deg": "sun_el", "glint_facet_deg": "facet", "glint_flag": "geom",
             "wind_ms": "wind", "wind_from_deg": "from", "sun_wind_axis_deg": "sun_wind",
             "glint_sigma": "glint_sig", "processing_baseline": "pb",
             "needs_boa_offset": "offset"}
    try:
        import pandas as pd
        a.out.mkdir(parents=True, exist_ok=True)
        csv = a.out / f"candidates_{site.name}.csv"
        full = pd.DataFrame(allrows)
        front = ["status"] + [c for c in full.columns if c != "status"]
        full[front].to_csv(csv, index=False)
        print(pd.DataFrame(kept)[cols].head(a.top).rename(columns=short).to_string(index=False))
        n_rej = len(allrows) - len(kept)
        print(f"\nfull table, including {n_rej} rejected rows and why -> {csv}")
    except ImportError:
        for r in kept[:a.top]:
            print({k: r[k] for k in cols})

    baselines = {r["processing_baseline"] for r in kept}
    if len(baselines) > 1:
        print(f"\nNOTE  mixed processing baselines in the shortlist: {sorted(map(str, baselines))}."
              f"\n      Products at baseline >= {BASELINE_OFFSET_FROM:.2f} need the -1000 DN BOA"
              f"\n      offset applied before scaling. Harmonise before comparing scenes.")
    print("\nCloud percentage is scene-wide and a poor proxy for cloud over a small AOI."
          "\ngeom (glint_flag) is geometry only. glint_sig adds wind from one ~25 km ERA5"
          "\ncell: slope needed to glint, in standard deviations -- LOWER is MORE glint-"
          "\nprone. Rank with it; do not read it as a value. Neither cloud nor glint is"
          "\nsettled until you have looked. Shortlist, then look.")
    return 0


def _add_wind(rows: list[dict[str, Any]], site: Site) -> tuple[list[dict[str, Any]], bool]:
    """Attach ERA5 wind and the glint index. Never fails the search.

    The broad except is deliberate: this is optional enrichment, and a network,
    HTTP or schema failure in a third-party API must not stop scene discovery.
    The failure is printed, and the columns are left empty rather than guessed.
    """
    w, s, e, n = site.bbox
    lat, lon = (s + n) / 2.0, (w + e) / 2.0
    start, end = window_dates([r["datetime_utc"] for r in rows])
    try:
        series, (glat, glon) = fetch_era5_wind(lat, lon, start, end)
    except Exception as exc:  # noqa: BLE001 -- see docstring
        print(f"wind: unavailable ({type(exc).__name__}: {exc}); glint index left empty")
        return attach_glint(rows, {}), False

    rows = attach_glint(rows, series)
    got = sum(r["wind_ms"] is not None for r in rows)
    where = ""
    if glat is not None and glon is not None:
        km = math.hypot((glat - lat) * 111.0, (glon - lon) * 111.0 * math.cos(math.radians(lat)))
        where = f"; ERA5 cell {glat:.3f}, {glon:.3f} is {km:.0f} km from AOI centre"
    print(f"wind: {got}/{len(rows)} scenes matched to the nearest hour{where}")
    print(f"      source: {WIND_SOURCE}")
    odd = outside_fit_range(rows)
    if odd["below"]:
        print(f"      NOTE {len(odd['below'])} scene(s) below 1 m/s: evaluated at 1 m/s, so"
              f" their glint_sigma is a lower bound (calmer water glints less)")
    if odd["above"]:
        print(f"      NOTE {len(odd['above'])} scene(s) above 14 m/s: glint_sigma is"
              f" extrapolation, and whitecaps will matter more than glint")
    return rows, got > 0


if __name__ == "__main__":
    sys.exit(main())
