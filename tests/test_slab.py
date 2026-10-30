import pytest

from ec2.slab import analyse_input, check_slab


def test_one_way_simply_supported_hand_calculation():
    """Simply supported 4.0 m, h 150, C30/37, gk 1.0 + self-weight 3.75, qk 2.5,

    H10 @ 200 both ways, cover 25:
    n = 1.35·4.75 + 1.5·2.5 = 10.1625 kN/m²;
    M = n·l²/8 = 20.325 kNm/m; V = n·l/2 = 20.325 kN/m;
    d = 120 mm; check K, z and As,req against hand calculation; verdict as computed.
    """
    data = {
        "slab": {"type": "one_way", "h": 150},
        "materials": {"concrete": "C30/37", "fyk": 500, "ductility": "B", "dg": 20},
        "span": {"l": 4.0, "supports": [{"x": 0.0, "type": "pin"}, {"x": 4.0, "type": "roller"}]},
        "reinforcement": {
            "bottom_x_dia": 10, "bottom_x_s": 200,
            "bottom_y_dia": 10, "bottom_y_s": 200,
            "top_x_dia": "none", "top_x_s": 0,
            "top_y_dia": "none", "top_y_s": 0,
            "cover": 25, "delta_c_dev": 10,
        },
        "actions": {
            "mode": "analysis", "gk": 1.0, "qk": 2.5, "self_weight": True,
            "category": "B", "pattern": True,
        },
        "durability": {"exposure": "XC1", "cement_group": "All", "fire_period": "none"},
    }

    res = check_slab(data)

    # Hand calculation values:
    # d = 150 - 25 - 5 = 120 mm
    # n = 1.35 * (1.0 + 3.75) + 1.5 * 2.5 = 10.1625 kN/m²
    # M = 10.1625 * 16 / 8 = 20.325 kNm/m
    # V = 10.1625 * 4 / 2 = 20.325 kN/m
    assert res["derived"]["MEd_sag"] == pytest.approx(20.325, abs=0.01)
    assert res["derived"]["VEd"] == pytest.approx(20.325, abs=0.01)
    assert res["derived"]["MEd_hog"] == 0.0

    # Checks lookup
    checks_by_id = {c.id: c for c in res["checks"]}

    # Sagging bending check:
    # K = 20.325e6 / (1000 * 120^2 * 30) = 0.04705
    # z = min(120/2 * (1 + sqrt(1 - 3.53*0.04705)), 0.95*120) = 114.0 mm
    # As_req = 20.325e6 / ( (500/1.15) * 114.0 ) = 409.99 mm²/m
    # Provided As: H10 @ 200 = 392.7 mm²/m -> As_prov < As_req so FAIL!
    c_sag = checks_by_id["bending_bottom_x"]
    assert c_sag.status == "fail"
    assert "393 vs 410 mm²/m" in c_sag.result or "393 vs 410" in c_sag.result

    # Hogging bending check is NA because M_hog is 0:
    c_hog = checks_by_id["bending_top_x"]
    assert c_hog.status == "na"

    # Overall verdict: fails because provided steel (393 mm²/m) is slightly less than required (410 mm²/m)
    assert res["verdict"] == "fail"


def test_two_equal_spans_pattern_loading():
    """Two equal 5 m spans, case B/C:

    largest sagging moment = 1.35·n_g·0.0703·l² + 1.5·n_q·0.0957·l² (±1 %);
    largest hogging (case A) = 0.125·(1.35·n_g + 1.5·n_q)·l² (±0.5 %).
    """
    l = 5.0
    h = 200.0
    sw = 25.0 * h / 1000.0  # 5.0 kN/m²
    gk = 2.0
    qk = 3.0
    n_g = gk + sw  # 7.0 kN/m²
    n_q = qk       # 3.0 kN/m²

    data = {
        "slab": {"type": "one_way", "h": h},
        "materials": {"concrete": "C30/37", "fyk": 500, "ductility": "B", "dg": 20},
        "span": {
            "l": 10.0,
            "supports": [
                {"x": 0.0, "type": "pin"},
                {"x": 5.0, "type": "roller"},
                {"x": 10.0, "type": "roller"},
            ],
        },
        "reinforcement": {
            "bottom_x_dia": 12, "bottom_x_s": 150,
            "bottom_y_dia": 10, "bottom_y_s": 200,
            "top_x_dia": 12, "top_x_s": 150,
            "top_y_dia": "none", "top_y_s": 0,
            "cover": 25, "delta_c_dev": 10,
        },
        "actions": {
            "mode": "analysis", "gk": gk, "qk": qk, "self_weight": True,
            "category": "B", "pattern": True,
        },
        "durability": {"exposure": "XC1", "cement_group": "All", "fire_period": "none"},
    }

    res = check_slab(data)

    expected_sag = 1.35 * n_g * 0.0703 * (l**2) + 1.5 * n_q * 0.0957 * (l**2)
    expected_hog = 0.125 * (1.35 * n_g + 1.5 * n_q) * (l**2)

    actual_sag = res["derived"]["MEd_sag"]
    actual_hog = res["derived"]["MEd_hog"]

    assert actual_sag == pytest.approx(expected_sag, rel=0.01)
    assert actual_hog == pytest.approx(expected_hog, rel=0.005)


