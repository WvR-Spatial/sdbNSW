"""Measure how far the image sits from its true position -- before comparing depths.

PRIMARY METHOD (default, `--method ortho`): register the scene against
reference orthoimagery on land -- see sdb/ortho.py. That replaced the method
below after the QGIS gate showed it was ~14 m wrong at Jervis Bay.

DIAGNOSTIC (`--method waterline`): the original steep-shoreline method, kept
because its failure is instructive and its tests pin the geometry. It writes
to a separate record and never feeds reference.py. Its original description:

The 2018 scene predates Sentinel-2's geometric refinement: ESA's July 2018
quality report puts S2A absolute geolocation at ~12 m (95%). A pixel of
misregistration is worth metres of apparent depth error on a sloping seabed, so
the offset is measured, not assumed.

Signal. Near-infrared is bright over land and near zero over water, and at a
shoreline pixel it is close to a linear mix of the two -- in proportion to the
land fraction of the pixel. The lidar gives that land fraction independently.
Slide the lidar across the image, and the offset at which the two agree best is
the misregistration.

Steep shores only. On a 1:20 beach, half a metre of tide error moves the
waterline 10 m -- the size of what is being measured. On a 30 degree cliff it
moves 0.9 m. Only waterline stretches steeper than STEEP_SLOPE_DEG are used,
which makes the estimate nearly independent of the tide at overpass.

Geometry. A straight shoreline only constrains the offset ACROSS it. So the
steep shoreline is split into segments that each face one direction; each
gives the offset along its own normal, by 1-D search; and the 2-D shift is the
least-squares solution across segments facing different ways. Residuals from
that fit are the error bar. If segments disagree, the misregistration is not a
rigid shift (or something else -- shadowed cliffs, whitewater at the cliff
base -- is biasing some of them), and the result says so instead of applying it.

Sign convention. shift = (east, north), metres: the ground position of each
image pixel minus its nominal position. It is applied by aggregating the lidar
onto the scene grid translated by `shift` (reference.py does this). Image
features are therefore drawn at `-shift` from where they really are.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from sdb import __version__
from sdb.reference import (DEFAULT_WATER_LEVEL_M, MIN_COVERAGE, SCL_CLOUD, SCL_NODATA, Grid,
                           LandFractionField, plane_translation, read_dem, read_scene)

# --------------------------------------------------------------------------
# Constants, with reasons
# --------------------------------------------------------------------------

#: Minimum slope at the waterline. tan(30 deg) = 0.58, so a water-level error
#: of dh moves the waterline at most 1.7 dh horizontally.
STEEP_SLOPE_DEG = 30.0

#: Half-width of the band of pixels either side of a segment's waterline over
#: which image and lidar are compared. Wide enough to hold the edge across the
#: whole search range; wider only adds land texture unrelated to the shoreline.
BAND_HALF_WIDTH_PX = 5

#: Search range and step along each segment's normal. Pre-refinement S2A
#: geolocation is ~12 m at 95%, so +/-30 m spans it with room to spare.
SEARCH_M = 30.0
STEP_M = 1.0

#: A segment needs this many 10 m waterline pixels (~200 m of shore) and a
#: correlation peak at least this strong to be used.
MIN_SEGMENT_PX = 20
MIN_PEAK_CORR = 0.5

#: Facing directions are binned this many ways before segments are formed, so
#: each segment has one normal.
N_DIRECTION_BINS = 8

#: Global solution needs at least this many segments, with normals spanning at
#: least this angle, or the 2-D shift is not determined.
MIN_SEGMENTS = 4
MIN_NORMAL_SPREAD_DEG = 60.0

#: Shifts smaller than this are recorded but not applied: below ~0.2 px the
#: correction is within the uncertainty of the aggregation itself.
APPLY_THRESHOLD_M = 2.0

#: Segment residual RMS above which the shift is not treated as rigid.
MAX_RESIDUAL_RMS_M = 5.0

#: Cross-check: the all-shoreline correlation peak is searched this far either
#: side of the steep-shore solution, at this step. It must agree per component
#: within max(AGREE_FLOOR_M, 2 x the steep-shore standard error) -- a
#: conventional 2-sigma rule with a floor for when the formal error is small.
#: Codified after an exploratory all-shore run on the Jervis scene, not tuned
#: to it: that scene passes with a wide margin (see PROJECT_BRIEF).
CHECK_HALF_M = 9.0
CHECK_STEP_M = 3.0
AGREE_FLOOR_M = 3.0


# --------------------------------------------------------------------------
# Pure pieces
# --------------------------------------------------------------------------


def slope_and_normal(z: np.ndarray, valid: np.ndarray, grid: Grid):
    """Slope (deg) and unit uphill normal (east, north) on the DEM grid.

    Uphill points toward land at a shoreline. Central differences; voids give NaN.
    """
    zf = np.where(valid, z, np.nan).astype(np.float32)
    d_row, d_col = np.gradient(zf, grid.dy, grid.dx)
    de, dn = d_col, -d_row              # rows run south, so north is -row
    mag = np.hypot(de, dn)
    with np.errstate(invalid="ignore", divide="ignore"):
        slope = np.degrees(np.arctan(mag))
        ne, nn = de / mag, dn / mag
    return slope, ne, nn


def waterline_cells(z: np.ndarray, valid: np.ndarray, water_level: float) -> np.ndarray:
    """Land cells (z > water level) with a 4-neighbour that is water."""
    land = valid & (z > water_level)
    water = valid & (z <= water_level)
    nb = np.zeros_like(water)
    nb[1:, :] |= water[:-1, :]
    nb[:-1, :] |= water[1:, :]
    nb[:, 1:] |= water[:, :-1]
    nb[:, :-1] |= water[:, 1:]
    return land & nb


@dataclass
class Segment:
    """A stretch of steep shoreline facing one way, on the scene grid."""

    id: int
    rows: np.ndarray
    cols: np.ndarray
    normal: tuple[float, float]         # unit, uphill (toward land): (east, north)
    centroid: tuple[float, float]       # (east, north), metres

    @property
    def facing_deg(self) -> float:
        """Azimuth the shore faces (seaward), clockwise from north."""
        return (math.degrees(math.atan2(-self.normal[0], -self.normal[1]))) % 360.0

    @property
    def n_px(self) -> int:
        return int(self.rows.size)


def steep_shore_segments(z: np.ndarray, valid: np.ndarray, src: Grid, dst: Grid, *,
                         water_level: float, min_slope: float = STEEP_SLOPE_DEG,
                         min_px: int = MIN_SEGMENT_PX,
                         n_bins: int = N_DIRECTION_BINS) -> list[Segment]:
    """Steep waterline on the DEM, mapped to scene pixels and split by facing.

    `src` must be in the scene's coordinates (datum translation applied).
    """
    from scipy import ndimage

    slope, ne, nn = slope_and_normal(z, valid, src)
    wl = waterline_cells(z, valid, water_level)
    with np.errstate(invalid="ignore"):
        steep = wl & (slope >= min_slope) & np.isfinite(ne)
    r, c = np.nonzero(steep)
    e = src.x0 + (c + 0.5) * src.dx
    n = src.y0 - (r + 0.5) * src.dy
    pc = np.floor((e - dst.x0) / dst.dx).astype(int)
    pr = np.floor((dst.y0 - n) / dst.dy).astype(int)
    ok = (pc >= 0) & (pc < dst.nx) & (pr >= 0) & (pr < dst.ny)
    pr, pc, vne, vnn = pr[ok], pc[ok], ne[r[ok], c[ok]], nn[r[ok], c[ok]]

    sum_e = np.zeros(dst.shape, np.float64)
    sum_n = np.zeros(dst.shape, np.float64)
    np.add.at(sum_e, (pr, pc), vne)
    np.add.at(sum_n, (pr, pc), vnn)
    hit = (sum_e != 0) | (sum_n != 0)
    az = np.degrees(np.arctan2(sum_e, sum_n)) % 360.0
    width = 360.0 / n_bins
    bins = np.floor(((az + width / 2) % 360.0) / width).astype(int)

    segs: list[Segment] = []
    for b in range(n_bins):
        m = hit & (bins == b)
        if not m.any():
            continue
        lab, _ = ndimage.label(ndimage.binary_dilation(m), structure=np.ones((3, 3), bool))
        for k, sl in enumerate(ndimage.find_objects(lab), start=1):
            if sl is None:
                continue
            sub = m[sl] & (lab[sl] == k)
            if sub.sum() < min_px:
                continue
            rr, cc = np.nonzero(sub)
            rr, cc = rr + sl[0].start, cc + sl[1].start
            ve, vn = sum_e[rr, cc].sum(), sum_n[rr, cc].sum()
            norm = math.hypot(ve, vn)
            cx, cy = dst.centres()
            segs.append(Segment(len(segs), rr, cc, (ve / norm, vn / norm),
                                (float(cx[cc].mean()), float(cy[rr].mean()))))
    return segs


def pearson(a: np.ndarray, b: np.ndarray) -> float:
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 10:
        return float("nan")
    a, b = a[ok] - a[ok].mean(), b[ok] - b[ok].mean()
    den = math.sqrt(float((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / den) if den > 0 else float("nan")


def segment_offset(seg: Segment, nir: np.ndarray, usable: np.ndarray,
                   z: np.ndarray, valid: np.ndarray, src: Grid, dst: Grid, *,
                   water_level: float, search_m: float = SEARCH_M, step_m: float = STEP_M,
                   band_px: int = BAND_HALF_WIDTH_PX) -> dict[str, Any]:
    """Offset of the image from the lidar along one segment's normal, metres.

    Positive = the image's ground position lies uphill (landward) of nominal.
    """
    from scipy import ndimage

    pad = band_px + int(math.ceil(search_m / dst.dx)) + 2
    r0, r1 = max(seg.rows.min() - pad, 0), min(seg.rows.max() + pad + 1, dst.ny)
    c0, c1 = max(seg.cols.min() - pad, 0), min(seg.cols.max() + pad + 1, dst.nx)
    win = dst.window(r0, c0, r1 - r0, c1 - c0)

    line = np.zeros(win.shape, bool)
    line[seg.rows - r0, seg.cols - c0] = True
    near = ndimage.distance_transform_edt(~line) <= band_px
    P = near & usable[r0:r1, c0:c1]
    nir_w = nir[r0:r1, c0:c1]

    # DEM window: the scene window plus the search range and a cell of margin.
    m = search_m + 2 * max(src.dx, src.dy)
    sc0 = max(int(math.floor((win.x0 - m - src.x0) / src.dx)), 0)
    sc1 = min(int(math.ceil((win.x0 + win.nx * win.dx + m - src.x0) / src.dx)), src.nx)
    sr0 = max(int(math.floor((src.y0 - (win.y0 + m)) / src.dy)), 0)
    sr1 = min(int(math.ceil((src.y0 - (win.y0 - win.ny * win.dy - m)) / src.dy)), src.ny)
    field = LandFractionField(z[sr0:sr1, sc0:sc1], valid[sr0:sr1, sc0:sc1],
                              src.window(sr0, sc0, sr1 - sr0, sc1 - sc0), water_level)

    ts = np.arange(-search_m, search_m + step_m / 2, step_m)
    ne, nn = seg.normal
    corr = np.full(ts.size, np.nan)
    for i, t in enumerate(ts):
        lf, cov = field.on(win.shifted(t * ne, t * nn))
        use = P & (cov >= MIN_COVERAGE)
        if use.sum() >= 20:
            corr[i] = pearson(nir_w[use], lf[use])

    out = {"segment": seg.id, "n_px": seg.n_px, "facing_deg": round(seg.facing_deg, 1),
           "centroid_e": round(seg.centroid[0], 1), "centroid_n": round(seg.centroid[1], 1),
           "normal": [round(ne, 4), round(nn, 4)], "n_band_px": int(P.sum())}
    if not np.isfinite(corr).any():
        return {**out, "offset_m": None, "peak_corr": None, "status": "no valid comparison"}
    i = int(np.nanargmax(corr))
    peak = float(corr[i])
    if i == 0 or i == ts.size - 1 or not (np.isfinite(corr[i - 1]) and np.isfinite(corr[i + 1])):
        return {**out, "offset_m": None, "peak_corr": round(peak, 3), "status": "peak at search edge"}
    a, b, c = corr[i - 1], corr[i], corr[i + 1]
    den = a - 2 * b + c
    frac = 0.5 * (a - c) / den if den < 0 else 0.0
    off = float(ts[i] + frac * step_m)
    status = "ok" if peak >= MIN_PEAK_CORR else "weak correlation"
    return {**out, "offset_m": round(off, 2), "peak_corr": round(peak, 3), "status": status}


def solve_shift(results: Sequence[dict[str, Any]], *,
                min_segments: int = MIN_SEGMENTS,
                min_spread_deg: float = MIN_NORMAL_SPREAD_DEG) -> dict[str, Any]:
    """Least-squares 2-D shift from per-segment normal offsets, with a robust pass.

    Each segment k observes d_k = n_k . s. Segments are the independent units:
    weights are sqrt(pixel count), so one long cliff cannot outvote the rest.
    One outlier pass drops segments beyond 3 robust sigmas (floor 1 m) and refits.
    """
    use = [r for r in results if r.get("status") == "ok" and r.get("offset_m") is not None]

    def fit(rows):
        A = np.array([r["normal"] for r in rows], float)
        d = np.array([r["offset_m"] for r in rows], float)
        w = np.sqrt(np.array([r["n_px"] for r in rows], float))
        w = w / w.mean()
        W = np.diag(w)
        N = A.T @ W @ A
        s = np.linalg.solve(N, A.T @ W @ d)
        res = d - A @ s
        dof = max(len(rows) - 2, 1)
        s2 = float((w * res ** 2).sum() / dof)
        cov = s2 * np.linalg.inv(N)
        return s, res, cov, N

    base = {"n_segments_used": len(use), "segments_dropped": []}
    if len(use) < min_segments:
        return {**base, "verdict": "insufficient",
                "reason": f"{len(use)} usable segments; need {min_segments}"}
    ang = np.array([math.degrees(math.atan2(r["normal"][0], r["normal"][1])) for r in use])
    spread = _max_axial_spread(ang)
    if spread < min_spread_deg:
        return {**base, "verdict": "insufficient",
                "reason": f"segment normals span {spread:.0f} deg; need {min_spread_deg:.0f}"}

    s, res, cov, _ = fit(use)
    sig = 1.4826 * float(np.median(np.abs(res - np.median(res))))
    cut = max(3.0 * sig, 1.0)
    keep = [r for r, e in zip(use, res) if abs(e) <= cut]
    dropped = [r["segment"] for r, e in zip(use, res) if abs(e) > cut]
    if dropped and len(keep) >= min_segments:
        s, res, cov, _ = fit(keep)
        use = keep
    rms = float(np.sqrt(np.mean(res ** 2)))
    se = np.sqrt(np.diag(cov))
    mag = float(math.hypot(*s))
    return {**base, "n_segments_used": len(use), "segments_dropped": dropped,
            "shift_m": {"east": round(float(s[0]), 2), "north": round(float(s[1]), 2)},
            "stderr_m": {"east": round(float(se[0]), 2), "north": round(float(se[1]), 2)},
            "magnitude_m": round(mag, 2), "residual_rms_m": round(rms, 2),
            "normal_spread_deg": round(spread, 0),
            "residuals": {str(r["segment"]): round(float(e), 2) for r, e in zip(use, res)}}


def verdict(sol: dict[str, Any], check: dict[str, Any] | None = None, *,
            apply_threshold: float = APPLY_THRESHOLD_M,
            max_rms: float = MAX_RESIDUAL_RMS_M) -> tuple[str, str]:
    """('apply' | 'negligible' | 'inconsistent' | 'insufficient', reason)."""
    if sol.get("verdict") == "insufficient":
        return "insufficient", sol["reason"]
    if sol["residual_rms_m"] > max_rms:
        return "inconsistent", (f"segments disagree (residual RMS {sol['residual_rms_m']} m > "
                                f"{max_rms} m): not a rigid shift, or some segments are biased")
    se = math.hypot(sol["stderr_m"]["east"], sol["stderr_m"]["north"])
    if sol["magnitude_m"] < max(apply_threshold, 2 * se):
        return "negligible", (f"|shift| {sol['magnitude_m']} m is below "
                              f"max({apply_threshold} m, 2 x stderr {se:.2f} m)")
    if check is not None and not check.get("agrees", False):
        return "inconsistent", ("steep-shore solution and all-shoreline cross-check disagree: "
                                + check.get("reason", "see cross_check"))
    return "apply", (f"|shift| {sol['magnitude_m']} m, consistent across segments"
                     + ("" if check is None else " and with the all-shoreline cross-check"))


def all_shore_check(z: np.ndarray, valid: np.ndarray, src: Grid, dst: Grid,
                    nir: np.ndarray, usable: np.ndarray, centre: tuple[float, float],
                    stderr: tuple[float, float], *, water_level: float,
                    half: float = CHECK_HALF_M, step: float = CHECK_STEP_M,
                    band_px: int = BAND_HALF_WIDTH_PX) -> dict[str, Any]:
    """Independent estimate from the WHOLE shoreline, searched around `centre`.

    Uses every shore, beaches included, as one pooled correlation. Beaches make
    it tide-sensitive, but tide errors push east- and west-facing beaches (and
    north- and south-facing ones) in opposite directions, so they largely
    cancel -- and it constrains directions the steep shores cannot. Agreement
    is the test; its peak is not applied.
    """
    from scipy import ndimage

    field = LandFractionField(z, valid, src, water_level)
    lf0, cov0 = field.on(dst.shifted(*centre))
    mixed = (lf0 > 0) & (lf0 < 1) & (cov0 >= MIN_COVERAGE)
    margin = int(math.ceil(half / dst.dx)) + 1
    P = ((ndimage.distance_transform_edt(~mixed) <= band_px) & usable
         & ndimage.binary_erosion(cov0 >= MIN_COVERAGE, iterations=margin))
    offs = np.arange(-half, half + step / 2, step)
    C = np.full((offs.size, offs.size), np.nan)
    for i, dn in enumerate(offs):
        for j, de in enumerate(offs):
            lf, _ = field.on(dst.shifted(centre[0] + de, centre[1] + dn))
            C[i, j] = pearson(nir[P], lf[P])
    lf, _ = field.on(dst)
    corr_nominal = pearson(nir[P], lf[P])

    i, j = np.unravel_index(np.nanargmax(C), C.shape)
    on_edge = i in (0, offs.size - 1) or j in (0, offs.size - 1)

    def refine(a, b, c):
        den = a - 2 * b + c
        return 0.5 * (a - c) / den * step if den < 0 else 0.0

    pe = centre[0] + offs[j] + (0.0 if on_edge else refine(C[i, j - 1], C[i, j], C[i, j + 1]))
    pn = centre[1] + offs[i] + (0.0 if on_edge else refine(C[i - 1, j], C[i, j], C[i + 1, j]))
    tol = (max(AGREE_FLOOR_M, 2 * stderr[0]), max(AGREE_FLOOR_M, 2 * stderr[1]))
    de, dn = pe - centre[0], pn - centre[1]
    agrees = (not on_edge) and abs(de) <= tol[0] and abs(dn) <= tol[1]
    reason = ("peak at the edge of the search window" if on_edge else
              f"differs by E {de:+.1f}, N {dn:+.1f} m; tolerance E {tol[0]:.1f}, N {tol[1]:.1f} m")
    return {"peak_m": {"east": round(float(pe), 2), "north": round(float(pn), 2)},
            "peak_corr": round(float(C[i, j]), 4), "corr_at_nominal": round(float(corr_nominal), 4),
            "tolerance_m": {"east": round(tol[0], 2), "north": round(tol[1], 2)},
            "difference_m": {"east": round(float(de), 2), "north": round(float(dn), 2)},
            "n_px": int(P.sum()), "agrees": bool(agrees), "reason": reason}


def _max_axial_spread(angles_deg: np.ndarray) -> float:
    """Largest angle between any two normals, 0-180 deg."""
    a = np.radians(angles_deg)
    v = np.stack([np.cos(a), np.sin(a)], 1)
    cosang = np.clip(v @ v.T, -1, 1)
    return float(np.degrees(np.arccos(cosang)).max())


def estimate_shift(z: np.ndarray, valid: np.ndarray, src: Grid, dst: Grid,
                   nir: np.ndarray, usable: np.ndarray, *,
                   water_level: float = DEFAULT_WATER_LEVEL_M,
                   min_slope: float = STEEP_SLOPE_DEG, min_px: int = MIN_SEGMENT_PX,
                   cross_check: bool = True) -> dict[str, Any]:
    """The whole measurement: segments -> per-segment offsets -> 2-D shift ->
    all-shoreline cross-check -> verdict."""
    segs = steep_shore_segments(z, valid, src, dst, water_level=water_level,
                                min_slope=min_slope, min_px=min_px)
    results = [segment_offset(s, nir, usable, z, valid, src, dst, water_level=water_level)
               for s in segs]
    sol = solve_shift(results)
    check = None
    if cross_check and "shift_m" in sol:
        check = all_shore_check(z, valid, src, dst, nir, usable,
                                (sol["shift_m"]["east"], sol["shift_m"]["north"]),
                                (sol["stderr_m"]["east"], sol["stderr_m"]["north"]),
                                water_level=water_level)
    v, why = verdict(sol, check)
    return {"verdict": v, "reason": why, **sol, "cross_check": check, "segments": results}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _plot(path: Path, nir: np.ndarray, dst: Grid, rec: dict[str, Any]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 8.5), facecolor="#0f172a")
    lo, hi = np.nanpercentile(nir, [2, 98])
    ext = (dst.x0, dst.x0 + dst.nx * dst.dx, dst.y0 - dst.ny * dst.dy, dst.y0)
    ax.imshow(np.clip((nir - lo) / (hi - lo), 0, 1), cmap="gray", extent=ext, interpolation="nearest")
    scale = 25.0                     # arrows exaggerated for visibility
    resid = rec.get("residuals", {})
    for s in rec["segments"]:
        if s["offset_m"] is None:
            ax.plot(s["centroid_e"], s["centroid_n"], "x", color="#64748b", ms=4)
            continue
        used = str(s["segment"]) in resid
        col = "#e0a458" if used else "#94a3b8"
        ax.arrow(s["centroid_e"], s["centroid_n"], s["normal"][0] * s["offset_m"] * scale,
                 s["normal"][1] * s["offset_m"] * scale, color=col, width=25, head_width=110,
                 length_includes_head=True)
    title = f"{rec['scene']} — per-segment offsets (x{scale:.0f})"
    if "shift_m" in rec:
        title += (f"\nshift E {rec['shift_m']['east']:+.1f} ± {rec['stderr_m']['east']:.1f}, "
                  f"N {rec['shift_m']['north']:+.1f} ± {rec['stderr_m']['north']:.1f} m   "
                  f"verdict: {rec['verdict']}")
    ax.set_title(title, color="#e2e8f0", fontsize=9)
    ax.tick_params(colors="#94a3b8", labelsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor="#0f172a")
    plt.close(fig)


def _plot_ortho(path: Path, nir: np.ndarray, dst: Grid, rec: dict[str, Any]) -> None:
    """Scene NIR with each window and its shift (exaggerated). No orthophoto is drawn."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    fig, ax = plt.subplots(figsize=(7.5, 8.5), facecolor="#0f172a")
    lo, hi = np.nanpercentile(nir, [2, 98])
    ext = (dst.x0, dst.x0 + dst.nx * dst.dx, dst.y0 - dst.ny * dst.dy, dst.y0)
    ax.imshow(np.clip((nir - lo) / (hi - lo), 0, 1), cmap="gray", extent=ext, interpolation="nearest")
    scale = 100.0
    for w in rec["windows"]:
        x0, y0, x1, y1 = w["bbox"]
        used = w.get("status") == "ok" and w["window"] not in rec.get("windows_dropped", [])
        col = "#e0a458" if used else "#64748b"
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=col, lw=1.2))
        if w.get("shift_e") is not None:
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            ax.arrow(cx, cy, w["shift_e"] * scale, w["shift_n"] * scale, color=col, width=30,
                     head_width=140, length_includes_head=True)
    title = f"{rec['scene']} — co-registration against NSW orthoimagery (arrows x{scale:.0f})"
    if "shift_m" in rec:
        title += (f"\nshift E {rec['shift_m']['east']:+.1f} ± {rec['stderr_m']['east']:.1f}, "
                  f"N {rec['shift_m']['north']:+.1f} ± {rec['stderr_m']['north']:.1f} m   "
                  f"verdict: {rec['verdict']}")
    ax.set_title(title, color="#e2e8f0", fontsize=9)
    ax.tick_params(colors="#94a3b8", labelsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor="#0f172a")
    plt.close(fig)


