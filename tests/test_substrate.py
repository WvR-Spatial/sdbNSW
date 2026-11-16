"""Tests for the substrate strata: fractions, the class rules, and paired block comparisons."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box

from sdb import substrate as SB
from sdb.reference import Grid
from sdb.substrate import CLASSES, classify, fractions, group_difference


def test_constants_are_the_preregistered_ones():
    """Changing any of these is a deviation from the committed addendum (PROJECT_BRIEF.md)."""
    assert (SB.MAJORITY, SB.CORE, SB.TRACE, SB.SUPERSAMPLE, SB.MIN_COMPARE_PX, SB.N_BOOT,
            SB.BLOCK_M) == (0.5, 0.9, 0.1, 5, 1000, 1000, 2000.0)
    assert CLASSES[SB.REFERENCE] == "sediment, no seagrass mapped"


# --- fractions ---------------------------------------------------------------------

G = Grid(1000.0, 2000.0, 10.0, 10.0, 6, 6)          # x 1000-1060, y 1940-2000


def _frac(geom, shift=(0.0, 0.0)):
    return fractions({"k": [geom]}, G, shift)["k"]


def test_whole_pixels_are_fully_covered():
    f = _frac(box(1010, 1970, 1030, 1990))            # columns 1-2, rows 1-2
    assert f[1:3, 1:3].tolist() == [[1, 1], [1, 1]] and f.sum() == 4


def test_a_partly_covered_pixel_reads_its_sub_cell_fraction():
    f = _frac(box(1000, 1990, 1004, 2000))            # 2 of the 5 sub-cell columns (2 m cells)
    assert f[0, 0] == pytest.approx(0.4) and f.sum() == pytest.approx(0.4)


def test_the_coregistration_shift_moves_the_footprint():
    """Pixel footprint = nominal + shift. 4 m west: pixel 0 sees x 996-1006, pixel 1 sees 1006-1016."""
    f = _frac(box(1000, 1990, 1010, 2000), shift=(-4.0, 0.0))
    assert f[0, 0] == pytest.approx(0.6) and f[0, 1] == pytest.approx(0.4)
    assert _frac(box(1000, 1990, 1010, 2000))[0, 0] == 1.0     # unshifted: exactly one pixel


# --- class rules --------------------------------------------------------------------

def _f(pos=0, pz=0, zh=0, sga=None, reef=0, unc=0):
    sga = pos + pz + zh if sga is None else sga
    return {k: np.array([v], float) for k, v in zip(SB.FRACTIONS, (pos, pz, zh, sga, reef, unc))}


@pytest.mark.parametrize("fr, expected", [
    (_f(pos=0.6, unc=1), "Posidonia"),
    (_f(pz=0.7, unc=1), "Posidonia/Zostera"),
    (_f(zh=0.5, unc=1), "Zostera/Halophila"),
    (_f(pos=0.3, zh=0.3, unc=1), "seagrass, mixed types"),
    (_f(reef=0.8, unc=0.2), "reef"),
    (_f(pos=0.6, reef=0.4), "Posidonia"),                 # seagrass takes precedence
    (_f(unc=1.0), "sediment, no seagrass mapped"),
    (_f(unc=0.95, sga=0.05, pos=0.05), "sediment, no seagrass mapped"),   # trace seagrass tolerated
    (_f(unc=0.8, pos=0.2), "edge/mixed"),                # seagrass above trace, below majority
    (_f(unc=0.6, reef=0.4), "edge/mixed"),
    (_f(unc=0.05), "not mapped"),
])
def test_class_rules_and_precedence(fr, expected):
    assert CLASSES[classify(fr)[0]] == expected


def test_the_core_rule_is_stricter():
    fr = _f(pos=0.7, unc=1)
    assert CLASSES[classify(fr, 0.5)[0]] == "Posidonia"
    assert CLASSES[classify(fr, 0.9)[0]] == "edge/mixed"


# --- paired block comparison -------------------------------------------------------------

def test_group_difference_recovers_a_planted_offset_exactly():
    blocks = np.repeat(np.arange(20), 100)
    a = np.zeros(blocks.size, bool)
    a[::2] = True                                         # both groups in every block
    err = np.where(a, 1.0, 0.0)
    d = group_difference(err, blocks, a, ~a, n_boot=200, rng=np.random.default_rng(0))
    assert d["bias_diff"] == {"point": 1.0, "lo": 1.0, "hi": 1.0}
    assert d["rmse_diff"]["point"] == pytest.approx(1.0)


def test_group_difference_point_is_the_direct_difference_and_the_interval_brackets_it():
    rng = np.random.default_rng(1)
    blocks = rng.integers(0, 40, 8_000)
    a = rng.random(8_000) < 0.3
    err = rng.normal(0, 1, 8_000) + 0.4 * a + rng.normal(0, 0.5, 40)[blocks]
    d = group_difference(err, blocks, a, ~a, n_boot=400, rng=np.random.default_rng(2))
    direct = err[a].mean() - err[~a].mean()
    assert d["bias_diff"]["point"] == pytest.approx(direct)
    assert d["bias_diff"]["lo"] < direct < d["bias_diff"]["hi"]


# --- CLI end to end ---------------------------------------------------------------------

def test_cli_end_to_end(tmp_path):
    import geopandas as gpd
    import rasterio
    import yaml

    from sdb.reference import write_layers

    n, x0, y0 = 150, 300000.0, 6120000.0
    g = Grid(x0, y0, 10.0, 10.0, n, n)
    sd = tmp_path / "data" / "raw" / "scenes" / "S"
    sd.mkdir(parents=True)
    wl = -0.5
    depth = np.full((n, n), 3.0)                          # all in the 2-5 m band
    resid = np.zeros((n, n))
    resid[20:60, 20:60] = 1.0                             # the Posidonia square reads 1 m deeper
    resid[100:140, 100:140] = -0.5                        # the reef square reads 0.5 m shallower
    write_layers(sd / "reference.tif", {"z_mean": wl - depth}, g, "EPSG:32756", ("z_mean",))
    write_layers(sd / "sdb.tif", {"oof_depth": depth + resid, "residual": resid}, g, "EPSG:32756",
                 ("oof_depth", "residual"))
    sq = lambda r0, c0, k: box(x0 + c0 * 10, y0 - (r0 + k) * 10, x0 + (c0 + k) * 10, y0 - r0 * 10)  # noqa: E731
    gpkg = tmp_path / "sub.gpkg"
    gpd.GeoDataFrame({"Habitat": ["Seagrass"], "Macrophyte": ["Posidonia"]},
                     geometry=[sq(20, 20, 40)], crs=7856).to_file(gpkg, layer="macrophytes")
    gpd.GeoDataFrame({"REEF": ["Reef", "Unconsolidated"]},
                     geometry=[sq(100, 100, 40), sq(0, 0, n)], crs=7856).to_file(gpkg, layer="reef_extent")
    out = tmp_path / "outputs"
    out.mkdir()
    (out / "reference_S.json").write_text(json.dumps(
        {"water_level_m_ahd": wl, "coregistration": {"shift_applied_m": [0.0, 0.0]}}))
    cfg = tmp_path / "sites.yml"
    cfg.write_text(yaml.safe_dump({"sites": {"t": {}}}))
    assert SB.main(["--site", "t", "--config", str(cfg), "--scene", "S", "--root", str(tmp_path),
                    "--out", str(out), "--substrate", str(gpkg), "--boot", "100"]) == 0
    rec = json.loads((out / "substrate_S.json").read_text())
    comps = {(c["band_m"], c["class"]): c for c in rec["threshold_0.5"]["vs_reference_inside_bay"]}
    assert comps[("2-5", "Posidonia")]["bias_diff"]["point"] == pytest.approx(1.0)
    assert comps[("2-5", "Posidonia")]["n_class"] == 1600
    assert comps[("2-5", "reef")]["bias_diff"]["point"] == pytest.approx(-0.5)
    assert "note" in comps[("2-5", "Zostera/Halophila")]
    assert rec["addendum_commit"] is None and len(rec["figures"]) == 1
    assert all(Path(f).exists() for f in rec["figures"])
    with rasterio.open(sd / "substrate.tif") as s:
        assert s.descriptions[0] == "class_majority"


def test_cli_refuses_without_the_substrate_file(tmp_path):
    (tmp_path / "outputs").mkdir()
    assert SB.main(["--scene", "S", "--root", str(tmp_path), "--out", str(tmp_path / "outputs"),
                    "--substrate", str(tmp_path / "nope.gpkg")]) == 2


def test_cli_tag_reads_exploratory_residuals_and_writes_apart(tmp_path):
    import geopandas as gpd
    import yaml

    from sdb.reference import write_layers

    n, x0, y0 = 60, 300000.0, 6120000.0
    g = Grid(x0, y0, 10.0, 10.0, n, n)
    sd = tmp_path / "data" / "raw" / "scenes" / "S"
    sd.mkdir(parents=True)
    depth = np.full((n, n), 3.0)
    resid = np.zeros((n, n))
    resid[:40, :40] = 0.7
    write_layers(sd / "reference.tif", {"z_mean": -0.5 - depth}, g, "EPSG:32756", ("z_mean",))
    write_layers(sd / "sdb_rule95.tif", {"oof_depth": depth + resid, "residual": resid}, g,
                 "EPSG:32756", ("oof_depth", "residual"))
    box_ = box(x0, y0 - 400, x0 + 400, y0)
    gpkg = tmp_path / "sub.gpkg"
    gpd.GeoDataFrame({"Habitat": ["Seagrass"], "Macrophyte": ["Posidonia"]},
                     geometry=[box_], crs=7856).to_file(gpkg, layer="macrophytes")
    gpd.GeoDataFrame({"REEF": ["Unconsolidated"]}, geometry=[box(x0, y0 - 600, x0 + 600, y0)],
                     crs=7856).to_file(gpkg, layer="reef_extent")
    out = tmp_path / "outputs"
    out.mkdir()
    (out / "reference_S.json").write_text(json.dumps({"water_level_m_ahd": -0.5}))
    cfg = tmp_path / "sites.yml"
    cfg.write_text(yaml.safe_dump({"sites": {"t": {}}}))
    assert SB.main(["--site", "t", "--config", str(cfg), "--scene", "S", "--root", str(tmp_path),
                    "--out", str(out), "--substrate", str(gpkg), "--boot", "50",
                    "--tag", "rule95"]) == 0
    rec = json.loads((out / "exploratory" / "substrate_S_rule95.json").read_text())
    assert rec["exploratory"]["name"] == "rule95"
    comp = {(c["band_m"], c["class"]): c for c in rec["threshold_0.5"]["vs_reference_inside_bay"]}
    assert comp[("2-5", "Posidonia")]["bias_diff"]["point"] == pytest.approx(0.7)
    assert not (sd / "substrate.tif").exists() and not (out / "substrate_S.json").exists()


def test_default_layers_are_the_sites_own(tmp_path, capsys):
    """Without --substrate a site reads substrate_<site>.gpkg, never another site's file."""
    raw = tmp_path / "data" / "raw" / "substrate"
    raw.mkdir(parents=True)
    (raw / "substrate_jervis_bay.gpkg").write_bytes(b"")      # present, but the wrong site
    (tmp_path / "outputs").mkdir()
    assert SB.main(["--site", "batemans_bay", "--scene", "S", "--root", str(tmp_path),
                    "--out", str(tmp_path / "outputs")]) == 2
    assert "substrate_batemans_bay.gpkg" in capsys.readouterr().err
