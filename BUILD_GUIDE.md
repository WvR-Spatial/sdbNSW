# Build guide — how this gets assembled

Companion to `PROJECT_BRIEF.md`. Read the brief first; it holds the *why* and
the decision gates. This holds the *how*, and marks who does what.

**→ YOU** = your hands, your machine, your judgement.
**→ CLAUDE** = I write it, you review and run it.

Neither the cloud container nor the Cowork workspace can reach the Sentinel-2
STAC endpoint or the Open-Meteo wind API — both sit behind an egress allowlist
and return 403 at the proxy. **All network fetches run in your own Python environment on Windows**
(or in GitHub Actions, which has unrestricted network). Plan around that: I
write and review code, you execute it and bring back the output.

---

## Phase 0 — Setup

**→ YOU · one evening, plus waiting time**

1. **Repo** — `sdbNSW`, cloned to `C:\Study\Claude\sdbNSW`. *Done.*
2. **Python environment** — conda-forge only, separate from your ArcPy
   environment. GDAL conflicts are not worth the afternoon. *Done.*
   ```
   conda env create -f environment.yml
   conda activate sdbnsw
   pip install -e . --no-deps
   ```
   `--no-deps` stops pip installing PyPI wheels with their own GDAL on top of
   conda's. Commands in this guide are written for the **Anaconda Prompt
   (cmd.exe)**, not PowerShell.
3. **Order the reference lidar.** ELVIS uses area-select then asynchronous
   delivery — you draw a polygon, it emails you a download link. This can take
   hours to a day, so **do it first**, before anything else.
   - Site 1 (Jervis Bay) only at this stage.
   - Take the **GeoTIFF** product, not the LAS point cloud, for v1.
   - Record the acquisition date of each tile. You need it for scene pairing.
4. **Note the attribution string** required by CC BY 4.0. It goes in the
   README and on the portfolio page, not just in a footnote.

**Gate:** lidar tile on disk, opens in QGIS, has sensible depth values in AHD.

---

## Phase 1 — One site, one scene

**→ CLAUDE** — `src/sdb/stac.py`: query Earth Search for Sentinel-2 L2A over
the site bbox, filter on cloud cover, sun elevation and glint risk, rank
candidates by proximity to the lidar acquisition date. Writes a candidate
table, downloads nothing.

It also pulls ERA5 wind at each overpass (one request to Open-Meteo) and adds
`glint_sigma`: how unusual a wave slope must be to glint, in standard
deviations, from wind speed and its direction against the sun. **Lower is more
glint-prone.** Rank with it; do not treat it as a value. `--no-wind` skips it; if the API is unreachable the search carries on
with the columns empty.

**→ YOU** — run it. Bring back the candidate table.

**→ YOU + CLAUDE together** — shortlist. This is a judgement call, not a
sort: lowest cloud is not always best if it sits six months from the lidar
date, and a glinty calm day can beat a clear windy one.

**→ YOU** — `python -m sdb.fetch quicklook --top 3`. Reads only the SCL and
true-colour assets over the AOI and reports **cloud over the AOI**, which the
tile-wide figure cannot tell you, plus a panel stretched over water so seabed
texture is visible. Bring back the panel and table; we pick the scene.

**→ YOU** — `python -m sdb.fetch scene --item <id>`. Writes the reflectance
stack to `data/raw/scenes/<id>/`. It refuses to write if the reflectance fails
the water plausibility check — that means the offset is wrong, and nothing
downstream should be built on it.

**→ CLAUDE** — `coreg.py` measures how far the image sits from its true
position by matching it to NSW orthoimagery over land (`ortho.py`);
`waterlevel.py` gives the water level at overpass; `reference.py` aggregates
the lidar onto the scene's 10 m grid (never the other way round), applying
both, and writes the masks. *Done.*

**→ YOU** — run, in this order (the first fetches ~30 MB of orthophoto once,
into gitignored `data/raw/ortho/`):
```
python -m sdb.coreg --scene S2A_56HKG_20180907_0_L2A
python -m sdb.waterlevel --scene S2A_56HKG_20180907_0_L2A --from-image
python -m sdb.reference --scene S2A_56HKG_20180907_0_L2A
```
Expected at Jervis Bay: shift **E −7.42, N −1.02 m**, verdict `APPLY`; water
level **−0.496 m AHD (provisional)**; **937,499** usable pixels. Different
numbers mean a different environment or input — stop and bring them back.

