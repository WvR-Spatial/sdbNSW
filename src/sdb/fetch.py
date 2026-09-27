"""Read Sentinel-2 L2A pixels over the AOI -- and only over the AOI.

Two subcommands:

  quicklook  For the top candidates from stac.py, read the scene classification
             (SCL) and true-colour assets over the AOI and report what the
             tile-wide cloud figure cannot: cloud over *this* AOI. Writes a
             side-by-side panel with a water-optimised stretch so you can judge
             whether the seabed is visible at all.

  scene      For the chosen item, read blue, green, red, nir and SCL over the
             AOI, convert to reflectance with the offset correct for its
             processing baseline, check that conversion against the physics of
             water, and write a GeoTIFF stack plus a provenance sidecar to
             data/raw/scenes/<item id>/.

Reads are windowed COG requests, so only the AOI's pixels leave AWS, never the
110 km tile. Imagery stays on its native UTM grid: the lidar is aggregated onto
it later, never the other way round.
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
from sdb.stac import load_site, needs_boa_offset

# --------------------------------------------------------------------------
# Constants, with reasons
# --------------------------------------------------------------------------

#: Sentinel-2 SCL classes. SCL is a land/atmosphere product rather than a water
#: product -- it under-calls water over bright shallow sand -- so it is used
#: for cloud and as a *conservative* water mask, never as the shoreline.
SCL_NODATA = (0, 1)              # no data, saturated/defective
SCL_CLOUD = (3, 8, 9, 10)        # shadow, medium, high, thin cirrus
SCL_WATER = 6

#: 10, 20 and 60 m bands of one granule share an upper-left corner. A 10 m
#: window whose offsets and lengths are multiples of 6 therefore maps onto whole
#: pixels at 20 m and 60 m, so coarser bands are upsampled by exact replication
#: instead of GDAL resampling of categorical data.
GRID_MULTIPLE = 6

#: Offset plausibility bounds on the median BOA reflectance of *water*.
#: Water absorbs red and near-infrared strongly, so their true values sit near
#: zero. The baseline >= 04.00 offset is an additive 0.1 on every band. Getting
#: it wrong therefore moves these medians by ~0.1 -- far outside the band below,
#: in either direction -- while blue and green, which carry the depth signal,
#: can legitimately sit anywhere from 0.02 to 0.12 and would not discriminate.
#: The lower bound tolerates atmospheric over-correction noise.
PLAUSIBLE_WATER_RED_NIR = (-0.02, 0.06)
MIN_WATER_PIXELS = 1000

#: Earth Search v1 names assets by common name; older catalogues by band id.
ASSET_KEYS: dict[str, tuple[str, ...]] = {
    "blue": ("blue", "B02"),
    "green": ("green", "B03"),
    "red": ("red", "B04"),
    "nir": ("nir", "B08"),
    "scl": ("scl", "SCL"),
    "visual": ("visual", "TCI"),
}
STACK_BANDS = ("blue", "green", "red", "nir")

GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF,.tiff",
    AWS_NO_SIGN_REQUEST="YES",
    AWS_REGION="us-west-2",
    GDAL_HTTP_MAX_RETRY="4",
    GDAL_HTTP_RETRY_DELAY="1",
)


# --------------------------------------------------------------------------
# Pure functions
# --------------------------------------------------------------------------


def scl_stats(scl: np.ndarray) -> dict[str, float]:
    """Cloud and water fractions over the AOI, from the SCL layer.

    Percentages are of *valid* pixels, so a window that clips the swath edge is
    not mistaken for a clear one.
    """
    valid = ~np.isin(scl, SCL_NODATA)
    n = int(valid.sum())
    if n == 0:
        nan = float("nan")
        return {"aoi_valid_pct": 0.0, "aoi_cloud_pct": nan, "aoi_water_pct": nan}
    cloud = np.isin(scl, SCL_CLOUD) & valid
    water = (scl == SCL_WATER) & valid
    return {
        "aoi_valid_pct": round(100.0 * n / scl.size, 2),
        "aoi_cloud_pct": round(100.0 * int(cloud.sum()) / n, 2),
        "aoi_water_pct": round(100.0 * int(water.sum()) / n, 2),
    }


@dataclass(frozen=True)
class Scaling:
    """reflectance = DN * scale + offset, and where that came from."""

    scale: float
    offset: float
    source: str
    agrees_with_baseline: bool | None


def reflectance_scaling(raster_bands: list[dict[str, Any]] | None,
                        processing_baseline: str | float | None) -> Scaling:
    """Decide how to turn digital numbers into reflectance, and say how.

    The asset's own `raster:bands` metadata wins when present, because it is the
    publisher's statement about these exact bytes. It is cross-checked against
    the processing-baseline rule; a disagreement is reported, not silently
    resolved, and the pixel-level plausibility check arbitrates.
    """
    rule = needs_boa_offset(processing_baseline)
    if raster_bands:
        b = raster_bands[0]
        if "scale" in b:
            scale = float(b["scale"])
            offset = float(b.get("offset", 0.0) or 0.0)
            has_offset = not math.isclose(offset, 0.0, abs_tol=1e-9)
            agrees = None if rule is None else (has_offset == rule)
            return Scaling(scale, offset, "asset raster:bands", agrees)
    if rule is True:
        return Scaling(1e-4, -0.1, "derived: baseline >= 04.00", True)
    if rule is False:
        return Scaling(1e-4, 0.0, "derived: baseline < 04.00", True)
    raise ValueError("cannot determine reflectance scaling: the asset declares no "
                     "raster:bands and the item has no processing baseline")


def apply_scaling(dn: np.ndarray, s: Scaling, nodata: float | int | None = 0) -> np.ndarray:
    """DN -> float32 reflectance; the product's nodata value becomes NaN."""
    out = dn.astype("float32") * np.float32(s.scale) + np.float32(s.offset)
    if nodata is not None:
        out[dn == nodata] = np.nan
    return out


