"""Tests for co-registration against reference orthoimagery.

No network: the service is replaced by a fake opener. Synthetic scenes are made
the way the sensor makes them -- the reference aggregated onto the scene grid
displaced by a KNOWN shift, blurred, re-scaled radiometrically, with noise --
so recovery, sign and the across-window rules are checked against known truth.
"""
from __future__ import annotations

import io
import json
import math
from pathlib import Path

import numpy as np
import pytest
from scipy import ndimage

from sdb import ortho as O
from sdb.reference import Grid, area_weights, block_sum

RNG = np.random.default_rng(7)
WIN = Grid(290000.0, 6110000.0, 10.0, 10.0, 200, 200)


def _texture(ny, nx, seed=0):
    """Roads (lines), blobs and noise -- the kind of structure the method uses."""
    r = np.random.default_rng(seed)
    f = ndimage.gaussian_filter(r.normal(size=(ny, nx)), 6) * 40 + 120
    for _ in range(12):
        i = r.integers(0, ny - 4); f[i:i + 4, :] += 60
        j = r.integers(0, nx - 3); f[:, j:j + 3] += 50
    return f + r.normal(0, 5, f.shape)


def _ortho_for(win: Grid, seed=0):
    pad = O.SEARCH_M + 10
    og = Grid(win.x0 - pad, win.y0 + pad, 2.0, 2.0,
              int((win.nx * win.dx + 2 * pad) / 2), int((win.ny * win.dy + 2 * pad) / 2))
    return _texture(og.ny, og.nx, seed).astype(np.float32), og


def _sensor(ortho, og, win, shift, seed=1):
    """What the scene records if each pixel really saw ground at nominal + shift."""
    r = np.random.default_rng(seed)
    wy, wx = area_weights(og, win.shifted(*shift))
    img = block_sum(ortho.astype(np.float64), wy, wx) / block_sum(np.ones_like(ortho, float), wy, wx)
    img = ndimage.gaussian_filter(img, 0.6)
    img = 0.0004 * np.clip(img, 1, None) ** 1.1 + 0.02          # different radiometry
    return (img + r.normal(0, 0.002, img.shape)).astype(np.float32)


# --- fetch (fake server) ---------------------------------------------------

class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _png_bytes(w, h):
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(np.full((h, w, 3), 128, np.uint8)).save(buf, format="PNG")
    return buf.getvalue()


def _fake_server(bbox, w, h, *, offer=None, body=None, fail_first=0):
    calls = {"n": 0}

    def opener(url, timeout):
        calls["n"] += 1
        if calls["n"] <= fail_first:
            raise TimeoutError("simulated")
        if "f=json" in url:
            x0, y0, x1, y1 = offer or bbox
            return _Resp(json.dumps({"width": w, "height": h, "extent": {
                "xmin": x0, "ymin": y0, "xmax": x1, "ymax": y1}}).encode())
        return _Resp(body if body is not None else _png_bytes(w, h))
    return opener, calls


BBOX = [285970.0, 6116290.0, 286070.0, 6116390.0]      # 100 m -> 50 px at 2 m


def test_fetch_writes_png_and_sidecar_then_uses_the_cache(tmp_path):
    opener, calls = _fake_server(BBOX, 50, 50)
    png = O.fetch_window(BBOX, 2.0, tmp_path, opener=opener)
    side = json.loads(png.with_suffix(".json").read_text())
    assert png.name == "E285970_N6116290_100x100m_2m.png"
    assert side["bbox"] == BBOX and side["size"] == [50, 50] and side["epsg"] == 32756
    assert "Spatial Services" in side["attribution"]
    n = calls["n"]
    O.fetch_window(BBOX, 2.0, tmp_path, opener=opener)
    assert calls["n"] == n                               # cached, not refetched


def test_fetch_refuses_an_extent_the_server_would_change(tmp_path):
    opener, _ = _fake_server(BBOX, 50, 50, offer=[BBOX[0] - 5, *BBOX[1:]])
    with pytest.raises(RuntimeError, match="honour"):
        O.fetch_window(BBOX, 2.0, tmp_path, opener=opener)


def test_fetch_refuses_something_that_is_not_a_png(tmp_path):
    opener, _ = _fake_server(BBOX, 50, 50, body=b"<html>error</html>")
    with pytest.raises(RuntimeError, match="PNG"):
        O.fetch_window(BBOX, 2.0, tmp_path, opener=opener)


def test_fetch_retries_transient_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(O.time, "sleep", lambda s: None)
    opener, _ = _fake_server(BBOX, 50, 50, fail_first=1)
    assert O.fetch_window(BBOX, 2.0, tmp_path, opener=opener).exists()


