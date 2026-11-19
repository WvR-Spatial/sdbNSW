# Satellite-Derived Bathymetry on an Exposed Temperate Coast — project brief

**Status:** Phase 1 gate **passed**. Co-registration against NSW orthoimagery
on land: **E −7.4 ± 1.0, N −1.0 ± 1.1 m** (8 windows agree), applied. Water
level at overpass **−0.392 m AHD, measured** (MHL gauge 216470, 1-minute record,
±20 mm); the provisional image estimate (−0.496) was 0.10 m low, as predicted.
Reference on the scene grid: **93.3 km² usable in 0–20 m**.
**Phase 2: protocol pre-registered** (`8332154`), run at the provisional water
level, then rerun at the measured one as the protocol required. **Gate passed:
pooled RMSE 2.68 m** [95% CI 2.31–3.13], bias −0.42 m, R² 0.69 (inside the bay
2.27 m, open coast 4.69 m); the provisional run gave 2.70 m. Worse than the ~1.8 m clear-water
Stumpf literature, as expected. **Does not meet CATZOC C at any depth**; error
is flat near 2 m RMSE to ~14 m, then climbs as the ratio saturates. SDB reads
~1 m too deep in 0–10 m. **Substrate (pre-registered addendum): reef reads
~1.7 m deeper than sediment at 5–20 m; seagrass makes little difference at
2–10 m; and bare shallow sediment itself reads 2.2 m too deep** — so the
shallow over-reading is mostly not substrate. **Exploratory follow-up:** the
fitting-depth wording was immaterial (95%-only rule: RMSE 2.82 m); the bias
pattern is regression toward the mean plus a ratio curve that bends, and bends
differently on the open coast. Every conclusion survives the measured water
level unchanged.
**v2 (ML), pre-registered** (`c2baa44`) and run once: gradient boosting on
image-only features gives **pooled RMSE 1.88 m** [1.67, 2.13], **0.80 m better
than Stumpf** [0.57, 1.06] on the same folds, and meets **CATZOC C to 3 m**.
Its blocked/random gap (1.060) is seven times Stumpf's, and a model given
coordinates flatters itself badly under a random split (0.74 vs 1.32 m) — the
leakage story, shown on real data. One prediction failed: coordinates still
helped on 2 km blocks, by interpolating the survey itself.
**Phase 4 (three sites): protocol pre-registered 1 Oct**, before any fit at the
new sites. Northern Beaches (Queenscliff–Palm Beach, one survey block) and
Batemans Bay (site 3; Richmond rejected) have native lidar, scenes and
co-registration in hand. Found on the way: **ELVIS
averages any extract that spans more than one survey block** — most of Jervis
Bay's reference is affected, by ~0.13 m RMS, which leaves its results inside
their intervals but compromises its relief strata.
**16 Nov, before any fit:** water levels **measured** — Northern Beaches
+0.501 m AHD (Sydney; Patonga +0.539, so no water-level sensitivity run),
Batemans Bay −0.181 m AHD (Princess Jetty). The image estimate was right at the
surf coast and **0.70 m wrong at the estuary**. **One amendment:** Northern
Beaches is assessed on the **open coast only** — Pittwater and the lagoons are
excluded (21 two-km blocks remain; eligible).
**Phase 4 run, 16 Nov** (*Phase 4 result*): Stumpf **3.03 m** at Northern
Beaches and **2.96 m** at Batemans Bay against Jervis Bay's 2.68; gbm **2.40**
and **2.45** against 1.88, better than Stumpf at every site. **Gate 4 is not
met:** error does not rise with the clarity metric across the three sites —
the site that reads clearest has the largest error. Three predictions held
(two partly on point estimates alone); **one failed** (no turbidity–error
trend inside Batemans Bay, 12 blocks). Within sites, block error rises with block
red reflectance on average (+0.35 [+0.09, +0.59]), but the depth mix of the
blocks confounds that test in opposite directions at the two new sites. An
**exploratory** depth-standardised version (defined and committed before it
was run) gives +0.40 [+0.10, +0.66] with all three sites positive — carried
mainly by Jervis Bay, and a statement about red reflectance, not turbidity.
One computing error was found and corrected after the first run; both results
are reported.
**Updated:** 16 Nov 2026 · **Repo:** `sdbNSW`
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

*Checked against the literature, 19 Nov (`paper/reference_check.md`): the two
paragraphs above overstate. The literature leans to clear water, but temperate
and optically complex sites are published (Irish coast, RMSE 1.6 to 2.4 m;
Aegean; an exposed sandy coast in Japan; the low-energy Adelaide coast). The
1.3 / 1.8 / 2.2 m figures are one study (St Thomas, 80/20 split of unstated
design), not the literature. What holds: no published assessment was found
for the NSW open coast. The paper uses the corrected framing.*

**The deliverable is a number and an envelope, not a map.** Expected answer:
"worse than the literature, and here is the depth-and-clarity boundary where
it fails." That is a finding. A pretty bathymetry raster is not.

**As found (16 Nov).** Worse than the literature at all three sites, and the
*depth* boundary is measured: error is roughly flat to about 15 m and climbs
beyond; Stumpf meets CATZOC C at no depth, and gradient boosting only in the
top 2–3 m at Jervis Bay and Batemans Bay and nowhere on the surf coast. The
*clarity* boundary is **not** established — the three scenes did not deliver
a clarity gradient that this imagery can measure (*Phase 4 result*). The
write-up says so; it does not claim a gradient.

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

*The gradient was the design intent. Phase 4 could not confirm it in these
scenes: the clarity metric sits at the floor of the atmospheric correction and
does not rank the sites reliably. What the three sites do give is three
settings — a sheltered bay, an exposed surf coast, an estuary mouth — under one
pipeline.*

| # | Site | Role | bbox (WGS84) |
|---|---|---|---|
| 1 | Jervis Bay | Best case — sheltered, clear, mixed substrate | **Measured:** 150.6607, −35.1504, 150.8083, −34.9735 (block NSW020502) |
| 2 | Northern Beaches (Queenscliff–Palm Beach) | Exposed, surf-dominated | **Measured:** 151.2460, −33.7867, 151.3570, −33.5918 — the single-date part of block NSW020302 (flown to 18 Sep 2018). **Open coast only** (amendment, 16 Nov): Pittwater and the lagoons inside the box are excluded |
| 3 | Batemans Bay / Clyde mouth | Turbid end — estuarine plume | **Measured:** 150.1592, −35.7700, 150.2906, −35.6870 — block NSW020602 (24 Aug 2018), two native boxes joined |

*Richmond River (Ballina) was screened and rejected on 1 Oct: a small plume
on the seam between two blocks flown 27 days apart (decisions register).*

**Start with Jervis Bay.** If it fails in the clearest water on the coast,
nothing downstream matters and you have spent one weekend finding out.

*As built, site 2 uses the same marine lidar and MHL gauge pipeline as the
other sites; the Narrabeen beach-survey data were not needed.*

## Data