def _run_ortho(a, site_cfg: dict[str, Any]) -> int:
    from sdb import ortho as O

    scene = read_scene(a.root / "data" / "raw" / "scenes" / a.scene)
    dst = scene["grid"]
    g = O.grey(scene["blue"], scene["green"], scene["red"])
    with np.errstate(invalid="ignore"):
        land = np.isfinite(g) & (scene["nir"] > 0.05)
    if "scl" in scene:
        land &= ~np.isin(scene["scl"], O.SCL_EXCLUDE)
    wins = O.select_windows(land, g, dst, n=a.windows, window_m=a.window_km * 1000.0)
    cache = a.root / "data" / "raw" / "ortho" / a.site
    print(f"{a.scene}\n  reference: NSW Imagery (Spatial Services), {O.ORTHO_RES_M:g} m, "
          f"cached in {cache}\n  {len(wins)} land windows of {a.window_km:g} km; "
          f"search +/-{O.SEARCH_M:g} m\n")

    results = []
    for w in wins:
        png = O.fetch_window(O.fetch_bbox(w), O.ORTHO_RES_M, cache)
        img, og = O.load_window(png)
        k = w["size_px"]
        r0, c0 = w["row0"], w["col0"]
        res = O.register_window(g[r0:r0 + k, c0:c0 + k], dst.window(r0, c0, k, k),
                                land[r0:r0 + k, c0:c0 + k], img, og)
        res.update({"window": w["id"], "bbox": w["bbox"], "land_frac": w["land_frac"],
                    "texture": w["texture"], "ortho": png.name})
        results.append(res)

    sol = O.combine(results)
    rec = {"scene": a.scene, "method": "ortho", **sol, "windows": results}

    print(f"  {'win':>3} {'centre E, N':>18} {'shift E':>8} {'shift N':>8} {'corr':>6} {'at 0':>6}  status")
    for r in results:
        cx = (r["bbox"][0] + r["bbox"][2]) / 2
        cy = (r["bbox"][1] + r["bbox"][3]) / 2
        se = "--" if r.get("shift_e") is None else f"{r['shift_e']:+.1f}"
        sn = "--" if r.get("shift_n") is None else f"{r['shift_n']:+.1f}"
        pc = "--" if r.get("peak_corr") is None else f"{r['peak_corr']:.2f}"
        cz = "--" if r.get("corr_at_zero") is None else f"{r['corr_at_zero']:.2f}"
        st = r["status"] + (" (dropped)" if r["window"] in sol.get("windows_dropped", []) else "")
        print(f"  {r['window']:>3} {cx:>9.0f},{cy:>8.0f} {se:>8} {sn:>8} {pc:>6} {cz:>6}  {st}")
    print()
    if "shift_m" in sol:
        print(f"  shift: E {sol['shift_m']['east']:+.2f} ± {sol['stderr_m']['east']:.2f} m, "
              f"N {sol['shift_m']['north']:+.2f} ± {sol['stderr_m']['north']:.2f} m   "
              f"(|shift| {sol['magnitude_m']} m; {sol['n_windows_ok']} windows, scatter "
              f"E {sol['scatter_m']['east']}, N {sol['scatter_m']['north']} m; "
              f"reference datum ambiguity ~{O.DATUM_AMBIGUITY_M:g} m)")
    print(f"  verdict: {sol['verdict'].upper()} -- {sol['reason']}")

    a.out.mkdir(parents=True, exist_ok=True)
    rec.update({
        "reference": {"service": O.SERVICE_URL, "attribution": O.ATTRIBUTION, "use": O.USE_NOTE,
                      "resolution_m": O.ORTHO_RES_M, "cache": str(cache)},
        "params": {"window_m": a.window_km * 1000.0, "n_windows": a.windows,
                   "min_land_frac": O.MIN_LAND_FRAC,
                   "min_spacing_m": O.SPACING_FACTOR * a.window_km * 1000.0, "search_m": O.SEARCH_M,
                   "coarse_step_m": O.COARSE_STEP_M, "fine_step_m": O.FINE_STEP_M,
                   "psf_sigma_px": O.PSF_SIGMA_PX, "min_window_corr": O.MIN_WINDOW_CORR,
                   "min_windows": O.MIN_WINDOWS, "max_scatter_m": O.MAX_SCATTER_M,
                   "apply_threshold_m": O.APPLY_THRESHOLD_M},
        "sign_convention": "shift = ground position of image pixel minus nominal; "
                           "apply by aggregating the reference onto the scene grid translated by shift",
        "written_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sdb_version": __version__,
    })
    jpath = a.out / f"coreg_{a.scene}.json"
    jpath.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    png = a.out / f"coreg_{a.scene}.png"
    _plot_ortho(png, scene["nir"], dst, rec)
    print(f"\n  record -> {jpath}\n  figure -> {png}")
    if rec["verdict"] == "apply":
        print("  reference.py will apply this shift (default --coreg auto).")
    return 0


