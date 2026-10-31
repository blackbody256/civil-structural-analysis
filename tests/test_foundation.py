"""Pad foundation (guide Chapter 6), against hand calculations."""
import copy

import pytest

from conftest import by_id
from ec2.foundation import ValidationError, check_foundation, pressure

# 400 × 400 column on a 3.0 × 3.0 × 0.6 m base, Gk 1000 + Qk 500 kN, no moment, H16 @ 150 both ways
CENTRAL = {
    "column": {"cx": 400, "cy": 400},
    "base": {"L": 3.0, "B": 3.0, "h": 600, "soil_depth": 0, "gamma_soil": 18},
    "soil": {"type": "custom", "q_allow": 200},
    "actions": {"Gk": 1000, "Qk": 500, "MGk": 0, "MQk": 0, "category": "B"},
    "materials": {"concrete": "C30/37", "fyk": 500},
    "reinforcement": {"x_dia": 16, "x_s": 150, "y_dia": 16, "y_s": 150, "cover": 50, "delta_c_dev": 10,
                      "cast": "blinding"},
    "durability": {"exposure": "XC2", "cement_group": "All"},
}


@pytest.fixture
def pad():
    return copy.deepcopy(CENTRAL)


def test_pressure_distributions():
    # e ≤ L/6: trapezoidal, p = N/A·(1 ± 6e/L)
    p = pressure(1000, 100, 3.0, 2.0)          # e = 0.1 = L/30
    assert p["shape"] == "trapezoidal"
    assert p["p1"] == pytest.approx(1000 / 6 * 1.2) and p["p2"] == pytest.approx(1000 / 6 * 0.8)
    # e > L/6: triangular over 3(L/2 − e), pmax = 2N/[3B(L/2 − e)]
    p = pressure(1000, 700, 3.0, 2.0)          # e = 0.7 > 0.5
    assert p["shape"] == "triangular" and p["contact"] == pytest.approx(2.4)
    assert p["p1"] == pytest.approx(2 * 1000 / (3 * 2.0 * 0.8))
    assert pressure(1000, 1600, 3.0, 2.0)["shape"] == "overturned"


def test_central_pad_matches_hand_calculation(pad):
    r = check_foundation(pad)
    d, checks = r["derived"], by_id(r)
    assert r["summary"]["verdict"] == "pass"
    # bearing: P = 1500 + 25 × 9 × 0.6 = 1635 kN over 9 m² = 181.7 kPa
    assert d["P"] == pytest.approx(1635) and d["sls_p1"] == pytest.approx(181.67, abs=0.01)
    # bending: 2100/9 = 233.3 kPa on a 1.3 m cantilever 3 m wide: M = 233.3 × 3 × 1.3²/2 = 591.5 kNm
    assert d["uls_p1"] == pytest.approx(233.33, abs=0.01)
    assert d["Mx"] == pytest.approx(591.5, abs=0.1) and d["My"] == pytest.approx(591.5, abs=0.1)
    # d = 600 − 50 − 8 = 542; z = 0.95d; As = 591.5e6/(434.8 × 0.95 × 542) = 2642 mm²
    assert d["dx"] == 542 and d["dy"] == 526
    assert d["As_req_x"] == pytest.approx(591.5e6 / (500 / 1.15 * 0.95 * 542), rel=1e-3)
    # beam shear at d: V = 233.3 × 3 × (1.3 − 0.542) = 530.6 kN, vEd = 0.326 MPa; vRd,c = vmin = 0.391 MPa
    assert d["Vx"] == pytest.approx(530.6, abs=0.1)
    assert "0.326 ≤ 0.391" in checks["shear_x"]["result"]
    # punching at the face: (2100 − 233.3 × 0.16) / (1600 × 534) = 2.41 MPa ≤ 5.28 MPa
    assert "2.41 ≤ 5.28" in checks["punching_face"]["result"]
    assert checks["overturning"]["status"] == "na"