def test_load_window_georeferences_from_the_sidecar(tmp_path):
    opener, _ = _fake_server(BBOX, 50, 50)
    img, g = O.load_window(O.fetch_window(BBOX, 2.0, tmp_path, opener=opener))
    assert img.shape == (50, 50)
    assert (g.x0, g.y0, g.dx, g.dy) == (BBOX[0], BBOX[3], 2.0, 2.0)


# --- window selection ------------------------------------------------------

def test_windows_land_only_textured_first_and_spread():
    grid = Grid(0.0, 20000.0, 10.0, 10.0, 1000, 1000)
    land = np.zeros(grid.shape, bool)
    land[:, :500] = True                                   # west half land, east half sea
    g = np.zeros(grid.shape, np.float32)
    g[:, :500] = _texture(1000, 500, seed=3)[:, :500] * 1e-3
    g[:500, :500] += RNG.normal(0, 0.05, (500, 500))       # extra texture in the north-west
    wins = O.select_windows(land, g, grid, n=12)
    assert wins and all(w["bbox"][2] <= 5000 + 1e-6 for w in wins)          # no sea windows
    cy = [(w["bbox"][1] + w["bbox"][3]) / 2 for w in wins]
    assert cy[0] > 10000                                   # most textured (north) comes first
    for i, a in enumerate(wins):
        for b in wins[i + 1:]:
            d = math.hypot((a["bbox"][0] - b["bbox"][0]), (a["bbox"][1] - b["bbox"][1]))
            assert d >= O.SPACING_FACTOR * O.WINDOW_M - 1e-6


def test_fetch_bbox_adds_the_search_margin():
    x0, y0, x1, y1 = O.fetch_bbox({"bbox": [0, 0, 2000, 2000]})
    assert x0 == -(O.SEARCH_M + 10) and x1 == 2000 + O.SEARCH_M + 10


# --- registration ----------------------------------------------------------

@pytest.mark.parametrize("shift", [(-7.4, -1.0), (12.2, 7.9), (-18.5, -11.1)])
def test_recovers_a_known_shift_with_the_right_sign(shift):
    ortho, og = _ortho_for(WIN)
    img = _sensor(ortho, og, WIN, shift)
    r = O.register_window(img, WIN, np.ones(img.shape, bool), ortho, og)
    assert r["status"] == "ok"
    assert r["shift_e"] == pytest.approx(shift[0], abs=0.7)
    assert r["shift_n"] == pytest.approx(shift[1], abs=0.7)
    assert r["peak_corr"] > r["corr_at_zero"]


def test_no_shift_reads_as_near_zero():
    ortho, og = _ortho_for(WIN)
    r = O.register_window(_sensor(ortho, og, WIN, (0.0, 0.0)), WIN, np.ones((200, 200), bool), ortho, og)
    assert math.hypot(r["shift_e"], r["shift_n"]) < 0.7


def test_structureless_window_is_not_trusted():
    ortho, og = _ortho_for(WIN)
    flat = np.full((200, 200), 0.05, np.float32) + RNG.normal(0, 0.002, (200, 200)).astype(np.float32)
    r = O.register_window(flat, WIN, np.ones((200, 200), bool), ortho, og)
    assert r["status"] != "ok"


# --- combining windows -----------------------------------------------------

def _w(i, e, n, status="ok"):
    return {"window": i, "shift_e": e, "shift_n": n, "status": status}


def test_combine_takes_the_median_and_drops_an_outlier():
    rows = [_w(i, -7.4 + d, -1.0 - d) for i, d in enumerate((-1.2, -0.5, 0.0, 0.3, 0.8, 1.1))]
    rows.append(_w(9, 15.1, -1.0))
    out = O.combine(rows)
    assert out["windows_dropped"] == [9]
    assert out["shift_m"]["east"] == pytest.approx(-7.4 + 0.15, abs=0.2)
    assert out["verdict"] == "apply"


def test_combine_verdicts():
    assert O.combine([_w(i, -7, -1) for i in range(3)])["verdict"] == "insufficient"
    assert O.combine([_w(i, -7, -1, "weak correlation") for i in range(6)])["verdict"] == "insufficient"
    small = [_w(i, 0.3 * (-1) ** i, 0.2) for i in range(6)]
    assert O.combine(small)["verdict"] == "negligible"
    wild = [_w(i, v, 0.0) for i, v in enumerate((-20, -12, -4, 4, 12, 20))]
    assert O.combine(wild)["verdict"] == "inconsistent"