| Source | What | Access | Licence | Commit to repo? |
|---|---|---|---|---|
| [NSW Marine LiDAR Topo-Bathy 2018](https://datasets.seed.nsw.gov.au/dataset/marine-lidar-topo-bathy-2018) | 5 m grid, IHO Order 1b, AHD, shore to 20–40 m, Jul–Dec 2018. **Order inside one survey block's raster**: an extract spanning several is averaged ("Average 16"); check with `scripts/dem_extracts.py` | [ELVIS](https://elevation.fsdf.org.au/) / AODN, manual area select | **CC BY 4.0** | **Release asset, not the repo** (decided 19 Nov) — the four extracts used, unmodified, in one zip with attribution and md5s; unzip at the repo root (`data/README.md`) |
| Sentinel-2 L2A | 10 m multispectral COGs | Earth Search STAC on AWS, anonymous | Copernicus open | No — derived results only |
| MHL tide gauge 216470, Jervis Bay (HMAS Creswell) | Observed water level at overpass. **Received 29 Sep**: `JervisBay.Level1.AHD.Actual.1min.csv`, 6–9 Sep 2018, 1-minute, complete (4,321 samples), supplied in **AHD** (station datum Jervis Bay Port Datum 1958 − 1.070 m), AEST ±2 min, quality code 55 throughout (±20 mm) | MHL data request (form or data-request@mhl.nsw.gov.au) | CC BY 4.0, attribute NSW DCCEEW | Raw file no (`data/raw/tide/`); derived value yes |
| MHL gauges for sites 2–3 | **Received 16 Nov** (requested 1 Oct): Sydney 213470, Patonga 212440 and Princess Jetty 216410, each 22 Aug – 30 Sep 2018 AEST, 1-minute, AHD, quality 55 throughout. Sydney waverider, hourly, 1–30 Sep 2018 (seabed-change context). Datum offsets and tidal planes from MHL's station pages (`data/README.md`, section 5) | As above | As above | Raw files no (`data/raw/MHL/`); derived values yes |
| NSW Imagery (Spatial Services) | Orthophoto windows for co-registration only | ArcGIS REST Export Map, anonymous | Catalogue: CC BY 3.0 AU; Spatial Services excludes images from its CC licence | **No** — cached in `data/raw/ortho/`, never redistributed or drawn |
| ERA5 10 m wind | Scene selection only — glint pre-screen | [Open-Meteo](https://open-meteo.com/) archive API, anonymous | CC BY 4.0 | No — fetched at run time |
| NSW DPI Fisheries *Estuarine Macrophytes* | Seagrass stratum: *Posidonia*, *Zostera*, *Halophila*. Jervis Bay from **Aug 2019** aerial imagery (object-based classification), field-checked **May 2020** (project MEMS). 2,356 seagrass polygons in the bay | ArcGIS REST (`Fisheries_Portal/Estuarine_Macrophytes`), fetched via QGIS | © NSW DPI Fisheries; **CC BY 4.0** as stated by the custodian's service (an IMAS redistribution states CC BY-NC) | No (`data/raw/substrate/`) — derived statistics only |
| DCCEEW *NSW seabed reef extent* | Reef / Unconsolidated, classified from **the same 2018 marine lidar** (plus 2017 subtidal reef mapping). 837 reef, 834 unconsolidated polygons | ArcGIS REST, fetched via QGIS | CC BY 4.0 | No (`data/raw/substrate/`) — derived statistics only |

**The CC BY licence on the reference data is a structural advantage.** Unlike
the Narrabeen survey (registration-gated, non-commercial, un-committable), a
reader can reproduce the validation from this repo and its reference-lidar
release. *(1 Oct plan: commit the subsets. 19 Nov: published as a release
asset instead — 117 MB zipped, beyond git's 100 MB file limit as one file, and
downloaded only by the rare reader who replicates.)*

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
- Error against **exposure**: inside the bay vs open coast within a scene; sea state and turbidity mainly *between* sites (Phase 4 — as run, three sites cannot separate them, and sea state enters only as context: the wave record at Northern Beaches)
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

### Substrate addendum — pre-registered 27 Sep 2026

Written after the layers were fetched and checked for dates, coverage and
alignment, and **before any error was computed by substrate**. The Phase 2
residual map had already been seen; these rules use only the layers' own
classes and round thresholds, nothing tuned to it. Implemented in
`src/sdb/substrate.py`, which reads the Phase 2 out-of-fold residuals
(`sdb.tif`) — no refit.

**Layers.** NSW DPI *Estuarine Macrophytes*, seagrass polygons only; DCCEEW
*seabed reef extent* (Reef / Unconsolidated). Reprojected GDA94 → GDA2020
(PROJ "GDA94 to GDA2020 (1)": 0.46 m E, 1.42 m N here — the same offset found
in the lidar grid's origin), then onto the scene grid translated by the applied
co-registration shift, i.e. the ground each pixel actually sees. Area fractions
at 2 m sub-sampling.

**Pixel classes** — majority rule (≥ 0.5 of the pixel), in this order of precedence:

1. *Posidonia* · 2. *Posidonia/Zostera* · 3. *Zostera/Halophila* — a single mapped type ≥ 0.5
4. seagrass, mixed types — all seagrass together ≥ 0.5, no single type
5. reef — reef ≥ 0.5, seagrass < 0.5
6. **sediment, no seagrass mapped** — unconsolidated ≥ 0.5, seagrass < 0.1, reef < 0.1. **The reference class**
7. edge/mixed — anything else with ≥ 0.1 mapped
8. not mapped

Robustness: the same rules at ≥ 0.9 ("core" pixels), reported alongside.

**Comparison.** Within each depth band of lidar depth, inside the bay: each
class against *sediment, no seagrass mapped* — difference in **bias**
(primary) and in RMSE, with 95% block-bootstrap intervals (2 km blocks, 1,000
draws, both groups resampled together by block). Compared only where the class
has ≥ 1,000 pixels in the band; smaller cells are described, not compared.
Reef additionally inside bay vs open coast.

**Direction stated in advance** (the brief's premise, not the map): dark
substrate reads deeper — a positive bias difference for *Posidonia* and reef,
smaller for *Zostera/Halophila*.

**Known limits, stated before the result.** Seagrass is mapped only to ~10 m
(14 *Posidonia* pixels deeper), so seagrass contrasts exist only in 0–10 m and
the deep reference class may hold unmapped *Halophila*. The map post-dates the
scene by 11 months. Unmapped dark seabed inside the reference class would
shrink a contrast, not create one.

### Substrate result — as pre-registered (addendum `73d02ce`)

`python -m sdb.substrate`, reading the Phase 2 residuals unchanged.
`outputs/substrate_S2A_56HKG_20180907_0_L2A.json`. Inside the bay, bias of each
class minus *sediment, no seagrass mapped*, m, with 95% block-bootstrap
intervals. The core (≥ 0.9) rule moves every figure by 0.2 m or less.

| Band | *Posidonia* | *Posidonia/Zostera* | *Zostera/Halophila* | Reef |
|---|---|---|---|---|
| 0–2 m | **−1.89** [−2.21, −1.13] | n < 1,000 | n < 1,000 | **−2.10** [−2.73, −1.46] |
| 2–5 m | +0.24 [−0.05, +0.52] | +0.10 [−0.54, +0.81] | +1.08 [−1.36, +1.37] | +0.17 [−0.09, +0.44] |
| 5–10 m | +0.12 [−0.26, +0.89] | +0.81 [−0.29, +1.57] | +0.80 [−0.99, +1.25] | **+1.66** [+1.24, +2.13] |
| 10–15 m | — | — | n < 1,000 | **+1.70** [+1.15, +2.72] |
| 15–20 m | — | — | — | **+1.66** [+0.57, +3.27] |

Reef, open coast minus inside bay: +1.03 (2–5 m), −1.02 (5–10), **−3.68**
(10–15), **−5.26** (15–20).

Against the direction stated in advance:

- **Reef — supported at 5–20 m.** Lidar-mapped reef reads ~1.7 m deeper than
  sediment at the same depth, intervals clear of zero.
- ***Posidonia* — not supported at 2–10 m.** +0.1 to +0.2 m, intervals
  include zero. Mixed and *Zostera/Halophila* classes are too small to say.
- **0–2 m — reversed, and the reference class is why.** In absolute terms
  shallow sediment reads **+2.22 m** too deep, *Posidonia* +0.33, reef +0.12.
  The contrast is sediment over-reading, not dark substrate under-reading.

What follows: the Phase 2 shallow over-reading is **mostly not substrate**.
Bare sediment reads +0.8 to +2.2 m too deep through 0–10 m on its own. The
dark patches off the western shore that carry the largest over-reading are
mapped reef, not seagrass. On the open coast, at depth, reef and sediment alike
read 5–6 m too shallow — exposure and water clarity, not substrate.

### Exploratory follow-up — not confirmatory (27 Sep 2026)

Prompted by the registered results, so none of this is a finding in its own
right. Outputs in `outputs/exploratory/`; the registered outputs are untouched.

**E1 — calibration step 2 without the "rises throughout" exception**
(`validate --exploratory rule95`). D_cal becomes 16–18 m (median 18) instead of
20. Pooled RMSE **2.82 m** [2.38, 3.34] against the registered 2.70; bias −0.96
(registered −0.41); depth-balanced RMSE 2.46 (2.48). Bias by band, 0–2 / 2–5 /
5–10 / 10–15 / 15–20 m: +0.98 / +1.09 / +0.47 / −0.51 / −2.83 (registered +0.98 /
+1.23 / +0.82 / +0.12 / −2.10). Substrate contrasts move by 0.1 m or less
(`substrate --tag rule95`). **The exception was not the cause of the shallow
over-reading.** The drafting fault was immaterial; the registered result stands.

**E2 — the ratio against depth** (`…_rule95_ratio_vs_depth.png`). Inside the
bay the median ratio rises almost linearly to ~14 m, then flattens. On the open
coast it flattens from ~8–10 m and lies on a lower curve (1.13 against 1.24 at
20 m). A single site-wide line cannot follow both: that is the open coast's
−5 to −6 m at depth.

**E3 — regression toward the mean** (`scripts/calibration_form_check.py`,
in-sample). The registered form regresses depth on a noisy ratio
(r = 0.89), which pulls every prediction toward mid-depths — shallow water
reads deep, deep water reads shallow — while staying close to unbiased *for a
given predicted depth*: −0.23 / +0.60 / −0.15 m at predicted 0–2 / 2–5 / 5–10 m.
Fitted the other way (ratio on depth, inverted) the pattern by lidar depth
changes sign in the shallows and shrinks at depth (0–2 m +0.86 → −1.22;
15–20 m −1.90 → −0.55), at the cost of pooled RMSE (2.68 → 3.02 m). What
remains after that is the curve's bend.

What it changes: the write-up reports error **both by lidar depth** (how the
method behaves) **and by predicted depth** (what a map user gets) and explains
why they differ. The larger structural problem is two water types under one
line — a v2 question, to be pre-registered as such, not a v1 tweak. Still
unexplained: bare shallow sediment reading 2.2 m deep in 0–2 m.

### Phase 2 result — rerun at the measured water level (−0.392 m AHD), 29 Sep

As the protocol required when the gauge record arrived: `waterlevel` →
`reference` → `validate` → `substrate`, nothing else changed. This is now the
primary result; the provisional run below stays as the record of what was
reported first (and remains in git history, `2906234` / `8ab07db`).

| | Measured water level (primary) | Provisional (−0.496) |
|---|---|---|
| Usable pixels | 932,838 | 937,499 |
| Pooled RMSE, 2 km blocks | **2.68 m** [2.31, 3.13] | 2.70 m [2.32, 3.15] |
| Bias · R² | −0.42 m [−0.95, +0.06] · 0.689 | −0.41 m · 0.688 |
| Depth-balanced RMSE | 2.48 m | 2.48 m |
| Naive split · blocked/naive | 2.66 m · 1.008 | 2.67 m · 1.009 |
| Bias by band, 0–2 / 2–5 / 5–10 / 10–15 / 15–20 m | +0.94 / +1.23 / +0.81 / +0.12 / −2.07 | +0.98 / +1.23 / +0.82 / +0.12 / −2.10 |
| Inside bay / open coast RMSE | 2.27 / 4.69 m | 2.28 / 4.72 m |
| Breakdown depth, CATZOC C and B | 0 m (exceeded from the shallowest bin) | 0 m |
| Saturation depth D_cal | 17–20 m (median 20) | 16–20 m (median 20) |
| Residual correlation range | 4 km (caveat applies) | 4 km |
| Substrate, inside bay, bias vs sediment | *Posidonia* −2.03 / +0.16 / +0.16 m (0–2 / 2–5 / 5–10); reef +1.66 / +1.71 / +1.64 m (5–10 / 10–15 / 15–20) | −1.89 / +0.24 / +0.12; reef +1.66 / +1.70 / +1.66 |

Every figure moves by 0.15 m or less and no conclusion changes — as expected,
since a constant water-level error only shifts the intercept and which pixels
fall in each band. The exploratory runs (E1–E3) were made at the provisional
level and are not rerun: their conclusions depend on shapes, not on a 0.1 m
offset.

### Phase 2 result — Jervis Bay, 7 Sep 2018 (provisional water level −0.496 m AHD)

The pre-registered run, unchanged. Reported first; superseded as the primary
result by the measured-level rerun above.

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
shallow over-reading in coherent patches on the western and northern shelves.
The substrate test (above) found the strongest patches are lidar-mapped reef,
and that bare sediment over-reads too — not the seagrass effect first assumed.
Exposure matters as much as depth — the open coast doubles the error.

Caveats on this run: the residual correlation outlasts the 2 km blocks, so the
bootstrap intervals are probably too narrow (the RMSE itself barely moves with
block size, 2.71 → 2.73 m at 4 km). Within-band R² is negative and not
meaningful — the depth range inside a band is small relative to the error.
Pixels within 50 m of shore carry RMSE of 6–8 m at 2–15 m depth (cliff-foot
rock, few pixels).

### Phase 3 conclusion — blocked vs random validation (Warren, 29 Sep; edited)

> The near-zero gap between our blocked and random validation (1.008) is what
> this model should produce. Stumpf is a simple two-parameter line: it has no
> capacity to overfit to neighbouring raster pixels or to memorise location, so
> spatial leakage cannot inflate its accuracy under a random split. The
> opportunity to leak was there — residuals correlate at 0.70 between adjacent
> pixels and do not fall below 0.1 until 4 km apart — but the model could not
> use it, and the block-size curve barely moves (2.66 m for a random split,
> 2.72 m for 4 km blocks). That makes the Stumpf run a clean control for
> leakage. We expect the need for spatially blocked validation to become
> obvious once we test more flexible models that are capable of that kind of
> spatial memorisation.

## v2 protocol — ML, pre-registered 29 Sep 2026

Committed before any ML model sees real data. The Phase 2 rules carry over:
anything changed after the first run is logged as a deviation and both results
are reported. Implemented in `src/sdb/ml.py`, run through `validate.py
--model`.

**Question.** Does a flexible model beat Stumpf out of sample, and — across the
three sites — does that advantage survive murkier water? At Jervis Bay this
gives the clear-water number.

**Model.** Gradient-boosted regression trees (scikit-learn
`HistGradientBoostingRegressor`), fixed settings, **no tuning**: squared-error
loss, 300 iterations, learning rate 0.1, 31 leaves, at least 100 samples per
leaf, **no early stopping** (it would carve a random validation split out of
each training fold), seed fixed per fold. One model family, chosen for speed
on ~1 M pixels; random forest is not also run — two tries at one question is a
fork, not a check.

**Features — per pixel, from the image only.** ln(1000·ρ) for blue, green, red
and NIR; the Stumpf ratio (blue/green); the blue/red ratio. **No coordinates**,
no neighbourhood or texture, nothing from the lidar or the substrate maps.
Undefined values (a log that is not positive) stay missing; the model handles
them natively.

**Training sample.** As v1: up to 5,000 pixels per 1 m depth bin, drawn inside
each training fold — but over the whole 0–20 m, with no D_cal, since a
nonlinear model can learn the saturation itself.

**Validation.** Identical to Phase 2: the same 2 km blocks and fold seeds 0–9,
so every repeat's folds are exactly v1's; each pixel's prediction is the mean
of its 10 out-of-fold predictions; the naive random split and the block-size
curve (random, 0.5, 1, 2, 4 km); every registered statistic, stratum,
interval and the CATZOC breakdown depth.

**Comparison with v1.** Paired, on identical pixels and folds: ML minus Stumpf
in RMSE, MAE and bias — pooled, by depth band, and inside bay vs open coast —
with 95% block-bootstrap intervals (2 km blocks, both models resampled
together, 1,000 draws). Against the measured-water-level Stumpf run.

**Leakage demonstration — labelled, never a result.** The same model with
easting and northing added (`gbm_xy`), through the same design. It exists to
show on real data what a random split rewards.

**Predictions, stated before the run.**

1. Spectral ML beats Stumpf on the blocked split (lower pooled RMSE; the
   literature suggests ~0.5 m in clear water).
2. Spectral ML's blocked/naive ratio exceeds Stumpf's 1.008 — spectral quirks
   shared by neighbouring pixels are something a flexible model can learn.
3. The coordinate model fails the Phase 3 gate: its naive RMSE is more than 30%
   below its blocked RMSE.
4. On the blocked split the coordinate model does no better than spectral ML —
   location cannot help where the model has not seen the ground.

**Sites 2 and 3.** The same code, settings and features, unchanged.

### v2 result — Jervis Bay (measured water level), 29 Sep

Run once after the protocol commit `c2baa44`, against the measured-level
Stumpf run on byte-identical inputs. `outputs/v2/`.

| | Stumpf (v1) | **gbm (v2 result)** | gbm_xy (leakage demonstration) |
|---|---|---|---|
| Pooled RMSE, 2 km blocks | 2.68 m [2.31, 3.13] | **1.88 m** [1.67, 2.13] | 1.32 m [1.13, 1.52] |
| Bias · R² | −0.42 · 0.69 | −0.12 · 0.85 | −0.07 · 0.93 |
| Depth-balanced RMSE | 2.48 m | 1.53 m | 1.26 m |
| Random split · blocked/random | 2.66 m · 1.008 | 1.78 m · **1.060** | 0.74 m · **1.777** |
| Block-size curve, random → 0.5 → 1 → 2 → 4 km | 2.66 → 2.67 → 2.68 → 2.69 → 2.72 | 1.80 → 1.83 → 1.86 → 1.92 → 2.06 | 0.78 → 0.99 → 1.16 → 1.50 → 1.88 |
| RMSE by band, 0–2 / 2–5 / 5–10 / 10–15 / 15–20 m | 2.11 / 2.67 / 2.07 / 2.06 / 3.46 | 0.55 / 1.32 / 1.88 / 1.80 / 2.11 | 0.77 / 1.54 / 1.47 / 1.15 / 1.36 |
| Inside bay / open coast | 2.27 / 4.69 m | 1.65 / 3.08 m | 1.09 / 2.39 m |
| Breakdown depth, CATZOC C / B | 0 / 0 m | **3 / 2 m** | 2 / 1 m |

**gbm minus Stumpf, paired** (same pixels and folds; 95% block bootstrap):
**−0.80 m** [−1.06, −0.57] pooled; by band −1.57 (0–2 m), −1.35 (2–5),
−0.19 [−0.61, +0.14] (5–10, not distinguishable), −0.26 (10–15), −1.35
(15–20). The advantage is largest exactly where the straight line fails — the
shallows and the saturation zone — and absent where Stumpf's line fits.

**Predictions, as written before the run:**

1. **Held.** Spectral ML beats Stumpf on the blocked split: −0.80 m, larger than
   the ~0.5 m the literature reports for clear water.
2. **Held.** Its blocked/random ratio is 1.060 against Stumpf's 1.008, and its
   block-size curve rises steadily instead of lying flat.
3. **Held.** The coordinate model's random-split RMSE is 44% below its blocked
   RMSE (0.74 vs 1.32 m), far past the 30% gate.
4. **Failed.** The coordinate model did *better* on 2 km blocks than spectral
   ML: 1.32 vs 1.88 m, paired difference −0.57 m [−0.70, −0.41]. Depth is
   smooth over kilometres, so given coordinates the model interpolates the
   surveyed depths of the surrounding training blocks — near a block edge the
   nearest training pixel is metres away. Its block-size curve shows the
   advantage draining away as blocks grow (0.78 m at random, 1.88 at 4 km,
   nearly back to spectral ML's 2.06). That is interpolation of the reference,
   not remote sensing, and it is unavailable where SDB is actually needed.

**What it means.** Blocking limits leakage only in proportion to how block
size compares with the autocorrelation of whatever the model can exploit. For
a model with location, that is the depth field itself, which is correlated
over kilometres. The dependable protection is keeping location out of the
features, which the v2 protocol did. **This is the write-up's methods story in
one table:** the control (Stumpf, flat curve), a legitimate flexible model
(gbm, a modest, rising gap), and a leaky one (gbm_xy, a random split that
flatters it by 44%).

**Caveats.** gbm's block-size curve has not plateaued by 4 km, so the 2 km
figure may be mildly optimistic; at 4 km its advantage over Stumpf is still
0.66 m (2.06 vs 2.72). The headline uses the protocol's mean of 10
out-of-fold predictions per pixel, which for a nonlinear model is a small
ensemble: a single repeat scores 1.92 m. The open coast is still twice the
bay's error under ML, and past ~17 m even gbm saturates.

## Phase 4 protocol — three sites, pre-registered 1 Oct 2026

Committed before any depth model is fitted at Northern Beaches or Batemans
Bay. The Phase 2 and v2 rules carry over: anything changed after the first
run at a new site is logged as a deviation, and both results are reported.

**Question.** How does the error change from the clearest site to the most
turbid, and does the ML advantage survive murkier water? The sites were chosen
to span a clarity gradient; whether the gradient exists in these scenes is
measured, not assumed.

**Same code, same settings.** Stumpf (Phase 2 protocol) and gbm (v2 protocol)
exactly as registered: calibration rule, depth-balanced sample, 2 km blocks
aligned to each scene's grid, 5 folds × 10 repeats with fold seeds 0–9, the
mean of out-of-fold predictions, naive split, block-size curve, correlogram,
block-bootstrap intervals, CATZOC C/B breakdown depth, exclusions by band,
gbm − Stumpf paired, and the `gbm_xy` leakage demonstration. Only the inputs
are site-specific: AOI, reference, scene, co-registration, water level. No
inside-bay stratum at the new sites. Substrate strata only if the layers are
fetched, with the addendum's class rules unchanged, before `validate` runs.

**Site eligibility — from the lidar and capture dates alone.**

1. One capture date across the AOI: one survey block's raster, not mosaicked
   by ELVIS. The reference must pass `scripts/dem_extracts.py check` (≥ 90% of
   underwater cells on the centimetre lattice).
2. At least **15 two-kilometre blocks** holding usable 0–20 m pixels in the
   `reference` mask at the measured water level — three or more per fold.

A site that fails either is reported as ineligible and not fitted.

| Site | AOI (WGS84) | Reference | Capture | 2 km blocks with 0–20 m water, before masking |
|---|---|---|---|---|
| Northern Beaches | 151.2460, −33.7867, 151.3570, −33.5918 | SydneyNorth only, native | 18 Sep 2018 (end of capture) | 34 |
| Batemans Bay | 150.1592, −35.7700, 150.2906, −35.6870 | BatemansBay boxes A ∪ B, native, joined without resampling | 24 Aug 2018 | 21 |

**Scenes — the site-1 rule.** The scene closest to the block's capture date
whose water over the lidar is free of cloud, haze and glint on inspection of
the water-stretched quicklook; Collection-1 preferred when otherwise equal.
Chosen on 1 Oct by inspection only, with no depth data looked at:

- Northern Beaches `S2A_56HLH_20180927_1_L2A`, 9 days after. 17 Sep (1 day):
  cloud over the northern water. 13 Sep (5 days): small cloud and haze patches
  over nearshore water.
- Batemans Bay `S2B_56HKF_20180823_1_L2A`, 1 day before. Water clear of cloud
  (the 3% is over land); wind 0.7 m/s.

Turbidity was not a selection criterion. The quicklooks are stretched per
scene, so their colour cannot rank it, and choosing scenes for it would build
the gradient into the sample.

**Pre-processing — same code.**

- Reflectance as supplied (Sen2Cor L2A: Jervis Bay baseline 00.01, the new
  sites Collection-1), checked against water physics at fetch.
- Co-registration on orthoimagery, with one fallback: window size steps
  2 → 1.5 → 1 km until at least four windows agree; every other threshold
  unchanged. Northern Beaches at 2 km: E −0.43, N −3.47 m (7 windows).
  Batemans Bay: 3 windows at 2 km (insufficient); at 1.5 km E +2.95,
  N −4.91 m (7 windows). Both applied.
- Water level from the MHL gauge at the overpass, as at site 1. Northern
  Beaches: **Sydney (213470) primary, Patonga (212440) cross-check**; their
  difference at the overpass is reported as the water-level uncertainty, and
  above 0.10 m the site is also run at Patonga's level. Batemans Bay: Princess
  Jetty (216410). Not Narrabeen Lagoon (213408D): the lagoon entrance damps
  and delays the tide. Without a gauge record, the image estimate plus Jervis
  Bay's measured bias (+0.104 m), labelled provisional.

**Water clarity — fixed now, from the image, never from the errors.**

- **Metric:** median red reflectance (B04, 665 nm, as supplied) over usable
  pixels whose lidar depth is **10–20 m**. Red is the standard single-band
  turbidity signal (Nechad et al. 2010). The 10 m floor keeps the seabed out:
  pure-water absorption alone sets Kd(red) ≥ 0.41 m⁻¹ (Pope & Fry 1997), so a
  bright sand bottom adds < 0.0002 at 10 m but of order 0.005 at 5 m — as
  large as the turbidity signal itself.
- Computed **per site**, and **per 2 km block** for blocks with ≥ 200 such
  pixels.
- Stated in advance: absolute red reflectance carries each scene's atmospheric
  correction, so site-to-site differences of a few thousandths may be
  atmosphere, not water. Comparisons within a scene share one correction —
  hence the block-level test below.
- Context only, not a metric: the depth the lidar reached (Jervis Bay 42.7,
  Northern Beaches 41.2, Batemans Bay 40.6 m) describes clarity on the survey
  date, not the image date.

**Analysis.**

1. **Site level (n = 3), descriptive.** Pooled and depth-balanced RMSE, bias,
   breakdown depths and gbm − Stumpf, per site, against site clarity. Decision
   gate 4 is read here.
2. **Block level — the inferential test.** Spearman rank correlation between
   block clarity and block RMSE over the same 10–20 m pixels, for Stumpf and
   for gbm, within each site; 95% interval by resampling blocks within site
   (1,000 draws). Across sites, the mean of the within-site correlations, so a
   site-level offset (atmosphere, exposure) cannot create the correlation.
3. **ML across sites.** gbm − Stumpf, paired per site, as in v2.

**Predictions, stated before the run.**

1. Batemans Bay has the highest site clarity metric (the most turbid water).
   If not, the turbid end did not materialise in these scenes, and that is
   reported.
2. Stumpf pooled RMSE at both new sites exceeds Jervis Bay's 2.68 m.
3. At Batemans Bay, Stumpf block RMSE in 10–20 m rises with block red
   reflectance (Spearman > 0, interval excluding 0).
4. gbm beats Stumpf at every site (paired interval excludes 0), by less at
   Batemans Bay than Jervis Bay's 0.80 m.

**Sensitivity runs — labelled, never the result.**

- **Reference averaging.** Northern Beaches rerun with the 1 Oct whole-block
  extract — the same coast, averaged by ELVIS — as the reference, everything
  else identical. It measures on real data what the averaging in Jervis Bay's
  reference does to each statistic.
- **Water level**, at Patonga's level if the gauges differ by more than
  0.10 m.

**Known limits, stated now.**

- Northern Beaches imagery is 9 days after the lidar on a surf coast, and
  sandbars move. The MHL Sydney wave record for 1–28 Sep is reported beside
  the 0–5 m results; no correction is attempted.
- Jervis Bay's reference is mostly ELVIS-averaged (register, 1 Oct); relief
  terciles are not compared across sites.
- Three sites cannot separate clarity from everything else that differs
  between them — exposure, substrate, scene, atmosphere. The within-site block
  test is the one that can.

### Phase 4 amendment, 16 Nov 2026 — Northern Beaches open coast only

Made before any depth model was fitted at Northern Beaches or Batemans Bay,
from the lidar, the habitat maps and the gauge records only. Everything else in
the protocol stands.

**What changes.** At Northern Beaches only water joined to the open sea is
assessed: the lidar water body, 4-connected at the measured water level, that
holds a named open-sea point (151.33, −33.74; ~3 km off Collaroy, 23 m deep).
Other fully-covered water is flagged *not connected to the open sea* (mask bit
64) and leaves every statistic, including the clarity metric and the block
count. Batemans Bay and Jervis Bay are unchanged: each is one water body.

**Why.** The box was drawn from the survey block's single-date window, and
that window also holds **Pittwater** — a sheltered estuary joined to the sea
only through Broken Bay, outside the box — and Narrabeen and Dee Why lagoons,
whose levels are not the sea's. Together they hold 10.7 of the 32.3 km² of
usable water, and 13 of the 34 two-km blocks hold nothing else. The site's registered role is *exposed,
surf-dominated open coast*; with Pittwater in, a third of it would be sheltered
estuary, mixing exposure into the very gradient the within-site block test is
meant to isolate. The lagoons would sit at the wrong water level.

**Effect, checked on the real reference at +0.501 m AHD before any fit.** The
rule removes 11.5 km² of water; **21.6 km² usable in 21 two-km blocks**
remain (32.3 km² and 34 blocks without it), so eligibility (≥ 15) still holds.
About 0.03 km² of near-shore sea at Newport, cut off from the ocean by a
lidar gap in the surf zone, is excluded with it — conservative, and too small
to matter.

**Not changed:** the four predictions, the sensitivity runs, the scene, the
clarity metric's definition. Prediction 2 now refers to the open coast, which
is what the site was registered to be.

### Phase 4 result — three sites, 16 Nov 2026

Run once per site after the amendment commit `2cd2f53` (20:57 AEDT; the first
fit was written at 21:06), with no deviation in any `validate` run.
`outputs/`, `outputs/v2/`, `outputs/sensitivity/`, `outputs/phase4/`.

| | Jervis Bay | Northern Beaches (open coast) | Batemans Bay |
|---|---|---|---|
| Scene · water level (m AHD) | 7 Sep 2018 · −0.392 | 27 Sep 2018 · +0.501 | 23 Aug 2018 · −0.181 |
| Assessed · 2 km blocks | 93.3 km² · 68 | 21.6 km² · 21 | 27.5 km² · 20 |
| **Clarity metric** (median red, 10–20 m) | 0.0037 | 0.0022 | 0.0053 |
| **Stumpf** pooled RMSE | 2.68 m [2.31, 3.13] | **3.03 m** [2.81, 3.22] | **2.96 m** [2.32, 3.52] |
| Stumpf bias · depth-balanced RMSE | −0.42 · 2.48 m | −0.55 · 3.02 m | −0.40 · 2.73 m |
| **gbm** pooled RMSE | 1.88 m [1.67, 2.13] | **2.40 m** [2.20, 2.58] | **2.45 m** [1.86, 2.95] |
| gbm bias · depth-balanced RMSE | −0.12 · 1.53 m | −0.31 · 2.12 m | −0.15 · 2.10 m |
| **gbm − Stumpf**, paired | −0.80 [−1.06, −0.57] | −0.63 [−0.78, −0.50] | −0.51 [−0.90, −0.15] |
| Stumpf RMSE by band, 0–2 / 2–5 / 5–10 / 10–15 / 15–20 m | 2.11 / 2.67 / 2.07 / 2.06 / 3.46 | 3.90 / 2.66 / 2.55 / 2.42 / 3.58 | 2.04 / 2.76 / 2.22 / 2.62 / 4.01 |
| gbm RMSE by band | 0.55 / 1.32 / 1.88 / 1.80 / 2.11 | 1.51 / 1.74 / 2.44 / 2.34 / 2.57 | 0.60 / 2.24 / 2.43 / 2.27 / 2.94 |
| Breakdown depth, CATZOC C / B: Stumpf · gbm | 0 / 0 · 3 / 2 m | 0 / 0 · 0 / 0 m | 0 / 0 · 2 / 1 m |
| Blocked/random: Stumpf · gbm · gbm_xy | 1.008 · 1.060 · 1.777 | 1.010 · 1.069 · 2.936 | 0.982 · 1.159 · 4.260 |
| Residual correlation range | 4 km | 1 km | 2 km |
| **Block test:** Spearman, block red vs block RMSE at 10–20 m — Stumpf | +0.52 [+0.25, +0.71], 48 blocks | +0.70 [+0.32, +0.89], 20 blocks | −0.18 [−0.77, +0.51], 12 blocks |
| — gbm | +0.55 [+0.27, +0.76] | +0.39 [−0.05, +0.74] | −0.00 [−0.63, +0.75] |

**Mean of the within-site correlations** (the registered inferential test):
Stumpf **+0.35** [+0.09, +0.59], gbm **+0.31** [+0.05, +0.58].

**Gate 4 — not met.** Ordered by the clarity metric the sites run Northern
Beaches, Jervis Bay, Batemans Bay; Stumpf RMSE runs 3.03, 2.68, 2.96 and gbm
2.40, 1.88, 2.45. The site that reads clearest has the largest error. As the
gate says, that is the finding.

**Predictions, as written before the run:**

1. **Held, weakly.** Batemans Bay has the highest red reflectance. But the
   three values span 0.003, the size the protocol said atmosphere alone could
   produce, and at Northern Beaches 10% of the 10–20 m pixels sit on the
   product's red floor (0.0001): its red is at the limit of the atmospheric
   correction. The ordering is not established as a property of the water.
2. **Held on the point estimates, as registered** (3.03 and 2.96 against
   2.68). The intervals overlap, most of all at Batemans Bay; this does not
   show the new sites are harder.
3. **Failed.** Inside Batemans Bay, Stumpf block error does not rise with block
   red reflectance: −0.18 [−0.77, +0.51]. Only 12 blocks hold 200 pixels at
   10–20 m, and block red spans a narrow range (0.0043–0.0074), so the test
   could have confirmed only a very strong trend. The block count was knowable
   from the lidar before the run and should have been checked when the
   prediction was written.
4. **Held.** gbm beats Stumpf at every site with intervals clear of zero, by
   less at Batemans Bay (0.51 m) than at Jervis Bay (0.80 m) — the second half
   on point estimates; those two intervals overlap.

**One deviation — both results reported.** The first run of `clarity`
(`outputs/phase4/clarity_run1_superseded.json`) gave Northern Beaches a block
correlation of −0.16 [−0.63, +0.33] (Stumpf) and −0.22 [−0.72, +0.22] (gbm),
and a mean within-site correlation of +0.06 [−0.19, +0.33] and +0.11 [−0.18,
+0.39]. Those were a computing error: 59 of the site's 151,486 clarity pixels
have no red value in the product; the site metric left them out (as written
and tested on 1 Oct), but the block metric did not, so 13 of 20 block medians
became NaN and were then ranked as the largest values. The correction leaves
those pixels out of the block median and RMSE alike; counting them as zero
instead gives the same correlations to four decimals. Jervis Bay, Batemans
Bay, gate 4 and all four predictions are identical in both runs.

**The block test is confounded by depth — read it with that.** Stumpf's error
grows with depth inside the 10–20 m window, and blocks differ in their depth
mix. From the block table in `clarity.json` (Spearman, no intervals):

| | Block mean depth vs Stumpf block RMSE | Block red vs block mean depth |
|---|---|---|
| Jervis Bay | +0.62 | +0.06 |
| Northern Beaches | +0.71 | **+0.70** |
| Batemans Bay | +0.64 | **−0.71** |

At Northern Beaches the redder blocks are the deeper, offshore ones, so depth
alone would produce the +0.70; at Batemans Bay the redder blocks are the
shallower ones near the Clyde, so depth works against any turbidity effect and
may be hiding one. Only at Jervis Bay is the test clean of this. The
registered statistic stands as registered; what it measures is "error rises
with red reflectance", not yet "error rises with turbidity". A depth-adjusted
version would be exploratory and is not run here.

**Leakage demonstration, repeated.** A model given coordinates looks three to
four times better under a random split than on 2 km blocks (Northern Beaches
0.91 vs 2.66 m; Batemans Bay 0.51 vs 2.16 m). On blocks it is worse than
spectral gbm at Northern Beaches (2.66 vs 2.40) and better at Batemans Bay
(2.16 vs 2.45, interval [1.19, 2.99]) — not a registered comparison.

**Substrate, addendum rules unchanged** (whole site; no seagrass class
reaches 1,000 pixels in any depth band). Reef reads deeper than sediment at the same depth at
both new sites, as at Jervis Bay from 5 m down: Northern Beaches +1.84 m
(2–5 m), +2.20 (5–10), +1.27 (10–15), all clear of zero, and +0.03 [−0.58,
+0.57] at 15–20 m; Batemans Bay +3.95 (0–2 m), +3.28, +2.54, +2.79, +2.47,
all clear of zero. The reef bias is now the most replicated result in the
project.

**Sensitivity — reference averaging** (Northern Beaches against the
ELVIS-averaged extract). Pooled RMSE moves by −0.02 m for both models and no
depth band by more than 0.07 m; gbm − Stumpf by 0.002 m. The relief terciles
do move — their edges fall from 0.09 / 0.17 m to 0.06 / 0.11 m and tercile
RMSE shifts by up to 0.17 m. That is the 1 Oct reading of Jervis Bay's
reference, now measured: its pooled results stand, its relief strata do not.

**Northern Beaches shallows.** Stumpf reads 3.1 m too deep at 0–2 m. Of the
open-coast reference water at 0–2 m, 35% is assessed and 65% is flagged as
too bright in the near-infrared, which on this coast is surf. *(Corrected
19 Nov: this line first said 12% assessed, a figure that counted the
Pittwater and lagoon shallows the open-coast rule removes. `validate`'s
exclusion table did not name that rule; it now does.)* The scene is nine days after the lidar with a 1.8 m, 15 s swell
running; no storm intervened (register, 16 Nov). Surf, foam and moved sand
cannot be separated here.

**Descriptive, post hoc (19 Nov) — what the site differences are made of.**
Computed from the committed `validate` and `substrate` records; no new fit,
no interval, not a test. Stumpf only, majority rule.

| | Jervis Bay | Northern Beaches | Batemans Bay |
|---|---|---|---|
| Share of assessed pixels at 15–20 m | 35% | 42% | 27% |
| Depth-balanced RMSE, Stumpf · gbm (equal weight per band) | 2.48 · 1.53 m | 3.02 · 2.12 m | 2.73 · 2.10 m |
| Share of assessed pixels on mapped reef | 10% | **54%** | 20% |
| Stumpf RMSE on sediment only | 2.42 m | 2.58 m | 2.77 m |
| Stumpf RMSE on reef only | 4.63 m | 3.35 m | 3.60 m |

- **Depth mix explains little of the gap.** Northern Beaches has the most deep
  pixels, but with every band weighted equally it still has the largest error.
- **Reef share explains much of it.** On sediment alone the three sites sit
  within 0.35 m of each other; Northern Beaches' pooled error is high because
  more than half its assessed seabed is mapped reef, which reads deeper than
  sediment at every site. Its reef is not worse than Jervis Bay's.
- **Reef and exposure cannot be separated here:** Northern Beaches' reef is
  the exposed rock platforms and headlands. The reef layer says nothing about
  cover (kelp, urchin barren, bare rock).
- The open coast has no mapped seagrass — the macrophyte layer maps estuaries.

**What it means.** Stumpf lands at 2.7–3.0 m at all three sites with
overlapping intervals. gbm lands at 1.9–2.5 m and is distinguishably worse on
the open coast than in Jervis Bay (2.40 [2.20, 2.58] against 1.88 [1.67,
2.13]). Nothing here shows clarity driving the differences between sites:
the metric is too close to the atmospheric correction's floor to rank them,
and the drivers that are measured inside sites are depth, reef and exposure.
The ML advantage survives at every site and is smallest at Batemans Bay, as
predicted, though not separably. The question the phase asked — does error
track clarity — is answered "not across these sites, and not shown within
them".

### Exploratory addendum — depth-standardised block test, defined 16 Nov 2026

**Not confirmatory.** Defined after the registered Phase 4 result was seen,
and after one rough look at a partial rank correlation on block mean depth
(+0.61 Jervis Bay, +0.40 Northern Beaches, +0.53 Batemans Bay; Stumpf, no
intervals). It cannot change gate 4, a prediction or the registered block
test, whatever it shows. This definition is committed before the analysis is
run on the real data; its code was tested on synthetic data only.

**Why.** The registered test asks whether redder blocks have larger RMSE. But
RMSE grows with depth inside 10–20 m, blocks differ in depth mix, and the mix
is tied to block red in opposite directions at the two new sites (*Phase 4
result*). The question that matters is whether a redder block errs more *than
its depths alone predict*.

**Definition.**

- Same pixels and blocks as the registered test: assessed, lidar depth
  10–20 m, red present; 2 km blocks with at least 200 such pixels.
- Per site and model, squared error is tallied in **1 m depth bins**.
- **Expected** squared error of a block: each of its pixels is given the mean
  squared error, in that pixel's depth bin, of the selected pixels in the
  site's *other* blocks — the block is left out of its own standard. A bin in
  which the other blocks hold fewer than 30 pixels gives no expectation; the
  block's pixels in it are left out of both sums, and a block left with fewer
  than 200 pixels is dropped.
- **Depth-standardised error** = √(observed ÷ expected). 1 means the block
  errs as its depths predict; above 1, worse.
- **Statistic:** Spearman between block median red and depth-standardised
  error, within each site, for Stumpf and gbm; 95% interval from resampling
  blocks (1,000 draws, seed 18; the standardised errors are not recomputed
  within a draw); across sites, the mean of the within-site correlations.
- **Reported with it:** the correlation of block mean depth with the
  standardised error (near zero if the standardisation has done its job) and
  the registered correlation over the same blocks.

**How it will be read — stated now.** A link between red reflectance and error
beyond depth is *supported* only if the across-site mean's interval lies above
zero **and** no site's own correlation is negative. Otherwise the registered
+0.35 is *not distinguishable from depth mix*. Either way it remains a
statement about red reflectance, not turbidity: reef, exposure and glint vary
with location too, and Northern Beaches' red is near the correction's floor.

`python -m sdb.clarity --depth-adjusted --run …` writes
`outputs/exploratory/clarity_depth_adjusted.json` and one figure stamped
EXPLORATORY; `outputs/phase4/` is not touched.

### Exploratory result — depth-standardised block test (addendum `884dce1`), 16 Nov

Run once, a minute after the addendum commit, with no deviation; no block
dropped and no pixel left out. `outputs/exploratory/`.

| Stumpf | Registered: red vs RMSE | **Red vs depth-standardised error** | Depth vs RMSE → depth vs standardised error |
|---|---|---|---|
| Jervis Bay (48 blocks) | +0.52 | **+0.55** [+0.29, +0.74] | +0.62 → +0.16 |
| Northern Beaches (20) | +0.70 | **+0.22** [−0.31, +0.75] | +0.71 → +0.09 |
| Batemans Bay (12) | −0.18 | **+0.44** [−0.30, +0.96] | +0.64 → −0.22 |
| **Mean of within-site** | +0.35 [+0.09, +0.59] | **+0.40** [+0.10, +0.66] | |

gbm: +0.58 [+0.31, +0.77], +0.14 [−0.40, +0.63], +0.29 [−0.45, +0.83]; mean
+0.34 [+0.02, +0.60].

**Read by the rule written beforehand: supported, for both models** — the
mean's interval lies above zero and no site is negative.

**What it shows.**

- The standardisation did its job: the tie between block depth and block
  error falls from +0.6–0.7 to between −0.22 and +0.16.
- The registered test's disagreement between sites was depth mix, in the two
  directions the confound predicted: Northern Beaches' +0.70 shrinks to +0.22,
  and Batemans Bay's −0.18 becomes +0.44. The sites now agree in sign, and the
  mean barely moves (+0.35 → +0.40).

**What it does not show.**

- Only Jervis Bay's own interval excludes zero. Northern Beaches and Batemans
  Bay, taken alone, show nothing; gbm's pooled lower bound is +0.02.
- It is exploratory: defined after the registered result and a rough look
  (+0.61, +0.40, +0.53 by partial correlation — the same direction, smaller).
- It is about red reflectance. Foam, surface roughness and exposure raise red
  too, and they vary with place just as turbidity does. Prediction 3 still
  failed, and gate 4 is still not met.

**The sentence the write-up may use:** within a scene, blocks with higher red
reflectance tend to have larger errors than their depths predict (exploratory;
mean rank correlation +0.40 [+0.10, +0.66] across three sites, clear at
Jervis Bay alone). It is a lead for a registered test on new scenes, not a
finding about turbidity.

### Phase 4 conclusion (Warren's draft of 19 Nov, revised after review)

Gate 4 was not met. Ranked by the clarity metric, the sites run Northern
Beaches, Jervis Bay, Batemans Bay, yet the error of satellite-derived
bathymetry (SDB) does not follow that order: the site that reads clearest
returns the largest Stumpf error (3.03 m), and its gradient-boosting (GBM)
error is indistinguishable from that of the most turbid site (2.40 m against
2.45 m). Two qualifications govern how far this can be taken. The Stumpf
errors overlap within their 95% intervals (2.68 [2.31, 3.13], 3.03 [2.81,
3.22] and 2.96 [2.32, 3.52] m), so the only resolved contrast between sites is
GBM's, Jervis Bay (1.88 [1.67, 2.13] m) against Northern Beaches (2.40 [2.20,
2.58] m). And the clarity metric spans only 0.003 in red reflectance, within
the margin the protocol attributed in advance to differences in atmospheric
correction, with 10% of Northern Beaches' 10–20 m pixels at the lowest value
the product records. The result therefore shows that no monotonic
relationship was observed, and that this imagery could not establish a
clarity gradient between the sites. It does not show that clarity is
immaterial. Each site is also represented by a single scene, so a difference
between sites is equally a difference in acquisition date, sea state, sun
geometry and atmosphere. That the two models agree rules out an artefact of
either model, since they share every pixel and the same reference, but not an
artefact of the scene.

The composition of the errors points to the seabed rather than the water
column. Depth distribution accounts for little: Northern Beaches holds the
largest share of pixels between 15 and 20 m, yet with each depth band weighted
equally it still has the largest Stumpf error (3.02 m, against 2.48 m at
Jervis Bay and 2.73 m at Batemans Bay). Substrate accounts for much more.
Mapped reef makes up 54% of the assessed seabed at Northern Beaches, against
10% at Jervis Bay and 20% at Batemans Bay, and in most depth bands reef reads
deeper than sediment at all three sites. On sediment alone the three Stumpf
errors lie within 0.35 m of one another (2.42, 2.58 and 2.77 m). Northern
Beaches' reef is no worse than Jervis Bay's (3.35 m against 4.63 m); the site
simply has far more of it. This breakdown is descriptive and post hoc rather
than a test, and on this coast it cannot be disentangled from exposure,
because all of Northern Beaches' reef lies on an open, swell-dominated
shoreline. The reef layer records presence, not cover, so whether kelp,
urchin barren or bare rock produces the bias remains open. The open coast
carries no mapped seagrass: what the original box contained lies in Pittwater
and the coastal lagoons, both excluded.

Exposure leaves a separate mark in the shallows. At Northern Beaches the
Stumpf error between 0 and 2 m is 3.90 m, against 2.11 m at Jervis Bay; 65%
of the open-coast water in that band was too bright in the near-infrared to
assess, which on this coast means surf; and a 1.8 m swell
at a 15 s period was running at the overpass. The scene was acquired nine
days after the lidar survey, with ordinary swell in between, so within the
surf zone the lidar may not describe the seabed the satellite observed. These
effects are confined to shallow water, however. The bands from 0 to 5 m hold
only 12% of Northern Beaches' assessed pixels, and GBM performs worse there
than at Jervis Bay in every depth band, so surf and seabed change cannot
account for the whole difference.

Within each scene the evidence leans the other way. An exploratory analysis,
committed before it was run but defined after the registered result had been
seen, compares each 2 km block's error with what its depth mix predicts.
Blocks with higher red reflectance err more than their depths alone would
suggest: the mean within-site rank correlation is +0.40 [+0.10, +0.66], with
the same sign at all three sites, although only Jervis Bay is resolved on its
own. Red reflectance also rises with foam and glint, so this is a lead
concerning red reflectance rather than evidence about turbidity, and it
warrants a registered test on further scenes.

For site selection on this coast, the practical implication is that reef
cover and exposure merit as much scrutiny at the screening stage as water
clarity. Three sites with one scene each cannot rank those factors against
one another; that requires several scenes per site, so that sea state and
atmosphere vary while the seabed stays fixed.

## Error budget

| Term | Magnitude | Note |
|---|---|---|
| Reference (IHO Order 1b) | ±0.52 m at 10 m, ±0.56 m at 20 m | TVU = √(a² + (b·d)²), a=0.5, b=0.013, 95% |
| Reference horizontal | 5 m + 5% depth ≈ 5.5 m | Sub-pixel at 10 m S2 |
| Expected SDB error | 1.3–2.2 m clear water; unknown here | The quantity being measured |
| Water level correction | **−0.392 m AHD measured**: gauge ±20 mm (code 55), timing ±2 min × 0.12 m/h ≈ ±4 mm, 1-minute noise ~1 cm (11-minute mean −0.394). The provisional image estimate was −0.496 | A constant error is absorbed by the Stumpf intercept; it moves depth bands, masks and anything reported against AHD. Moving from −0.496 to −0.392 changed pooled RMSE by 0.02 m |
| Water level, sites 2–3 | Northern Beaches **+0.501 m AHD** (Sydney); Patonga reads 0.04 m higher — taken as the uncertainty. Batemans Bay **−0.181 m AHD** (Princess Jetty, ~3 km up the Clyde: ~22 min tidal lag ≈ 0.04 m at the overpass) | Same role as at Jervis Bay: a constant is absorbed by the fit; it moves bands and masks. The image estimate was 0.01 m off at Northern Beaches and **0.70 m off** at Batemans Bay |
| Co-registration, sites 2–3 | Northern Beaches E −0.43 ± 0.32, N −3.47 ± 0.14 m; Batemans Bay E +2.95 ± 0.62, N −4.91 ± 0.09 m (1.5 km windows); both measured on 7 windows and removed | Standard errors under 1 m: minor, as at Jervis Bay |
| **Clarity metric** | Site medians 0.0022–0.0053 in red reflectance; the protocol's own caveat is "a few thousandths may be atmosphere"; 10% of Northern Beaches' pixels sit on the product floor (0.0001) | The metric cannot rank sites. Within a scene it ranks blocks, but block depth mix confounds the registered test (*Phase 4 result*) |
| **Co-registration** | 7.5 m measured and removed; residual ±1.0 m E, ±1.1 m N (1σ), plus ~1.5 m possible datum offset in the reference imagery | On a 1:10 seabed slope 1 m of misregistration is 0.1 m of depth. Now a minor term |
| Sub-pixel relief | Median 0.01–0.09 m, p90 ≤ 0.24 m by depth band | Std of the 5 m cells inside each 10 m pixel. Minor except on reef edges; kept for stratification. **At Jervis Bay suppressed by the ELVIS averaging below** |
| **Reference processing (ELVIS averaging)** | Jervis Bay only: 0.13 m RMS at 10 m in 0–20 m (+0.05 m mean, p99 0.52 m), surface displaced 2.5 m S and 2.5 m W — measured on the averaged vs native Northern Beaches extracts | Moves Jervis Bay's RMSE by < 0.01 m in quadrature. Phase 4 measures its effect on every statistic directly. Sites 2 and 3 are native |
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

Batemans Bay pairs as closely (scene 23 Aug, block 24 Aug). Northern Beaches
does not: the nearest clean scene is 27 Sep, 9 days after its block was
finished, on a surf coast. Its 0–5 m results carry that, with the wave record
between the two dates reported beside them.

## Decision gates

| Phase | Gate | Fail action |
|---|---|---|
| 1 | Seabed visibly resolvable in the scene; lidar and imagery align | Try another scene/date before touching the method |
| 2 | Site 1 RMSE within ~2× literature (< ~4 m) | Diagnose water level, glint, atmospheric correction — do not tune blindly |
| 3 | Blocked-CV result holds within ~30% of naive split | If not, the naive number was the illusion; report both |
| 4 | Sites 2 and 3 produce a monotonic error–clarity relationship | If not, that is itself the finding — report it. **Not met, 16 Nov** (*Phase 4 result*) |

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
│       ├── ml.py               # v2: gradient boosting on per-pixel image features
│       ├── substrate.py        # substrate strata for the errors (pre-registered addendum)
│       ├── validate.py         # blocked CV, statistics, stratification
│       ├── clarity.py          # Phase 4: clarity against error, within and across sites
│       └── viz.py              # one palette, one set of chrome
├── tests/                      # every statistic against an analytic answer
├── scripts/                    # one-off provenance checks (network), not pipeline;
│                               #   dem_extracts.py: native-value check, exact join of ELVIS boxes
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

Draft, revised 16 Nov to claim only what was measured: *"Independent accuracy
assessment of satellite-derived bathymetry at three NSW coastal sites — a
sheltered bay, an exposed surf coast and an estuary mouth — against IHO Order
1b airborne lidar, under pre-registered protocols and spatially blocked
validation. RMSE 2.7–3.0 m for the band-ratio method and 1.9–2.5 m for
gradient boosting over 0–20 m; reports error by depth band, substrate and
exposure, and the depth at which each method breaks down."*
Tags: Sentinel-2 · STAC/COG · Accuracy Assessment · Bathymetry · Python

*The 1 Oct draft said "spanning a water-clarity gradient" and "sea state".
Neither survived: the gradient was not measurable in these scenes, and sea
state was never a stratum, only context.*

Deliverable: GitHub Pages page with the error figures and a small
SDB-versus-lidar comparison, plus the repo. Limitations panel above results.

## Write-up plan (proposed 16 Nov; decisions 19 Nov)

**Standard:** a short conference paper (the model is a 6–8 page industry
paper, e.g. *Coasts & Ports* or a hydrographic society conference) that a
non-specialist can also get the answer from in a minute. One document, three
layers; each layer complete without the next.

1. **For everyone (top of the page, ~60 seconds).** A plain-language summary
   of ≤ 150 words with no undefined term; three numbers at most, each with
   what it means in practice; one figure (satellite depth against lidar depth
   at one site); and the limitations panel — Warren's, in plain words, above
   the results.
2. **The paper.** Structured abstract (≤ 250 words: background, methods,
   results, conclusion) · Introduction and the gap · Study sites and data ·
   Methods (pre-registration, pipeline, blocked validation, statistics) ·
   Results · Discussion (against the literature; what drives the error) ·
   Limitations · Conclusions · Data and code availability · Author
   contributions and AI assistance · References. About 3,500 words, 5–6
   figures, 3 tables.
3. **The repository.** Protocols, decisions register, every output. Cited from
   the paper as supplementary material, not repeated in it.

**Rules the paper keeps.**

- Every number carries its interval and its unit of replication (blocks, not
  pixels); one scene per site is stated as the main limit on generality.
- Confirmatory and exploratory results are never mixed: a *predictions
  scorecard* table (every registered prediction and gate, held or failed)
  and a *deviations and corrections* table (the rerun at the measured water
  level, the open-coast amendment, the `clarity` correction).
- Failures are reported at the same size as successes: gate 4, prediction 3,
  v2 prediction 4.
- Literature numbers are quoted with their validation design; every reference
  is checked against its source before it is cited.
- Figures: one palette, colour-blind safe, assertion-style captions (the
  caption states what the figure shows), alt text, regenerated in one pass
  with a single font.
- **House style (Warren, 19 Nov), for the paper, the page and every repo
  document:** Australian spelling; no em-dashes; en-dashes only in numeric
  ranges; specific words over stock phrases; no inflated claims about the
  importance of a method or result; a wide vocabulary used precisely. Avoid
  the usual tells: "delve", "crucial", "pivotal", "robust" outside its
  statistical sense, "landscape", "leverage", "showcase", "seamless",
  "underscore", "it is worth noting", "not only … but also", triads for
  rhythm, and closing sentences that restate the paragraph.

**Tools for figures (decided 19 Nov).** Charts in matplotlib, generated by a
script from the committed outputs, so every figure is reproducible and shares
one style. Maps (F1 locator, F6 residual map) from QGIS through the QGIS MCP
server already connected, driven by a committed PyQGIS script rather than by
hand, with the lidar's own hillshade as the base so that no unlicensed
imagery appears. No further MCP servers are needed; ArcGIS and Excel would add
licence dependence and no reproducibility.

**Figures and tables, provisional.** F1 sites and what SDB measures · F2
error by depth, three sites × two methods, with the CATZOC C allowance · F3
blocked against random validation (the leakage demonstration) · F4 reef
against sediment at three sites · F5 red reflectance against block error,
registered beside exploratory · F6 residual map, one site. T1 sites, scenes,
pairing and water levels · T2 results with intervals · T3 predictions
scorecard.

**Order of work.** Warren: Phase 4 conclusion, limitations panel, lidar
hosting, the decisions below. Claude: reference check, figure pass, outline
with word budgets for approval, then the draft.

**Decisions (19 Nov).**

- **Format:** a web page and a conference-layout PDF, built from one source.
- **Titles.** Paper and PDF: *Satellite-derived bathymetry on an exposed
  temperate coast: a pre-registered accuracy assessment against airborne
  lidar at three New South Wales sites.* Portfolio page and card: *How deep
  can a satellite see off the NSW coast?*, with the answer beneath it. The
  project began as a comparison with tropical studies; as completed, the
  tropical literature is the benchmark and the gap, not the subject. Any
  comparison with it must account for validation design, since much of it
  used random or unreported splits, which this project shows can flatter a
  model.
- **Phase 4 conclusion:** Warren's draft, revised after review on his
  instruction (*Phase 4 conclusion*).
- **AI workflow:** presented as Warren's use of current agentic tools to run
  a larger study in less time, with the safeguards that made it checkable;
  not as co-authorship. Draft statements below.

**How it was built: AI-assisted workflow (draft for Warren's approval, 19 Nov).**
The emphasis is the workflow and its safeguards, not authorship. Two
lengths, from the same facts.

*Paper version (Data, code and workflow statement):*

> This study was planned and run by the author with Claude (Anthropic) as an
> agentic assistant. The agent worked in a cloud workspace connected to the
> author's workstation through Model Context Protocol (MCP) servers, which
> gave it a shell and file access within the project folder and access to a
> local QGIS instance for querying web map services. It wrote most of the
> code and its 281 automated tests, parsed the data services, and drafted
> protocol and documentation text. The author framed the question, chose the
> sites, obtained the lidar and gauge records, checked image registration
> visually in QGIS, made each methodological decision, ran every analysis
> step and reviewed its output, and wrote the interpretation, which was
> revised after review against the outputs. Each protocol was committed
> before any model was fitted, and every change and error, the agent's
> included, is logged with its date in the repository's decisions register.

*Web page and README version ("How this was built"):*

> I built this part-time over about eight weeks, a few of them spent waiting
> for tide-gauge records, using an AI agent as the main means
> of production and organising the work so that everything it produced could
> be checked.
>
> The agent, Claude, ran in a cloud workspace and reached my workstation
> through MCP connectors: a shell and file bridge into the project folder,
> and a QGIS server that let it query ArcGIS REST services and inspect
> layers. It wrote most of the 9,500 lines of Python, including 281 tests,
> and drafted the protocols and documentation. I set the question and the
> sites, ordered the lidar and requested the tide records, checked the image
> registration by eye in QGIS, made each methodological decision, ran every
> step on my own machine and wrote the interpretation.
>
> Three practices made the output checkable. Each analysis was
> pre-registered, so its protocol was committed before any model saw the
> reference data. Every change is logged with its reason, including the
> agent's mistakes: a site boundary that silently took in an estuary, a rule
> that passed its tests and failed on real data, and a sorting fault that
> reversed one site's result. And every file moved between machines was
> verified by checksum at its destination.
>
> The outcome is a study of wider scope than I would have attempted alone in
> the same time, with a record of how each part was made.

*Confirmed 19 Nov:* part-time, about eight weeks (27 Sep to 19 Nov), including
the wait for the MHL records. The line and test counts are refreshed at
publication.

**Repository documents for readers (at the final draft).** The brief, build
guide and data README are working records written as a dialogue ("→ YOU",
"→ CLAUDE", "my error"). For publication they become documents for a reader:

- `PROJECT_BRIEF.md` becomes a project record: question, sites, data, methods,
  results and the decisions register, in the house style and in the third
  person or Warren's first person.
- Each registered protocol is frozen verbatim in `docs/protocols/`, with the
  commit that registered it, so that editing the readable record cannot alter
  what was pre-registered. The code's commit lookups search history and are
  unaffected.
- The decisions register keeps every entry, date and substance, including the
  errors; only the voice changes. The working version stays in git history.
- `BUILD_GUIDE.md` becomes a reproduction guide: install, fetch, run, with
  expected outputs.

### Limitations (Warren's draft of 19 Nov, revised after review)

**Layer 1: the plain panel, above the results.**

> **What these results do not tell you**
>
> - **They are not for navigation.** Satellite depth estimates are not a
>   hydrographic survey. Even the lidar used here as ground truth is published
>   with a warning against navigation use without further processing. The
>   lidar is specified to within about half a metre; the satellite estimates
>   are typically 2 to 3 m out.
> - **Each site was seen on one day.** Every site was assessed on a single
>   cloud-free image from late winter or early spring 2018. Other days, with
>   different tides, swell or river flows, could give different results.
> - **Water clarity could not be isolated.** On these dates the satellite's
>   measure of clarity sat too close to its own noise floor to rank the three
>   sites, and with only three sites, clarity cannot be separated from reef
>   cover, wave exposure or the atmosphere on the day.
> - **The surf zone is largely missing.** Breaking waves and foam are removed
>   before any depth is estimated. At Northern Beaches that removed about two
>   thirds of the water shallower than 2 m, so results there describe the
>   calmer patches only.
> - **Depths to 20 m, at three sites.** Nothing here speaks to deeper water or
>   to other coasts.

**Layer 2: the paper's Limitations section.**

*Single scene per site.* Each site is represented by one Sentinel-2
acquisition (23 August, 7 September and 27 September 2018). The results
describe the methods under those days' tide, swell, sun geometry and
atmosphere, not across seasons, floods or river plumes, and any difference
between sites is equally a difference between scenes.

*Clarity not isolated.* The clarity metric (median red reflectance at
10–20 m) spans 0.0022 to 0.0053 across the sites, within the margin
attributed in advance to differences in atmospheric correction, and 10% of
Northern Beaches' 10–20 m pixels sit at the product's minimum value. With
three sites, clarity cannot be separated from reef cover, exposure or
scene-to-scene atmospheric differences.

*Shallow water.* Pixels too bright in the near-infrared are removed before
any depth is estimated. In the 0–2 m band this removes 65% of Northern
Beaches' open-coast water, where the cause is surf, 39% at Jervis Bay and 18%
at Batemans Bay, where glint on wavelets or very shallow bright sand may
also be responsible. Results in the top 2 m describe the remaining pixels only.

*Seabed change.* Jervis Bay and Batemans Bay were imaged one day before their
lidar surveys, so seabed change is unlikely to matter. Northern Beaches'
nearest clear image followed its survey by nine days on an active surf coast,
with a 1.8 m, 15 s swell at the overpass though no storm in between; in the
top 5 m, surf and moved sand cannot be separated.

*Imagery and models.* All runs use standard Sentinel-2 Level-2A surface
reflectance, with no sun-glint correction, no water-specific atmospheric
correction and no model tuning. Purpose-built processing and tuned or
substrate-aware models may reduce the error; none would remove the loss of
signal with depth.

*Reference uncertainty.* The lidar is specified to IHO Order 1b, about
±0.5 m at 95% confidence over 0–20 m. That is small against the satellite
error overall, but comparable to gradient boosting's error in the top 2 m at
Jervis Bay and Batemans Bay (0.55 and 0.60 m). Jervis Bay's lidar extract was
also averaged by the supplying portal where it crossed survey blocks
(about 0.13 m RMS). The same comparison at Northern Beaches moved pooled RMSE
by 0.02 m, so the headline figures stand, but Jervis Bay's breakdown by
seabed roughness is unreliable.

*Spatial dependence.* Residual errors stay correlated over 4 km at Jervis
Bay, beyond the 2 km validation blocks, so its intervals may be somewhat
narrow. Gradient boosting's error also grows with block size, from 1.92 to
2.06 m at Jervis Bay and from 2.53 to 2.81 m at Batemans Bay between 2 and
4 km blocks, while Stumpf's barely changes; its 2 km figures are best read as
lower bounds. It still outperforms Stumpf at every site on 4 km blocks.

*Scope.* Northern Beaches is assessed on the open coast only, by a
pre-fit amendment that excluded Pittwater and the coastal lagoons. All
results are for 0–20 m. The within-site analysis adjusted for depth is
exploratory: it was defined after the registered result had been seen.

## Open decisions

- [x] Repo name `sdbNSW`
- [x] Jervis Bay scene — `S2A_56HKG_20180907_0_L2A` (see decisions register)
- [x] **Observed water level at overpass** — MHL Jervis Bay (216470): −0.392 m AHD at 10:02:37 AEST, 7 Sep 2018
- [x] Site 3 — **Batemans Bay**; Richmond rejected (register, 1 Oct)
- [x] Phase 4 protocol — pre-registered 1 Oct (*Phase 4 protocol*)
- [x] MHL gauge records for sites 2–3 and the Sydney wave record — received 16 Nov; water levels measured
- [x] Substrate layers for sites 2–3 — fetched 16 Nov, before any `validate` run
- [x] Northern Beaches extent — **open coast only** (*Phase 4 amendment, 16 Nov*)
- [x] Phase 4 run — 16 Nov (*Phase 4 result*); gate 4 not met; one deviation, both results kept
- [x] Depth-standardised block test — exploratory addendum `884dce1`, run 16 Nov (*Exploratory result*): supported by its own rule, carried mainly by Jervis Bay
- [x] Reference lidar as a GitHub release asset: published 19 Nov as `reference-lidar-2018` (zip md5 `1170eddb15480750a0adf5da849d0616`, sha256 `995b70840fc4d133bf6c6ccb18fce22c8a60c8bb915cfa627501d22e4f9f5bce`)
- [ ] **Make the repository public before the page goes live.** On 19 Nov the GitHub API returned 404 for the repo and its releases without authentication, so neither is visible to a reader yet
- [x] Phase 4 conclusion: Warren's draft, revised after review (19 Nov)
- [x] AI workflow statement, conclusion and limitations signed off (19 Nov)
- [x] Reference check (`paper/reference_check.md`, `paper/references.bib`); two small items to confirm before final
- [ ] **Paper outline** (`paper/outline.md`): approve, and give the author line and PDF layout
- [ ] Limitations: Warren's draft of 19 Nov, revised after review into a plain panel and a paper section (*Limitations*); awaiting approval
- [ ] `README.md` (result first), `site/` page, portfolio card with its number
- [x] Atmospheric correction — **L2A as supplied** for v1; ACOLITE only as diagnosis if the gate fails
- [x] Sun glint correction — **none** for v1 (register, 27 Sep)
- [x] Whether ML enters v1 — **no**; v2 pre-registered 29 Sep (*v2 protocol*): gradient boosting, spectral features only, same folds, paired against Stumpf
- [x] Breakdown threshold — **CATZOC C** (2.0 m + 5% of depth, 95%); CATZOC B alongside
- [x] **Substrate layers** — NSW DPI *Estuarine Macrophytes* (seagrass) and DCCEEW *seabed reef extent* (lidar-derived), fetched and checked; class rules pre-registered (*Substrate addendum*)

## Decisions register

Dated, including reversals. This is what turns a folder of scripts into a
defensible piece of work.

| Date | Decision | Why |
|---|---|---|
| 27 Sep | Reference ordered in native **GDA2020 / MGA 56 (EPSG:7856)** | Any reprojection resamples the reference surface. GDA2020 also sits within centimetres of the ITRF frame Sentinel-2 uses; GDA94 is ~1.8 m off |
| 27 Sep | Delivered DEM verified | 5 m, AHD, IHO Order 1b per supplier metadata. −42.7 to +166.6 m. **95.6 km² in 0–20 m** (~955k cells at 10 m). Mosaic of blocks flown 8 and 9 Sep 2018. Laser reached 42.7 m — top of the stated 20–40 m range, so the water is clear |
| 27 Sep | **Aggregate lidar onto the S2 10 m grid**; never upsample imagery | Upsampling invents spatial detail and flatters the error. Aggregating four 5 m cells also reduces reference noise |
| 27 Sep | AOI straddles MGRS **56HKG / 56HLG**, no common date. 56HKG covers 100%; 56HLG only the eastern part. **All 56HLG scenes rejected** — including the same-day 8 Sep scene | A scene covering part of the bay cannot validate the bay. Partial coverage is a hard rejection, not a score penalty |
| 27 Sep | Duplicate processings collapsed; prefer baseline **05.00** (Collection-1) | Same datatake published twice. Collection-1 is consistently reprocessed. Its −0.1 BOA offset is applied at fetch and verified against water physics (red/NIR medians near zero). **Corrected 1 Oct** (below): on Earth Search the offset is already in Collection-1 pixels |
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
| 27 Sep | **Substrate layers fetched and checked** (via QGIS; 5,937 macrophyte, 1,671 reef-extent, 1,131 reef-source polygons in the lidar extent; `data/raw/substrate/provenance.json`). Alignment: *Posidonia* fringes and *Zostera* shoals in the southern bay, and the lidar reef outcrops off the western shore, match their image edges to about a pixel. Coverage inside the bay, usable pixels at ≥ 0.5: *Posidonia* 8,935 / 21,585 / 17,055 in 0–2 / 2–5 / 5–10 m; reef 39,306 across all depths; sediment with no seagrass mapped 711,336 | Two layers together explain the dark seabed visible in the image: the dark patches off Huskisson that the seagrass map lacks are lidar-mapped reef. Seagrass mapping stops at ~10 m. Open coast: no seagrass mapped, 45% reef. The custodian's service states CC BY 4.0 (an IMAS copy says CC BY-NC); the custodian's statement is used. The reef service's layer descriptions are copied from a Wollongong multibeam dataset — the per-polygon Source field is the reliable one |
| 27 Sep | **Substrate comparison run once, as registered** (addendum committed in `73d02ce` first). Reef +1.7 m at 5–20 m; *Posidonia* ~0 at 2–10 m; 0–2 m reversed | The pre-stated direction held for reef and failed for seagrass; reported as found. Correction to the Phase 2 reading above: I attributed the shallow over-reading to "where seagrass is expected". The overlay shows those patches are reef, and bare sediment over-reads on its own — the likelier source is the calibration (a straight line through a saturating relationship, fitted to 20 m in 46 of 50 folds) and shallow bright-bottom effects |
| 27 Sep | **Next diagnostics are exploratory, and labelled so**: (1) the calibration with the 95% rule alone, no "rises throughout" exception; (2) shallow sediment over-reading against distance to shore and bottom brightness | Both were prompted by these results, so neither can be confirmatory. Each is reported beside the registered result, never in place of it |
| 27 Sep | **Exploratory E1–E3 run** (details under *Exploratory follow-up*). The 95%-only rule does slightly worse (RMSE 2.82 vs 2.70 m) and leaves the shallow bias in place | The drafting fault in step 2 is closed as immaterial — the registered rule stays. The bias pattern is explained by the calibration's form: depth regressed on a noisy ratio regresses toward the mean, and the ratio curve bends at ~14 m in the bay and ~8–10 m on the open coast. `validate --exploratory` and `substrate --tag` write only to `outputs/exploratory/`, so a variant can never overwrite a registered output |
| 29 Sep | **Gauge record received and checked before use.** 1-minute, complete, AHD stated in the header and confirmed by the record's mean (−0.03 m over 3 days vs MSL +0.074); AEST ±2 min and quality code 55 = ±20 mm per MHL's conditions sheet; Jervis Bay station datum adjustment 1.070 m, matching the config | The layout differed from the one the parser was written for: **Date and Time in separate columns** after a 30-line licence block. The old parser **failed loudly** (a tokenizer error), not silently. Fixed to join date and time, read the stated datum and quality codes, and **refuse if the header's datum contradicts the numbers**; pinned by a test of this exact layout. The tidal rate is now fitted over ±15 min — with 1-minute samples the two bracketing values differ by noise as much as by tide |
| 29 Sep | **Prediction test passed: water level −0.392 m AHD** at 10:02:37 AEST (tide falling 0.12 m/h). Predicted in the register on 27 Sep: about −0.3 to −0.4 m, the image estimate biased low by ~0.1–0.2 m. Observed bias of the image estimate: **0.104 m** | The image method's known bias (NIR reading through the first decimetres of water) is now measured once. Useful for sites 2 and 3 if a gauge is missing, as a correction with a stated uncertainty rather than a guess |
| 29 Sep | **Phase 2 rerun at the measured level becomes the primary result**; the provisional run is kept beside it | The protocol said "report both". Pooled RMSE 2.70 → 2.68 m; no conclusion changes. Exploratory runs are not repeated |
| 29 Sep | **Phase 3 closed** with Warren's conclusion on blocked vs random validation (above) | Stumpf is the control; the prediction it makes — flexible models will open a gap — is carried into v2 as prediction 2 |
| 29 Sep | **v2 pre-registered**: one model family (gradient boosting, fixed settings, no tuning, no early stopping), image-only per-pixel features, v1's folds and depth-balanced sample over 0–20 m, paired comparison with Stumpf; a coordinate model run only as a labelled leakage demonstration; four predictions written down first | Every choice that could be tuned to the answer is fixed before the answer exists. No tuning because honest tuning needs nested cross-validation — cost and complexity out of proportion to the question, which is the size of the ML advantage, not its maximum |
| 29 Sep | **v2 run once, as registered: gbm 1.88 m, 0.80 m better than Stumpf** [0.57, 1.06]; meets CATZOC C to 3 m. Predictions 1–3 held; **prediction 4 failed** | Coordinates helped even on 2 km blocks because depth itself is correlated over kilometres — the model interpolates the survey from neighbouring blocks. Recorded as a failed prediction, not explained away: it shows that block size protects only against what the model can exploit, and that the real safeguard is excluding location, as v2 did |
| 29 Sep | **Phase 3 conclusion edited** (with Warren's agreement): Australian spelling, "clean" rather than "perfect" control, and the correlation and block-size evidence added | The claim that the model *could not* use leakage is stronger with the evidence that the data offered it |
| 1 Oct | **Site 2 sized by the validation design, not the place name.** The first ELVIS clip (the requested 1.7 × 5.15 km Narrabeen–Collaroy box) held 4.1 km² of 0–20 m water in 3–4 two-km blocks — fewer than five folds. Re-ordered across the SydneyNorth block (NSW020302) | Same code at every site means each site must fit the design. The block's ends lie in the SydneyHarbour (flown 18 Aug) and BrokenBay (24 Aug) rasters, a month before SydneyNorth (18 Sep), so the AOI is the single-date window between them: Queenscliff–Palm Beach |
| 1 Oct | **ELVIS averages any extract that spans more than one survey block ("Average 16").** The whole-block Narrabeen extract is exactly a 4×4 mean of the native cells (321,291 cells, zero difference), centred half a cell off: smoothed over 20 m and displaced 2.5 m S and 2.5 m W. At 10 m in 0–20 m it differs from native by 0.13 m RMS (+0.05 m mean, p99 0.52 m). Native values sit on a centimetre lattice (97–99% of underwater cells); averaged ones do not (~10%, i.e. chance) | Orders kept inside one block's raster come back native: Northern Beaches is bit-identical to the first clip on 327,640 cells, and both Batemans Bay boxes pass. `scripts/dem_extracts.py` checks any delivery, and joins boxes of one block only where every overlapping cell is identical |
| 1 Oct | **Jervis Bay's reference is mostly ELVIS-averaged** (257 of 299 one-km tiles; native only in a ~5 × 8 km Beecroft patch). Headline results stand: 0.13 m of reference error in quadrature moves 2.68 and 1.88 m by < 0.01 m. **Its relief terciles are compromised** — averaging suppresses within-pixel spread everywhere except the Beecroft patch | Disclosed rather than re-ordered: a native Jervis Bay needs five block orders joined by hand, for an effect inside the intervals. Phase 4 measures the effect directly (sensitivity run). The 27 Sep "delivered DEM verified" check covered range and units, not resampling; that check is now a script |
| 1 Oct | **Scene search: scene-wide nodata applies only when an item has no footprint**; measured AOI coverage decides. The candidates table is written even when nothing passes | At Sydney both orbits clip tile 56HLH (14–20% nodata), which rejected all 36 acquisitions, and the empty result left no table to show why. At Batemans Bay a 100%-coverage, 0.4%-cloud scene had been rejected the same way. No Jervis Bay row was rejected on nodata alone |
| 1 Oct | **Site 3: Batemans Bay. Richmond River rejected** | Screened on quicklooks before any lidar was ordered. Richmond's plume is a small patch at the mouth, and the mouth sits on the seam between ByronBallina (4 Aug) and Broadwater (8 Jul), 27 days apart. Batemans Bay is one block and one date, shows the Clyde plume across the inner bay, and has an AHD gauge |
| 1 Oct | **Scenes: Northern Beaches 27 Sep (9 days after), Batemans Bay 23 Aug (1 day before)**, by the site-1 rule. 28 Aug at Batemans Bay was proposed for its turbid look and declined | The quicklook panels are stretched per channel to each scene's own water, so their colour cannot rank turbidity; 28 Aug also had 5 m/s wind and wave texture across the outer bay. Choosing scenes for turbidity would build the gradient into the sample |
| 1 Oct | **Earth Search Collection-1 pixels already have the BOA offset removed.** Items carry `earthsearch:boa_offset_applied: true` while `raster:bands` still declares −0.1; trusting the latter subtracted it twice (Northern Beaches water red −0.096), and the water-physics check refused the stack. The item flag now wins over a contradicting `raster:bands`; the check still arbitrates | **Corrects the 27 Sep entry** on Collection-1 offsets, which had never met a real Collection-1 pixel. Jervis Bay used baseline 00.01 (flag false, offset 0, water red +0.0039) and is unaffected. Both new scenes pass (red +0.0036 and +0.0053) |
| 1 Oct | **Batemans Bay lidar in two native boxes**, joined without resampling (overlap 881,967 cells, bit-identical) | A whole-block order touches the MoruyaCoast and Murramurang rasters and would be averaged. Cost: the far north-east corner by Murramurang |
| 1 Oct | **Co-registration window fallback: 2 → 1.5 → 1 km until at least four windows agree**, other thresholds unchanged. Northern Beaches, 2 km: E −0.43, N −3.47 m (7 windows, scatter 0.7 / 0.3 m). Batemans Bay: 3 windows at 2 km — insufficient — then at 1.5 km E +2.95, N −4.91 m (7 windows, scatter 1.3 / 0.2 m). Both applied | Batemans Bay's AOI is half water; 2 km tiles that are 90% land and 3 km apart fit only three, all in one corner — unable to test that the shift is rigid or to catch an outlier. Written after seeing that, but it concerns land area, not depth errors. Both new scenes are Collection-1 (geometrically refined) and shift 3.5–5.7 m, against Jervis Bay's 7.5 m on unrefined 00.01 |
| 1 Oct | **Provisional water levels from the image:** Northern Beaches +0.49, Batemans Bay +0.52 m AHD. `waterlevel --from-image` no longer requires gauge constants | Superseded when the gauge records arrive. On surf beaches whitewater may bias the image estimate beyond Jervis Bay's 0.10 m |
| 1 Oct | **Gauges: Sydney 213470 (primary) and Patonga 212440 (cross-check) for Northern Beaches; Princess Jetty 216410 for Batemans Bay. Not Ocean Street Bridge (213408D)** | The two ocean-connected gauges bracket the site, so their difference is a measured uncertainty. Ocean Street Bridge records Narrabeen Lagoon, whose entrance damps and delays the tide |
| 1 Oct | **Phase 4 protocol pre-registered** before any fit at sites 2 or 3 | Eligibility from the lidar and dates, clarity from the image, the scene and gauge rules, four predictions and two sensitivity runs, all fixed first. The within-site block test is the inferential core, because three sites cannot separate clarity from everything else that differs between them |
| 1 Oct | **Phase 4 code written after the protocol commit `a5b5f5d`, tested on synthetic data only**: `clarity.py` (metric, block table, Spearman with block-resampled intervals, mean of within-site correlations, gate 4, the four predictions evaluated as written); `reference --dem/--tag` and `validate --reference-tag` for sensitivity runs, which can only write tagged files and `outputs/sensitivity/`; `validate` exits without fitting below 15 blocks | Same order as Phase 2: protocol, then code, then real data. A test pins the design's reason for the within-site mean: two sites that differ only in level give a pooled Spearman above 0.7 and a within-site mean near 0. Another pins that a sensitivity run leaves the registered outputs byte-identical |
| 16 Nov | **Substrate layers fetched for Northern Beaches and Batemans Bay**, before any `validate` run, as the protocol allows. Same queries and class rules as Jervis Bay; one GeoPackage per site (`substrate_<site>.gpkg`, with `provenance_<site>.json`). Northern Beaches 1,404 macrophyte, 1,781 reef-extent, 475 reef-source polygons; Batemans Bay 718, 1,901, 1,469 | Macrophyte mapping dates differ by water body: Pittwater Aug–Sep 2018 (contemporaneous), the lagoons 2008, Batemans Bay/Clyde 2012–2022. New classes (*Posidonia* – Sparse, *Zostera* – Sparse) fall under the addendum's rules unchanged. The Fisheries service now refuses Python's default User-Agent (403); a browser-style one was sent. `substrate` now defaults to the site's own GeoPackage, so a site can never read another's layers (`391c625`) |
| 16 Nov | **MHL records received and checked before use.** Sydney 213470, Patonga 212440, Princess Jetty 216410: 1-minute, 22 Aug – 30 Sep 2018 AEST, AHD in the header and confirmed by each record's mean (−0.035 to −0.049 m over five weeks, against MSL +0.05 to +0.065), quality 55 throughout; one 17-minute gap (Princess Jetty, 02:50 AEST 13 Sep). Datum adjustments from MHL's *Data conditions* sheet (Sydney: Zero Fort Denison 1897, 0.925 m; the other two record in AHD); tidal planes from MHL's station pages, 2018–19 column | **213470 is MHL's own Sydney gauge** (151.2585, −33.8255, inside the harbour near Middle Head), **not Fort Denison** as the 1 Oct request assumed. A station recorded in AHD made the datum inference ambiguous by construction (both candidates coincide) and `waterlevel` refused it; for such stations it now checks only that the mean sits at MSL, which still catches centimetres or a wrong file. Pinned by a test |
| 16 Nov | **Water levels measured.** Northern Beaches **+0.501 m AHD** (Sydney, 10:06:03 AEST 27 Sep, falling 0.09 m/h); Patonga +0.539, a **0.038 m** difference — under the protocol's 0.10 m, so no water-level sensitivity run; the difference is reported as the uncertainty. Batemans Bay **−0.181 m AHD** (Princess Jetty, 10:06:33 AEST 23 Aug, falling 0.12 m/h) | Patonga was read with `waterlevel --gauge-key tide_gauge_check --tag patonga`, which writes only to `outputs/sensitivity/` — a cross-check gauge can never become the level `reference` uses. Princess Jetty sits ~3 km up the Clyde; its M2 tide lags the coast by ~22 min, worth ~0.04 m at the overpass's rate. Reported as uncertainty, not corrected — the protocol named the gauge |
| 16 Nov | **The image estimate held at the surf coast and failed at the estuary.** Northern Beaches: image +0.493 vs gauge +0.501 (0.008 m low). Batemans Bay: image +0.520 vs gauge −0.181 — **0.70 m high**, opposite in sign to Jervis Bay's 0.10 m low bias | The 1 Oct worry was surf; the failure came from the estuary instead. Cause not investigated (no fit depends on it now). Lesson: the protocol's fallback (image + Jervis Bay's bias) would have put Batemans Bay's reference ~0.8 m wrong. The image estimate is a check on a gauge, not a substitute for one |
| 16 Nov | **Sydney wave record: no storm between the survey and the scene.** Hourly Hs, 647 of 697 hours present. 18 Sep (lidar end) to the overpass: median 1.53 m, p90 2.18 m, max 2.81 m (04:00 24 Sep, Tp 10 s, S); 1–17 Sep max 2.85 m. At the overpass Hs ~1.8 m, Tp ~15 s from the SSE | Sandbars may still have moved in nine days of ordinary swell; nothing exceptional. Reported beside the 0–5 m results as registered, no correction. A 15 s groundswell at the overpass is consistent with the bright-NIR flag removing 2.0 km² of surf-zone water |
| 16 Nov | **Phase 4 amendment: Northern Beaches open coast only** (*Phase 4 amendment, 16 Nov 2026*) — Pittwater and the lagoons excluded by a named open-sea point; 21.6 km² in 21 blocks remain | My error: the AOI was drawn from the block's single-date window without checking which water bodies it held, and Pittwater is a third of it. Caught while reading the substrate layers, before any fit; Warren chose the open coast only. **The first implementation was wrong too:** it took water touching the AOI's east edge, tested on synthetic grids filled to the edge; on the real grid a lidar-free margin surrounds everything, so nothing touched any edge and `reference` refused. Replaced by the seed point, and the test fixture now carries the margin. Lesson, again: synthetic tests check the logic, not the assumption about the data's shape — run on the real input before calling it done |
| 16 Nov | **Phase 4 run at both new sites** after the amendment commit `2cd2f53`: `waterlevel`, `reference`, `validate` (Stumpf, gbm, gbm_xy), `substrate`, the `elvis_avg` sensitivity pair, `clarity`. No deviation in any fit. Results in *Phase 4 result* | Gate 4 not met; predictions 1, 2 and 4 held (2 and half of 4 on point estimates only), prediction 3 failed |
| 16 Nov | **`clarity` corrected after its first run; both results kept.** Northern Beaches' block correlation was computed over NaN block medians ranked as the largest values (59 pixels with no red value, 13 of 20 blocks). Corrected: −0.16 → +0.70 (Stumpf); mean within-site +0.06 [−0.19, +0.33] → +0.35 [+0.09, +0.59]. First run kept as `outputs/phase4/clarity_run1_superseded.json`; the record's `deviations` says so | My error, and the test suite's gap: `site_clarity` had a test with a missing value, `block_table` did not, and `spearman` ranked NaN without complaint. Both closed; `spearman` now refuses non-finite input. Caught only because the block table was read row by row before committing — 13 `null` medians beside a correlation claiming 20 blocks. **A correction that moves the headline toward the hoped-for answer needs more scrutiny, not less:** the missing-value rule it applies was written and tested on 1 Oct, before any data; treating the 59 pixels as zero gives the same answer; and nothing else in the record changes |
| 16 Nov | **The block test does not isolate turbidity** — block depth mix is correlated with block error at every site (+0.6 to +0.7) and with block red in opposite directions at Northern Beaches (+0.70) and Batemans Bay (−0.71). Block mean depth added to `clarity.json`'s block table so this can be checked from the record | A design flaw in the 1 Oct protocol, mine: it guarded against site-level offsets and forgot that RMSE is depth-dependent inside the 10–20 m window. A depth-standardised block error should have been registered. Not repaired after the fact: the registered statistic is reported as registered, with the confound beside it |
| 16 Nov | **Exploratory addendum defined: a depth-standardised block test** (*Exploratory addendum*), committed before it is run on real data. Each block's error is compared with what its depth mix predicts from the site's other blocks | Warren asked for it if it would add to the project. It does: the phase's question is whether error tracks clarity, and the registered test cannot answer it at two of three sites. It is exploratory because the registered result — and a rough partial correlation — had already been seen; the reading rule is fixed in advance so that a favourable number cannot be argued into more than it is |
| 16 Nov | **Brief checked against its stated goals before the write-up.** Kept: the question, the blocked-validation design, the "number and an envelope" deliverable. Changed: the portfolio draft no longer claims a clarity gradient or a sea-state stratum; *The question* and *Sites* now say what was and was not found; error-budget rows added for sites 2–3 and for the clarity metric | Three open items carry into Phase 5: the reference lidar is still not committed (the reproducibility promise in *Data*), and the Phase 4 conclusion and the limitations panel are Warren's to write |
| 16 Nov | **Exploratory depth-standardised block test run** after addendum commit `884dce1`: mean within-site +0.40 [+0.10, +0.66] (Stumpf), +0.34 [+0.02, +0.60] (gbm); all three sites positive; *supported* by the rule written beforehand | The registered test's site-to-site disagreement was depth mix. The result is carried mainly by Jervis Bay and concerns red reflectance, not turbidity; it changes neither gate 4 nor prediction 3. Reported as a lead, not a finding |
| 16 Nov | **Write-up standard set** (Warren): conference-paper quality, readable by a non-technical portfolio audience. Plan proposed in *Write-up plan* — one document in three layers | Nothing is drafted until the limitations panel and Phase 4 conclusion exist in Warren's words and the outline is approved |
| 19 Nov | **Reference lidar published as a release asset, not committed.** The four extracts used (three references, one sensitivity) in `sdbNSW_reference_lidar_2018.zip`, 117 MB, paths mirroring the repo, attribution and md5s inside | One file over git's 100 MB limit; committed separately they would add 122 MB to every clone for a reader who almost never replicates. A release costs only the reader who downloads it. The md5s match those in the `reference` records |
| 19 Nov | **Descriptive decomposition of the site differences** (post hoc, no new fit): depth-balanced RMSE and error by substrate class per site (*Phase 4 result*) | Northern Beaches' higher error goes mostly with its reef share (54% of assessed pixels, against 10% and 20%); on sediment the sites are within 0.35 m. Reef and exposure are the same pixels there, so this does not separate them |
| 19 Nov | **Output format and title.** Web page and conference-layout PDF from one source. Title open: the tropical literature is the benchmark, not the subject | Warren's decisions |
| 19 Nov | **Titles set; Phase 4 conclusion revised; AI workflow statement drafted; house style set** | Warren's decisions. The conclusion keeps his argument (gate 4 is the finding; exposure and substrate matter) and corrects what the data contradict or already answer: the Stumpf ranking lies within its intervals; one scene per site; no mapped seagrass on the open coast; depth mix measured and small; reef share measured and large; the within-site lead |
| 19 Nov | **The repository is private.** The release was published, but an unauthenticated request for the repo and its releases returns 404 | Must be public before the page links to it; the release's sha256 is recorded so a reader can verify the download |
| 19 Nov | **Correction: the share of Northern Beaches' 0–2 m water lost to surf.** The *Phase 4 result* and the first revision of the conclusion said only 12% of the 0–2 m reference water was assessed, attributing the loss to surf. Recomputed from the mask: 66% of that "reference water" is Pittwater and lagoon shallows removed by the open-coast rule; of the open-coast water, 35% is assessed and 65% flagged bright. Jervis Bay 60% assessed (39% bright), Batemans Bay 82% (18%) | My error, found while checking Warren's limitations panel against the outputs: `validate`'s exclusion table counted water the open-coast rule removes as reference water and did not list the rule as a reason. It now reports `not_sea` (tested); committed records are unchanged and the brief carries the corrected figures |
| 19 Nov | **Limitations drafted** by Warren and revised after review: a five-point plain panel for layer 1, and his fuller list, corrected, as the paper's Limitations section | Corrections: the shallow-water exclusion figures; the averaging check was made at Northern Beaches, not Jervis Bay; reference uncertainty is comparable only to gradient boosting's shallow error at two sites; reef bias is not beyond correction; the block-size caveat applies to gradient boosting at Batemans Bay as well as Jervis Bay. The navigation warning was checked against the lidar metadata |
| 19 Nov | **Every reference checked before drafting** (`paper/reference_check.md`); 33 entries in `paper/references.bib`, each against Crossref or the publisher, and every quoted figure against its abstract or text | Two framing claims in *The question* were wrong: SDB validation is not "almost entirely clear tropical water" (Ireland, the Aegean, Japan and Adelaide are published), and the 1.3 / 1.8 / 2.2 m benchmark is one study with an 80/20 split of unstated design. The novelty claim narrows to "no published assessment on the NSW open coast", which the searches support. Corrected before any text depends on it |
| 19 Nov | **Outline proposed** (`paper/outline.md`): about 4,300 words, six figures plus a hero figure, four tables; Pandoc and Typst build the page and PDF from one Markdown source | Awaiting Warren's approval, author line and PDF layout |

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
- Earth Search STAC item with `earthsearch:boa_offset_applied` — https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_56HLH_20180927_1_L2A
- The same double-offset trap found independently — https://github.com/Khadra-AI/thuraya-experience/pull/109
- ESA, radiometric offset in PB04.00 products — https://forum.step.esa.int/t/info-introduction-of-additional-radiometric-offset-in-pb04-00-products/35431
- Nechad, Ruddick & Park (2010), generic multisensor algorithm for total suspended matter, *RSE* 114(4) — https://doi.org/10.1016/j.rse.2009.11.022
- Pope & Fry (1997), absorption spectrum of pure water, *Applied Optics* 36(33) — https://doi.org/10.1364/AO.36.008710
- PSMSL, Sydney Fort Denison — https://psmsl.org/data/obtaining/stations/196.php
