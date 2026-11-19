# How deep can a satellite see off the NSW coast?

Down to about 15 m before its error starts to climb, and typically 2 to 3 m
out even there: good enough for reconnaissance, not for navigation.

This repository holds a pre-registered accuracy assessment of
satellite-derived bathymetry (SDB) from Sentinel-2, tested against the 2018
NSW marine lidar survey at three sites: sheltered Jervis Bay, the surf coast
of Sydney's Northern Beaches, and Batemans Bay at the mouth of the Clyde
River.

- **Read it:** [web page](https://wvr-spatial.github.io/sdbNSW/) ·
  [paper (PDF)](https://wvr-spatial.github.io/sdbNSW/sdbNSW_paper.pdf)
- **Replicate it:** [reference lidar release](https://github.com/WvR-Spatial/sdbNSW/releases/tag/reference-lidar-2018)
  and [`BUILD_GUIDE.md`](BUILD_GUIDE.md)
- **Check it:** [`protocols/`](protocols/) for what was registered before each
  run, and [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) for the full record and the
  decisions register

## The result

Pooled error over 0–20 m on spatially independent validation (2 km blocks),
with 95% block-bootstrap intervals:

| | Jervis Bay | Northern Beaches | Batemans Bay |
|:--|:--|:--|:--|
| Band ratio (Stumpf), RMSE | 2.68 m [2.31, 3.13] | 3.03 m [2.81, 3.22] | 2.96 m [2.32, 3.52] |
| Gradient boosting, RMSE | 1.88 m [1.67, 2.13] | 2.40 m [2.20, 2.58] | 2.45 m [1.86, 2.95] |
| Gradient boosting − band ratio | −0.80 m [−1.06, −0.57] | −0.63 m [−0.78, −0.50] | −0.51 m [−0.90, −0.15] |
| Meets CATZOC C (gradient boosting) | to 3 m | nowhere | to 2 m |

- Error is roughly level to about 15 m and climbs beyond it, where too little
  light returns from the seabed.
- Gradient boosting, using image features only, beat the band ratio at every
  site, mainly in the shallows and beyond 15 m.
- A model given map coordinates scored 1.8 to 4.3 times better on a random
  split of pixels than on unseen 2 km blocks. Random splits reward memorising
  the place.
- Error did not follow the water-clarity metric across sites, but the metric
  sat too close to the atmospheric correction's floor to rank them. The surf
  coast's larger error goes with its reef: 54% of its assessed seabed, against
  10% and 20% at the other sites. Reef read 1.3 to 4.0 m deeper than sediment at
  the same depth in most depth bands.

## What it does not tell you

The results are not for navigation; each site was assessed on one image; water
clarity could not be isolated; the surf zone is largely missing; and they
cover 0–20 m at three sites only. The [web page](https://wvr-spatial.github.io/sdbNSW/)
explains each point, and section 6 of the paper gives the detail.

## How it was done

- **Pre-registered.** Each protocol, with its predictions and decision gate,
  was committed before any model was fitted to the data it governs. The
  registered texts are frozen in [`protocols/`](protocols/); every change
  made after a run is logged with its reason, and both results are kept.
- **Data.** Sentinel-2 Level-2A surface reflectance from the Earth Search
  catalogue; NSW Marine LiDAR Topo-Bathy 2018 (5 m, IHO Order 1b) aggregated
  to the 10 m image grid after the image's geolocation error was measured
  and removed; water level at each overpass from Manly Hydraulics Laboratory
  tide gauges; reef and seagrass maps to group the errors.
- **Models.** The Stumpf band ratio, and gradient-boosted trees with fixed
  settings and per-pixel image features. A third model with coordinates
  exists only to show what a random split rewards.
- **Validation.** 2 km spatial blocks, five folds, ten repeats; intervals by
  block bootstrap; error by depth band and seabed type; the depth at which
  error exceeds IHO CATZOC C.

## Repository

```
sdbNSW/
├── README.md            this file
├── PROJECT_BRIEF.md     the project record: question, data, results, decisions register
├── BUILD_GUIDE.md       how to reproduce every result, figure and the paper
├── protocols/           the registered protocols, verbatim, with their commits
├── src/sdb/             the pipeline (an importable package)
├── tests/               282 tests, mostly against analytically known answers
├── scripts/             figures, protocol freezing, data checks
├── config/sites.yml     site extents, tide gauges, open-sea point
├── data/README.md       where each input comes from, and its licence
├── outputs/             every result record (JSON) and diagnostic figure, committed
├── paper/               the paper's source, references and build
└── docs/                the published web page and PDF (GitHub Pages)
```

## How this was built

I built this part-time over about eight weeks, a few of them spent waiting
for tide-gauge records, using an AI agent as the main means of production and
organising the work so that everything it produced could be checked.

The agent, Claude, ran in a cloud workspace and reached my workstation
through MCP connectors: a shell and file bridge into the project folder, and
a QGIS server that let it query ArcGIS REST services and inspect layers. It
wrote most of the 10,000 or so lines of Python, including 282 tests, and
drafted the protocols and documentation. I set the question and the sites,
ordered the lidar and requested the tide records, checked the image
registration by eye in QGIS, made each methodological decision, ran every
step on my own machine and wrote the interpretation.

Three practices made the output checkable. Each analysis was pre-registered,
so its protocol was committed before any model saw the reference data. Every
change is logged with its reason, including the agent's mistakes: a site
boundary that silently took in an estuary, a rule that passed its tests and
failed on real data, and a sorting fault that reversed one site's result. And
every file moved between machines was verified by checksum at its
destination.

The outcome is a study of wider scope than I would have attempted alone in
the same time, with a record of how each part was made.

## Licence and citation

Code: MIT ([`LICENSE`](LICENSE)). Paper, web page and figures: CC BY 4.0.
Third-party data keep their own licences ([`data/README.md`](data/README.md));
the lidar is

> NSW Marine LiDAR Topo-Bathy 2018 © State of New South Wales (Department of
> Climate Change, Energy, the Environment and Water), licensed under CC BY 4.0.

To cite:

> van Ryn, W. (2026). *Satellite-derived bathymetry on an exposed temperate
> coast: a pre-registered accuracy assessment against airborne lidar at three
> New South Wales sites* (Version 1.0). https://wvr-spatial.github.io/sdbNSW/

Not peer reviewed.

[Warren van Ryn](https://wvr-spatial.github.io/Portfolio/), Melbourne, Australia.