def _run_waterline(a, site_cfg: dict[str, Any]) -> int:
    z, valid, src, src_crs = read_dem(a.root / site_cfg["reference_dem"])
    scene = read_scene(a.root / "data" / "raw" / "scenes" / a.scene)
    dst = scene["grid"]
    (tx, ty), datum = plane_translation(src_crs, scene["crs"], src)
    src = src.shifted(tx, ty)

    nir = scene["nir"]
    usable = np.isfinite(nir)
    if "scl" in scene:
        usable &= ~np.isin(scene["scl"], SCL_CLOUD + SCL_NODATA)

    print(f"{a.scene}\n  DIAGNOSTIC ONLY -- waterline method (superseded; never applied)\n"
          f"  steep shoreline >= {a.min_slope:g} deg at water level "
          f"{a.water_level:+.2f} m AHD; search +/-{SEARCH_M:g} m along each normal\n")
    rec = estimate_shift(z, valid, src, dst, nir, usable, water_level=a.water_level,
                         min_slope=a.min_slope, min_px=a.min_px,
                         cross_check=not a.no_cross_check)
    rec = {"scene": a.scene, "method": "waterline (diagnostic)", **rec}

    resid = rec.get("residuals", {})
    print(f"  {'seg':>4} {'faces':>6} {'px':>5} {'offset m':>9} {'corr':>6} {'resid m':>8}  status")
    for s in rec["segments"]:
        off = "--" if s["offset_m"] is None else f"{s['offset_m']:+.1f}"
        cor = "--" if s["peak_corr"] is None else f"{s['peak_corr']:.2f}"
        rs = resid.get(str(s["segment"]))
        rs = "--" if rs is None else f"{rs:+.1f}"
        st = s["status"] + (" (dropped)" if s["segment"] in rec.get("segments_dropped", []) else "")
        print(f"  {s['segment']:>4} {s['facing_deg']:>5.0f}° {s['n_px']:>5} {off:>9} {cor:>6} {rs:>8}  {st}")
    print()
    if "shift_m" in rec:
        print(f"  shift: E {rec['shift_m']['east']:+.2f} ± {rec['stderr_m']['east']:.2f} m, "
              f"N {rec['shift_m']['north']:+.2f} ± {rec['stderr_m']['north']:.2f} m")
    print(f"  diagnostic verdict: {rec['verdict']} -- {rec['reason']}")

    a.out.mkdir(parents=True, exist_ok=True)
    rec.update({"water_level_m_ahd": a.water_level, "datum": datum,
                "note": "Diagnostic only. Biased at Jervis Bay by shadowed cliffs, whitewater "
                        "and low-tide beaches; see PROJECT_BRIEF. Not read by reference.py.",
                "written_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "sdb_version": __version__})
    jpath = a.out / f"coreg_{a.scene}_waterline.json"
    jpath.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    _plot(a.out / f"coreg_{a.scene}_waterline.png", nir, dst, rec)
    print(f"\n  record -> {jpath}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    import yaml

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--site", default="jervis_bay")
    p.add_argument("--config", type=Path, default=Path("config/sites.yml"))
    p.add_argument("--scene", required=True)
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--out", type=Path, default=Path("outputs"))
    p.add_argument("--method", choices=("ortho", "waterline"), default="ortho",
                   help="ortho (default): register against orthoimagery on land. "
                        "waterline: the superseded shoreline method, as a diagnostic")
    p.add_argument("--windows", type=int, default=12, help="ortho: number of land windows")
    p.add_argument("--window-km", type=float, default=2.0, help="ortho: window size, km")
    p.add_argument("--water-level", type=float, default=DEFAULT_WATER_LEVEL_M,
                   help="waterline only")
    p.add_argument("--min-slope", type=float, default=STEEP_SLOPE_DEG, help="waterline only")
    p.add_argument("--min-px", type=int, default=MIN_SEGMENT_PX, help="waterline only")
    p.add_argument("--no-cross-check", action="store_true", help="waterline only")
    a = p.parse_args(argv)

    site_cfg = yaml.safe_load(a.config.read_text(encoding="utf-8"))["sites"][a.site]
    return _run_ortho(a, site_cfg) if a.method == "ortho" else _run_waterline(a, site_cfg)


if __name__ == "__main__":
    sys.exit(main())
