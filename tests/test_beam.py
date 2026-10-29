"""Beam check: loads → matrix stiffness analysis → design of every critical moment and shear."""
import copy
import math

import pytest

from conftest import by_id
from ec2 import fire, flexure, tables
from ec2.beam import ValidationError, analyse_input, check_beam, spans_of

# 300 × 500 simply supported over 6 m, C30/37, 4H20 bottom, 2H12 top, H8 links.
BEAM = {
    "project": {"name": "Test", "ref": "B1"},
    "section": {"shape": "rectangular", "b": 300, "h": 500},
    "materials": {"concrete": "C30/37", "fyk": 500, "ductility": "B", "dg": 20},
    "span": {"l": 6.0, "supports": [{"x": 0, "type": "pin"}, {"x": 6, "type": "roller"}]},
    "reinforcement": {"bottom_n": 4, "bottom_dia": 20, "top_n": 2, "top_dia": 12, "link_dia": 8, "legs": 2,
                      "cover": 30, "delta_c_dev": 10},
    "actions": {"mode": "analysis", "gk": 15, "qk": 10, "self_weight": True, "category": "B"},
    "durability": {"exposure": "XC1", "cement_group": "All", "fire_period": "R60"},
}

# The client's example with a section to design.
CLIENT = {
    **copy.deepcopy(BEAM),
    "section": {"shape": "rectangular", "b": 400, "h": 750},
    "span": {"l": 20, "supports": [{"x": 0, "type": "fixed"}, {"x": 10, "type": "roller"}, {"x": 20, "type": "roller"}]},
    "reinforcement": {"bottom_n": 4, "bottom_dia": 20, "top_n": 4, "top_dia": 25, "link_dia": 10, "legs": 2, "cover": 35},
    "actions": {"mode": "analysis", "gk": 0, "qk": 0, "self_weight": False, "category": "B",
                "loads": [{"type": "linear", "case": "Ed", "w1": 30, "w2": 0, "x1": 0, "x2": 6},
                          {"type": "point", "case": "Ed", "W": 200, "x": 6},
                          {"type": "moment", "case": "Ed", "M": 90, "x": 10},
                          {"type": "point", "case": "Ed", "W": 150, "x": 15}]},
    "stiffness": {"E_method": "enter", "E": 28, "I_method": "enter",
                  "segments": [{"x1": 0, "x2": 6, "I": 8700}, {"x1": 6, "x2": 20, "I": 5800}]},
}


@pytest.fixture
def beam():
    return copy.deepcopy(BEAM)


def test_hand_calculated_simply_supported_beam(beam):
    report = check_beam(beam)
    d = report["derived"]
    # gk = 15 + 25×0.3×0.5 = 18.75; G = 1.35gk, Q = 1.5qk: w = 25.31 + 15 = 40.31 kN/m
    assert d["w"] == pytest.approx(1.35 * 18.75 + 1.5 * 10)
    assert d["MEd_sag"] == pytest.approx(d["w"] * 36 / 8, rel=1e-6)          # wl²/8 from the analysis
    assert d["VEd"] == pytest.approx(d["w"] * 3, rel=1e-6)                   # wl/2
    assert d["x_sag"] == pytest.approx(3)
    assert d["MEd_hog"] == 0
    assert d["bottom"]["d"] == pytest.approx(452)                            # 500 − 30 − 8 − 10
    s = d["sag"]
    assert s["K"] == pytest.approx(d["MEd_sag"] * 1e6 / (300 * 452**2 * 30), rel=1e-6)
    z = 452 / 2 * (1 + math.sqrt(1 - 3.53 * s["K"]))
    assert s["z"] == pytest.approx(z, rel=1e-6)
    assert s["As_req"] == pytest.approx(d["MEd_sag"] * 1e6 / (500 / 1.15 * z), rel=1e-6)
    assert d["links"]["near"] == 325                                         # ρw,min and 0.75d govern
    assert report["summary"]["verdict"] == "pass"


def test_zero_moment_is_not_designed_for(beam):
    """A simply supported beam has no hogging moment, so the top bars are not designed for one."""
    checks = by_id(check_beam(beam))
    assert checks["bending_hog"]["status"] == "na"
    assert "tension_hog" not in checks and "cracking_top" not in checks and "as_min_top" not in checks
    assert checks["tension_sag"]["status"] == "pass"


