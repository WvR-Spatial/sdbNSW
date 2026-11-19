# Data

Two directories, two different rules.

| Path | Committed? | What it holds |
|---|---|---|
| `raw/` | **No** — gitignored | Manual downloads, as supplied. Large, re-orderable, reproducible by following the steps below. |
| `reference/` | **Yes** | Small derived products: clipped subsets, indexes, footprints. These are what the analysis reads. |

Code always references these paths relative to the repository root, so a clone
works anywhere. Files under `raw/` are simply absent until someone downloads
them, and the pipeline should fail with a clear message rather than silently
skipping.

---

## What to download

### 1. NSW Marine LiDAR Topo-Bathy 2018 — 5 m DEM  *(the reference surface)*

The validation reference. **Licence: CC BY 4.0** — attribution required in any
publication of results, including the portfolio page.

- Portal: [ELVIS](https://elevation.fsdf.org.au/)
- Draw the area of interest, then under **Digital Elevation Models → 5 Metre**
  select *"5 metre Topo-Bathy DEM derived from NSW Marine LiDAR Project 2018"*.
- Product: **GeoTIFF**, not the LAS point cloud.
- **CRS: GDA2020 / MGA zone 56 (EPSG:7856)** — this is the data's native CRS.
  Do not let the portal reproject it; any reprojection resamples the elevation
  values and puts interpolation error into the reference surface.
- Delivery is asynchronous — ELVIS emails a link.
- Save to `raw/`.

Attribution string:

> NSW Marine LiDAR Topo-Bathy 2018 © State of New South Wales
> (Department of Climate Change, Energy, the Environment and Water),
> licensed under CC BY 4.0.

**Keep each order inside one survey block's raster.** When an order touches
more than one block, ELVIS mosaics them with "Average 16" interpolation: every
cell becomes the mean of a 4×4 window, smoothed over 20 m and displaced half a
cell (2.5 m south, 2.5 m west). The delivery's readme says so only as "where
required". Block extents are in the coverage index (section 2). Where a site
needs more than one rectangle inside a block, order several and join them:

```
python scripts\dem_extracts.py check  <delivered .tif> [--against <another extract>]
python scripts\dem_extracts.py merge  <out .tif> <box A .tif> <box B .tif>
```

`check` reports the grid phase and the share of underwater cells on a
whole-centimetre lattice: 0.97–0.99 for native values, ~0.1 after averaging.
`merge` refuses unless every input shares one grid and every overlapping cell
is identical, and writes a JSON sidecar with the inputs' md5s. Jervis Bay's
delivery (below) predates this and is mostly averaged.

### 2. Survey coverage index  *(optional — already reduced)*

The whole-of-NSW block footprints, used to establish per-block capture dates.
Source: [SEED](https://datasets.seed.nsw.gov.au/dataset/marine-lidar-topo-bathy-2018)
→ **Download Package** (ZIP, ~5 MB).

This is *not* elevation data. It has already been reduced to the two committed
files below, so you only need it again to re-derive them for another site.

### 3. Sentinel-2 L2A

Fetched programmatically from the Earth Search STAC catalogue on AWS — no
account, nothing to download by hand.

```
python -m sdb.stac --site jervis_bay                      # rank candidates
python -m sdb.fetch quicklook --top 3                     # AOI cloud + visual check
python -m sdb.fetch scene --item <item id>                # fetch the chosen scene
```

Only the AOI's pixels are read (windowed COG requests), and they land in
`raw/scenes/<item id>/`:

| File | Contents |
|---|---|
| `reflectance.tif` | blue, green, red, nir — BOA reflectance, float32, native UTM 10 m grid, NaN = nodata |
| `scl.tif` | scene classification, upsampled to 10 m by exact replication |
| `provenance.json` | item id, processing baseline, the scale/offset applied and where it came from, the water plausibility check, AOI cloud/water fractions |

The processing-baseline offset has already been applied and checked against
water physics, so nothing downstream should apply it again. `provenance.json`
records which conversion was used.

Earth Search's Collection-1 items (baseline 05.00, ids ending `_1` or `_2`)
already have the −1000 DN offset taken out of their pixels and say so with
`earthsearch:boa_offset_applied: true`, yet their `raster:bands` still declare
`offset: -0.1`. `fetch` follows the item flag; applying both subtracts the
offset twice, which the water check catches (red and NIR near −0.1).

Three more commands put the lidar on that scene's grid:

```
python -m sdb.coreg --scene <item id>                   # image offset vs orthoimagery (~1 min)
python -m sdb.waterlevel --scene <item id> --from-image # provisional water level (~20 s)
python -m sdb.reference --scene <item id>               # lidar onto the scene grid (~6 s)
```

`reference` applies the offset from `coreg` when its verdict is `apply`, uses
the water level from `waterlevel`, and adds to `raw/scenes/<item id>/`:

| File | Contents |
|---|---|
| `reference.tif` | `z_mean` (m AHD), `coverage` (0–1), `relief` (std of the 5 m cells in each pixel, m), `land_frac` (0–1 at the water level used) — float32, on the scene's own grid |
| `mask.tif` | uint8 bit flags, 0 = usable: 1 lidar incomplete · 2 land · 4 outside depth window · 8 cloud/shadow · 16 bright NIR over lidar water · 32 no image · 64 water not joined to the open sea (sites with `open_sea_point`) |

The small records that explain them — offset measured, datum operation, water
level assumed, pixel counts by depth band — go to `outputs/` and are committed.

`python -m sdb.validate --scene <item id>` (Phase 2) adds `sdb.tif` beside
them — `oof_depth` (out-of-fold SDB depth, m) and `residual` (SDB − lidar, m,
positive = reads too deep), float32, NaN outside assessed pixels. Its record
(`outputs/sdb_<item id>.json`) and figures (`outputs/figures/`) are committed;
the raster is not.

`python -m sdb.substrate --scene <item id>` adds `substrate.tif`:
`class_majority` and `class_core` (index into the class list in
`outputs/substrate_<item id>.json`), `seagrass_frac`, `reef_frac` — on the
ground each pixel sees, i.e. with the co-registration shift applied.

Exploratory variants (`validate --exploratory <name>`) write `sdb_<name>.tif`
beside the scene and their records to `outputs/exploratory/`; v2 models
(`validate --model gbm | gbm_xy`) write `sdb_<model>.tif` and `outputs/v2/`.
Neither ever overwrites `sdb.tif`.

### 4. Orthoimagery for co-registration  *(fetched automatically, never committed)*

`coreg` fetches 2 km windows of NSW Imagery (Spatial Services) through its
public Export Map endpoint, in the scene's CRS at 2 m, and caches them as PNG +
JSON sidecar in `raw/ortho/<site>/`. Used only as a positional reference: the
imagery's licence is unclear (catalogue CC BY 3.0 AU; Spatial Services excludes
images from its Creative Commons licence), so it is not redistributed, not
committed and not drawn in any figure.

> NSW Imagery © State of New South Wales (Spatial Services, Department of
> Customer Service NSW).

### 5. Tide gauge record

Observed water level at the overpass. Source: Manly Hydraulics Laboratory,
**Jervis Bay gauge 216470** (HMAS Creswell), by data request — the form under
*Data Request* on [mhl.nsw.gov.au](https://www.mhl.nsw.gov.au/Station-216470) or
data-request@mhl.nsw.gov.au. Ask for 6–8 September 2018. Licence CC BY 4.0;
attribute NSW DCCEEW. Save the CSV to `raw/tide/`.

Received 29 Sep 2026 as `JervisBay.Level1.AHD.Actual.1min.csv`, with MHL's
*Data conditions and limitations* PDF (keep both):

- A 30-line licence and station block, then `Date,Time,Value [m],Quality` —
  date and time in **separate columns**, day first, CRLF line endings.
- 1-minute samples, 6 Sep 00:00 – 9 Sep 00:00 AEST, none missing.
- Supplied in **AHD** (the header says so; the record's mean agrees). The
  station's own datum is Jervis Bay Port Datum (1958): AHD = SD − 1.070 m.
- Times **AEST** (UTC+10, no daylight saving), accurate to ±2 minutes.
- Quality code **55** throughout: processed to ±20 mm.

`waterlevel` reads this layout as supplied, infers the datum from the numbers
and refuses if that contradicts the header. `waterlevel --from-image` remains
for sites without a gauge; at Jervis Bay it read 0.104 m low.

Sites 2 and 3, requested 1 Oct 2026 and **received 16 Nov 2026** in the same
layout, saved as supplied:

```
raw/MHL/Ocean tide/Sydney.Level1.AHD.Actual.1min.csv          213470  Northern Beaches, primary
raw/MHL/Ocean tide/Patonga.Level1.AHD.Actual.1min.csv         212440  Northern Beaches, cross-check
raw/MHL/Ocean tide/PrincessJetty.Level1.AHD.Actual.1min.csv   216410  Batemans Bay
raw/MHL/Ocean tide/Data conditions and limitations.pdf
raw/MHL/Wave/SYDDOW 1_9_2018 to 30_9_2018.csv                 Sydney waverider, hourly
raw/MHL/Wave/sydney_LocationHistory.pdf, Wave Data Analysis and Statistics Aug 2025.pdf
```

- Each tide record: 1-minute, 22 Aug 00:00 – 30 Sep 00:00 AEST 2018 (more
  than asked, which covers both overpasses), AHD in the header and confirmed
  by the mean, quality 55 throughout. One gap: Princess Jetty, 17 minutes
  from 02:50 AEST 13 Sep.
- **213470 is MHL's own Sydney gauge** (151.2585, −33.8255, inside the
  harbour near Middle Head), not Fort Denison.
- The wave file is hourly Hsig, Hmax, Tz, Tp, direction and sea temperature,
  1–30 Sep 2018 (647 of 697 hours; MHL filter `DATA_STATUS <= 6`).

Each station's constants are in its site's entry in `config/sites.yml`
(`tide_gauge`, and `tide_gauge_check` for Patonga), taken from MHL:

| Station | Station datum | AHD = SD − | MSL | ISLW | HHWSS (m AHD, 2018–19) |
|---|---|---|---|---|---|
| Jervis Bay 216470 | Jervis Bay Port Datum (1958) | 1.070 | +0.074 | −0.776 | +1.028 |
| Sydney 213470 | Zero Fort Denison (1897) | 0.925 | +0.050 | −0.807 | +1.005 |
| Patonga 212440 | AHD | 0.000 | +0.065 | −0.808 | +1.034 |
| Princess Jetty 216410 | AHD | 0.000 | +0.049 | −0.726 | +0.914 |

Datum adjustments are from the *Data conditions and limitations* PDF. Tidal
planes are from each station's page, which loads its table by script; the
table itself is at
`https://www.mhl.nsw.gov.au/s3/www/stations/planes/<station>_<Name>_table.html`
(read with a browser-style User-Agent). Not Ocean Street Bridge (213408D): it
records Narrabeen Lagoon, not the sea.

A cross-check gauge is read into `outputs/sensitivity/` only:

```
python -m sdb.waterlevel --site narrabeen_long_reef --scene <scene> --gauge-file <Patonga csv> --gauge-key tide_gauge_check --tag patonga
```

### 6. Substrate layers  *(fetched via QGIS; never committed)*

Used only to group validation errors, never as model inputs. One GeoPackage
per site, `raw/substrate/substrate_<site>.gpkg` (layers `macrophytes`,
`reef_extent`, `reef_sources`; EPSG:4283 as served), which `substrate` reads by
default, with a provenance JSON recording the queries, counts and md5
(`provenance.json` for Jervis Bay, `provenance_<site>.json` for the others).
Commit derived statistics only. The services are reachable from a desktop
(QGIS's Python was used), not from every network; since Nov 2026 the Fisheries
service refuses Python's default User-Agent, so send a browser-style one.

| Site | Fetched | Macrophyte / reef-extent / reef-source polygons | Macrophyte mapping |
|---|---|---|---|
| Jervis Bay | 27 Sep 2026 | 5,937 / 1,671 / 1,131 | Aug 2019 aerial, field May 2020 |
| Northern Beaches | 16 Nov 2026 | 1,404 / 1,781 / 475 | Pittwater Aug–Sep 2018 (field Aug 2019); Narrabeen, Dee Why, Manly lagoons Jun 2008 (field May 2010) |
| Batemans Bay | 16 Nov 2026 | 718 / 1,901 / 1,469 | Clyde, Cullendulla Creek, the bay: 2012–2022 aerial, field Feb 2023 |

The macrophyte layer maps estuaries only. At Northern Beaches every polygon is
in Pittwater, the lagoons or the Hawkesbury, all outside the open-coast rule,
so the site's seagrass strata are empty by construction — "not mapped", not
"absent". Its substrate comparison is reef against sediment.

- **NSW DPI Fisheries — Estuarine Macrophytes** (seagrass: *Posidonia*,
  *Zostera*, *Halophila*). Jervis Bay mapped from Aug 2019 aerial imagery,
  field-checked May 2020. ArcGIS REST:
  `spatial.industry.nsw.gov.au/arcgis/rest/services/Fisheries_Portal/Estuarine_Macrophytes/MapServer/0`.
  © NSW DPI Fisheries; CC BY 4.0 as stated by the service (an IMAS copy states CC BY-NC).
- **DCCEEW — NSW seabed reef extent**, classified from the 2018 marine lidar.
  ArcGIS REST: `mapprod3.environment.nsw.gov.au/arcgis/rest/services/Marine/NSW_seabed_reef_extent/MapServer`.
  CC BY 4.0.

---

### 7. Basemap for the location map  *(copied from QGIS; never committed)*

`scripts/figures.py` draws the locator panel of Figure 1 from Natural Earth
admin-1 boundaries (public domain), read from the `world_map.gpkg` that ships
with QGIS (`resources/data/world_map.gpkg` in a QGIS 3.40 install). Copy it to
`data/raw/basemap/world_map_qgis340.gpkg`; layer `states_provinces` is used.
Natural Earth's own admin-1 download works too if the layer name is changed.

## Reference lidar for replication — a release, not the repo

The four 5 m extracts the validation used are published, unmodified, as one
GitHub release asset rather than committed: **release `reference-lidar-2018`**,
`sdbNSW_reference_lidar_2018.zip` (116,741,451 bytes, md5
`1170eddb15480750a0adf5da849d0616`). Unzip at the repo root; every file lands
at the path `config/sites.yml` and `BUILD_GUIDE.md` expect, with the
attribution above and a `MANIFEST.md5`.

| File (under `raw/`) | md5 | Used for |
|---|---|---|
| `JervisBay/…/NSW_Marine_5m_TopoBathy_DEM.tif` | `1fc6c508dc4c5681501722a5234fa10c` | Jervis Bay reference (mostly averaged, see section 1) |
| `Narrabeen/B/…/NSW_Marine_5m_TopoBathy_DEM.tif` | `2d577a785cb8a76a2d1b9abd57b55645` | Northern Beaches reference (native) |
| `Narrabeen/…/NSW_Marine_5m_TopoBathy_DEM.tif` | `e956c123256df2e2595c5682af9473d7` | Northern Beaches averaging sensitivity (`--tag elvis_avg`) |
| `BatemansBay/BatemansBay_5m_native_AB.tif` (+ `.json`) | `3e79901571ccc8a5d7bdda7d337f2c09` | Batemans Bay reference (native union) |

The zip is rebuilt only if a reference changes; its md5s match those recorded
in `outputs/reference_*.json`.

## What is committed under `reference/`

| File | Derived from | Notes |
|---|---|---|
| `nsw_marine_lidar_blocks_index.csv` | coverage shapefile | All 48 survey blocks, attributes only. `CAPT_END` is the capture date used for scene pairing. |
| `jervisbay_lidar_blocks.geojson` | coverage shapefile | The five blocks intersecting the Jervis Bay AOI, simplified to 20 m, WGS84. |

### Site 1 — measured, not estimated

```
block        JervisBay  (NS_ID 33, COMPCODE NSW020502)
product      JervisBay2018_DEM_2866107_01_005
captured     2018-09-08
area         178.4 km2
bbox WGS84   150.6607, -35.1504, 150.8083, -34.9735
native CRS   EPSG:7856  (GDA2020 / MGA zone 56)
```

All five blocks covering the AOI were flown 8–9 September 2018, so scene
pairing targets a two-day window rather than the survey's full
8 July – 3 October 2018 span. The delivery spans all five blocks' rasters and
is therefore ELVIS-averaged except in a patch on the Beecroft coast
(`dem_extracts.py check`: 9% of underwater cells on the cm lattice).

### Site 2 — Northern Beaches

```
block        SydneyNorth  (NS_ID 23, COMPCODE NSW020302)
product      SydneyNorth2018_DEM_3376256_01_005
captured     to 2018-09-18 (CAPT_END)
ordered      lon 151.24-151.37, lat -33.7867 to -33.592  (inside SydneyNorth only)
saved        raw/Narrabeen/B/NSW Government - DCCEEW/DEM/5 Metre/
check        native: 97% of underwater cells on the cm lattice; bit-identical
             to the first (small) clip on 327,640 cells
AOI          151.2460, -33.7867, 151.3570, -33.5918  (MGA56 E 337230-347890,
             N 6260100-6281900: clear of SydneyHarbour, flown 18 Aug, and
             BrokenBay, 24 Aug)
0-20 m       35.5 km2 in the AOI, 34 two-km blocks; laser reached 41.2 m
open coast   only water joined to the sea at 151.33, -33.74 is assessed
             (Phase 4 amendment, 16 Nov 2026): at the measured +0.501 m AHD,
             21.6 km2 usable in 21 two-km blocks; Pittwater and the lagoons
             (11.5 km2 of water) are flagged 64
```

`raw/Narrabeen/NSW Government - DCCEEW/` holds the earlier whole-block extract,
which ELVIS averaged. It is kept as the input for the Phase 4 sensitivity run,
never as the reference.

### Site 3 — Batemans Bay

```
block        BatemansBay  (COMPCODE NSW020602)
product      BatemansBay2018_DEM_2436036_01_005
captured     2018-08-24 (CAPT_END)
ordered      A: lon 150.1607-150.2388, lat -35.77 to -35.687
             B: lon 150.1592-150.2906, lat -35.77 to -35.7304
             (inside BatemansBay only: MoruyaCoast and Murramurang rasters
             overlap the block's other corners)
saved        raw/BatemansBay/A/..., raw/BatemansBay/B/...
joined       raw/BatemansBay/BatemansBay_5m_native_AB.tif (+ .json sidecar),
             by dem_extracts.py merge; overlap 881,967 cells, bit-identical
AOI          150.1592, -35.7700, 150.2906, -35.6870 (A u B; the far north-east
             corner is not covered)
0-20 m       28.4 km2, 21 two-km blocks; laser reached 40.6 m
```
