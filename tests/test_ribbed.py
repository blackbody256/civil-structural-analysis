"""Ribbed slab on Maxpan blocks, against the client's worked example (LN11 Example 3)."""
import copy

import pytest

from conftest import by_id
from ec2 import tables
from ec2.ribbed import ValidationError, check_ribbed, geometry, parse_ribbed, rib_loads

# 200 mm ribbed slab: 6" Maxpans (150 mm), 150 mm ribs, 50 mm topping, three 4.5 m spans on beams.
EX3 = {
    "slab": {"type": "ribbed", "maxpan": '6"', "bw": 150, "hf": 50},
    "materials": {"concrete": "C25/30", "fyk": 500},
    "span": {"l": 13.5, "supports": [{"x": 0, "type": "pin"}, {"x": 4.5, "type": "roller"},
                                     {"x": 9, "type": "roller"}, {"x": 13.5, "type": "roller"}]},
    "reinforcement": {"bottom_n": 2, "bottom_dia": 10, "top_n": 2, "top_dia": 10, "link_dia": "none", "cover": 25,
                      "delta_c_dev": 10, "mesh": "A98"},
    "actions": {"mode": "analysis", "gk": 1.2, "qk": 3.0, "self_weight": True, "category": "B", "loads": [],
                "pattern": True},
    "durability": {"exposure": "XC1", "cement_group": "All", "fire_period": "none"},
}


@pytest.fixture
def ex3():
    return copy.deepcopy(EX3)


def test_maxpan_table():
    assert tables.MAXPANS['6"'] == {"mass": 8.50, "length": 300, "width": 300, "height": 150}
    assert [p["mass"] for p in tables.MAXPANS.values()] == [6.80, 7.50, 8.50, 9.80, 11.0, 12.3, 16.5]


def test_loads_per_rib_match_the_example(ex3):
    inp = parse_ribbed(ex3)
    assert inp.h == 200 and inp.spacing == 450
    ld = rib_loads(inp)
    assert ld["sw_c"] == pytest.approx((0.15 * 0.15 + 0.45 * 0.05) * 25)          # 1.125 kN/m
    assert ld["sw_pan"] == pytest.approx(8.50 * 9.81e-3 / 0.3)                      # 0.278 kN/m
    assert ld["finishes"] == pytest.approx(1.2 * 0.45)                               # 0.54 kN/m
    assert ld["n_g"] == pytest.approx(1.943, abs=0.001)
    assert ld["n_q"] == pytest.approx(1.35)
    assert ld["w"] == pytest.approx(4.65, abs=0.005)


def test_effective_flange_width_matches_the_example(ex3):
    geo = geometry(parse_ribbed(ex3), critical_x=2.0)                                 # end span
    assert geo.b1 == 150 and geo.l0 == pytest.approx(0.85 * 4500)
    assert geo.beff == pytest.approx(450)


def test_example_designs_and_passes(ex3):
    r = check_ribbed(ex3)
    checks = by_id(r)
    assert r["summary"]["verdict"] == "pass"
    sag = " ".join(checks["bending_sag"]["working"])
    assert "neutral axis in the flange" in sag
    # shear at the first interior support: VRd,c = 0.597 × 150 × 170 = 15.2 kN (example 15.26 kN)
    shear = " ".join(checks["shear"]["working"])
    assert "no shear reinforcement needed" in shear
    assert r["derived"]["VEd"] == pytest.approx(0.6 * 4.65 * 4.5, rel=0.02)          # ≈ 0.6F, example 12.56 kN
    assert checks["mesh"]["status"] == "pass"                                        # A98 ≥ 0.13 % × 1000 × 50 = 65


def test_missing_top_bars_and_mesh_fail(ex3):
    ex3["reinforcement"].update(top_dia="none", mesh="none")
    checks = by_id(check_ribbed(ex3))
    assert checks["bending_hog"]["status"] == "fail"
    assert checks["mesh"]["status"] == "fail"


def test_links_designed_when_concrete_shear_is_not_enough(ex3):
    ex3["actions"]["qk"] = 10.0
    ex3["reinforcement"].update(bottom_dia=16, top_dia=16, top_n=2, link_dia=6, legs=2)
    shear = by_id(check_ribbed(ex3))["shear"]
    assert "links needed" in " ".join(shear["working"])


def test_bars_must_fit_in_the_rib(ex3):
    ex3["slab"]["bw"] = 100
    ex3["reinforcement"].update(bottom_n=3, bottom_dia=20)       # 60 mm of bars in 100 − 2 × 25 = 50 mm
    with pytest.raises(ValidationError) as err:
        check_ribbed(ex3)
    assert "reinforcement.bottom_n" in err.value.errors


def test_slab_api_routes_ribbed(ex3):
    from app import app
    c = app.test_client()
    res = c.post("/api/slab/check", json=ex3).get_json()
    assert res["derived"]["slab_type"] == "ribbed" and "strip" in res["plots"]["figures"]
    assert c.post("/api/slab/analysis", json=ex3).status_code == 200
    assert c.post("/api/slab/report.pdf", json=ex3).data.startswith(b"%PDF")
