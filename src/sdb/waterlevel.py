"""Water level at the moment of the overpass, in metres AHD.

Why it matters, and how much. The lidar gives seabed elevation in AHD; the
image sees depth below the water surface at 10:02 local time. Depth = water
level - elevation. A constant error in the water level is absorbed by the
intercept of an empirical (Stumpf) calibration, so it barely moves a calibrated
RMSE -- but it shifts every pixel's depth band, which pixels count as land or
as 0-20 m, and any depth reported against AHD. So: measured when possible,
estimated and labelled provisional when not.

Two sources, never silently mixed:

  gauge    MHL Jervis Bay tide gauge (216470, HMAS Creswell), observed series
           supplied by MHL as CSV. Times are AEST (UTC+10, no daylight saving).
           The datum is inferred from the numbers, not the label: MHL's own
           pages label chart-datum values "m AHD" and AHD tables "Chart Datum".
           Mean sea level 2018-19 was +0.074 m AHD, i.e. +1.144 m chart datum
           (AHD offset -1.07 m), so the series mean identifies its datum.

  image    Provisional. The water level at which the lidar's land/water pattern
           best matches the image's near-infrared along the whole shoreline.
           NIR still reads bright through the first ~0.1-0.2 m of water, so
           this is biased LOW by about that much. Labelled as such.

Writes outputs/waterlevel_<scene>.json; reference.py reads it automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from sdb import __version__

AEST = timezone(timedelta(hours=10))

#: A gauge sample must lie within this many minutes either side of the overpass.
MAX_GAP_MIN = 30.0

#: Datum inference: the series mean over the supplied record must sit within
#: this of mean sea level in exactly one datum. The two candidates are 1.07 m
#: apart; a day of tide averages to within ~0.1 m of MSL.
DATUM_TOLERANCE_M = 0.35

#: Plausibility band beyond the extreme tidal planes (m). A value outside
#: [ISLW - margin, HHWSS + margin] means a datum or unit error, not a tide.
PLAUSIBLE_MARGIN_M = 0.4

#: Image estimate search, m AHD.
IMAGE_SEARCH = (-1.2, 0.8)
IMAGE_COARSE_STEP = 0.1
IMAGE_FINE_STEP = 0.025
IMAGE_BAND_PX = 8
IMAGE_BIAS_NOTE = ("NIR reads bright through the first ~0.1-0.2 m of water, so the image "
                   "estimate is biased low by about that much")


@dataclass(frozen=True)
class Gauge:
    """Tide gauge constants, all in metres AHD except the offset."""

    station: str
    name: str
    ahd_offset_m: float          # level_AHD = level_CD + offset
    msl_ahd: float
    islw_ahd: float
    hhwss_ahd: float
    source: str

    @classmethod
    def from_config(cls, d: dict[str, Any]) -> "Gauge":
        return cls(str(d["station"]), d["name"], float(d["ahd_offset_m"]), float(d["msl_ahd"]),
                   float(d["islw_ahd"]), float(d["hhwss_ahd"]), d.get("source", ""))


# --------------------------------------------------------------------------
# Gauge record (pure)
# --------------------------------------------------------------------------


def read_gauge_csv(path: Path, *, time_col: str | None = None,
                   level_col: str | None = None) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """(times as UTC datetime64[s], levels float64, notes) from an MHL-style CSV.

    Tolerant of layout: header lines before the table are skipped, the time
    column is the first that parses as dates (day first, Australian style), the
    level column the first mostly-numeric one after it -- unless named. Times
    are taken as AEST, as MHL documents, and converted to UTC.
    """
    import pandas as pd

    raw = Path(path).read_text(encoding="utf-8-sig", errors="replace").splitlines()
    start = 0
    for i, line in enumerate(raw[:200]):
        cells = [c.strip() for c in line.split(",")]
        if len(cells) >= 2 and _looks_like_datetime(cells[0]) and _looks_numeric(cells[1]):
            start = max(i - 1, 0)
            break
    header_is_data = _looks_like_datetime(raw[start].split(",")[0].strip())
    df = pd.read_csv(path, skiprows=start, header=None if header_is_data else 0,
                     encoding="utf-8-sig", skipinitialspace=True)
    df.columns = [str(c).strip() for c in df.columns]

    tcol = time_col or next(c for c in df.columns
                            if pd.to_datetime(df[c].head(20), dayfirst=True, errors="coerce").notna().mean() > 0.8)
    lcol = level_col or next(c for c in df.columns if c != tcol
                             and pd.to_numeric(df[c], errors="coerce").notna().mean() > 0.8)
    t = pd.to_datetime(df[tcol], dayfirst=True, errors="coerce")
    z = pd.to_numeric(df[lcol], errors="coerce")
    ok = t.notna() & z.notna()
    t_local = t[ok].dt.tz_localize(AEST) if t[ok].dt.tz is None else t[ok]
    t_utc = t_local.dt.tz_convert("UTC").dt.tz_localize(None).values.astype("datetime64[s]")
    order = np.argsort(t_utc)
    notes = {"file_rows": int(len(df)), "rows_used": int(ok.sum()), "time_column": tcol,
             "level_column": lcol, "header_lines_skipped": start,
             "timezone_assumed": "AEST (UTC+10), per MHL" if t[ok].dt.tz is None else "from file"}
    return t_utc[order], z[ok].to_numpy(float)[order], notes


def _looks_like_datetime(s: str) -> bool:
    import pandas as pd
    if not s or s.replace(".", "", 1).lstrip("-").isdigit():
        return False
    return pd.to_datetime(s, dayfirst=True, errors="coerce") is not pd.NaT


def _looks_numeric(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def infer_datum(levels: np.ndarray, gauge: Gauge, *, tol: float = DATUM_TOLERANCE_M) -> str:
    """'ahd' or 'cd', from where the record's mean sits. Raises if ambiguous."""
    m = float(np.nanmean(levels))
    d_ahd = abs(m - gauge.msl_ahd)
    d_cd = abs(m - (gauge.msl_ahd - gauge.ahd_offset_m))
    hits = [name for name, d in (("ahd", d_ahd), ("cd", d_cd)) if d <= tol]
    if len(hits) != 1:
        raise ValueError(f"cannot tell the datum: record mean {m:+.3f} m is {d_ahd:.2f} m from MSL "
                         f"in AHD and {d_cd:.2f} m from MSL in chart datum; pass --datum")
    return hits[0]


