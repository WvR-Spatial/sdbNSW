"""EXPLORATORY diagnostic, in-sample: is the Phase 2 bias pattern regression toward the mean?

The registered calibration regresses depth on the Stumpf ratio. When the ratio is
noisy, that slope is attenuated by roughly r^2, so predictions are pulled toward
the middle of the depth range: shallow water reads deep, deep water reads shallow,
while error *conditional on predicted depth* stays near zero. The classical
alternative -- ratio on depth, then inverted -- removes that pull but has larger
error overall. Comparing the two, on the same depth-balanced sample, separates
regression toward the mean from curvature in the ratio-depth relationship.

    python scripts/calibration_form_check.py --scene S2A_56HKG_20180907_0_L2A

In-sample by design: this explains the registered result; it is not a result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio

from sdb.reference import DEPTH_BANDS_M
from sdb.sdb import balanced_sample, stumpf_ratio


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--scene", required=True)
    p.add_argument("--root", type=Path, default=Path("."))
    a = p.parse_args()
    sd = a.root / "data" / "raw" / "scenes" / a.scene
    wl = json.loads((a.root / "outputs" / f"reference_{a.scene}.json").read_text())["water_level_m_ahd"]
    with rasterio.open(sd / "reflectance.tif") as s:
        b, g = s.read(1).astype(float), s.read(2).astype(float)
    with rasterio.open(sd / "reference.tif") as s:
        z = s.read(1).astype(float)
    with rasterio.open(sd / "mask.tif") as s:
        u = s.read(1) == 0
    d, r = wl - z[u], stumpf_ratio(b[u], g[u])
    idx = balanced_sample(d, d_max=20.0, rng=np.random.default_rng(0))
    m1, c1 = np.polyfit(r[idx], d[idx], 1)           # depth on ratio (the registered form)
    bb, aa = np.polyfit(d[idx], r[idx], 1)           # ratio on depth, inverted
    inv, cls = m1 * r + c1, (r - aa) / bb
    cor = np.corrcoef(r[idx], d[idx])[0, 1]
    print(f"{a.scene}  (in-sample, depth-balanced 0-20 m sample of {idx.size:,})")
    print(f"  corr(ratio, depth) {cor:.3f}, r^2 {cor**2:.3f}")
    print(f"  metres of depth per unit ratio: depth-on-ratio {m1:.1f}, ratio-on-depth inverted "
          f"{1 / bb:.1f} (their ratio is r^2 by construction: the attenuation)")
    print(f"  pooled RMSE: depth-on-ratio {np.sqrt(np.mean((inv - d) ** 2)):.2f} m, "
          f"inverted {np.sqrt(np.mean((cls - d) ** 2)):.2f} m")
    for label, key in (("lidar", d), ("predicted", None)):
        print(f"\n  bias by {label} depth   depth-on-ratio   inverted")
        for lo, hi in DEPTH_BANDS_M:
            ki = (d if key is not None else inv)
            kc = (d if key is not None else cls)
            si = (ki >= lo) & ((ki <= hi) if hi == 20 else (ki < hi))
            sc = (kc >= lo) & ((kc <= hi) if hi == 20 else (kc < hi))
            print(f"    {lo:>2}-{hi:<3} m {np.mean(inv[si] - d[si]):>+16.2f} {np.mean(cls[sc] - d[sc]):>+10.2f}")


if __name__ == "__main__":
    main()
