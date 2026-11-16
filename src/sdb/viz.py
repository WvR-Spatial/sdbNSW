"""One palette, one set of chrome, for every figure in the project.

Diagnostic figures for Phase 2 (static PNG): out-of-fold SDB against lidar,
error by depth against the CATZOC allowances, and the residual map. Colours:
categorical slots in fixed order (validated all-pairs for three series; the
third sits below 3:1 on the surface, so every line carries a direct text label),
one sequential hue for density, a blue-grey-red diverging scale for signed error.
Text never takes a series colour.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import numpy as np

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a")          # blue, orange, aqua
SEQUENTIAL = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b")
#: Negative (SDB too shallow) blue, neutral grey, positive (SDB too deep) red.
DIVERGING = ("#184f95", "#5598e7", "#b7d3f6", "#f0efec", "#f3bcbb", "#e34948", "#9c2a29")


def _style():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "text.color": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.6, "grid.linestyle": "-", "axes.spines.top": False,
        "axes.spines.right": False, "font.size": 9, "axes.titlesize": 10,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False,
        "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
    })
    return plt


def _cmap(colours: Sequence[str], name: str):
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list(name, list(colours))


def scatter(path: Path, depth: np.ndarray, pred: np.ndarray, pooled: dict[str, Any],
            title: str) -> Path:
    plt = _style()
    fig, ax = plt.subplots(figsize=(5.2, 5.0), dpi=150)
    hb = ax.hexbin(depth, pred, gridsize=90, extent=(0, 20, -2, 24), bins="log", mincnt=1,
                   cmap=_cmap(SEQUENTIAL, "seq"), linewidths=0)
    ax.set_axisbelow(True)
    ax.plot([0, 20], [0, 20], color=INK_2, lw=1.0)
    ax.text(19.4, 20.3, "1:1", color=INK_2, ha="right", va="bottom",
            bbox=dict(boxstyle="round,pad=0.2", fc=SURFACE, ec="none"))
    ax.set(xlim=(0, 20), ylim=(-2, 24), xlabel="Lidar depth (m)",
           ylabel="SDB depth, out-of-fold (m)", title=title)
    ax.text(0.4, 23.4, f"RMSE {pooled['rmse']:.2f} m   bias {pooled['bias']:+.2f} m   "
            f"R² {pooled['r2']:.2f}\nn = {pooled['n']:,} pixels",
            va="top", color=INK_2, fontsize=8)
    cb = fig.colorbar(hb, ax=ax, shrink=0.8, pad=0.02)
    cb.set_label("pixels per cell", color=INK_2)
    cb.outline.set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def error_by_depth(path: Path, curve: list[dict[str, Any]], breakdown: dict[str, float | None],
                   catzoc: dict[str, tuple[float, float]], title: str) -> Path:
    plt = _style()
    rows = [c for c in curve if c.get("n")]
    mid = np.array([(c["lo"] + c["hi"]) / 2 for c in rows])
    fig, ax = plt.subplots(figsize=(7.0, 4.2), dpi=150)
    ax.axhline(0, color=AXIS, lw=0.8)
    xs = np.linspace(0, 20, 50)
    for (k, (a, b)), ls in zip(sorted(catzoc.items(), reverse=True), ("--", ":")):
        ax.plot(xs, a + b * xs, color=MUTED, lw=1.0, ls=ls)
        ax.text(20.2, a + b * 20, f"CATZOC {k}", color=MUTED, va="center", fontsize=8)
    for key, lab, col in (("bias", "bias", SERIES[0]), ("rmse", "RMSE", SERIES[1]),
                          ("p95_abs", "95th pct |e|", SERIES[2])):
        y = np.array([c[key] for c in rows])
        ax.plot(mid, y, color=col, lw=1.6, label=lab, marker="o", ms=3.5,
                markeredgecolor=SURFACE, markeredgewidth=0.8)
        ax.text(mid[-1] + 0.3, y[-1], lab, color=INK_2, va="center", fontsize=8)
    from_surface = sorted(k for k, v in breakdown.items() if v == 0)
    for k, v in breakdown.items():
        if v:                                   # a line at 0 m would sit on the axis
            ax.axvline(v, color=INK_2, lw=0.8)
            ax.text(v + 0.15, ax.get_ylim()[1], f"breakdown {k}: {v:g} m", color=INK_2,
                    va="top", fontsize=8, rotation=90)
    if from_surface:
        ax.text(0.02, 0.96, "95th pct |e| exceeds CATZOC " + " and ".join(from_surface)
                + " from the shallowest bin", transform=ax.transAxes, ha="left", va="top",
                color=INK_2, fontsize=8)
    ax.set(xlim=(0, 23.5), xlabel="Lidar depth (m, 1 m bins)", ylabel="Error (m)", title=title)
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def residual_map(path: Path, resid_img: np.ndarray, grid: Any, block_m: float, title: str,
                 polygon: Sequence[Sequence[float]] | None = None, vmax: float = 5.0) -> Path:
    plt = _style()
    rows, cols = np.nonzero(np.isfinite(resid_img))
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    sub = resid_img[r0:r1, c0:c1]
    x0 = grid.x0 + c0 * grid.dx
    y0 = grid.y0 - r0 * grid.dy
    ext = np.array([x0, x0 + (c1 - c0) * grid.dx, y0 - (r1 - r0) * grid.dy, y0]) / 1000
    h = 7.5
    w = h * (ext[1] - ext[0]) / (ext[3] - ext[2]) + 1.4
    fig, ax = plt.subplots(figsize=(w, h), dpi=150)
    ax.grid(False)
    im = ax.imshow(sub, extent=ext, cmap=_cmap(DIVERGING, "div"), vmin=-vmax, vmax=vmax,
                   interpolation="nearest")
    bk = block_m / 1000
    gx0 = grid.x0 / 1000
    gy0 = grid.y0 / 1000
    for x in np.arange(gx0 + np.ceil((ext[0] - gx0) / bk) * bk, ext[1], bk):
        ax.axvline(x, color=GRID, lw=0.4)
    for y in np.arange(gy0 - np.ceil((gy0 - ext[3]) / bk) * bk, ext[2], -bk):
        ax.axhline(y, color=GRID, lw=0.4)
    if polygon:
        p = np.asarray(polygon, dtype=float) / 1000
        ax.plot(np.r_[p[:, 0], p[0, 0]], np.r_[p[:, 1], p[0, 1]], color=INK_2, lw=0.8)
    ax.set(xlim=ext[:2], ylim=ext[2:], xlabel="Easting (km, UTM 56S)",
           ylabel="Northing (km)", title=title)
    ax.set_aspect("equal")
    cb = fig.colorbar(im, ax=ax, shrink=0.7, pad=0.02, extend="both")
    cb.set_label("SDB − lidar (m)   + reads too deep", color=INK_2)
    cb.outline.set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def model_comparison(path: Path, curves: dict[str, list[dict[str, Any]]]) -> Path:
    """RMSE (solid) and bias (dashed) by 1 m lidar-depth bin, one colour per model."""
    plt = _style()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.0, 4.2), dpi=150)
    ax.axhline(0, color=AXIS, lw=0.8)
    for (name, curve), col in zip(curves.items(), SERIES):
        rows = [c for c in curve if c.get("n")]
        mid = np.array([(c["lo"] + c["hi"]) / 2 for c in rows])
        rm = np.array([c["rmse"] for c in rows])
        bi = np.array([c["bias"] for c in rows])
        ax.plot(mid, rm, color=col, lw=1.6, label=f"{name}: RMSE")
        ax.plot(mid, bi, color=col, lw=1.2, ls="--", label=f"{name}: bias")
        ax.text(mid[-1] + 0.3, rm[-1], name, color=INK_2, fontsize=8, va="center")
    ax.set(xlim=(0, 23.5), xlabel="Lidar depth (m, 1 m bins)", ylabel="Error (m)",
           title="Out-of-fold error by depth, same folds")
    ax.legend(loc="upper left", fontsize=7.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def ratio_depth_curve(path: Path, depth: np.ndarray, ratio: np.ndarray, inside: np.ndarray,
                      lines: dict[str, tuple[float, float]], bin_m: float = 0.5) -> Path:
    """Median Stumpf ratio (and interquartile band) by lidar depth, with fitted lines.

    Shows the model's form directly: a straight line in depth against a curve
    that flattens as the green signal from the seabed fades.
    """
    plt = _style()
    path.parent.mkdir(parents=True, exist_ok=True)
    edges = np.arange(0, 20 + bin_m / 2, bin_m)
    mid = (edges[:-1] + edges[1:]) / 2
    fig, ax = plt.subplots(figsize=(7.0, 4.4), dpi=150)
    for (name, sel), col in zip((("inside bay", inside), ("open coast", ~inside)), SERIES):
        k = np.digitize(depth[sel], edges) - 1
        rr = ratio[sel]
        q = np.full((len(mid), 3), np.nan)
        for i in range(len(mid)):
            v = rr[k == i]
            if v.size >= 200:
                q[i] = np.percentile(v, [25, 50, 75])
        ax.fill_between(mid, q[:, 0], q[:, 2], color=col, alpha=0.12, lw=0)
        ax.plot(mid, q[:, 1], color=col, lw=1.6, label=f"{name}: median, IQR")
        last = np.flatnonzero(np.isfinite(q[:, 1]))[-1]
        ax.text(mid[last] + 0.3, q[last, 1], name, color=INK_2, fontsize=8, va="center")
    for (name, (m1, m0)), ls in zip(lines.items(), ("-", "--", ":")):
        ax.plot(edges, (edges + m0) / m1, color=INK_2, lw=1.0, ls=ls, label=f"line: {name}")
    ax.set(xlim=(0, 23), xlabel="Lidar depth (m)", ylabel="Stumpf ratio ln(1000·blue) / ln(1000·green)",
           title="Stumpf ratio against depth, and the calibrated lines")
    ax.legend(loc="upper left", fontsize=7.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def substrate_contrasts(path: Path, comps: list[dict[str, Any]], classes: Sequence[str],
                        bands: Sequence[str], *, region: str = "inside the bay") -> Path:
    """Small multiples: bias of each class minus sediment, by depth band, with 95% CIs."""
    plt = _style()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axs = plt.subplots(1, len(classes), figsize=(2.6 * len(classes), 3.4), dpi=150,
                            sharey=True)
    x = np.arange(len(bands))
    for ax, cname in zip(np.atleast_1d(axs), classes):
        ax.axhline(0, color=AXIS, lw=0.8)
        for c in comps:
            if c["class"] != cname:
                continue
            i = list(bands).index(c["band_m"])
            if "bias_diff" in c:
                b = c["bias_diff"]
                ax.errorbar(i, b["point"], yerr=[[b["point"] - b["lo"]], [b["hi"] - b["point"]]],
                            fmt="o", color=SERIES[0], ms=5, elinewidth=1.4, capsize=0,
                            markeredgecolor=SURFACE, markeredgewidth=0.8)
                ax.text(i + 0.12, b["point"], f"{b['point']:+.2f}", color=INK_2, fontsize=7,
                        va="center")
            elif c["n_class"]:
                ax.text(i, 0.03, "n<1k", color=MUTED, fontsize=6.5, ha="center", va="bottom",
                        transform=ax.get_xaxis_transform())
        ax.set_xticks(x, bands, rotation=0, fontsize=7)
        ax.set_xlim(-0.5, len(bands) - 0.5)
        ax.set_title(cname, fontsize=9)
    np.atleast_1d(axs)[0].set_ylabel("Bias minus sediment (m)\n+ reads deeper")
    fig.supxlabel(f"Lidar depth band (m), {region}", fontsize=8, color=INK_2)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def phase2_figures(fdir: Path, scene: str, *, depth: np.ndarray, pred: np.ndarray,
                   curve: list[dict[str, Any]], breakdown: dict[str, float | None],
                   resid_img: np.ndarray, grid: Any, block_m: float, pooled: dict[str, Any],
                   polygon: Sequence[Sequence[float]] | None = None) -> list[Path]:
    from sdb.validate import CATZOC

    fdir.mkdir(parents=True, exist_ok=True)
    return [
        scatter(fdir / f"sdb_{scene}_scatter.png", depth, pred, pooled,
                "Out-of-fold SDB vs lidar"),
        error_by_depth(fdir / f"sdb_{scene}_error_by_depth.png", curve, breakdown, CATZOC,
                       "Error by lidar depth, against CATZOC allowances"),
        residual_map(fdir / f"sdb_{scene}_residual_map.png", resid_img, grid, block_m,
                     f"Out-of-fold residual ({block_m / 1000:g} km validation blocks)", polygon),
    ]


def clarity_blocks(path: Path, sites: dict[str, dict[str, Any]],
                   blocks: dict[str, list[dict[str, Any]]]) -> Path:
    """Phase 4: block RMSE in 10-20 m against block red reflectance, one panel per site.

    Shared axes so the sites can be read against each other -- with the caveat,
    printed on the figure, that absolute red carries each scene's atmospheric
    correction. Stumpf filled, gbm open; within-site Spearman in each panel.
    """
    plt = _style()
    path.parent.mkdir(parents=True, exist_ok=True)
    names = list(sites)
    fig, axs = plt.subplots(1, len(names), figsize=(3.4 * len(names), 3.6), dpi=150,
                            sharex=True, sharey=True, squeeze=False)
    for ax, k in zip(axs[0], names):
        tab = blocks.get(k) or []
        x = np.array([t["clarity"] for t in tab])
        for (m, col), filled in zip((("stumpf", SERIES[0]), ("gbm", SERIES[1])), (True, False)):
            if not tab or m not in tab[0]["rmse"]:
                continue
            y = np.array([t["rmse"][m] for t in tab])
            ax.scatter(x, y, s=18, color=col if filled else "none", edgecolors=col, lw=1.0,
                       label="Stumpf" if m == "stumpf" else "gbm", zorder=3)
        lines = []
        for m in ("stumpf", "gbm"):
            w = sites[k]["within"].get(m)
            if w and np.isfinite(w["rho"]):
                lines.append(f"{'Stumpf' if m == 'stumpf' else 'gbm'} ρ {w['rho']:+.2f} "
                             f"[{w['lo']:+.2f}, {w['hi']:+.2f}]")
        ax.text(0.03, 0.97, "\n".join(lines) + f"\n{len(tab)} blocks", transform=ax.transAxes,
                va="top", fontsize=7, color=INK_2)
        c = sites[k]["clarity"]["median_red"]
        ax.set_title(f"{k.replace('_', ' ')}" + (f"\nsite median red {c:.4f}" if c is not None
                                                  else ""), fontsize=9)
        ax.set_axisbelow(True)
    axs[0][0].set_ylabel("Block RMSE, 10–20 m (m)")
    axs[0][0].legend(loc="lower right", fontsize=7)
    fig.supxlabel("Block median red reflectance, 10–20 m  (higher = more turbid; absolute "
                  "values carry each scene's atmospheric correction)", fontsize=7.5, color=INK_2)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path
