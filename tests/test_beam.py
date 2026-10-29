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
    # gk = 15 + 25×0.3×0.5 = 18.75; G = 1.35×gk, Q = 1.5×10: w = 1.35×18.75 + 1.5×10 = 40.3125 kN/m
    assert d["w"] == pytest.approx(40.3125, abs=0.01)
    assert d["MEd"] == pytest.approx(40.3125 * 36 / 8, abs=0.05)       # wl²/8 = 181.41
    assert d["VEd"] == pytest.approx(40.3125 * 3, abs=0.05)            # wl/2 = 120.94
    # d = 500 − 30 − 8 − 10 = 452; K = M/(b d² fck)
    assert d["d"] == pytest.approx(452)
    assert d["K"] == pytest.approx(181.40625e6 / (300 * 452**2 * 30), rel=1e-3)
    z = 452 / 2 * (1 + math.sqrt(1 - 3.53 * d["K"]))
    assert d["z"] == pytest.approx(z, rel=1e-6)
    assert d["As_req"] == pytest.approx(181.40625e6 / (500 / 1.15 * z), rel=1e-3)
    # links: ρw,min governs (0.263 mm²/mm), 101/0.263 = 382 > 0.75d = 339 → 325 mm
    assert d["links"]["near"] == 325
    checks = by_id(report)
    assert checks["deflection"]["limit"] == pytest.approx(25.46, abs=0.1)
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


def test_form_examples():
    """The flanged and failing examples offered on the beam page."""
    flanged = copy.deepcopy(BEAM)
    flanged["section"] = {"shape": "flanged", "flange": "T", "b": 300, "h": 550, "hf": 150,
                          "beff_method": "calculate", "b1": 1350, "b2": 1350}
    flanged["span"] = {"l": 7.0, "system": "end", "location": "span"}
    flanged["reinforcement"].update(tension_dia=25, compression_dia=16)
    flanged["actions"].update(gk=25, qk=15)
    report = check_beam(flanged)
    assert report["derived"]["beff"] == pytest.approx(2030)
    assert report["summary"]["counts"]["pass"] == 15 and report["summary"]["verdict"] == "pass"

    cantilever = copy.deepcopy(BEAM)
    cantilever["section"] = {"shape": "rectangular", "b": 250, "h": 450}
    cantilever["materials"]["concrete"] = "C25/30"
    cantilever["span"] = {"l": 3.0, "system": "cantilever", "location": "support"}
    cantilever["reinforcement"].update(tension_n=3, link_dia=6, cover=25)
    cantilever["actions"].update(gk=20, qk=15, category="C")
    cantilever["durability"] = {"exposure": "XC3/4-XF1", "cement_group": "All except IVB", "fire_period": "R90"}
    failed = {c["id"] for c in check_beam(cantilever)["checks"] if c["status"] == "fail"}
    assert failed == {"cover_durability", "fire", "tension", "compression", "deflection", "cracking"}


def test_beam_analysis_mode(beam):
    """Beam check with Matrix Stiffness Analysis mode."""
    beam_analysis = copy.deepcopy(beam)
    beam_analysis["actions"] = {
        "mode": "analysis",
        "self_weight": True,
        "partitions": False,
        "kprime_limit": True,
        "loads": [
            {"type": "point", "W": 50.0, "x": 3.0},
            {"type": "udl", "w": 12.0, "l1": 0.0, "l2": 6.0}
        ]
    }
    report = check_beam(beam_analysis)
    assert report["summary"]["verdict"] == "pass"
    assert report["derived"]["mode"] == "analysis"
    assert len(report["derived"]["reactions"]) == 2
    assert report["derived"]["max_deflection_mm"] > 0
    assert len(report["plots"]["elevation"]["delta"]) > 0

    # Check API and PDF export with analysis mode
    from app import app
    client = app.test_client()
    res = client.post("/api/beam/check", json=beam_analysis)
    assert res.status_code == 200
    pdf = client.post("/api/beam/report.pdf", json=beam_analysis)
    assert pdf.status_code == 200
    assert pdf.mimetype == "application/pdf"
    assert pdf.data.startswith(b"%PDF")


