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
account, nothing to download by hand. See `src/sdb/stac.py`.

### 4. MHL NSW tide data

Water level at scene acquisition time, for the vertical offset between
instantaneous depth and AHD. Source: [MHL](http://new.mhl.nsw.gov.au/).
Save to `raw/`.

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
