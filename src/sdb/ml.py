"""v2: gradient-boosted trees on per-pixel image features -- as pre-registered.

The *v2 protocol* in PROJECT_BRIEF.md, committed before any ML model saw real
data. Change a constant here and the change is a deviation to be logged.

One model family (scikit-learn HistGradientBoostingRegressor) with fixed
settings and no tuning. Early stopping is off: it would hold out a *random*
validation split inside each training fold -- the very leakage the blocked
design exists to prevent. Features come from the image alone, per pixel:

    ln(1000*rho) for blue, green, red, NIR; the Stumpf ratio (blue/green); blue/red

The coordinate model ("gbm_xy") adds easting and northing. It is run only as a
labelled leakage demonstration: with location as a feature, a flexible model can
look a test pixel's neighbours up rather than read its depth from the light.

Training uses v1's depth-balanced sample (up to 5,000 pixels per 1 m bin) drawn
inside each training fold, over the whole 0-20 m.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from sdb.sdb import MAX_DEPTH_M, N_SCALE, PER_BIN_CAP, balanced_sample, stumpf_ratio

# --------------------------------------------------------------------------
# Pre-registered constants
# --------------------------------------------------------------------------

HGB_PARAMS: dict[str, Any] = {
    "loss": "squared_error",
    "max_iter": 300,
    "learning_rate": 0.1,
    "max_leaf_nodes": 31,
    "min_samples_leaf": 100,
    "early_stopping": False,
}
SPECTRAL = ("ln_blue", "ln_green", "ln_red", "ln_nir", "psdb_green", "psdb_red")
XY = ("easting_km", "northing_km")
MODELS = {"gbm": SPECTRAL, "gbm_xy": SPECTRAL + XY}
#: Models that are demonstrations, not results.
DEMONSTRATIONS = ("gbm_xy",)


# --------------------------------------------------------------------------
# Features
# --------------------------------------------------------------------------


def spectral_features(blue: np.ndarray, green: np.ndarray, red: np.ndarray, nir: np.ndarray,
                      n: float = N_SCALE) -> np.ndarray:
    """(pixels x 6) float32 in SPECTRAL order; NaN where a log is undefined."""
    bands = [np.asarray(b, dtype=np.float64).ravel() for b in (blue, green, red, nir)]
    with np.errstate(divide="ignore", invalid="ignore"):
        logs = [np.log(n * b) for b in bands]
    logs = [np.where(np.isfinite(v), v, np.nan) for v in logs]
    return np.column_stack(logs + [stumpf_ratio(bands[0], bands[1], n),
                                   stumpf_ratio(bands[0], bands[2], n)]).astype(np.float32)


def features(model: str, blue, green, red, nir, x=None, y=None) -> np.ndarray:
    """Feature matrix for a named model; x, y (metres) only for the coordinate model."""
    if model not in MODELS:
        raise ValueError(f"unknown model {model!r}; choose from {sorted(MODELS)}")
    F = spectral_features(blue, green, red, nir)
    if "easting_km" in MODELS[model]:
        if x is None or y is None:
            raise ValueError(f"{model} needs coordinates")
        F = np.column_stack([F, np.asarray(x, float).ravel() / 1000.0,
                             np.asarray(y, float).ravel() / 1000.0]).astype(np.float32)
    return F


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------


@dataclass
class GBM:
    reg: Any = field(repr=False)
    n_sample: int
    names: tuple[str, ...]

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.reg.predict(X).astype(np.float64)

    def summary(self) -> dict[str, Any]:
        return {"n_sample": self.n_sample, "n_iter": int(self.reg.n_iter_),
                "features": list(self.names)}


def fit_gbm(X: np.ndarray, depth: np.ndarray, rng: np.random.Generator, *,
            names: tuple[str, ...] = SPECTRAL, cap: int = PER_BIN_CAP,
            max_depth: float = MAX_DEPTH_M) -> GBM:
    """The pre-registered fit on one training set: balanced sample, fixed settings."""
    from sklearn.ensemble import HistGradientBoostingRegressor

    d = np.asarray(depth, dtype=np.float64)
    idx = balanced_sample(d, d_max=max_depth + 1e-9, rng=rng, cap=cap)
    reg = HistGradientBoostingRegressor(**HGB_PARAMS, random_state=int(rng.integers(2**31 - 1)))
    reg.fit(np.asarray(X)[idx], d[idx])
    return GBM(reg, int(idx.size), names)


def fitter(model: str):
    """A fit(X, y, rng) callable for validate.cross_validate."""
    names = MODELS[model]

    def fit(X, y, rng):
        return fit_gbm(X, y, rng, names=names)

    return fit