def to_ahd(levels: np.ndarray, datum: str, gauge: Gauge) -> np.ndarray:
    if datum == "ahd":
        return levels.astype(float)
    if datum == "cd":
        return levels.astype(float) + gauge.ahd_offset_m
    raise ValueError(f"unknown datum {datum!r}")


def level_at(times_utc: np.ndarray, levels: np.ndarray, when_utc: datetime, *,
             max_gap_min: float = MAX_GAP_MIN) -> dict[str, Any]:
    """Linear interpolation at `when_utc`, with the bracketing samples and the tidal rate."""
    w = np.datetime64(when_utc.astimezone(timezone.utc).replace(tzinfo=None), "s")
    i = int(np.searchsorted(times_utc, w))
    if i == 0 or i >= len(times_utc):
        raise ValueError(f"record ({times_utc[0]} to {times_utc[-1]} UTC) does not bracket {w} UTC")
    t0, t1 = times_utc[i - 1], times_utc[i]
    g0 = (w - t0) / np.timedelta64(1, "m")
    g1 = (t1 - w) / np.timedelta64(1, "m")
    if g0 > max_gap_min or g1 > max_gap_min:
        raise ValueError(f"nearest samples are {g0:.0f} min before and {g1:.0f} min after the overpass")
    span = (t1 - t0) / np.timedelta64(1, "s")
    f = 0.0 if span == 0 else float((w - t0) / np.timedelta64(1, "s") / span)
    z = float(levels[i - 1] + f * (levels[i] - levels[i - 1]))
    rate = float((levels[i] - levels[i - 1]) / (span / 3600.0)) if span else 0.0
    return {"level": z, "before_utc": str(t0), "after_utc": str(t1),
            "gap_before_min": round(float(g0), 1), "gap_after_min": round(float(g1), 1),
            "tidal_rate_m_per_h": round(rate, 3)}


