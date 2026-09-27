# Satellite-Derived Bathymetry on an Exposed Temperate Coast — project brief

**Status:** Phase 0 complete (feasibility gate passed). Not yet started.
**Created:** 27 Sep 2026 · **Repo name (proposed):** `sdbNSW`
**Portfolio slot:** replaces *Revealing the Ancient Murray via REM*.

This is a living document. Revise it as decisions change — do not let the repo
drift away from it silently.

---

## The question

> Does satellite-derived bathymetry work on an exposed temperate coast, and
> where exactly does it stop working?

Published SDB validation is almost entirely clear tropical water — St Thomas
and the Caribbean, the South China Sea, south-west Florida. Reported accuracy
sits around 1.3 m RMSE for machine-learning approaches, 1.8 m for the Stumpf
band-ratio transform, 2.2 m for linear models, over 0–20 m.

The NSW coast is temperate, swell-exposed, with active surf zones, river
plumes and seasonal turbidity. Nobody has published the error envelope for it.

**The deliverable is a number and an envelope, not a map.** Expected answer:
"worse than the literature, and here is the depth-and-clarity boundary where
it fails." That is a finding. A pretty bathymetry raster is not.

## Why this project

Closes three capability gaps in one piece:

| Gap | How |
|---|---|
| Multispectral imagery analysis | Own derivation from Sentinel-2 L2A, not a derived product |
| Quantitative accuracy assessment | RMSE / bias / R² against an independent IHO-grade reference |
| Marine / coastal | Nearshore bathymetry |

It also cashes the claim on the portfolio about understanding the physics
behind the sensor: SDB *is* radiative transfer through a water column.

## Sites — a water-clarity gradient

Three sites, one pipeline, three bounding boxes. One site gives an RMSE;
three give the relationship between error and the thing that drives it.

| # | Site | Role | Indicative bbox (WGS84, **confirm against lidar tiles**) |
|---|---|---|---|
| 1 | Jervis Bay | Best case — sheltered, clear, mixed substrate | 150.65, −35.18, 150.83, −35.02 |
| 2 | Narrabeen–Long Reef | Exposed, surf-dominated | 151.29, −33.74, 151.33, −33.70 |
| 3 | Batemans Bay / Clyde mouth | Worst case — estuarine turbidity | 150.17, −35.75, 150.25, −35.68 |

*Alternative for site 3 if the Clyde signal is too weak: Richmond River mouth, Ballina.*

**Start with Jervis Bay.** If it fails in the clearest water on the coast,
nothing downstream matters and you have spent one weekend finding out.

Site 2 reuses the Narrabeen survey data and MHL wave/tide workflows already
built in `narrabeen-stage1`.

## Data

