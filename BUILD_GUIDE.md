# Reproduction guide

How to rerun every result in this repository, rebuild the figures and the
paper, and check that what you get matches what was published. The *why*
behind each step is in [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) and the
registered texts in [`protocols/`](protocols/); this guide is the *how*.

Every result record under `outputs/` names the md5 of each input it read, so a
rerun can be checked file by file. Expected values are given below at each
step; numbers that differ beyond the last decimal mean a different input or
environment, and are worth stopping for.

Commands are written for the Anaconda Prompt on Windows (cmd.exe), where the
project was run. On Linux or macOS change `\` to `/` in paths and `rem` to `#`.

## 1. Environment

```
conda env create -f environment.yml
conda activate sdbnsw
pip install -e . --no-deps
python -m pytest -q
```

Expect `282 passed`. The environment is conda-forge only; `--no-deps` stops pip
installing PyPI wheels with their own GDAL on top of conda's.

Network access is needed for the Sentinel-2 catalogue (Earth Search on AWS),
NSW orthoimagery (Spatial Services), ERA5 wind (Open-Meteo, scene selection
only) and the habitat map services. All are public and anonymous.

## 2. Inputs

| Input | How to get it | Where it goes |
|:--|:--|:--|
| Lidar reference, three sites plus one sensitivity extract | Download `sdbNSW_reference_lidar_2018.zip` from the release [`reference-lidar-2018`](https://github.com/WvR-Spatial/sdbNSW/releases/tag/reference-lidar-2018) and unzip at the repository root; check against its `MANIFEST.md5`. Or order from ELVIS as described in `data/README.md` | `data\raw\...`, at the paths `config\sites.yml` expects |
| Sentinel-2 Level-2A scenes | Fetched by `sdb.fetch` (step 3) | `data\raw\scenes\<scene>\` |
| Orthoimagery windows | Fetched by `sdb.coreg` | `data\raw\ortho\` |
| Tide-gauge records | Manly Hydraulics Laboratory, on request (`data/README.md`, section 5). **Optional:** the measured water levels are committed in `outputs\waterlevel_<scene>.json`, and `reference` reads them from there | `data\raw\MHL\`, `data\raw\tide\` |
| Reef and seagrass layers | ArcGIS REST services, one GeoPackage per site (`data/README.md`, section 6) | `data\raw\substrate\` |
| Basemap for Figure 1 | Natural Earth admin-1, from the `world_map.gpkg` bundled with QGIS (`data/README.md`, section 7) | `data\raw\basemap\` |

`data\raw\` is not committed. Everything under it is either downloadable as
above or recreated by the pipeline.

## 3. Each site, in order

| Site key | Scene | Notes |
|:--|:--|:--|
| `jervis_bay` | `S2A_56HKG_20180907_0_L2A` | the default site |
| `narrabeen_long_reef` | `S2A_56HLH_20180927_1_L2A` | Northern Beaches; open coast only |
| `batemans_bay` | `S2B_56HKF_20180823_1_L2A` | co-registration needs 1.5 km windows |

For each site (`<site>`, `<scene>`):

```
python -m sdb.fetch --site <site> scene --item <scene>
python -m sdb.coreg --site <site> --scene <scene>
python -m sdb.reference --site <site> --scene <scene>
python -m sdb.validate --site <site> --scene <scene>
python -m sdb.validate --site <site> --scene <scene> --model gbm
python -m sdb.validate --site <site> --scene <scene> --model gbm_xy
python -m sdb.substrate --site <site> --scene <scene>
```

At Batemans Bay add `--window-km 1.5` to `coreg`. Scene selection
(`sdb.stac`, `sdb.fetch quicklook`) is not needed to reproduce the results:
the scenes are fixed, and the reasons for each choice are in the decisions
register.

Do not run `waterlevel --from-image` unless you mean to: it overwrites the
committed, gauge-measured water level with the image's provisional estimate.
With the gauge records in hand, `waterlevel` reproduces the committed values:

```
python -m sdb.waterlevel --site jervis_bay --scene S2A_56HKG_20180907_0_L2A --gauge-file data\raw\tide\JervisBay.Level1.AHD.Actual.1min.csv
python -m sdb.waterlevel --site narrabeen_long_reef --scene S2A_56HLH_20180927_1_L2A --gauge-file "data\raw\MHL\Ocean tide\Sydney.Level1.AHD.Actual.1min.csv"
python -m sdb.waterlevel --site batemans_bay --scene S2B_56HKF_20180823_1_L2A --gauge-file "data\raw\MHL\Ocean tide\PrincessJetty.Level1.AHD.Actual.1min.csv"
```

**Expected values**

| | Jervis Bay | Northern Beaches | Batemans Bay |
|:--|:--|:--|:--|
| `fetch`: water check | passes (red over water +0.0039) | passes (+0.0036) | passes (+0.0053) |
| `coreg`: shift east, north (m); verdict | −7.42, −1.02; apply | −0.43, −3.47; apply | +2.95, −4.91; apply |
| `waterlevel` (m AHD) | −0.392 | +0.501 | −0.181 |
| `reference`: usable pixels | 932,838 (93.28 km²) | 216,259 (21.63 km²) | 274,689 (27.47 km²) |
| `validate`: band-ratio pooled RMSE | 2.68 m [2.31, 3.13] | 3.03 m [2.81, 3.22] | 2.96 m [2.32, 3.52] |
| `validate --model gbm` | 1.88 m [1.67, 2.13] | 2.40 m [2.20, 2.58] | 2.45 m [1.86, 2.95] |
| `validate --model gbm_xy`, blocked/random | 1.774 | 2.936 | 4.260 |

At Northern Beaches `reference` also reports 115,357 pixels of water not
connected to the open sea (Pittwater and the lagoons), and `validate` 21
eligible blocks. `validate` refuses a site with fewer than 15 blocks and writes
nothing.

The band ratio takes under a minute per site. Each gradient-boosting run makes
250 fits and takes about 15 minutes on two cores at Jervis Bay, less at the
smaller sites. Tree building is multithreaded, so a machine with a different
number of cores may differ in the last decimal.

Each step writes a JSON record to `outputs\` (committed) and rasters beside
the scene (not committed): `reference.tif` and `mask.tif`, then `sdb.tif`
(out-of-fold depth and residual), `sdb_gbm.tif`, `sdb_gbm_xy.tif` and
`substrate.tif`. Gradient-boosting records go to `outputs\v2\`. No model
overwrites another's raster.

## 4. Across the three sites

The registered clarity analysis, then the exploratory depth-standardised test:

```
python -m sdb.clarity --run jervis_bay=S2A_56HKG_20180907_0_L2A --run narrabeen_long_reef=S2A_56HLH_20180927_1_L2A --run batemans_bay=S2B_56HKF_20180823_1_L2A
python -m sdb.clarity --depth-adjusted --run jervis_bay=S2A_56HKG_20180907_0_L2A --run narrabeen_long_reef=S2A_56HLH_20180927_1_L2A --run batemans_bay=S2B_56HKF_20180823_1_L2A
```

The first writes `outputs\phase4\clarity.json` and prints each registered
prediction as held or failed: gate 4 not met; mean within-site correlation
+0.35 [+0.09, +0.59] for the band ratio. The second writes only to
`outputs\exploratory\`: mean +0.40 [+0.10, +0.66], read as *supported* by the
rule fixed beforehand. `outputs\phase4\clarity_run1_superseded.json` is the
first, erroneous run, kept on purpose (decisions register, 16 Nov).

## 5. Sensitivity and exploratory runs

These are labelled in their records and can only write to
`outputs\sensitivity\` or `outputs\exploratory\`.

```
rem Reference averaging: Northern Beaches against the ELVIS-averaged extract
python -m sdb.reference --site narrabeen_long_reef --scene S2A_56HLH_20180927_1_L2A --dem "data/raw/Narrabeen/NSW Government - DCCEEW/DEM/5 Metre/NSW_Marine_5m_TopoBathy_DEM.tif" --tag elvis_avg
python -m sdb.validate --site narrabeen_long_reef --scene S2A_56HLH_20180927_1_L2A --reference-tag elvis_avg
python -m sdb.validate --site narrabeen_long_reef --scene S2A_56HLH_20180927_1_L2A --reference-tag elvis_avg --model gbm

rem Second tide gauge at Northern Beaches (Patonga): +0.539 m AHD
python -m sdb.waterlevel --site narrabeen_long_reef --scene S2A_56HLH_20180927_1_L2A --gauge-file "data\raw\MHL\Ocean tide\Patonga.Level1.AHD.Actual.1min.csv" --gauge-key tide_gauge_check --tag patonga

rem Jervis Bay calibration variants (exploratory, Phase 2)
python -m sdb.validate --scene S2A_56HKG_20180907_0_L2A --exploratory rule95
python -m sdb.substrate --scene S2A_56HKG_20180907_0_L2A --tag rule95
python scripts\calibration_form_check.py --scene S2A_56HKG_20180907_0_L2A
```

Expected: the averaged reference moves pooled RMSE by −0.02 m for both models.
The Jervis Bay exploratory runs were made at the image-estimated water level
(−0.496 m AHD) before the gauge record arrived and were not repeated, so a
rerun now, at the measured level, will differ slightly from the recorded
values (pooled RMSE 2.82 m for `rule95`).

## 6. Figures, web page and PDF

```
python scripts\figures.py
python paper\build.py
```

`figures.py` writes the hero figure and Figures 1–6 to `docs\figures\` from the
committed records and the site rasters (`--no-rasters` makes only the four
charts that need no rasters). The charts use the Inter typeface if it is
installed.

`build.py` turns `paper\paper.md` into `docs\index.html` and
`docs\sdbNSW_paper.pdf`. It needs pandoc 3.1 or later on the PATH and the typst
Python package (`pip install typst`); `build.py --figures` runs `figures.py`
first. An unchanged source rebuilds the PDF to identical bytes. GitHub Pages
serves `docs\` from the `main` branch.

## 7. Checks

```
python scripts\freeze_protocols.py --check
python scripts\dem_extracts.py check <a delivered lidar .tif>
```

The first confirms that each file in `protocols\` still matches the text its
commit registered. The second reports whether a lidar extract holds native
values or ELVIS-averaged ones (`data/README.md`, section 1).