The first co-registration method (steep shorelines) was ~14 m wrong here and is
kept only as a diagnostic: `python -m sdb.coreg --scene … --method waterline`
writes a separate record that nothing reads.

**→ YOU** — request the observed water level from MHL, Jervis Bay gauge
216470, for 6–8 September 2018 (form under *Data Request* on
mhl.nsw.gov.au, or data-request@mhl.nsw.gov.au). When the CSV arrives, save it
under `data/raw/tide/` and run:
```
python -m sdb.waterlevel --scene S2A_56HKG_20180907_0_L2A --gauge-file data\raw\tide\<file>.csv
python -m sdb.reference --scene S2A_56HKG_20180907_0_L2A
```
The datum is inferred from the record's mean and checked against the header's
statement (a contradiction is refused); times are taken as AEST. *Done 29 Sep:
−0.392 m AHD, superseding the provisional −0.496; `reference` then gives
932,838 usable pixels (93.28 km²).*

**→ YOU · QGIS** — the visual check, done 27 Sep, and it caught the first
co-registration. It stays in the guide for sites 2 and 3: compare the scene
with an **independent orthophoto on land** (runways, roads, street grids), not
at the shoreline, where shadowed cliffs, whitewater and tide all move the edge.
Also: can you see the seabed? Does `mask.tif` flag 16 sit on beaches, reefs and
the outer coast rather than open water?

QGIS via MCP is fine for this looking-and-poking. **Nothing that touches the
pipeline gets done in the GUI** — anything GUI-driven is not reproducible by a
reader, which is the exact criticism that sinks the Murray REM piece.

**Gate:** seabed visible; co-registration confirmed on land. *Passed on
geometry; water level measured by the gauge on 29 Sep.*

---

## Phase 2 — Empirical SDB, first number

The method is fixed in advance: *Phase 2 protocol* in `PROJECT_BRIEF.md`,
committed in `8332154` before any model saw real data. The code implements it
and records any departure as a deviation.

**→ CLAUDE (done)** — `src/sdb/sdb.py` (Stumpf transform and the calibration
rule), `src/sdb/validate.py` (blocked cross-validation, statistics, breakdown
depth, CLI), `src/sdb/viz.py` (figures). Tests: `tests/test_sdb.py`,
`tests/test_validate.py` — including the water-level invariance and a leakage
demonstration. **225 tests** with `tests/test_substrate.py`.

**→ YOU** —

```
pytest -q
python -m sdb.validate --scene S2A_56HKG_20180907_0_L2A
```

~40 s. Expected at the provisional water level (−0.496 m AHD), from inputs with
md5 `bb441e91…` (reflectance), `5e165671…` (reference), `b3188e21…` (mask):

| | |
|---|---|
| Pooled RMSE (2 km blocks, 5-fold × 10) | **2.70 m** [2.32, 3.15], bias −0.41 m, R² 0.688 |
| Naive random split | 2.67 m (blocked / naive 1.009) |
| Depth-balanced RMSE | 2.48 m |
| Inside bay / open coast | 2.28 m / 4.72 m |
| Breakdown depth, CATZOC C and B | **0 m** — exceeded from the shallowest bin |
| Saturation depth D_cal | 16–20 m (median 20) |
| Residual correlation range | 4000 m — exceeds the block: caveat applies |
| Gate | **PASS** |

It writes `outputs/sdb_<scene>.json`, three figures in `outputs/figures/`,
and `sdb.tif` (out-of-fold depth and residual) beside the scene. Commit the
JSON and figures; `sdb.tif` stays in gitignored `data/raw/`.

**With the gauge record (29 Sep):** `waterlevel --gauge-file …` → `reference` →
`validate` → `substrate`. Expected: pooled RMSE **2.68 m** [2.31, 3.13], bias
−0.42 m, 932,838 pixels; substrate reef +1.66 m at 5–10 m. Both runs are
reported in the brief.

**Gate:** site 1 RMSE within roughly 2× the literature (< ~4 m). If it is
wildly worse, the fault is almost always water level, sun glint, or
misregistration — in that order. **Do not tune the model to make the number
look better.** Find the cause.

---

## Phase 3 — Validation done properly