def test_client_example_designs_sagging_hogging_and_shear():
    report = check_beam(CLIENT)
    d = report["derived"]
    assert d["MEd_sag"] == pytest.approx(251.04, abs=0.01) and d["x_sag"] == pytest.approx(15)
    assert d["MEd_hog"] == pytest.approx(337.92, abs=0.01) and d["x_hog"] == pytest.approx(10)
    assert d["VEd"] == pytest.approx(146.33, abs=0.01) and d["x_v"] == pytest.approx(0)
    checks = by_id(report)
    for cid in ("tension_sag", "tension_hog", "strut", "deflection", "cracking_bottom", "cracking_top"):
        assert checks[cid]["status"] == "pass", cid
    # deflection is checked for both 10 m spans: the first restrained at both ends, the second an end span
    lines = " ".join(checks["deflection"]["working"])
    assert "Span 1 (0–10 m, interior span)" in lines and "Span 2 (10–20 m, end span)" in lines
    rx = {r["x"]: r for r in report["plots"]["analysis"]["reactions"]}
    assert rx[0.0]["M"] == pytest.approx(281.19, abs=0.01)
    assert report["summary"]["verdict"] == "pass"


def test_design_loads_without_the_0925_factor(beam):
    beam["actions"]["self_weight"] = False
    assert check_beam(beam)["derived"]["w"] == pytest.approx(1.35 * 15 + 1.5 * 10)


def test_load_cases_are_factored(beam):
    beam["actions"].update(gk=0, qk=0, self_weight=False)
    for case, factor in (("Ed", 1.0), ("G", 1.35), ("Q", 1.5)):
        beam["actions"]["loads"] = [{"type": "point", "case": case, "W": 100, "x": 3}]
        assert check_beam(beam)["derived"]["MEd_sag"] == pytest.approx(factor * 100 * 6 / 4)


def test_one_way_slab_uses_the_tributary_width(beam):
    beam["actions"].update(gk=0, qk=0, self_weight=False,
                           slab={"on": True, "type": "one_way", "gk": 5, "qk": 3, "trib": 2.5})
    w = (1.35 * 5 + 1.5 * 3) * 2.5
    d = check_beam(beam)["derived"]
    assert d["w"] == pytest.approx(w) and d["w_shear"] == pytest.approx(w)
    assert d["MEd_sag"] == pytest.approx(w * 36 / 8, rel=1e-6)


def test_two_way_slab_equivalent_loads(beam):
    """The client's formulas: moment and shear equivalents of the trapezoidal load on the long beam."""
    beam["actions"].update(gk=0, qk=0, self_weight=False,
                           slab={"on": True, "type": "two_way_long", "gk": 5, "qk": 2.5, "lx": 4, "ly": 6, "sides": 1})
    w_slab = 1.35 * 5 + 1.5 * 2.5
    w_m = w_slab * 4 / 6 * (3 - (4 / 6) ** 2)
    w_v = w_slab * 4 / 4 * (2 - 4 / 6)
    d = check_beam(beam)["derived"]
    assert d["w"] == pytest.approx(w_m) and d["w_shear"] == pytest.approx(w_v)
    assert d["MEd_sag"] == pytest.approx(w_m * 36 / 8, rel=1e-6)
    assert d["VEd"] == pytest.approx(w_v * 3, rel=1e-6)
    beam["actions"]["slab"].update(type="two_way_short", sides=2)
    d = check_beam(beam)["derived"]
    assert d["w"] == pytest.approx(2 * w_slab * 4 / 3) and d["w_shear"] == pytest.approx(2 * w_slab * 4 / 4)


def test_continuous_beam_designs_the_support(beam):
    beam["span"] = {"l": 12, "supports": [{"x": 0, "type": "pin"}, {"x": 6, "type": "roller"}, {"x": 12, "type": "roller"}]}
    beam["reinforcement"].update(top_n=3, top_dia=20)
    report = check_beam(beam)
    d = report["derived"]
    assert d["MEd_hog"] == pytest.approx(d["w"] * 36 / 8, rel=1e-6)     # wl²/8 over the middle support
    assert d["x_hog"] == pytest.approx(6)
    assert d["VEd"] == pytest.approx(0.625 * d["w"] * 6, rel=1e-6)
    checks = by_id(report)
    assert checks["tension_hog"]["status"] in {"pass", "fail"} and "top" in checks["tension_hog"]["title"]
    assert [s.kind for s in spans_of(12, beam["span"]["supports"])] == ["end", "end"]


