# Satellite-Derived Bathymetry on an Exposed Temperate Coast — project brief

**Status:** Phase 1 gate **passed on geometry, provisional on water level**.
Co-registration against NSW orthoimagery on land: **E −7.4 ± 1.0,
N −1.0 ± 1.1 m** (8 windows agree), applied. Water level at overpass
**−0.50 m AHD, provisional** (image estimate, biased low ~0.1–0.2 m); the
observed record from MHL's Jervis Bay gauge has been requested. Reference on
the scene grid: **93.8 km² usable in 0–20 m**.
**Phase 2: protocol pre-registered** (`8332154`), then run once. **Gate
passed: pooled RMSE 2.70 m** [95% CI 2.32–3.15], bias −0.41 m, R² 0.69
(inside the bay 2.28 m, open coast 4.72 m). Worse than the ~1.8 m clear-water
Stumpf literature, as expected. **Does not meet CATZOC C at any depth**; error
is flat near 2 m RMSE to ~14 m, then climbs as the ratio saturates. SDB reads
~1 m too deep in 0–10 m, in spatially coherent patches — substrate is next.
Provisional water level; rerun when the gauge record arrives.
**Updated:** 27 Sep 2026 · **Repo:** `sdbNSW`
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

| # | Site | Role | bbox (WGS84) |
|---|---|---|---|
| 1 | Jervis Bay | Best case — sheltered, clear, mixed substrate | **Measured:** 150.6607, −35.1504, 150.8083, −34.9735 (block NSW020502) |
| 2 | Narrabeen–Long Reef | Exposed, surf-dominated | Indicative 151.29, −33.74, 151.33, −33.70 — measure from `data/reference/nsw_marine_lidar_blocks_index.csv` |
| 3 | Batemans Bay / Clyde mouth | Worst case — estuarine turbidity | Indicative 150.17, −35.75, 150.25, −35.68 — block NSW020602, captured 2018-08-24 |

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
| MHL tide gauge 216470, Jervis Bay (HMAS Creswell) | Observed water level at overpass; AEST; chart datum, AHD offset −1.07 m | MHL data request (form or data-request@mhl.nsw.gov.au) | CC BY 4.0, attribute NSW DCCEEW | Raw file no (`data/raw/tide/`); derived value yes |
| NSW Imagery (Spatial Services) | Orthophoto windows for co-registration only | ArcGIS REST Export Map, anonymous | Catalogue: CC BY 3.0 AU; Spatial Services excludes images from its CC licence | **No** — cached in `data/raw/ortho/`, never redistributed or drawn |
| ERA5 10 m wind | Scene selection only — glint pre-screen | [Open-Meteo](https://open-meteo.com/) archive API, anonymous | CC BY 4.0 | No — fetched at run time |
| NSW DPI Fisheries *Estuarine Macrophytes* (candidate) | Seagrass stratum: *Posidonia*, *Zostera*, *Halophila*. Jervis Bay from **Aug 2019** aerial imagery (object-based classification), field-checked **May 2020** (project MEMS) | ArcGIS REST (`Fisheries_Portal/Estuarine_Macrophytes`) | © NSW DPI Fisheries; IMAS copy CC BY-NC 4.0 | No — derived statistics only |
| DCCEEW *NSW seabed reef extent* (candidate) | Reef stratum, classified from **the same 2018 marine lidar** (plus 2017 subtidal reef mapping) | ArcGIS REST / zip | CC BY 4.0 | Derived statistics |

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
Exact specification: *Phase 2 protocol* below.

**v2 — ML, in scope only if v1 earns it.** Random forest / gradient boosting
regression on the same bands, same folds, same reference. The question is not
"can ML do SDB" (it can) but **does the ML advantage survive degraded water
clarity, or does it evaporate?** Literature says ~0.5 m advantage in clear
water and is silent on turbid. Interesting either way, including if ML loses.
**Never give the model coordinates as features** — that is how a flexible model
memorises the site and how random splits flatter it.

Defer ML until site 1 has an empirical number. A comparison with nothing to
compare against is a demo.

## Validation design

**Spatially blocked cross-validation, not random splits.** Neighbouring
raster pixels are not independent samples; a random split on autocorrelated
data inflates accuracy badly. A large slice of the ML-for-SDB literature gets
this wrong. Getting it right — and explaining why in the write-up — is worth
more than any accuracy number.

Expect little difference for Stumpf: two global parameters cannot memorise
location, so blocked ≈ random is the likely v1 result. That is the **control**:
the leakage story is shown when a flexible model (v2) diverges on the same folds.

Report, per site:

- RMSE, bias and R², stratified by **depth band** (0–2, 2–5, 5–10, 10–15, 15–20 m), by lidar depth **and by predicted depth** (a map user only has the latter)
- Error stratified by **substrate** — dark seagrass reads as deeper water, the classic SDB failure mode
- Error against **exposure**: inside the bay vs open coast within a scene; sea state and turbidity mainly *between* sites (Phase 4)
- The depth at which error exceeds a stated threshold — the **breakdown depth**
- The **denominators**: how much reference water in each band could not be assessed, and why

## Phase 2 protocol — pre-registered 27 Sep 2026

Committed before any depth model is fitted to real data. Anything changed
after the first run is logged in the decisions register as a **deviation**,
with the reason, and both results are reported. Implemented in
`src/sdb/sdb.py` (maths) and `src/sdb/validate.py` (folds, statistics, CLI).

**Data.** Scene `S2A_56HKG_20180907_0_L2A`; pixels whose `mask.tif` flag is 0.
Depth `d = WL − z_mean`, with WL read from `outputs/reference_<scene>.json`
so depth and mask always share one water level. Surface reflectance as
supplied (Sen2Cor L2A, baseline 00.01). **No glint correction** (register, 27 Sep).

**Model.** pSDB = ln(1000·ρ_blue) / ln(1000·ρ_green) (Stumpf et al. 2003).
Both logarithms are positive in every usable pixel (minimum 0.34); a pixel
where either is ≤ 0 is excluded and counted. Depth = m1·pSDB − m0, ordinary
least squares of depth on pSDB. **One calibration for the whole site** —
inside bay and open coast alike, as a user of the method would apply it.

**Calibration — inside each training fold, never on held-out pixels.**

1. Median pSDB in 1 m depth bins over 0–20 m (bins with fewer than 200
   pixels ignored), smoothed with a 3-bin running median.
2. Fitting limit **D_cal** = upper edge of the shallowest bin whose smoothed
   median reaches 95% of the rise from the shallowest bin to the peak — the
   depth where the ratio stops rising. 20 m if it rises throughout.
3. Calibration sample: up to 5,000 pixels drawn at random from each 1 m bin
   below D_cal — **depth-balanced**, because 70% of usable pixels lie in
   10–20 m and 2.7% in 0–2 m; an unweighted fit would be set by the depths
   where the signal is weakest.
4. OLS on that sample. D_cal per fold is reported: it is the **optical
   saturation depth**, a finding in itself.

**Validation.**

- **Primary:** blocked 5-fold cross-validation. 2 km square blocks aligned to
  the scene grid (67 blocks hold usable pixels). Blocks are shuffled and dealt
  to folds in turn; **10 repeats**, fold seeds 0–9. Each pixel's prediction
  is the mean of its 10 out-of-fold predictions — none from a model that saw
  its block. Every statistic below is computed on these.
- **Naive:** pixel-level random 5-fold, same repeats, reported alongside.
- **Block-size curve:** pooled RMSE for random, 0.5, 1, 2 and 4 km blocks
  (mean and range over repeats).
- **Residual correlogram** at lags 10 m – 8 km; its *range* is the shortest
  lag at which correlation falls below 0.1. If the range exceeds 2 km, the
  primary result carries that caveat.

**Statistics.** Error e = SDB − lidar (positive = SDB reads too deep). For each
group: n, bias, RMSE, MAE, median |e|, 95th percentile |e|, R².

- **Pooled** over all usable pixels — for the gate and literature comparison
- **Depth-balanced RMSE** = mean of the five depth-band RMSEs — pooled RMSE is
  as much a property of the depth histogram as of the method
- By 1 m bin, and by depth band of lidar depth and of predicted depth
- **Inside bay vs open coast**: polygon `strata.inside_bay` in
  `config/sites.yml` (the only water it crosses is the entrance line, Point
  Perpendicular – Bowen Island – Governor Head; checked by connectivity).
  823,009 vs 114,490 usable pixels at the provisional water level
- By sub-pixel relief tercile; by distance to shore (0–50, 50–100, 100–200,
  200–500, 500–1000, > 1000 m) within depth band — a darker NIR rim along every
  shore suggests adjacency over-correction, which would bias shallow water
- By substrate, once a layer is adopted (below)
- **95% confidence intervals by block bootstrap**: 2 km blocks resampled with
  replacement, 1,000 draws, percentile intervals, for bias, RMSE, MAE and R²
- **Exclusions per depth band**: reference water that could not be assessed,
  by reason. The bright-NIR flag alone removes 32% of 0–2 m pixels, so the
  0–2 m result describes calm water only

**Breakdown depth.** The lower edge of the shallowest 1 m lidar-depth bin whose
95th-percentile |e| exceeds **IHO CATZOC C: 2.0 m + 5% of depth** (95%
confidence), evaluated at the bin's mid-depth. CATZOC B (1.0 m + 2%) is
reported the same way. The full curve is published; "not reached" if no bin in
0–20 m exceeds it.

**Gate.** Pooled RMSE < 4 m (Phase 2 gate). On failure, diagnose water level,
glint, then atmospheric correction, in that order — no tuning.

**Not in v1.** The red/green switching model (Caballero & Stumpf 2019) improves
0–5 m, which is not the question here; if added later it is labelled
exploratory. Glint correction and ACOLITE — only as diagnosis if the gate fails.
ML — v2, same folds.

**When the gauge record arrives.** Re-run `waterlevel` → `reference` →
`validate` and report both. For a fixed set of pixels a constant water-level
error changes only m0 and leaves every residual unchanged (pinned by a test);
what moves is which pixels fall in each band and inside 0–20 m.

**Substrate — adopted before substrate results are read, not before the run.**
Substrate never enters the model; it only groups out-of-fold errors, so adding
it after the run cannot flatter the fit. The class rules (which classes, how
mixed pixels are labelled) are fixed before errors by class are computed.

### Phase 2 result — Jervis Bay, 7 Sep 2018 (provisional water level −0.496 m AHD)

The pre-registered run, unchanged. `outputs/sdb_S2A_56HKG_20180907_0_L2A.json`.

| | Result |
|---|---|
| Pooled, 2 km blocks, 5-fold × 10 | RMSE **2.70 m** [2.32, 3.15] · bias −0.41 m [−0.95, +0.07] · R² 0.69 [0.57, 0.77] · n 937,499 |
| Depth-balanced RMSE | 2.48 m |
| Naive random split | 2.67 m — blocked/naive **1.009**, as predicted for a two-parameter model |
| Block-size curve (random, 0.5, 1, 2, 4 km) | 2.67, 2.70, 2.70, 2.71, 2.73 m |
| By depth band (bias / RMSE, m) | 0–2 **+0.98** / 2.09 · 2–5 **+1.23** / 2.67 · 5–10 **+0.82** / 2.08 · 10–15 +0.12 / 2.08 · 15–20 **−2.10** / 3.50 |
| Inside bay / open coast | RMSE 2.28 [2.01, 2.55] / **4.72** [3.64, 5.89]; open coast 15–20 m bias −5.75 |
| Breakdown depth | CATZOC C and B both **exceeded from the shallowest bin**: 95th-percentile error 3.2–3.9 m through 0–13 m against an allowance of 2.0–2.7 m |
| Saturation depth D_cal | 20 m in 46 of 50 folds, 16–17 m in 4 |
| Residual correlation | 0.69 at 10 m, 0.16 at 2 km, below 0.1 by **4 km** — longer than the blocks |
| Assessed share of reference water | 0–2 m 66%, 2–5 m 97%, deeper ≥ 99% |

What it says: the method passes the gate but is not charting-grade anywhere in
this bay, and it fails in two distinct ways — a ~2 m error floor from the
surface down, carrying a +1 m (too deep) bias in 0–10 m, and a saturation
failure beyond ~14 m where SDB reads too shallow. The residual map puts the
shallow over-reading in coherent patches on the western and northern shelves,
where seagrass is expected: the substrate stratification is the test of that.
Exposure matters as much as depth — the open coast doubles the error.

Caveats on this run: the residual correlation outlasts the 2 km blocks, so the
bootstrap intervals are probably too narrow (the RMSE itself barely moves with
block size, 2.71 → 2.73 m at 4 km). Within-band R² is negative and not
meaningful — the depth range inside a band is small relative to the error.
Pixels within 50 m of shore carry RMSE of 6–8 m at 2–15 m depth (cliff-foot
rock, few pixels).

## Error budget

| Term | Magnitude | Note |
|---|---|---|
| Reference (IHO Order 1b) | ±0.52 m at 10 m, ±0.56 m at 20 m | TVU = √(a² + (b·d)²), a=0.5, b=0.013, 95% |
| Reference horizontal | 5 m + 5% depth ≈ 5.5 m | Sub-pixel at 10 m S2 |
| Expected SDB error | 1.3–2.2 m clear water; unknown here | The quantity being measured |
| Water level correction | Provisional −0.50 m AHD (image; biased low ~0.1–0.2 m, broad peak ±0.15 m); gauge record requested | A constant error is absorbed by the Stumpf intercept; it moves depth bands, masks and anything reported against AHD |
| **Co-registration** | 7.5 m measured and removed; residual ±1.0 m E, ±1.1 m N (1σ), plus ~1.5 m possible datum offset in the reference imagery | On a 1:10 seabed slope 1 m of misregistration is 0.1 m of depth. Now a minor term |
| Sub-pixel relief | Median 0.01–0.09 m, p90 ≤ 0.24 m by depth band | Std of the 5 m cells inside each 10 m pixel. Minor except on reef edges; kept for stratification |
| **Seabed change 2018→scene** | **The real constraint** | See below |

Reference is 2.5–4× more precise than the error being measured. Gate passes.
**Be honest that it narrows in the top 2 m**, where SDB is most accurate and
reference uncertainty and method error converge.

**Temporal pairing is the design constraint.** The survey spans 8 July –
3 October 2018 and sandy nearshore seabed moves. Pair each site with scenes as
close as possible to *that block's* capture date.

For Jervis Bay this largely resolved itself: every block over the AOI was
flown on 8–9 September 2018, and the chosen scene is 7 September — one day
before the survey, so seabed change is a minor term here rather than the
dominant one. It will not be for every site.

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
├── environment.yml / pyproject.toml
├── .gitignore
├── src/
│   └── sdb/
│       ├── stac.py             # scene discovery + selection
│       ├── glint.py            # Cox–Munk glint index from ERA5 wind (selection only)
│       ├── fetch.py            # quicklooks; AOI reflectance stack + SCL
│       ├── ortho.py            # orthoimagery fetch/cache, window selection, registration
│       ├── coreg.py            # co-registration CLI (ortho primary; waterline diagnostic)
│       ├── reference.py        # exact area-weighted lidar -> scene grid; masks
│       ├── waterlevel.py       # water level at overpass: MHL gauge, or image (provisional)
│       ├── sdb.py              # Stumpf ratio transform, calibration
│       ├── validate.py         # blocked CV, statistics, stratification
│       └── viz.py              # one palette, one set of chrome
├── tests/                      # every statistic against an analytic answer
├── scripts/                    # one-off provenance checks (network), not pipeline
├── config/
│   └── sites.yml               # bboxes, pairing windows, tide gauge, strata polygons
├── data/
│   ├── README.md               # provenance: how to obtain each input, licences, what is committed
│   ├── reference/              # committed: block index, CC BY lidar subsets
│   └── raw/                    # gitignored: ELVIS delivery, scenes/<id>/
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

- [x] Repo name `sdbNSW`
- [x] Jervis Bay scene — `S2A_56HKG_20180907_0_L2A` (see decisions register)
- [ ] **Observed water level at overpass** — MHL Jervis Bay (216470) record for 6–8 Sep 2018 requested; replaces the provisional image estimate when it arrives
- [ ] Confirm site 3 (Batemans vs Richmond) after checking lidar tile coverage
- [x] Atmospheric correction — **L2A as supplied** for v1; ACOLITE only as diagnosis if the gate fails
- [x] Sun glint correction — **none** for v1 (register, 27 Sep)
- [x] Whether ML enters v1 — **no**; v2, same folds, no coordinates as features
- [x] Breakdown threshold — **CATZOC C** (2.0 m + 5% of depth, 95%); CATZOC B alongside
- [ ] **Substrate layer** — candidates: NSW DPI *Estuarine Macrophytes* (seagrass) and DCCEEW *seabed reef extent* (lidar-derived). Fetch, check dates, coverage of the usable area and alignment, then fix the class rules before errors by substrate are read

## Decisions register

Dated, including reversals. This is what turns a folder of scripts into a
defensible piece of work.

| Date | Decision | Why |
|---|---|---|
| 27 Sep | Reference ordered in native **GDA2020 / MGA 56 (EPSG:7856)** | Any reprojection resamples the reference surface. GDA2020 also sits within centimetres of the ITRF frame Sentinel-2 uses; GDA94 is ~1.8 m off |
| 27 Sep | Delivered DEM verified | 5 m, AHD, IHO Order 1b per supplier metadata. −42.7 to +166.6 m. **95.6 km² in 0–20 m** (~955k cells at 10 m). Mosaic of blocks flown 8 and 9 Sep 2018. Laser reached 42.7 m — top of the stated 20–40 m range, so the water is clear |
| 27 Sep | **Aggregate lidar onto the S2 10 m grid**; never upsample imagery | Upsampling invents spatial detail and flatters the error. Aggregating four 5 m cells also reduces reference noise |
| 27 Sep | AOI straddles MGRS **56HKG / 56HLG**, no common date. 56HKG covers 100%; 56HLG only the eastern part. **All 56HLG scenes rejected** — including the same-day 8 Sep scene | A scene covering part of the bay cannot validate the bay. Partial coverage is a hard rejection, not a score penalty |
| 27 Sep | Duplicate processings collapsed; prefer baseline **05.00** (Collection-1) | Same datatake published twice. Collection-1 is consistently reprocessed. Its −0.1 BOA offset is applied at fetch and verified against water physics (red/NIR medians near zero) |
| 27 Sep | Scene: **`S2A_56HKG_20180907_0_L2A`**, 2018-09-07 00:02 UTC, one day before the lidar | AOI cloud 0.55% despite 36.4% tile cloud; calm inside the bay, seabed visible along the shallow margins. **12 Sep rejected** on inspection: wind-roughened surface, glint streaks across the bay, resolved wave texture offshore — with near-identical sun geometry (facet 23.4° vs 24.3°), so the difference is wind, which the glint heuristic cannot see. **17 Sep rejected**: cumulus and shadow over the bay (3.6% AOI vs 1.2% tile). Tile cloud misled in both directions |
| 27 Sep | Accept baseline **00.01** for the chosen scene | No Collection-1 version exists for 7 Sep. Departs from the 05.00 preference; scene quality outweighs processing preference. No BOA offset applies; the conversion is verified by the water plausibility check at fetch |
| 27 Sep | Stratify site-1 error **inside-bay vs open coast** | The outer coast east of Beecroft is visibly rougher than the sheltered bay in every candidate, and both lie in the 0–20 m envelope — an exposure gradient within a single scene |
| 27 Sep | **Wind disagreement resolved: the model, not the hour.** The first pull used Open-Meteo's default `best_match`, which here is **ECMWF IFS 9 km** (cell −35.044, 150.687); `stac.py` requests **ERA5 0.25°** (cell −35.000, 150.750). Same hour — no time-zone slip. 12 and 17 Sep: the two agree (NNE, within 0.6 m/s and 13°). **7 Sep: 0.86 vs 3.58 m/s** — the overpass (10:02 local) falls while the morning north-westerly is dying ahead of a north-easterly; ERA5 puts the lull at the overpass, IFS about two hours later. Direction agrees throughout. Evidence: `scripts/check_wind_sources.py` | Earlier today this register read "speed prediction falsified; direction explains the glint", built on one pull whose defaults were not recorded. Neither that nor the reverse is established: 7 Sep wind at overpass lies somewhere in 0.9–3.6 m/s. **Lesson: pin every parameter of an API call a decision rests on — a default is a hidden parameter** |
| 27 Sep | What survives both sources: **12 Sep is the most glint-prone** of the three — slope needed to glint 3.7σ (ERA5) / 3.9σ (IFS) vs 4.5–6.4σ for the clean scenes. Scene choice unaffected | The only discriminating observation. 7 and 17 Sep were both clean, so their order is untested |
| 27 Sep | **ERA5 stays the default wind source** (`models=era5`, pinned) | Reanalysis: one consistent system for every date and all three sites, citable. IFS resolves the coast better but is an archive of operational forecasts whose model changes over time, from 2017 only. Neither is validated here; a station record (e.g. BOM Point Perpendicular at the bay entrance) would arbitrate if a decision ever hinged on it |
| 27 Sep | **The glint index flags; it does not rank close calls.** The choice of source alone moved 7 Sep from 4.5σ to 6.4σ | Treat scenes whose `glint_sigma` differs by less than the between-model spread (~2σ at a transition hour) as indistinguishable. A second-source option for `stac.py` is deferred to site 2, when a choice may actually depend on it |
| 27 Sep | Wind-aware glint index in scene discovery (`glint.py`, on by default, `--no-wind` to skip), reported as **`glint_sigma`** — slope needed to glint in standard deviations, lower = more glint-prone. **Reported, never scored** | The first version reported glint relative to the calmest scene: near calm the Gaussian tail gives ~10⁻¹⁶ reflectance and the ratios reached 10⁷ — meaningless. Sigma is bounded, monotonic and readable. Winds below 1 m/s are evaluated at 1 m/s, so sigma is then a lower bound. Out of the score: one discriminating observation does not justify a weight. Fails soft if the API is unreachable; refuses km/h (the API default) |
| 27 Sep | Lidar grid **does not nest** in the S2 10 m grid: origin E 286500.454, N 6127921.421, pixel 5.000000011 m. **Aggregate by area-weighted average** onto the scene grid, not 2×2 block means | Offset (0.45, 1.42) m from a 5 m lattice — consistent with a round GDA94 grid shifted to GDA2020 by editing the georeferencing, not resampling (good: values untouched). Block means would misplace the reference by up to 1.4 m. GDA2020 vs WGS84 at the 2018 epoch is ~0.1 m — negligible |
| 27 Sep | **Co-registration is measured, not assumed.** Estimate the image-to-lidar shift before any depth comparison; the Phase 1 alignment gate becomes a number | ESA's July 2018 L1C quality report: S2A absolute geolocation ~12 m at 95%, no ground control. GRI refinement (8 m at 95%) arrived with baseline 03.00 and the Collection-1 reprocessing; the chosen scene is baseline 00.01, so unrefined. Up to a pixel of misregistration would dominate error on slopes. If the shift cannot be measured confidently, fetch the Collection-1 version from Copernicus Data Space instead |
| 27 Sep | **Glint index passed a prediction test.** Predictions committed in `e5955e7` before viewing: 22 Oct (2.6σ) glint, 28 Aug (3.4σ) glint, 18 Aug (5.0σ) clean. Quicklooks: all three as predicted | Across six scenes glint shows at ≤3.9σ, clean water at ≥4.5σ. Tentative rule for sites 2–3: **below ~4σ expect glint**. Six scenes, one bay — a rule of thumb, not a calibration |
| 27 Sep | **Aggregation by exact per-axis overlap areas**, not GDAL resampling | PROJ treats GDA2020 → WGS84 here as a null operation (checked at run time: 0.1 mm), so the lidar lies in the scene's plane, offset 0.454 m E / 1.421 m N. Exact, GDAL-version independent, and cheap enough (0.5 s) to repeat at every trial shift. Tested against closed forms: a plane averages to its centre value, a step to its area fraction. 91.6 km² usable in 0–20 m vs 95.6 km² at 5 m — the difference is shoreline-mixed pixels, cloud and flags |
| 27 Sep | **Misregistration measured: E −18.5 ± 2.9 m, N −11.1 ± 5.8 m (21.6 m, ~2 px) — applied, provisionally.** Image features are drawn ~18 m east and ~11 m north of where they are | Steep shores only (waterline ≥30°): 7 segments, all on Beecroft Peninsula — Bowen Island and the southern headlands are fringed by rock platforms (median waterline slope 10°), which the filter correctly excludes. Independent all-shoreline cross-check: (−17.0, −5.3); correlation 0.613 → 0.684. Supporting diagnostics: shifting halves the land pixels that read as water; the opposite shift makes both measures markedly worse. ~2× ESA's 12 m (95%) figure — large but supported by two estimators. **Provisional** because no steep shore faces north or south: re-estimate with gentle shores admitted once the tide is known |
| 27 Sep | Cross-check agreement rule: per component within max(3 m, 2 × steep-shore stderr) | Conventional 2σ with a floor. Codified *after* an exploratory all-shore run on this scene, so not blind — but not tuned: the scene passes by a wide margin (E 1.5 of 5.8 m, N 5.8 of 11.6 m) |
| 27 Sep | Why steep shores only — **shown, not argued**: synthetic island, true shift 8.4 m, tide assumed 0.6 m too high | Steep-only estimate 0.7 m out. All-shore estimate 5.0 m out *and called the shift negligible* — the tide error on beaches nearly hid a real misregistration. Pinned in `tests/test_coreg.py` |
| 27 Sep | **The tide was below 0 m AHD at overpass.** The image prefers a water level of **~−0.45 m AHD** (all-shore correlation peaks there, with or without the shift), and 73% of 0–1 m pixels read bright in NIR at 0 m whatever the shift | Prediction for `waterlevel.py`: the gauge should read about **−0.3 to −0.5 m AHD** at 00:02 UTC 7 Sep 2018 — NIR sees through the first ~0.2 m of water, so the image estimate is biased slightly low |
| 27 Sep | **QGIS gate: the 21.6 m co-registration is wrong. Superseded.** Screenshot pairs at identical extents, cross-correlated here (four preprocessing variants each). Airfield: S2 − NSW Imagery **E +7.0, N +3.7 m**; S2 − ESRI E +9.0, N +3.0; ESRI − NSW −1.3 to −2.4 E, ~+0.5 N — the three close. Huskisson (noisier, roofs): S2 − NSW E +4.6 to +8.2, N +1.1 to +5.2; ESRI − NSW ≈ −2 m again | True misregistration ≈ **E −6.5, N −3.5 m (≈ 7–8 m, ±~2 m)** — within ESA's 12 m (95%). NSW Imagery is authoritative but may be served with GDA94 treated as WGS84, a ~1.5 m ambiguity; ESRI agrees with it to ~2 m. The shift applied to `reference.tif` (−18.47, −11.11) is ~14 m wrong — worse than none. Nothing downstream used it |
| 27 Sep | **Why the waterline method failed: its biases all pointed east in this scene** | West-facing cliffs are in shadow under a north-easterly sun, so their image edge reads landward (east). East-facing ocean cliffs carry whitewater at the base, so their edge reads seaward (east). The bay's long beaches mostly face east, so a low tide and NIR seeing through the first ~0.2 m of water push their edge seaward (east). Different mechanisms, one direction. The QGIS view shows the shadow band directly |
| 27 Sep | **Lesson: agreement between two estimators that share a signal is not independence** | Steep-shore and all-shore estimates agreed (−18.5 vs −17.0 E) and I treated that as confirmation. Both read the same water edge and inherited the same biases. The test that caught it used a different signal entirely — land features against an independent orthophoto. The gate worked because it was a different kind of check, not a second opinion from the same kind |
| 27 Sep | **Proposed: co-register against reference orthoimagery, on land**, with the waterline method demoted to a diagnostic | Fetch NSW Imagery windows through its public ArcGIS REST `export` endpoint directly in EPSG:32756; aggregate to 10 m; sub-pixel phase correlation against S2 over several land windows spread across the scene (runways, roads, clearings, towns); median shift, window scatter as the error bar. Licence to be confirmed before use. **Awaiting approval** |
| 27 Sep | **Co-registration rebuilt on orthoimagery: E −7.42 ± 0.98, N −1.02 ± 1.14 m (7.5 m) — applied.** 11 automatically chosen 2 km land windows; 8 agree (scatter E 2.2, N 2.6 m), 1 outlier dropped (+15 m E, Booderee), 2 rejected for weak correlation (forest) | Exact area aggregation of 2 m orthophoto onto the scene grid at each trial shift, gradient correlation, coarse-then-fine search. Recovers synthetic shifts to <0.7 m under different radiometry, blur and noise. East matches the screenshot check (−7.0 at the airfield); north is smaller than it suggested (−1.0 vs −3.7), within ~2σ, and rests on eight windows rather than two |
| 27 Sep | Orthoimagery used as a **positional reference only** | Licence is unclear for images (catalogue CC BY 3.0 AU; Spatial Services' copyright page excludes images; parts are third-party). Tiles stay in gitignored `data/raw/ortho/`, only numbers are committed, and figures show Sentinel-2 NIR, never the orthophoto. Fetch uses the standard library only, so it also ran inside QGIS's Python to test it on real data |
| 27 Sep | **Tide gauge found in the bay**: MHL 216470, Jervis Bay at HMAS Creswell, radar since 1989, AEST, chart datum with AHD offset −1.07 m | Historical data by request (CC BY 4.0). Not in the Bureau's Water Data Online; MHL's web predictions only reach back 90 days. The 2018 record must come from MHL |
| 27 Sep | **Datum inferred from the numbers, not the label** | MHL's own pages label chart-datum values "m AHD" (live chart: 1.66, above the 1.36 m AHD flood of record) and an AHD table "Chart Datum". MSL 2018-19 is +0.074 m AHD = +1.144 m CD, so a record's mean identifies its datum; ambiguous means refuse |
| 27 Sep | **Provisional water level −0.50 m AHD** from the image (whole-shoreline NIR vs lidar land fraction, co-registration applied) | Consistent with a near-spring low: new moon 9 Sep; MLWS 2018-19 is −0.515 m AHD. Biased low by ~0.1–0.2 m (NIR reads through very shallow water), so the gauge should read about −0.3 to −0.4 m. Estimator exact on curved synthetic shorelines; worst case one straight grid-aligned beach, ~6 cm |
| 27 Sep | **Phase 2 does not wait for the gauge** | A constant water-level error is absorbed by the Stumpf intercept; it moves depth-band membership and masks. Re-run `reference` when the gauge value arrives and report both |
| 27 Sep | Glint geometry: closed form `cos(2ω)=…` **replaced** with the vector derivation | The closed form is wrong off the principal plane (~0.8° at θs=20°, θv=30°, Δφ=90°). Immaterial at S2's near-nadir view, but wrong. Pinned by a grid test against an independent derivation |
| 27 Sep | **Phase 2 protocol pre-registered** before any depth model sees real data. Pre-fit checks deliberately did **not** look at the band ratio against depth | The co-registration lesson: a rule set after seeing the data is not blind, however honest. Every choice that could be tuned to the answer — calibration range, sample, blocks, thresholds — is fixed by rule in advance, and data-driven choices are made inside each training fold |
| 27 Sep | **No glint correction for v1.** Optically deep water (> 25 m, 197,785 px): NIR detail finer than 90 m has std 0.0012 and blue follows it at slope 0.78 (R² 0.28) — glint-like but ~0.001 in blue, ~4% of the median. The blue–NIR covariance a Hedley regression would fit is dominated by a **km-scale field** (810 m means: slope 4.9, R² 0.93) | Glint is spectrally near-flat, so a slope of ~5 is water type or atmosphere, not glint: Hedley would subtract real signal. The only lidar-covered deep water is at the entrance and outer coast, a different water mass from the bay. Sentinel-2's band-to-band timing also decorrelates pixel-scale glint (Harmel et al. 2018) |
| 27 Sep | **Depth-balanced calibration and reporting** | 70% of usable pixels are 10–20 m, 2.7% are 0–2 m. Unweighted, both the fit and the headline RMSE would describe the deep, weak-signal end |
| 27 Sep | **Breakdown threshold: CATZOC C**, not an invented one | An external charting standard (2.0 m + 5% of depth at 95%) that a hydrographer recognises. CATZOC B alongside. The curve is published so a reader can apply any other |
| 27 Sep | **Red/green switching model left out of v1** | It improves 0–5 m (Caballero & Stumpf 2019); the question is where the method stops working, which the blue/green ratio sets. Added later only as exploratory |
| 27 Sep | **Inside bay vs open coast defined by polygon**, checked by water connectivity | A first rectangle split mislabelled Wreck Bay and Summercloud Bay (south-facing ocean coast at the scene's southern edge) as bay. The polygon crosses water only on the entrance line (Point Perpendicular – Bowen Island – Governor Head): 823,009 bay vs 114,490 open-coast usable pixels (2,623 open-coast in 0–2 m) |
| 27 Sep | **2 km blocks** | 67 blocks with usable pixels; 4 km leaves 24, and 1 in 20 random fold draws then gets almost no 0–2 m pixels. Deep-water blue varies on km scales, so blocks must be ≥ 1 km; the correlogram checks it |
| 27 Sep | **Bright-NIR flag removes 32% of 0–2 m pixels** (11,717 of 36,842) — kept, but reported | The 0–2 m result therefore describes calm, non-breaking water. Stated with the denominators, not hidden in a mask |
| 27 Sep | **Implementation note on calibration step 2**, recorded before the run: its two sentences conflict for a steadily rising curve — 95% of the rise is reached one bin early (19 m), while the second sentence says 20 m. Implemented **as written**: peak in the deepest bin = "rises throughout" = 20 m; otherwise the 95% rule. Pinned in `tests/test_sdb.py` | Not a deviation: the committed text was followed. On the real data the exception decided **46 of 50 folds** — the median ratio keeps creeping upward to 20 m even where the error curve shows saturation from ~14 m. The pure 95% rule would likely have stopped earlier. Any rerun with it is **exploratory**, reported beside the pre-registered result, not instead of it |
| 27 Sep | **Phase 2 run once, as registered: gate passed**, pooled RMSE 2.70 m [2.32, 3.15]. Full table under *Phase 2 result* | Code written and tested on synthetic data after commit `8332154`, then run on the real pairs. The pattern is the model's, not the validation's: in-sample band biases from the all-data line match the out-of-fold ones to within 0.2 m |
| 27 Sep | **Breakdown depth = 0 m** for CATZOC C and B — the pre-registered statistic, reported as is | The rule finds the first bin that fails; here every bin fails, so its answer is "never meets CATZOC C", itself the finding. The shape — a flat ~2 m RMSE floor to ~14 m, then saturation — is described from the curve, not by inventing a new threshold after the fact |
| 27 Sep | **Residual correlation range 4 km > 2 km blocks: caveat applies**, as the protocol requires | Mostly systematic structure — depth-dependent bias, the open-coast offset and shelf-scale patches — rather than leakage: RMSE is flat across block sizes (2.67–2.73 m). The bootstrap intervals, which resample 2 km blocks, are the part most likely to be optimistic |
| 27 Sep | **Substrate candidates found; none adopted yet.** NSW DPI *Estuarine Macrophytes* covers the whole bay (Aug 2019 aerial, field May 2020; *Posidonia*/*Zostera*/*Halophila*); DCCEEW *seabed reef extent* is classified from the same 2018 lidar. GA's 2007–08 video and grabs cover only the southern bay; the 2018 lidar reflectivity is raw LAS | The seagrass map is 11 months after the scene: *Posidonia* is persistent, *Zostera*/*Halophila* are not. It is aerial-optical, so it may miss seagrass exactly where Sentinel-2 fails (deep, sparse *Halophila*); "not mapped as vegetated" is not "sand". The reef layer is independent of the imagery and contemporaneous |

## Sources

- NSW Marine LiDAR Topo-Bathy 2018 — https://datasets.seed.nsw.gov.au/dataset/marine-lidar-topo-bathy-2018
- ELVIS — https://elevation.fsdf.org.au/
- IHO S-44 Ed. 6.1.0 — https://iho.int/uploads/user/pubs/standards/s-44/S-44_Edition_6.1.0.pdf
- Sentinel-2 + ICESat-2 SDB with ML (Frontiers, 2023) — https://doi.org/10.3389/feart.2023.1111817
- SDB empirical vs ML in dynamic coastal water (2024) — https://doi.org/10.1080/21664250.2024.2445418
- ICESat-2 Bathymetry Working Group — https://github.com/ICESat2-Bathymetry/Information
- AusSeabed — https://www.ausseabed.gov.au/data
- MHL Jervis Bay tide gauge 216470 — https://www.mhl.nsw.gov.au/Station-216470
- PSMSL station JERVIS BAY II — https://psmsl.org/data/obtaining/stations/2312.php
- NSW Imagery Export Map service — https://maps.six.nsw.gov.au/arcgis/rest/services/public/NSW_Imagery/MapServer
- Spatial Services copyright — https://www.spatial.nsw.gov.au/copyright
- Sentinel-2 L1C Data Quality Report, Issue 28 (July 2018) — geolocation performance — https://sentinels.copernicus.eu/documents/247904/3897638/Sentinel-2_L1C_Data_Quality_Report/9699703d-556e-407a-a955-65c0c82dfcb5?version=1.2
- Sentinel-2 geometric refinement (GRI) — https://sentinels.copernicus.eu/-/forthcoming-deployment-of-the-copernicus-sentinel-2-products-geometric-refinement
- Cox & Munk (1954), roughness of the sea surface from sun glitter, *JOSA* 44(11) — https://doi.org/10.1364/JOSA.44.000838
- Hersbach et al. (2020), the ERA5 global reanalysis, *QJRMS* 146 — https://doi.org/10.1002/qj.3803
- Open-Meteo historical weather API — https://open-meteo.com/en/docs/historical-weather-api
- Stumpf, Holderied & Sinclair (2003), water depth from high-resolution imagery over variable bottom types, *Limnol. Oceanogr.* 48(1, part 2) — https://doi.org/10.4319/lo.2003.48.1_part_2.0547
- Caballero & Stumpf (2019), nearshore bathymetry from Sentinel-2A/2B, South Florida — https://www.researchgate.net/publication/334085536
- Hedley et al. (2005), simple and robust removal of sun glint — deglint specification in ESA SNAP — https://step.esa.int/main/wp-content/help/versions/9.0.0/snap-supported-plugins/org.esa.sen2coral.sen2coral.algorithms/deglint/DeglintAlgoSpec.html
- Harmel et al. (2018), sunglint correction of Sentinel-2 MSI from SWIR bands, *RSE* 204 — https://www.sciencedirect.com/science/article/abs/pii/S0034425717304856
- Roberts et al. (2017), cross-validation strategies for structured data, *Ecography* 40 — https://doi.org/10.1111/ecog.02881
- CATZOC definitions (S-57 attribute) — https://docs.teledynecaris.com/s-57/S57Cat/S57CatSite/attribut/catzoc.htm
- NSW DPI Fisheries Estuarine Macrophytes (REST) — https://spatial.industry.nsw.gov.au/arcgis/rest/services/Fisheries_Portal/Estuarine_Macrophytes/MapServer/0
- DCCEEW NSW seabed reef extent — https://mapprod3.environment.nsw.gov.au/arcgis/rest/services/Marine/NSW_seabed_reef_extent/MapServer
- GA Record 2009/10, Jervis Bay soft-sediment habitats — https://www.ga.gov.au/bigobj/GA14300.pdf
