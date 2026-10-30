import math
import numpy as np
import pytest

from ec2 import fire, flexure, tables


def test_two_way_coefficients_direct_pdf_values():
    # 1. Interior panel at ly/lx = 1.0 (PDF Table 8)
    int_10 = tables.two_way_coefficients("interior", 1.0)
    assert int_10["bsx_sup"] == pytest.approx(0.031)
    assert int_10["bsx_mid"] == pytest.approx(0.024)
    assert int_10["bsy_sup"] == pytest.approx(0.032)
    assert int_10["bsy_mid"] == pytest.approx(0.024)

    # 2. One short edge discontinuous at ly/lx = 1.0 (PDF Table 8)
    short_10 = tables.two_way_coefficients("one_short_discontinuous", 1.0)
    assert short_10["bsx_sup"] == pytest.approx(0.039)
    assert short_10["bsx_mid"] == pytest.approx(0.029)
    assert short_10["bsy_sup"] == pytest.approx(0.037)
    assert short_10["bsy_mid"] == pytest.approx(0.028)

    # 3. One long edge discontinuous at ly/lx = 1.5 (PDF Table 8)
    long_15 = tables.two_way_coefficients("one_long_discontinuous", 1.5)
    assert long_15["bsx_sup"] == pytest.approx(0.073)
    assert long_15["bsx_mid"] == pytest.approx(0.055)
    assert long_15["bsy_sup"] == pytest.approx(0.037)
    assert long_15["bsy_mid"] == pytest.approx(0.028)


def test_two_way_coefficients_interpolation_at_125():
    # Interpolation at ly/lx = 1.25 is the exact mean of the 1.2 and 1.3 values
    int_12 = tables.two_way_coefficients("interior", 1.2)
    int_13 = tables.two_way_coefficients("interior", 1.3)
    int_125 = tables.two_way_coefficients("interior", 1.25)

    expected_sup = (int_12["bsx_sup"] + int_13["bsx_sup"]) / 2.0
    expected_mid = (int_12["bsx_mid"] + int_13["bsx_mid"]) / 2.0

    assert int_125["bsx_sup"] == pytest.approx(expected_sup)
    assert int_125["bsx_mid"] == pytest.approx(expected_mid)
    # Also verify that it matches the 0.044 printed in the PDF Table 8!
    assert int_125["bsx_sup"] == pytest.approx(0.044)


def test_two_way_coefficients_arrays_and_monotonicity():
    assert len(tables.SLAB_CASES) == 9
    assert len(tables.SLAB_LY_LX) == 8

    for case in tables.SLAB_CASES:
        mid = case["bsx_mid"]
        assert len(mid) == 8
        # Mid-span coefficients must strictly increase with ly/lx
        assert np.all(np.diff(mid) > 0), f"Case {case['id']} bsx_mid is not strictly increasing"

        sup = case["bsx_sup"]
        if sup is not None:
            assert len(sup) == 8
            assert np.all(np.diff(sup) > 0), f"Case {case['id']} bsx_sup is not strictly increasing"


def test_two_way_coefficients_out_of_range():
    with pytest.raises(ValueError, match="ly/lx = 2.1"):
        tables.two_way_coefficients("interior", 2.1)
    with pytest.raises(ValueError, match="ly/lx = 0.9"):
        tables.two_way_coefficients("interior", 0.9)


def test_vrd_c_against_table7():
    # Table 7 in the guide is prepared for fck = 30 MPa.
    # Test 4 values across different d and rho_l:
    # 1. d = 200, rho_l = 0.50% (0.005) -> 0.59 MPa
    assert flexure.vrd_c(30.0, 200.0, 0.005) == pytest.approx(0.59, abs=0.01)

    # 2. d = 250, rho_l = 1.00% (0.010) -> 0.71 MPa
    assert flexure.vrd_c(30.0, 250.0, 0.010) == pytest.approx(0.71, abs=0.01)

    # 3. d = 300, rho_l = 0.25% (0.0025) -> 0.47 MPa
    assert flexure.vrd_c(30.0, 300.0, 0.0025) == pytest.approx(0.47, abs=0.01)

    # 4. d = 500, rho_l = 1.50% (0.015) -> 0.70 MPa
    assert flexure.vrd_c(30.0, 500.0, 0.015) == pytest.approx(0.70, abs=0.01)


def test_slab_fire_r60_and_r90():
    # R60 one-way: hs=80, a=20
    ok, req, lines = fire.check_slab_fire("R60", "one_way", h=80, a=20)
    assert ok is True
    assert req == {"hs": 80, "a": 20}

    ok, req, lines = fire.check_slab_fire("R60", "one_way", h=75, a=20)
    assert ok is False

    # R60 two-way ly/lx <= 1.5: hs=80, a=10
    ok, req, lines = fire.check_slab_fire("R60", "two_way", h=80, a=10, ly_lx=1.2)
    assert ok is True
    assert req == {"hs": 80, "a": 10}

    # R60 two-way 1.5 < ly/lx <= 2.0: hs=80, a=15
    ok, req, lines = fire.check_slab_fire("R60", "two_way", h=80, a=12, ly_lx=1.8)
    assert ok is False
    assert req == {"hs": 80, "a": 15}

    # R90 one-way: hs=100, a=30
    ok, req, lines = fire.check_slab_fire("R90", "one_way", h=100, a=30)
    assert ok is True
    assert req == {"hs": 100, "a": 30}

    # R90 two-way ly/lx <= 1.5: hs=100, a=15
    ok, req, lines = fire.check_slab_fire("R90", "two_way", h=100, a=15, ly_lx=1.4)
    assert ok is True
    assert req == {"hs": 100, "a": 15}

    # R90 two-way 1.5 < ly/lx <= 2.0: hs=100, a=20
    ok, req, lines = fire.check_slab_fire("R90", "two_way", h=100, a=20, ly_lx=1.7)
    assert ok is True
    assert req == {"hs": 100, "a": 20}
