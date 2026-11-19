# Registered protocols

Each analysis in this project was registered before it was run: its protocol, predictions and decision gate were committed to `PROJECT_BRIEF.md` before any model was fitted to the data it governs. That file has since been rewritten as a readable project record, so the registered texts are kept here, each copied verbatim from the commit that registered it by `scripts/freeze_protocols.py`.

`python scripts/freeze_protocols.py --check` confirms that every file still matches git history. The code finds the same commits independently: each output record under `outputs/` names the commit that introduced its protocol.

| File | Protocol | Registered | Commit |
|:--|:--|:--|:--|
| [`01_phase2_band_ratio.md`](01_phase2_band_ratio.md) | Phase 2 protocol: the band ratio at Jervis Bay | 2026-09-27 | `8332154` |
| [`02_substrate_addendum.md`](02_substrate_addendum.md) | Substrate addendum | 2026-09-27 | `73d02ce` |
| [`03_v2_gradient_boosting.md`](03_v2_gradient_boosting.md) | v2 protocol: gradient boosting | 2026-09-29 | `c2baa44` |
| [`04_phase4_three_sites.md`](04_phase4_three_sites.md) | Phase 4 protocol: three sites | 2026-10-01 | `a5b5f5d` |
| [`05_phase4_amendment.md`](05_phase4_amendment.md) | Phase 4 amendment: Northern Beaches open coast only | 2026-11-16 | `2cd2f53` |
| [`06_exploratory_depth_standardised.md`](06_exploratory_depth_standardised.md) | Exploratory addendum: depth-standardised block test | 2026-11-16 | `884dce1` |

Changes made after a protocol was registered are listed, with their reasons, in the decisions register of `PROJECT_BRIEF.md` and in Table 4 of the paper.