def plausible(level_ahd: float, gauge: Gauge, margin: float = PLAUSIBLE_MARGIN_M) -> bool:
    return gauge.islw_ahd - margin <= level_ahd <= gauge.hhwss_ahd + margin


# --------------------------------------------------------------------------
# Image estimate (pure; provisional)
# --------------------------------------------------------------------------


def image_estimate(z: np.ndarray, valid: np.ndarray, src, dst, nir: np.ndarray,
                   usable: np.ndarray, *, search: tuple[float, float] = IMAGE_SEARCH,
                   coarse: float = IMAGE_COARSE_STEP, fine: float = IMAGE_FINE_STEP,
                   band_px: int = IMAGE_BAND_PX) -> dict[str, Any]:
    """Water level (m AHD) at which lidar land fraction best matches image NIR.

    `dst` must already carry the co-registration shift. The pixel set is fixed
    (a band around the 0 m AHD waterline) so every trial level is scored on the
    same pixels.
    """
    from scipy import ndimage

    from sdb.reference import MIN_COVERAGE, LandFractionField

    lf0, cov0 = LandFractionField(z, valid, src, 0.0).on(dst)
    mixed = (lf0 > 0) & (lf0 < 1) & (cov0 >= MIN_COVERAGE)
    P = (ndimage.distance_transform_edt(~mixed) <= band_px) & usable & (cov0 >= MIN_COVERAGE)
    a = nir[P].astype(np.float64)

    def score(wl: float) -> float:
        lf, _ = LandFractionField(z, valid, src, wl).on(dst)
        b = lf[P]
        ok = np.isfinite(a) & np.isfinite(b)
        x, y = a[ok] - a[ok].mean(), b[ok] - b[ok].mean()
        return float((x * y).sum() / math.sqrt(float((x * x).sum() * (y * y).sum())))

    levels = np.arange(search[0], search[1] + coarse / 2, coarse)
    scores = np.array([score(w) for w in levels])
    k = int(np.nanargmax(scores))
    if k in (0, len(levels) - 1):
        return {"status": "peak at search edge", "levels": levels.tolist(), "scores": scores.tolist()}
    fl = np.arange(levels[k] - coarse, levels[k] + coarse + fine / 2, fine)
    fs = np.array([score(w) for w in fl])
    j = int(np.nanargmax(fs))
    best = float(fl[j])
    if 0 < j < len(fl) - 1:
        a0, b0, c0 = fs[j - 1], fs[j], fs[j + 1]
        den = a0 - 2 * b0 + c0
        if den < 0:
            best += float(np.clip(0.5 * (a0 - c0) / den, -0.5, 0.5)) * fine
    return {"status": "ok", "level_m_ahd": round(best, 3), "peak_corr": round(float(fs[j]), 4),
            "corr_at_0m": round(score(0.0), 4), "n_px": int(P.sum()),
            "coarse": {"levels": [round(x, 3) for x in levels], "corr": [round(x, 4) for x in scores]},
            "bias": IMAGE_BIAS_NOTE}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _md5(p: Path) -> str:
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    import yaml

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--site", default="jervis_bay")
    p.add_argument("--config", type=Path, default=Path("config/sites.yml"))
    p.add_argument("--scene", required=True)
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--out", type=Path, default=Path("outputs"))
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--gauge-file", type=Path, help="MHL CSV for the gauge in config")
    src.add_argument("--from-image", action="store_true",
                     help="provisional estimate from the image (biased low ~0.1-0.2 m)")
    p.add_argument("--datum", choices=("auto", "ahd", "cd"), default="auto",
                   help="gauge file datum; auto infers it from the record's mean")
    p.add_argument("--time-col"), p.add_argument("--level-col")
    a = p.parse_args(argv)

    site = yaml.safe_load(a.config.read_text(encoding="utf-8"))["sites"][a.site]
    gauge = Gauge.from_config(site["tide_gauge"])
    scene_dir = a.root / "data" / "raw" / "scenes" / a.scene
    prov = json.loads((scene_dir / "provenance.json").read_text(encoding="utf-8"))
    when = datetime.fromisoformat(prov["datetime_utc"].replace("Z", "+00:00"))
    print(f"{a.scene}\n  overpass {when:%Y-%m-%d %H:%M:%S} UTC = "
          f"{when.astimezone(AEST):%H:%M:%S} AEST")

    rec: dict[str, Any] = {"scene": a.scene, "overpass_utc": when.isoformat(),
                           "gauge": vars(gauge)}
    if a.gauge_file:
        t, lv, notes = read_gauge_csv(a.gauge_file, time_col=a.time_col, level_col=a.level_col)
        datum = infer_datum(lv, gauge) if a.datum == "auto" else a.datum
        ahd = to_ahd(lv, datum, gauge)
        at = level_at(t, ahd, when)
        ok = plausible(at["level"], gauge)
        print(f"  gauge {gauge.name} ({gauge.station}): {notes['rows_used']} samples, "
              f"{t[0]} to {t[-1]} UTC\n  datum: {datum.upper()}"
              f"{' (inferred from the record mean)' if a.datum == 'auto' else ' (as given)'}"
              f"\n  level at overpass: {at['level']:+.3f} m AHD (samples {at['gap_before_min']} min "
              f"before, {at['gap_after_min']} after; tide moving {at['tidal_rate_m_per_h']:+.2f} m/h)")
        if not ok:
            print(f"  REFUSED: outside the plausible range [{gauge.islw_ahd - PLAUSIBLE_MARGIN_M:+.2f}, "
                  f"{gauge.hhwss_ahd + PLAUSIBLE_MARGIN_M:+.2f}] m AHD -- check units and datum")
            return 2
        rec.update({"method": "gauge", "water_level_m_ahd": round(at["level"], 3),
                    "status": "measured", "datum_in_file": datum, "interpolation": at,
                    "file": {"path": str(a.gauge_file), "md5": _md5(a.gauge_file), **notes}})
    else:
        from sdb.reference import SCL_CLOUD, SCL_NODATA, plane_translation, read_dem, read_scene

        z, valid, s, s_crs = read_dem(a.root / site["reference_dem"])
        scene = read_scene(scene_dir)
        dst = scene["grid"]
        (tx, ty), _ = plane_translation(s_crs, scene["crs"], s)
        shift = (0.0, 0.0)
        cpath = a.out / f"coreg_{a.scene}.json"
        if cpath.exists():
            c = json.loads(cpath.read_text(encoding="utf-8"))
            if c.get("verdict") == "apply":
                shift = (float(c["shift_m"]["east"]), float(c["shift_m"]["north"]))
        usable = np.isfinite(scene["nir"])
        if "scl" in scene:
            usable &= ~np.isin(scene["scl"], SCL_CLOUD + SCL_NODATA)
        est = image_estimate(z, valid, s.shifted(tx, ty), dst.shifted(*shift), scene["nir"], usable)
        if est["status"] != "ok":
            print(f"  image estimate failed: {est['status']}")
            return 2
        print(f"  image estimate (co-registration {shift[0]:+.2f} E, {shift[1]:+.2f} N applied): "
              f"{est['level_m_ahd']:+.3f} m AHD  (correlation {est['corr_at_0m']:.4f} at 0 m -> "
              f"{est['peak_corr']:.4f}; {est['n_px']:,} shoreline pixels)\n  PROVISIONAL: {IMAGE_BIAS_NOTE}")
        rec.update({"method": "image", "water_level_m_ahd": est["level_m_ahd"],
                    "status": "provisional", "coregistration_applied_m": list(shift), "estimate": est})

    print(f"  tidal planes 2018-19 (m AHD): MSL {gauge.msl_ahd:+.3f}, ISLW {gauge.islw_ahd:+.3f}, "
          f"HHWSS {gauge.hhwss_ahd:+.3f}")
    rec.update({"written_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "sdb_version": __version__})
    a.out.mkdir(parents=True, exist_ok=True)
    jpath = a.out / f"waterlevel_{a.scene}.json"
    jpath.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(f"\n  record -> {jpath}\n  reference.py will use {rec['water_level_m_ahd']:+.3f} m AHD "
          f"({rec['status']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
