"""Co-register the scene against reference orthoimagery, on land.

Why this, not the shoreline. The first co-registration read the waterline and
was ~14 m wrong at Jervis Bay: shadowed cliffs, whitewater at cliff bases and
low-tide beaches all displaced the image's apparent shoreline the same way.
Land features -- runways, roads, clearings, street grids -- carry none of that
water-edge physics. Matched against an independent orthophoto, they measure
the image's georeferencing directly.

Method, per window:
  1. Windows are chosen automatically: 2 km tiles of the scene that are almost
     all land, cloud-free, and rich in texture, spread across the scene.
  2. The orthophoto for each window is fetched once from the NSW Spatial
     Services Export Map endpoint, in the scene's own CRS, and cached.
  3. The orthophoto is aggregated onto the scene grid by exact area weighting
     (reference.block_sum) -- the grid translated by a trial shift -- and
     blurred slightly for the sensor's point-spread function.
  4. Both images become gradient magnitude, so that different dates, sensors
     and radiometry matter less than where the edges are, and are correlated.
  5. Coarse-then-fine search over shifts, sub-sample peak by quadratic fit.
Across windows: the median shift, window-to-window scatter as the error bar.

Sign convention -- identical to the waterline method: shift = (east, north),
the ground position of each image pixel minus its nominal position. Apply by
aggregating the reference onto the scene grid translated by `shift`.

Licence. The NSW Imagery service is listed as CC BY 3.0 AU in the national
catalogue, but Spatial Services' copyright page excludes images from its
Creative Commons licence and parts of the mosaic are third-party. It is used
here only as a positional reference: tiles stay in gitignored data/raw/, only
derived numbers are committed, and no figure reproduces the imagery.

Datum. The service is Web Mercator on WGS84; the underlying orthophotos may be
GDA94 treated as WGS84. That is a ~1.5 m ambiguity, carried as a systematic
term (DATUM_AMBIGUITY_M) rather than hidden.

Network access is confined to `fetch_window`, which uses only the standard
library so it also runs inside QGIS's Python.
"""

from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

# --------------------------------------------------------------------------
# Constants, with reasons
# --------------------------------------------------------------------------

SERVICE_URL = ("https://maps.six.nsw.gov.au/arcgis/rest/services/public/"
               "NSW_Imagery/MapServer/export")
ATTRIBUTION = ("NSW Imagery (c) State of New South Wales (Spatial Services, "
               "Department of Customer Service NSW)")
USE_NOTE = ("Positional reference only; imagery not redistributed. Catalogue licence "
            "CC BY 3.0 AU; Spatial Services' copyright page excludes images.")

#: Window size and orthophoto resolution. 2 km holds a runway or a street grid;
#: 2 m gives 25 reference cells per 10 m pixel, so trial shifts well below a
#: metre are represented by the exact aggregation rather than by interpolation.
WINDOW_M = 2000.0
ORTHO_RES_M = 2.0

#: Window selection. A window must be almost all land -- water differs between
#: dates and carries glint and waves -- and far enough from the others that the
#: windows sample the whole scene rather than one neighbourhood.
N_WINDOWS = 12
MIN_LAND_FRAC = 0.90
SPACING_FACTOR = 1.5          # window centres at least 1.5 window widths apart

#: Search. Pre-refinement S2A geolocation is ~12 m at 95%; +/-30 m spans it.
SEARCH_M = 30.0
COARSE_STEP_M = 3.0
FINE_HALF_M = 3.0
FINE_STEP_M = 0.5

#: Sentinel-2's point-spread function is wider than its 10 m pixel; the box-
#: aggregated orthophoto is blurred by this much (pixels) to resemble it.
PSF_SIGMA_PX = 0.5

#: A window's result is used only if its correlation peak is at least this
#: strong. Gradient images from different dates and sensors correlate modestly
#: even when perfectly aligned; this rejects windows with no common structure.
MIN_WINDOW_CORR = 0.3

#: Across windows: at least this many, scatter (robust sigma) no larger than
#: this per component, or the result is not a single rigid shift.
MIN_WINDOWS = 4
MAX_SCATTER_M = 4.0

#: Apply threshold, as in the waterline method.
APPLY_THRESHOLD_M = 2.0

#: Possible GDA94-as-WGS84 offset in the reference service. Reported, not fitted.
DATUM_AMBIGUITY_M = 1.5

SCL_WATER = 6
SCL_EXCLUDE = (0, 1, 3, 6, 8, 9, 10)     # nodata, defective, shadow, water, cloud


