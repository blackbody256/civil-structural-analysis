"""Beam check against hand calculations and the printed tables."""
import copy
import math

import pytest

from conftest import by_id
from ec2 import fire, flexure, tables
from ec2.beam import ValidationError, check_beam

# 300 × 500 simply supported over 6 m, C30/37, 4H20 bottom, 2H12 top, H8 links.
BEAM = {
    "project": {"name": "Test", "ref": "B1"},
    "section": {"shape": "rectangular", "b": 300, "h": 500},
    "materials": {"concrete": "C30/37", "fyk": 500, "ductility": "B", "dg": 20},
    "span": {"l": 6.0, "system": "simple", "location": "span"},
    "reinforcement": {"tension_n": 4, "tension_dia": 20, "layers": 1, "compression_n": 2, "compression_dia": 12,
                      "link_dia": 8, "legs": 2, "cover": 30, "delta_c_dev": 10},
    "actions": {"mode": "loads", "gk": 15, "qk": 10, "self_weight": True, "category": "B", "combination": "6.10ab"},
    "durability": {"exposure": "XC1", "cement_group": "All", "fire_period": "R60"},
}


@pytest.fixture
def beam():
    return copy.deepcopy(BEAM)


def test_hand_calculated_simply_supported_beam(beam):
    report = check_beam(beam)
    d = report["derived"]
    # gk = 15 + 25×0.3×0.5 = 18.75; 6.10b governs: w = 0.925×1.35×18.75 + 1.5×10 = 38.41 kN/m
    assert d["w"] == pytest.approx(38.414, abs=0.01)
    assert d["MEd"] == pytest.approx(38.414 * 36 / 8, abs=0.05)        # wl²/8
    assert d["VEd"] == pytest.approx(38.414 * 3, abs=0.05)             # wl/2
    # d = 500 − 30 − 8 − 10 = 452; K = M/(b d² fck)
    assert d["d"] == pytest.approx(452)
    assert d["K"] == pytest.approx(172.86e6 / (300 * 452**2 * 30), rel=1e-3)
    z = 452 / 2 * (1 + math.sqrt(1 - 3.53 * d["K"]))
    assert d["z"] == pytest.approx(z, rel=1e-6)
    assert d["As_req"] == pytest.approx(172.86e6 / (500 / 1.15 * z), rel=1e-3)
    # links: ρw,min governs (0.263 mm²/mm), 101/0.263 = 382 > 0.75d = 339 → 325 mm
    assert d["links"]["near"] == 325
    checks = by_id(report)
    assert checks["deflection"]["limit"] == pytest.approx(25.95, abs=0.1)
    assert report["summary"]["verdict"] == "pass"


def test_k_prime_matches_table4():
    for delta, kp in zip(tables.KPRIME_DELTA, tables.KPRIME):
        assert flexure.k_prime(delta, uk_limit=False) == pytest.approx(kp, abs=0.003)
    assert flexure.k_prime(1.0) == pytest.approx(0.168)


def test_strut_capacity_matches_table7():
    for fck, v25, v10 in zip(tables.STRUT_FCK, tables.STRUT_COT25, tables.STRUT_COT10):
        assert flexure.strut_capacity(fck, 2.5) == pytest.approx(v25, abs=0.01)
        assert flexure.strut_capacity(fck, 1.0) == pytest.approx(v10, abs=0.01)


def test_minimum_shear_ratio_matches_table9():
    for fck, rho in zip(tables.STRUT_FCK, tables.RHO_W_MIN):
        assert flexure.rho_w_min(fck, 500) * 1000 == pytest.approx(rho, abs=0.006)


def test_crack_limits_interpolate_table11():
    assert tables.crack_limits(200, 0.3) == (25, 250)
    assert tables.crack_limits(220, 0.3) == (20.5, 225)
    assert tables.crack_limits(100, 0.4) == (40, 300)
    assert tables.crack_limits(400, 0.3) == (None, None)


