# Phase 4 protocol: three sites

Governs site eligibility, scene and gauge rules, the clarity metric, the within-site block test, four predictions and the sensitivity runs.

Registered in commit `a5b5f5df213aa24fb239dcd1c36c783f3a3069da` (2026-10-01T22:41:19+10:00). The text below the rule is copied unchanged from `PROJECT_BRIEF.md` as it stood at that commit, including its original punctuation and its working voice. To see it in place:

```
git show a5b5f5d:PROJECT_BRIEF.md
```

SHA-256 of the copied text: `d31cfc97b9233a62da2eb0b18888924afc5a4d8cd74b8979e26f06f75cfa74ce`

---

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