def test_punching_deducts_the_ground_reaction_inside_the_perimeter(pad):
    r = check_foundation(pad)
    lines = " ".join(by_id(r)["punching"]["working"])
    # at a = d = 534 mm: area inside = 0.16 + 4 × 0.4 × 0.534 + π × 0.534² = 1.910 m², ΔVEd = 233.3 × 1.910 = 445.7 kN
    assert "a = 1.00d = 534 mm" in lines and "ΔVEd = 445." in lines


def test_moment_and_overturning(pad):
    pad["actions"].update(MGk=20, MQk=60)
    r = check_foundation(pad)
    d, checks = r["derived"], by_id(r)
    # e = 80/1635 = 48.9 mm ≤ L/6: pmax = 181.67 × (1 + 6 × 48.93/3000)
    assert d["sls_p1"] == pytest.approx(181.67 * (1 + 6 * 80 / 1635 / 3), rel=1e-3)
    # EQU: 0.9 × 1135 × 1.5 = 1532 kNm against 1.1 × 20 + 1.5 × 60 = 112 kNm
    assert "112.0 ≤ 1532.2" in checks["overturning"]["result"]
    assert "β = " in " ".join(checks["punching"]["working"])


def test_overturning_fails_with_a_large_wind_moment(pad):
    pad["actions"].update(Gk=150, Qk=0, MQk=200)
    pad["base"].update(L=1.5, B=1.5, h=400)
    checks = by_id(check_foundation(pad))
    assert checks["overturning"]["status"] == "fail"


def test_cover_against_the_soil_needs_75mm(pad):
    pad["reinforcement"]["cast"] = "soil"
    cover = by_id(check_foundation(pad))["cover"]
    assert cover["status"] == "fail" and "50 < 75" in cover["result"]


def test_very_soft_clay_has_no_presumed_value(pad):
    pad["soil"] = {"type": "very_soft_clay", "q_allow": None}
    assert by_id(check_foundation(pad))["bearing"]["status"] == "fail"


def test_lift_off_gives_a_warning(pad):
    pad["actions"].update(MQk=400)                 # e = 400/1635 = 245 mm < L/6; make it larger
    pad["base"].update(L=1.4)
    pad["soil"]["q_allow"] = 2000
    bearing = by_id(check_foundation(pad))["bearing"]
    assert bearing["status"] == "warn" and "triangular" in " ".join(bearing["working"])


def test_column_must_fit_on_the_base(pad):
    pad["column"]["cx"] = 3200
    with pytest.raises(ValidationError) as err:
        check_foundation(pad)
    assert "column.cx" in err.value.errors


def test_api_check_and_pdf(pad):
    from app import app
    c = app.test_client()
    res = c.post("/api/foundation/check", json=pad).get_json()
    assert res["element"] == "foundation" and {"plan", "section", "plan_plain"} <= set(res["plots"]["figures"])
    assert c.post("/api/foundation/report.pdf", json=pad).data.startswith(b"%PDF")
    assert c.post("/api/foundation/check", json={"column": {}}).status_code == 400


def test_page_examples(pad):
    """The two examples in static/js/foundation-examples.js: all pass, and 8 fail."""
    pad["base"].update(L=3.2, soil_depth=0.5)
    pad["soil"] = {"type": "stiff_clay", "q_allow": 200}
    pad["actions"].update(MGk=20, MQk=60)
    assert check_foundation(pad)["summary"]["counts"]["fail"] == 0
    pad["column"] = {"cx": 300, "cy": 300}
    pad["base"].update(L=2.6, B=2.6, h=450)
    pad["soil"] = {"type": "firm_clay", "q_allow": 150}
    pad["actions"]["MQk"] = 150
    pad["materials"]["concrete"] = "C25/30"
    pad["reinforcement"].update(x_dia=12, x_s=200, y_dia=12, y_s=200, cast="soil")
    fails = [c["id"] for c in check_foundation(pad)["checks"] if c["status"] == "fail"]
    assert fails == ["cover", "bearing", "bending_x", "bending_y", "shear_x", "shear_y", "punching_face", "punching"]