def test_beam_fire_table():
    assert fire.check_beam_fire("R60", "simple", 300, 48)[0] is True
    assert fire.check_beam_fire("R90", "simple", 200, 40)[0] is False     # needs 200/45
    assert fire.check_beam_fire("R90", "continuous", 250, 25)[0] is True


def test_flanged_neutral_axis_in_flange(beam):
    beam["section"] = {"shape": "flanged", "flange": "T", "b": 300, "h": 500, "hf": 150,
                       "beff_method": "enter", "beff": 1500}
    report = check_beam(beam)
    lines = " ".join(by_id(report)["bending_design"]["working"])
    assert "neutral axis in the flange" in lines
    assert report["derived"]["K"] == pytest.approx(report["derived"]["MEd"] * 1e6 / (1500 * 452**2 * 30), rel=1e-3)


def test_flanged_neutral_axis_in_web():
    res = flexure.flanged(800e6, beff=900, bw=250, hf=100, d=500, fck=30, fyd=500 / 1.15, kp=0.168)
    assert res["in_flange"] is False and res["ok"]
    mrf = 0.57 * 30 * (900 - 250) * 100 * (500 - 50)
    assert res["MRf"] == pytest.approx(mrf)
    assert res["Kf"] == pytest.approx((800e6 - mrf) / (30 * 250 * 500**2))


def test_effective_flange_width_calculated(beam):
    beam["section"] = {"shape": "flanged", "flange": "T", "b": 300, "h": 500, "hf": 150,
                       "beff_method": "calculate", "b1": 1350, "b2": 1350}
    # simply supported: l0 = 6000; beff,i = min(0.2×1350 + 600, 1200, 1350) = 870
    assert check_beam(beam)["derived"]["beff"] == pytest.approx(300 + 2 * 870)


def test_continuous_support_uses_coefficients_and_redistribution(beam):
    beam["span"].update(system="end", location="support")
    report = check_beam(beam)
    w = report["derived"]["w"]
    assert report["derived"]["MEd"] == pytest.approx(0.094 * w * 36, rel=1e-6)
    assert report["derived"]["VEd"] == pytest.approx(0.63 * w * 6, rel=1e-6)
    assert by_id(report)["deflection"]["status"] == "na"
    assert report["plots"]["section"]["tension_face"] == "top"


def test_compression_steel_when_k_exceeds_k_prime(beam):
    beam["actions"].update(gk=60, qk=40)
    report = check_beam(beam)
    assert report["derived"]["K"] > 0.168
    assert report["derived"]["As2_req"] > 0
    assert by_id(report)["compression"]["status"] in {"pass", "fail"}


def test_direct_actions(beam):
    beam["actions"] = {"mode": "direct", "MEd": 150, "VEd": 100}
    report = check_beam(beam)
    assert report["derived"]["MEd"] == pytest.approx(150)
    assert any("310" in w for w in by_id(report)["deflection"]["working"])


@pytest.mark.parametrize("change, field", [
    ({"span": {"l": 6, "system": "simple", "location": "support"}}, "span.location"),
    ({"span": {"l": 3, "system": "cantilever", "location": "span"}}, "span.location"),
    ({"reinforcement": {**BEAM["reinforcement"], "tension_n": 8, "tension_dia": 32}}, "reinforcement.tension_n"),
])
def test_validation(beam, change, field):
    beam.update(change)
    with pytest.raises(ValidationError) as err:
        check_beam(beam)
    assert field in err.value.errors


def test_beam_api_and_pdf(beam):
    from app import app
    client = app.test_client()
    assert client.post("/api/beam/check", json=beam).get_json()["summary"]["verdict"] == "pass"
    pdf = client.post("/api/beam/report.pdf", json=beam)
    assert pdf.mimetype == "application/pdf" and pdf.data.startswith(b"%PDF")
    assert client.post("/api/slab/check", json={}).status_code == 404
