"""Phase 4: water clarity against error, within and across the three sites.

Implements the analysis registered in PROJECT_BRIEF.md (*Phase 4 protocol --
three sites, pre-registered 1 Oct 2026*). It fits nothing: it reads what
`validate` wrote (out-of-fold residual rasters and JSON records), the scene's
reflectance and the reference.

Clarity metric. Median red reflectance (B04, as supplied) over assessed pixels
whose lidar depth is 10-20 m. Red is the standard single-band turbidity
signal; at >= 10 m pure-water absorption alone (Kd(red) >= 0.41 /m) keeps a
bright seabed's contribution below ~0.0002. Per site, and per 2 km block (the
validation blocks) holding at least 200 such pixels.

Block level -- the inferential test. Spearman rank correlation between block
clarity and block RMSE over the same pixels, per model, within each site, with
a 95% interval from resampling blocks within the site. Across sites, the mean
of the within-site correlations, so a site-level offset (atmospheric
correction, exposure) cannot manufacture a correlation.

Site level (n = 3) -- descriptive. The registered statistics against site
clarity; decision gate 4 (a monotonic relationship) is read here.

Absolute red reflectance carries each scene's atmospheric correction, so
differences of a few thousandths between sites may be atmosphere rather than
water. Within a scene that term is shared.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from sdb import __version__
from sdb.validate import BLOCK_M, PHASE4_AMENDMENT_MARKER, PHASE4_MARKER, _git_commit, _r, block_ids

# --------------------------------------------------------------------------
# Constants -- registered in the Phase 4 protocol
# --------------------------------------------------------------------------

CLARITY_DEPTH_M = (10.0, 20.0)
MIN_BLOCK_PX = 200
N_BOOT = 1000
BOOT_SEED = 17

#: Site keys the registered predictions name.
JB, NB, BB = "jervis_bay", "narrabeen_long_reef", "batemans_bay"
MODELS = ("stumpf", "gbm")


# --------------------------------------------------------------------------
# Pure functions
# --------------------------------------------------------------------------


def clarity_pixels(depth: np.ndarray, assessed: np.ndarray,
                   depth_m: tuple[float, float] = CLARITY_DEPTH_M) -> np.ndarray:
    """Assessed pixels inside the clarity depth range (inclusive at both ends)."""
    lo, hi = depth_m
    with np.errstate(invalid="ignore"):
        return assessed & (depth >= lo) & (depth <= hi)


def site_clarity(red: np.ndarray, sel: np.ndarray) -> dict[str, Any]:
    v = red[sel & np.isfinite(red)]
    return {"median_red": float(np.median(v)) if v.size else None, "n": int(v.size)}


def block_table(red: np.ndarray, resid: dict[str, np.ndarray], sel: np.ndarray,
                blocks: np.ndarray, *, min_px: int = MIN_BLOCK_PX) -> list[dict[str, Any]]:
    """Per block: pixel count, median red and RMSE per model, over the selected pixels.

    `blocks` is an image of block ids. Blocks with fewer than `min_px` selected
    pixels are left out.
    """
    ids = blocks[sel]
    out = []
    for b in np.unique(ids):
        m = sel & (blocks == b)
        n = int(m.sum())
        if n < min_px:
            continue
        row = {"block": int(b), "n": n, "clarity": float(np.median(red[m])),
               "rmse": {k: float(np.sqrt(np.mean(v[m] ** 2))) for k, v in resid.items()}}
        out.append(row)
    return out


def _ranks(x: np.ndarray) -> np.ndarray:
    """Average ranks, ties shared (as in Spearman's definition)."""
    order = np.argsort(x, kind="mergesort")
    r = np.empty(x.size)
    r[order] = np.arange(1, x.size + 1)
    xs = x[order]
    i = 0
    while i < x.size:
        j = i
        while j + 1 < x.size and xs[j + 1] == xs[i]:
            j += 1
        if j > i:
            r[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return r


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rank correlation; NaN if fewer than 3 points or either is constant."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.size < 3:
        return float("nan")
    rx, ry = _ranks(x), _ranks(y)
    sx, sy = rx.std(), ry.std()
    if sx == 0 or sy == 0:
        return float("nan")
    return float(np.mean((rx - rx.mean()) * (ry - ry.mean())) / (sx * sy))


def spearman_ci(x: np.ndarray, y: np.ndarray, *, n_boot: int = N_BOOT,
                rng: np.random.Generator) -> dict[str, Any]:
    """Point Spearman and a percentile interval from resampling blocks (rows)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    rho = spearman(x, y)
    draws = []
    for _ in range(n_boot):
        k = rng.integers(0, x.size, x.size) if x.size else np.array([], int)
        draws.append(spearman(x[k], y[k]))
    d = np.array(draws)
    d = d[np.isfinite(d)]
    lo, hi = (np.percentile(d, [2.5, 97.5]) if d.size else (np.nan, np.nan))
    return {"rho": rho, "lo": float(lo), "hi": float(hi), "n_blocks": int(x.size),
            "n_valid_draws": int(d.size)}


def mean_within_site(pairs: dict[str, tuple[np.ndarray, np.ndarray]], *, n_boot: int = N_BOOT,
                     rng: np.random.Generator) -> dict[str, Any]:
    """Mean of within-site Spearman correlations, blocks resampled within each site."""
    point = [spearman(x, y) for x, y in pairs.values()]
    point = [p for p in point if np.isfinite(p)]
    draws = []
    for _ in range(n_boot):
        rs = []
        for x, y in pairs.values():
            k = rng.integers(0, len(x), len(x))
            rs.append(spearman(np.asarray(x)[k], np.asarray(y)[k]))
        rs = [v for v in rs if np.isfinite(v)]
        if rs:
            draws.append(np.mean(rs))
    d = np.array(draws)
    lo, hi = (np.percentile(d, [2.5, 97.5]) if d.size else (np.nan, np.nan))
    return {"mean_rho": float(np.mean(point)) if point else float("nan"),
            "lo": float(lo), "hi": float(hi), "sites": list(pairs), "n_valid_draws": int(d.size)}


def monotonic(clarity: Sequence[float], value: Sequence[float]) -> bool | None:
    """True if `value` strictly increases with `clarity` (sites ordered by clarity)."""
    c, v = np.asarray(clarity, float), np.asarray(value, float)
    if c.size < 2 or not (np.isfinite(c).all() and np.isfinite(v).all()):
        return None
    s = v[np.argsort(c)]
    return bool(np.all(np.diff(s) > 0))


def evaluate_predictions(sites: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """The four registered predictions, as written, against the summary per site.

    Each site entry carries: clarity["median_red"], stumpf["rmse"],
    gbm_vs_stumpf {"point", "lo", "hi"} and within["stumpf"] {"rho", "lo", "hi"}.
    """
    have = lambda *ks: all(k in sites for k in ks)  # noqa: E731
    out = []

    # 1. Batemans Bay has the highest site clarity metric.
    if have(JB, NB, BB):
        cl = {k: sites[k]["clarity"]["median_red"] for k in (JB, NB, BB)}
        top = max(cl, key=lambda k: cl[k])
        out.append({"prediction": 1, "text": "Batemans Bay has the highest site clarity metric",
                    "result": "held" if top == BB else "failed", "evidence": cl})
    else:
        out.append({"prediction": 1, "result": "not evaluated", "evidence": "sites missing"})

    # 2. Stumpf pooled RMSE at both new sites exceeds Jervis Bay's.
    if have(JB, NB, BB):
        rm = {k: sites[k]["stumpf"]["rmse"] for k in (JB, NB, BB)}
        ok = rm[NB] > rm[JB] and rm[BB] > rm[JB]
        out.append({"prediction": 2, "text": "Stumpf pooled RMSE at both new sites exceeds "
                    "Jervis Bay's", "result": "held" if ok else "failed", "evidence": rm})
    else:
        out.append({"prediction": 2, "result": "not evaluated", "evidence": "sites missing"})

    # 3. At Batemans Bay, Stumpf block RMSE in 10-20 m rises with block red reflectance.
    if have(BB):
        w = sites[BB]["within"]["stumpf"]
        if np.isfinite(w["rho"]) and w["rho"] > 0 and w["lo"] > 0:
            res = "held"
        elif np.isfinite(w["rho"]) and w["rho"] > 0:
            res = "not supported: positive, but the interval includes 0"
        else:
            res = "failed"
        out.append({"prediction": 3, "text": "At Batemans Bay, Stumpf block RMSE in 10-20 m "
                    "rises with block red reflectance (Spearman > 0, interval excluding 0)",
                    "result": res, "evidence": w})
    else:
        out.append({"prediction": 3, "result": "not evaluated", "evidence": "site missing"})

    # 4. gbm beats Stumpf at every site, by less at Batemans Bay than at Jervis Bay.
    if have(JB, BB) and all(sites[k].get("gbm_vs_stumpf") for k in sites):
        d = {k: sites[k]["gbm_vs_stumpf"] for k in sites}
        everywhere = all(v["hi"] < 0 for v in d.values())
        smaller = d[BB]["point"] > d[JB]["point"]          # less negative = smaller advantage
        res = "held" if everywhere and smaller else "failed"
        out.append({"prediction": 4, "text": "gbm beats Stumpf at every site (paired interval "
                    "excludes 0), by less at Batemans Bay than at Jervis Bay",
                    "result": res, "evidence": {"gbm_minus_stumpf": d,
                                                "every_site_interval_below_0": everywhere,
                                                "batemans_advantage_smaller": smaller}})
    else:
        out.append({"prediction": 4, "result": "not evaluated", "evidence": "gbm runs missing"})
    return out


def compare_records(primary: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    """Other minus primary for the headline statistics of two validate records."""
    def bands(rec):
        return {r["group"]: r.get("rmse") for r in rec.get("by_band_lidar_depth", [])}

    def relief(rec):
        g = (rec.get("strata") or {}).get("relief_tercile", {}).get("groups", [])
        return {r["group"]: r.get("rmse") for r in g}

    diff = lambda a, b: None if a is None or b is None else b - a  # noqa: E731
    pb, ob = bands(primary), bands(other)
    pr, orl = relief(primary), relief(other)
    out = {"pooled_rmse": diff(primary["pooled"]["rmse"], other["pooled"]["rmse"]),
           "pooled_bias": diff(primary["pooled"]["bias"], other["pooled"]["bias"]),
           "depth_balanced_rmse": diff(primary.get("depth_balanced_rmse"),
                                       other.get("depth_balanced_rmse")),
           "rmse_by_band": {k: diff(pb.get(k), ob.get(k)) for k in pb},
           "rmse_by_relief_tercile": {k: diff(pr.get(k), orl.get(k)) for k in pr},
           "relief_tercile_edges_m": {"primary": (primary.get("strata") or {})
                                      .get("relief_tercile", {}).get("edges_m"),
                                      "other": (other.get("strata") or {})
                                      .get("relief_tercile", {}).get("edges_m")}}
    vp, vo = primary.get("vs_stumpf"), other.get("vs_stumpf")
    if vp and vo:
        out["gbm_minus_stumpf"] = diff(vp["pooled"]["rmse_diff"]["point"],
                                       vo["pooled"]["rmse_diff"]["point"])
    return out


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------


def _read_band(path: Path, name: str) -> np.ndarray:
    import rasterio

    with rasterio.open(path) as s:
        return s.read(list(s.descriptions).index(name) + 1).astype(np.float64)


def load_site(root: Path, out: Path, scene: str) -> dict[str, Any]:
    """Everything the analysis needs for one site, from validate's outputs."""
    from sdb.reference import read_scene

    sd = root / "data" / "raw" / "scenes" / scene
    rrec = json.loads((out / f"reference_{scene}.json").read_text(encoding="utf-8"))
    wl = float(rrec["water_level_m_ahd"])
    sc = read_scene(sd)
    depth = wl - _read_band(sd / "reference.tif", "z_mean")
    resid = {"stumpf": _read_band(sd / "sdb.tif", "residual")}
    recs = {"stumpf": json.loads((out / f"sdb_{scene}.json").read_text(encoding="utf-8"))}
    gp = sd / "sdb_gbm.tif"
    gj = out / "v2" / f"sdb_{scene}_gbm.json"
    if gp.exists() and gj.exists():
        resid["gbm"] = _read_band(gp, "residual")
        recs["gbm"] = json.loads(gj.read_text(encoding="utf-8"))
    assessed = np.isfinite(resid["stumpf"])
    if "gbm" in resid and not np.array_equal(assessed, np.isfinite(resid["gbm"])):
        raise ValueError(f"{scene}: Stumpf and gbm residuals cover different pixels")
    return {"scene": scene, "grid": sc["grid"], "red": sc["red"], "depth": depth,
            "assessed": assessed, "resid": resid, "records": recs, "water_level_m_ahd": wl}


def analyse(sites: dict[str, dict[str, Any]], *, n_boot: int = N_BOOT,
            seed: int = BOOT_SEED) -> dict[str, Any]:
    """The registered analysis over loaded sites (see `load_site`)."""
    rng = np.random.default_rng(seed)
    summary: dict[str, dict[str, Any]] = {}
    tables: dict[str, list[dict[str, Any]]] = {}
    for name, s in sites.items():
        sel = clarity_pixels(s["depth"], s["assessed"])
        g = s["grid"]
        rows, cols = np.indices(s["red"].shape)
        blocks = block_ids(rows, cols, block_px=int(round(BLOCK_M / g.dx)))
        tab = block_table(s["red"], s["resid"], sel, blocks)
        tables[name] = tab
        within = {}
        for m in s["resid"]:
            x = np.array([t["clarity"] for t in tab])
            y = np.array([t["rmse"][m] for t in tab])
            within[m] = spearman_ci(x, y, n_boot=n_boot, rng=rng)
        st = s["records"]["stumpf"]
        entry = {"scene": s["scene"], "water_level_m_ahd": s["water_level_m_ahd"],
                 "clarity": site_clarity(s["red"], sel),
                 "blocks_used": len(tab), "within": within,
                 "stumpf": {"rmse": st["pooled"]["rmse"], "ci95": st["pooled"].get("ci95"),
                            "bias": st["pooled"]["bias"],
                            "depth_balanced_rmse": st.get("depth_balanced_rmse"),
                            "breakdown_depth_m": st.get("breakdown_depth_m")}}
        gb = s["records"].get("gbm")
        if gb:
            entry["gbm"] = {"rmse": gb["pooled"]["rmse"], "bias": gb["pooled"]["bias"],
                            "depth_balanced_rmse": gb.get("depth_balanced_rmse"),
                            "breakdown_depth_m": gb.get("breakdown_depth_m")}
            vs = (gb.get("vs_stumpf") or {}).get("pooled")
            if vs:
                entry["gbm_vs_stumpf"] = vs["rmse_diff"]
        summary[name] = entry

    across = {}
    for m in MODELS:
        pairs = {k: (np.array([t["clarity"] for t in tables[k]]),
                     np.array([t["rmse"][m] for t in tables[k]]))
                 for k in tables if tables[k] and m in tables[k][0]["rmse"]}
        if pairs:
            across[m] = mean_within_site(pairs, n_boot=n_boot, rng=rng)

    names = list(summary)
    cl = [summary[k]["clarity"]["median_red"] for k in names]
    gate = {"order_by_clarity": [names[i] for i in np.argsort(cl)] if None not in cl else None,
            "stumpf_rmse_monotonic": monotonic(cl, [summary[k]["stumpf"]["rmse"] for k in names])
            if None not in cl else None}
    if all("gbm" in summary[k] for k in names) and None not in cl:
        gate["gbm_rmse_monotonic"] = monotonic(cl, [summary[k]["gbm"]["rmse"] for k in names])
    return {"sites": summary, "blocks": tables, "across_sites_mean_within_rho": across,
            "gate4": gate, "predictions": evaluate_predictions(summary)}


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--run", action="append", required=True, metavar="SITE=SCENE",
                   help="one per site, e.g. batemans_bay=S2B_56HKF_20180823_1_L2A")
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--out", type=Path, default=Path("outputs"))
    p.add_argument("--boot", type=int, default=N_BOOT)
    p.add_argument("--no-figures", action="store_true")
    a = p.parse_args(argv)

    runs = dict(r.split("=", 1) for r in a.run)
    sites = {k: load_site(a.root, a.out, v) for k, v in runs.items()}
    res = analyse(sites, n_boot=a.boot)

    # Sensitivity records (validate --reference-tag) beside their primaries.
    sens = {}
    for k, scene in runs.items():
        for f in sorted((a.out / "sensitivity").glob(f"sdb_{scene}_*.json")):
            rec = json.loads(f.read_text(encoding="utf-8"))
            if not rec.get("sensitivity"):
                continue
            model = rec["model"]["name"]
            prim = sites[k]["records"].get(model)
            if prim:
                sens[f.stem] = {"site": k, "model": model,
                                "tag": rec["sensitivity"]["reference_tag"],
                                "other_minus_primary": compare_records(prim, rec)}
    res["sensitivity"] = sens

    deviations = [f"boot={a.boot} (protocol {N_BOOT})"] if a.boot != N_BOOT else []
    record = {"protocol": "PROJECT_BRIEF.md, Phase 4 protocol (pre-registered 1 Oct 2026)",
              "protocol_commit": _git_commit(a.root, "PROJECT_BRIEF.md", PHASE4_MARKER),
              "amendment_commit": _git_commit(a.root, "PROJECT_BRIEF.md", PHASE4_AMENDMENT_MARKER),
              "deviations": deviations,
              "metric": {"what": "median red reflectance (B04, as supplied)",
                         "pixels": f"assessed, lidar depth {CLARITY_DEPTH_M[0]:g}-"
                                   f"{CLARITY_DEPTH_M[1]:g} m",
                         "block_m": BLOCK_M, "min_block_px": MIN_BLOCK_PX,
                         "boot": a.boot, "boot_seed": BOOT_SEED},
              **res,
              "written_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "sdb_version": __version__}
    od = a.out / "phase4"
    od.mkdir(parents=True, exist_ok=True)
    if not a.no_figures:
        from sdb import viz
        record["figures"] = [str(viz.clarity_blocks(od / "figures" / "clarity_vs_block_rmse.png",
                                                    res["sites"], res["blocks"]))]
    jp = od / "clarity.json"
    jp.write_text(json.dumps(_r(record, 6), indent=2), encoding="utf-8")

    print(f"{'site':<22} {'clarity':>8} {'blocks':>6} {'Stumpf':>7} {'gbm':>6} "
          f"{'gbm-St':>7}   rho Stumpf [95%]          rho gbm [95%]")
    for k, s in res["sites"].items():
        w = s["within"]
        fr = lambda d: (f"{d['rho']:+.2f} [{d['lo']:+.2f}, {d['hi']:+.2f}]"  # noqa: E731
                        if d and np.isfinite(d["rho"]) else "--")
        g = s.get("gbm", {}).get("rmse")
        dv = s.get("gbm_vs_stumpf", {}).get("point")
        c = s["clarity"]["median_red"]
        print(f"{k:<22} {c if c is not None else float('nan'):>8.4f} {s['blocks_used']:>6} "
              f"{s['stumpf']['rmse']:>7.2f} {g if g is not None else float('nan'):>6.2f} "
              f"{dv if dv is not None else float('nan'):>+7.2f}   {fr(w.get('stumpf')):<25} "
              f"{fr(w.get('gbm'))}")
    for m, v in res["across_sites_mean_within_rho"].items():
        print(f"  mean within-site rho, {m}: {v['mean_rho']:+.2f} [{v['lo']:+.2f}, {v['hi']:+.2f}]")
    print(f"  gate 4 (monotonic): {res['gate4']}")
    for pr in res["predictions"]:
        print(f"  prediction {pr['prediction']}: {pr['result']}")
    for nm, s in sens.items():
        print(f"  sensitivity {nm}: pooled RMSE {s['other_minus_primary']['pooled_rmse']:+.3f} m "
              f"vs primary")
    print(f"\n  record -> {jp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
