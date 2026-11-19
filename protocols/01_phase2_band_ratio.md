# Phase 2 protocol: the band ratio at Jervis Bay

Governs the Stumpf band ratio at Jervis Bay: calibration, blocked validation, statistics and the CATZOC breakdown depth; later runs at every site follow it.

Registered in commit `8332154275e6b1308d6c49e3347fcbd3b31c1797` (2026-09-27T21:08:43+10:00). The text below the rule is copied unchanged from `PROJECT_BRIEF.md` as it stood at that commit, including its original punctuation and its working voice. To see it in place:

```
git show 8332154:PROJECT_BRIEF.md
```

SHA-256 of the copied text: `6ebc5a04de76dc72d6d0e2f1bb7847d1717159a6740bdf90b522d9e4386470c9`

---

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