def offset_plausibility(red: np.ndarray, nir: np.ndarray, water: np.ndarray,
                        *, bounds: tuple[float, float] = PLAUSIBLE_WATER_RED_NIR,
                        min_pixels: int = MIN_WATER_PIXELS) -> dict[str, Any]:
    """Check the reflectance conversion against what water must look like.

    Returns a verdict of "pass", "fail" or "insufficient". A fail means the
    offset is almost certainly missing (medians ~+0.1 too high) or applied twice
    (~-0.1 too low); nothing downstream should be computed from that stack.
    """
    m = water & np.isfinite(red) & np.isfinite(nir)
    n = int(m.sum())
    if n < min_pixels:
        return {"verdict": "insufficient", "n_water_pixels": n,
                "reason": f"only {n} SCL water pixels; need {min_pixels}"}
    r_med, n_med = float(np.median(red[m])), float(np.median(nir[m]))
    lo, hi = bounds
    ok = lo <= r_med <= hi and lo <= n_med <= hi
    reason = "red and nir water medians inside bounds" if ok else (
        "water medians outside bounds: offset likely "
        + ("MISSING" if max(r_med, n_med) > hi else "APPLIED TWICE"))
    return {"verdict": "pass" if ok else "fail", "n_water_pixels": n,
            "median_red": round(r_med, 4), "median_nir": round(n_med, 4),
            "bounds": list(bounds), "reason": reason}


def aligned_window(width: int, height: int, transform, crs, bbox_wgs84: Sequence[float],
                   multiple: int = GRID_MULTIPLE):
    """Pixel window on a 10 m grid covering the AOI, snapped for band alignment.

    Offsets snap down and far edges snap up to multiples of `multiple`, so the
    window always *contains* the AOI and maps to whole pixels at 20 m and 60 m.
    Returns (window, clipped): `clipped` is True when the AOI runs off the tile
    and the window had to be cut back to the raster's extent.
    """
    from rasterio.warp import transform_bounds
    from rasterio.windows import Window, from_bounds

    l, b, r, t = transform_bounds("EPSG:4326", crs, *bbox_wgs84, densify_pts=21)
    w = from_bounds(l, b, r, t, transform=transform)
    c0 = math.floor(w.col_off / multiple) * multiple
    r0 = math.floor(w.row_off / multiple) * multiple
    c1 = math.ceil((w.col_off + w.width) / multiple) * multiple
    r1 = math.ceil((w.row_off + w.height) / multiple) * multiple
    clipped = c0 < 0 or r0 < 0 or c1 > width or r1 > height
    c0, r0 = max(c0, 0), max(r0, 0)
    c1 = min(c1, width - width % multiple)
    r1 = min(r1, height - height % multiple)
    return Window(c0, r0, c1 - c0, r1 - r0), clipped


def upsample_exact(a: np.ndarray, factor: int) -> np.ndarray:
    """Nearest-neighbour upsample by pixel replication. Right for categorical data."""
    return np.repeat(np.repeat(a, factor, axis=0), factor, axis=1)