def test_hogging_without_top_bars_fails_and_simple_span_is_na():
    # Two-span slab without top bars:
    data = {
        "slab": {"type": "one_way", "h": 150},
        "materials": {"concrete": "C30/37", "fyk": 500, "ductility": "B", "dg": 20},
        "span": {
            "l": 8.0,
            "supports": [{"x": 0.0, "type": "pin"}, {"x": 4.0, "type": "roller"}, {"x": 8.0, "type": "roller"}],
        },
        "reinforcement": {
            "bottom_x_dia": 12, "bottom_x_s": 150,
            "bottom_y_dia": 10, "bottom_y_s": 200,
            "top_x_dia": "none", "top_x_s": 0,
            "top_y_dia": "none", "top_y_s": 0,
            "cover": 25, "delta_c_dev": 10,
        },
        "actions": {
            "mode": "analysis", "gk": 1.0, "qk": 2.0, "self_weight": True,
            "category": "B", "pattern": True,
        },
        "durability": {"exposure": "XC1", "cement_group": "All", "fire_period": "none"},
    }

    res = check_slab(data)
    checks_by_id = {c.id: c for c in res["checks"]}
    c_hog = checks_by_id["bending_top_x"]
    assert c_hog.status == "fail"
    assert "Add top bars over the supports." in c_hog.note


def test_vrd_c_failure_for_thin_heavily_loaded_slab():
    data = {
        "slab": {"type": "one_way", "h": 70},  # very thin
        "materials": {"concrete": "C25/30", "fyk": 500, "ductility": "B", "dg": 20},
        "span": {"l": 3.0, "supports": [{"x": 0.0, "type": "pin"}, {"x": 3.0, "type": "roller"}]},
        "reinforcement": {
            "bottom_x_dia": 10, "bottom_x_s": 150,
            "bottom_y_dia": 8, "bottom_y_s": 200,
            "top_x_dia": "none", "top_x_s": 0,
            "top_y_dia": "none", "top_y_s": 0,
            "cover": 25, "delta_c_dev": 10,
        },
        "actions": {
            "mode": "analysis", "gk": 5.0, "qk": 20.0, "self_weight": True,
            "category": "E", "pattern": False,
        },
        "durability": {"exposure": "XC1", "cement_group": "All", "fire_period": "none"},
    }

    res = check_slab(data)
    checks_by_id = {c.id: c for c in res["checks"]}
    c_shear = checks_by_id["shear"]
    assert c_shear.status == "fail"
    assert "Increase the slab thickness" in c_shear.note


def test_thick_slab_h_greater_than_200_uses_crack_table():
    data = {
        "slab": {"type": "one_way", "h": 250},  # h > 200 mm
        "materials": {"concrete": "C30/37", "fyk": 500, "ductility": "B", "dg": 20},
        "span": {"l": 4.0, "supports": [{"x": 0.0, "type": "pin"}, {"x": 4.0, "type": "roller"}]},
        "reinforcement": {
            "bottom_x_dia": 10, "bottom_x_s": 150,
            "bottom_y_dia": 10, "bottom_y_s": 200,
            "top_x_dia": "none", "top_x_s": 0,
            "top_y_dia": "none", "top_y_s": 0,
            "cover": 25, "delta_c_dev": 10,
        },
        "actions": {
            "mode": "analysis", "gk": 1.0, "qk": 2.0, "self_weight": True,
            "category": "B", "pattern": False,
        },
        "durability": {"exposure": "XC1", "cement_group": "All", "fire_period": "none"},
    }

    res = check_slab(data)
    checks_by_id = {c.id: c for c in res["checks"]}
    c_crack = checks_by_id["crack_control"]
    assert "Table 11" in c_crack.working[0]


def test_analyse_input_one_way():
    data = {
        "slab": {"type": "one_way", "h": 150},
        "span": {"l": 4.0, "supports": [{"x": 0.0, "type": "pin"}, {"x": 4.0, "type": "roller"}]},
        "actions": {"mode": "analysis", "gk": 1.0, "qk": 2.5, "self_weight": True, "category": "B"},
    }
    plots = analyse_input(data)
    assert plots["analysis"] is not None
    assert "reactions" in plots["analysis"]
    assert "envelope" in plots["analysis"]
    assert "loads" in plots
