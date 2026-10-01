"""Tests for the water level at overpass.

The traps being guarded: Australian day-first dates (07/09 is 7 September),
AEST timestamps (UTC+10, no daylight saving), and a datum that MHL's own pages
mislabel -- so the datum is inferred from the numbers.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pytest

from sdb.waterlevel import (Gauge, image_estimate, infer_datum, level_at, plausible,
                            read_gauge_csv, to_ahd)

JB = Gauge("216470", "Jervis Bay (HMAS Creswell)", -1.07, 0.074, -0.776, 1.028, "test")
OVERPASS = datetime(2018, 9, 7, 0, 2, 37, tzinfo=timezone.utc)      # 10:02:37 AEST
H_OVERPASS = 34 + (2 + 37 / 60) / 60          # hours from 06/09/2018 00:00 AEST


def _tide(hours, amp=0.6, phase_h=4.0, msl=0.074):
    """A semidiurnal tide in m AHD, hours from 2018-09-06 00:00 AEST (the record start)."""
    return msl + amp * np.cos(2 * np.pi * (hours - phase_h) / 12.42)


def _write_mhl_csv(path, datum="cd", header=True, step_min=15):
    hours = np.arange(0, 48, step_min / 60)
    z = _tide(hours)
    if datum == "cd":
        z = z - JB.ahd_offset_m
    lines = []
    if header:
        lines += ["Station: 216470 Jervis Bay", "Variable: Water Level", "Units: m", "",
                  "Date/Time,Level (m),Quality"]
    for h, v in zip(hours, z):
        t = datetime(2018, 9, 6, 0, 0) + np.timedelta64(int(round(h * 60)), "m").astype(object)
        lines.append(f"{t:%d/%m/%Y %H:%M},{v:.3f},1")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return hours, z


# --- reading ---------------------------------------------------------------

def test_reads_day_first_aest_times_as_utc(tmp_path):
    f = tmp_path / "jb.csv"
    _write_mhl_csv(f)
    t, z, notes = read_gauge_csv(f)
    assert str(t[0]) == "2018-09-05T14:00:00"          # 06/09/2018 00:00 AEST
    assert notes["header_lines_skipped"] >= 4
    assert notes["level_column"].startswith("Level")
    assert "AEST" in notes["timezone_assumed"]


def test_reads_a_file_with_no_header(tmp_path):
    f = tmp_path / "bare.csv"
    _write_mhl_csv(f, header=False)
    t, z, _ = read_gauge_csv(f)
    assert len(t) == len(z) == 192


# --- datum -----------------------------------------------------------------

def test_datum_is_inferred_from_the_numbers(tmp_path):
    f = tmp_path / "cd.csv"
    _write_mhl_csv(f, datum="cd")
    _, z, _ = read_gauge_csv(f)
    assert infer_datum(z, JB) == "cd"
    assert infer_datum(to_ahd(z, "cd", JB), JB) == "ahd"


def test_an_ambiguous_mean_is_refused():
    with pytest.raises(ValueError, match="datum"):
        infer_datum(np.full(10, 0.61), JB)


def test_chart_datum_converts_with_the_station_offset():
    assert to_ahd(np.array([1.144]), "cd", JB)[0] == pytest.approx(0.074)


# --- interpolation ---------------------------------------------------------

def test_interpolates_to_the_overpass_and_reports_the_tidal_rate(tmp_path):
    f = tmp_path / "jb.csv"
    _write_mhl_csv(f, datum="cd")
    t, z, _ = read_gauge_csv(f)
    at = level_at(t, to_ahd(z, "cd", JB), OVERPASS)
    assert at["level"] == pytest.approx(_tide(H_OVERPASS), abs=0.005)
    assert at["gap_before_min"] <= 15 and at["gap_after_min"] <= 15
    assert at["tidal_rate_m_per_h"] != 0


def test_refuses_a_distant_or_unbracketed_sample():
    t = np.array(["2018-09-06T23:00:00", "2018-09-07T01:30:00"], dtype="datetime64[s]")
    with pytest.raises(ValueError, match="min"):
        level_at(t, np.array([0.1, 0.2]), OVERPASS)
    t2 = np.array(["2018-09-07T01:00:00", "2018-09-07T02:00:00"], dtype="datetime64[s]")
    with pytest.raises(ValueError, match="bracket"):
        level_at(t2, np.array([0.1, 0.2]), OVERPASS)


def test_plausibility_band():
    assert plausible(-0.45, JB) and plausible(1.2, JB)
    assert not plausible(-45.0, JB)                      # centimetres read as metres
    assert not plausible(2.3, JB)


# --- image estimate --------------------------------------------------------

def _beach_case(shape, true_wl):
    from sdb.reference import Grid, LandFractionField

    src = Grid(0.454, 3001.421, 5.0, 5.0, 600, 600)
    dst = Grid(0.0, 3000.0, 10.0, 10.0, 300, 300)
    x, y = src.centres()
    X, Y = np.meshgrid(x, y)
    z = ((X - 1500.0) / 25.0 if shape == "straight"
         else (1000.0 - np.hypot(X - 1500.0, Y - 1500.0)) / 25.0).astype(np.float32)   # 1:25 slope
    v = np.ones_like(z, bool)
    lf, cov = LandFractionField(z, v, src, true_wl).on(dst)
    rng = np.random.default_rng(2)
    nir = (0.003 + 0.25 * np.nan_to_num(lf) + rng.normal(0, 0.004, lf.shape)).astype(np.float32)
    return image_estimate(z, v, src, dst, nir, np.isfinite(nir) & (cov >= 0.999))


@pytest.mark.parametrize("true_wl", [-0.4, 0.2])
def test_image_estimate_recovers_the_level_on_a_curved_shoreline(true_wl):
    est = _beach_case("island", true_wl)
    assert est["status"] == "ok"
    assert est["level_m_ahd"] == pytest.approx(true_wl, abs=0.02)


def test_image_estimate_worst_case_is_one_straight_grid_aligned_shore():
    """Every mixed pixel at the same sub-pixel phase flattens the peak: ~6 cm
    (0.15 px on a 1:25 beach). Real coastlines cross pixels at all phases."""
    est = _beach_case("straight", -0.4)
    assert est["level_m_ahd"] == pytest.approx(-0.4, abs=0.1)


# --- CLI: gauge file -> record -> reference.py uses it --------------------------

def test_cli_gauge_record_is_used_by_reference(tmp_path):
    import rasterio
    import yaml

    from sdb import reference, waterlevel
    from sdb.reference import Grid

    root = tmp_path
    sd = root / "data" / "raw" / "scenes" / "S"
    sd.mkdir(parents=True)
    (sd / "provenance.json").write_text(json.dumps({"datetime_utc": "2018-09-07T00:02:37.460000Z"}))
    g = Grid(300000.0, 6120000.0, 10.0, 10.0, 60, 60)
    prof = dict(driver="GTiff", width=60, height=60, crs="EPSG:32756", transform=g.transform(),
                dtype="float32")
    with rasterio.open(sd / "reflectance.tif", "w", count=4, **prof) as dst:
        for i, n in enumerate(("blue", "green", "red", "nir"), 1):
            dst.write(np.full((60, 60), 0.05, np.float32), i)
            dst.set_band_description(i, n)
    with rasterio.open(root / "dem.tif", "w", driver="GTiff", width=120, height=120, count=1,
                       dtype="float32", crs="EPSG:7856", nodata=-9999.0,
                       transform=Grid(300000.0, 6120000.0, 5.0, 5.0, 120, 120).transform()) as dst:
        dst.write(np.full((120, 120), -6.0, np.float32), 1)
    cfg = root / "sites.yml"
    cfg.write_text(yaml.safe_dump({"sites": {"t": {"reference_dem": "dem.tif", "tide_gauge": {
        "station": "216470", "name": "Jervis Bay", "ahd_offset_m": -1.07, "msl_ahd": 0.074,
        "islw_ahd": -0.776, "hhwss_ahd": 1.028}}}}))
    csv = root / "jb.csv"
    _write_mhl_csv(csv, datum="cd")
    out = root / "outputs"

    assert waterlevel.main(["--site", "t", "--config", str(cfg), "--scene", "S", "--root", str(root),
                            "--out", str(out), "--gauge-file", str(csv)]) == 0
    rec = json.loads((out / "waterlevel_S.json").read_text())
    assert rec["status"] == "measured" and rec["datum_in_file"] == "cd"
    assert rec["water_level_m_ahd"] == pytest.approx(_tide(H_OVERPASS), abs=0.005)

    assert reference.main(["--site", "t", "--config", str(cfg), "--scene", "S", "--root", str(root),
                           "--out", str(out), "--coreg", "off"]) == 0
    ref = json.loads((out / "reference_S.json").read_text())
    assert ref["water_level_m_ahd"] == rec["water_level_m_ahd"]
    assert "measured" in ref["water_level_source"]


def test_cli_refuses_an_implausible_level(tmp_path):
    import yaml

    from sdb import waterlevel

    root = tmp_path
    sd = root / "data" / "raw" / "scenes" / "S"
    sd.mkdir(parents=True)
    (sd / "provenance.json").write_text(json.dumps({"datetime_utc": "2018-09-07T00:02:37Z"}))
    cfg = root / "sites.yml"
    cfg.write_text(yaml.safe_dump({"sites": {"t": {"reference_dem": "x", "tide_gauge": {
        "station": "1", "name": "J", "ahd_offset_m": -1.07, "msl_ahd": 0.074,
        "islw_ahd": -0.776, "hhwss_ahd": 1.028}}}}))
    csv = root / "cm.csv"
    hours, z = _write_mhl_csv(csv, datum="ahd")
    txt = csv.read_text().splitlines()
    fixed = txt[:5] + [f"{ln.split(',')[0]},{float(ln.split(',')[1]) * 100:.1f},1" for ln in txt[5:]]
    csv.write_text("\n".join(fixed) + "\n")               # centimetres, datum forced
    assert waterlevel.main(["--site", "t", "--config", str(cfg), "--scene", "S", "--root", str(root),
                            "--out", str(root / "o"), "--gauge-file", str(csv), "--datum", "ahd"]) == 2


# --- MHL's actual export layout (as received for 216470, Sep 2026) ---------------

MHL_PREAMBLE = [
    "The data supplied is licensed under a Creative Commons Attribution 4.0 licence. ",
    "To view a copy of this licence visit:", "http://creativecommons.org/licenses/by/4.0", "",
    "Licence:", "You are free:", "", "               1.to copy distribute display and perform the work",
    "", "Under the following conditions:",
    "               2. Please attribute NSW Department of Climate Change Energy the Environment "
    "and Water in any publications using this data.", "", "",
    "Station Name, Jervis Bay", "Station Number, 216470", "Longitude,150.707439",
    "Latitude,-35.121953", 'Web,"http://www.mhl.nsw.gov.au/Station-216470"', "",
]


def _write_mhl_export(path, datum_line="Datum, Australian Height Datum (1971)", offset=0.0, noise=0.01):
    """Date and Time in separate columns, 1-minute samples, CRLF endings, quality codes."""
    mins = np.arange(0, 3 * 24 * 60 + 1)
    hours = mins / 60
    rng = np.random.default_rng(0)
    z = _tide(hours) + offset + rng.normal(0, noise, mins.size)
    rows = [f"{(datetime(2018, 9, 6) + np.timedelta64(int(m), 'm').astype(object)):%d/%m/%Y,%H:%M:%S},"
            f"{v:.3f},55" for m, v in zip(mins, z)]
    lines = MHL_PREAMBLE + [datum_line, "", "Parameter, Level 1", "", "Date,Time,Value [m],Quality"] + rows
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode("ascii"))
    return hours, z


def test_reads_mhls_export_with_separate_date_and_time_columns(tmp_path):
    f = tmp_path / "JervisBay.Level1.AHD.Actual.1min.csv"
    _write_mhl_export(f)
    t, z, notes = read_gauge_csv(f)
    assert len(t) == 3 * 24 * 60 + 1
    assert str(t[0]) == "2018-09-05T14:00:00" and str(t[1]) == "2018-09-05T14:01:00"
    assert (notes["time_column"], notes["clock_column"], notes["level_column"]) == ("Date", "Time", "Value [m]")
    assert notes["datum_stated"] == "Australian Height Datum (1971)"
    assert notes["quality_codes"] == {"55": len(t)}
    at = level_at(t, z, OVERPASS)
    assert at["level"] == pytest.approx(_tide(H_OVERPASS), abs=0.02)        # 1 cm noise
    true_rate = -0.6 * 2 * np.pi / 12.42 * np.sin(2 * np.pi * (H_OVERPASS - 4.0) / 12.42)
    assert at["tidal_rate_m_per_h"] == pytest.approx(true_rate, abs=0.03)   # not the noise


def test_a_header_datum_that_contradicts_the_numbers_is_refused(tmp_path):
    from sdb.waterlevel import check_stated_datum

    check_stated_datum("Australian Height Datum (1971)", "ahd")
    check_stated_datum(None, "cd")
    with pytest.raises(ValueError, match="header states"):
        check_stated_datum("Australian Height Datum (1971)", "cd")
    f = tmp_path / "mislabelled.csv"
    _write_mhl_export(f, offset=-JB.ahd_offset_m)            # chart-datum numbers under an AHD label
    _, z, notes = read_gauge_csv(f)
    assert infer_datum(z, JB) == "cd"
    with pytest.raises(ValueError, match="header states"):
        check_stated_datum(notes["datum_stated"], infer_datum(z, JB))


def test_cli_keeps_the_superseded_image_estimate_and_refuses_a_contradicted_header(tmp_path):
    import yaml

    from sdb import waterlevel

    root = tmp_path
    sd = root / "data" / "raw" / "scenes" / "S"
    sd.mkdir(parents=True)
    (sd / "provenance.json").write_text(json.dumps({"datetime_utc": "2018-09-07T00:02:37Z"}))
    cfg = root / "sites.yml"
    cfg.write_text(yaml.safe_dump({"sites": {"t": {"reference_dem": "x", "tide_gauge": {
        "station": "216470", "name": "Jervis Bay", "ahd_offset_m": -1.07, "msl_ahd": 0.074,
        "islw_ahd": -0.776, "hhwss_ahd": 1.028}}}}))
    out = root / "o"
    out.mkdir()
    (out / "waterlevel_S.json").write_text(json.dumps(
        {"method": "image", "status": "provisional", "water_level_m_ahd": -0.496}))
    good = root / "good.csv"
    _write_mhl_export(good)
    args = ["--site", "t", "--config", str(cfg), "--scene", "S", "--root", str(root), "--out", str(out)]
    assert waterlevel.main(args + ["--gauge-file", str(good)]) == 0
    rec = json.loads((out / "waterlevel_S.json").read_text())
    assert rec["status"] == "measured" and rec["superseded"]["water_level_m_ahd"] == -0.496
    assert rec["file"]["datum_stated"].startswith("Australian Height Datum")
    bad = root / "bad.csv"
    _write_mhl_export(bad, offset=-JB.ahd_offset_m)
    assert waterlevel.main(args + ["--gauge-file", str(bad)]) == 2


def test_gauge_file_needs_gauge_constants_but_the_image_estimate_does_not(tmp_path):
    """A new site can get its provisional image estimate before MHL replies."""
    from sdb.waterlevel import main
    cfg = tmp_path / "sites.yml"
    cfg.write_text("sites:\n  newsite:\n    label: x\n", encoding="utf-8")
    rc = main(["--site", "newsite", "--config", str(cfg), "--scene", "S2X",
               "--root", str(tmp_path), "--gauge-file", str(tmp_path / "g.csv")])
    assert rc == 2
