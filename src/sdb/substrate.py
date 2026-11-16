"""Substrate strata for the validation errors -- the pre-registered addendum.

Reads the seagrass and reef layers, puts each class's area fraction onto the
ground every scene pixel actually sees (the scene grid translated by the applied
co-registration shift), labels pixels by the rules in PROJECT_BRIEF.md
(*Substrate addendum*), and compares Phase 2's out-of-fold errors between
classes within depth bands. Nothing is refitted: the residuals are read from
sdb.tif, written by validate.py.

Substrate is correlated with depth (seagrass is mapped only to ~10 m) and with
exposure (the open coast is half reef), so every comparison is made within a
depth band and inside the bay, against the reference class "sediment, no
seagrass mapped". Differences carry block-bootstrap intervals in which both
groups are resampled by the same 2 km blocks.

    python -m sdb.substrate --scene S2A_56HKG_20180907_0_L2A
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
from sdb.reference import DEPTH_BANDS_M, Grid, md5, write_layers
from sdb.validate import (_git_commit, _r, band_labels, block_ids, inside_polygon, metrics)

# --------------------------------------------------------------------------
# Pre-registered constants (Substrate addendum)
# --------------------------------------------------------------------------

MAJORITY = 0.5
CORE = 0.9
TRACE = 0.1
SUPERSAMPLE = 5                  # 2 m cells inside a 10 m pixel
MIN_COMPARE_PX = 1000
N_BOOT = 1000
BOOT_SEED = 13
BLOCK_M = 2000.0
CLASSES = ("Posidonia", "Posidonia/Zostera", "Zostera/Halophila", "seagrass, mixed types",
           "reef", "sediment, no seagrass mapped", "edge/mixed", "not mapped")
REFERENCE = CLASSES.index("sediment, no seagrass mapped")
COMPARED = ("Posidonia", "Posidonia/Zostera", "Zostera/Halophila", "reef")
FRACTIONS = ("posidonia", "posidonia_zostera", "zostera_halophila", "seagrass_any", "reef",
             "unconsolidated")
ADDENDUM_MARKER = "Substrate addendum"
#: One GeoPackage per site, so a site can never silently read another site's layers.
DEFAULT_GPKG = "data/raw/substrate/substrate_{site}.gpkg"


# --------------------------------------------------------------------------
# Layers -> fractions -> classes
# --------------------------------------------------------------------------


def load_layers(gpkg: Path, epsg: int = 7856) -> dict[str, Any]:
    """Class geometries from the two layers, in GDA2020 / MGA 56 (= the scene plane)."""
    import geopandas as gpd

    m = gpd.read_file(gpkg, layer="macrophytes").to_crs(epsg)
    r = gpd.read_file(gpkg, layer="reef_extent").to_crs(epsg)
    sg = m[m["Habitat"] == "Seagrass"]
    return {
        "posidonia": sg[sg["Macrophyte"] == "Posidonia"].geometry,
        "posidonia_zostera": sg[sg["Macrophyte"] == "Posidonia/Zostera"].geometry,
        "zostera_halophila": sg[sg["Macrophyte"].isin(["Zostera", "Halophila"])].geometry,
        "seagrass_any": sg.geometry,
        "reef": r[r["REEF"] == "Reef"].geometry,
        "unconsolidated": r[r["REEF"] == "Unconsolidated"].geometry,
    }


def fractions(geoms: dict[str, Sequence], grid: Grid, shift: tuple[float, float] = (0.0, 0.0),
              supersample: int = SUPERSAMPLE) -> dict[str, np.ndarray]:
    """Area fraction of each class in every pixel of grid, translated by shift (m E, m N)."""
    from affine import Affine
    from rasterio import features

    s = supersample
    T = Affine(grid.dx / s, 0, grid.x0 + shift[0], 0, -grid.dy / s, grid.y0 + shift[1])
    out = {}
    for k, gs in geoms.items():
        shapes = [(g, 1) for g in gs if g is not None and not g.is_empty]
        if not shapes:
            out[k] = np.zeros((grid.ny, grid.nx), np.float32)
            continue
        a = features.rasterize(shapes, out_shape=(grid.ny * s, grid.nx * s), transform=T,
                               fill=0, dtype="uint8")
        out[k] = a.reshape(grid.ny, s, grid.nx, s).mean(axis=(1, 3)).astype(np.float32)
    return out


def classify(frac: dict[str, np.ndarray], threshold: float = MAJORITY,
             trace: float = TRACE) -> np.ndarray:
    """Index into CLASSES per pixel, by the addendum's rules and precedence."""
    pos, pz, zh, sga, reef, unc = (np.asarray(frac[k]) for k in FRACTIONS)
    c = np.full(pos.shape, CLASSES.index("edge/mixed"), np.int8)
    c[(sga + reef + unc) < trace] = CLASSES.index("not mapped")
    c[(unc >= threshold) & (sga < trace) & (reef < trace)] = REFERENCE
    c[(reef >= threshold) & (sga < threshold)] = CLASSES.index("reef")
    c[(sga >= threshold) & (pos < threshold) & (pz < threshold) & (zh < threshold)] = \
        CLASSES.index("seagrass, mixed types")
    c[zh >= threshold] = CLASSES.index("Zostera/Halophila")
    c[pz >= threshold] = CLASSES.index("Posidonia/Zostera")
    c[pos >= threshold] = CLASSES.index("Posidonia")
    return c


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------