| Source | What | Access | Licence | Commit to repo? |
|---|---|---|---|---|
| [NSW Marine LiDAR Topo-Bathy 2018](https://datasets.seed.nsw.gov.au/dataset/marine-lidar-topo-bathy-2018) | 5 m grid, IHO Order 1b, AHD, shore to 20–40 m, Jul–Dec 2018 | [ELVIS](https://elevation.fsdf.org.au/) / AODN, manual area select | **CC BY 4.0** | **Yes** — clipped subsets, with attribution |
| Sentinel-2 L2A | 10 m multispectral COGs | Earth Search STAC on AWS, anonymous | Copernicus open | No — derived results only |
| MHL NSW tide | Water level at acquisition time | mhl.nsw.gov.au | Attribution | Derived only |
| NSW seagrass / substrate mapping | Stratification variable | SEED | Check per dataset | Clipped subsets |

**The CC BY licence on the reference data is a structural advantage.** Unlike
the Narrabeen survey (registration-gated, non-commercial, un-committable), a
reader can clone this repo and reproduce the validation. Do not squander that
— commit the reference subsets.

## Method

**v1 — empirical.** Stumpf ratio transform: log(blue)/log(green), calibrated
against a subset of the lidar, validated on held-out data. Water level at
acquisition time applied as a **scalar vertical offset** to reconcile
instantaneous depth with AHD. This is much simpler and less error-prone than
the horizontal, slope-dependent tidal correction in the shoreline work.

**v2 — ML, in scope only if v1 earns it.** Random forest / gradient boosting
regression on the same bands, same folds, same reference. The question is not
"can ML do SDB" (it can) but **does the ML advantage survive degraded water
clarity, or does it evaporate?** Literature says ~0.5 m advantage in clear
water and is silent on turbid. Interesting either way, including if ML loses.

Defer ML until site 1 has an empirical number. A comparison with nothing to
compare against is a demo.

## Validation design

**Spatially blocked cross-validation, not random splits.** Neighbouring
raster pixels are not independent samples; a random split on autocorrelated
data inflates accuracy badly. A large slice of the ML-for-SDB literature gets
this wrong. Getting it right — and explaining why in the write-up — is worth
more than any accuracy number.

Report, per site:

- RMSE, bias and R², stratified by **depth band** (0–2, 2–5, 5–10, 10–15, 15–20 m)
- Error stratified by **substrate** — dark seagrass reads as deeper water, the classic SDB failure mode
- Error against **sea state / turbidity proxy** at acquisition
- The depth at which error exceeds a stated threshold — the **breakdown depth**

## Error budget

| Term | Magnitude | Note |
|---|---|---|
| Reference (IHO Order 1b) | ±0.52 m at 10 m, ±0.56 m at 20 m | TVU = √(a² + (b·d)²), a=0.5, b=0.013, 95% |
| Reference horizontal | 5 m + 5% depth ≈ 5.5 m | Sub-pixel at 10 m S2 |
| Expected SDB error | 1.3–2.2 m clear water; unknown here | The quantity being measured |
| Water level correction | Tide gauge + interpolation | Scalar offset |
| **Seabed change 2018→scene** | **The real constraint** | See below |

Reference is 2.5–4× more precise than the error being measured. Gate passes.
**Be honest that it narrows in the top 2 m**, where SDB is most accurate and
reference uncertainty and method error converge.

**Temporal pairing is the design constraint.** Lidar was flown across a
six-month window in 2018 and sandy nearshore seabed moves. Pair each lidar
tile with Sentinel-2 scenes as close as possible to *that tile's* acquisition
date. Residual seabed change is a line in the error budget, not an oversight.
State the pairing tolerance before building, not after.

## Decision gates

| Phase | Gate | Fail action |
|---|---|---|
| 1 | Seabed visibly resolvable in the scene; lidar and imagery align | Try another scene/date before touching the method |
| 2 | Site 1 RMSE within ~2× literature (< ~4 m) | Diagnose water level, glint, atmospheric correction — do not tune blindly |
| 3 | Blocked-CV result holds within ~30% of naive split | If not, the naive number was the illusion; report both |
| 4 | Sites 2 and 3 produce a monotonic error–clarity relationship | If not, that is itself the finding — report it |

## What this is not

Not a navigation product. Not a hydrographic survey. Not a replacement for
multibeam or lidar. Not an operational service. The reference data's own
metadata says it should not be used for navigation without further
processing; the same applies doubly here.

## Repo structure

```
sdbNSW/
├── README.md                   # the result: question, number, limitations first
├── PROJECT_BRIEF.md            # this file
├── BUILD_GUIDE.md              # the walkthrough
├── requirements.txt
├── .gitignore
├── src/
│   └── sdb/
│       ├── stac.py             # scene discovery + selection
│       ├── reference.py        # lidar load, clip, align to S2 grid
│       ├── waterlevel.py       # tide at acquisition time
│       ├── sdb.py              # Stumpf ratio transform, calibration
│       ├── validate.py         # blocked CV, statistics, stratification
│       └── viz.py              # one palette, one set of chrome
├── tests/                      # every statistic against an analytic answer
├── config/
│   └── sites.yml               # the three bboxes and their pairing windows
├── data/
│   ├── reference/              # committed CC BY lidar subsets
│   └── scenes/                 # gitignored — imagery is not committed
├── outputs/                    # figures, paired observations, metrics
└── site/                       # GitHub Pages deliverable
```

Conventions follow `seismicPython`: importable package under `src/`, no I/O
in the maths, tests against analytically known answers.

## Portfolio integration

Replaces the Murray REM card. The card must carry a **number**, which no
current card does.

Draft: *"Independent accuracy assessment of satellite-derived bathymetry
across three NSW coastal sites spanning a water-clarity gradient, validated
against IHO Order 1b airborne lidar. Reports RMSE by depth band, substrate
and sea state, and the depth at which the method breaks down."*
Tags: Sentinel-2 · STAC/COG · Accuracy Assessment · Bathymetry · Python

Deliverable: GitHub Pages page with the error figures and a small
SDB-versus-lidar comparison, plus the repo. Limitations panel above results.

## Open decisions

- [ ] Confirm repo name `sdbNSW`
- [ ] Confirm site 3 (Batemans vs Richmond) after checking lidar tile coverage
- [ ] Atmospheric correction: L2A as supplied, or test whether it matters (one paper found it optional)
- [ ] Sun glint correction method
- [ ] Whether ML enters v1

## Sources

- NSW Marine LiDAR Topo-Bathy 2018 — https://datasets.seed.nsw.gov.au/dataset/marine-lidar-topo-bathy-2018
- ELVIS — https://elevation.fsdf.org.au/
- IHO S-44 Ed. 6.1.0 — https://iho.int/uploads/user/pubs/standards/s-44/S-44_Edition_6.1.0.pdf
- Sentinel-2 + ICESat-2 SDB with ML (Frontiers, 2023) — https://doi.org/10.3389/feart.2023.1111817
- SDB empirical vs ML in dynamic coastal water (2024) — https://doi.org/10.1080/21664250.2024.2445418
- ICESat-2 Bathymetry Working Group — https://github.com/ICESat2-Bathymetry/Information
- AusSeabed — https://www.ausseabed.gov.au/data
