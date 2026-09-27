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


def repeated_cv(depth: np.ndarray, ratio: np.ndarray, rows: np.ndarray, cols: np.ndarray, *,
                block_m: float, pixel_m: float, folds: int, repeats: int) -> dict[str, Any]:
    """Repeated k-fold CV. block_m = 0 means a random pixel-level split."""
    preds, cals = [], []
    for rep in range(repeats):
        frng = np.random.default_rng(rep)
        if block_m > 0:
            fold = block_folds(block_ids(rows, cols, block_px=int(round(block_m / pixel_m))),
                               folds, frng)
        else:
            fold = random_folds(depth.size, folds, frng)
        p, models = cross_validate(ratio, depth, fold, stumpf_fit,
                                   np.random.default_rng(CAL_SEED + rep))
        preds.append(p.astype(np.float32))
        cals += [dict(repeat=rep, fold=i, **m.summary()) for i, m in enumerate(models)]
    per_rep = [float(np.sqrt(np.mean((p.astype(np.float64) - depth) ** 2))) for p in preds]
    return {"pred": np.mean(np.stack(preds), axis=0, dtype=np.float64),
            "per_repeat_rmse": per_rep, "calibrations": cals}


#: Text that first appeared in PROJECT_BRIEF.md with the pre-registration commit.
PROTOCOL_MARKER = "pre-registered 27 Sep 2026"


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
    a = p.parse_args(argv)

    curve_blocks = tuple(float(v) for v in a.curve_blocks.split(",") if v.strip())
    deviations = [f"{nm}={got} (protocol {want})" for nm, got, want in (
        ("repeats", a.repeats, N_REPEATS), ("folds", a.folds, N_FOLDS),
        ("block_m", a.block_m, BLOCK_M), ("boot", a.boot, N_BOOT),
        ("curve_blocks", curve_blocks, BLOCK_CURVE_M)) if got != want]

    site_cfg = yaml.safe_load(a.config.read_text(encoding="utf-8"))["sites"][a.site]
    scene_dir = a.root / "data" / "raw" / "scenes" / a.scene
    rpath = a.out / f"reference_{a.scene}.json"
    if not rpath.exists():
        print(f"no {rpath}: run sdb.reference first", file=sys.stderr)
        return 2
    rrec = json.loads(rpath.read_text(encoding="utf-8"))
    wl = float(rrec["water_level_m_ahd"])

    scene = read_scene(scene_dir)
    grid, crs = scene["grid"], scene["crs"]
    with rasterio.open(scene_dir / "reference.tif") as s:
        ref = {d: s.read(i + 1).astype(np.float64) for i, d in enumerate(s.descriptions)}
    with rasterio.open(scene_dir / "mask.tif") as s:
        flags = s.read(1)
    if not (flags.shape == ref["z_mean"].shape == scene["blue"].shape):
        print("reflectance, reference and mask grids differ", file=sys.stderr)
        return 2
    pixel_m = float(grid.dx)

    print(f"{a.scene}\n  water level {wl:+.3f} m AHD ({rrec.get('water_level_source', '?')})")
    if deviations:
        print("  DEVIATES from the pre-registered protocol: " + "; ".join(deviations))

    depth_img = wl - ref["z_mean"]
    ratio_img = stumpf_ratio(scene["blue"], scene["green"])
    ratio_ok = np.isfinite(ratio_img)
    ok = (flags == 0) & ratio_ok
    rows, cols = np.nonzero(ok)
    d, r = depth_img[ok], ratio_img[ok]
    print(f"  usable pixels {int((flags == 0).sum()):,}; ratio undefined in "
          f"{int(((flags == 0) & ~ratio_ok).sum()):,}; assessed {d.size:,}")

    # --- primary, naive and the block-size curve ---------------------------
    runs: dict[float, dict] = {}
    for bm in dict.fromkeys((a.block_m, 0.0) + curve_blocks):
        runs[bm] = repeated_cv(d, r, rows, cols, block_m=bm, pixel_m=pixel_m,
                               folds=a.folds, repeats=a.repeats)
        tag = "random" if bm == 0 else f"{bm / 1000:g} km"
        rr = runs[bm]["per_repeat_rmse"]
        print(f"  CV {tag:>8}: pooled RMSE {np.mean(rr):.3f} m (repeats {min(rr):.3f}-{max(rr):.3f})")
    prim, naive = runs[a.block_m], runs[0.0]
    pred = prim["pred"]
    err = pred - d

    final = calibrate(d, r, np.random.default_rng(FINAL_SEED))

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

    dcal = [c["d_cal_m"] for c in prim["calibrations"]]
    rm_blocked, rm_naive = pooled["rmse"], metrics(naive["pred"], d)["rmse"]
    gate = "pass" if rm_blocked < GATE_RMSE_M else "fail"

    record = {
        "scene": a.scene, "site": a.site,
        "protocol": "PROJECT_BRIEF.md, Phase 2 protocol (pre-registered 27 Sep 2026)",
        "protocol_commit": _git_commit(a.root, "PROJECT_BRIEF.md"),
        "deviations": deviations,
        "inputs": {n: {"path": str(scene_dir / n), "md5": md5(scene_dir / n)}
                   for n in ("reflectance.tif", "reference.tif", "mask.tif")},
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
        "saturation_depth_d_cal_m": {"min": min(dcal), "median": float(np.median(dcal)),
                                     "max": max(dcal)},
        "calibrations": prim["calibrations"],
        "all_data_calibration": {**final.summary(), "note":
                                 "fitted to every assessed pixel, for mapping; not a validation result"},
        "exclusions_by_band": exclusions_by_band(flags, depth_img, ratio_ok),
        "written_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sdb_version": __version__,
    }

    oof = np.full(flags.shape, np.nan)
    oof[rows, cols] = pred
    write_layers(scene_dir / "sdb.tif", {"oof_depth": oof, "residual": resid_img}, grid, crs,
                 ("oof_depth", "residual"))
    a.out.mkdir(parents=True, exist_ok=True)
    figs = []
    if not a.no_figures:
        from sdb import viz

        fdir = a.out / "figures"
        figs = viz.phase2_figures(fdir, a.scene, depth=d, pred=pred, curve=curve,
                                  breakdown=breakdown, resid_img=resid_img, grid=grid,
                                  block_m=a.block_m, pooled=pooled,
                                  polygon=poly["polygon"] if poly else None)
    record["figures"] = [str(f) for f in figs]
    record["outputs"] = [str(scene_dir / "sdb.tif")]
    jpath = a.out / f"sdb_{a.scene}.json"
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
    print(f"  saturation depth D_cal over folds: {min(dcal):g}-{max(dcal):g} m "
          f"(median {np.median(dcal):g})")
    print(f"  residual correlation range: "
          f"{'beyond the largest lag' if crange is None else f'{crange:g} m'}"
          f"{'  -> EXCEEDS the block size: caveat applies' if record['range_exceeds_block'] else ''}")
    print(f"  gate (pooled RMSE < {GATE_RMSE_M:g} m): {gate.upper()}")
    print(f"\n  record -> {jpath}\n  layers -> {scene_dir / 'sdb.tif'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
