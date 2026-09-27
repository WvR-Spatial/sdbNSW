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

**→ CLAUDE** — `src/sdb/reference.py`: load the lidar and **aggregate** it onto
the Sentinel-2 10 m grid (never upsample the imagery to 5 m), mask land and the
surf zone, produce an aligned reference array.

**→ YOU · QGIS** — the visual check, and it matters more than it sounds.
Load the scene and the lidar together:
- Can you actually see the seabed in the imagery? If not, no method will.
- Do features line up — reef edges, channel margins? A half-pixel
  misregistration is worth several metres of apparent error.
- Where is the surf zone, and is it masked?

QGIS via MCP is fine for this looking-and-poking. **Nothing that touches the
pipeline gets done in the GUI** — anything GUI-driven is not reproducible by a
reader, which is the exact criticism that sinks the Murray REM piece.

**Gate:** seabed visible, alignment confirmed. Otherwise try another scene
before laying a finger on the method.

---

## Phase 2 — Empirical SDB, first number

**→ CLAUDE** — `src/sdb/sdb.py` (Stumpf ratio transform, calibration against
a reference subset) and `src/sdb/waterlevel.py` (tide at acquisition time as a
scalar vertical offset). Plus `tests/` — every function checked against an
analytically known answer, in the style of `narrabeen-stage1`.

**→ YOU** — fetch the MHL tide series for the site and period. Run `pytest`.
Run the pipeline. Bring back the first RMSE.

**Gate:** site 1 RMSE within roughly 2× the literature (< ~4 m). If it is
wildly worse, the fault is almost always water level, sun glint, or
misregistration — in that order. **Do not tune the model to make the number
look better.** Find the cause.

---

## Phase 3 — Validation done properly

**→ CLAUDE** — `src/sdb/validate.py`: spatially blocked cross-validation,
error stratified by depth band and substrate, the breakdown-depth statistic.
Report the naive random-split number alongside the blocked one.

**→ YOU** — obtain the substrate/seagrass layer for the site from SEED.

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
