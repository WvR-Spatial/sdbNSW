"""Put the reference lidar on the Sentinel-2 grid -- exactly.

The lidar is a 5 m grid on GDA2020 / MGA zone 56; the scene a 10 m grid on
WGS84 / UTM zone 56S. Same projection; the datums differ by ~0.1 m at the 2018
epoch and PROJ treats the pair as a null transformation. So the lidar grid lies
in the scene's map plane, merely offset -- by (0.45, 1.42) m at Jervis Bay,
because the supplier shifted a round GDA94 grid to GDA2020 without resampling.

That makes aggregation a matter of exact overlap areas, computed separately per
axis: every 10 m pixel is the area-weighted mean of the 5 m cells it overlaps,
partial cells counted by the fraction that falls inside. No GDAL resampling
kernel, no version-dependent behaviour, and cheap enough to repeat at any
sub-pixel shift -- which coreg.py relies on. The plane assumption is checked at
run time, not trusted.

Per 10 m pixel this writes:
  z_mean     area-weighted mean elevation, m AHD (negative = below datum)
  coverage   fraction of the pixel covered by valid lidar
  relief     area-weighted std of the 5 m cells inside the pixel. Where the
             seabed changes steeply within 10 m, no single reference value is
             representative, however accurate the lidar. Error is stratified by
             this later.
  land_frac  fraction of the covered area above the water level

and a bit-flag mask saying why each pixel is, or is not, usable.

Imagery is never resampled. When coreg.py has measured an offset, the lidar is
aggregated onto the ground the image actually sees, and written on the scene's
own grid so the two stay pixel-for-pixel.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from sdb import __version__

# --------------------------------------------------------------------------
# Constants, with reasons
# --------------------------------------------------------------------------

#: Largest departure of the datum operation from a pure translation across the
#: grid that is accepted. Beyond it the "same plane" assumption fails and a
#: real reprojection would be needed. 1 cm is 0.1% of a pixel.
MAX_PLANE_NONUNIFORMITY_M = 0.01

#: A pixel must be fully covered by lidar to be used. Partial pixels mix known
#: seabed with a void, so their mean describes only part of what the sensor saw.
MIN_COVERAGE = 0.999

#: Depth range evaluated, metres below the water surface at overpass. Matches
#: the brief; the laser reached 42.7 m here, but published SDB work stops at 20.
DEPTH_WINDOW_M = (0.0, 20.0)

#: NIR reflectance above which a pixel that the lidar says is entirely water is
#: flagged. Median water NIR in the 7 Sep scene is 0.0025. Offshore this catches
#: whitewater and glint; in the top metre it mostly catches water that was far
#: shallower than assumed, or dry -- i.e. a water-level error. At an assumed
#: 0 m AHD it flags 73% of 0-1 m pixels at Jervis Bay, whatever the
#: co-registration: the tide was lower than assumed.
BRIGHT_WATER_NIR = 0.03

#: Assumed water level until waterlevel.py supplies the tide at overpass.
#: AHD is close to mean sea level; Jervis Bay's spring range is ~1.6 m.
DEFAULT_WATER_LEVEL_M = 0.0

FLAG_NO_LIDAR = 1
FLAG_LAND = 2
FLAG_DEPTH = 4
FLAG_CLOUD = 8
FLAG_BRIGHT_WATER = 16
FLAG_NO_IMAGE = 32
FLAG_NAMES = {
    FLAG_NO_LIDAR: "lidar coverage incomplete",
    FLAG_LAND: "any land in pixel",
    FLAG_DEPTH: "outside depth window",
    FLAG_CLOUD: "cloud or shadow (SCL)",
    FLAG_BRIGHT_WATER: "bright NIR over lidar water",
    FLAG_NO_IMAGE: "no image data",
}

DEPTH_BANDS_M = ((0, 2), (2, 5), (5, 10), (10, 15), (15, 20))

SCL_NODATA = (0, 1)
SCL_CLOUD = (3, 8, 9, 10)


# --------------------------------------------------------------------------
# Grids and exact area-weighted aggregation (pure)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Grid:
    """A north-up, axis-aligned raster grid. (x0, y0) is the upper-left corner;
    dx and dy are positive pixel sizes; nx columns, ny rows."""

    x0: float
    y0: float
    dx: float
    dy: float
    nx: int
    ny: int

    @classmethod
    def from_transform(cls, transform: Sequence[float], shape: Sequence[int]) -> "Grid":
        a, b, c, d, e, f = list(transform)[:6]
        if abs(b) > 1e-12 or abs(d) > 1e-12:
            raise ValueError("rotated or sheared grids are not supported")
        if a <= 0 or e >= 0:
            raise ValueError("expected a north-up grid (positive x size, negative y size)")
        return cls(float(c), float(f), float(a), float(-e), int(shape[1]), int(shape[0]))

    @property
    def shape(self) -> tuple[int, int]:
        return self.ny, self.nx

    def transform(self):
        from affine import Affine
        return Affine(self.dx, 0.0, self.x0, 0.0, -self.dy, self.y0)

    def shifted(self, de: float, dn: float) -> "Grid":
        return replace(self, x0=self.x0 + de, y0=self.y0 + dn)

    def window(self, row0: int, col0: int, nrows: int, ncols: int) -> "Grid":
        return replace(self, x0=self.x0 + col0 * self.dx, y0=self.y0 - row0 * self.dy,
                       nx=int(ncols), ny=int(nrows))

    def x_edges(self) -> np.ndarray:
        return self.x0 + self.dx * np.arange(self.nx + 1)

    def s_edges(self) -> np.ndarray:
        """Row edges as southing (-northing), so they ascend with row index."""
        return -self.y0 + self.dy * np.arange(self.ny + 1)

    def centres(self) -> tuple[np.ndarray, np.ndarray]:
        return (self.x0 + self.dx * (np.arange(self.nx) + 0.5),
                self.y0 - self.dy * (np.arange(self.ny) + 0.5))


def overlap_matrix(src_edges: np.ndarray, dst_edges: np.ndarray):
    """Sparse (n_dst x n_src) matrix of overlap LENGTHS between 1-D cells.

    Both edge arrays must ascend. Row k holds, for each source cell, how much of
    it lies inside destination cell k.
    """
    from scipy.sparse import csr_matrix

    src = np.asarray(src_edges, dtype=np.float64)
    dst = np.asarray(dst_edges, dtype=np.float64)
    n_src, n_dst = len(src) - 1, len(dst) - 1
    lo = np.clip(np.searchsorted(src, dst[:-1], side="right") - 1, 0, n_src - 1)
    hi = np.clip(np.searchsorted(src, dst[1:], side="left") - 1, 0, n_src - 1)
    span = int(max((hi - lo).max(initial=0), 0)) + 1
    k = np.repeat(np.arange(n_dst), span)
    j = (lo[:, None] + np.arange(span)[None, :]).ravel()
    inrange = j <= np.repeat(hi, span)
    k, j = k[inrange], j[inrange]
    ov = np.minimum(dst[k + 1], src[j + 1]) - np.maximum(dst[k], src[j])
    keep = ov > 0
    return csr_matrix((ov[keep], (k[keep], j[keep])), shape=(n_dst, n_src))


def area_weights(src: Grid, dst: Grid):
    """Per-axis overlap matrices (rows, cols) from a source grid to a destination grid."""
    return overlap_matrix(src.s_edges(), dst.s_edges()), overlap_matrix(src.x_edges(), dst.x_edges())


def block_sum(a: np.ndarray, wy, wx) -> np.ndarray:
    """Area-weighted sum of a source-grid array over each destination pixel (units x m^2)."""
    return np.asarray(wx @ np.asarray(wy @ a).T).T


def aggregate_dem(z: np.ndarray, valid: np.ndarray, src: Grid, dst: Grid, *,
                  water_level: float = DEFAULT_WATER_LEVEL_M) -> dict[str, np.ndarray]:
    """Exact area-weighted aggregation of a DEM onto another grid in the same plane.

    `src` must already be expressed in the destination's coordinates (apply any
    datum translation to it first); `dst` is where each output pixel actually
    is on the ground (apply any co-registration shift to it first).
    """
    wy, wx = area_weights(src, dst)
    v = valid.astype(np.float64)
    w = block_sum(v, wy, wx)
    zz = np.where(valid, z, 0.0).astype(np.float64)
    s1 = block_sum(zz, wy, wx)
    s2 = block_sum(zz * zz, wy, wx)
    del zz
    land = block_sum((valid & (z > water_level)).astype(np.float64), wy, wx)

    has = w > 0
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(has, s1 / w, np.nan)
        var = np.where(has, np.maximum(s2 / w - mean * mean, 0.0), np.nan)
        land_frac = np.where(has, land / w, np.nan)
    return {
        "z_mean": mean.astype(np.float32),
        "coverage": (w / (dst.dx * dst.dy)).astype(np.float32),
        "relief": np.sqrt(var).astype(np.float32),
        "land_frac": land_frac.astype(np.float32),
    }


class LandFractionField:
    """Land/water from a DEM at one water level, ready to aggregate onto any grid.

    Holds the float arrays once so that repeated aggregation -- one per trial
    shift in coreg.py -- costs only the two sparse products.
    """

    def __init__(self, z: np.ndarray, valid: np.ndarray, src: Grid, water_level: float):
        self.src = src
        self.v = valid.astype(np.float64)
        self.land = (valid & (z > water_level)).astype(np.float64)

    def on(self, dst: Grid) -> tuple[np.ndarray, np.ndarray]:
        """(land fraction of the covered area, coverage) on `dst`."""
        wy, wx = area_weights(self.src, dst)
        w = block_sum(self.v, wy, wx)
        land = block_sum(self.land, wy, wx)
        with np.errstate(invalid="ignore", divide="ignore"):
            lf = np.where(w > 0, land / w, np.nan)
        return lf, w / (dst.dx * dst.dy)


def land_fraction(z: np.ndarray, valid: np.ndarray, src: Grid, dst: Grid,
                  water_level: float) -> tuple[np.ndarray, np.ndarray]:
    """(land fraction of covered area, coverage) -- the cheap subset coreg needs."""
    return LandFractionField(z, valid, src, water_level).on(dst)


def plane_translation(src_crs: Any, dst_crs: Any, grid: Grid, *,
                      tol: float = MAX_PLANE_NONUNIFORMITY_M) -> tuple[tuple[float, float], dict[str, Any]]:
    """Check that src_crs -> dst_crs is a pure translation over `grid`, and return it.

    Transforms the grid's corners and centre with the best operation PROJ has
    available. If the operation moves them all by the same vector (to within
    `tol`), aggregation can proceed in one plane. Otherwise raises.
    """
    from pyproj import CRS
    from pyproj.transformer import TransformerGroup

    s, d = CRS.from_user_input(src_crs), CRS.from_user_input(dst_crs)
    if s == d:
        return (0.0, 0.0), {"operation": "identical CRS", "translation_m": [0.0, 0.0],
                            "nonuniformity_m": 0.0}
    tg = TransformerGroup(s, d, always_xy=True)
    if not tg.transformers:
        raise ValueError(f"no available transformation {s.to_string()} -> {d.to_string()}")
    t = tg.transformers[0]
    xs = np.array([grid.x0, grid.x0 + grid.nx * grid.dx] * 2 + [grid.x0 + grid.nx * grid.dx / 2])
    ys = np.array([grid.y0] * 2 + [grid.y0 - grid.ny * grid.dy] * 2 + [grid.y0 - grid.ny * grid.dy / 2])
    X, Y = t.transform(xs, ys)
    dx, dy = np.asarray(X) - xs, np.asarray(Y) - ys
    tx, ty = float(dx.mean()), float(dy.mean())
    nonuni = float(np.max(np.hypot(dx - tx, dy - ty)))
    info = {"operation": t.description, "stated_accuracy_m": t.accuracy,
            "translation_m": [round(tx, 4), round(ty, 4)], "nonuniformity_m": round(nonuni, 6)}
    if nonuni > tol:
        raise ValueError(f"{s.to_string()} -> {d.to_string()} is not a translation over this grid "
                         f"(departs by {nonuni:.3f} m); a real reprojection is needed")
    return (tx, ty), info


# --------------------------------------------------------------------------
# Masks and summary (pure)
# --------------------------------------------------------------------------


def analysis_mask(ref: dict[str, np.ndarray], *, water_level: float = DEFAULT_WATER_LEVEL_M,
                  depth_window: tuple[float, float] = DEPTH_WINDOW_M,
                  scl: np.ndarray | None = None, nir: np.ndarray | None = None) -> np.ndarray:
    """Bit flags per pixel; 0 means usable. A pixel may carry several flags."""
    flags = np.zeros(ref["z_mean"].shape, dtype=np.uint8)
    cov = ref["coverage"]
    has = cov > 0
    flags[~(cov >= MIN_COVERAGE)] |= FLAG_NO_LIDAR
    flags[has & (ref["land_frac"] > 0)] |= FLAG_LAND
    depth = water_level - ref["z_mean"]
    lo, hi = depth_window
    flags[has & ~((depth >= lo) & (depth <= hi))] |= FLAG_DEPTH
    if scl is not None:
        flags[np.isin(scl, SCL_CLOUD)] |= FLAG_CLOUD
        flags[np.isin(scl, SCL_NODATA)] |= FLAG_NO_IMAGE
    if nir is not None:
        flags[~np.isfinite(nir)] |= FLAG_NO_IMAGE
        with np.errstate(invalid="ignore"):
            flags[has & (ref["land_frac"] == 0) & (nir > BRIGHT_WATER_NIR)] |= FLAG_BRIGHT_WATER
    return flags


def summarise(ref: dict[str, np.ndarray], flags: np.ndarray, *, pixel_area_m2: float,
              water_level: float = DEFAULT_WATER_LEVEL_M) -> dict[str, Any]:
    """Counts by flag, usable area by depth band, and sub-pixel relief by band."""
    usable = flags == 0
    depth = water_level - ref["z_mean"]
    out: dict[str, Any] = {
        "pixels_total": int(flags.size),
        "pixels_usable": int(usable.sum()),
        "usable_km2": round(usable.sum() * pixel_area_m2 / 1e6, 2),
        "flagged_any": {name: int(((flags & bit) > 0).sum()) for bit, name in FLAG_NAMES.items()},
        "by_depth_band": [],
    }
    for lo, hi in DEPTH_BANDS_M:
        m = usable & (depth >= lo) & (depth < hi if hi < DEPTH_BANDS_M[-1][1] else depth <= hi)
        rel = ref["relief"][m]
        out["by_depth_band"].append({
            "band_m": f"{lo}-{hi}", "pixels": int(m.sum()),
            "km2": round(m.sum() * pixel_area_m2 / 1e6, 2),
            "relief_median_m": round(float(np.median(rel)), 3) if rel.size else None,
            "relief_p90_m": round(float(np.percentile(rel, 90)), 3) if rel.size else None,
        })
    return out


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------


def read_dem(path: Path) -> tuple[np.ndarray, np.ndarray, Grid, Any]:
    import rasterio

    with rasterio.open(path) as s:
        m = s.read(1, masked=True)
        z = np.asarray(m.data, dtype=np.float32)
        valid = ~np.ma.getmaskarray(m) & np.isfinite(z) & (z > -1e30)
        return z, valid, Grid.from_transform(s.transform, s.shape), s.crs


def read_scene(scene_dir: Path) -> dict[str, Any]:
    import rasterio

    with rasterio.open(scene_dir / "reflectance.tif") as s:
        bands = {d: s.read(i + 1) for i, d in enumerate(s.descriptions)}
        out = {"grid": Grid.from_transform(s.transform, s.shape), "crs": s.crs, **bands}
    scl_path = scene_dir / "scl.tif"
    if scl_path.exists():
        with rasterio.open(scl_path) as s:
            out["scl"] = s.read(1)
    return out


def write_layers(path: Path, layers: dict[str, np.ndarray], grid: Grid, crs: Any,
                 names: Sequence[str], dtype: str = "float32", nodata: Any = float("nan")) -> None:
    import rasterio

    profile = dict(driver="GTiff", width=grid.nx, height=grid.ny, count=len(names), dtype=dtype,
                   crs=crs, transform=grid.transform(), nodata=nodata, tiled=True,
                   blockxsize=256, blockysize=256, compress="deflate",
                   **({"predictor": 3} if dtype == "float32" else {}))
    with rasterio.open(path, "w", **profile) as dst:
        for i, n in enumerate(names, start=1):
            dst.write(layers[n].astype(dtype), i)
            dst.set_band_description(i, n)


def md5(path: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def load_coreg(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    import yaml

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--site", default="jervis_bay")
    p.add_argument("--config", type=Path, default=Path("config/sites.yml"))
    p.add_argument("--scene", required=True, help="item id under data/raw/scenes/")
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--out", type=Path, default=Path("outputs"))
    p.add_argument("--water-level", type=float, default=None,
                   help="water level at overpass, m AHD. Default: outputs/waterlevel_<scene>.json "
                        "if present, else assumed 0.0")
    p.add_argument("--depth-max", type=float, default=DEPTH_WINDOW_M[1])
    p.add_argument("--coreg", choices=("auto", "off"), default="auto",
                   help="auto: apply outputs/coreg_<scene>.json if its verdict is 'apply'")
    p.add_argument("--dem", type=Path, default=None,
                   help="sensitivity only, with --tag: a different reference DEM (repo-relative)")
    p.add_argument("--tag", default=None,
                   help="sensitivity run (another DEM, or another --water-level): writes "
                        "reference_<tag>.tif / mask_<tag>.tif and "
                        "<out>/sensitivity/reference_<scene>_<tag>.json; never touches the primary")
    a = p.parse_args(argv)
    if a.dem is not None and a.tag is None:
        p.error("--dem needs --tag: a different DEM must never overwrite the registered reference")

    site_cfg = yaml.safe_load(a.config.read_text(encoding="utf-8"))["sites"][a.site]
    dem_rel = a.dem if a.dem is not None else Path(site_cfg["reference_dem"])
    dem_path = a.root / dem_rel
    scene_dir = a.root / "data" / "raw" / "scenes" / a.scene
    sfx = f"_{a.tag}" if a.tag else ""
    print(f"{a.scene}\n  lidar: {dem_path}"
          + (f"\n  SENSITIVITY '{a.tag}': not the registered reference" if a.tag else ""))

    z, valid, src, src_crs = read_dem(dem_path)
    scene = read_scene(scene_dir)
    dst = scene["grid"]
    (tx, ty), datum = plane_translation(src_crs, scene["crs"], src)
    print(f"  datum: {datum['operation']}\n         translation ({tx:+.4f}, {ty:+.4f}) m, "
          f"non-uniformity {datum['nonuniformity_m'] * 1000:.2f} mm -> same plane")
    fx = (src.x0 + tx - dst.x0) % dst.dx
    fy = (src.y0 + ty - dst.y0) % dst.dy
    print(f"  lidar cell edges sit {fx:.3f} m east and {fy:.3f} m north of the scene's pixel "
          f"edges -> area-weighted aggregation")

    shift, coreg_note = (0.0, 0.0), "not applied (no coreg file)"
    cpath = a.out / f"coreg_{a.scene}.json"
    creg = load_coreg(cpath) if a.coreg == "auto" else None
    if a.coreg == "off":
        coreg_note = "not applied (--coreg off)"
    elif creg is not None:
        if creg.get("verdict") == "apply":
            shift = (float(creg["shift_m"]["east"]), float(creg["shift_m"]["north"]))
            coreg_note = f"APPLIED from {cpath.name}"
        else:
            coreg_note = f"not applied: {cpath.name} verdict is '{creg.get('verdict')}'"
    print(f"  co-registration: {coreg_note}"
          + (f"  ({shift[0]:+.2f} E, {shift[1]:+.2f} N m)" if shift != (0.0, 0.0) else ""))

    wpath = a.out / f"waterlevel_{a.scene}.json"
    if a.water_level is not None:
        wl_src = "supplied on the command line"
    elif wpath.exists():
        wrec = json.loads(wpath.read_text(encoding="utf-8"))
        a.water_level = float(wrec["water_level_m_ahd"])
        wl_src = f"{wrec['status']} ({wrec['method']}) from {wpath.name}"
    else:
        a.water_level = DEFAULT_WATER_LEVEL_M
        wl_src = "assumed (AHD ~ mean sea level)"

    ref = aggregate_dem(z, valid, src.shifted(tx, ty), dst.shifted(*shift),
                        water_level=a.water_level)
    flags = analysis_mask(ref, water_level=a.water_level, depth_window=(0.0, a.depth_max),
                          scl=scene.get("scl"), nir=scene.get("nir"))
    summ = summarise(ref, flags, pixel_area_m2=dst.dx * dst.dy, water_level=a.water_level)

    print(f"  water level: {a.water_level:+.3f} m AHD, {wl_src}\n")
    print(f"  usable pixels: {summ['pixels_usable']:,} ({summ['usable_km2']} km2) "
          f"of {summ['pixels_total']:,}")
    for name, n in summ["flagged_any"].items():
        print(f"    {name:<34} {n:>10,}")
    print(f"\n  {'depth m':>8} {'pixels':>9} {'km2':>7} {'relief median':>14} {'p90':>7}")
    for b in summ["by_depth_band"]:
        med = "--" if b["relief_median_m"] is None else f"{b['relief_median_m']:.2f}"
        p90 = "--" if b["relief_p90_m"] is None else f"{b['relief_p90_m']:.2f}"
        print(f"  {b['band_m']:>8} {b['pixels']:>9,} {b['km2']:>7} {med:>14} {p90:>7}")

    ref_tif, mask_tif = scene_dir / f"reference{sfx}.tif", scene_dir / f"mask{sfx}.tif"
    write_layers(ref_tif, ref, dst, scene["crs"], ("z_mean", "coverage", "relief", "land_frac"))
    write_layers(mask_tif, {"flags": flags}, dst, scene["crs"], ("flags",),
                 dtype="uint8", nodata=None)

    out_dir = a.out / "sensitivity" if a.tag else a.out
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "scene": a.scene,
        "sensitivity": ({"tag": a.tag, "status": "SENSITIVITY: not the registered reference; "
                         "report beside the primary result, never instead of it"}
                        if a.tag else None),
        "lidar": {"path": str(dem_rel), "md5": md5(dem_path),
                  "crs": str(src_crs), "grid": vars(src)},
        "scene_grid": {"crs": str(scene["crs"]), "grid": vars(dst)},
        "datum": datum,
        "coregistration": {"note": coreg_note, "shift_applied_m": list(shift)},
        "water_level_m_ahd": a.water_level, "water_level_source": wl_src,
        "depth_window_m": [0.0, a.depth_max],
        "flags": {str(k): v for k, v in FLAG_NAMES.items()},
        "summary": summ,
        "outputs": [str(ref_tif), str(mask_tif)],
        "written_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sdb_version": __version__,
    }
    jpath = out_dir / f"reference_{a.scene}{sfx}.json"
    jpath.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"\n  wrote {ref_tif.name} + {mask_tif.name} -> {scene_dir}\n  record -> {jpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
