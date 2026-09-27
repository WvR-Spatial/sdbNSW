"""Stumpf band-ratio bathymetry: the transform and its calibration rule.

Pure maths, no I/O. This is the *Model* and *Calibration* part of the Phase 2
protocol in PROJECT_BRIEF.md, pre-registered before any fit to real data;
change a constant here and the change is a deviation to be logged.

The transform (Stumpf, Holderied & Sinclair 2003):

    pSDB = ln(n * rho_blue) / ln(n * rho_green),   depth = m1 * pSDB - m0

Light is attenuated exponentially with depth and more strongly in green than in
blue, so the ratio of the logs rises with depth until the green signal from the
seabed is lost in the water column. Past that depth, the *optical saturation
depth*, the ratio carries no depth information; including those pixels in the
fit only flattens the line. Hence the calibration rule:

1. median pSDB in 1 m depth bins (0-20 m), smoothed with a 3-bin running median;
2. D_cal = upper edge of the shallowest bin whose smoothed median reaches 95% of
   the rise from the shallowest bin to the peak -- where the ratio stops rising;
   20 m if it rises throughout, i.e. the peak is the deepest bin (the protocol's
   two sentences, applied as written: a steady rise would otherwise reach 95% one
   bin early and give 19 m);
3. a depth-balanced sample below D_cal: up to 5,000 pixels per 1 m bin;
4. ordinary least squares of depth on pSDB.

All of it runs inside a training fold, never on held-out pixels.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# --------------------------------------------------------------------------
# Pre-registered constants
# --------------------------------------------------------------------------

#: Scale constant inside the logs. Stumpf et al. chose n so both logs stay
#: positive and the ratio is near-linear in depth; 1000 is the common choice for
#: reflectance. At Jervis Bay the smallest ln(n * rho) over usable pixels is 0.34.
N_SCALE = 1000.0

BIN_M = 1.0
MAX_DEPTH_M = 20.0
#: Bins with fewer pixels than this are ignored when locating D_cal.
MIN_BIN_COUNT = 200
SMOOTH_BINS = 3
RISE_FRACTION = 0.95
#: Depth-balanced calibration: at most this many pixels per 1 m bin.
PER_BIN_CAP = 5000


# --------------------------------------------------------------------------
# The transform
# --------------------------------------------------------------------------


def stumpf_ratio(blue: np.ndarray, green: np.ndarray, n: float = N_SCALE) -> np.ndarray:
    """ln(n*blue) / ln(n*green); NaN where either log is not positive or not finite."""
    with np.errstate(divide="ignore", invalid="ignore"):
        lb = np.log(n * np.asarray(blue, dtype=np.float64))
        lg = np.log(n * np.asarray(green, dtype=np.float64))
        out = lb / lg
    ok = np.isfinite(lb) & np.isfinite(lg) & (lb > 0) & (lg > 0)
    return np.where(ok, out, np.nan)


def fit_linear(ratio: np.ndarray, depth: np.ndarray) -> tuple[float, float]:
    """OLS of depth on ratio, in Stumpf's form depth = m1 * ratio - m0."""
    r = np.asarray(ratio, dtype=np.float64)
    d = np.asarray(depth, dtype=np.float64)
    if r.size < 2:
        raise ValueError("need at least two pixels to fit a line")
    rm, dm = r.mean(), d.mean()
    var = np.sum((r - rm) ** 2)
    if var == 0:
        raise ValueError("ratio has no spread: cannot fit a line")
    m1 = float(np.sum((r - rm) * (d - dm)) / var)
    return m1, float(m1 * rm - dm)


def predict(ratio: np.ndarray, m1: float, m0: float) -> np.ndarray:
    return m1 * np.asarray(ratio, dtype=np.float64) - m0


# --------------------------------------------------------------------------
# The calibration rule
# --------------------------------------------------------------------------


def _bin_index(depth: np.ndarray, bin_m: float, n_bins: int) -> np.ndarray:
    """Bin k holds [k, k+1) * bin_m; the top edge (e.g. exactly 20 m) joins the last bin."""
    k = np.floor(np.asarray(depth, dtype=np.float64) / bin_m)
    k = np.where(np.isclose(depth, n_bins * bin_m), n_bins - 1, k)
    out = np.full(k.shape, -1, dtype=np.int64)
    ok = np.isfinite(k) & (k >= 0) & (k < n_bins)
    out[ok] = k[ok].astype(np.int64)
    return out


def binned_medians(depth: np.ndarray, ratio: np.ndarray, *, bin_m: float = BIN_M,
                   max_depth: float = MAX_DEPTH_M,
                   min_count: int = MIN_BIN_COUNT) -> tuple[np.ndarray, np.ndarray]:
    """Median ratio and pixel count per depth bin; NaN median where count < min_count."""
    n_bins = int(round(max_depth / bin_m))
    k = _bin_index(depth, bin_m, n_bins)
    ok = (k >= 0) & np.isfinite(ratio)
    k, r = k[ok], np.asarray(ratio, dtype=np.float64)[ok]
    order = np.argsort(k, kind="stable")
    k, r = k[order], r[order]
    counts = np.bincount(k, minlength=n_bins)
    med = np.full(n_bins, np.nan)
    starts = np.r_[0, np.cumsum(counts)[:-1]]
    for b in range(n_bins):
        if counts[b] >= min_count:
            med[b] = np.median(r[starts[b]:starts[b] + counts[b]])
    return med, counts


