"""Check and merge ELVIS 5 m DEM extracts without resampling them.

ELVIS mosaics an order that touches more than one source raster, and its
"Average 16" interpolation then replaces every cell with the mean of a 4x4
window -- smoothing over 20 m and shifting the surface by half a cell
(data/README.md). An order kept inside one source raster comes back with the
supplier's own values. Two tests tell the difference:

  check   Grid phase (origin modulo 5 m), and the share of underwater cells on
          a whole-centimetre lattice: ~0.97+ for native values, ~0.1 (chance)
          after averaging. With --against, cell-by-cell identity against
          another extract over their overlap.
  merge   Union of extracts of ONE product. Refuses unless every input shares
          CRS, cell size and grid phase and every overlap is bit-identical, so
          the result is the supplier's values with nothing interpolated.

    python scripts/dem_extracts.py check A.tif [--against B.tif]
    python scripts/dem_extracts.py merge OUT.tif A.tif B.tif [...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import from_bounds

CELL_M = 5.0
LATTICE_TOL_CM = 0.05          # within 0.5 mm of a whole centimetre
NATIVE_MIN_LATTICE = 0.9       # observed: native 0.96-0.99, averaged 0.11


def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def lattice_share(z: np.ndarray) -> float:
    """Share of finite cells within LATTICE_TOL_CM of a whole centimetre."""
    v = z[np.isfinite(z)].astype("f8")
    if v.size == 0:
        return float("nan")
    r = np.abs(v * 100 - np.round(v * 100))
    return float(np.mean(r < LATTICE_TOL_CM))


def read(path: Path):
    with rasterio.open(path) as d:
        z = d.read(1, masked=True).astype("f8").filled(np.nan)
        return z, d.transform, d.crs, d.profile


def phase(t) -> tuple[float, float]:
    return round(t.c % CELL_M, 4), round(t.f % CELL_M, 4)


def overlap(za, ta, zb, tb):
    """Cells of a and b over their common extent, or None if they don't overlap."""
    ha, wa = za.shape
    hb, wb = zb.shape
    l = max(ta.c, tb.c)
    r = min(ta.c + wa * ta.a, tb.c + wb * tb.a)
    t = min(ta.f, tb.f)
    b = max(ta.f + ha * ta.e, tb.f + hb * tb.e)
    if r <= l or t <= b:
        return None
    w1, w2 = from_bounds(l, b, r, t, transform=ta), from_bounds(l, b, r, t, transform=tb)
    r1, c1, r2, c2 = (round(w1.row_off), round(w1.col_off), round(w2.row_off), round(w2.col_off))
    h, w = round(w1.height), round(w1.width)
    return za[r1:r1 + h, c1:c1 + w], zb[r2:r2 + h, c2:c2 + w]


def compare(za, ta, zb, tb) -> dict:
    ov = overlap(za, ta, zb, tb)
    if ov is None:
        return {"overlap_cells": 0}
    a, b = ov
    both = np.isfinite(a) & np.isfinite(b)
    d = np.abs(a - b)[both]
    return {"overlap_cells": int(both.sum()), "identical_cells": int((d == 0).sum()),
            "max_abs_diff_m": float(d.max()) if d.size else None}


def cmd_check(a) -> int:
    z, t, crs, _ = read(a.dem)
    under = np.where(z < 0, z, np.nan)
    rep = {"dem": str(a.dem), "crs": str(crs), "phase_xy_m": phase(t), "shape": list(z.shape),
           "lattice_share_underwater": round(lattice_share(under), 3)}
    rep["verdict"] = ("native" if rep["lattice_share_underwater"] >= NATIVE_MIN_LATTICE
                      else "RESAMPLED (likely ELVIS Average 16)")
    if a.against:
        zb, tb, _, _ = read(a.against)
        rep["against"] = {"dem": str(a.against), "phase_xy_m": phase(tb), **compare(z, t, zb, tb)}
    print(json.dumps(rep, indent=2))
    return 0 if rep["verdict"] == "native" else 1


