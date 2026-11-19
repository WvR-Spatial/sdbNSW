# v2 protocol: gradient boosting

Governs the gradient-boosting model, its features, its comparison with the band ratio and the coordinate model kept as a leakage demonstration.

Registered in commit `c2baa44f1f40490ae247a78ce5d7d5ff40248436` (2026-09-29T23:19:07+10:00). The text below the rule is copied unchanged from `PROJECT_BRIEF.md` as it stood at that commit, including its original punctuation and its working voice. To see it in place:

```
git show c2baa44:PROJECT_BRIEF.md
```

SHA-256 of the copied text: `5b2ea83d6ac185894d2a0a5c18abd99e331f8c08bfa8b04cab5cf11d7c264e13`

---

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
