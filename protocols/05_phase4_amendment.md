# Phase 4 amendment: Northern Beaches open coast only

Governs the open-sea rule at Northern Beaches, made before any fit at the new sites.

Registered in commit `2cd2f534a448cbeef9d12003ae6e44b89e1fe023` (2026-11-16T20:57:15+11:00). The text below the rule is copied unchanged from `PROJECT_BRIEF.md` as it stood at that commit, including its original punctuation and its working voice. To see it in place:

```
git show 2cd2f53:PROJECT_BRIEF.md
```

SHA-256 of the copied text: `b3813b2726f485a655c74eaf2b0654e83478ae54c7d2cdf5818716efaaddd48a`

---

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