def water_stretch(rgb: np.ndarray, water: np.ndarray, pct=(2, 98)) -> np.ndarray:
    """Per-channel percentile stretch computed over water only.

    A true-colour image stretched for land shows the sea as near-black; this
    spends the whole display range on the water so seabed texture is visible.
    Land saturates, deliberately.
    """
    out = np.zeros(rgb.shape, dtype="float32")
    for i in range(rgb.shape[0]):
        ch = rgb[i].astype("float32")
        px = ch[water & np.isfinite(ch)]
        if px.size < 50:
            px = ch[np.isfinite(ch)]
        lo, hi = np.percentile(px, pct) if px.size else (0.0, 1.0)
        out[i] = np.clip((ch - lo) / max(hi - lo, 1e-6), 0, 1)
    return out


def pick_asset(assets: dict[str, Any], band: str) -> tuple[str, Any]:
    for key in ASSET_KEYS[band]:
        if key in assets:
            return key, assets[key]
    raise KeyError(f"item has no {band} asset (looked for {ASSET_KEYS[band]})")


# --------------------------------------------------------------------------
# Raster I/O -- local paths and https/s3 hrefs are read identically
# --------------------------------------------------------------------------


def read_aoi_stack(hrefs: dict[str, str], bbox_wgs84: Sequence[float],
                   scalings: dict[str, Scaling] | None = None,
                   bands: Sequence[str] = STACK_BANDS) -> dict[str, Any]:
    """Windowed read of 10 m bands plus SCL, aligned on the 10 m grid.

    `hrefs` maps band names (and "scl") to anything rasterio can open. When
    `scalings` is given the 10 m bands come back as reflectance, else as DN.
    """
    import rasterio

    with rasterio.Env(**GDAL_ENV):
        with rasterio.open(hrefs[bands[0]]) as ref:
            win, clipped = aligned_window(ref.width, ref.height, ref.transform,
                                          ref.crs, bbox_wgs84)
            transform = ref.window_transform(win)
            crs, res10 = ref.crs, ref.res[0]

        out: dict[str, Any] = {"transform": transform, "crs": crs, "clipped": clipped,
                               "shape": (int(win.height), int(win.width))}
        for band in bands:
            with rasterio.open(hrefs[band]) as src:
                if src.res[0] != res10:
                    raise ValueError(f"{band} is {src.res[0]} m; stack expects {res10} m")
                dn = src.read(1, window=win)
                out[band] = apply_scaling(dn, scalings[band]) if scalings else dn

        if "scl" in hrefs:
            with rasterio.open(hrefs["scl"]) as src:
                f = int(round(src.res[0] / res10))
                from rasterio.windows import Window
                w20 = Window(win.col_off // f, win.row_off // f, win.width // f, win.height // f)
                scl = upsample_exact(src.read(1, window=w20), f)
            if scl.shape != out["shape"]:
                raise ValueError(f"SCL {scl.shape} does not align with 10 m stack {out['shape']}")
            out["scl"] = scl
    return out


def write_stack(path: Path, arrs: dict[str, np.ndarray], transform, crs,
                bands: Sequence[str] = STACK_BANDS) -> None:
    import rasterio

    h, w = arrs[bands[0]].shape
    profile = dict(driver="GTiff", width=w, height=h, count=len(bands), dtype="float32",
                   crs=crs, transform=transform, nodata=float("nan"), tiled=True,
                   blockxsize=256, blockysize=256, compress="deflate", predictor=3)
    with rasterio.open(path, "w", **profile) as dst:
        for i, b in enumerate(bands, start=1):
            dst.write(arrs[b].astype("float32"), i)
            dst.set_band_description(i, b)


def write_scl(path: Path, scl: np.ndarray, transform, crs) -> None:
    import rasterio

    h, w = scl.shape
    with rasterio.open(path, "w", driver="GTiff", width=w, height=h, count=1,
                       dtype="uint8", crs=crs, transform=transform, nodata=0,
                       tiled=True, blockxsize=256, blockysize=256,
                       compress="deflate") as dst:
        dst.write(scl.astype("uint8"), 1)
        dst.set_band_description(1, "scl")


# --------------------------------------------------------------------------
# STAC access -- the only network-facing part
# --------------------------------------------------------------------------


def get_items(ids: Sequence[str], stac_url: str, collection: str):
    from pystac_client import Client

    found = {it.id: it for it in Client.open(stac_url)
             .search(collections=[collection], ids=list(ids)).items()}
    missing = [i for i in ids if i not in found]
    if missing:
        raise SystemExit(f"not found in {collection}: {missing}")
    return [found[i] for i in ids]


def _bbox_for(site_cfg: dict[str, Any], site_bbox, which: str):
    if which == "delivered" and site_cfg.get("delivered_bbox"):
        return tuple(site_cfg["delivered_bbox"]), "delivered DEM extent"
    return tuple(site_bbox), "lidar block extent"


def _site_cfg(config: Path, key: str) -> dict[str, Any]:
    import yaml
    return yaml.safe_load(config.read_text(encoding="utf-8"))["sites"][key]


# --------------------------------------------------------------------------
# Subcommands
# --------------------------------------------------------------------------


def cmd_quicklook(a) -> int:
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    site, defaults = load_site(a.config, a.site)
    bbox, bbox_src = _bbox_for(_site_cfg(a.config, a.site), site.bbox, a.bbox)
    cand = pd.read_csv(a.candidates or a.out / f"candidates_{site.name}.csv")
    if "status" in cand.columns:
        cand = cand[cand["status"] == "kept"]
    ids = list(a.ids) if a.ids else list(cand["id"].head(a.top))
    print(f"{site.label}: quicklook of {len(ids)} scene(s) over the {bbox_src}\n")

    items = get_items(ids, defaults["stac_url"], defaults["collection"])
    rows, panels = [], []
    for it in items:
        hrefs = {b: pick_asset(it.assets, b)[1].href for b in ("scl", "visual")}
        import rasterio
        with rasterio.Env(**GDAL_ENV):
            with rasterio.open(hrefs["visual"]) as src:
                win, clipped = aligned_window(src.width, src.height, src.transform,
                                              src.crs, bbox)
                rgb = src.read((1, 2, 3), window=win)
            with rasterio.open(hrefs["scl"]) as src:
                from rasterio.windows import Window
                w20 = Window(win.col_off // 2, win.row_off // 2, win.width // 2, win.height // 2)
                scl = upsample_exact(src.read(1, window=w20), 2)
        st = scl_stats(scl)
        c = cand[cand["id"] == it.id]
        row = {"id": it.id, "datetime_utc": it.properties["datetime"][:16].replace("T", " "),
               "days_from_lidar": int(c["days_from_lidar"].iloc[0]) if len(c) else None,
               "tile_cloud_pct": float(c["cloud_pct"].iloc[0]) if len(c) else None,
               **st, "clipped": clipped}
        rows.append(row)
        panels.append((row, water_stretch(rgb, scl == SCL_WATER)))
        print(f"  {row['datetime_utc']}  +{row['days_from_lidar']} d   tile cloud "
              f"{row['tile_cloud_pct']:5.1f}%  ->  AOI cloud {st['aoi_cloud_pct']:5.1f}%   "
              f"AOI water {st['aoi_water_pct']:5.1f}%   {it.id}")

    a.out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(a.out / f"quicklook_{site.name}.csv", index=False)

    fig, axes = plt.subplots(1, len(panels), figsize=(5.2 * len(panels), 6.4),
                             facecolor="#0f172a", squeeze=False)
    for ax, (row, img) in zip(axes[0], panels):
        ax.imshow(np.moveaxis(img, 0, -1), interpolation="nearest")
        ax.set_title(f"{row['datetime_utc'][:10]}  ·  +{row['days_from_lidar']} d\n"
                     f"AOI cloud {row['aoi_cloud_pct']:.1f}%   (tile {row['tile_cloud_pct']:.1f}%)",
                     color="#e2e8f0", fontsize=10)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_color("#334155")
    fig.suptitle(f"{site.label} — true colour, stretched over water only (land saturates)",
                 color="#94a3b8", fontsize=10)
    fig.tight_layout()
    png = a.out / f"quicklook_{site.name}.png"
    fig.savefig(png, dpi=110, facecolor="#0f172a")
    print(f"\npanel -> {png}\ntable -> {a.out / f'quicklook_{site.name}.csv'}")
    print("\nLook for: seabed texture in the shallows, cloud or shadow over the bay,"
          "\nglint streaks, whitecaps, and turbid plumes near the creek mouths.")
    return 0


def cmd_scene(a) -> int:
    site, defaults = load_site(a.config, a.site)
    bbox, bbox_src = _bbox_for(_site_cfg(a.config, a.site), site.bbox, a.bbox)
    (item,) = get_items([a.item], defaults["stac_url"], defaults["collection"])
    props = item.properties
    baseline = props.get("s2:processing_baseline")
    print(f"{item.id}\n  baseline {baseline}   datetime {props['datetime']}   extent: {bbox_src}")

    hrefs, scalings, asset_meta = {}, {}, {}
    for b in (*STACK_BANDS, "scl"):
        key, asset = pick_asset(item.assets, b)
        hrefs[b] = asset.href
        asset_meta[b] = {"asset_key": key, "href": asset.href}
        if b != "scl":
            scalings[b] = reflectance_scaling(asset.extra_fields.get("raster:bands"), baseline)
            print(f"  {b:5s} scale {scalings[b].scale:g} offset {scalings[b].offset:+g}"
                  f"  [{scalings[b].source}; agrees with baseline rule: "
                  f"{scalings[b].agrees_with_baseline}]")

    if any(s.agrees_with_baseline is False for s in scalings.values()):
        print("\n  WARNING  declared scaling disagrees with the processing-baseline rule."
              "\n           The plausibility check below decides which is right.")

    stack = read_aoi_stack(hrefs, bbox, scalings)
    if stack["clipped"]:
        print("\n  WARNING  AOI runs off this tile; the window was cut back to the tile edge.")

    water = stack["scl"] == SCL_WATER
    plaus = offset_plausibility(stack["red"], stack["nir"], water)
    st = scl_stats(stack["scl"])
    print(f"\n  AOI: {stack['shape'][1]} x {stack['shape'][0]} px   "
          f"cloud {st['aoi_cloud_pct']}%   water {st['aoi_water_pct']}%")
    print(f"  plausibility: {plaus['verdict'].upper()} -- {plaus['reason']}")
    for k in ("median_red", "median_nir"):
        if k in plaus:
            print(f"    {k}: {plaus[k]}")

    if plaus["verdict"] == "fail" and not a.force:
        print("\n  Refusing to write a stack whose reflectance fails the water check."
              "\n  Fix the scaling, or pass --force to write it anyway for inspection.")
        return 2

    outdir = a.root / "data" / "raw" / "scenes" / item.id
    outdir.mkdir(parents=True, exist_ok=True)
    write_stack(outdir / "reflectance.tif", stack, stack["transform"], stack["crs"])
    write_scl(outdir / "scl.tif", stack["scl"], stack["transform"], stack["crs"])

    sidecar = {
        "item_id": item.id,
        "collection": defaults["collection"],
        "stac_url": defaults["stac_url"],
        "datetime_utc": props["datetime"],
        "platform": props.get("platform"),
        "processing_baseline": baseline,
        "sun_elevation_deg": props.get("view:sun_elevation"),
        "sun_azimuth_deg": props.get("view:sun_azimuth"),
        "bbox_wgs84": list(bbox),
        "bbox_source": bbox_src,
        "crs": str(stack["crs"]),
        "transform": list(stack["transform"])[:6],
        "shape_rows_cols": list(stack["shape"]),
        "window_clipped_to_tile": stack["clipped"],
        "bands": list(STACK_BANDS),
        "units": "BOA reflectance (unitless), float32, NaN = nodata",
        "scaling": {b: vars(s) for b, s in scalings.items()},
        "plausibility": plaus,
        "scl_stats": st,
        "assets": asset_meta,
        "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sdb_version": __version__,
    }
    (outdir / "provenance.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    print(f"\n  wrote {outdir}\\{{reflectance.tif, scl.tif, provenance.json}}")
    return 0 if plaus["verdict"] != "fail" else 2


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--site", default="jervis_bay")
    p.add_argument("--config", type=Path, default=Path("config/sites.yml"))
    p.add_argument("--out", type=Path, default=Path("outputs"))
    p.add_argument("--bbox", choices=("delivered", "block"), default="delivered",
                   help="fetch over the delivered DEM extent (default) or the lidar block")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("quicklook", help="true AOI cloud + water-stretched panel")
    q.add_argument("--top", type=int, default=3)
    q.add_argument("--ids", nargs="*", help="explicit item ids instead of --top")
    q.add_argument("--candidates", type=Path, help="defaults to outputs/candidates_<site>.csv")

    s = sub.add_parser("scene", help="fetch one scene as a reflectance stack")
    s.add_argument("--item", required=True)
    s.add_argument("--root", type=Path, default=Path("."))
    s.add_argument("--force", action="store_true",
                   help="write the stack even if the water plausibility check fails")

    a = p.parse_args(argv)
    return cmd_quicklook(a) if a.cmd == "quicklook" else cmd_scene(a)


if __name__ == "__main__":
    sys.exit(main())
