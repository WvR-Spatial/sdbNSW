# Reference check, 19 November 2026

Every work the paper cites was checked before drafting: bibliographic details
against Crossref (through an OpenAlex and Crossref lookup service) or the
publisher's page, and every figure quoted from it against its abstract or full
text. `references.bib` holds the checked entries. Status: **checked** (details
and quoted claim confirmed), **details only** (bibliography confirmed; the
paper cites it for a general point, not a number), **to confirm** (one item
outstanding, stated).

## Works whose numbers the paper quotes

| Key | Checked against | What the paper may say | Status |
|---|---|---|---|
| xie2023 | Crossref; full text (Frontiers) | St Thomas, US Virgin Islands, clear water, 0–20 m, NOAA CUDEM reference: random forest 1.28 m RMSE (nine bands), Stumpf 1.78 m, Lyzenga linear 2.19 m (Table 5). Training and test points split 80/20; the paper does not say whether the split was random or spatial. Training depths from ICESat-2 | checked |
| caballero2019 | Crossref; abstract | South Florida, Stumpf ratio with ACOLITE correction, calibrated on 5–10 chart depths, validated on lidar: median absolute error 0.5 m at West Palm Beach (0–18 m), 0.4 m Key West, 0.22 m Dry Tortugas, low turbidity. Median absolute error, not RMSE | checked |
| caballero2023 | Crossref; abstract | Multi-scene compositing to suppress turbidity; Caribbean and US east coast; median errors under 1 m to 30 m against lidar | checked |
| casal2020 | Crossref; abstract | Irish coast, optically complex, model inversion, 12 Sentinel-2 images: mean RMSE 1.60 m (Dublin Bay), 1.66 m (Mulroy Bay), 2.43 m (Brandon Bay) | checked |
| traganos2018 | Crossref; abstract | Aegean Sea, spatially independent calibration and validation sets; best validation RMSE 1.67 m | checked |
| quang2025 | Crossref; abstract. Author entered as Crossref records it (family name "Hao Quang"), so the text cites Hao Quang et al. | Hasaki, Ibaraki, Japan: an exposed, highly dynamic sandy coast. Echo-sounding reference; 70/30 split of survey points per year; CatBoost R² 0.84–0.92 to about 15 m, RMSE under 0.5 m above 7 m. The abstract does not describe a spatial split | checked |
| downes2025 | Crossref; abstract | Adelaide metropolitan coast, South Australia: shallow, mixed bottom, **low wave energy**. Best RMSE 0.41 m at the calibration site (PlanetScope), 0.51 m beyond it over 0.5–5 m; multiband linear beat band ratio | checked |
| almar2021 | Crossref; abstract | Wave-kinematics bathymetry from Sentinel-2, global atlas, RMSE 6–9 m; an alternative where surf defeats colour-based methods | checked |
| iho2022s44 | IHO PDF | Order 1b: TVU = √(a² + (b·d)²), a = 0.5 m, b = 0.013, 95% confidence | checked |
| iho2000s57 | S-57 catalogue page (Teledyne CARIS mirror) | CATZOC C depth accuracy 2.00 m + 5% of depth; B 1.00 m + 2%; D "worse than ZOC C". The page states 95% (2.45σ) for **position** accuracy and gives no confidence level for depth; the paper compares the allowance with the 95th percentile of absolute error and must say that this is its choice | checked, wording noted |
| dcceew2018lidar | SEED dataset page; delivery metadata PDF | CC BY 4.0; July–December 2018; vertical precision IHO Order 1b; "should not be used for navigation without additional processing" | checked |
| anderson2009 | GA PDF | Jervis Bay soft sediments: sand-dominated, mud mainly inshore of about 20 m | checked |
| esa2022offset | ESA STEP forum notice | Radiometric offset −1000 for L2A from processing baseline 04.00 (25 Jan 2022); reflectance = (DN + offset) / 10000 | checked |

## Works cited for a general point

| Key | Used for | Status |
|---|---|---|
| lyzenga1978 | origin of empirical SDB | details only (pages 379–383 from the publisher) |
| stumpf2003 | the ratio method used here | details only; method as implemented is specified in the protocol |
| drusch2012 | Sentinel-2 mission | details only |
| mainknorn2017 | Sen2Cor, the L2A processor | details only |
| ashphaq2021 | review of SDB methods | details only |
| roberts2017, ploton2020 | spatial cross-validation and its effect on reported accuracy | details only |
| nosek2018 | pre-registration | details only |
| friedman2001, pedregosa2011 | gradient boosting; scikit-learn's implementation | details only (JMLR has no DOI; checked on jmlr.org) |
| hedley2005, harmel2018 | glint corrections not applied here | details only |
| coxmunk1954, hersbach2020 | wind as a glint screen in scene selection | details only (Cox and Munk pages 838–850 from the publisher) |
| nechad2010 | red reflectance as an index of suspended matter | checked (abstract via the VLIZ record, 19 Nov): a single-band algorithm for total suspended matter, lowest validation errors at the red bands (665 to 681 nm) |
| popefry1997 | strong absorption of red light by pure water | checked: pages 8710–8723 (Oregon Medical Laser Center's record of the paper; Crossref gives the first page only). The paper quotes "about 0.4 m⁻¹" at 665 nm, not a tabulated value |
| element84earthsearch, dpi2023macrophytes, dcceew2023reef, mhl2026tides | data sources | access dates from the project record |

## What the check changed

1. **"Published SDB validation is almost entirely clear tropical water" is
   not true and is not used.** The literature leans to clear water
   (Caribbean, Florida, South China Sea), but temperate and optically complex
   sites are published: the Irish coast (casal2020, RMSE 1.6–2.4 m), the
   Aegean (traganos2018), an exposed sandy coast in Japan (quang2025), and,
   in Australia, the low-energy Adelaide coast (downes2025).
2. **"Around 1.3 m for ML, 1.8 m for Stumpf, 2.2 m for linear models" is one
   study, not "the literature":** St Thomas in xie2023, with an 80/20 split of
   unstated design. The paper quotes it as that.
3. **"Nobody has published the error envelope for [the NSW coast]" becomes a
   statement of what the search found:** no published accuracy assessment of
   SDB on the NSW open coast; the nearest temperate Australian study is a
   low-energy coast.
4. **What the paper can claim as its contribution:** a multi-site assessment
   on a swell-exposed temperate coast against contemporaneous lidar, with
   pre-registered predictions, spatially blocked validation and a direct
   demonstration of how a random split flatters a model. Spatially independent
   validation is not new (traganos2018); doing it with pre-registered
   predictions across three sites is uncommon.

## Searches run (19 Nov)

OpenAlex and Semantic Scholar (FastTrack), Consensus, and web search, for
satellite-derived bathymetry with: New South Wales, Sydney, Jervis Bay,
Batemans Bay, eastern Australia, temperate, exposed coast, airborne lidar
validation. Grey literature (agency reports, theses) was not searched
systematically.