def test_slab_to_beam_loading(beam):
    """Test one-way and two-way slab equivalent UDL calculations."""
    # 1. One-way slab
    b_oneway = copy.deepcopy(beam)
    b_oneway["actions"]["has_slab"] = True
    b_oneway["actions"]["slab_type"] = "one_way"
    b_oneway["actions"]["slab_gk"] = 4.0
    b_oneway["actions"]["slab_qk"] = 3.0
    b_oneway["actions"]["slab_trib"] = 2.5
    b_oneway["actions"]["self_weight"] = False
    b_oneway["actions"]["gk"] = 0.0
    b_oneway["actions"]["qk"] = 0.0

    rep1 = check_beam(b_oneway)
    w_slab1 = 1.35 * 4.0 + 1.5 * 3.0  # 5.4 + 4.5 = 9.9 kN/m²
    expected_w1 = w_slab1 * 2.5       # 24.75 kN/m
    assert rep1["derived"]["w"] == pytest.approx(expected_w1, rel=1e-3)
    assert rep1["derived"]["MEd"] == pytest.approx(expected_w1 * 36 / 8, rel=1e-3)

    # 2. Two-way slab onto long beam Ly
    b_twoway = copy.deepcopy(beam)
    b_twoway["actions"]["has_slab"] = True
    b_twoway["actions"]["slab_type"] = "two_way_long"
    b_twoway["actions"]["slab_gk"] = 5.0
    b_twoway["actions"]["slab_qk"] = 3.0
    b_twoway["actions"]["slab_lx"] = 4.0
    b_twoway["actions"]["slab_ly"] = 6.0
    b_twoway["actions"]["self_weight"] = False
    b_twoway["actions"]["gk"] = 0.0
    b_twoway["actions"]["qk"] = 0.0

    rep2 = check_beam(b_twoway)
    w_slab2 = 1.35 * 5.0 + 1.5 * 3.0  # 6.75 + 4.5 = 11.25 kN/m²
    r = 4.0 / 6.0
    expected_weq_m = w_slab2 * (4.0 / 6.0) * (3.0 - r**2)   # 11.25 * (2/3) * (3 - 4/9) = 19.1667 kN/m
    expected_weq_v = w_slab2 * (4.0 / 4.0) * (2.0 - r)      # 11.25 * 1 * (4/3) = 15.0 kN/m
    assert rep2["derived"]["w"] == pytest.approx(expected_weq_m, rel=1e-3)
    assert rep2["derived"]["MEd"] == pytest.approx(expected_weq_m * 36 / 8, rel=1e-3)
    assert rep2["derived"]["VEd"] == pytest.approx(expected_weq_v * 6.0 / 2, rel=1e-3)


def test_textbook_beam_in_check_pipeline(beam):
    """Test textbook 20 m beam runs through check_beam pipeline with non-zero actions."""
    textbook_beam = copy.deepcopy(beam)
    textbook_beam["span"]["l"] = 20.0
    textbook_beam["span"]["system"] = "end"
    textbook_beam["span"]["location"] = "span"
    textbook_beam["section"]["b"] = 400
    textbook_beam["section"]["h"] = 750
    textbook_beam["reinforcement"]["tension_n"] = 5
    textbook_beam["reinforcement"]["tension_dia"] = 25
    textbook_beam["reinforcement"]["compression_n"] = 2
    textbook_beam["reinforcement"]["compression_dia"] = 16
    textbook_beam["reinforcement"]["link_dia"] = 10
    textbook_beam["actions"] = {
        "mode": "analysis",
        "self_weight": False,
        "loads": [
            {"type": "linear", "w1": 30.0, "w2": 0.0, "l1": 0.0, "l2": 6.0},
            {"type": "point", "W": 200.0, "x": 6.0},
            {"type": "moment", "M0": 90.0, "x": 10.0},
            {"type": "point", "W": 150.0, "x": 15.0}
        ]
    }
    report = check_beam(textbook_beam)
    # Ensure critical MEd and VEd are non-zero and used for section checks
    assert report["derived"]["MEd"] > 0
    assert report["derived"]["VEd"] > 0
    assert report["derived"]["analysis_res"]["abs_max_M_kNm"] > 250.0
    assert report["derived"]["analysis_res"]["abs_max_V_kN"] > 140.0