def group_difference(err: np.ndarray, blocks: np.ndarray, a: np.ndarray, b: np.ndarray, *,
                     n_boot: int = N_BOOT, rng: np.random.Generator,
                     level: float = 0.95) -> dict[str, dict[str, float]]:
    """Bias and RMSE of group a minus group b, CIs from resampling blocks jointly."""
    sel = a | b
    ub, inv = np.unique(blocks[sel], return_inverse=True)
    inv = inv.ravel()
    e, ga = np.asarray(err, np.float64)[sel], a[sel]
    nb = ub.size

    def sums(m):
        return np.stack([np.bincount(inv[m], weights=w[m], minlength=nb)
                         for w in (np.ones_like(e), e, e * e)], axis=1)

    SA, SB = sums(ga), sums(~ga)

    def stats(TA, TB):
        with np.errstate(invalid="ignore", divide="ignore"):
            return {"bias_diff": TA[:, 1] / TA[:, 0] - TB[:, 1] / TB[:, 0],
                    "rmse_diff": np.sqrt(TA[:, 2] / TA[:, 0]) - np.sqrt(TB[:, 2] / TB[:, 0])}

    draws = rng.integers(0, nb, size=(n_boot, nb))
    W = np.stack([np.bincount(d, minlength=nb) for d in draws]).astype(np.float64)
    boot = stats(W @ SA, W @ SB)
    point = stats(SA.sum(0, keepdims=True), SB.sum(0, keepdims=True))
    q = [(1 - level) / 2 * 100, (1 + level) / 2 * 100]
    out = {}
    for k, v in boot.items():
        v = v[np.isfinite(v)]
        lo, hi = np.percentile(v, q) if v.size else (np.nan, np.nan)
        out[k] = {"point": float(point[k][0]), "lo": float(lo), "hi": float(hi)}
    out["n_blocks"] = int(nb)
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    import rasterio
    import yaml

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--site", default="jervis_bay")
    p.add_argument("--config", type=Path, default=Path("config/sites.yml"))
    p.add_argument("--scene", required=True)
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--out", type=Path, default=Path("outputs"))
    p.add_argument("--substrate", type=Path, default=None,
                   help=f"GeoPackage of substrate layers (default <root>/{DEFAULT_GPKG})")
    p.add_argument("--boot", type=int, default=N_BOOT)
    p.add_argument("--no-figures", action="store_true")
    p.add_argument("--tag", default=None,
                   help="exploratory variant name, e.g. rule95: reads sdb_<tag>.tif and writes to "
                        "<out>/exploratory/")
    a = p.parse_args(argv)
    tag = f"_{a.tag}" if a.tag else ""
    res_dir = a.out / "exploratory" if a.tag else a.out

    gpkg = a.substrate or a.root / DEFAULT_GPKG.format(site=a.site)
    scene_dir = a.root / "data" / "raw" / "scenes" / a.scene
    rpath = a.out / f"reference_{a.scene}.json"
    resid_path = scene_dir / f"sdb{tag}.tif"
    for need in (gpkg, rpath, resid_path):
        if not need.exists():
            print(f"missing {need}", file=sys.stderr)
            return 2
    rrec = json.loads(rpath.read_text(encoding="utf-8"))
    wl = float(rrec["water_level_m_ahd"])
    shift = tuple(float(v) for v in (rrec.get("coregistration") or {}).get("shift_applied_m", (0, 0)))
    site_cfg = yaml.safe_load(a.config.read_text(encoding="utf-8"))["sites"][a.site]

    with rasterio.open(resid_path) as s:
        resid = s.read(2).astype(np.float64)
        grid = Grid.from_transform(s.transform, s.shape)
        crs = s.crs
    with rasterio.open(scene_dir / "reference.tif") as s:
        z = s.read(1).astype(np.float64)
    depth_img = wl - z

    geoms = load_layers(gpkg)
    frac = fractions(geoms, grid, shift)
    cls = {thr: classify(frac, thr) for thr in (MAJORITY, CORE)}

    ok = np.isfinite(resid)
    rows, cols = np.nonzero(ok)
    err, d = resid[ok], depth_img[ok]
    blocks = block_ids(rows, cols, block_px=int(round(BLOCK_M / grid.dx)))
    band, band_names = band_labels(d, DEPTH_BANDS_M)
    poly = (site_cfg.get("strata") or {}).get("inside_bay")
    inside = (inside_polygon(grid.x0 + (cols + 0.5) * grid.dx, grid.y0 - (rows + 0.5) * grid.dy,
                             poly["polygon"]) if poly else np.ones(err.size, bool))
    # Without an inside-bay polygon (sites 2 and 3) the comparisons cover the whole
    # site. The record keys keep their Jervis Bay names; `comparison_region` says
    # what they hold.
    scope = "inside bay" if poly else "whole site"
    regions = {"inside bay": inside, "open coast": ~inside} if poly else {scope: inside}
    print(f"{a.scene}\n  substrate {gpkg.name}; co-registration shift {shift}; "
          f"assessed pixels {err.size:,}")

    rng = np.random.default_rng(BOOT_SEED)
    record_rules: dict[str, Any] = {}
    for thr, lab_img in cls.items():
        lab = lab_img[ok]
        key = f"threshold_{thr:g}"
        table = []
        for rname, rsel in regions.items():
            for bi, bname in enumerate(band_names):
                for ci, cname in enumerate(CLASSES):
                    m = rsel & (band == bi) & (lab == ci)
                    if m.any():
                        table.append({"region": rname, "band_m": bname, "class": cname,
                                      **metrics(err[m], np.zeros(int(m.sum())))})
        comps = []
        for bi, bname in enumerate(band_names):
            ref = inside & (band == bi) & (lab == REFERENCE)
            for cname in COMPARED:
                m = inside & (band == bi) & (lab == CLASSES.index(cname))
                row = {"band_m": bname, "class": cname, "n_class": int(m.sum()), "n_reference": int(ref.sum())}
                if m.sum() >= MIN_COMPARE_PX and ref.sum() >= MIN_COMPARE_PX:
                    row.update(group_difference(err, blocks, m, ref, n_boot=a.boot, rng=rng))
                else:
                    row["note"] = f"not compared: fewer than {MIN_COMPARE_PX} pixels"
                comps.append(row)
        reef_io = []
        for bi, bname in enumerate(band_names):
            rin = inside & (band == bi) & (lab == CLASSES.index("reef"))
            rout = ~inside & (band == bi) & (lab == CLASSES.index("reef"))
            row = {"band_m": bname, "n_open": int(rout.sum()), "n_inside": int(rin.sum())}
            if rin.sum() >= MIN_COMPARE_PX and rout.sum() >= MIN_COMPARE_PX:
                row.update(group_difference(err, blocks, rout, rin, n_boot=a.boot, rng=rng))
            else:
                row["note"] = f"not compared: fewer than {MIN_COMPARE_PX} pixels"
            reef_io.append(row)
        record_rules[key] = {"errors_by_class": table, "vs_reference_inside_bay": comps,
                             "reef_open_minus_inside": reef_io}

    # --- outputs ------------------------------------------------------------
    layers = {"class_majority": cls[MAJORITY].astype(np.float32),
              "class_core": cls[CORE].astype(np.float32),
              "seagrass_frac": frac["seagrass_any"], "reef_frac": frac["reef"]}
    if not a.tag:                        # the classes do not depend on the residuals
        write_layers(scene_dir / "substrate.tif", layers, grid, crs, tuple(layers))
    record = {
        "scene": a.scene,
        "addendum": "PROJECT_BRIEF.md, Substrate addendum (pre-registered 27 Sep 2026)",
        "addendum_commit": _git_commit(a.root, "PROJECT_BRIEF.md", ADDENDUM_MARKER),
        "substrate": {"path": str(gpkg), "md5": md5(gpkg)},
        "residuals": {"path": str(resid_path), "md5": md5(resid_path)},
        "exploratory": ({"name": a.tag, "status": "EXPLORATORY: residuals from an exploratory "
                         "variant of validate.py; not confirmatory"} if a.tag else None),
        "water_level_m_ahd": wl, "coregistration_shift_m": list(shift),
        "comparison_region": (scope if poly else
                              "whole site (no inside_bay polygon; keys keep their Jervis Bay names)"),
        "classes": list(CLASSES), "reference_class": CLASSES[REFERENCE],
        "rules": {"majority": MAJORITY, "core": CORE, "trace": TRACE, "supersample_m": grid.dx / SUPERSAMPLE,
                  "min_compare_px": MIN_COMPARE_PX, "boot": a.boot, "boot_seed": BOOT_SEED,
                  "block_m": BLOCK_M},
        "error_sign": "e = SDB - lidar; positive = SDB reads too deep",
        **record_rules,
        "written_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sdb_version": __version__,
    }
    figs = []
    if not a.no_figures:
        from sdb import viz

        figs = [viz.substrate_contrasts(res_dir / "figures" / f"substrate_{a.scene}{tag}_bias_vs_sediment.png",
                                        record_rules[f"threshold_{MAJORITY:g}"]["vs_reference_inside_bay"],
                                        COMPARED, band_names,
                                        region="inside the bay" if poly else "whole site")]
    record["figures"] = [str(f) for f in figs]
    res_dir.mkdir(parents=True, exist_ok=True)
    jpath = res_dir / f"substrate_{a.scene}{tag}.json"
    jpath.write_text(json.dumps(_r(record), indent=2), encoding="utf-8")

    print(f"\n  {scope}, bias vs '{CLASSES[REFERENCE]}' (majority rule; core rule in brackets):")
    core = {(c["band_m"], c["class"]): c for c in record_rules[f"threshold_{CORE:g}"]["vs_reference_inside_bay"]}
    for c in record_rules[f"threshold_{MAJORITY:g}"]["vs_reference_inside_bay"]:
        if "bias_diff" in c:
            b = c["bias_diff"]
            k = core.get((c["band_m"], c["class"]), {}).get("bias_diff")
            ks = f"   [{k['point']:+.2f}]" if k else ""
            print(f"    {c['band_m']:>6} m  {c['class']:<18} n {c['n_class']:>7,}  "
                  f"{b['point']:+.2f} m [{b['lo']:+.2f}, {b['hi']:+.2f}]{ks}")
    if poly:
        print("\n  reef, open coast minus inside bay (bias):")
        for c in record_rules[f"threshold_{MAJORITY:g}"]["reef_open_minus_inside"]:
            if "bias_diff" in c:
                b = c["bias_diff"]
                print(f"    {c['band_m']:>6} m  {b['point']:+.2f} m [{b['lo']:+.2f}, {b['hi']:+.2f}]")
    print(f"\n  record -> {jpath}" + ("" if a.tag else f"\n  layers -> {scene_dir / 'substrate.tif'}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
