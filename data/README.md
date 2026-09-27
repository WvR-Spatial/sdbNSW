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
| `mask.tif` | uint8 bit flags, 0 = usable: 1 lidar incomplete · 2 land · 4 outside depth window · 8 cloud/shadow · 16 bright NIR over lidar water · 32 no image |

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

- Times are **AEST** (UTC+10, no daylight saving).
- Gauge datum is **chart datum**; AHD = CD − 1.07 m. MHL's labels are not
  reliable on this, so `waterlevel` infers the datum from the record's mean.

Until it arrives, `waterlevel --from-image` gives a provisional estimate
(−0.50 m AHD at Jervis Bay, biased low by ~0.1–0.2 m).

### 6. Substrate layers  *(fetched via QGIS; never committed)*

Used only to group validation errors, never as model inputs. Saved to
`raw/substrate/substrate_jervis_bay.gpkg` (layers `macrophytes`, `reef_extent`,
`reef_sources`; EPSG:4283 as served) with `provenance.json` recording the
queries, counts and md5. Commit derived statistics only. The services are
reachable from a desktop (QGIS's Python was used), not from every network.

- **NSW DPI Fisheries — Estuarine Macrophytes** (seagrass: *Posidonia*,
  *Zostera*, *Halophila*). Jervis Bay mapped from Aug 2019 aerial imagery,
  field-checked May 2020. ArcGIS REST:
  `spatial.industry.nsw.gov.au/arcgis/rest/services/Fisheries_Portal/Estuarine_Macrophytes/MapServer/0`.
  © NSW DPI Fisheries; CC BY 4.0 as stated by the service (an IMAS copy states CC BY-NC).
- **DCCEEW — NSW seabed reef extent**, classified from the 2018 marine lidar.
  ArcGIS REST: `mapprod3.environment.nsw.gov.au/arcgis/rest/services/Marine/NSW_seabed_reef_extent/MapServer`.
  CC BY 4.0.

---

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
8 July – 3 October 2018 span.