def cmd_merge(a) -> int:
    srcs = [read(p) for p in a.inputs]
    z0, t0, crs0, prof0 = srcs[0]
    for p, (z, t, crs, _) in zip(a.inputs, srcs):
        if crs != crs0 or not np.isclose(t.a, t0.a) or not np.isclose(t.e, t0.e):
            sys.exit(f"{p}: CRS or cell size differs from {a.inputs[0]}")
        if phase(t) != phase(t0):
            sys.exit(f"{p}: grid phase {phase(t)} != {phase(t0)}; merging would resample")
        if lattice_share(np.where(z < 0, z, np.nan)) < NATIVE_MIN_LATTICE:
            sys.exit(f"{p}: underwater values are not on the centimetre lattice -- resampled extract")
    checks = []
    for i in range(len(srcs)):
        for j in range(i + 1, len(srcs)):
            c = compare(srcs[i][0], srcs[i][1], srcs[j][0], srcs[j][1])
            if c["overlap_cells"] and c["identical_cells"] != c["overlap_cells"]:
                sys.exit(f"{a.inputs[i]} and {a.inputs[j]} disagree on {c['overlap_cells'] - c['identical_cells']} "
                         f"overlapping cells (max {c['max_abs_diff_m']} m); not one product")
            checks.append({"a": a.inputs[i].name, "b": a.inputs[j].name, **c})

    cell = t0.a
    left = min(t.c for _, t, _, _ in srcs)
    top = max(t.f for _, t, _, _ in srcs)
    right = max(t.c + z.shape[1] * cell for z, t, _, _ in srcs)
    bottom = min(t.f + z.shape[0] * t.e for z, t, _, _ in srcs)
    w, h = round((right - left) / cell), round((top - bottom) / cell)
    out = np.full((h, w), np.nan)
    tout = from_origin(left, top, cell, cell)
    for z, t, _, _ in srcs:
        r0, c0 = round((top - t.f) / cell), round((t.c - left) / cell)
        tgt = out[r0:r0 + z.shape[0], c0:c0 + z.shape[1]]
        fill = np.isfinite(z) & ~np.isfinite(tgt)
        tgt[fill] = z[fill]

    nodata = prof0.get("nodata")
    prof = dict(prof0, height=h, width=w, transform=tout, dtype="float32",
                compress="lzw", tiled=True, blockxsize=256, blockysize=256)
    data = np.where(np.isfinite(out), out, nodata if nodata is not None else np.nan).astype("float32")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(a.out, "w", **prof) as dst:
        dst.write(data, 1)
        dst.update_tags(AREA_OR_POINT="Area")

    # The written file must reproduce every input cell exactly.
    zm, tm, _, _ = read(a.out)
    for p, (z, t, _, _) in zip(a.inputs, srcs):
        c = compare(zm, tm, z, t)
        if c["identical_cells"] != int(np.isfinite(z).sum()):
            sys.exit(f"merged file does not reproduce {p} exactly: {c}")

    side = {"output": a.out.name, "md5": md5(a.out), "phase_xy_m": phase(tout),
            "shape": [h, w], "bounds": [left, bottom, right, top],
            "inputs": [{"path": str(p), "md5": md5(p)} for p in a.inputs],
            "overlap_checks": checks, "method": "union, no resampling; first input wins where "
            "both have data (overlaps are verified identical, so order does not matter)",
            "written_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    a.out.with_suffix(".json").write_text(json.dumps(side, indent=2), encoding="utf-8")
    print(json.dumps(side, indent=2))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("dem", type=Path)
    c.add_argument("--against", type=Path)
    m = sub.add_parser("merge")
    m.add_argument("out", type=Path)
    m.add_argument("inputs", type=Path, nargs="+")
    a = p.parse_args(argv)
    return cmd_check(a) if a.cmd == "check" else cmd_merge(a)


if __name__ == "__main__":
    sys.exit(main())
