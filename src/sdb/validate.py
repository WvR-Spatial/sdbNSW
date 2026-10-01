"""Out-of-fold validation of Stumpf SDB against the lidar, as pre-registered.

Implements the *Validation*, *Statistics* and *Breakdown depth* parts of the
Phase 2 protocol in PROJECT_BRIEF.md. The defaults below ARE the protocol:
running with anything else is recorded in the output as a deviation.

Why blocked folds: neighbouring pixels share seabed, water and atmosphere, so a
model tested on pixels next to the ones it was fitted on is partly tested on its
training data. Whole 2 km blocks are held out instead. A two-parameter Stumpf
line cannot memorise location, so blocked and random splits should agree here;
the random split is reported alongside as the control for later, flexible
models. Each pixel's prediction is the mean of its out-of-fold predictions over
10 repeats -- none from a model that saw its block.

Error is e = SDB - lidar: positive means the SDB reads too deep, the direction
that matters to anyone navigating by it.

    python -m sdb.validate --scene S2A_56HKG_20180907_0_L2A
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from sdb import __version__
from sdb.reference import (DEPTH_BANDS_M, FLAG_BRIGHT_WATER, FLAG_CLOUD, FLAG_DEPTH,
                           FLAG_LAND, FLAG_NO_IMAGE, FLAG_NO_LIDAR, md5, read_scene,
                           write_layers)
from sdb.sdb import calibrate, stumpf_ratio

# --------------------------------------------------------------------------
# Pre-registered constants
# --------------------------------------------------------------------------

BLOCK_M = 2000.0
N_FOLDS = 5
N_REPEATS = 10
#: Block sizes for the block-size curve; 0 means a random pixel-level split.
BLOCK_CURVE_M = (0.0, 500.0, 1000.0, 2000.0, 4000.0)
#: Fold assignment for repeat r uses seed r; calibration sampling seed CAL_SEED + r.
CAL_SEED = 1000
FINAL_SEED = 2018
N_BOOT = 1000
BOOT_SEED = 7
CORR_LAGS_M = (10, 20, 50, 100, 200, 500, 1000, 2000, 4000, 8000)
CORR_PAIRS = 20000
CORR_SEED = 11
#: Residual correlogram "range": the shortest lag at which r falls below this.
CORR_RANGE_R = 0.1
#: IHO CATZOC depth accuracy at 95%: a + b * depth.
CATZOC = {"C": (2.0, 0.05), "B": (1.0, 0.02)}
BIN_M = 1.0
MAX_DEPTH_M = 20.0
DIST_EDGES_M = (0.0, 50.0, 100.0, 200.0, 500.0, 1000.0, float("inf"))
GATE_RMSE_M = 4.0


# --------------------------------------------------------------------------
# Folds
# --------------------------------------------------------------------------


def block_ids(rows: np.ndarray, cols: np.ndarray, *, block_px: int) -> np.ndarray:
    """Square blocks of block_px pixels, aligned to the scene grid's origin."""
    if block_px < 1:
        raise ValueError("block must be at least one pixel")
    return (np.asarray(rows) // block_px) * 1_000_000 + np.asarray(cols) // block_px


def block_folds(blocks: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    """Shuffle the blocks and deal them to k folds in turn. No block is split."""
    ub, inv = np.unique(blocks, return_inverse=True)
    if ub.size < k:
        raise ValueError(f"{ub.size} blocks cannot fill {k} folds")
    fold_of = np.empty(ub.size, dtype=np.int64)
    fold_of[rng.permutation(ub.size)] = np.arange(ub.size) % k
    return fold_of[inv.ravel()]


def random_folds(n: int, k: int, rng: np.random.Generator) -> np.ndarray:
    out = np.empty(n, dtype=np.int64)
    out[rng.permutation(n)] = np.arange(n) % k
    return out


def cross_validate(X: np.ndarray, y: np.ndarray, folds: np.ndarray,
                   fit: Callable[[np.ndarray, np.ndarray, np.random.Generator], Any],
                   rng: np.random.Generator) -> tuple[np.ndarray, list]:
    """Out-of-fold predictions. fit(X_train, y_train, rng) returns an object with .predict(X)."""
    pred = np.full(len(y), np.nan)
    models = []
    for f in np.unique(folds):
        test = folds == f
        model = fit(X[~test], y[~test], rng)
        pred[test] = model.predict(X[test])
        models.append(model)
    return pred, models


def stumpf_fit(ratio: np.ndarray, depth: np.ndarray, rng: np.random.Generator):
    return calibrate(depth, ratio, rng)


def stumpf_fit_rule95(ratio: np.ndarray, depth: np.ndarray, rng: np.random.Generator):
    """EXPLORATORY: the 95% rule alone, without the 'rises throughout' exception."""
    return calibrate(depth, ratio, rng, rises_throughout_exception=False)


#: Exploratory variants: prompted by the registered result, so never confirmatory.
#: Each writes to <out>/exploratory/ and never touches the registered outputs.
EXPLORATORY = {
    "rule95": {"fit": stumpf_fit_rule95,
               "what": "calibration step 2 applied as the 95%-of-rise rule alone, without the "
                       "'20 m if it rises throughout' exception",
               "why": "the exception set D_cal = 20 m in 46 of 50 registered folds while the error "
                      "curve showed saturation from ~14 m"},
}


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------


def metrics(pred: np.ndarray, true: np.ndarray) -> dict[str, float]:
    """n, bias, RMSE, MAE, median and 95th percentile |e|, R^2; e = pred - true."""
    e = np.asarray(pred, dtype=np.float64) - np.asarray(true, dtype=np.float64)
    n = int(e.size)
    if n == 0:
        return {"n": 0}
    a = np.abs(e)
    t = np.asarray(true, dtype=np.float64)
    sst = float(np.sum((t - t.mean()) ** 2))
    return {"n": n, "bias": float(e.mean()), "rmse": float(np.sqrt(np.mean(e ** 2))),
            "mae": float(a.mean()), "median_abs": float(np.median(a)),
            "p95_abs": float(np.percentile(a, 95)),
            "r2": float(1 - np.sum(e ** 2) / sst) if sst > 0 else float("nan")}


def band_labels(values: np.ndarray, bands: Sequence[tuple[float, float]] = DEPTH_BANDS_M,
                *, open_ends: bool = False) -> tuple[np.ndarray, list[str]]:
    """Index of the band each value falls in; the top band includes its upper edge.

    With open_ends, values below the first band get 0, above the last get the last
    label, and the bands are shifted up one -- for predicted depth, which can fall
    outside 0-20 m.
    """
    v = np.asarray(values, dtype=np.float64)
    names = [f"{lo:g}-{hi:g}" for lo, hi in bands]
    lab = np.full(v.shape, -1, dtype=np.int64)
    off = 1 if open_ends else 0
    for i, (lo, hi) in enumerate(bands):
        top = v <= hi if i == len(bands) - 1 else v < hi
        lab[(v >= lo) & top] = i + off
    if open_ends:
        lab[v < bands[0][0]] = 0
        lab[v > bands[-1][1]] = len(bands) + 1
        names = [f"<{bands[0][0]:g}"] + names + [f">{bands[-1][1]:g}"]
    return lab, names


def grouped(pred: np.ndarray, true: np.ndarray, labels: np.ndarray,
            names: Sequence[str]) -> list[dict[str, Any]]:
    return [{"group": nm, **metrics(pred[labels == i], true[labels == i])}
            for i, nm in enumerate(names)]


def depth_balanced_rmse(pred: np.ndarray, true: np.ndarray,
                        bands: Sequence[tuple[float, float]] = DEPTH_BANDS_M) -> float:
    """Mean of the per-band RMSEs, so each depth band counts equally."""
    lab, _ = band_labels(true, bands)
    r = [metrics(pred[lab == i], true[lab == i]).get("rmse") for i in range(len(bands))]
    r = [x for x in r if x is not None]
    return float(np.mean(r)) if r else float("nan")


def block_bootstrap(pred: np.ndarray, true: np.ndarray, blocks: np.ndarray, *,
                    n_boot: int = N_BOOT, rng: np.random.Generator,
                    level: float = 0.95) -> dict[str, dict[str, float]]:
    """Percentile CIs for bias, RMSE, MAE and R^2, resampling whole blocks.

    Each statistic is a function of per-block sums (n, sum e, sum e^2, sum |e|,
    sum t, sum t^2), so a draw is a weighted sum of block totals -- exact and fast.
    """
    e = np.asarray(pred, dtype=np.float64) - np.asarray(true, dtype=np.float64)
    t = np.asarray(true, dtype=np.float64)
    ub, inv = np.unique(blocks, return_inverse=True)
    inv = inv.ravel()
    nb = ub.size
    S = np.stack([np.bincount(inv, weights=w, minlength=nb)
                  for w in (np.ones_like(e), e, e * e, np.abs(e), t, t * t)], axis=1)

    def stats(T: np.ndarray) -> dict[str, np.ndarray]:
        n, se, see, sae, st, stt = T.T
        with np.errstate(invalid="ignore", divide="ignore"):
            sst = stt - st ** 2 / n
            return {"bias": se / n, "rmse": np.sqrt(see / n), "mae": sae / n,
                    "r2": np.where(sst > 0, 1 - see / sst, np.nan)}

    draws = rng.integers(0, nb, size=(n_boot, nb))
    W = np.stack([np.bincount(d, minlength=nb) for d in draws]).astype(np.float64)
    boot = stats(W @ S)
    point = stats(S.sum(axis=0, keepdims=True))
    q = [(1 - level) / 2 * 100, (1 + level) / 2 * 100]
    out = {}
    for k in boot:
        v = boot[k][np.isfinite(boot[k])]
        lo, hi = np.percentile(v, q) if v.size else (np.nan, np.nan)
        out[k] = {"point": float(point[k][0]), "lo": float(lo), "hi": float(hi)}
    out["n_blocks"] = {"point": float(nb), "lo": float(nb), "hi": float(nb)}
    return out


def depth_curve(pred: np.ndarray, true: np.ndarray, *, bin_m: float = BIN_M,
                max_depth: float = MAX_DEPTH_M) -> list[dict[str, Any]]:
    """Error statistics per bin of lidar depth."""
    edges = np.arange(0.0, max_depth + bin_m / 2, bin_m)
    bands = list(zip(edges[:-1], edges[1:]))
    lab, _ = band_labels(true, bands)
    out = []
    for i, (lo, hi) in enumerate(bands):
        m = metrics(pred[lab == i], true[lab == i])
        out.append({"lo": float(lo), "hi": float(hi), **m})
    return out


def breakdown_depth(curve: list[dict[str, Any]], a: float, b: float) -> float | None:
    """Lower edge of the shallowest bin whose p95 |e| exceeds a + b * mid-depth."""
    for row in curve:
        if row.get("n", 0) and row["p95_abs"] > a + b * (row["lo"] + row["hi"]) / 2:
            return row["lo"]
    return None


def correlogram(resid: np.ndarray, *, pixel_m: float, lags_m: Sequence[float] = CORR_LAGS_M,
                n_pairs: int = CORR_PAIRS, rng: np.random.Generator) -> list[dict[str, float]]:
    """Correlation of residuals between pixel pairs at each nominal lag, random directions."""
    valid = np.flatnonzero(np.isfinite(resid))
    ny, nx = resid.shape
    flat = resid.ravel()
    out = []
    for lag in lags_m:
        a = rng.choice(valid, n_pairs)
        r0, c0 = np.divmod(a, nx)
        th = rng.uniform(0, 2 * np.pi, n_pairs)
        r1 = r0 + np.rint(lag / pixel_m * np.sin(th)).astype(np.int64)
        c1 = c0 + np.rint(lag / pixel_m * np.cos(th)).astype(np.int64)
        ok = (r1 >= 0) & (r1 < ny) & (c1 >= 0) & (c1 < nx)
        v0 = flat[a[ok]]
        v1 = flat[r1[ok] * nx + c1[ok]]
        good = np.isfinite(v1)
        n = int(good.sum())
        r = float(np.corrcoef(v0[good], v1[good])[0, 1]) if n > 2 else float("nan")
        out.append({"lag_m": float(lag), "r": r, "n_pairs": n})
    return out


def correlation_range(curve: list[dict[str, float]], threshold: float = CORR_RANGE_R) -> float | None:
    for row in curve:
        if np.isfinite(row["r"]) and row["r"] < threshold:
            return row["lag_m"]
    return None


def distance_to_land(flags: np.ndarray, *, pixel_m: float) -> np.ndarray:
    from scipy import ndimage

    land = (flags & FLAG_LAND) > 0
    if not land.any():
        return np.full(flags.shape, np.inf)
    return ndimage.distance_transform_edt(~land) * pixel_m


def exclusions_by_band(flags: np.ndarray, depth: np.ndarray, ratio_ok: np.ndarray,
                       bands: Sequence[tuple[float, float]] = DEPTH_BANDS_M) -> list[dict[str, Any]]:
    """Reference water in the depth window, and why each part was not assessed.

    'Reference water' = fully lidar-covered, no land, inside the depth window.
    Reasons can overlap, so they need not sum to the excluded total.
    """
    ref = (flags & (FLAG_NO_LIDAR | FLAG_LAND | FLAG_DEPTH)) == 0
    lab, names = band_labels(depth, bands)
    assessed = (flags == 0) & ratio_ok
    out = []
    for i, nm in enumerate(names):
        m = ref & (lab == i)
        n = int(m.sum())
        out.append({
            "band_m": nm, "reference_px": n, "assessed_px": int((m & assessed).sum()),
            "assessed_frac": round(float((m & assessed).sum() / n), 4) if n else None,
            "cloud_or_shadow": int((m & ((flags & FLAG_CLOUD) > 0)).sum()),
            "bright_nir": int((m & ((flags & FLAG_BRIGHT_WATER) > 0)).sum()),
            "no_image": int((m & ((flags & FLAG_NO_IMAGE) > 0)).sum()),
            "ratio_undefined": int((m & (flags == 0) & ~ratio_ok).sum()),
        })
    return out


def inside_polygon(x: np.ndarray, y: np.ndarray, polygon: Sequence[Sequence[float]]) -> np.ndarray:
    from matplotlib.path import Path as MPath

    return MPath(np.asarray(polygon, dtype=np.float64)).contains_points(np.c_[x, y])


# --------------------------------------------------------------------------
# One validation run
# --------------------------------------------------------------------------


def paired_difference(pred_a: np.ndarray, pred_b: np.ndarray, true: np.ndarray,
                      blocks: np.ndarray, *, n_boot: int = N_BOOT, rng: np.random.Generator,
                      level: float = 0.95) -> dict[str, Any]:
    """Model a minus model b on the same pixels: RMSE, MAE and bias differences.

    Intervals resample whole blocks, the same draw for both models, so the
    spatially shared part of their errors cancels rather than inflating the spread.
    """
    t = np.asarray(true, dtype=np.float64)
    ea, eb = np.asarray(pred_a, np.float64) - t, np.asarray(pred_b, np.float64) - t
    ub, inv = np.unique(blocks, return_inverse=True)
    inv = inv.ravel()
    nb = ub.size
    S = np.stack([np.bincount(inv, weights=w, minlength=nb)
                  for w in (np.ones_like(ea), ea, ea * ea, np.abs(ea), eb, eb * eb, np.abs(eb))],
                 axis=1)

    def stats(T):
        n = T[:, 0]
        with np.errstate(invalid="ignore", divide="ignore"):
            ra, rb = np.sqrt(T[:, 2] / n), np.sqrt(T[:, 5] / n)
            return {"rmse_diff": ra - rb, "mae_diff": T[:, 3] / n - T[:, 6] / n,
                    "bias_diff": T[:, 1] / n - T[:, 4] / n, "rmse_a": ra, "rmse_b": rb}

    draws = rng.integers(0, nb, size=(n_boot, nb))
    W = np.stack([np.bincount(dr, minlength=nb) for dr in draws]).astype(np.float64)
    boot, point = stats(W @ S), stats(S.sum(axis=0, keepdims=True))
    q = [(1 - level) / 2 * 100, (1 + level) / 2 * 100]
    out: dict[str, Any] = {"n": int(t.size), "n_blocks": int(nb)}
    for k in ("rmse_diff", "mae_diff", "bias_diff"):
        v = boot[k][np.isfinite(boot[k])]
        lo, hi = np.percentile(v, q) if v.size else (np.nan, np.nan)
        out[k] = {"point": float(point[k][0]), "lo": float(lo), "hi": float(hi)}
    out["rmse_a"], out["rmse_b"] = float(point["rmse_a"][0]), float(point["rmse_b"][0])
    return out


def repeated_cv(depth: np.ndarray, ratio: np.ndarray, rows: np.ndarray, cols: np.ndarray, *,
                block_m: float, pixel_m: float, folds: int, repeats: int,
                fit: Callable = stumpf_fit) -> dict[str, Any]:
    """Repeated k-fold CV. block_m = 0 means a random pixel-level split."""
    preds, cals = [], []
    for rep in range(repeats):
        frng = np.random.default_rng(rep)
        if block_m > 0:
            fold = block_folds(block_ids(rows, cols, block_px=int(round(block_m / pixel_m))),
                               folds, frng)
        else:
            fold = random_folds(depth.size, folds, frng)
        p, models = cross_validate(ratio, depth, fold, fit,
                                   np.random.default_rng(CAL_SEED + rep))
        preds.append(p.astype(np.float32))
        cals += [dict(repeat=rep, fold=i, **m.summary()) for i, m in enumerate(models)]
    per_rep = [float(np.sqrt(np.mean((p.astype(np.float64) - depth) ** 2))) for p in preds]
    return {"pred": np.mean(np.stack(preds), axis=0, dtype=np.float64),
            "per_repeat_rmse": per_rep, "calibrations": cals}


#: Text that first appeared in PROJECT_BRIEF.md with the pre-registration commit.
PROTOCOL_MARKER = "pre-registered 27 Sep 2026"
#: ...and the v2 (ML) protocol's.
V2_MARKER = "ML, pre-registered 29 Sep 2026"
#: ...and the Phase 4 (three sites) protocol's.
PHASE4_MARKER = "three sites, pre-registered 1 Oct 2026"

#: Phase 4 eligibility: blocks of the primary size holding usable 0-20 m pixels.
#: Five folds need at least three blocks each; fewer and a site is not fitted.
MIN_BLOCKS = 15


def eligible_blocks(flags: np.ndarray, *, block_px: int) -> int:
    """Number of blocks that hold at least one usable pixel (flag 0)."""
    rows, cols = np.nonzero(flags == 0)
    return int(np.unique(block_ids(rows, cols, block_px=block_px)).size) if rows.size else 0


def _git_commit(root: Path, path: str, marker: str = PROTOCOL_MARKER) -> dict[str, str] | None:
    """The commit that introduced the protocol text -- not merely the latest edit to the file."""
    try:
        out = subprocess.run(["git", "-C", str(root), "log", "--reverse", "--format=%H %cI",
                              "-S", marker, "--", path],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            h, d = out.stdout.splitlines()[0].split()
            return {"commit": h, "date": d}
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None


def _r(x: Any, nd: int = 4) -> Any:
    """Round floats recursively for the JSON record."""
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if not np.isfinite(x) else round(float(x), nd)
    if isinstance(x, dict):
        return {k: _r(v, nd) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_r(v, nd) for v in x]
    return x


def main(argv: Sequence[str] | None = None) -> int:
    import rasterio
    import yaml

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--site", default="jervis_bay")
    p.add_argument("--config", type=Path, default=Path("config/sites.yml"))
    p.add_argument("--scene", required=True, help="item id under data/raw/scenes/")
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--out", type=Path, default=Path("outputs"))
    p.add_argument("--repeats", type=int, default=N_REPEATS)
    p.add_argument("--folds", type=int, default=N_FOLDS)
    p.add_argument("--block-m", type=float, default=BLOCK_M)
    p.add_argument("--boot", type=int, default=N_BOOT)
    p.add_argument("--curve-blocks", default=",".join(f"{b:g}" for b in BLOCK_CURVE_M),
                   help="block sizes (m) for the block-size curve; 0 = random split")
    p.add_argument("--no-figures", action="store_true")
    p.add_argument("--exploratory", choices=sorted(EXPLORATORY), default=None,
                   help="run a labelled exploratory variant; outputs go to <out>/exploratory/")
    p.add_argument("--model", choices=("stumpf", "gbm", "gbm_xy"), default="stumpf",
                   help="stumpf = v1 (registered); gbm = v2; gbm_xy = v2 leakage demonstration. "
                        "v2 outputs go to <out>/v2/")
    p.add_argument("--reference-tag", default=None,
                   help="sensitivity run on reference_<tag>.tif from `reference --tag`; "
                        "outputs go to <out>/sensitivity/")
    a = p.parse_args(argv)
    if a.exploratory and a.model != "stumpf":
        p.error("--exploratory applies to the Stumpf model only")
    if a.exploratory and a.reference_tag:
        p.error("--exploratory and --reference-tag do not combine")
    variant = EXPLORATORY.get(a.exploratory)
    is_ml = a.model != "stumpf"
    if is_ml:
        from sdb import ml
    fit = ml.fitter(a.model) if is_ml else (variant["fit"] if variant else stumpf_fit)
    rtag = f"_{a.reference_tag}" if a.reference_tag else ""
    tag = rtag + (f"_{a.model}" if is_ml else (f"_{a.exploratory}" if variant else ""))
    res_dir = (a.out / "sensitivity" if rtag else
               a.out / ("v2" if is_ml else "exploratory" if variant else ""))

    curve_blocks = tuple(float(v) for v in a.curve_blocks.split(",") if v.strip())
    deviations = [f"{nm}={got} (protocol {want})" for nm, got, want in (
        ("repeats", a.repeats, N_REPEATS), ("folds", a.folds, N_FOLDS),
        ("block_m", a.block_m, BLOCK_M), ("boot", a.boot, N_BOOT),
        ("curve_blocks", curve_blocks, BLOCK_CURVE_M)) if got != want]
    if variant:
        deviations.append(f"EXPLORATORY '{a.exploratory}': {variant['what']}")
    if rtag:
        deviations.append(f"SENSITIVITY: reference '{a.reference_tag}' instead of the registered one")

    site_cfg = yaml.safe_load(a.config.read_text(encoding="utf-8"))["sites"][a.site]
    scene_dir = a.root / "data" / "raw" / "scenes" / a.scene
    rpath = (a.out / "sensitivity" if rtag else a.out) / f"reference_{a.scene}{rtag}.json"
    if not rpath.exists():
        print(f"no {rpath}: run sdb.reference first"
              + (f" with --tag {a.reference_tag}" if rtag else ""), file=sys.stderr)
        return 2
    rrec = json.loads(rpath.read_text(encoding="utf-8"))
    wl = float(rrec["water_level_m_ahd"])

    scene = read_scene(scene_dir)
    grid, crs = scene["grid"], scene["crs"]
    ref_tif, mask_tif = scene_dir / f"reference{rtag}.tif", scene_dir / f"mask{rtag}.tif"
    with rasterio.open(ref_tif) as s:
        ref = {d: s.read(i + 1).astype(np.float64) for i, d in enumerate(s.descriptions)}
    with rasterio.open(mask_tif) as s:
        flags = s.read(1)
    if not (flags.shape == ref["z_mean"].shape == scene["blue"].shape):
        print("reflectance, reference and mask grids differ", file=sys.stderr)
        return 2
    pixel_m = float(grid.dx)

    print(f"{a.scene}\n  water level {wl:+.3f} m AHD ({rrec.get('water_level_source', '?')})")
    if deviations:
        print("  DEVIATES from the pre-registered protocol: " + "; ".join(deviations))

    n_blocks = eligible_blocks(flags, block_px=int(round(a.block_m / pixel_m)))
    print(f"  {a.block_m / 1000:g} km blocks with usable pixels: {n_blocks} "
          f"(Phase 4 eligibility: at least {MIN_BLOCKS})")
    if n_blocks < MIN_BLOCKS:
        print(f"  INELIGIBLE under the Phase 4 protocol: fewer than {MIN_BLOCKS} blocks. "
              f"Not fitted; report the site as ineligible.")
        return 3

    depth_img = wl - ref["z_mean"]
    ratio_img = stumpf_ratio(scene["blue"], scene["green"])
    ratio_ok = np.isfinite(ratio_img)
    ok = (flags == 0) & ratio_ok
    rows, cols = np.nonzero(ok)
    d, r = depth_img[ok], ratio_img[ok]
    print(f"  usable pixels {int((flags == 0).sum()):,}; ratio undefined in "
          f"{int(((flags == 0) & ~ratio_ok).sum()):,}; assessed {d.size:,}")
    if is_ml:
        X = ml.features(a.model, *(scene[b][ok] for b in ("blue", "green", "red", "nir")),
                        x=grid.x0 + (cols + 0.5) * grid.dx, y=grid.y0 - (rows + 0.5) * grid.dy)
        print(f"  model {a.model}: {', '.join(ml.MODELS[a.model])}"
              + ("  [LEAKAGE DEMONSTRATION -- not a result]" if a.model in ml.DEMONSTRATIONS else ""))
    else:
        X = r

    # --- primary, naive and the block-size curve ---------------------------
    runs: dict[float, dict] = {}
    for bm in dict.fromkeys((a.block_m, 0.0) + curve_blocks):
        runs[bm] = repeated_cv(d, X, rows, cols, block_m=bm, pixel_m=pixel_m,
                               folds=a.folds, repeats=a.repeats, fit=fit)
        label = "random" if bm == 0 else f"{bm / 1000:g} km"
        rr = runs[bm]["per_repeat_rmse"]
        print(f"  CV {label:>8}: pooled RMSE {np.mean(rr):.3f} m (repeats {min(rr):.3f}-{max(rr):.3f})")
    prim, naive = runs[a.block_m], runs[0.0]
    pred = prim["pred"]
    err = pred - d

    final = fit(X, d, np.random.default_rng(FINAL_SEED))

    # --- statistics --------------------------------------------------------
    brng = np.random.default_rng(BOOT_SEED)
    blocks = block_ids(rows, cols, block_px=int(round(a.block_m / pixel_m)))
    pooled = metrics(pred, d)
    ci = block_bootstrap(pred, d, blocks, n_boot=a.boot, rng=brng)
    lab_t, band_names = band_labels(d)
    by_band = []
    for i, nm in enumerate(band_names):
        m = lab_t == i
        row = {"group": nm, **metrics(pred[m], d[m])}
        if m.any():
            row["ci95"] = block_bootstrap(pred[m], d[m], blocks[m], n_boot=a.boot, rng=brng)
        by_band.append(row)
    lab_p, pnames = band_labels(pred, open_ends=True)
    curve = depth_curve(pred, d)
    breakdown = {k: breakdown_depth(curve, *ab) for k, ab in CATZOC.items()}

    strata: dict[str, Any] = {}
    poly = (site_cfg.get("strata") or {}).get("inside_bay")
    inside = None
    if poly:
        x = grid.x0 + (cols + 0.5) * grid.dx
        y = grid.y0 - (rows + 0.5) * grid.dy
        inside = inside_polygon(x, y, poly["polygon"])
        strata["inside_bay_vs_open_coast"] = []
        for nm, m in (("inside bay", inside), ("open coast", ~inside)):
            row = {"group": nm, **metrics(pred[m], d[m])}
            if m.any():
                row["ci95"] = block_bootstrap(pred[m], d[m], blocks[m], n_boot=a.boot, rng=brng)
                lb, _ = band_labels(d[m])
                row["by_band"] = grouped(pred[m], d[m], lb, band_names)
            strata["inside_bay_vs_open_coast"].append(row)
    relief = ref["relief"][ok]
    t_edges = np.quantile(relief, [1 / 3, 2 / 3])
    t_lab = np.digitize(relief, t_edges)
    strata["relief_tercile"] = {"edges_m": t_edges.tolist(),
                                "groups": grouped(pred, d, t_lab, ["low", "mid", "high"])}
    dist = distance_to_land(flags, pixel_m=pixel_m)[ok]
    d_lab = np.digitize(dist, DIST_EDGES_M[1:-1])
    d_names = [f"{lo:g}-{hi:g}" if np.isfinite(hi) else f">{lo:g}"
               for lo, hi in zip(DIST_EDGES_M[:-1], DIST_EDGES_M[1:])]
    strata["distance_to_shore_by_band"] = [
        {"band_m": bn, "by_distance_m": grouped(pred[lab_t == i], d[lab_t == i],
                                                d_lab[lab_t == i], d_names)}
        for i, bn in enumerate(band_names)]

    resid_img = np.full(flags.shape, np.nan)
    resid_img[rows, cols] = err
    corr = correlogram(resid_img, pixel_m=pixel_m, rng=np.random.default_rng(CORR_SEED))
    crange = correlation_range(corr)

    dcal = [c["d_cal_m"] for c in prim["calibrations"] if "d_cal_m" in c]
    rm_blocked, rm_naive = pooled["rmse"], metrics(naive["pred"], d)["rmse"]
    gate = "pass" if rm_blocked < GATE_RMSE_M else "fail"

    record = {
        "scene": a.scene, "site": a.site,
        "protocol": ("PROJECT_BRIEF.md, v2 protocol (pre-registered 29 Sep 2026)" if is_ml else
                     "PROJECT_BRIEF.md, Phase 2 protocol (pre-registered 27 Sep 2026)"),
        "protocol_commit": _git_commit(a.root, "PROJECT_BRIEF.md",
                                       V2_MARKER if is_ml else PROTOCOL_MARKER),
        "phase4_protocol_commit": _git_commit(a.root, "PROJECT_BRIEF.md", PHASE4_MARKER),
        "eligibility": {"blocks_with_usable_pixels": n_blocks, "min_blocks": MIN_BLOCKS,
                        "block_m": a.block_m},
        "sensitivity": ({"reference_tag": a.reference_tag, "reference_record": str(rpath),
                         "status": "SENSITIVITY: report beside the registered result, never "
                                   "instead of it"} if rtag else None),
        "model": ({"name": a.model, "params": ml.HGB_PARAMS, "features": list(ml.MODELS[a.model]),
                   "demonstration": a.model in ml.DEMONSTRATIONS} if is_ml else
                  {"name": "stumpf"}),
        "deviations": deviations,
        "exploratory": ({"name": a.exploratory, "what": variant["what"], "why": variant["why"],
                         "status": "EXPLORATORY: prompted by the registered result; not confirmatory. "
                                   "Report beside the registered result, never instead of it"}
                        if variant else None),
        "inputs": {f.name: {"path": str(f), "md5": md5(f)}
                   for f in (scene_dir / "reflectance.tif", ref_tif, mask_tif)},
        "water_level_m_ahd": wl, "water_level_source": rrec.get("water_level_source"),
        "error_sign": "e = SDB - lidar; positive = SDB reads too deep",
        "pixels": {"usable": int((flags == 0).sum()), "ratio_undefined":
                   int(((flags == 0) & ~ratio_ok).sum()), "assessed": int(d.size)},
        "design": {"block_m": a.block_m, "folds": a.folds, "repeats": a.repeats,
                   "fold_seeds": list(range(a.repeats)), "cal_seed_base": CAL_SEED,
                   "boot": a.boot, "boot_seed": BOOT_SEED, "prediction":
                   "mean of the out-of-fold predictions over repeats"},
        "gate": {"rule": f"pooled RMSE < {GATE_RMSE_M} m", "rmse_m": rm_blocked, "result": gate},
        "pooled": {**pooled, "ci95": ci},
        "depth_balanced_rmse": depth_balanced_rmse(pred, d),
        "by_band_lidar_depth": by_band,
        "by_band_predicted_depth": grouped(pred, d, lab_p, pnames),
        "by_1m_bin": curve,
        "breakdown_depth_m": {f"CATZOC_{k}": v for k, v in breakdown.items()},
        "catzoc_allowance": {k: f"{ab[0]} m + {ab[1] * 100:g}% of depth (95%)"
                             for k, ab in CATZOC.items()},
        "strata": strata,
        "blocked_vs_naive": {"blocked_rmse": rm_blocked, "naive_rmse": rm_naive,
                             "blocked_over_naive": rm_blocked / rm_naive},
        "block_size_curve": [{"block_m": bm, "rmse_mean": float(np.mean(v["per_repeat_rmse"])),
                              "rmse_min": min(v["per_repeat_rmse"]),
                              "rmse_max": max(v["per_repeat_rmse"])}
                             for bm, v in sorted(runs.items())],
        "residual_correlogram": corr,
        "residual_correlation_range_m": crange,
        "range_exceeds_block": bool(crange is None or crange > a.block_m),
        "saturation_depth_d_cal_m": ({"min": min(dcal), "median": float(np.median(dcal)),
                                      "max": max(dcal)} if dcal else None),
        "calibrations": prim["calibrations"],
        "all_data_calibration": {**final.summary(), "note":
                                 "fitted to every assessed pixel, for mapping; not a validation result"},
        "exclusions_by_band": exclusions_by_band(flags, depth_img, ratio_ok),
        "written_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sdb_version": __version__,
    }

    # --- v2: paired comparison with the registered Stumpf run ---------------
    stumpf_rec, vs = None, None
    if is_ml:
        # Against the Stumpf run on the same reference: the registered one, or the
        # same sensitivity tag.
        sj = (a.out / "sensitivity" if rtag else a.out) / f"sdb_{a.scene}{rtag}.json"
        stumpf_rec = json.loads(sj.read_text(encoding="utf-8")) if sj.exists() else None
        st_path = scene_dir / f"sdb{rtag}.tif"
        if st_path.exists():
            with rasterio.open(st_path) as s:
                st_pred = s.read(1).astype(np.float64)[rows, cols]
            if np.isfinite(st_pred).all():
                prng = np.random.default_rng(BOOT_SEED + 1)
                vs = {"against": {"path": str(st_path), "md5": md5(st_path),
                                  "water_level_m_ahd": (stumpf_rec or {}).get("water_level_m_ahd")},
                      "sign": "model minus Stumpf; negative = the model is better",
                      "pooled": paired_difference(pred, st_pred, d, blocks, n_boot=a.boot, rng=prng),
                      "by_band_lidar_depth": [
                          {"group": nm, **paired_difference(pred[lab_t == i], st_pred[lab_t == i],
                                                            d[lab_t == i], blocks[lab_t == i],
                                                            n_boot=a.boot, rng=prng)}
                          for i, nm in enumerate(band_names) if (lab_t == i).any()]}
                if inside is not None:
                    vs["inside_bay_vs_open_coast"] = [
                        {"group": nm, **paired_difference(pred[m], st_pred[m], d[m], blocks[m],
                                                          n_boot=a.boot, rng=prng)}
                        for nm, m in (("inside bay", inside), ("open coast", ~inside)) if m.any()]
                if stumpf_rec:
                    vs["blocked_over_naive"] = {
                        "model": rm_blocked / rm_naive,
                        "stumpf": stumpf_rec["blocked_vs_naive"]["blocked_over_naive"]}
            else:
                print("  sdb.tif does not cover the same pixels: run the Stumpf model first "
                      "on the same inputs; no paired comparison")
        record["vs_stumpf"] = vs

    oof = np.full(flags.shape, np.nan)
    oof[rows, cols] = pred
    raster = scene_dir / f"sdb{tag}.tif"
    write_layers(raster, {"oof_depth": oof, "residual": resid_img}, grid, crs,
                 ("oof_depth", "residual"))
    res_dir.mkdir(parents=True, exist_ok=True)
    figs = []
    if not a.no_figures:
        from sdb import viz

        fdir = res_dir / "figures"
        figs = viz.phase2_figures(fdir, a.scene + tag, depth=d, pred=pred, curve=curve,
                                  breakdown=breakdown, resid_img=resid_img, grid=grid,
                                  block_m=a.block_m, pooled=pooled,
                                  polygon=poly["polygon"] if poly else None)
        if variant:
            lines = {f"{a.exploratory} (all data)": (final.m1, final.m0)}
            reg = a.out / f"sdb_{a.scene}.json"
            if reg.exists():
                rc = json.loads(reg.read_text(encoding="utf-8"))["all_data_calibration"]
                lines = {"registered (all data)": (rc["m1"], rc["m0"]), **lines}
            figs.append(viz.ratio_depth_curve(
                fdir / f"sdb_{a.scene}{tag}_ratio_vs_depth.png", d, r,
                inside if inside is not None else np.ones(d.size, bool), lines))
        if is_ml and stumpf_rec:
            figs.append(viz.model_comparison(
                fdir / f"sdb_{a.scene}{tag}_vs_stumpf_by_depth.png",
                {"Stumpf (v1)": stumpf_rec["by_1m_bin"], a.model: curve}))
    record["figures"] = [str(f) for f in figs]
    record["outputs"] = [str(raster)]
    jpath = res_dir / f"sdb_{a.scene}{tag}.json"
    jpath.write_text(json.dumps(_r(record), indent=2), encoding="utf-8")

    c = ci
    print(f"\n  pooled (blocked {a.block_m / 1000:g} km, {a.folds}-fold x {a.repeats}):")
    print(f"    RMSE {pooled['rmse']:.2f} m [{c['rmse']['lo']:.2f}, {c['rmse']['hi']:.2f}]   "
          f"bias {pooled['bias']:+.2f} m [{c['bias']['lo']:+.2f}, {c['bias']['hi']:+.2f}]   "
          f"R2 {pooled['r2']:.3f}   n {pooled['n']:,}")
    print(f"    depth-balanced RMSE {record['depth_balanced_rmse']:.2f} m")
    print(f"    naive random split RMSE {rm_naive:.2f} m (blocked/naive {rm_blocked / rm_naive:.3f})")
    print(f"\n  {'band m':>7} {'n':>9} {'bias':>7} {'RMSE':>6} {'p95|e|':>7} {'R2':>6}")
    for row in by_band:
        if row["n"]:
            print(f"  {row['group']:>7} {row['n']:>9,} {row['bias']:>+7.2f} {row['rmse']:>6.2f} "
                  f"{row['p95_abs']:>7.2f} {row['r2']:>6.2f}")
    if inside is not None:
        for row in strata["inside_bay_vs_open_coast"]:
            if row["n"]:
                print(f"  {row['group']:>11}: n {row['n']:,}  bias {row['bias']:+.2f}  "
                      f"RMSE {row['rmse']:.2f}")
    fmt = lambda v: "not reached in 0-20 m" if v is None else f"{v:g} m"  # noqa: E731
    print(f"\n  breakdown depth: CATZOC C {fmt(breakdown['C'])}; CATZOC B {fmt(breakdown['B'])}")
    if dcal:
        print(f"  saturation depth D_cal over folds: {min(dcal):g}-{max(dcal):g} m "
              f"(median {np.median(dcal):g})")
    if vs:
        v = vs["pooled"]
        print(f"\n  vs Stumpf (paired, same pixels and folds; negative = {a.model} better):")
        print(f"    RMSE {v['rmse_a']:.2f} vs {v['rmse_b']:.2f} m: difference {v['rmse_diff']['point']:+.2f} "
              f"[{v['rmse_diff']['lo']:+.2f}, {v['rmse_diff']['hi']:+.2f}]   bias difference "
              f"{v['bias_diff']['point']:+.2f} [{v['bias_diff']['lo']:+.2f}, {v['bias_diff']['hi']:+.2f}]")
        for row in vs["by_band_lidar_depth"]:
            print(f"    {row['group']:>6} m  RMSE {row['rmse_a']:.2f} vs {row['rmse_b']:.2f}  "
                  f"({row['rmse_diff']['point']:+.2f} [{row['rmse_diff']['lo']:+.2f}, "
                  f"{row['rmse_diff']['hi']:+.2f}])")
        if "blocked_over_naive" in vs:
            b = vs["blocked_over_naive"]
            print(f"    blocked/naive: {b['model']:.3f} ({a.model}) vs {b['stumpf']:.3f} (Stumpf)")
    print(f"  residual correlation range: "
          f"{'beyond the largest lag' if crange is None else f'{crange:g} m'}"
          f"{'  -> EXCEEDS the block size: caveat applies' if record['range_exceeds_block'] else ''}")
    print(f"  gate (pooled RMSE < {GATE_RMSE_M:g} m): {gate.upper()}")
    print(f"\n  record -> {jpath}\n  layers -> {raster}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
