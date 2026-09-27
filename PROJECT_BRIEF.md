# Satellite-Derived Bathymetry on an Exposed Temperate Coast — project brief

**Status:** Phase 1 — gate **not yet passed**. Scene fetched and checked;
lidar aggregated onto the scene grid (91.6 km² usable in 0–20 m). The QGIS gate
**overturned the waterline co-registration**: against NSW Spatial Services
orthoimagery, on land, the image is offset **~7–8 m (E −6.5, N −3.5)**, not
21.6 m. `reference.tif` currently carries the wrong shift — do not build on
it. Next: co-registration against reference orthoimagery (plan below), then
the tide at overpass.
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
| MHL NSW tide | Water level at acquisition time | mhl.nsw.gov.au | Attribution | Derived only |
| ERA5 10 m wind | Scene selection only — glint pre-screen | [Open-Meteo](https://open-meteo.com/) archive API, anonymous | CC BY 4.0 | No — fetched at run time |
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
| Water level correction | Not yet measured. Image implies ~−0.45 m AHD at overpass vs 0 m assumed | Scalar offset. Now the leading open term |
| **Co-registration** | ~7–8 m before correction (land features vs NSW orthoimagery); ±~2 m after, pending the orthoimagery-based `coreg` | On a 1:10 seabed slope 5 m of misregistration is 0.5 m of depth. The waterline method's 21.6 m was biased — see register |
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
│       ├── coreg.py            # image-to-lidar offset from steep shorelines
│       ├── reference.py        # exact area-weighted lidar -> scene grid; masks
│       ├── waterlevel.py       # tide at acquisition time
│       ├── sdb.py              # Stumpf ratio transform, calibration
│       ├── validate.py         # blocked CV, statistics, stratification
│       └── viz.py              # one palette, one set of chrome
├── tests/                      # every statistic against an analytic answer
├── scripts/                    # one-off provenance checks (network), not pipeline
├── config/
│   └── sites.yml               # the three bboxes and their pairing windows
├── data/
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
- [ ] **Water level at overpass** — gauge source for Jervis Bay (MHL, or a BOM gauge with a datum tie to AHD). Next
- [ ] Confirm site 3 (Batemans vs Richmond) after checking lidar tile coverage
- [ ] Atmospheric correction: L2A as supplied, or test whether it matters (one paper found it optional)
- [ ] Sun glint correction method
- [ ] Whether ML enters v1

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
| 27 Sep | Glint geometry: closed form `cos(2ω)=…` **replaced** with the vector derivation | The closed form is wrong off the principal plane (~0.8° at θs=20°, θv=30°, Δφ=90°). Immaterial at S2's near-nadir view, but wrong. Pinned by a grid test against an independent derivation |

## Sources

- NSW Marine LiDAR Topo-Bathy 2018 — https://datasets.seed.nsw.gov.au/dataset/marine-lidar-topo-bathy-2018
- ELVIS — https://elevation.fsdf.org.au/
- IHO S-44 Ed. 6.1.0 — https://iho.int/uploads/user/pubs/standards/s-44/S-44_Edition_6.1.0.pdf
- Sentinel-2 + ICESat-2 SDB with ML (Frontiers, 2023) — https://doi.org/10.3389/feart.2023.1111817
- SDB empirical vs ML in dynamic coastal water (2024) — https://doi.org/10.1080/21664250.2024.2445418
- ICESat-2 Bathymetry Working Group — https://github.com/ICESat2-Bathymetry/Information
- AusSeabed — https://www.ausseabed.gov.au/data
- Sentinel-2 L1C Data Quality Report, Issue 28 (July 2018) — geolocation performance — https://sentinels.copernicus.eu/documents/247904/3897638/Sentinel-2_L1C_Data_Quality_Report/9699703d-556e-407a-a955-65c0c82dfcb5?version=1.2
- Sentinel-2 geometric refinement (GRI) — https://sentinels.copernicus.eu/-/forthcoming-deployment-of-the-copernicus-sentinel-2-products-geometric-refinement
- Cox & Munk (1954), roughness of the sea surface from sun glitter, *JOSA* 44(11) — https://doi.org/10.1364/JOSA.44.000838
- Hersbach et al. (2020), the ERA5 global reanalysis, *QJRMS* 146 — https://doi.org/10.1002/qj.3803
- Open-Meteo historical weather API — https://open-meteo.com/en/docs/historical-weather-api