def test_cantilever_uses_the_top_bars(beam):
    beam["span"] = {"l": 3, "supports": [{"x": 0, "type": "fixed"}]}
    beam["reinforcement"].update(top_n=3, top_dia=20)
    report = check_beam(beam)
    d = report["derived"]
    assert d["MEd_sag"] == 0 and d["MEd_hog"] == pytest.approx(d["w"] * 9 / 2, rel=1e-6)
    lines = " ".join(by_id(report)["deflection"]["working"])
    assert "cantilever" in lines and "top bars" in lines


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
    lines = " ".join(by_id(report)["bending_sag"]["working"])
    assert "neutral axis in the flange" in lines
    assert report["derived"]["sag"]["K"] == pytest.approx(report["derived"]["MEd_sag"] * 1e6 / (1500 * 452**2 * 30), rel=1e-6)


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


def test_compression_steel_when_k_exceeds_k_prime(beam):
    beam["actions"].update(gk=60, qk=40)
    report = check_beam(beam)
    assert report["derived"]["sag"]["K"] > 0.168
    assert report["derived"]["sag"]["As2_req"] > 0
    assert by_id(report)["compression_sag"]["status"] in {"pass", "fail"}


def test_direct_actions(beam):
    beam["actions"] = {"mode": "direct", "M_sag": 150, "M_hog": 0, "VEd": 100}
    report = check_beam(beam)
    assert report["derived"]["MEd_sag"] == pytest.approx(150)
    assert by_id(report)["bending_hog"]["status"] == "na"
    assert any("310" in w for w in by_id(report)["deflection"]["working"])
    assert report["plots"]["analysis"] is None


def test_old_inputs_are_read(beam):
    """Inputs saved before the analysis (one section per run) still load."""
    old = copy.deepcopy(beam)
    old["span"] = {"l": 6, "system": "simple", "location": "span"}
    old["reinforcement"] = {"tension_n": 4, "tension_dia": 20, "compression_n": 2, "compression_dia": 12,
                            "link_dia": 8, "legs": 2, "cover": 30}
    old["actions"]["mode"] = "loads"
    assert check_beam(old)["derived"]["MEd_sag"] == pytest.approx(check_beam(beam)["derived"]["MEd_sag"])


@pytest.mark.parametrize("change, field", [
    ({"span": {"l": 6, "supports": [{"x": 3, "type": "roller"}]}}, "span.supports"),
    ({"span": {"l": 6, "supports": [{"x": 8, "type": "pin"}, {"x": 0, "type": "pin"}]}}, "span.supports.0.x"),
    ({"span": {"l": 6, "supports": []}}, "span.supports"),
    ({"reinforcement": {**BEAM["reinforcement"], "bottom_n": 8, "bottom_dia": 32}}, "reinforcement.bottom_n"),
])
def test_validation(beam, change, field):
    beam.update(change)
    with pytest.raises(ValidationError) as err:
        check_beam(beam)
    assert field in err.value.errors


def test_load_validation(beam):
    beam["actions"]["loads"] = [{"type": "udl", "case": "G", "w": 5, "x1": 4, "x2": 2},
                                {"type": "point", "case": "Ed", "W": 10, "x": 9}]
    with pytest.raises(ValidationError) as err:
        check_beam(beam)
    assert {"actions.loads.0.x2", "actions.loads.1.x"} <= set(err.value.errors)


def test_stiffness_segments_must_cover_the_beam():
    bad = copy.deepcopy(CLIENT)
    bad["stiffness"]["segments"] = [{"x1": 0, "x2": 6, "I": 8700}]
    with pytest.raises(ValidationError) as err:
        check_beam(bad)
    assert "stiffness.segments" in err.value.errors


def test_live_analysis_for_the_form():
    plots = analyse_input(CLIENT)
    assert plots["analysis"]["envelope"]["hogging"]["M"] == pytest.approx(-337.92, abs=0.01)
    assert plots["loads"]["w"] == 0


def test_beam_api_and_pdf(beam):
    from app import app
    client = app.test_client()
    res = client.post("/api/beam/check", json=CLIENT).get_json()
    assert res["summary"]["verdict"] == "pass"
    assert set(res["plots"]["figures"]) == {"loading", "model", "reactions", "diagrams", "deflection"}
    pdf = client.post("/api/beam/report.pdf", json=CLIENT)
    assert pdf.mimetype == "application/pdf" and pdf.data.startswith(b"%PDF")
    live = client.post("/api/beam/analysis", json=CLIENT).get_json()
    assert "diagrams" in live["figures"]
    bad = client.post("/api/beam/analysis", json={**beam, "span": {"l": 6, "supports": [{"x": 3, "type": "roller"}]}})
    assert bad.status_code == 400 and "span.supports" in bad.get_json()["errors"]
    assert client.post("/api/slab/check", json={}).status_code == 404