def running_median(values: np.ndarray, width: int = SMOOTH_BINS) -> np.ndarray:
    """Centred running median over finite neighbours; NaN stays NaN."""
    v = np.asarray(values, dtype=np.float64)
    h = width // 2
    out = np.full(v.shape, np.nan)
    for i in range(v.size):
        if np.isfinite(v[i]):
            w = v[max(0, i - h):i + h + 1]
            out[i] = np.median(w[np.isfinite(w)])
    return out


def saturation_depth(depth: np.ndarray, ratio: np.ndarray, *, bin_m: float = BIN_M,
                     max_depth: float = MAX_DEPTH_M, min_count: int = MIN_BIN_COUNT,
                     rise_fraction: float = RISE_FRACTION,
                     rises_throughout_exception: bool = True) -> tuple[float, dict]:
    """D_cal: where the smoothed median ratio stops rising (see module docstring).

    Returns (d_cal, info). info["degenerate"] is True when the ratio never rises
    above its shallowest bin -- no usable depth signal -- in which case d_cal is
    the upper edge of the shallowest bin.

    rises_throughout_exception=False drops the protocol's second sentence and
    applies the 95% rule everywhere. EXPLORATORY only -- the registered rule is True.
    """
    med, counts = binned_medians(depth, ratio, bin_m=bin_m, max_depth=max_depth,
                                 min_count=min_count)
    s = running_median(med)
    fin = np.flatnonzero(np.isfinite(s))
    if fin.size == 0:
        raise ValueError(f"no depth bin has {min_count} pixels: cannot locate D_cal")
    k0 = int(fin[0])
    kp = int(np.nanargmax(s))
    info = {"bin_m": bin_m, "medians": med.tolist(), "smoothed": s.tolist(),
            "counts": counts.tolist(), "peak_bin": kp, "degenerate": False}
    if kp <= k0 or s[kp] <= s[k0]:
        info.update(degenerate=True, rule="no rise")
        return (k0 + 1) * bin_m, info
    if rises_throughout_exception and kp == int(fin[-1]):
        # The protocol's exception, as written: peak in the deepest bin = the
        # ratio "rises throughout", so the whole range is used.
        info["rule"] = "rises throughout"
        return (kp + 1) * bin_m, info
    thr = s[k0] + rise_fraction * (s[kp] - s[k0])
    kc = next(k for k in range(k0, kp + 1) if np.isfinite(s[k]) and s[k] >= thr)
    info.update(rule=f"{rise_fraction:.0%} of rise", threshold=float(thr))
    return (kc + 1) * bin_m, info


def balanced_sample(depth: np.ndarray, *, d_max: float, rng: np.random.Generator,
                    bin_m: float = BIN_M, cap: int = PER_BIN_CAP) -> np.ndarray:
    """Indices of at most `cap` pixels drawn at random from each bin in [0, d_max)."""
    d = np.asarray(depth, dtype=np.float64)
    ok = np.flatnonzero(np.isfinite(d) & (d >= 0) & (d < d_max))
    k = np.floor(d[ok] / bin_m).astype(np.int64)
    order = np.argsort(k, kind="stable")
    ok, k = ok[order], k[order]
    picks = []
    for b in np.unique(k):
        members = ok[k == b]
        picks.append(members if members.size <= cap else rng.choice(members, cap, replace=False))
    return np.sort(np.concatenate(picks)) if picks else np.array([], dtype=np.int64)


@dataclass
class Calibration:
    """A fitted Stumpf line and how it was obtained."""

    m1: float
    m0: float
    d_cal: float
    n_sample: int
    degenerate: bool
    curve: dict = field(default_factory=dict, repr=False)

    def predict(self, ratio: np.ndarray) -> np.ndarray:
        return predict(ratio, self.m1, self.m0)

    def summary(self) -> dict:
        return {"m1": self.m1, "m0": self.m0, "d_cal_m": self.d_cal,
                "n_sample": self.n_sample, "degenerate": self.degenerate}


def calibrate(depth: np.ndarray, ratio: np.ndarray, rng: np.random.Generator, *,
              bin_m: float = BIN_M, max_depth: float = MAX_DEPTH_M,
              min_count: int = MIN_BIN_COUNT, rise_fraction: float = RISE_FRACTION,
              cap: int = PER_BIN_CAP, rises_throughout_exception: bool = True) -> Calibration:
    """The whole pre-registered rule on one training set (exception off = exploratory)."""
    d = np.asarray(depth, dtype=np.float64)
    r = np.asarray(ratio, dtype=np.float64)
    ok = np.isfinite(d) & np.isfinite(r)
    d, r = d[ok], r[ok]
    d_cal, info = saturation_depth(d, r, bin_m=bin_m, max_depth=max_depth,
                                   min_count=min_count, rise_fraction=rise_fraction,
                                   rises_throughout_exception=rises_throughout_exception)
    idx = balanced_sample(d, d_max=d_cal, rng=rng, bin_m=bin_m, cap=cap)
    m1, m0 = fit_linear(r[idx], d[idx])
    return Calibration(m1, m0, d_cal, int(idx.size), info["degenerate"], info)
