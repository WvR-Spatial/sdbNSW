# Outline for approval (19 November 2026)

Two products from one Markdown source: a web page for the portfolio and a
conference-layout PDF. The paper is about 4,300 words before tables and
references; the web page carries it in full beneath a plain-language opening.

Titles (approved 19 Nov). Paper: *Satellite-derived bathymetry on an exposed
temperate coast: a pre-registered accuracy assessment against airborne lidar at
three New South Wales sites.* Web page: *How deep can a satellite see off the
NSW coast?*

## Layer 1: the opening of the web page (about 450 words)

| Element | Content | Words |
|---|---|---|
| Title and answer | *How deep can a satellite see off the NSW coast?* Beneath it, one sentence: typically 2 to 3 m out in water to 20 m; useful for reconnaissance, not navigation | 30 |
| Plain summary | What was tested, where, against what, and what was found, with no undefined term | ≤ 150 |
| Three numbers | Typical error (1.9 to 3.0 m); the depth from which error climbs (about 15 m); how much a careless test flatters a model (a model given coordinates looked two to four times better under a random split than on separate blocks) | 60 |
| Hero figure | Satellite depth against lidar depth, three sites, with the CATZOC C allowance shaded | caption 40 |
| Limitations panel | As signed off | 170 |
| Links | PDF, repository, reference lidar release | |

"How this was built" (signed off) sits at the foot of the page, after the
paper, under its own heading.

## Layer 2: the paper

| Section | Content | Sources | Words |
|---|---|---|---|
| Abstract | Structured: background, methods, results, conclusions | | ≤ 250 |
| Keywords | satellite-derived bathymetry; Sentinel-2; airborne lidar; spatial cross-validation; pre-registration; New South Wales | | |
| 1 Introduction | Empirical SDB and Sentinel-2. What the literature reports, with each figure's validation design: clear water (St Thomas; South Florida), temperate and optically complex water (Ireland; Aegean; Hasaki), Australia (Adelaide, low energy). Turbidity as the recognised limit. Why random splits flatter models. The gap: no published assessment on the swell-exposed NSW coast. Three questions: how accurate, and to what depth; whether gradient boosting's advantage holds; whether error follows water clarity between and within sites | lyzenga1978, stumpf2003, drusch2012, ashphaq2021, xie2023, caballero2019, casal2020, traganos2018, quang2025, downes2025, caballero2023, roberts2017, ploton2020 | 500 |
| 2 Sites and data | Three sites and why (T1, F1). Lidar: Order 1b, CC BY, the portal averaging found at Jervis Bay. Sentinel-2 L2A from Earth Search, the offset trap. Tide gauges and datum handling. Substrate layers. Sydney wave record | dcceew2018lidar, iho2022s44, element84earthsearch, esa2022offset, mainknorn2017, mhl2026tides, dpi2023macrophytes, dcceew2023reef, anderson2009 | 550 |
| 3 Methods | 3.1 Pre-registration: protocols committed before any fit; one amendment; deviations logged (T4). 3.2 Reference: aggregation to the 10 m grid, measured water level, co-registration, masks including the open-sea rule. 3.3 Models: Stumpf ratio; gradient boosting with fixed settings and no coordinates; the coordinate model kept only to demonstrate leakage. 3.4 Validation: 2 km spatial blocks, repeated five-fold, block bootstrap intervals, depth bands, CATZOC breakdown depth, residual correlation range, block-size curve. 3.5 Clarity: the metric, gate 4, the registered block test, the exploratory depth-standardised test. 3.6 Substrate strata | stumpf2003, friedman2001, pedregosa2011, roberts2017, nosek2018, iho2000s57, nechad2010, popefry1997, coxmunk1954, hersbach2020 | 1,000 |
| 4 Results | 4.1 Accuracy by site and depth (T2, F2). 4.2 Gradient boosting against Stumpf. 4.3 Validation design (F3). 4.4 Seabed type, including the reef-share breakdown (F4). 4.5 Clarity: gate 4, the registered block test and the exploratory one (F5). 4.6 Sensitivity: reference averaging, the second gauge. Predictions scorecard (T3) | outputs only | 950 |
| 5 Discussion | 5.1 Against the literature, design by design: Ireland's 1.6 to 2.4 m is the nearest comparison; St Thomas and Hasaki used point splits. 5.2 What sets the error here: the signed-off conclusion's argument in full. 5.3 Practical reading: reconnaissance, site screening for reef and exposure, wave-based methods for surf coasts (F6 residual map) | casal2020, xie2023, quang2025, downes2025, almar2021, caballero2023, hedley2005, harmel2018 | 700 |
| 6 Limitations | As signed off (the paper version) | | 450 |
| 7 Conclusions | The signed-off conclusion condensed to its claims and their scope | | 250 |
| Data and code | Repository, reference lidar release, licences | | 80 |
| Workflow statement | As signed off (the paper version) | | 150 |
| Acknowledgements | DCCEEW (lidar, reef extent), Manly Hydraulics Laboratory, DPI Fisheries, ESA and Element 84 | | 50 |
| References | About 30, author-date (APA 7) | `references.bib` | |

The signed-off conclusion is too long for a Conclusions section; its argument
becomes Discussion 5.2 nearly as written, and Conclusions states the result in
five or six sentences. Nothing in it is dropped.

## Figures

| | Shows | Built with |
|---|---|---|
| Hero (web) | Satellite against lidar depth, three sites, CATZOC C band | matplotlib |
| F1 | Location: NSW inset; three panels on lidar hillshade with the assessed area and, at Northern Beaches, the water excluded by the open-sea rule | QGIS (PyQGIS script) |
| F2 | RMSE and 95th-percentile error by depth band, three sites by two models, CATZOC C allowance | matplotlib |
| F3 | Random against blocked validation for Stumpf, gradient boosting and the coordinate model; block-size curves | matplotlib |
| F4 | Reef minus sediment bias by depth band at three sites, with reef share | matplotlib |
| F5 | Clarity: site medians against RMSE; within-site correlations, registered and depth-standardised, with intervals | matplotlib |
| F6 | Residual map at one site on hillshade | QGIS |

One font, one colour-blind-safe palette, captions that state the finding, alt
text on the web page.

## Tables

T1 sites, scenes, lidar dates, pairing gap, water levels and gauges ·
T2 pooled and depth-balanced RMSE, bias and breakdown depth, both models, with
intervals · T3 predictions scorecard: gates 1 to 4, the four v2 predictions and
the four Phase 4 predictions, held or failed · T4 deviations, amendments and
corrections.

## Build

Pandoc with citeproc renders the Markdown to HTML (portfolio page, GitHub
Pages from the repository) and to Typst, which typesets the PDF. Both tools
run here; nothing needs installing on Warren's machine. Figures are generated
by `scripts/figures.py` and `scripts/maps_qgis.py` from committed outputs, so
the whole paper rebuilds from the repository.

## Decisions for Warren

1. **Author line** exactly as it should appear: name, affiliation (or
   "independent"), and whether to include an ORCID or email.
2. **PDF layout:** two-column A4 with a full-width title and abstract (reads
   as a conference paper; recommended), or single column (easier to read on
   screen).