Blocked cross-validation, the naive split and the breakdown statistic already
run in `validate.py` (Phase 2). What remains here is substrate, and ML (v2).

**→ YOU + CLAUDE** — substrate: fetch the NSW DPI *Estuarine Macrophytes*
(seagrass) and DCCEEW *seabed reef extent* layers for Jervis Bay into
`data/raw/substrate/` (their ArcGIS REST services are reachable from your
machine, not from the cloud workspace). Then: check the mapping dates, how much
of the usable area each class covers by depth band, and alignment against the
scene; fix the class rules **before** errors by substrate are computed.
*Done: layers in `data/raw/substrate/`, rules committed in `73d02ce`.*

```
python -m sdb.substrate --scene S2A_56HKG_20180907_0_L2A
```

~15 s. Reads `sdb.tif` from Phase 2 (no refit). Expected: inside the bay,
*Posidonia* minus sediment −1.89 m (0–2 m), +0.24 (2–5), +0.12 (5–10); reef
+1.66 (5–10), +1.70 (10–15), +1.66 (15–20). Writes
`outputs/substrate_<scene>.json`, one figure, and `substrate.tif` beside the
scene. Commit the JSON and figure.

**Exploratory follow-up** (labelled, never replaces a registered result;
writes only to `outputs/exploratory/`):

```
python -m sdb.validate --scene S2A_56HKG_20180907_0_L2A --exploratory rule95
python -m sdb.substrate --scene S2A_56HKG_20180907_0_L2A --tag rule95
python scripts\calibration_form_check.py --scene S2A_56HKG_20180907_0_L2A
```

Expected: pooled RMSE 2.82 m, D_cal 16–18 m; substrate contrasts within 0.1 m
of the registered ones; the script prints slopes 49.4 vs 62.2 and pooled RMSE
2.68 vs 3.02 m.

**→ YOU** — read the output and decide whether you believe it. The gap
between the naive and blocked numbers is a result in its own right and
deserves a paragraph.

---

## Phase 4 — Three sites

**→ YOU** — order lidar for sites 2 and 3 from ELVIS (async again — order
both at the start of this phase).

**→ CLAUDE** — `config/sites.yml`, and whatever the pipeline needs to run
per-site without copy-paste.

**→ YOU** — run all three. Bring back the comparison.

**Gate:** does error track water clarity monotonically? If it does, you have a
clean finding. If it does not, that is a more interesting finding — report it
and say what you think is confounding it.

---

## Phase 5 — Publish

**→ CLAUDE** — `src/sdb/viz.py` and the figures; the GitHub Pages deliverable
in `site/`; repo hygiene.

**→ YOU · this part cannot be delegated** — write the limitations panel in
your own words, **before** writing the results section. It is the part of your
work that reads as yours, and it is the reason the fire and seismic pieces
land. If you cannot say a limitation aloud in plain language, you do not yet
understand it well enough to publish the result.

**→ YOU** — update the portfolio: remove the Murray REM card, add this one
with its number, commit the patched `index.html` from
`C:\Study\Claude\Portfolio\` if not already done.

**→ CLAUDE** — update `PROJECT_BRIEF.md` to match what was actually built,
and write the portfolio state doc entry.

---

## Working rhythm

- Start each session by pointing me at `PROJECT_BRIEF.md`. It is the memory;
  I have none between sessions.
- One phase per session where possible. Bring back the output of the last
  phase, not a description of it.
- When a gate fails, stop and diagnose rather than proceeding with a worse
  number. The Narrabeen lesson was not "the data was wrong" — it was that the
  mismatch surfaced after the effort, not before.
- Record decisions in the brief as they are made, including the ones we
  reverse. A decision register is the difference between a portfolio piece and
  a folder of scripts.

## Tools, at a glance

| Job | Tool | Whose hands |
|---|---|---|
| Reference data order | ELVIS web portal | You |
| Imagery discovery | `pystac-client` → Earth Search | You run, I write |
| Wind at overpass | Open-Meteo archive (ERA5) | You run, I write |
| Raster processing | `rioxarray` / `rasterio` | I write, you run |
| Visual QA | QGIS (incl. MCP) | You |
| Statistics | `numpy` / `scikit-learn` | I write |
| Tests | `pytest` | I write, you run |
| Version control | git / GitHub | You |
| Publication | GitHub Pages | I write, you deploy |