def test_combine_reports_the_reference_datum_ambiguity():
    out = O.combine([_w(i, -7.4, -1.0) for i in range(5)])
    assert out["datum_ambiguity_m"] == O.DATUM_AMBIGUITY_M


# --- end to end: coreg CLI -> reference CLI, no network ----------------------

def test_cli_measures_records_and_reference_applies_it(tmp_path, monkeypatch):
    import rasterio
    import yaml

    from sdb import coreg, reference

    true = (-7.4, -1.0)
    scene = Grid(300000.0, 6120000.0, 10.0, 10.0, 520, 520)
    # a textured landscape, sampled as the sensor would with a known shift
    big = Grid(scene.x0 - 100, scene.y0 + 100, 2.0, 2.0, 2700, 2700)
    field = _texture(big.ny, big.nx, seed=11).astype(np.float32)
    img = _sensor(field, big, scene, true, seed=5)

    root = tmp_path
    sd = root / "data" / "raw" / "scenes" / "SCENE"
    sd.mkdir(parents=True)
    prof = dict(driver="GTiff", width=scene.nx, height=scene.ny, crs="EPSG:32756",
                transform=scene.transform(), dtype="float32")
    with rasterio.open(sd / "reflectance.tif", "w", count=4, **prof) as dst:
        for i, name in enumerate(("blue", "green", "red", "nir"), 1):
            dst.write(img if name != "nir" else img * 3 + 0.2, i)
            dst.set_band_description(i, name)
    with rasterio.open(sd / "scl.tif", "w", count=1, **{**prof, "dtype": "uint8"}) as dst:
        dst.write(np.full((scene.ny, scene.nx), 4, np.uint8), 1)       # all vegetation

    # pre-populate the orthophoto cache with the same field, so no network is used
    from PIL import Image
    g = O.grey(img, img, img)
    wins = O.select_windows(np.ones(scene.shape, bool), g, scene, n=12, window_m=1000.0)
    cache = root / "data" / "raw" / "ortho" / "testsite"
    cache.mkdir(parents=True)
    for w in wins:
        fb = O.fetch_bbox(w)
        c0 = int(round((fb[0] - big.x0) / 2)); r0 = int(round((big.y0 - fb[3]) / 2))
        nx, ny = int(round((fb[2] - fb[0]) / 2)), int(round((fb[3] - fb[1]) / 2))
        sub = np.clip(field[r0:r0 + ny, c0:c0 + nx], 0, 255).astype(np.uint8)
        stem = O.window_filename(fb, O.ORTHO_RES_M)
        Image.fromarray(np.stack([sub] * 3, -1)).save(cache / f"{stem}.png")
        (cache / f"{stem}.json").write_text(json.dumps({"bbox": fb, "size": [nx, ny], "epsg": 32756}))

    def no_network(*a, **k):
        raise AssertionError("tried to use the network")
    monkeypatch.setattr(O.urllib.request, "urlopen", no_network)

    # a flat DEM so reference.py has something to aggregate
    dem = root / "dem.tif"
    with rasterio.open(dem, "w", driver="GTiff", width=1040, height=1040, count=1, dtype="float32",
                       crs="EPSG:7856", transform=Grid(scene.x0, scene.y0, 5.0, 5.0, 1040, 1040).transform(),
                       nodata=-9999.0) as dst:
        dst.write(np.full((1040, 1040), -8.0, np.float32), 1)
    cfg = root / "sites.yml"
    cfg.write_text(yaml.safe_dump({"sites": {"testsite": {"reference_dem": "dem.tif"}}}))

    out = root / "outputs"
    assert coreg.main(["--site", "testsite", "--config", str(cfg), "--scene", "SCENE",
                       "--root", str(root), "--out", str(out), "--window-km", "1"]) == 0
    rec = json.loads((out / "coreg_SCENE.json").read_text())
    assert rec["method"] == "ortho" and rec["verdict"] == "apply"
    assert rec["shift_m"]["east"] == pytest.approx(true[0], abs=1.0)
    assert rec["shift_m"]["north"] == pytest.approx(true[1], abs=1.0)

    assert reference.main(["--site", "testsite", "--config", str(cfg), "--scene", "SCENE",
                           "--root", str(root), "--out", str(out)]) == 0
    ref = json.loads((out / "reference_SCENE.json").read_text())
    assert ref["coregistration"]["shift_applied_m"] == [rec["shift_m"]["east"], rec["shift_m"]["north"]]
    assert Path(sd / "reference.tif").exists()
