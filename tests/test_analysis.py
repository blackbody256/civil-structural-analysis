"""Tests for the Matrix Stiffness Beam Analysis engine (ec2/analysis.py)."""
import math
import numpy as np
import pytest

from ec2.analysis import BeamAnalysis, solve_beam


def test_simply_supported_point_load():
    L = 6.0
    P = 120.0  # kN
    E = 30e6   # kPa
    I = 0.002  # m4
    res = solve_beam(
        span_m=L,
        system="simple",
        loads=[{"type": "point", "W": P, "x": 3.0}],
        E_kpa=E,
        I_m4=I,
        self_weight=0.0
    )
    # Theoretical results
    expected_R = P / 2.0  # 60 kN
    expected_M = P * L / 4.0  # 180 kNm
    expected_defl_m = P * L**3 / (48.0 * E * I)  # 0.0089999 m = 9.0 mm

    assert len(res["reactions"]) == 2
    assert math.isclose(res["reactions"][0]["Ry"], -expected_R, rel_tol=1e-3)
    assert math.isclose(res["reactions"][1]["Ry"], -expected_R, rel_tol=1e-3)
    assert math.isclose(res["abs_max_M_kNm"], expected_M, rel_tol=1e-3)
    assert math.isclose(res["abs_max_V_kN"], expected_R, rel_tol=1e-3)
    assert math.isclose(res["max_deflection_mm"], expected_defl_m * 1000.0, rel_tol=1e-3)


def test_simply_supported_udl():
    L = 8.0
    w = 25.0  # kN/m
    E = 33e6  # kPa
    I = 0.005  # m4
    res = solve_beam(
        span_m=L,
        system="simple",
        loads=[{"type": "udl", "w": w, "l1": 0.0, "l2": L}],
        E_kpa=E,
        I_m4=I,
        self_weight=0.0
    )
    expected_R = w * L / 2.0  # 100 kN
    expected_M = w * L**2 / 8.0  # 200 kNm
    expected_defl_m = 5.0 * w * L**4 / (384.0 * E * I)  # 5 * 25 * 4096 / (384 * 33e6 * 0.005)

    assert math.isclose(res["reactions"][0]["Ry"], -expected_R, rel_tol=1e-3)
    assert math.isclose(res["reactions"][1]["Ry"], -expected_R, rel_tol=1e-3)
    assert math.isclose(res["abs_max_M_kNm"], expected_M, rel_tol=1e-3)
    assert math.isclose(res["abs_max_V_kN"], expected_R, rel_tol=1e-3)
    assert math.isclose(res["max_deflection_mm"], expected_defl_m * 1000.0, rel_tol=1e-3)


def test_cantilever_point_load_and_udl():
    L = 3.5
    P = 40.0   # kN at tip
    w = 12.0   # kN/m
    E = 30e6
    I = 0.0015
    res = solve_beam(
        span_m=L,
        system="cantilever",
        loads=[
            {"type": "point", "W": P, "x": L},
            {"type": "udl", "w": w, "l1": 0.0, "l2": L}
        ],
        E_kpa=E,
        I_m4=I,
        self_weight=0.0
    )
    expected_V = P + w * L  # 40 + 42 = 82 kN
    expected_M = P * L + w * L**2 / 2.0  # 140 + 73.5 = 213.5 kNm
    expected_tip_defl_m = (P * L**3 / (3.0 * E * I)) + (w * L**4 / (8.0 * E * I))

    assert len(res["reactions"]) == 1
    fixed_r = res["reactions"][0]
    assert math.isclose(abs(fixed_r["Ry"]), expected_V, rel_tol=1e-3)
    assert math.isclose(abs(fixed_r["M"]), expected_M, rel_tol=1e-3)
    assert math.isclose(res["abs_max_M_kNm"], expected_M, rel_tol=1e-3)
    assert math.isclose(res["abs_max_V_kN"], expected_V, rel_tol=1e-3)
    assert math.isclose(res["max_deflection_mm"], expected_tip_defl_m * 1000.0, rel_tol=1e-3)


def test_client_beam_pro_example():
    """Verify exact match with client's load_example from Beam Pro.py."""
    a = BeamAnalysis()
    a.num_nodes = 3
    a.nodes = {0: 0.0, 1: 5.0, 2: 10.0}
    a.total_dofs = 6
    a.num_elements = 2
    a.elements[0] = (0, 1)
    a.elements[1] = (1, 2)
    a.E[0] = 200e6
    a.E[1] = 200e6
    a.I[0] = 0.0001
    a.I[1] = 0.0001
    a.L[0] = 5.0
    a.L[1] = 5.0
    a.supports = {0: [1, 0], 2: [1, 1]}
    a.point_loads = [{"node": 1, "Fy": -20.0, "M": 0.0}]
    a.member_udl = [{"elem": 0, "w": -10.0, "l1": 0.0, "l2": 5.0}]

    a.run_analysis()

    # Equilibrium checks
    total_reaction = abs(a.reactions[0]) + abs(a.reactions[4])
    total_applied = 20.0 + 10.0 * 5.0
    assert math.isclose(total_reaction, total_applied, rel_tol=1e-4)

    # Reaction values from Matrix stiffness
    assert math.isclose(abs(a.reactions[0]), 38.28125, rel_tol=1e-4)
    assert math.isclose(abs(a.reactions[4]), 31.71875, rel_tol=1e-4)
    assert math.isclose(abs(a.reactions[5]), 92.1875, rel_tol=1e-4)

    x, v, m, d = a.get_diagram_data(20)
    assert len(x) == len(v) == len(m) == len(d)
    assert np.max(np.abs(v)) > 38.0
    assert np.max(np.abs(m)) > 92.0


def test_partial_udl_and_moment():
    res = solve_beam(
        span_m=6.0,
        system="simple",
        loads=[
            {"type": "udl", "w": 10.0, "l1": 1.0, "l2": 4.0},
            {"type": "moment", "M0": 25.0, "x": 3.0}
        ],
        E_kpa=30e6,
        I_m4=0.002
    )
    assert res["abs_max_M_kNm"] > 0
    assert res["abs_max_V_kN"] > 0
    assert len(res["key_points"]) > 0