# --------------------------------------------------------------------------
# Fetch and cache (standard library only)
# --------------------------------------------------------------------------


def window_filename(bbox: Sequence[float], res: float) -> str:
    x0, y0, x1, y1 = bbox
    return f"E{x0:.0f}_N{y0:.0f}_{x1 - x0:.0f}x{y1 - y0:.0f}m_{res:g}m"


def fetch_window(bbox: Sequence[float], res: float, out_dir: Path, *, epsg: int = 32756,
                 url: str = SERVICE_URL, timeout: float = 60.0, retries: int = 3,
                 opener: Callable[..., Any] | None = None) -> Path:
    """Fetch one orthophoto window in `epsg`, write PNG + JSON sidecar, return the PNG path.

    Asks for the extent first (f=json) to confirm the server will honour it --
    it may adjust extents whose aspect ratio does not match the image size --
    then fetches the image itself. Cached: an existing PNG is not refetched.
    """
    opener = opener or urllib.request.urlopen
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = window_filename(bbox, res)
    png, side = out_dir / f"{stem}.png", out_dir / f"{stem}.json"
    if png.exists() and side.exists():
        return png

    x0, y0, x1, y1 = bbox
    w, h = int(round((x1 - x0) / res)), int(round((y1 - y0) / res))
    params = {"bbox": f"{x0},{y0},{x1},{y1}", "bboxSR": epsg, "imageSR": epsg,
              "size": f"{w},{h}", "format": "png24", "transparent": "false"}

    def get(p: dict[str, Any]) -> bytes:
        last = None
        for attempt in range(retries):
            try:
                with opener(url + "?" + urllib.parse.urlencode(p), timeout=timeout) as r:
                    return r.read()
            except Exception as exc:          # noqa: BLE001 -- retried, then re-raised
                last = exc
                time.sleep(2 ** attempt)
        raise RuntimeError(f"orthophoto request failed after {retries} attempts: {last}")

    meta = json.loads(get({**params, "f": "json"}).decode("utf-8"))
    ext = meta.get("extent", {})
    got = (ext.get("xmin"), ext.get("ymin"), ext.get("xmax"), ext.get("ymax"))
    if None in got or max(abs(a - b) for a, b in zip(got, bbox)) > 0.01 or \
            (meta.get("width"), meta.get("height")) != (w, h):
        raise RuntimeError(f"server would not honour the requested extent: asked {bbox} "
                           f"{w}x{h}, offered {got} {meta.get('width')}x{meta.get('height')}")
    data = get({**params, "f": "image"})
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"expected a PNG, got {data[:60]!r}")
    pw, ph = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if (pw, ph) != (w, h):
        raise RuntimeError(f"PNG is {pw}x{ph}, expected {w}x{h}")
    png.write_bytes(data)
    side.write_text(json.dumps({
        "bbox": list(bbox), "epsg": epsg, "size": [w, h], "resolution_m": res,
        "service": url, "attribution": ATTRIBUTION, "use": USE_NOTE,
        "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8")
    return png


def load_window(png: Path):
    """(grey image float32, Grid) from a cached window."""
    from PIL import Image

    from sdb.reference import Grid

    meta = json.loads(Path(png).with_suffix(".json").read_text(encoding="utf-8"))
    x0, y0, x1, y1 = meta["bbox"]
    w, h = meta["size"]
    img = np.asarray(Image.open(png).convert("RGB"), dtype=np.float32)
    if img.shape[:2] != (h, w):
        raise ValueError(f"{png.name}: image is {img.shape[1]}x{img.shape[0]}, sidecar says {w}x{h}")
    return img.mean(axis=2), Grid(x0, y1, (x1 - x0) / w, (y1 - y0) / h, w, h)


# --------------------------------------------------------------------------
# Window selection (pure)
# --------------------------------------------------------------------------


def grey(blue: np.ndarray, green: np.ndarray, red: np.ndarray) -> np.ndarray:
    return ((blue + green + red) / 3.0).astype(np.float32)


def gradient(img: np.ndarray) -> np.ndarray:
    from scipy import ndimage
    return np.hypot(ndimage.sobel(img, 0), ndimage.sobel(img, 1))


def select_windows(land: np.ndarray, s2grey: np.ndarray, grid, *, window_m: float = WINDOW_M,
                   n: int = N_WINDOWS, min_land: float = MIN_LAND_FRAC,
                   min_spacing: float | None = None, margin_m: float = SEARCH_M) -> list[dict]:
    """Land-dominated, textured, well-spread windows on the scene grid.

    Tiles are placed so that each keeps `margin_m` of scene around it, which the
    shifted aggregation needs. Texture is mean gradient magnitude over land.
    """
    if min_spacing is None:
        min_spacing = SPACING_FACTOR * window_m
    k = int(round(window_m / grid.dx))
    m = int(math.ceil(margin_m / grid.dx)) + 2
    g = gradient(np.nan_to_num(s2grey))
    cands = []
    for r0 in range(m, grid.ny - k - m + 1, k):
        for c0 in range(m, grid.nx - k - m + 1, k):
            lm = land[r0:r0 + k, c0:c0 + k]
            frac = float(lm.mean())
            if frac < min_land:
                continue
            tex = float(g[r0:r0 + k, c0:c0 + k][lm].mean())
            x0 = grid.x0 + c0 * grid.dx
            y1 = grid.y0 - r0 * grid.dy
            cands.append({"row0": r0, "col0": c0, "size_px": k, "land_frac": round(frac, 3),
                          "texture": tex, "bbox": [x0, y1 - k * grid.dy, x0 + k * grid.dx, y1]})
    cands.sort(key=lambda d: -d["texture"])
    chosen: list[dict] = []
    for c in cands:
        cx, cy = (c["bbox"][0] + c["bbox"][2]) / 2, (c["bbox"][1] + c["bbox"][3]) / 2
        if all(math.hypot(cx - (d["bbox"][0] + d["bbox"][2]) / 2,
                          cy - (d["bbox"][1] + d["bbox"][3]) / 2) >= min_spacing for d in chosen):
            chosen.append(c)
        if len(chosen) == n:
            break
    for i, c in enumerate(chosen):
        c["id"] = i
        c["texture"] = round(c["texture"], 5)
    return chosen


def fetch_bbox(win: dict, margin_m: float = SEARCH_M, pad_m: float = 10.0) -> list[float]:
    """Orthophoto extent for a window: the tile plus the search margin."""
    x0, y0, x1, y1 = win["bbox"]
    e = margin_m + pad_m
    return [x0 - e, y0 - e, x1 + e, y1 + e]


# --------------------------------------------------------------------------
# Registration (pure)
# --------------------------------------------------------------------------


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    den = math.sqrt(float((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / den) if den > 0 else float("nan")


def register_window(s2grey_win: np.ndarray, win_grid, valid: np.ndarray,
                    ortho: np.ndarray, ortho_grid, *, search_m: float = SEARCH_M,
                    coarse: float = COARSE_STEP_M, fine_half: float = FINE_HALF_M,
                    fine: float = FINE_STEP_M, psf_sigma: float = PSF_SIGMA_PX) -> dict[str, Any]:
    """Shift of one scene window relative to its orthophoto, metres (see sign convention)."""
    from scipy import ndimage

    from sdb.reference import area_weights, block_sum

    ov = np.ones_like(ortho, dtype=np.float64)
    og = ortho.astype(np.float64)
    gs2 = gradient(np.nan_to_num(s2grey_win.astype(np.float64)))
    edge = np.zeros(valid.shape, bool)
    edge[2:-2, 2:-2] = True
    use = valid & edge
    if use.sum() < 200:
        return {"status": "too few valid pixels", "n_px": int(use.sum())}
    a = gs2[use]

    cache: dict[tuple[float, float], float] = {}

    def corr(de: float, dn: float) -> float:
        key = (round(de, 3), round(dn, 3))
        if key not in cache:
            wy, wx = area_weights(ortho_grid, win_grid.shifted(de, dn))
            w = block_sum(ov, wy, wx)
            with np.errstate(invalid="ignore", divide="ignore"):
                r = block_sum(og, wy, wx) / w
            if not np.all(w[use] > 0.999 * win_grid.dx * win_grid.dy):
                cache[key] = float("nan")           # trial shift ran off the orthophoto
            else:
                g = gradient(ndimage.gaussian_filter(r, psf_sigma))
                cache[key] = _pearson(a, g[use])
        return cache[key]

    def best_on(xs, ys):
        vals = np.array([[corr(x, y) for x in xs] for y in ys])
        if not np.isfinite(vals).any():
            return None
        i, j = np.unravel_index(np.nanargmax(vals), vals.shape)
        return xs[j], ys[i], vals

    grid_c = np.arange(-search_m, search_m + coarse / 2, coarse)
    r = best_on(grid_c, grid_c)
    if r is None:
        return {"status": "no valid comparison", "n_px": int(use.sum())}
    ce, cn, _ = r
    on_edge = abs(ce) >= search_m - 1e-6 or abs(cn) >= search_m - 1e-6
    fx = np.arange(ce - fine_half, ce + fine_half + fine / 2, fine)
    fy = np.arange(cn - fine_half, cn + fine_half + fine / 2, fine)
    fe, fn, vals = best_on(fx, fy)
    i = int(np.where(np.isclose(fy, fn))[0][0])
    j = int(np.where(np.isclose(fx, fe))[0][0])
    de = dn = 0.0
    if 0 < i < len(fy) - 1 and 0 < j < len(fx) - 1:
        v = vals[i - 1:i + 2, j - 1:j + 2]
        if np.isfinite(v).all():
            de = _quad_offset(v[1, 0], v[1, 1], v[1, 2]) * fine
            dn = _quad_offset(v[0, 1], v[1, 1], v[2, 1]) * fine
    peak = float(vals[i, j])
    status = ("peak at search edge" if on_edge else
              "weak correlation" if peak < MIN_WINDOW_CORR else "ok")
    return {"shift_e": round(float(fe + de), 2), "shift_n": round(float(fn + dn), 2),
            "peak_corr": round(peak, 3), "corr_at_zero": round(corr(0.0, 0.0), 3),
            "n_px": int(use.sum()), "status": status}


def _quad_offset(a: float, b: float, c: float) -> float:
    den = a - 2 * b + c
    return float(np.clip(0.5 * (a - c) / den, -0.5, 0.5)) if den < 0 else 0.0


def combine(results: Sequence[dict[str, Any]], *, min_windows: int = MIN_WINDOWS,
            max_scatter: float = MAX_SCATTER_M,
            apply_threshold: float = APPLY_THRESHOLD_M) -> dict[str, Any]:
    """Median shift across windows, robust scatter, one outlier pass, verdict."""
    ok = [r for r in results if r.get("status") == "ok"]
    base = {"n_windows_ok": len(ok), "windows_dropped": []}
    if len(ok) < min_windows:
        return {**base, "verdict": "insufficient",
                "reason": f"{len(ok)} usable windows; need {min_windows}"}

    def stats(rows):
        e = np.array([r["shift_e"] for r in rows])
        n = np.array([r["shift_n"] for r in rows])
        me, mn = float(np.median(e)), float(np.median(n))
        se_ = 1.4826 * float(np.median(np.abs(e - me)))
        sn_ = 1.4826 * float(np.median(np.abs(n - mn)))
        return e, n, me, mn, se_, sn_

    e, n, me, mn, sig_e, sig_n = stats(ok)
    cut_e, cut_n = 3 * max(sig_e, 1.0), 3 * max(sig_n, 1.0)
    keep = [r for r, a, b in zip(ok, e, n) if abs(a - me) <= cut_e and abs(b - mn) <= cut_n]
    dropped = [r["window"] for r, a, b in zip(ok, e, n)
               if not (abs(a - me) <= cut_e and abs(b - mn) <= cut_n)]
    if dropped and len(keep) >= min_windows:
        ok = keep
        e, n, me, mn, sig_e, sig_n = stats(ok)
    k = len(ok)
    stderr = (1.2533 * max(sig_e, 0.1) / math.sqrt(k), 1.2533 * max(sig_n, 0.1) / math.sqrt(k))
    mag = math.hypot(me, mn)
    out = {**base, "n_windows_ok": k, "windows_dropped": dropped,
           "shift_m": {"east": round(me, 2), "north": round(mn, 2)},
           "stderr_m": {"east": round(stderr[0], 2), "north": round(stderr[1], 2)},
           "scatter_m": {"east": round(sig_e, 2), "north": round(sig_n, 2)},
           "magnitude_m": round(mag, 2), "datum_ambiguity_m": DATUM_AMBIGUITY_M}
    if sig_e > max_scatter or sig_n > max_scatter:
        return {**out, "verdict": "inconsistent",
                "reason": f"windows disagree (scatter E {sig_e:.1f}, N {sig_n:.1f} m > {max_scatter} m)"}
    se = math.hypot(*stderr)
    if mag < max(apply_threshold, 2 * se):
        return {**out, "verdict": "negligible",
                "reason": f"|shift| {mag:.2f} m below max({apply_threshold} m, 2 x stderr {se:.2f} m)"}
    return {**out, "verdict": "apply",
            "reason": f"|shift| {mag:.2f} m; {k} windows agree (scatter E {sig_e:.1f}, N {sig_n:.1f} m)"}
