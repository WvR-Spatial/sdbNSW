"""Figures for the paper and web page, generated from the pipeline's outputs.

    python scripts/figures.py [--root .] [--out docs/figures]

F2 to F5 read only the committed records under outputs/. The hero figure and
the maps (F1, F6) read the rasters under data/raw/scenes/, so they need a full
pipeline run; the maps also read the substrate layers and a Natural Earth
basemap (QGIS's bundled world_map.gpkg, copied to data/raw/basemap/).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

SITES = [("jervis_bay", "Jervis Bay", "S2A_56HKG_20180907_0_L2A"),
         ("narrabeen_long_reef", "Northern Beaches", "S2A_56HLH_20180927_1_L2A"),
         ("batemans_bay", "Batemans Bay", "S2B_56HKF_20180823_1_L2A")]
# Categorical slots in fixed order (validated: dataviz skill, all-pairs, light surface).
STUMPF, GBM, GBM_XY = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK_2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
BAND_FILL = "#f0efec"
SEQ = ["#fcfcfb", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
DPI = 300
MM = 1 / 25.4
FULL = 178 * MM    # full text width of the two-column A4 layout
HALF = 86 * MM


def style() -> None:
    plt.rcParams.update({
        "font.family": "Inter", "font.size": 7.5, "axes.titlesize": 8, "axes.labelsize": 7.5,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.6, "axes.labelcolor": INK_2,
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2, "ytick.labelcolor": INK_2,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "semibold",
        "axes.titlecolor": INK, "axes.titlelocation": "left", "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "legend.frameon": False,
        "lines.solid_capstyle": "round", "svg.fonttype": "none",
    })


def load(root: Path, rel: str) -> dict:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def records(root: Path) -> dict:
    out = {}
    for key, _, scene in SITES:
        out[key] = {
            "stumpf": load(root, f"outputs/sdb_{scene}.json"),
            "gbm": load(root, f"outputs/v2/sdb_{scene}_gbm.json"),
            "gbm_xy": load(root, f"outputs/v2/sdb_{scene}_gbm_xy.json"),
            "substrate": load(root, f"outputs/substrate_{scene}.json"),
        }
    return out


def save(fig, out: Path, name: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{name}.png"
    fig.savefig(p, dpi=DPI, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    return p


# --------------------------------------------------------------------------- hero

def hero(root: Path, out: Path, recs: dict) -> Path:
    """Satellite (gradient boosting, out of fold) against lidar depth at each site."""
    import rasterio

    fig, axs = plt.subplots(1, 3, figsize=(FULL, 66 * MM), sharex=True, sharey=True)
    d = np.linspace(0, 20, 50)
    for ax, (key, name, scene) in zip(axs, SITES):
        with rasterio.open(root / "data/raw/scenes" / scene / "sdb_gbm.tif") as r:
            sdb, res = r.read(1), r.read(2)
        ok = np.isfinite(res) & np.isfinite(sdb)
        lidar, sat = (sdb - res)[ok], sdb[ok]
        for sgn in (-1, 1):
            ax.plot(d, d + sgn * (2 + 0.05 * d), color=INK_2, lw=0.8, ls=(0, (4, 2)), zorder=3)
        hb = ax.hexbin(lidar, sat, gridsize=46, extent=(0, 20, -1, 22), mincnt=5, bins="log",
                       cmap=matplotlib.colors.ListedColormap(SEQ[2:]), linewidths=0, zorder=1)
        ax.plot([0, 20], [0, 20], color=INK, lw=0.8, zorder=2)
        g = recs[key]["gbm"]["pooled"]
        ax.set_title(name)
        ax.text(0.03, 0.97, f"RMSE {g['rmse']:.2f} m\n{g['n']:,} pixels", transform=ax.transAxes,
                va="top", ha="left", color=INK_2, fontsize=7, zorder=4,
                bbox={"boxstyle": "square,pad=0.25", "fc": SURFACE, "ec": "none", "alpha": 0.85})
        ax.set_xlim(0, 20)
        ax.set_ylim(0, 22)
        ax.set_xticks([0, 5, 10, 15, 20])
        ax.set_yticks([0, 5, 10, 15, 20])
    axs[0].set_ylabel("Satellite depth (m)")
    axs[1].set_xlabel("Lidar depth (m)")
    axs[2].text(19.6, 0.6, "dashed: CATZOC C\nallowance either side", ha="right", va="bottom",
                color=INK_2, fontsize=6.5, zorder=4,
                bbox={"boxstyle": "square,pad=0.25", "fc": SURFACE, "ec": "none", "alpha": 0.85})
    cb = fig.colorbar(hb, ax=axs, shrink=0.8, pad=0.015, aspect=30)
    cb.set_label("Pixels per cell", color=INK_2)
    cb.outline.set_visible(False)
    cb.ax.tick_params(color=MUTED, labelcolor=INK_2)
    return save(fig, out, "hero_satellite_vs_lidar")


# --------------------------------------------------------------------------- F2

def error_by_depth(out: Path, recs: dict) -> Path:
    fig, axs = plt.subplots(2, 3, figsize=(FULL, 98 * MM), sharex=True, sharey="row")
    for j, (key, name, _) in enumerate(SITES):
        for model, colour, label in (("stumpf", STUMPF, "Stumpf ratio"), ("gbm", GBM, "Gradient boosting")):
            bins = recs[key][model]["by_1m_bin"]
            mid = np.array([(b["lo"] + b["hi"]) / 2 for b in bins])
            ok = np.array([b["n"] >= 200 for b in bins])
            rmse = np.array([b["rmse"] for b in bins])
            p95 = np.array([b["p95_abs"] for b in bins])
            axs[0, j].plot(mid[ok], rmse[ok], color=colour, lw=1.6, label=label)
            axs[1, j].plot(mid[ok], p95[ok], color=colour, lw=1.6, label=label)
        d = np.linspace(0, 20, 41)
        axs[1, j].plot(d, 2 + 0.05 * d, color=MUTED, lw=1.0, ls=(0, (4, 2)), label="CATZOC C allowance")
        axs[0, j].set_title(name)
        axs[1, j].set_xlabel("Lidar depth (m)")
        axs[1, j].set_xticks([0, 5, 10, 15, 20])
    axs[0, 0].set_ylabel("RMSE (m)")
    axs[1, 0].set_ylabel("95th percentile of |error| (m)")
    axs[0, 0].set_ylim(0, None)
    axs[1, 0].set_ylim(0, None)
    h, lab = axs[1, 0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.035))
    fig.subplots_adjust(hspace=0.18, wspace=0.08, bottom=0.14)
    return save(fig, out, "f2_error_by_depth")


# --------------------------------------------------------------------------- F3

def validation_design(out: Path, recs: dict) -> Path:
    fig, axs = plt.subplots(1, 3, figsize=(FULL, 58 * MM), sharey=True)
    for ax, (key, name, _) in zip(axs, SITES):
        for model, colour, label in (("stumpf", STUMPF, "Stumpf ratio"),
                                     ("gbm", GBM, "Gradient boosting"),
                                     ("gbm_xy", GBM_XY, "Gradient boosting with coordinates")):
            c = recs[key][model]["block_size_curve"]
            x = np.arange(len(c))
            y = [p["rmse_mean"] for p in c]
            ax.plot(x, y, color=colour, lw=1.6, marker="o", ms=3.2, label=label)
        ax.set_xticks(range(5), ["random", "0.5", "1", "2", "4"])
        ax.axvline(3, color=AXIS, lw=0.8, zorder=0)
        ax.set_title(name)
        ax.set_xlabel("Validation block size (km)")
    axs[0].set_ylabel("RMSE (m)")
    axs[0].set_ylim(0, None)
    axs[0].text(3.08, 0.12, "registered\n2 km", color=MUTED, fontsize=6.5, va="bottom")
    h, lab = axs[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.07))
    fig.subplots_adjust(wspace=0.08, bottom=0.26)
    return save(fig, out, "f3_validation_design")


# --------------------------------------------------------------------------- F4

def reef_vs_sediment(out: Path, recs: dict) -> Path:
    bands = ["0-2", "2-5", "5-10", "10-15", "15-20"]
    fig, axs = plt.subplots(1, 3, figsize=(FULL, 56 * MM), sharey=True)
    for ax, (key, name, _) in zip(axs, SITES):
        s = recs[key]["substrate"]["threshold_0.5"]
        rows = {c["band_m"]: c for c in s["vs_reference_inside_bay"] if c["class"] == "reef"}
        for i, b in enumerate(bands):
            c = rows.get(b)
            if not c or "bias_diff" not in c:
                ax.text(i, 0.15, "too few\npixels", ha="center", va="bottom", fontsize=6, color=MUTED)
                continue
            bd = c["bias_diff"]
            ax.plot([i, i], [bd["lo"], bd["hi"]], color=STUMPF, lw=1.4)
            ax.plot(i, bd["point"], "o", color=STUMPF, ms=4.2, mec=SURFACE, mew=0.8)
        ax.axhline(0, color=AXIS, lw=0.8, zorder=0)
        n = {}
        for r in s["errors_by_class"]:
            n[r["class"]] = n.get(r["class"], 0) + r["n"]
        share = n.get("reef", 0) / sum(n.values())
        ax.set_title(name)
        ax.text(0.97, 0.04, f"reef {share:.0%} of assessed seabed", transform=ax.transAxes,
                ha="right", va="bottom", fontsize=6.8, color=INK_2)
        ax.set_xticks(range(5), ["0–2", "2–5", "5–10", "10–15", "15–20"])
        ax.set_xlabel("Lidar depth band (m)")
    axs[0].set_ylabel("Reef minus sediment bias (m)\npositive = reef reads deeper")
    fig.subplots_adjust(wspace=0.08)
    return save(fig, out, "f4_reef_vs_sediment")


# --------------------------------------------------------------------------- F5

def clarity(root: Path, out: Path, recs: dict) -> Path:
    reg = load(root, "outputs/phase4/clarity.json")
    exp = load(root, "outputs/exploratory/clarity_depth_adjusted.json")
    fig, (a, b) = plt.subplots(1, 2, figsize=(FULL, 70 * MM), gridspec_kw={"width_ratios": [1, 1.2]})
    # (a) between sites: pooled RMSE against the site clarity metric
    for model, colour, label, dx in (("stumpf", STUMPF, "Stumpf ratio", -0.00005),
                                     ("gbm", GBM, "Gradient boosting", 0.00005)):
        xs, ys = [], []
        for key, name, _ in SITES:
            x = reg["sites"][key]["clarity"]["median_red"] + dx
            p = recs[key][model]["pooled"]
            ci = p["ci95"]["rmse"]
            a.plot([x, x], [ci["lo"], ci["hi"]], color=colour, lw=1.3)
            xs.append(x)
            ys.append(p["rmse"])
        a.plot(xs, ys, "o", color=colour, ms=4.6, mec=SURFACE, mew=0.8, label=label, ls="none")
    for key, name, _ in SITES:
        a.text(reg["sites"][key]["clarity"]["median_red"], 0.25, name, ha="center", va="bottom",
               fontsize=6.6, color=INK_2)
    a.set_xlim(0.0015, 0.006)
    a.set_ylim(0, 3.8)
    a.set_xlabel("Median red reflectance at 10–20 m (higher = more turbid)")
    a.set_ylabel("Pooled RMSE, 0–20 m (m)")
    a.set_title("a  Between sites")
    a.legend(loc="lower right", bbox_to_anchor=(1.0, 0.1))
    # (b) within sites (Stumpf): registered block RMSE and the exploratory depth-standardised error
    rows = [(f"{name}\n{reg['sites'][key]['blocks_used']} blocks", reg["sites"][key]["within"]["stumpf"],
             exp["sites"][key]["within"]["stumpf"]) for key, name, _ in SITES]
    rows.append(("Mean of the\nthree sites", reg["across_sites_mean_within_rho"]["stumpf"],
                 exp["across_sites_mean_within_rho"]["stumpf"]))
    ys = []
    for i, (name, r, e) in enumerate(rows):
        y = len(rows) - 1 - i
        ys.append(y)
        for est, dy, filled in ((r, 0.15, False), (e, -0.15, True)):
            rho = est.get("rho", est.get("mean_rho"))
            b.plot([est["lo"], est["hi"]], [y + dy, y + dy], color=STUMPF, lw=1.3)
            b.plot(rho, y + dy, "o", ms=4.6, color=STUMPF if filled else SURFACE, mec=STUMPF, mew=1.2)
    b.set_yticks(ys, [r[0] for r in rows])
    for t in b.get_yticklabels()[-1:]:
        t.set_fontweight("semibold")
        t.set_color(INK)
    b.tick_params(axis="y", length=0)
    b.axvline(0, color=AXIS, lw=0.8, zorder=0)
    b.axhline(0.5, color=GRID, lw=0.6, zorder=0)
    b.set_xlim(-1.0, 1.0)
    b.set_ylim(-0.6, len(rows) - 0.4)
    b.grid(axis="y", visible=False)
    b.set_xticks([-1.0, -0.5, 0, 0.5, 1.0])
    b.set_xlabel("Spearman correlation: block red reflectance against block error")
    b.set_title("b  Within sites, 2 km blocks (Stumpf)")
    b.plot([], [], "o", ms=4.6, color=SURFACE, mec=STUMPF, mew=1.2, label="Registered: block RMSE")
    b.plot([], [], "o", ms=4.6, color=STUMPF, mec=STUMPF, mew=1.2,
           label="Exploratory: error against what depth predicts")
    b.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    fig.subplots_adjust(wspace=0.32, bottom=0.27)
    return save(fig, out, "f5_clarity")


# --------------------------------------------------------------------------- maps

BASEMAP = "data/raw/basemap/world_map_qgis340.gpkg"
LAND, WATER_ASSESSED, NOT_SEA = "#e6e4dc", "#9ec5f4", "#c3c2b7"
RES_CMAP = ["#184f95", "#3987e5", "#9ec5f4", "#f0efec", "#f4b6b3", "#e34948", "#a32c2c"]


def _grid(path: Path):
    import rasterio

    with rasterio.open(path) as r:
        return r.read(), r.bounds, r.transform, r.crs


def _hillshade(z: np.ndarray, px: float, az: float = 315, alt: float = 45, exag: float = 4.0) -> np.ndarray:
    zz = np.where(np.isfinite(z), z, np.nanmean(z))
    gy, gx = np.gradient(zz * exag, px)
    slope = np.pi / 2 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    a, b = np.radians(360 - az + 90), np.radians(alt)
    hs = np.sin(b) * np.sin(slope) + np.cos(b) * np.cos(slope) * np.cos(a - aspect)
    return np.where(np.isfinite(z), np.clip(hs, 0, 1), np.nan)


def _scalebar(ax, x0: float, y0: float, km: float, label: str | None = None) -> None:
    from matplotlib import patheffects as pe

    halo = [pe.withStroke(linewidth=2.2, foreground=SURFACE)]
    ax.plot([x0, x0 + km * 1000], [y0, y0], color=INK, lw=1.6, solid_capstyle="butt", zorder=5,
            path_effects=[pe.withStroke(linewidth=3.2, foreground=SURFACE)])
    ax.text(x0 + km * 500, y0 + 250, label or f"{km:g} km", ha="center", va="bottom", fontsize=6.5,
            color=INK, zorder=5, path_effects=halo)


def _base(ax, root: Path, scene: str):
    (z, *_), bounds, _, _ = _grid(root / "data/raw/scenes" / scene / "reference.tif")
    hs = _hillshade(z, 10.0)
    ext = (bounds.left, bounds.right, bounds.bottom, bounds.top)
    ax.imshow(hs, extent=ext, cmap="Greys_r", vmin=-0.6, vmax=1.15, interpolation="bilinear", zorder=0)
    ax.set_xlim(bounds.left, bounds.right)
    ax.set_ylim(bounds.bottom, bounds.top)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for sp in ax.spines.values():
        sp.set_visible(True)
        sp.set_color(AXIS)
        sp.set_linewidth(0.6)
    return z, bounds, ext


def site_map(root: Path, out: Path) -> Path:
    """F1: where the sites are, and what was assessed at each."""
    import geopandas as gpd
    from matplotlib.colors import ListedColormap
    from matplotlib.gridspec import GridSpec
    from matplotlib.patches import Patch
    import rasterio

    widths = []
    for _, _, scene in SITES:
        with rasterio.open(root / "data/raw/scenes" / scene / "reference.tif") as r:
            widths.append(r.bounds.right - r.bounds.left)
    fig = plt.figure(figsize=(FULL, 76 * MM))
    gs = GridSpec(1, 4, figure=fig, width_ratios=[0.95 * max(widths)] + widths, wspace=0.06,
                  left=0.005, right=0.995, top=0.93, bottom=0.11)
    # locator
    ax = fig.add_subplot(gs[0])
    states = gpd.read_file(root / BASEMAP, layer="states_provinces")
    au = states[states["admin"] == "Australia"]
    au.plot(ax=ax, color=LAND, edgecolor=SURFACE, lw=0.5)
    ax.set_xlabel("")
    ax.set_ylabel("")
    states[states["name"] == "New South Wales"].plot(ax=ax, color="#d6d3c8", edgecolor=SURFACE, lw=0.5)
    pts = {"Jervis Bay": (150.73, -35.06), "Northern Beaches": (151.30, -33.69), "Batemans Bay": (150.22, -35.73)}
    for name, (x, y) in pts.items():
        ax.plot(x, y, "s", ms=4.2, color=STUMPF, mec=SURFACE, mew=0.6)
        ax.text(x + 0.3, y, name, va="center", fontsize=6.3, color=INK)
    ax.plot(151.21, -33.87, "o", ms=2.2, color=INK_2)
    ax.text(150.95, -33.95, "Sydney", ha="right", va="top", fontsize=6, color=INK_2)
    ax.text(147.3, -32.0, "New South\nWales", fontsize=6.5, color=INK_2, ha="center")
    ax.set_xlim(145.5, 157.6)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_ylim(-38.0, -28.5)
    ax.set_aspect(1 / np.cos(np.radians(33.5)))
    ax.set_facecolor("#f4f7fb")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    ax.set_title("a  Location", fontsize=7.5)
    ax.set_anchor("N")
    # sites at one scale
    letters = "bcd"
    for i, (key, name, scene) in enumerate(SITES):
        ax = fig.add_subplot(gs[i + 1])
        z, b, ext = _base(ax, root, scene)
        with rasterio.open(root / "data/raw/scenes" / scene / "mask.tif") as r:
            m = r.read(1)
        assessed = np.where(m == 0, 1.0, np.nan)
        ax.imshow(assessed, extent=ext, cmap=ListedColormap([WATER_ASSESSED]), alpha=0.75,
                  interpolation="nearest", zorder=1)
        cut = np.where((m & 64) > 0, 1.0, np.nan)
        if np.isfinite(cut).any():
            ax.imshow(cut, extent=ext, cmap=ListedColormap([NOT_SEA]), alpha=0.9, interpolation="nearest", zorder=1)
        for x in np.arange(b.left, b.right, 2000):
            ax.axvline(x, color=INK, lw=0.3, alpha=0.3, zorder=2)
        for y in np.arange(b.top, b.bottom, -2000):
            ax.axhline(y, color=INK, lw=0.3, alpha=0.3, zorder=2)
        _scalebar(ax, b.left + 600, b.bottom + 700, 2)
        ax.set_title(f"{letters[i]}  {name}", fontsize=7.5)
        ax.set_anchor("N")
    handles = [Patch(color=WATER_ASSESSED, alpha=0.75, label="Assessed water, 0–20 m"),
               Patch(color=NOT_SEA, label="Water not joined to the open sea (excluded)"),
               matplotlib.lines.Line2D([], [], color=INK, alpha=0.4, lw=0.6, label="2 km validation blocks")]
    fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.0))
    return save(fig, out, "f1_sites")


def residual_map(root: Path, out: Path) -> Path:
    """F6: Stumpf residuals at Northern Beaches, with the mapped reef."""
    import geopandas as gpd
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    from matplotlib.patches import Rectangle
    import rasterio

    key, name, scene = SITES[1]
    with rasterio.open(root / "data/raw/scenes" / scene / "sdb.tif") as r:
        res = r.read(2)
        crs = r.crs
    reef = gpd.read_file(root / "data/raw/substrate/substrate_narrabeen_long_reef.gpkg", layer="reef_extent")
    reef = reef[reef["REEF"] == "Reef"].to_crs(crs)
    reef = gpd.GeoSeries([reef.buffer(2.0).union_all().buffer(-2.0)], crs=crs)   # close tile seams
    cmap = LinearSegmentedColormap.from_list("div", RES_CMAP)
    norm = TwoSlopeNorm(vmin=-6, vcenter=0, vmax=6)
    with rasterio.open(root / "data/raw/scenes" / scene / "mask.tif") as r:
        m, tr = r.read(1), r.transform
    cols = np.where((m == 0).any(axis=0))[0]
    xa, xb = tr.c + cols.min() * tr.a - 600, tr.c + (cols.max() + 1) * tr.a + 600
    fig, (a, b) = plt.subplots(1, 2, figsize=(FULL, 112 * MM), gridspec_kw={"width_ratios": [0.62, 1]})
    zx0, zy0, zw, zh = 342300.0, 6262300.0, 4400.0, 5600.0   # Dee Why to Long Reef and Collaroy
    for ax, zoom in ((a, False), (b, True)):
        z, bnd, ext = _base(ax, root, scene)
        im = ax.imshow(res, extent=ext, cmap=cmap, norm=norm, interpolation="nearest", alpha=0.95, zorder=1)
        reef.boundary.plot(ax=ax, color=INK, lw=0.35 if not zoom else 0.6, zorder=2)
        ax.set_xlabel("")
        ax.set_ylabel("")
        if zoom:
            ax.set_xlim(zx0, zx0 + zw)
            ax.set_ylim(zy0, zy0 + zh)
            _scalebar(ax, zx0 + 250, zy0 + 300, 1)
            ax.set_title("b  Dee Why to Collaroy (box in a)", fontsize=7.5)
        else:
            ax.set_xlim(xa, xb)
            ax.add_patch(Rectangle((zx0, zy0), zw, zh, fill=False, ec=INK, lw=0.8, zorder=3))
            _scalebar(ax, xa + 400, bnd.bottom + 700, 2)
            ax.set_title("a  Whole site", fontsize=7.5)
    cb = fig.colorbar(im, ax=[a, b], shrink=0.7, pad=0.02, aspect=30)
    cb.set_label("Error (m): satellite minus lidar\nred = reads too deep, blue = too shallow", color=INK_2)
    cb.outline.set_visible(False)
    cb.ax.tick_params(color=MUTED, labelcolor=INK_2)
    b.plot([], [], color=INK, lw=0.6, label="Mapped reef (DCCEEW)")
    b.legend(loc="lower right", fontsize=6.5, frameon=True, facecolor=SURFACE, edgecolor="none")
    return save(fig, out, "f6_residual_map")


def card(root: Path, out: Path) -> Path:
    """Portfolio card image, 1200 x 800 px: Stumpf error off Long Reef on lidar hillshade."""
    import geopandas as gpd
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    import rasterio

    key, name, scene = SITES[1]
    with rasterio.open(root / "data/raw/scenes" / scene / "sdb.tif") as r:
        res, crs = r.read(2), r.crs
    reef = gpd.read_file(root / "data/raw/substrate/substrate_narrabeen_long_reef.gpkg", layer="reef_extent")
    reef = reef[reef["REEF"] == "Reef"].to_crs(crs)
    reef = gpd.GeoSeries([reef.buffer(2.0).union_all().buffer(-2.0)], crs=crs)
    fig = plt.figure(figsize=(6, 4), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    z, bnd, ext = _base(ax, root, scene)
    ax.imshow(res, extent=ext, cmap=LinearSegmentedColormap.from_list("div", RES_CMAP),
              norm=TwoSlopeNorm(vmin=-6, vcenter=0, vmax=6), interpolation="nearest", alpha=0.95, zorder=1)
    reef.boundary.plot(ax=ax, color=INK, lw=0.45, zorder=2)
    x0, y0, w = 341300.0, 6262500.0, 6300.0
    ax.set_xlim(x0, x0 + w)
    ax.set_ylim(y0, y0 + w * 2 / 3)
    for sp in ax.spines.values():
        sp.set_visible(False)
    out.mkdir(parents=True, exist_ok=True)
    p = out / "sdbNSW_card.png"
    fig.savefig(p, dpi=200)
    plt.close(fig)
    return p


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--out", type=Path, default=Path("docs/figures"))
    p.add_argument("--no-rasters", action="store_true",
                   help="skip the hero figure and maps, which need the pipeline's rasters")
    p.add_argument("--card", action="store_true", help="also write the portfolio card image")
    a = p.parse_args(argv)
    style()
    recs = records(a.root)
    made = [error_by_depth(a.out, recs), validation_design(a.out, recs),
            reef_vs_sediment(a.out, recs), clarity(a.root, a.out, recs)]
    if not a.no_rasters:
        made += [hero(a.root, a.out, recs), site_map(a.root, a.out), residual_map(a.root, a.out)]
        if a.card:
            made.append(card(a.root, a.out))
    for m in made:
        print(m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
