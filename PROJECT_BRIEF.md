# Project record: satellite-derived bathymetry on an exposed temperate coast

The full record of the sdbNSW project: the question, the sites and data, the
result of each phase as it was reported at the time, Warren van Ryn's
conclusions, and the decisions register. The paper
([web page](https://wvr-spatial.github.io/sdbNSW/),
[PDF](https://wvr-spatial.github.io/sdbNSW/sdbNSW_paper.pdf)) is the
summary; this is the evidence behind it.

During the project this file was the working brief, written as a running
exchange between Warren and the AI agent that wrote most of the code. It was
rewritten as this record on 19 November 2026. The working version remains in
git history (`git show dd6ad52:PROJECT_BRIEF.md`), and every protocol that was
registered in it is frozen verbatim, with its commit, in
[`protocols/`](protocols/).

Conventions: error e = SDB − lidar, so positive values read too deep.
Intervals are 95% block-bootstrap intervals unless stated. *Stumpf* is the
band-ratio model; *gbm* the gradient-boosting model; *gbm_xy* the same model
given coordinates, run only to demonstrate leakage. Depth bands are 0–2,
2–5, 5–10, 10–15 and 15–20 m of lidar depth.

## Status, 19 November 2026

Complete. All three sites were assessed under pre-registered protocols with
one amendment made before any fit at the new sites. Stumpf pooled RMSE is
2.68, 3.03 and 2.96 m at Jervis Bay, Northern Beaches and Batemans Bay; gbm
1.88, 2.40 and 2.45 m, better at every site with paired intervals clear of
zero. Stumpf meets CATZOC C at no depth; gbm meets it to 3 m at Jervis Bay
and 2 m at Batemans Bay. Error is roughly level to about 15 m and climbs
beyond. Decision gate 4 was not met: error does not follow the clarity
metric across sites, and the metric could not rank them. An exploratory,
depth-standardised test within sites links red reflectance to error beyond
what depth explains (mean rank correlation +0.40 [+0.10, +0.66]). The paper,
web page and figures are published; the reference lidar is a release asset.

## The question

> Does satellite-derived bathymetry work on an exposed temperate coast, and
> where exactly does it stop working?

The NSW coast is temperate and swell-exposed, with surf zones, rocky reefs,
river plumes and seasonal turbidity, and no published accuracy assessment of
SDB on its open coast was found. The deliverable was set as a number and an
envelope, not a map: how large the error is, and the depth and the water
clarity at which the method fails.

*How the framing changed.* The project began by describing published SDB
validation as almost entirely clear tropical water, with typical errors of
1.3 m for machine learning, 1.8 m for the Stumpf ratio and 2.2 m for linear
models. The reference check before drafting (`paper/reference_check.md`)
found both overstated. The literature leans to clear water, but temperate
and optically complex sites are published (the Irish coast at 1.6 to 2.4 m
RMSE, the Aegean, an exposed sandy coast in Japan, the low-energy Adelaide
coast), and the three figures come from one study at St Thomas with an 80/20
split of unstated design. What held was narrower: no published assessment of
the NSW open coast.

*As answered.* Worse than the clear-water figures at all three sites, and the
depth boundary is measured: error is roughly level to about 15 m and climbs
beyond. The clarity boundary is not established, because the three scenes did
not deliver a clarity gradient this imagery can measure.

## Sites

Three sites, one pipeline. The design intent was a clarity gradient from a
sheltered, clear bay to an estuarine plume; Phase 4 could not confirm the
gradient in these scenes, so what the sites give is three settings under one
method: a sheltered bay, an exposed surf coast and an estuary mouth.

| # | Site | Setting | Extent (WGS84) and survey block |
|:--|:--|:--|:--|
| 1 | Jervis Bay | Sheltered embayment and its entrance; clear, mixed seabed | 150.6607, −35.1504, 150.8083, −34.9735; block NSW020502 and neighbours, flown 8–9 Sep 2018 |
| 2 | Northern Beaches (Queenscliff to Palm Beach) | Exposed, surf-dominated open coast | 151.2460, −33.7867, 151.3570, −33.5918; the single-date part of block NSW020302 (flown to 18 Sep 2018). Open coast only, by amendment |
| 3 | Batemans Bay and the Clyde mouth | Estuary mouth with a river plume | 150.1592, −35.7700, 150.2906, −35.6870; block NSW020602 (24 Aug 2018), two native boxes joined |

Richmond River (Ballina) was screened as site 3 and rejected on 1 October: its
plume is a small patch on the seam between two blocks flown 27 days apart.

## Data

| Source | What it supplies | Access | Licence | In the repository |
|:--|:--|:--|:--|:--|
| [NSW Marine LiDAR Topo-Bathy 2018](https://datasets.seed.nsw.gov.au/dataset/marine-lidar-topo-bathy-2018) | 5 m grid on AHD, IHO Order 1b, shore to 20–40 m, July to December 2018. An extract that spans several survey blocks is averaged by the portal; see `data/README.md` | ELVIS, area select | CC BY 4.0 | The four extracts used, unmodified, as a release asset |
| Sentinel-2 Level-2A | 10 m surface reflectance, one scene per site | Earth Search STAC on AWS, anonymous | Copernicus open data | Derived results only |
| Manly Hydraulics Laboratory tide gauges | Water level at each overpass: Jervis Bay 216470; Sydney 213470 and Patonga 212440 for Northern Beaches; Princess Jetty 216410 for Batemans Bay. One-minute records in AHD, quality code 55 (±20 mm). Sydney waverider record for sea state | On request | CC BY 4.0, attribute NSW DCCEEW | Derived water levels only |
| NSW Imagery (Spatial Services) | Orthophoto windows on land, used only to measure the image's geolocation error | ArcGIS REST, anonymous | Images excluded from Spatial Services' CC licence | Never stored or drawn |
| ERA5 10 m wind | A glint screen during scene selection | Open-Meteo archive API | CC BY 4.0 | Fetched at run time |
| NSW DPI Fisheries Estuarine Macrophytes | Seagrass classes for grouping errors; estuaries only | ArcGIS REST | CC BY 4.0 as stated by the service | Derived statistics only |
| DCCEEW NSW seabed reef extent | Reef and unconsolidated sediment, classified from the same 2018 lidar | ArcGIS REST | CC BY 4.0 | Derived statistics only |

## Method in brief

**v1, the band ratio.** The Stumpf ratio, ln(1000·ρ_blue) / ln(1000·ρ_green),
regressed linearly on depth inside each training fold, on a depth-balanced
sample below a fitting limit where the binned ratio stops rising. One
calibration per site. Water level at the overpass enters as a scalar offset
between instantaneous depth and AHD.

**v2, gradient boosting.** scikit-learn's HistGradientBoostingRegressor with
fixed settings and no tuning, on per-pixel image features (log reflectance in
four bands, the Stumpf ratio, the blue-to-red ratio). No coordinates: that is
how a flexible model memorises a site and how a random split flatters it.
The question for v2 was not whether machine learning can do SDB, but whether
its advantage over the band ratio holds out of sample and at murkier sites.

**Validation.** Spatially blocked cross-validation on 2 km blocks, five folds,
ten repeats, with a random pixel split reported alongside as a control. The
band ratio, with two parameters, cannot memorise location, so blocked and
random results should agree for it; a flexible model should open a gap. Error
is reported by depth band (by lidar depth and by predicted depth), by seabed
type, inside the bay against the open coast at Jervis Bay, and as the
breakdown depth at which the 95th percentile of absolute error exceeds
CATZOC C, with the denominators: how much reference water in each band could
not be assessed, and why.

## Protocols

Each protocol was committed before any model was fitted to the data it
governs, and the output records name the commit that introduced it.

| Protocol | Registered | Commit | Verbatim text |
|:--|:--|:--|:--|
| Phase 2: the band ratio at Jervis Bay | 27 Sep 2026 | `8332154` | [`protocols/01_phase2_band_ratio.md`](protocols/01_phase2_band_ratio.md) |
| Substrate addendum | 27 Sep 2026 | `73d02ce` | [`protocols/02_substrate_addendum.md`](protocols/02_substrate_addendum.md) |
| v2: gradient boosting | 29 Sep 2026 | `c2baa44` | [`protocols/03_v2_gradient_boosting.md`](protocols/03_v2_gradient_boosting.md) |
| Phase 4: three sites | 1 Oct 2026 | `a5b5f5d` | [`protocols/04_phase4_three_sites.md`](protocols/04_phase4_three_sites.md) |
| Phase 4 amendment: Northern Beaches open coast only | 16 Nov 2026 | `2cd2f53` | [`protocols/05_phase4_amendment.md`](protocols/05_phase4_amendment.md) |
| Exploratory addendum: depth-standardised block test | 16 Nov 2026 | `884dce1` | [`protocols/06_exploratory_depth_standardised.md`](protocols/06_exploratory_depth_standardised.md) |

## Results

### Phase 1: alignment and water level, Jervis Bay

- **Co-registration.** The image sits E −7.42 ± 0.98 m, N −1.02 ± 1.14 m from
  its true position (7.5 m), measured against NSW orthoimagery on eight
  agreeing land windows and removed before any comparison. A first estimate
  from steep shorelines (21.6 m) was wrong and was caught by a visual check
  against independent imagery in QGIS (decisions register, 27 Sep).
- **Water level.** −0.392 m AHD at the overpass, from the gauge's one-minute
  record. The image's own estimate, −0.496 m, was predicted to read 0.1 to
  0.2 m low before the record arrived; it read 0.104 m low.
- **Reference.** 93.3 km² of usable water at 0–20 m on the scene grid.

Gate 1 (seabed visible; lidar and image aligned) passed.

### Phase 2: the band ratio at Jervis Bay

Run once as registered at the image-estimated water level (−0.496 m AHD), then
rerun at the gauged level when the record arrived, as the protocol required.
The gauged run is the primary result.

| | Gauged water level (primary) | Image estimate (first run) |
|:--|:--|:--|
| Usable pixels | 932,838 | 937,499 |
| Pooled RMSE, 2 km blocks | **2.68 m** [2.31, 3.13] | 2.70 m [2.32, 3.15] |
| Bias · R² | −0.42 m [−0.95, +0.06] · 0.689 | −0.41 m · 0.688 |
| Depth-balanced RMSE | 2.48 m | 2.48 m |
| Random split · blocked/random | 2.66 m · 1.008 | 2.67 m · 1.009 |
| Bias by band | +0.94 / +1.23 / +0.81 / +0.12 / −2.07 | +0.98 / +1.23 / +0.82 / +0.12 / −2.10 |
| RMSE by band | 2.11 / 2.67 / 2.07 / 2.06 / 3.46 | 2.09 / 2.67 / 2.08 / 2.08 / 3.50 |
| Inside bay / open coast RMSE | 2.27 / 4.69 m | 2.28 / 4.72 m |
| Breakdown depth, CATZOC C and B | 0 m (exceeded from the shallowest bin) | 0 m |
| Fitting limit D_cal | 17–20 m (median 20) | 16–20 m (median 20) |
| Residual correlation range | 4 km (beyond the blocks) | 4 km |

Every figure moved by 0.15 m or less: a constant water-level error changes only
the intercept and which pixels fall in each band.

Gate 2 passed. The method is not charting-grade anywhere in the bay, and it
fails in two distinct ways: a floor of about 2 m RMSE from the surface down,
with a bias of about +1 m (too deep) through 0–10 m, and saturation beyond
about 14 m, where SDB reads too shallow. The open coast outside the entrance
doubles the error. Residuals correlate at 0.70 between adjacent pixels, 0.16
at 2 km and below 0.1 only at 4 km, longer than the blocks, so the intervals
are probably somewhat narrow; the RMSE itself barely moves with block size
(2.66 m at random, 2.72 m on 4 km blocks). Within-band R² is negative and not
meaningful. Pixels within 50 m of shore carry RMSE of 6 to 8 m at 2–15 m
depth (cliff-foot rock, few pixels). In the 0–2 m band the bright-NIR flag
removed 32% of pixels at the first run's water level, so that band describes
calm water only.

### Substrate at Jervis Bay (registered addendum)

`substrate` reads the Phase 2 residuals; nothing is refitted. Inside the bay,
bias of each class minus that of *sediment, no seagrass mapped*, at the gauged
water level:

| Band | *Posidonia* | Reef |
|:--|:--|:--|
| 0–2 m | **−2.03** [−2.33, −1.20] | **−2.12** [−2.76, −1.47] |
| 2–5 m | +0.16 [−0.15, +0.45] | +0.07 [−0.19, +0.36] |
| 5–10 m | +0.16 [−0.22, +0.87] | **+1.66** [+1.23, +2.12] |
| 10–15 m | (not mapped) | **+1.71** [+1.18, +2.65] |
| 15–20 m | (not mapped) | **+1.64** [+0.67, +3.27] |

The *Posidonia/Zostera* and *Zostera/Halophila* classes are too small to
compare in most bands, and their intervals span zero where they are compared.
The stricter rule (pixels at least 90% one class) moves every figure by 0.2 m
or less. Reef, open coast minus inside the bay: +1.09 (2–5 m), −0.97 (5–10),
**−3.66** (10–15), **−5.21** (15–20).

Against the direction stated in advance (dark seabed reads deeper):

- **Reef: supported at 5–20 m**, about 1.7 m deeper than sediment at the same
  depth, intervals clear of zero.
- ***Posidonia*: not supported** at 2–10 m.
- **0–2 m: reversed, because of the reference class.** Bare shallow sediment
  itself reads 2.2 m too deep, *Posidonia* +0.2 and reef +0.1.

So the Phase 2 shallow over-reading is mostly not substrate. The dark patches
off the western shore that carry the largest over-reading are mapped reef,
not seagrass. On the open coast at depth, reef and sediment alike read 5 to
6 m too shallow.

### Exploratory follow-up, Jervis Bay (not confirmatory)

Prompted by the registered results and run at the image-estimated water level;
outputs in `outputs/exploratory/`.

- **E1, the fitting-limit rule without its exception.** The registered rule's
  two sentences conflict for a steadily rising curve; it was implemented as
  written. The other reading stops the fit at 16–18 m and gives pooled RMSE
  2.82 m against 2.70 m, with the shallow bias unchanged. The drafting fault
  was immaterial.
- **E2, the ratio against depth.** Inside the bay the median ratio rises almost
  linearly to about 14 m, then flattens; on the open coast it flattens from 8
  to 10 m and lies on a lower curve. One site-wide line cannot follow both,
  which is the open coast's −5 to −6 m at depth.
- **E3, regression toward the mean.** Regressing depth on a noisy ratio
  (r = 0.89) pulls predictions toward mid-depths: shallow water reads deep and
  deep water shallow, while staying close to unbiased for a given *predicted*
  depth. Fitted the other way the pattern changes sign in the shallows and
  shrinks at depth, at the cost of pooled RMSE (2.68 → 3.02 m).

The paper therefore reports error both by lidar depth (how the method behaves)
and by predicted depth (what a map user gets).

### Phase 3: blocked against random validation (Warren, 29 Sep)

> The near-zero gap between our blocked and random validation (1.008) is what
> this model should produce. Stumpf is a simple two-parameter line: it has no
> capacity to overfit to neighbouring raster pixels or to memorise location,
> so spatial leakage cannot inflate its accuracy under a random split. The
> opportunity to leak was there (residuals correlate at 0.70 between adjacent
> pixels and do not fall below 0.1 until 4 km apart), but the model could not
> use it, and the block-size curve barely moves (2.66 m for a random split,
> 2.72 m for 4 km blocks). That makes the Stumpf run a clean control for
> leakage. We expect the need for spatially blocked validation to become
> obvious once we test more flexible models that are capable of that kind of
> spatial memorisation.

Gate 3 (blocked RMSE within about 30% of random) passed.

### v2: gradient boosting at Jervis Bay

Run once after the protocol commit, paired with the gauged Stumpf run on
identical inputs. `outputs/v2/`.

| | Stumpf (v1) | **gbm (v2 result)** | gbm_xy (leakage demonstration) |
|:--|:--|:--|:--|
| Pooled RMSE, 2 km blocks | 2.68 m [2.31, 3.13] | **1.88 m** [1.67, 2.13] | 1.32 m [1.12, 1.51] |
| Bias · R² | −0.42 · 0.69 | −0.12 · 0.85 | −0.07 · 0.93 |
| Depth-balanced RMSE | 2.48 m | 1.53 m | 1.25 m |
| Random split · blocked/random | 2.66 m · 1.008 | 1.78 m · **1.060** | 0.74 m · **1.774** |
| Block-size curve, random → 0.5 → 1 → 2 → 4 km | 2.66 → 2.67 → 2.68 → 2.69 → 2.72 | 1.80 → 1.83 → 1.86 → 1.92 → 2.06 | 0.78 → 0.99 → 1.16 → 1.50 → 1.87 |
| RMSE by band | 2.11 / 2.67 / 2.07 / 2.06 / 3.46 | 0.55 / 1.32 / 1.88 / 1.80 / 2.11 | 0.77 / 1.52 / 1.46 / 1.15 / 1.36 |
| Inside bay / open coast | 2.27 / 4.69 m | 1.65 / 3.08 m | 1.09 / 2.39 m |
| Breakdown depth, CATZOC C / B | 0 / 0 m | **3 / 2 m** | 2 / 1 m |

**gbm minus Stumpf, paired:** −0.80 m [−1.06, −0.57] pooled; by band −1.57
(0–2 m), −1.35 (2–5), −0.19 [−0.61, +0.14] (5–10, not distinguishable),
−0.26 (10–15), −1.35 (15–20). The advantage is largest where a straight line
fails, the shallows and the saturation zone, and absent where it fits.

Predictions, as written before the run:

1. **Held.** gbm beats Stumpf on blocks, by 0.80 m, more than the roughly
   0.5 m reported for clear water.
2. **Held.** Its blocked/random ratio is 1.060 against Stumpf's 1.008, and its
   block-size curve rises steadily instead of lying flat.
3. **Held.** The coordinate model's random-split RMSE is 44% below its blocked
   RMSE (0.74 against 1.32 m), past the 30% gate.
4. **Failed.** The coordinate model did *better* on 2 km blocks than gbm (1.32
   against 1.88 m). Depth is smooth over kilometres, so given coordinates the
   model interpolates the surveyed depths of the surrounding training blocks;
   near a block edge the nearest training pixel is metres away. Its advantage
   drains away as blocks grow (0.78 m at random, 1.87 m on 4 km blocks, close
   to gbm's 2.06). That is interpolation of the reference, not remote
   sensing, and it is unavailable where SDB is needed.

Blocking limits leakage only in proportion to how block size compares with
the autocorrelation of whatever the model can exploit; for a model with
location, that is the depth field itself. The dependable protection is
keeping location out of the features, as v2 did. Caveats: gbm's block-size
curve has not levelled by 4 km, so its 2 km figure may be mildly optimistic
(its advantage at 4 km is still 0.66 m); the headline scores the mean of ten
out-of-fold predictions per pixel, which for a nonlinear model is a small
ensemble (a single repeat scores 1.92 m); and beyond about 17 m even gbm
saturates.

### Phase 4: three sites

**Amendment, before any fit (16 Nov).** The Northern Beaches box, drawn from
the survey block's single-date window, also held Pittwater, a sheltered
estuary joined to the sea only through Broken Bay, and Narrabeen and Dee Why
lagoons, whose levels are not the sea's: 10.7 of the 32.3 km² of usable water,
with 13 of the 34 blocks holding nothing else. Since the site's registered
role was the exposed open coast, only water 4-connected to a named open-sea
point (151.33, −33.74) is assessed. The rule removes 11.5 km² of water and
leaves 21.6 km² in 21 blocks, so eligibility (at least 15) holds.

**Inputs measured before any fit.** Water levels: Northern Beaches +0.501 m
AHD (Sydney gauge; Patonga +0.539, so no water-level sensitivity run),
Batemans Bay −0.181 m AHD (Princess Jetty). The image estimate was right at
the surf coast (0.008 m low) and 0.70 m too high at the estuary.
Co-registration: Northern Beaches E −0.43, N −3.47 m; Batemans Bay E +2.95,
N −4.91 m on 1.5 km windows.

Run once per site after the amendment commit, with no deviation in any fit.

| | Jervis Bay | Northern Beaches (open coast) | Batemans Bay |
|:--|:--|:--|:--|
| Scene · water level (m AHD) | 7 Sep 2018 · −0.392 | 27 Sep 2018 · +0.501 | 23 Aug 2018 · −0.181 |
| Assessed · 2 km blocks | 93.3 km² · 68 | 21.6 km² · 21 | 27.5 km² · 20 |
| **Clarity metric** (median red, 10–20 m) | 0.0037 | 0.0022 | 0.0053 |
| **Stumpf** pooled RMSE | 2.68 m [2.31, 3.13] | **3.03 m** [2.81, 3.22] | **2.96 m** [2.32, 3.52] |
| Stumpf bias · depth-balanced RMSE | −0.42 · 2.48 m | −0.55 · 3.02 m | −0.40 · 2.73 m |
| **gbm** pooled RMSE | 1.88 m [1.67, 2.13] | **2.40 m** [2.20, 2.58] | **2.45 m** [1.86, 2.95] |
| gbm bias · depth-balanced RMSE | −0.12 · 1.53 m | −0.31 · 2.12 m | −0.15 · 2.10 m |
| **gbm − Stumpf**, paired | −0.80 [−1.06, −0.57] | −0.63 [−0.78, −0.50] | −0.51 [−0.90, −0.15] |
| Stumpf RMSE by band | 2.11 / 2.67 / 2.07 / 2.06 / 3.46 | 3.90 / 2.66 / 2.55 / 2.42 / 3.58 | 2.04 / 2.76 / 2.22 / 2.62 / 4.01 |
| gbm RMSE by band | 0.55 / 1.32 / 1.88 / 1.80 / 2.11 | 1.51 / 1.74 / 2.44 / 2.34 / 2.57 | 0.60 / 2.24 / 2.43 / 2.27 / 2.94 |
| Breakdown depth, CATZOC C / B: Stumpf · gbm | 0 / 0 · 3 / 2 m | 0 / 0 · 0 / 0 m | 0 / 0 · 2 / 1 m |
| Blocked/random: Stumpf · gbm · gbm_xy | 1.008 · 1.060 · 1.774 | 1.010 · 1.069 · 2.936 | 0.982 · 1.159 · 4.260 |
| Residual correlation range | 4 km | 1 km | 2 km |
| **Block test**, Spearman of block red against block RMSE at 10–20 m: Stumpf | +0.52 [+0.25, +0.71], 48 blocks | +0.70 [+0.32, +0.89], 20 blocks | −0.18 [−0.77, +0.51], 12 blocks |
| Block test: gbm | +0.55 [+0.27, +0.76] | +0.39 [−0.05, +0.74] | −0.00 [−0.63, +0.75] |

Mean of the within-site correlations, the registered inferential test: Stumpf
**+0.35** [+0.09, +0.59], gbm **+0.31** [+0.05, +0.58].

**Gate 4: not met.** Ordered by the clarity metric the sites run Northern
Beaches, Jervis Bay, Batemans Bay; Stumpf RMSE runs 3.03, 2.68, 2.96 and gbm
2.40, 1.88, 2.45. The site that reads clearest has the largest error. As the
gate says, that is the finding.

Predictions, as written before the run:

1. **Held, weakly.** Batemans Bay has the highest red reflectance. But the
   three values span 0.003, the size the protocol said atmosphere alone could
   produce, and 10% of Northern Beaches' 10–20 m pixels sit on the product's
   red floor (0.0001). The ordering is not established as a property of the
   water.
2. **Held on the point estimates**, as registered (3.03 and 2.96 against
   2.68). The intervals overlap, most of all at Batemans Bay; this does not
   show the new sites are harder.
3. **Failed.** Inside Batemans Bay, Stumpf block error does not rise with
   block red reflectance (−0.18 [−0.77, +0.51]). Only 12 blocks hold 200
   pixels at 10–20 m and block red spans a narrow range (0.0043 to 0.0074), so
   only a very strong trend could have been confirmed. The block count was
   knowable from the lidar and should have been checked when the prediction
   was written.
4. **Held.** gbm beats Stumpf at every site with intervals clear of zero, by
   less at Batemans Bay (0.51 m) than at Jervis Bay (0.80 m); the second half
   holds on point estimates, as those two intervals overlap.

**One deviation, both results kept.** The first run of `clarity`
(`outputs/phase4/clarity_run1_superseded.json`) gave Northern Beaches a block
correlation of −0.16 [−0.63, +0.33] (Stumpf) and a mean within-site
correlation of +0.06 [−0.19, +0.33]. That was a computing error: 59 of the
site's 151,486 clarity pixels have no red value; the site metric left them
out, as written and tested on 1 Oct, but the block metric did not, so 13 of
20 block medians became missing values and were then ranked as the largest.
The correction leaves those pixels out of block median and block RMSE alike;
counting them as zero instead gives the same correlations to four decimals.
Jervis Bay, Batemans Bay, gate 4 and all four predictions are identical in
both runs.

**The block test is confounded by depth.** Stumpf's error grows with depth
inside the 10–20 m window, and blocks differ in their depth mix (Spearman,
from the block table in `clarity.json`):

| | Block mean depth against Stumpf block RMSE | Block red against block mean depth |
|:--|:--|:--|
| Jervis Bay | +0.62 | +0.06 |
| Northern Beaches | +0.71 | **+0.70** |
| Batemans Bay | +0.64 | **−0.71** |

At Northern Beaches the redder blocks are the deeper, offshore ones, so depth
alone would produce the +0.70; at Batemans Bay the redder blocks are the
shallower ones near the Clyde, so depth works against any turbidity effect.
Only at Jervis Bay is the test clean of this. The registered statistic stands
as registered; what it measures is that error rises with red reflectance, not
yet that it rises with turbidity.

**Leakage demonstration, repeated.** The coordinate model looks three to four
times better under a random split than on 2 km blocks at the new sites
(Northern Beaches 0.91 against 2.66 m; Batemans Bay 0.51 against 2.16 m). On
blocks it is worse than gbm at Northern Beaches (2.66 against 2.40 m) and
better at Batemans Bay (2.16 against 2.45 m, interval [1.19, 2.98]); this is
not a registered comparison.

**Substrate, addendum rules unchanged** (whole site; no seagrass class reaches
1,000 pixels in any band). Reef reads deeper than sediment at the same depth at
both new sites: Northern Beaches +1.84 (2–5 m), +2.20 (5–10) and +1.27
(10–15), all clear of zero, and +0.03 [−0.58, +0.57] at 15–20 m; Batemans Bay
+3.95, +3.28, +2.54, +2.79 and +2.47 across the five bands, all clear of
zero. With Jervis Bay's 5–20 m result, the reef bias is the most replicated
result in the project.

**Sensitivity: reference averaging.** Northern Beaches rerun against the
portal-averaged extract of the same coast: pooled RMSE moves by −0.02 m for
both models, no band by more than 0.07 m, and gbm − Stumpf by 0.002 m. The
relief terciles do move (edges 0.09 / 0.17 m become 0.06 / 0.11 m; tercile
RMSE shifts by up to 0.17 m). Jervis Bay's pooled results stand; its relief
strata do not.

**Northern Beaches shallows.** Stumpf reads 3.1 m too deep at 0–2 m. Of the
open-coast water at 0–2 m, 35% is assessed and 65% flagged as too bright in
the NIR, which on this coast is surf. The scene is nine days after the lidar,
with a 1.8 m, 15 s swell running and no storm in between; surf, foam and moved
sand cannot be separated here.

**Descriptive, post hoc: what the site differences are made of.** From the
committed records, no new fit, no interval; Stumpf, majority rule.

| | Jervis Bay | Northern Beaches | Batemans Bay |
|:--|:--|:--|:--|
| Share of assessed pixels at 15–20 m | 35% | 42% | 27% |
| Depth-balanced RMSE, Stumpf · gbm | 2.48 · 1.53 m | 3.02 · 2.12 m | 2.73 · 2.10 m |
| Share of assessed pixels on mapped reef | 10% | **54%** | 20% |
| Stumpf RMSE on sediment only | 2.42 m | 2.58 m | 2.77 m |
| Stumpf RMSE on reef only | 4.63 m | 3.35 m | 3.60 m |
| Share of pixels within the CATZOC C allowance, gbm · Stumpf | 88% · 75% | 78% · 63% | 79% · 66% |

- **Depth mix explains little of the gap.** Northern Beaches has the most deep
  pixels, but with every band weighted equally it still has the largest error.
- **Reef share explains much of it.** On sediment alone the three sites lie
  within 0.35 m of each other; Northern Beaches' pooled error is high because
  more than half its assessed seabed is reef, which reads deeper than sediment
  at every site. Its reef is not worse than Jervis Bay's.
- **Reef and exposure cannot be separated here:** Northern Beaches' reef is
  the exposed rock platforms and headlands, and the reef layer says nothing
  about cover (kelp, urchin barren, bare rock).
- The open coast has no mapped seagrass; the macrophyte layer maps estuaries.

### Exploratory: depth-standardised block test

Defined after the registered Phase 4 result and one rough look at a partial
correlation (+0.61, +0.40, +0.53), and committed before it was run. Each
block's error is compared with what its depth mix predicts from the site's
other blocks, in 1 m bins. A link beyond depth is *supported* only if the mean
correlation's interval lies above zero and no site is negative. Run once, with
no block dropped. `outputs/exploratory/`.

| Stumpf | Registered: red against RMSE | **Red against depth-standardised error** | Depth against RMSE → depth against standardised error |
|:--|:--|:--|:--|
| Jervis Bay (48 blocks) | +0.52 | **+0.55** [+0.29, +0.74] | +0.62 → +0.16 |
| Northern Beaches (20) | +0.70 | **+0.22** [−0.31, +0.75] | +0.71 → +0.09 |
| Batemans Bay (12) | −0.18 | **+0.44** [−0.30, +0.96] | +0.64 → −0.22 |
| **Mean of within-site** | +0.35 [+0.09, +0.59] | **+0.40** [+0.10, +0.66] | |

gbm: +0.58 [+0.31, +0.77], +0.14 [−0.40, +0.63], +0.29 [−0.45, +0.83]; mean
+0.34 [+0.02, +0.60].

Read by the rule written beforehand: **supported, for both models.** The
standardisation did its job (the tie between block depth and block error fell
from +0.6 to +0.7 to between −0.22 and +0.16), and the registered test's
disagreement between sites was depth mix, in the two directions the confound
predicted. But only Jervis Bay's own interval excludes zero; the test was
defined after the registered result had been seen; and red reflectance also
rises with foam, surface roughness and exposure. Prediction 3 still failed and
gate 4 is still not met. The sentence the write-up uses: within a scene,
blocks with higher red reflectance tend to have larger errors than their
depths predict (exploratory; mean rank correlation +0.40 [+0.10, +0.66] across
three sites, clear at Jervis Bay alone). It is a lead for a registered test on
new scenes, not a finding about turbidity.

### Phase 4 conclusion (Warren van Ryn, 19 Nov)

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
only 11% of Northern Beaches' assessed pixels, and GBM performs worse there
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
|:--|:--|:--|
| Reference (IHO Order 1b) | ±0.52 m at 10 m, ±0.56 m at 20 m | TVU = √(a² + (b·d)²), a=0.5, b=0.013, 95% |
| Reference horizontal | 5 m + 5% depth ≈ 5.5 m | Sub-pixel at 10 m S2 |
| SDB error | Unknown at the outset | The quantity being measured: 1.9 to 3.0 m RMSE as found |
| Water level correction | **−0.392 m AHD measured**: gauge ±20 mm (code 55), timing ±2 min × 0.12 m/h ≈ ±4 mm, 1-minute noise ~1 cm (11-minute mean −0.394). The provisional image estimate was −0.496 | A constant error is absorbed by the Stumpf intercept; it moves depth bands, masks and anything reported against AHD. Moving from −0.496 to −0.392 changed pooled RMSE by 0.02 m |
| Water level, sites 2–3 | Northern Beaches **+0.501 m AHD** (Sydney); Patonga reads 0.04 m higher, taken as the uncertainty. Batemans Bay **−0.181 m AHD** (Princess Jetty, ~3 km up the Clyde: ~22 min tidal lag ≈ 0.04 m at the overpass) | Same role as at Jervis Bay: a constant is absorbed by the fit; it moves bands and masks. The image estimate was 0.01 m off at Northern Beaches and **0.70 m off** at Batemans Bay |
| Co-registration, sites 2–3 | Northern Beaches E −0.43 ± 0.32, N −3.47 ± 0.14 m; Batemans Bay E +2.95 ± 0.62, N −4.91 ± 0.09 m (1.5 km windows); both measured on 7 windows and removed | Standard errors under 1 m: minor, as at Jervis Bay |
| **Clarity metric** | Site medians 0.0022–0.0053 in red reflectance; the protocol's own caveat is "a few thousandths may be atmosphere"; 10% of Northern Beaches' pixels sit on the product floor (0.0001) | The metric cannot rank sites. Within a scene it ranks blocks, but block depth mix confounds the registered test (*Phase 4 result*) |
| **Co-registration** | 7.5 m measured and removed; residual ±1.0 m E, ±1.1 m N (1σ), plus ~1.5 m possible datum offset in the reference imagery | On a 1:10 seabed slope 1 m of misregistration is 0.1 m of depth: a minor term once measured |
| Sub-pixel relief | Median 0.01–0.09 m, p90 ≤ 0.24 m by depth band | Standard deviation of the 5 m cells inside each 10 m pixel. Minor except on reef edges; kept for stratification. **Suppressed at Jervis Bay by the portal's averaging (below)** |
| **Reference processing (ELVIS averaging)** | Jervis Bay only: 0.13 m RMS at 10 m in 0–20 m (+0.05 m mean, p99 0.52 m), surface displaced 2.5 m S and 2.5 m W; measured on the averaged and native Northern Beaches extracts | Moves Jervis Bay's RMSE by < 0.01 m in quadrature. Phase 4 measures its effect on every statistic directly. Sites 2 and 3 are native |
| **Seabed change between survey and scene** | **The main constraint** | See below |

The reference is 2.5 to 4 times more precise than the error being measured,
except in the top 2 m, where SDB is most accurate and the reference's
uncertainty and the method's error converge.

**Temporal pairing is the design constraint.** The survey spans 8 July to
3 October 2018 and sandy nearshore seabed moves, so each site was paired with
the scene closest to *its own block's* capture date.

For Jervis Bay this largely resolved itself: every block over the AOI was
flown on 8–9 September 2018, and the chosen scene is 7 September, one day
before the survey, so seabed change is a minor term here rather than the
dominant one.

Batemans Bay pairs as closely (scene 23 Aug, block 24 Aug). Northern Beaches
does not: the nearest clean scene is 27 Sep, nine days after its block was
finished, on a surf coast. Its 0–5 m results carry that, with the wave record
between the two dates reported beside them.

## Decision gates

| Phase | Gate | On failure |
|:--|:--|:--|
| 1 | Seabed visibly resolvable in the scene; lidar and imagery align | Try another scene or date before touching the method |
| 2 | Site 1 RMSE within about twice the literature (below about 4 m) | Diagnose water level, glint and atmospheric correction, in that order; no tuning |
| 3 | Blocked result within about 30% of the random split | If not, the random-split number was the illusion; report both |
| 4 | Sites 2 and 3 produce a monotonic relationship between error and clarity | If not, that is itself the finding, and it is reported. **Not met, 16 Nov** |

Gates 1 to 3 passed; gate 4 was not met.

## Limitations (Warren van Ryn, 19 Nov)

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

## What this is not

Not a navigation product, a hydrographic survey, a replacement for multibeam
or lidar, or an operational service. The reference lidar's own metadata says
it should not be used for navigation without further processing; that applies
with more force to depths estimated from it.

## Write-up

**Outputs.** One Markdown source, `paper/paper.md`, builds two products with
`paper/build.py` (Pandoc with citeproc for both; Typst for the PDF):

- a web page, `docs/index.html`, served by GitHub Pages, which opens with a
  plain-language layer for a non-specialist (the answer, a summary of 137
  words, three numbers, the main figure and the limitations panel) and then
  carries the paper in full;
- a two-column A4 PDF in conference layout, `docs/sdbNSW_paper.pdf`, about ten
  pages with references.

Figures come from `scripts/figures.py`, one script and one style, reading the
committed records and the pipeline's rasters. The maps were planned as a
PyQGIS layout and were drawn in matplotlib instead, so that every figure is
reproducible from one command; QGIS supplied the basemap (its bundled Natural
Earth layer, public domain).

**Titles.** Paper: *Satellite-derived bathymetry on an exposed temperate
coast: a pre-registered accuracy assessment against airborne lidar at three
New South Wales sites.* Web page: *How deep can a satellite see off the NSW
coast?*, with the answer beneath it. The project began as a comparison with
tropical studies; as completed, that literature is the benchmark and the gap,
not the subject, and any comparison with it accounts for validation design.

**Rules the paper keeps.** Every number carries its interval and its unit of
replication (blocks, not pixels). Confirmatory and exploratory results are
never mixed: a predictions scorecard lists every registered prediction and
gate, held or failed, and a table lists every deviation, amendment and
correction. Failures are reported at the same size as successes. Literature
figures are quoted with their validation design, and every reference was
checked against its source before it was cited.

**House style**, for the paper, the page and every repository document:
Australian spelling; no em-dashes; en-dashes only in numeric ranges; specific
words over stock phrases; no inflated claims about the importance of a method
or result. The registered protocols in `protocols/` are the exception: they
are kept exactly as committed.

**AI assistance.** The paper's statement, signed off on 19 Nov:

> This study was planned and run by the author with Claude (Anthropic) as an
> agentic assistant. The agent worked in a cloud workspace connected to the
> author's workstation through Model Context Protocol (MCP) servers, which
> gave it a shell and file access within the project folder and access to a
> local QGIS instance for querying web map services. It wrote most of the
> code and its 282 automated tests, parsed the data services, and drafted
> protocol and documentation text. The author framed the question, chose the
> sites, obtained the lidar and gauge records, checked image registration
> visually in QGIS, made each methodological decision, ran every analysis
> step and reviewed its output, and wrote the interpretation, which was
> revised after review against the outputs. Each protocol was committed
> before any model was fitted, and every change and error, the agent's
> included, is logged with its date in the repository's decisions register.

The longer, first-person version is "How this was built" in `README.md` and
at the foot of the web page.

**Portfolio card.** Replaces *Revealing the Ancient Murray via REM*:
"Pre-registered accuracy assessment of satellite-derived bathymetry at three
NSW coastal sites (a sheltered bay, an exposed surf coast and an estuary
mouth) against IHO Order 1b airborne lidar, with spatially blocked
validation. RMSE 2.7–3.0 m for the band-ratio method and 1.9–2.5 m for
gradient boosting over 0–20 m, with error by depth band and seabed type, and
the depth at which each method breaks down." An earlier draft claimed a
water-clarity gradient and a sea-state stratum; neither survived the results.

## Repository structure

```
sdbNSW/
├── README.md                  the result, and how to read, check and cite it
├── PROJECT_BRIEF.md           this record
├── BUILD_GUIDE.md             reproduction guide: every result, figure and the paper
├── LICENSE                    code MIT; paper and figures CC BY 4.0
├── environment.yml, pyproject.toml, requirements.txt
├── protocols/                 the registered protocols, verbatim, with their commits
├── src/sdb/
│   ├── stac.py                scene discovery and ranking
│   ├── glint.py               Cox and Munk glint index from ERA5 wind (selection only)
│   ├── fetch.py               quicklooks; the reflectance stack over the site
│   ├── ortho.py, coreg.py     image geolocation measured against orthoimagery on land
│   ├── waterlevel.py          water level at the overpass from MHL gauges
│   ├── reference.py           exact area-weighted lidar onto the scene grid; masks
│   ├── sdb.py                 the Stumpf ratio and its calibration rule
│   ├── ml.py                  gradient boosting on per-pixel image features
│   ├── validate.py            blocked cross-validation, statistics, breakdown depth
│   ├── substrate.py           seabed classes for grouping errors
│   ├── clarity.py             the clarity metric and the within-site block tests
│   └── viz.py                 diagnostic figures
├── tests/                     282 tests, mostly against analytically known answers
├── scripts/
│   ├── figures.py             the paper's and page's figures
│   ├── freeze_protocols.py    copies each protocol from its registering commit
│   ├── dem_extracts.py        detects portal-averaged lidar; joins native boxes exactly
│   ├── calibration_form_check.py, check_wind_sources.py   one-off checks cited in the register
├── config/sites.yml           extents, tide gauges, the open-sea point
├── data/
│   ├── README.md              how to obtain each input, and its licence
│   ├── reference/             committed: survey block index and footprints
│   └── raw/                   not committed: downloads, scenes and rasters
├── outputs/                   every result record (JSON) and diagnostic figure
├── paper/                     paper.md, references, templates, build script, reference check
└── docs/                      the published web page, PDF and figures
```

The code follows the conventions of the author's `seismicPython`: an
importable package under `src/`, no input or output inside the mathematics,
and tests against analytically known answers.

## Decisions register

Every decision with its date and reason, including reversals and errors, as
recorded at the time; where a later entry corrects an earlier one, both stand.
Entries were written in the working voice of the project and have been edited
only for voice and punctuation. "The agent's error" marks a fault in code or
text the AI agent wrote; decisions credited to Warren were his.

| Date | Decision | Why |
|:--|:--|:--|
| 27 Sep | Reference ordered in native **GDA2020 / MGA 56 (EPSG:7856)** | Any reprojection resamples the reference surface. GDA2020 also sits within centimetres of the ITRF frame Sentinel-2 uses; GDA94 is ~1.8 m off |
| 27 Sep | Delivered DEM verified | 5 m, AHD, IHO Order 1b per supplier metadata. −42.7 to +166.6 m. **95.6 km² in 0–20 m** (~955k cells at 10 m). Mosaic of blocks flown 8 and 9 Sep 2018. Laser reached 42.7 m, the top of the stated 20–40 m range, so the water is clear |
| 27 Sep | **Aggregate lidar onto the S2 10 m grid**; never upsample imagery | Upsampling invents spatial detail and flatters the error. Aggregating four 5 m cells also reduces reference noise |
| 27 Sep | AOI straddles MGRS **56HKG / 56HLG**, no common date. 56HKG covers 100%; 56HLG only the eastern part. **All 56HLG scenes rejected**, including the same-day 8 Sep scene | A scene covering part of the bay cannot validate the bay. Partial coverage is a hard rejection, not a score penalty |
| 27 Sep | Duplicate processings collapsed; prefer baseline **05.00** (Collection-1) | Same datatake published twice. Collection-1 is consistently reprocessed. Its −0.1 BOA offset is applied at fetch and verified against water physics (red/NIR medians near zero). **Corrected 1 Oct** (below): on Earth Search the offset is already in Collection-1 pixels |
| 27 Sep | Scene: **`S2A_56HKG_20180907_0_L2A`**, 2018-09-07 00:02 UTC, one day before the lidar | AOI cloud 0.55% despite 36.4% tile cloud; calm inside the bay, seabed visible along the shallow margins. **12 Sep rejected** on inspection: wind-roughened surface, glint streaks across the bay, resolved wave texture offshore, with near-identical sun geometry (facet 23.4° against 24.3°), so the difference is wind, which the glint heuristic cannot see. **17 Sep rejected**: cumulus and shadow over the bay (3.6% AOI vs 1.2% tile). Tile cloud misled in both directions |
| 27 Sep | Accept baseline **00.01** for the chosen scene | No Collection-1 version exists for 7 Sep. Departs from the 05.00 preference; scene quality outweighs processing preference. No BOA offset applies; the conversion is verified by the water plausibility check at fetch |
| 27 Sep | Stratify site-1 error **inside-bay vs open coast** | The outer coast east of Beecroft is visibly rougher than the sheltered bay in every candidate, and both lie in the 0–20 m envelope: an exposure gradient within a single scene |
| 27 Sep | **Wind disagreement resolved: the model, not the hour.** The first pull used Open-Meteo's default `best_match`, which here is **ECMWF IFS 9 km** (cell −35.044, 150.687); `stac.py` requests **ERA5 0.25°** (cell −35.000, 150.750). Same hour, so no time-zone slip. 12 and 17 Sep: the two agree (NNE, within 0.6 m/s and 13°). **7 Sep: 0.86 against 3.58 m/s**: the overpass (10:02 local) falls while the morning north-westerly is dying ahead of a north-easterly; ERA5 puts the lull at the overpass, IFS about two hours later. Direction agrees throughout. Evidence: `scripts/check_wind_sources.py` | Earlier on 27 Sep this register read "speed prediction falsified; direction explains the glint", built on one pull whose defaults were not recorded. Neither that nor the reverse is established: 7 Sep wind at overpass lies somewhere in 0.9–3.6 m/s. **Lesson: pin every parameter of an API call a decision rests on; a default is a hidden parameter** |
| 27 Sep | What survives both sources: **12 Sep is the most glint-prone** of the three: slope needed to glint 3.7σ (ERA5) / 3.9σ (IFS) vs 4.5–6.4σ for the clean scenes. Scene choice unaffected | The only discriminating observation. 7 and 17 Sep were both clean, so their order is untested |
| 27 Sep | **ERA5 stays the default wind source** (`models=era5`, pinned) | Reanalysis: one consistent system for every date and all three sites, citable. IFS resolves the coast better but is an archive of operational forecasts whose model changes over time, from 2017 only. Neither is validated here; a station record (e.g. BOM Point Perpendicular at the bay entrance) would arbitrate if a decision ever hinged on it |
| 27 Sep | **The glint index flags; it does not rank close calls.** The choice of source alone moved 7 Sep from 4.5σ to 6.4σ | Treat scenes whose `glint_sigma` differs by less than the between-model spread (~2σ at a transition hour) as indistinguishable. A second-source option for `stac.py` is deferred to site 2, when a choice may actually depend on it |
| 27 Sep | Wind-aware glint index in scene discovery (`glint.py`, on by default, `--no-wind` to skip), reported as **`glint_sigma`**, the slope needed to glint in standard deviations (lower is more glint-prone). **Reported, never scored** | The first version reported glint relative to the calmest scene: near calm the Gaussian tail gives ~10⁻¹⁶ reflectance and the ratios reached 10⁷, which is meaningless. Sigma is bounded, monotonic and readable. Winds below 1 m/s are evaluated at 1 m/s, so sigma is then a lower bound. Out of the score: one discriminating observation does not justify a weight. Fails soft if the API is unreachable; refuses km/h (the API default) |
| 27 Sep | Lidar grid **does not nest** in the S2 10 m grid: origin E 286500.454, N 6127921.421, pixel 5.000000011 m. **Aggregate by area-weighted average** onto the scene grid, not 2×2 block means | Offset (0.45, 1.42) m from a 5 m lattice, consistent with a round GDA94 grid shifted to GDA2020 by editing the georeferencing, not resampling (good: values untouched). Block means would misplace the reference by up to 1.4 m. GDA2020 against WGS84 at the 2018 epoch is ~0.1 m, which is negligible |
| 27 Sep | **Co-registration is measured, not assumed.** Estimate the image-to-lidar shift before any depth comparison; the Phase 1 alignment gate becomes a number | ESA's July 2018 L1C quality report: S2A absolute geolocation ~12 m at 95%, no ground control. GRI refinement (8 m at 95%) arrived with baseline 03.00 and the Collection-1 reprocessing; the chosen scene is baseline 00.01, so unrefined. Up to a pixel of misregistration would dominate error on slopes. If the shift cannot be measured confidently, fetch the Collection-1 version from Copernicus Data Space instead |
| 27 Sep | **Glint index passed a prediction test.** Predictions committed in `e5955e7` before viewing: 22 Oct (2.6σ) glint, 28 Aug (3.4σ) glint, 18 Aug (5.0σ) clean. Quicklooks: all three as predicted | Across six scenes glint shows at ≤3.9σ, clean water at ≥4.5σ. Tentative rule for sites 2–3: **below ~4σ expect glint**. Six scenes in one bay: a rule of thumb, not a calibration |
| 27 Sep | **Aggregation by exact per-axis overlap areas**, not GDAL resampling | PROJ treats GDA2020 → WGS84 here as a null operation (checked at run time: 0.1 mm), so the lidar lies in the scene's plane, offset 0.454 m E / 1.421 m N. Exact, GDAL-version independent, and cheap enough (0.5 s) to repeat at every trial shift. Tested against closed forms: a plane averages to its centre value, a step to its area fraction. 91.6 km² usable in 0–20 m against 95.6 km² at 5 m; the difference is shoreline-mixed pixels, cloud and flags |
| 27 Sep | **Misregistration measured: E −18.5 ± 2.9 m, N −11.1 ± 5.8 m (21.6 m, ~2 px), applied provisionally.** Image features are drawn ~18 m east and ~11 m north of where they are | Steep shores only (waterline ≥30°): 7 segments, all on Beecroft Peninsula; Bowen Island and the southern headlands are fringed by rock platforms (median waterline slope 10°), which the filter correctly excludes. Independent all-shoreline cross-check: (−17.0, −5.3); correlation 0.613 → 0.684. Supporting diagnostics: shifting halves the land pixels that read as water; the opposite shift makes both measures markedly worse. About twice ESA's 12 m (95%) figure: large, but supported by two estimators. **Provisional** because no steep shore faces north or south: re-estimate with gentle shores admitted once the tide is known |
| 27 Sep | Cross-check agreement rule: per component within max(3 m, 2 × steep-shore stderr) | Conventional 2σ with a floor. Codified *after* an exploratory all-shore run on this scene, so not blind, but not tuned: the scene passes by a wide margin (E 1.5 of 5.8 m, N 5.8 of 11.6 m) |
| 27 Sep | Why steep shores only, **shown, not argued**: synthetic island, true shift 8.4 m, tide assumed 0.6 m too high | Steep-only estimate 0.7 m out. All-shore estimate 5.0 m out *and called the shift negligible*: the tide error on beaches nearly hid a real misregistration. Pinned in `tests/test_coreg.py` |
| 27 Sep | **The tide was below 0 m AHD at overpass.** The image prefers a water level of **~−0.45 m AHD** (all-shore correlation peaks there, with or without the shift), and 73% of 0–1 m pixels read bright in NIR at 0 m whatever the shift | Prediction for `waterlevel.py`: the gauge should read about **−0.3 to −0.5 m AHD** at 00:02 UTC 7 Sep 2018, because NIR sees through the first ~0.2 m of water, so the image estimate is biased slightly low |
| 27 Sep | **QGIS gate: the 21.6 m co-registration is wrong. Superseded.** Screenshot pairs at identical extents, cross-correlated here (four preprocessing variants each). Airfield: S2 − NSW Imagery **E +7.0, N +3.7 m**; S2 − ESRI E +9.0, N +3.0; ESRI − NSW −1.3 to −2.4 E, ~+0.5 N: the three agree closely. Huskisson (noisier, roofs): S2 − NSW E +4.6 to +8.2, N +1.1 to +5.2; ESRI − NSW ≈ −2 m again | True misregistration ≈ **E −6.5, N −3.5 m (≈ 7–8 m, ±~2 m)**, within ESA's 12 m (95%). NSW Imagery is authoritative but may be served with GDA94 treated as WGS84, a ~1.5 m ambiguity; ESRI agrees with it to ~2 m. The shift applied to `reference.tif` (−18.47, −11.11) is ~14 m wrong, worse than none. Nothing downstream used it |
| 27 Sep | **Why the waterline method failed: its biases all pointed east in this scene** | West-facing cliffs are in shadow under a north-easterly sun, so their image edge reads landward (east). East-facing ocean cliffs carry whitewater at the base, so their edge reads seaward (east). The bay's long beaches mostly face east, so a low tide and NIR seeing through the first ~0.2 m of water push their edge seaward (east). Different mechanisms, one direction. The QGIS view shows the shadow band directly |
| 27 Sep | **Lesson: agreement between two estimators that share a signal is not independence** | Steep-shore and all-shore estimates agreed (−18.5 vs −17.0 E) and the agent treated that as confirmation. Both read the same water edge and inherited the same biases. The test that caught it used a different signal entirely: land features against an independent orthophoto. The gate worked because it was a different kind of check, not a second opinion from the same kind |
| 27 Sep | **Proposed: co-register against reference orthoimagery, on land**, with the waterline method demoted to a diagnostic | Fetch NSW Imagery windows through its public ArcGIS REST `export` endpoint directly in EPSG:32756; aggregate to 10 m; sub-pixel phase correlation against S2 over several land windows spread across the scene (runways, roads, clearings, towns); median shift, window scatter as the error bar. Licence to be confirmed before use. **Awaiting approval** |
| 27 Sep | **Co-registration rebuilt on orthoimagery: E −7.42 ± 0.98, N −1.02 ± 1.14 m (7.5 m), applied.** 11 automatically chosen 2 km land windows; 8 agree (scatter E 2.2, N 2.6 m), 1 outlier dropped (+15 m E, Booderee), 2 rejected for weak correlation (forest) | Exact area aggregation of 2 m orthophoto onto the scene grid at each trial shift, gradient correlation, coarse-then-fine search. Recovers synthetic shifts to <0.7 m under different radiometry, blur and noise. East matches the screenshot check (−7.0 at the airfield); north is smaller than it suggested (−1.0 vs −3.7), within ~2σ, and rests on eight windows rather than two |
| 27 Sep | Orthoimagery used as a **positional reference only** | Licence is unclear for images (catalogue CC BY 3.0 AU; Spatial Services' copyright page excludes images; parts are third-party). Tiles stay in gitignored `data/raw/ortho/`, only numbers are committed, and figures show Sentinel-2 NIR, never the orthophoto. Fetch uses the standard library only, so it also ran inside QGIS's Python to test it on real data |
| 27 Sep | **Tide gauge found in the bay**: MHL 216470, Jervis Bay at HMAS Creswell, radar since 1989, AEST, chart datum with AHD offset −1.07 m | Historical data by request (CC BY 4.0). Not in the Bureau's Water Data Online; MHL's web predictions only reach back 90 days. The 2018 record must come from MHL |
| 27 Sep | **Datum inferred from the numbers, not the label** | MHL's own pages label chart-datum values "m AHD" (live chart: 1.66, above the 1.36 m AHD flood of record) and an AHD table "Chart Datum". MSL 2018-19 is +0.074 m AHD = +1.144 m CD, so a record's mean identifies its datum; ambiguous means refuse |
| 27 Sep | **Provisional water level −0.50 m AHD** from the image (whole-shoreline NIR vs lidar land fraction, co-registration applied) | Consistent with a near-spring low: new moon 9 Sep; MLWS 2018-19 is −0.515 m AHD. Biased low by ~0.1–0.2 m (NIR reads through very shallow water), so the gauge should read about −0.3 to −0.4 m. Estimator exact on curved synthetic shorelines; worst case one straight grid-aligned beach, ~6 cm |
| 27 Sep | **Phase 2 does not wait for the gauge** | A constant water-level error is absorbed by the Stumpf intercept; it moves depth-band membership and masks. Re-run `reference` when the gauge value arrives and report both |
| 27 Sep | Glint geometry: closed form `cos(2ω)=…` **replaced** with the vector derivation | The closed form is wrong off the principal plane (~0.8° at θs=20°, θv=30°, Δφ=90°). Immaterial at S2's near-nadir view, but wrong. Pinned by a grid test against an independent derivation |
| 27 Sep | **Phase 2 protocol pre-registered** before any depth model sees real data. Pre-fit checks deliberately did **not** look at the band ratio against depth | The co-registration lesson: a rule set after seeing the data is not blind, however honest. Every choice that could be tuned to the answer (calibration range, sample, blocks, thresholds) is fixed by rule in advance, and data-driven choices are made inside each training fold |
| 27 Sep | **No glint correction for v1.** Optically deep water (> 25 m, 197,785 px): NIR detail finer than 90 m has std 0.0012 and blue follows it at slope 0.78 (R² 0.28): glint-like, but ~0.001 in blue, ~4% of the median. The covariance between blue and NIR a Hedley regression would fit is dominated by a **km-scale field** (810 m means: slope 4.9, R² 0.93) | Glint is spectrally near-flat, so a slope of ~5 is water type or atmosphere, not glint: Hedley would subtract real signal. The only lidar-covered deep water is at the entrance and outer coast, a different water mass from the bay. Sentinel-2's band-to-band timing also decorrelates pixel-scale glint (Harmel et al. 2018) |
| 27 Sep | **Depth-balanced calibration and reporting** | 70% of usable pixels are 10–20 m, 2.7% are 0–2 m. Unweighted, both the fit and the headline RMSE would describe the deep, weak-signal end |
| 27 Sep | **Breakdown threshold: CATZOC C**, not an invented one | An external charting standard (2.0 m + 5% of depth at 95%) that a hydrographer recognises. CATZOC B alongside. The curve is published so a reader can apply any other |
| 27 Sep | **Red/green switching model left out of v1** | It improves 0–5 m (Caballero & Stumpf 2019); the question is where the method stops working, which the blue/green ratio sets. Added later only as exploratory |
| 27 Sep | **Inside bay vs open coast defined by polygon**, checked by water connectivity | A first rectangle split mislabelled Wreck Bay and Summercloud Bay (south-facing ocean coast at the scene's southern edge) as bay. The polygon crosses water only on the entrance line (Point Perpendicular, Bowen Island, Governor Head): 823,009 bay vs 114,490 open-coast usable pixels (2,623 open-coast in 0–2 m) |
| 27 Sep | **2 km blocks** | 67 blocks with usable pixels; 4 km leaves 24, and 1 in 20 random fold draws then gets almost no 0–2 m pixels. Deep-water blue varies on km scales, so blocks must be ≥ 1 km; the correlogram checks it |
| 27 Sep | **Bright-NIR flag removes 32% of 0–2 m pixels** (11,717 of 36,842): kept, but reported | The 0–2 m result therefore describes calm, non-breaking water. Stated with the denominators, not hidden in a mask |
| 27 Sep | **Implementation note on calibration step 2**, recorded before the run: its two sentences conflict for a steadily rising curve: 95% of the rise is reached one bin early (19 m), while the second sentence says 20 m. Implemented **as written**: peak in the deepest bin = "rises throughout" = 20 m; otherwise the 95% rule. Pinned in `tests/test_sdb.py` | Not a deviation: the committed text was followed. On the real data the exception decided **46 of 50 folds**; the median ratio keeps creeping upward to 20 m even where the error curve shows saturation from ~14 m. The pure 95% rule would likely have stopped earlier. Any rerun with it is **exploratory**, reported beside the pre-registered result, not instead of it |
| 27 Sep | **Phase 2 run once, as registered: gate passed**, pooled RMSE 2.70 m [2.32, 3.15]. Full table under *Phase 2: the band ratio at Jervis Bay* | Code written and tested on synthetic data after commit `8332154`, then run on the real pairs. The pattern is the model's, not the validation's: in-sample band biases from the all-data line match the out-of-fold ones to within 0.2 m |
| 27 Sep | **Breakdown depth = 0 m** for CATZOC C and B: the pre-registered statistic, reported as is | The rule finds the first bin that fails; here every bin fails, so its answer is "never meets CATZOC C", itself the finding. The shape (a flat ~2 m RMSE floor to ~14 m, then saturation) is described from the curve, not by inventing a new threshold after the fact |
| 27 Sep | **Residual correlation range 4 km > 2 km blocks: caveat applies**, as the protocol requires | Mostly systematic structure (depth-dependent bias, the open-coast offset and shelf-scale patches) rather than leakage: RMSE is flat across block sizes (2.67–2.73 m). The bootstrap intervals, which resample 2 km blocks, are the part most likely to be optimistic |
| 27 Sep | **Substrate candidates found; none adopted yet.** NSW DPI *Estuarine Macrophytes* covers the whole bay (Aug 2019 aerial, field May 2020; *Posidonia*/*Zostera*/*Halophila*); DCCEEW *seabed reef extent* is classified from the same 2018 lidar. GA's 2007–08 video and grabs cover only the southern bay; the 2018 lidar reflectivity is raw LAS | The seagrass map is 11 months after the scene: *Posidonia* is persistent, *Zostera*/*Halophila* are not. It is aerial-optical, so it may miss seagrass exactly where Sentinel-2 fails (deep, sparse *Halophila*); "not mapped as vegetated" is not "sand". The reef layer is independent of the imagery and contemporaneous |
| 27 Sep | **Substrate layers fetched and checked** (via QGIS; 5,937 macrophyte, 1,671 reef-extent, 1,131 reef-source polygons in the lidar extent; `data/raw/substrate/provenance.json`). Alignment: *Posidonia* fringes and *Zostera* shoals in the southern bay, and the lidar reef outcrops off the western shore, match their image edges to about a pixel. Coverage inside the bay, usable pixels at ≥ 0.5: *Posidonia* 8,935 / 21,585 / 17,055 in 0–2 / 2–5 / 5–10 m; reef 39,306 across all depths; sediment with no seagrass mapped 711,336 | Two layers together explain the dark seabed visible in the image: the dark patches off Huskisson that the seagrass map lacks are lidar-mapped reef. Seagrass mapping stops at ~10 m. Open coast: no seagrass mapped, 45% reef. The custodian's service states CC BY 4.0 (an IMAS copy says CC BY-NC); the custodian's statement is used. The reef service's layer descriptions are copied from a Wollongong multibeam dataset; the per-polygon Source field is the reliable one |
| 27 Sep | **Substrate comparison run once, as registered** (addendum committed in `73d02ce` first). Reef +1.7 m at 5–20 m; *Posidonia* ~0 at 2–10 m; 0–2 m reversed | The pre-stated direction held for reef and failed for seagrass; reported as found. Correction to the Phase 2 reading above: the agent attributed the shallow over-reading to "where seagrass is expected". The overlay shows those patches are reef, and bare sediment over-reads on its own; the likelier source is the calibration (a straight line through a saturating relationship, fitted to 20 m in 46 of 50 folds) and shallow bright-bottom effects |
| 27 Sep | **Next diagnostics are exploratory, and labelled so**: (1) the calibration with the 95% rule alone, no "rises throughout" exception; (2) shallow sediment over-reading against distance to shore and bottom brightness | Both were prompted by these results, so neither can be confirmatory. Each is reported beside the registered result, never in place of it |
| 27 Sep | **Exploratory E1–E3 run** (details under *Exploratory follow-up, Jervis Bay*). The 95%-only rule does slightly worse (RMSE 2.82 vs 2.70 m) and leaves the shallow bias in place | The drafting fault in step 2 is closed as immaterial; the registered rule stays. The bias pattern is explained by the calibration's form: depth regressed on a noisy ratio regresses toward the mean, and the ratio curve bends at ~14 m in the bay and ~8–10 m on the open coast. `validate --exploratory` and `substrate --tag` write only to `outputs/exploratory/`, so a variant can never overwrite a registered output |
| 29 Sep | **Gauge record received and checked before use.** 1-minute, complete, AHD stated in the header and confirmed by the record's mean (−0.03 m over 3 days vs MSL +0.074); AEST ±2 min and quality code 55 = ±20 mm per MHL's conditions sheet; Jervis Bay station datum adjustment 1.070 m, matching the config | The layout differed from the one the parser was written for: **Date and Time in separate columns** after a 30-line licence block. The old parser **failed loudly** (a tokenizer error), not silently. Fixed to join date and time, read the stated datum and quality codes, and **refuse if the header's datum contradicts the numbers**; pinned by a test of this exact layout. The tidal rate is now fitted over ±15 min, because with 1-minute samples the two bracketing values differ by noise as much as by tide |
| 29 Sep | **Prediction test passed: water level −0.392 m AHD** at 10:02:37 AEST (tide falling 0.12 m/h). Predicted in the register on 27 Sep: about −0.3 to −0.4 m, the image estimate biased low by ~0.1–0.2 m. Observed bias of the image estimate: **0.104 m** | The image method's known bias (NIR reading through the first decimetres of water) is now measured once. Useful for sites 2 and 3 if a gauge is missing, as a correction with a stated uncertainty rather than a guess |
| 29 Sep | **Phase 2 rerun at the measured level becomes the primary result**; the provisional run is kept beside it | The protocol said "report both". Pooled RMSE 2.70 → 2.68 m; no conclusion changes. Exploratory runs are not repeated |
| 29 Sep | **Phase 3 closed** with Warren's conclusion on blocked vs random validation (*Phase 3*) | Stumpf is the control; the prediction it makes, that flexible models will open a gap, is carried into v2 as prediction 2 |
| 29 Sep | **v2 pre-registered**: one model family (gradient boosting, fixed settings, no tuning, no early stopping), image-only per-pixel features, v1's folds and depth-balanced sample over 0–20 m, paired comparison with Stumpf; a coordinate model run only as a labelled leakage demonstration; four predictions written down first | Every choice that could be tuned to the answer is fixed before the answer exists. No tuning, because honest tuning needs nested cross-validation, whose cost and complexity are out of proportion to the question: the size of the ML advantage, not its maximum |
| 29 Sep | **v2 run once, as registered: gbm 1.88 m, 0.80 m better than Stumpf** [0.57, 1.06]; meets CATZOC C to 3 m. Predictions 1–3 held; **prediction 4 failed** | Coordinates helped even on 2 km blocks because depth itself is correlated over kilometres: the model interpolates the survey from neighbouring blocks. Recorded as a failed prediction, not explained away: it shows that block size protects only against what the model can exploit, and that the real safeguard is excluding location, as v2 did |
| 29 Sep | **Phase 3 conclusion edited** (with Warren's agreement): Australian spelling, "clean" rather than "perfect" control, and the correlation and block-size evidence added | The claim that the model *could not* use leakage is stronger with the evidence that the data offered it |
| 1 Oct | **Site 2 sized by the validation design, not the place name.** The first ELVIS clip (the requested 1.7 × 5.15 km Narrabeen to Collaroy box) held 4.1 km² of 0–20 m water in 3–4 two-km blocks, fewer than five folds. Re-ordered across the SydneyNorth block (NSW020302) | Same code at every site means each site must fit the design. The block's ends lie in the SydneyHarbour (flown 18 Aug) and BrokenBay (24 Aug) rasters, a month before SydneyNorth (18 Sep), so the AOI is the single-date window between them: Queenscliff to Palm Beach |
| 1 Oct | **ELVIS averages any extract that spans more than one survey block ("Average 16").** The whole-block Narrabeen extract is exactly a 4×4 mean of the native cells (321,291 cells, zero difference), centred half a cell off: smoothed over 20 m and displaced 2.5 m S and 2.5 m W. At 10 m in 0–20 m it differs from native by 0.13 m RMS (+0.05 m mean, p99 0.52 m). Native values sit on a centimetre lattice (97–99% of underwater cells); averaged ones do not (~10%, i.e. chance) | Orders kept inside one block's raster come back native: Northern Beaches is bit-identical to the first clip on 327,640 cells, and both Batemans Bay boxes pass. `scripts/dem_extracts.py` checks any delivery, and joins boxes of one block only where every overlapping cell is identical |
| 1 Oct | **Jervis Bay's reference is mostly ELVIS-averaged** (257 of 299 one-km tiles; native only in a ~5 × 8 km Beecroft patch). Headline results stand: 0.13 m of reference error in quadrature moves 2.68 and 1.88 m by < 0.01 m. **Its relief terciles are compromised**: averaging suppresses within-pixel spread everywhere except the Beecroft patch | Disclosed rather than re-ordered: a native Jervis Bay needs five block orders joined by hand, for an effect inside the intervals. Phase 4 measures the effect directly (sensitivity run). The 27 Sep "delivered DEM verified" check covered range and units, not resampling; that check is now a script |
| 1 Oct | **Scene search: scene-wide nodata applies only when an item has no footprint**; measured AOI coverage decides. The candidates table is written even when nothing passes | At Sydney both orbits clip tile 56HLH (14–20% nodata), which rejected all 36 acquisitions, and the empty result left no table to show why. At Batemans Bay a 100%-coverage, 0.4%-cloud scene had been rejected the same way. No Jervis Bay row was rejected on nodata alone |
| 1 Oct | **Site 3: Batemans Bay. Richmond River rejected** | Screened on quicklooks before any lidar was ordered. Richmond's plume is a small patch at the mouth, and the mouth sits on the seam between ByronBallina (4 Aug) and Broadwater (8 Jul), 27 days apart. Batemans Bay is one block and one date, shows the Clyde plume across the inner bay, and has an AHD gauge |
| 1 Oct | **Scenes: Northern Beaches 27 Sep (9 days after), Batemans Bay 23 Aug (1 day before)**, by the site-1 rule. 28 Aug at Batemans Bay was proposed for its turbid look and declined | The quicklook panels are stretched per channel to each scene's own water, so their colour cannot rank turbidity; 28 Aug also had 5 m/s wind and wave texture across the outer bay. Choosing scenes for turbidity would build the gradient into the sample |
| 1 Oct | **Earth Search Collection-1 pixels already have the BOA offset removed.** Items carry `earthsearch:boa_offset_applied: true` while `raster:bands` still declares −0.1; trusting the latter subtracted it twice (Northern Beaches water red −0.096), and the water-physics check refused the stack. The item flag now wins over a contradicting `raster:bands`; the check still arbitrates | **Corrects the 27 Sep entry** on Collection-1 offsets, which had never met a real Collection-1 pixel. Jervis Bay used baseline 00.01 (flag false, offset 0, water red +0.0039) and is unaffected. Both new scenes pass (red +0.0036 and +0.0053) |
| 1 Oct | **Batemans Bay lidar in two native boxes**, joined without resampling (overlap 881,967 cells, bit-identical) | A whole-block order touches the MoruyaCoast and Murramurang rasters and would be averaged. Cost: the far north-east corner by Murramurang |
| 1 Oct | **Co-registration window fallback: 2 → 1.5 → 1 km until at least four windows agree**, other thresholds unchanged. Northern Beaches, 2 km: E −0.43, N −3.47 m (7 windows, scatter 0.7 / 0.3 m). Batemans Bay: 3 windows at 2 km, which is insufficient, then at 1.5 km E +2.95, N −4.91 m (7 windows, scatter 1.3 / 0.2 m). Both applied | Batemans Bay's AOI is half water; 2 km tiles that are 90% land and 3 km apart fit only three, all in one corner, unable to test that the shift is rigid or to catch an outlier. Written after seeing that, but it concerns land area, not depth errors. Both new scenes are Collection-1 (geometrically refined) and shift 3.5–5.7 m, against Jervis Bay's 7.5 m on unrefined 00.01 |
| 1 Oct | **Provisional water levels from the image:** Northern Beaches +0.49, Batemans Bay +0.52 m AHD. `waterlevel --from-image` no longer requires gauge constants | Superseded when the gauge records arrive. On surf beaches whitewater may bias the image estimate beyond Jervis Bay's 0.10 m |
| 1 Oct | **Gauges: Sydney 213470 (primary) and Patonga 212440 (cross-check) for Northern Beaches; Princess Jetty 216410 for Batemans Bay. Not Ocean Street Bridge (213408D)** | The two ocean-connected gauges bracket the site, so their difference is a measured uncertainty. Ocean Street Bridge records Narrabeen Lagoon, whose entrance damps and delays the tide |
| 1 Oct | **Phase 4 protocol pre-registered** before any fit at sites 2 or 3 | Eligibility from the lidar and dates, clarity from the image, the scene and gauge rules, four predictions and two sensitivity runs, all fixed first. The within-site block test is the inferential core, because three sites cannot separate clarity from everything else that differs between them |
| 1 Oct | **Phase 4 code written after the protocol commit `a5b5f5d`, tested on synthetic data only**: `clarity.py` (metric, block table, Spearman with block-resampled intervals, mean of within-site correlations, gate 4, the four predictions evaluated as written); `reference --dem/--tag` and `validate --reference-tag` for sensitivity runs, which can only write tagged files and `outputs/sensitivity/`; `validate` exits without fitting below 15 blocks | Same order as Phase 2: protocol, then code, then real data. A test pins the design's reason for the within-site mean: two sites that differ only in level give a pooled Spearman above 0.7 and a within-site mean near 0. Another pins that a sensitivity run leaves the registered outputs byte-identical |
| 16 Nov | **Substrate layers fetched for Northern Beaches and Batemans Bay**, before any `validate` run, as the protocol allows. Same queries and class rules as Jervis Bay; one GeoPackage per site (`substrate_<site>.gpkg`, with `provenance_<site>.json`). Northern Beaches 1,404 macrophyte, 1,781 reef-extent, 475 reef-source polygons; Batemans Bay 718, 1,901, 1,469 | Macrophyte mapping dates differ by water body: Pittwater August and September 2018 (contemporaneous), the lagoons 2008, Batemans Bay/Clyde 2012–2022. New classes (*Posidonia*, Sparse and *Zostera*, Sparse) fall under the addendum's rules unchanged. The Fisheries service now refuses Python's default User-Agent (403); a browser-style one was sent. `substrate` now defaults to the site's own GeoPackage, so a site can never read another's layers (`391c625`) |
| 16 Nov | **MHL records received and checked before use.** Sydney 213470, Patonga 212440, Princess Jetty 216410: 1-minute, 22 Aug – 30 Sep 2018 AEST, AHD in the header and confirmed by each record's mean (−0.035 to −0.049 m over five weeks, against MSL +0.05 to +0.065), quality 55 throughout; one 17-minute gap (Princess Jetty, 02:50 AEST 13 Sep). Datum adjustments from MHL's *Data conditions* sheet (Sydney: Zero Fort Denison 1897, 0.925 m; the other two record in AHD); tidal planes from MHL's station pages, 2018–19 column | **213470 is MHL's own Sydney gauge** (151.2585, −33.8255, inside the harbour near Middle Head), **not Fort Denison** as the 1 Oct request assumed. A station recorded in AHD made the datum inference ambiguous by construction (both candidates coincide) and `waterlevel` refused it; for such stations it now checks only that the mean sits at MSL, which still catches centimetres or a wrong file. Pinned by a test |
| 16 Nov | **Water levels measured.** Northern Beaches **+0.501 m AHD** (Sydney, 10:06:03 AEST 27 Sep, falling 0.09 m/h); Patonga +0.539, a **0.038 m** difference, under the protocol's 0.10 m, so no water-level sensitivity run; the difference is reported as the uncertainty. Batemans Bay **−0.181 m AHD** (Princess Jetty, 10:06:33 AEST 23 Aug, falling 0.12 m/h) | Patonga was read with `waterlevel --gauge-key tide_gauge_check --tag patonga`, which writes only to `outputs/sensitivity/`, so a cross-check gauge can never become the level `reference` uses. Princess Jetty sits ~3 km up the Clyde; its M2 tide lags the coast by ~22 min, worth ~0.04 m at the overpass's rate. Reported as uncertainty, not corrected: the protocol named the gauge |
| 16 Nov | **The image estimate held at the surf coast and failed at the estuary.** Northern Beaches: image +0.493 vs gauge +0.501 (0.008 m low). Batemans Bay: image +0.520 against gauge −0.181, **0.70 m high**, opposite in sign to Jervis Bay's 0.10 m low bias | The 1 Oct worry was surf; the failure came from the estuary instead. Cause not investigated (no fit depends on it now). Lesson: the protocol's fallback (image + Jervis Bay's bias) would have put Batemans Bay's reference ~0.8 m wrong. The image estimate is a check on a gauge, not a substitute for one |
| 16 Nov | **Sydney wave record: no storm between the survey and the scene.** Hourly Hs, 647 of 697 hours present. 18 Sep (lidar end) to the overpass: median 1.53 m, p90 2.18 m, max 2.81 m (04:00 24 Sep, Tp 10 s, S); 1–17 Sep max 2.85 m. At the overpass Hs ~1.8 m, Tp ~15 s from the SSE | Sandbars may still have moved in nine days of ordinary swell; nothing exceptional. Reported beside the 0–5 m results as registered, no correction. A 15 s groundswell at the overpass is consistent with the bright-NIR flag removing 2.0 km² of surf-zone water |
| 16 Nov | **Phase 4 amendment: Northern Beaches open coast only** (`protocols/05_phase4_amendment.md`): Pittwater and the lagoons excluded by a named open-sea point; 21.6 km² in 21 blocks remain | The agent's error: the AOI was drawn from the block's single-date window without checking which water bodies it held, and Pittwater is a third of it. Caught while reading the substrate layers, before any fit; Warren chose the open coast only. **The first implementation was wrong too:** it took water touching the AOI's east edge, tested on synthetic grids filled to the edge; on the real grid a lidar-free margin surrounds everything, so nothing touched any edge and `reference` refused. Replaced by the seed point, and the test fixture now carries the margin. Lesson, again: synthetic tests check the logic, not the assumption about the data's shape; run on the real input before calling it done |
| 16 Nov | **Phase 4 run at both new sites** after the amendment commit `2cd2f53`: `waterlevel`, `reference`, `validate` (Stumpf, gbm, gbm_xy), `substrate`, the `elvis_avg` sensitivity pair, `clarity`. No deviation in any fit. Results in *Phase 4: three sites* | Gate 4 not met; predictions 1, 2 and 4 held (2 and half of 4 on point estimates only), prediction 3 failed |
| 16 Nov | **`clarity` corrected after its first run; both results kept.** Northern Beaches' block correlation was computed over NaN block medians ranked as the largest values (59 pixels with no red value, 13 of 20 blocks). Corrected: −0.16 → +0.70 (Stumpf); mean within-site +0.06 [−0.19, +0.33] → +0.35 [+0.09, +0.59]. First run kept as `outputs/phase4/clarity_run1_superseded.json`; the record's `deviations` says so | The agent's error, and the test suite's gap: `site_clarity` had a test with a missing value, `block_table` did not, and `spearman` ranked NaN without complaint. Both closed; `spearman` now refuses non-finite input. Caught only because the block table was read row by row before committing: 13 `null` medians beside a correlation claiming 20 blocks. **A correction that moves the headline toward the hoped-for answer needs more scrutiny, not less:** the missing-value rule it applies was written and tested on 1 Oct, before any data; treating the 59 pixels as zero gives the same answer; and nothing else in the record changes |
| 16 Nov | **The block test does not isolate turbidity**: block depth mix is correlated with block error at every site (+0.6 to +0.7) and with block red in opposite directions at Northern Beaches (+0.70) and Batemans Bay (−0.71). Block mean depth added to `clarity.json`'s block table so this can be checked from the record | A design flaw in the 1 Oct protocol, drafted by the agent: it guarded against site-level offsets and forgot that RMSE is depth-dependent inside the 10–20 m window. A depth-standardised block error should have been registered. Not repaired after the fact: the registered statistic is reported as registered, with the confound beside it |
| 16 Nov | **Exploratory addendum defined: a depth-standardised block test** (`protocols/06_exploratory_depth_standardised.md`), committed before it is run on real data. Each block's error is compared with what its depth mix predicts from the site's other blocks | Warren asked for it if it would add to the project. It does: the phase's question is whether error tracks clarity, and the registered test cannot answer it at two of three sites. It is exploratory because the registered result, and a rough partial correlation, had already been seen; the reading rule is fixed in advance so that a favourable number cannot be argued into more than it is |
| 16 Nov | **Brief checked against its stated goals before the write-up.** Kept: the question, the blocked-validation design, the "number and an envelope" deliverable. Changed: the portfolio draft no longer claims a clarity gradient or a sea-state stratum; *The question* and *Sites* now say what was and was not found; error-budget rows added for sites 2–3 and for the clarity metric | Three open items carry into Phase 5: the reference lidar is still not committed (the reproducibility promise in *Data*), and the Phase 4 conclusion and the limitations panel are Warren's to write |
| 16 Nov | **Exploratory depth-standardised block test run** after addendum commit `884dce1`: mean within-site +0.40 [+0.10, +0.66] (Stumpf), +0.34 [+0.02, +0.60] (gbm); all three sites positive; *supported* by the rule written beforehand | The registered test's site-to-site disagreement was depth mix. The result is carried mainly by Jervis Bay and concerns red reflectance, not turbidity; it changes neither gate 4 nor prediction 3. Reported as a lead, not a finding |
| 16 Nov | **Write-up standard set** (Warren): conference-paper quality, readable by a non-technical portfolio audience. Plan proposed: one document in three layers | Nothing is drafted until the limitations panel and Phase 4 conclusion exist in Warren's words and the outline is approved |
| 19 Nov | **Reference lidar published as a release asset, not committed.** The four extracts used (three references, one sensitivity) in `sdbNSW_reference_lidar_2018.zip`, 117 MB, paths mirroring the repo, attribution and md5s inside | One file over git's 100 MB limit; committed separately they would add 122 MB to every clone for a reader who almost never replicates. A release costs only the reader who downloads it. The md5s match those in the `reference` records |
| 19 Nov | **Descriptive decomposition of the site differences** (post hoc, no new fit): depth-balanced RMSE and error by substrate class per site (*Phase 4: three sites*) | Northern Beaches' higher error goes mostly with its reef share (54% of assessed pixels, against 10% and 20%); on sediment the sites are within 0.35 m. Reef and exposure are the same pixels there, so this does not separate them |
| 19 Nov | **Output format and title.** Web page and conference-layout PDF from one source. Title open: the tropical literature is the benchmark, not the subject | Warren's decisions |
| 19 Nov | **Titles set; Phase 4 conclusion revised; AI workflow statement drafted; house style set** | Warren's decisions. The conclusion keeps his argument (gate 4 is the finding; exposure and substrate matter) and corrects what the data contradict or already answer: the Stumpf ranking lies within its intervals; one scene per site; no mapped seagrass on the open coast; depth mix measured and small; reef share measured and large; the within-site lead |
| 19 Nov | **The repository is private.** The release was published, but an unauthenticated request for the repo and its releases returns 404 | Must be public before the page links to it; the release's sha256 is recorded so a reader can verify the download |
| 19 Nov | **Correction: the share of Northern Beaches' 0–2 m water lost to surf.** The *Phase 4 result* and the first revision of the conclusion said only 12% of the 0–2 m reference water was assessed, attributing the loss to surf. Recomputed from the mask: 66% of that "reference water" is Pittwater and lagoon shallows removed by the open-coast rule; of the open-coast water, 35% is assessed and 65% flagged bright. Jervis Bay 60% assessed (39% bright), Batemans Bay 82% (18%) | The agent's error, found while checking Warren's limitations panel against the outputs: `validate`'s exclusion table counted water the open-coast rule removes as reference water and did not list the rule as a reason. It now reports `not_sea` (tested); committed records are unchanged and the brief carries the corrected figures |
| 19 Nov | **Limitations drafted** by Warren and revised after review: a five-point plain panel for layer 1, and his fuller list, corrected, as the paper's Limitations section | Corrections: the shallow-water exclusion figures; the averaging check was made at Northern Beaches, not Jervis Bay; reference uncertainty is comparable only to gradient boosting's shallow error at two sites; reef bias is not beyond correction; the block-size caveat applies to gradient boosting at Batemans Bay as well as Jervis Bay. The navigation warning was checked against the lidar metadata |
| 19 Nov | **Every reference checked before drafting** (`paper/reference_check.md`); 33 entries in `paper/references.bib`, each against Crossref or the publisher, and every quoted figure against its abstract or text | Two framing claims in *The question* were wrong: SDB validation is not "almost entirely clear tropical water" (Ireland, the Aegean, Japan and Adelaide are published), and the 1.3 / 1.8 / 2.2 m benchmark is one study with an 80/20 split of unstated design. The novelty claim narrows to "no published assessment on the NSW open coast", which the searches support. Corrected before any text depends on it |
| 19 Nov | **Outline proposed** (`paper/outline.md`): about 4,300 words, six figures plus a hero figure, four tables; Pandoc and Typst build the page and PDF from one Markdown source | Approved by Warren the same day, with the author lines and a two-column PDF layout |
| 19 Nov | **Figures built** (`scripts/figures.py`, one script, one style): the hero figure, F1–F6, 300 dpi, from the committed records and the pipeline's rasters. **Maps drawn in matplotlib, not a PyQGIS layout** as planned | One style and one command for every figure, and nothing driven through a GUI. QGIS's part was the basemap: its bundled Natural Earth `world_map.gpkg` (public domain), copied through the QGIS MCP server to `data/raw/basemap/` |
| 19 Nov | **Paper drafted** (`paper/paper.md`) and built by `paper/build.py` (Pandoc with citeproc, then Typst) into the web page `docs/index.html` and the two-column PDF `docs/sdbNSW_paper.pdf`; the page carries the paper in full beneath the plain-language opening | The signed-off conclusion becomes Discussion 5.2 nearly as written; the signed-off limitations are the paper's section 6 and the page's panel; the workflow statements close the PDF and the page. Author lines as Warren gave them, the page's name linking to the portfolio |
| 19 Nov | **Two transcription errors found while checking the draft against the records.** (1) The conclusion said the 0–5 m bands hold 12% of Northern Beaches' assessed pixels: 24,388 of 216,258 is 11%. (2) The v2 result table's coordinate-model column at Jervis Bay (interval [1.13, 1.52], depth-balanced 1.26, blocked/random 1.777, 4 km 1.88, two band RMSEs) differed in the last digit from the committed record (`4be3c62`): [1.12, 1.51], 1.25, 1.774, 1.87. Corrected here; the paper uses the record | Neither changes a reading. The paper's numbers were checked against the records and this brief by script: every multi-digit number in it occurs in one or the other |
| 19 Nov | **Reference check closed.** Nechad et al. (2010) confirmed as a single-band algorithm whose best validation bands are red (665–681 nm); Pope and Fry (1997) pages 8710–8723; Hao Quang et al. (2025) entered with the family name Crossref records; Stumpf et al. (2003) issue "1, part 2" | `paper/reference_check.md` updated |
| 19 Nov | **Descriptive, post hoc: share of pixels within the CATZOC C allowance** (2 m + 5% of lidar depth), from the out-of-fold rasters. gbm 88%, 78%, 79%; Stumpf 75%, 63%, 66% | A plain-language reading of the hero figure; labelled descriptive in the paper. Not a registered statistic |
| 19 Nov | **Licence proposed: code MIT, paper and figures CC BY 4.0** (`LICENSE`, the page footer, the PDF's first-page footer) | The repository was public with no licence, so nothing in it could be reused. Committed by Warren on 19 Nov |

## Sources

Sources consulted during the project. The paper's references, each checked
against its source, are in `paper/references.bib` and `paper/reference_check.md`.

- [NSW Marine LiDAR Topo-Bathy 2018](https://datasets.seed.nsw.gov.au/dataset/marine-lidar-topo-bathy-2018)
- [ELVIS](https://elevation.fsdf.org.au/)
- [IHO S-44 Ed. 6.1.0](https://iho.int/uploads/user/pubs/standards/s-44/S-44_Edition_6.1.0.pdf)
- [Sentinel-2 + ICESat-2 SDB with ML (Frontiers, 2023)](https://doi.org/10.3389/feart.2023.1111817)
- [SDB empirical vs ML in dynamic coastal water (2024)](https://doi.org/10.1080/21664250.2024.2445418)
- [ICESat-2 Bathymetry Working Group](https://github.com/ICESat2-Bathymetry/Information)
- [AusSeabed](https://www.ausseabed.gov.au/data)
- [MHL Jervis Bay tide gauge 216470](https://www.mhl.nsw.gov.au/Station-216470)
- [PSMSL station JERVIS BAY II](https://psmsl.org/data/obtaining/stations/2312.php)
- [NSW Imagery Export Map service](https://maps.six.nsw.gov.au/arcgis/rest/services/public/NSW_Imagery/MapServer)
- [Spatial Services copyright](https://www.spatial.nsw.gov.au/copyright)
- [Sentinel-2 L1C Data Quality Report, Issue 28 (July 2018), geolocation performance](https://sentinels.copernicus.eu/documents/247904/3897638/Sentinel-2_L1C_Data_Quality_Report/9699703d-556e-407a-a955-65c0c82dfcb5?version=1.2)
- [Sentinel-2 geometric refinement (GRI)](https://sentinels.copernicus.eu/-/forthcoming-deployment-of-the-copernicus-sentinel-2-products-geometric-refinement)
- [Cox & Munk (1954), roughness of the sea surface from sun glitter, *JOSA* 44(11)](https://doi.org/10.1364/JOSA.44.000838)
- [Hersbach et al. (2020), the ERA5 global reanalysis, *QJRMS* 146](https://doi.org/10.1002/qj.3803)
- [Open-Meteo historical weather API](https://open-meteo.com/en/docs/historical-weather-api)
- [Stumpf, Holderied & Sinclair (2003), water depth from high-resolution imagery over variable bottom types, *Limnol. Oceanogr.* 48(1, part 2)](https://doi.org/10.4319/lo.2003.48.1_part_2.0547)
- [Caballero & Stumpf (2019), nearshore bathymetry from Sentinel-2A/2B, South Florida](https://www.researchgate.net/publication/334085536)
- [Hedley et al. (2005), simple and robust removal of sun glint, deglint specification in ESA SNAP](https://step.esa.int/main/wp-content/help/versions/9.0.0/snap-supported-plugins/org.esa.sen2coral.sen2coral.algorithms/deglint/DeglintAlgoSpec.html)
- [Harmel et al. (2018), sunglint correction of Sentinel-2 MSI from SWIR bands, *RSE* 204](https://www.sciencedirect.com/science/article/abs/pii/S0034425717304856)
- [Roberts et al. (2017), cross-validation strategies for structured data, *Ecography* 40](https://doi.org/10.1111/ecog.02881)
- [CATZOC definitions (S-57 attribute)](https://docs.teledynecaris.com/s-57/S57Cat/S57CatSite/attribut/catzoc.htm)
- [NSW DPI Fisheries Estuarine Macrophytes (REST)](https://spatial.industry.nsw.gov.au/arcgis/rest/services/Fisheries_Portal/Estuarine_Macrophytes/MapServer/0)
- [DCCEEW NSW seabed reef extent](https://mapprod3.environment.nsw.gov.au/arcgis/rest/services/Marine/NSW_seabed_reef_extent/MapServer)
- [GA Record 2009/10, Jervis Bay soft-sediment habitats](https://www.ga.gov.au/bigobj/GA14300.pdf)
- [Earth Search STAC item with `earthsearch:boa_offset_applied`](https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_56HLH_20180927_1_L2A)
- [The same double-offset trap found independently](https://github.com/Khadra-AI/thuraya-experience/pull/109)
- [ESA, radiometric offset in PB04.00 products](https://forum.step.esa.int/t/info-introduction-of-additional-radiometric-offset-in-pb04-00-products/35431)
- [Nechad, Ruddick & Park (2010), generic multisensor algorithm for total suspended matter, *RSE* 114(4)](https://doi.org/10.1016/j.rse.2009.11.022)
- [Pope & Fry (1997), absorption spectrum of pure water, *Applied Optics* 36(33)](https://doi.org/10.1364/AO.36.008710)
- [PSMSL, Sydney Fort Denison](https://psmsl.org/data/obtaining/stations/196.php)
