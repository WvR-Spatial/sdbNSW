# Exploratory addendum: depth-standardised block test

Governs an exploratory test defined after the registered Phase 4 result was seen, with its reading rule fixed before it was run.

Registered in commit `884dce1517e9df43dd53711e7cb2bb92c77cf8a0` (2026-11-16T22:39:27+11:00). The text below the rule is copied unchanged from `PROJECT_BRIEF.md` as it stood at that commit, including its original punctuation and its working voice. To see it in place:

```
git show 884dce1:PROJECT_BRIEF.md
```

SHA-256 of the copied text: `5fb5dd1b3515250ef3106d88749a77bba9b2a7db7ffb28cb094b01f6ba1b92d1`

---

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
