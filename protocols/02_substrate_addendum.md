# Substrate addendum

Governs how pixels are classed by seabed type and how classes are compared.

Registered in commit `73d02ce1d598ffc385a3f364dd3a7553a6f47fb8` (2026-09-27T21:52:08+10:00). The text below the rule is copied unchanged from `PROJECT_BRIEF.md` as it stood at that commit, including its original punctuation and its working voice. To see it in place:

```
git show 73d02ce:PROJECT_BRIEF.md
```

SHA-256 of the copied text: `8909cba57497146329cd1d4091173c4befa85559f4e1ef673d6eece967b583ae`

---

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
