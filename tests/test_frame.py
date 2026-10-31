"""Tests for 2D frame stiffness analysis and column actions (ec2/frame.py)."""
import math
import pytest
from ec2.frame import solve, analyse_frame, column_actions
from ec2.inputs import ValidationError
from ec2.slenderness import PINNED


def test_fixed_fixed_beam_midspan_point_load():
    """Fixed-fixed beam 5m with 150 kN downward load at midspan."""
    nodes = [
        {"id": "A", "x": 0.0, "y": 0.0},
        {"id": "B", "x": 2.5, "y": 0.0},
        {"id": "C", "x": 5.0, "y": 0.0},
    ]
    members = [
        {"id": "E1", "node1": "A", "node2": "B", "E": 2e8, "A": 1.5e-2, "I": 1.2e-4},
        {"id": "E2", "node1": "B", "node2": "C", "E": 2e8, "A": 1.5e-2, "I": 1.2e-4},
    ]
    supports = [
        {"node": "A", "dx": True, "dy": True, "rz": True},
        {"node": "C", "dx": True, "dy": True, "rz": True},
    ]
    loads = [{"node": "B", "fx": 0.0, "fy": -150.0, "mz": 0.0}]

    res = solve(nodes, members, supports, loads)
    assert res["reactions"]["A"]["Ry"] == pytest.approx(75.0, abs=1e-2)
    assert res["reactions"]["C"]["Ry"] == pytest.approx(75.0, abs=1e-2)
    assert res["reactions"]["A"]["Mz"] == pytest.approx(93.75, abs=1e-2)
    assert res["reactions"]["C"]["Mz"] == pytest.approx(-93.75, abs=1e-2)

    m1 = res["members"][0]
    m2 = res["members"][1]
    assert m1["moment_start"] == pytest.approx(-93.75, abs=1e-2)
    assert m1["moment_end"] == pytest.approx(93.75, abs=1e-2)
    assert m2["moment_start"] == pytest.approx(93.75, abs=1e-2)
    assert m2["moment_end"] == pytest.approx(-93.75, abs=1e-2)


def test_propped_cantilever_udl():
    """Propped cantilever 6m, fixed A, roller B, UDL 20 kN/m down."""
    nodes = [
        {"id": "A", "x": 0.0, "y": 0.0},
        {"id": "B", "x": 6.0, "y": 0.0},
    ]
    members = [
        {"id": "E1", "node1": "A", "node2": "B", "E": 2e8, "A": 1.5e-2, "I": 1.2e-4},
    ]
    supports = [
        {"node": "A", "dx": True, "dy": True, "rz": True},
        {"node": "B", "dx": False, "dy": True, "rz": False},
    ]
    loads = [{"member": "E1", "load_type": "udl", "w": -20.0}]

    res = solve(nodes, members, supports, loads)
    assert res["reactions"]["A"]["Ry"] == pytest.approx(75.0, abs=1e-2)
    assert res["reactions"]["B"]["Ry"] == pytest.approx(45.0, abs=1e-2)
    assert res["reactions"]["A"]["Mz"] == pytest.approx(90.0, abs=1e-2)
    assert res["members"][0]["moment_start"] == pytest.approx(-90.0, abs=1e-2)
    assert res["members"][0]["moment_end"] == pytest.approx(0.0, abs=1e-2)


def test_portal_frame_client_example():
    """Portal frame from client tool examples with lateral loads and beam UDLs."""
    nodes = [
        {"id": "A", "x": 0.0, "y": 0.0},
        {"id": "B", "x": 0.0, "y": 4.0},
        {"id": "E", "x": 0.0, "y": 8.0},
        {"id": "D", "x": 5.0, "y": 0.0},
        {"id": "C", "x": 5.0, "y": 4.0},
        {"id": "F", "x": 5.0, "y": 8.0},
    ]
    members = [
        {"id": "Col1", "node1": "A", "node2": "B", "E": 2e8, "A": 2e-2, "I": 1.6e-4},
        {"id": "Col3", "node1": "B", "node2": "E", "E": 2e8, "A": 2e-2, "I": 1.6e-4},
        {"id": "Col2", "node1": "D", "node2": "C", "E": 2e8, "A": 2e-2, "I": 1.6e-4},
        {"id": "Col4", "node1": "C", "node2": "F", "E": 2e8, "A": 2e-2, "I": 1.6e-4},
        {"id": "Beam1", "node1": "B", "node2": "C", "E": 2e8, "A": 1.5e-2, "I": 1.2e-4},
        {"id": "Beam2", "node1": "E", "node2": "F", "E": 2e8, "A": 1.5e-2, "I": 1.2e-4},
    ]
    supports = [
        {"node": "A", "dx": True, "dy": True, "rz": True},
        {"node": "D", "dx": True, "dy": True, "rz": True},
    ]
    loads = [
        {"node": "B", "fx": 30.0, "fy": 0.0, "mz": 0.0},
        {"node": "E", "fx": 50.0, "fy": 0.0, "mz": 0.0},
        {"member": "Beam1", "load_type": "udl", "w": -15.0},
        {"member": "Beam2", "load_type": "udl", "w": -20.0},
    ]

    res = solve(nodes, members, supports, loads)
    assert res["reactions"]["A"]["Rx"] == pytest.approx(-37.267, abs=0.01)
    assert res["reactions"]["A"]["Ry"] == pytest.approx(26.037, abs=0.01)
    assert res["reactions"]["A"]["Mz"] == pytest.approx(102.712, abs=0.01)

    assert res["reactions"]["D"]["Rx"] == pytest.approx(-42.733, abs=0.01)
    assert res["reactions"]["D"]["Ry"] == pytest.approx(148.963, abs=0.01)
    assert res["reactions"]["D"]["Mz"] == pytest.approx(109.973, abs=0.01)

    m_by_id = {m["id"]: m for m in res["members"]}
    assert m_by_id["Col1"]["axial"] == pytest.approx(-26.037, abs=0.01)
    assert m_by_id["Col1"]["moment_start"] == pytest.approx(-102.712, abs=0.01)
    assert m_by_id["Col1"]["moment_end"] == pytest.approx(46.355, abs=0.01)

    assert m_by_id["Beam1"]["moment_start"] == pytest.approx(65.078, abs=0.01)
    assert m_by_id["Beam1"]["moment_end"] == pytest.approx(-123.172, abs=0.01)

    assert m_by_id["Col2"]["axial"] == pytest.approx(-148.963, abs=0.01)
    assert m_by_id["Col2"]["moment_start"] == pytest.approx(-109.973, abs=0.01)
    assert m_by_id["Col2"]["moment_end"] == pytest.approx(60.960, abs=0.01)

    assert res["determinacy"]["value"] == 6


def test_point_load_at_a_zero_defect_fix():
    """Client tool defect: ld.a || L/2 sends a=0 to midspan. Verify a=0 works correctly."""
    nodes = [
        {"id": "A", "x": 0.0, "y": 0.0},
        {"id": "B", "x": 4.0, "y": 0.0},
    ]
    members = [
        {"id": "E1", "node1": "A", "node2": "B", "E": 2e8, "A": 1.5e-2, "I": 1.2e-4},
    ]
    supports = [
        {"node": "A", "dx": True, "dy": True, "rz": False},
        {"node": "B", "dx": False, "dy": True, "rz": False},
    ]
    loads = [{"member": "E1", "load_type": "point", "P": -10.0, "a": 0.0}]

    res = solve(nodes, members, supports, loads)
    assert res["reactions"]["A"]["Ry"] == pytest.approx(10.0, abs=1e-3)
    assert res["reactions"]["B"]["Ry"] == pytest.approx(0.0, abs=1e-3)


def test_gravity_udl_on_inclined_member():
    """Gravity UDL on an inclined member: vertical reactions sum to w*L, no horizontal reaction."""
    nodes = [
        {"id": "A", "x": 0.0, "y": 0.0},
        {"id": "B", "x": 3.0, "y": 4.0},
    ]
    members = [
        {"id": "E1", "node1": "A", "node2": "B", "E": 2e8, "A": 1.5e-2, "I": 1.2e-4},
    ]
    supports = [
        {"node": "A", "dx": True, "dy": True, "rz": False},
        {"node": "B", "dx": False, "dy": True, "rz": False},
    ]
    # Length is 5m, w = 10 kN/m downward -> total gravity load = 50 kN
    loads = [{"member": "E1", "load_type": "udl_gravity", "w": 10.0}]

    res = solve(nodes, members, supports, loads)
    rA = res["reactions"]["A"]
    rB = res["reactions"]["B"]
    assert rA["Rx"] == pytest.approx(0.0, abs=1e-3)
    assert (rA["Ry"] + rB["Ry"]) == pytest.approx(50.0, abs=1e-3)


def test_unstable_frame_raises_error():
    """Unstable frame with insufficient supports raises ValueError."""
    nodes = [
        {"id": "A", "x": 0.0, "y": 0.0},
        {"id": "B", "x": 3.0, "y": 0.0},
    ]
    members = [
        {"id": "E1", "node1": "A", "node2": "B", "E": 2e8, "A": 1.5e-2, "I": 1.2e-4},
    ]
    supports = [
        {"node": "A", "dx": False, "dy": True, "rz": False},
        {"node": "B", "dx": False, "dy": True, "rz": False},
    ]
    loads = [{"node": "B", "fx": 10.0, "fy": 0.0, "mz": 0.0}]

    with pytest.raises(ValueError, match="The frame is unstable: check the supports"):
        solve(nodes, members, supports, loads)


def test_invalid_topology_errors():
    """Invalid topology inputs raise descriptive ValueErrors."""
    nodes = [{"id": "A", "x": 0.0, "y": 0.0}, {"id": "B", "x": 3.0, "y": 0.0}]
    supports = [{"node": "A", "dx": True, "dy": True, "rz": True}]

    # Zero length member
    with pytest.raises(ValueError, match="zero length"):
        solve(
            [{"id": "A", "x": 0.0, "y": 0.0}, {"id": "B", "x": 0.0, "y": 0.0}],
            [{"id": "E1", "node1": "A", "node2": "B", "E": 2e8, "A": 0.01, "I": 1e-4}],
            supports,
            [],
        )

    # Unknown node
    with pytest.raises(ValueError, match="references unknown node"):
        solve(
            nodes,
            [{"id": "E1", "node1": "A", "node2": "C", "E": 2e8, "A": 0.01, "I": 1e-4}],
            supports,
            [],
        )

    # Connect node to itself
    with pytest.raises(ValueError, match="connects node 'A' to itself"):
        solve(
            nodes,
            [{"id": "E1", "node1": "A", "node2": "A", "E": 2e8, "A": 0.01, "I": 1e-4}],
            supports,
            [],
        )


def test_analyse_frame_and_column_actions():
    """Test analyse_frame with G/Q factoring, self-weight, and column_actions extraction."""
    payload = {
        "materials": {"concrete": "C30/37"},
        "frame": {
            "nodes": [
                {"id": "N1", "x": 0.0, "y": 0.0},
                {"id": "N2", "x": 0.0, "y": 3.5},
                {"id": "N3", "x": 6.0, "y": 0.0},
                {"id": "N4", "x": 6.0, "y": 3.5},
            ],
            "members": [
                {"id": "C1", "node1": "N1", "node2": "N2", "b": 300, "h": 300},
                {"id": "C2", "node1": "N3", "node2": "N4", "b": 300, "h": 300},
                {"id": "B1", "node1": "N2", "node2": "N4", "b": 300, "h": 500},
            ],
            "supports": [
                {"node": "N1", "type": "fixed"},
                {"node": "N3", "type": "pin"},
            ],
            "loads": [
                {"type": "udl", "member": "B1", "w": 20.0, "case": "G"},
                {"type": "point", "member": "B1", "P": 40.0, "a": 3.0, "case": "Q"},
                {"type": "node", "node": "N2", "fx": 15.0, "fy": 0.0, "mz": 0.0, "case": "Q"},
            ],
            "self_weight": True,
            "E_method": "concrete",
        },
    }

    res = analyse_frame(payload)
    assert "displacements" in res
    assert "reactions" in res
    assert set(res["vertical_members"]) == {"C1", "C2"}

    # Extract actions for C1
    act_c1 = column_actions(res, "C1", payload["frame"]["members"], payload["frame"]["supports"])
    assert act_c1["member"] == "C1"
    assert act_c1["NEd"] > 0  # Compression
    assert act_c1["l"] == pytest.approx(3.5)
    assert act_c1["bottom_node"] == "N1"
    assert act_c1["top_node"] == "N2"
    assert act_c1["k_bottom"] == pytest.approx(0.1)  # Fixed support
    assert 0.1 <= act_c1["k_top"] < 10.0  # Joint N2 with framing beam B1
    assert act_c1["curvature"] in ("single", "double")

    # Extract actions for C2
    act_c2 = column_actions(res, "C2", payload["frame"]["members"], payload["frame"]["supports"])
    assert act_c2["bottom_node"] == "N3"
    assert act_c2["top_node"] == "N4"
    assert math.isinf(act_c2["k_bottom"])  # Pinned support -> inf


def test_column_actions_errors():
    """column_actions raises errors for non-vertical or tension members."""
    nodes = [
        {"id": "A", "x": 0.0, "y": 0.0},
        {"id": "B", "x": 4.0, "y": 0.0},
    ]
    members = [{"id": "B1", "node1": "A", "node2": "B", "E": 2e8, "A": 0.09, "I": 6.75e-4}]
    supports = [{"node": "A", "type": "fixed"}, {"node": "B", "type": "pin"}]
    loads = [{"member": "B1", "load_type": "udl_gravity", "w": 20.0}]

    res = solve(nodes, members, supports, loads)
    res["nodes"] = nodes

    # Non-vertical member
    with pytest.raises(ValueError, match="not vertical"):
        column_actions(res, "B1", members, supports)

    # Tension member
    col_nodes = [{"id": "C1_bot", "x": 0.0, "y": 0.0}, {"id": "C1_top", "x": 0.0, "y": 3.0}]
    col_mems = [{"id": "Col_T", "node1": "C1_bot", "node2": "C1_top", "E": 2e8, "A": 0.09, "I": 6.75e-4}]
    col_sups = [{"node": "C1_bot", "type": "fixed"}]
    col_loads = [{"node": "C1_top", "fx": 0.0, "fy": 100.0, "mz": 0.0}]  # Upward tension
    res_t = solve(col_nodes, col_mems, col_sups, col_loads)
    res_t["nodes"] = col_nodes
    with pytest.raises(ValueError, match="in tension"):
        column_actions(res_t, "Col_T", col_mems, col_sups)


def test_analyse_frame_validation_errors():
    """analyse_frame validates required inputs with Reader and raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        analyse_frame({"frame": {"nodes": []}})
    assert "frame.nodes" in exc.value.errors


def _member(res, mid):
    return next(m for m in res["members"] if m["id"] == mid)


def test_point_load_along_a_column_axial_force():
    """A downward point load at mid-height of a free-standing column: compression below it, none above."""
    nodes = [{"id": "A", "x": 0.0, "y": 0.0}, {"id": "B", "x": 0.0, "y": 4.0}]
    members = [{"id": "C", "node1": "A", "node2": "B", "E": 2e8, "A": 0.09, "I": 6.75e-4}]
    supports = [{"node": "A", "type": "fixed"}]
    loads = [{"member": "C", "load_type": "point_gravity", "P": 10.0, "a": 2.0}]

    res = solve(nodes, members, supports, loads)
    col = _member(res, "C")
    assert res["reactions"]["A"]["Ry"] == pytest.approx(10.0)
    assert col["axial_start"] == pytest.approx(-10.0)
    assert col["axial_end"] == pytest.approx(0.0, abs=1e-9)
    above = [n for x, n in zip(col["x"], col["N"]) if x > 2.0]
    assert all(n == pytest.approx(0.0, abs=1e-9) for n in above)

    res["nodes"] = nodes
    assert column_actions(res, "C", members, supports)["NEd"] == pytest.approx(10.0)


def test_point_load_on_an_inclined_member_axial_force():
    """Pin–roller member (0,0)–(4,3), 10 kN down at a = 2.5 m: N = −3 kN before the load, +3 kN after it."""
    nodes = [{"id": "A", "x": 0.0, "y": 0.0}, {"id": "B", "x": 4.0, "y": 3.0}]
    members = [{"id": "R", "node1": "A", "node2": "B", "E": 2e8, "A": 0.09, "I": 6.75e-4}]
    supports = [{"node": "A", "type": "pin"}, {"node": "B", "type": "roller"}]
    loads = [{"member": "R", "load_type": "point_gravity", "P": 10.0, "a": 2.5}]

    res = solve(nodes, members, supports, loads)
    m = _member(res, "R")
    assert res["reactions"]["A"]["Ry"] == pytest.approx(5.0)
    assert res["reactions"]["B"]["Ry"] == pytest.approx(5.0)
    assert m["axial_start"] == pytest.approx(-3.0)
    assert m["axial_end"] == pytest.approx(3.0)
    assert max(m["M"], key=abs) == pytest.approx(10.0)   # 5 kN × 2 m horizontal lever arm


def test_diagrams_close_on_the_member_end_forces():
    """The sampled N, V and M agree with the end forces, and M follows dM/dx = V, on the client's portal frame."""
    nodes = [
        {"id": "A", "x": 0.0, "y": 0.0}, {"id": "B", "x": 0.0, "y": 4.0}, {"id": "C", "x": 5.0, "y": 4.0},
        {"id": "D", "x": 5.0, "y": 0.0},
    ]
    col = {"E": 2e8, "A": 2e-2, "I": 1.6e-4}
    beam = {"E": 2e8, "A": 1.5e-2, "I": 1.2e-4}
    members = [
        {"id": "Col1", "node1": "A", "node2": "B", **col},
        {"id": "Beam1", "node1": "B", "node2": "C", **beam},
        {"id": "Col2", "node1": "D", "node2": "C", **col},
    ]
    supports = [{"node": "A", "type": "fixed"}, {"node": "D", "type": "fixed"}]
    loads = [
        {"node": "B", "fx": 30.0, "fy": 0.0, "mz": 0.0},
        {"member": "Beam1", "load_type": "udl_gravity", "w": 15.0},
        {"member": "Beam1", "load_type": "point_gravity", "P": 40.0, "a": 1.5},
        {"member": "Col1", "load_type": "point_gravity", "P": 20.0, "a": 1.0},
    ]
    res = solve(nodes, members, supports, loads)
    for m in res["members"]:
        assert m["N"][0] == pytest.approx(m["axial_start"])
        assert m["V"][0] == pytest.approx(m["shear_start"])
        assert m["V"][-1] == pytest.approx(m["shear_end"])
        assert m["M"][0] == pytest.approx(m["moment_start"])
        assert m["M"][-1] == pytest.approx(m["moment_end"], abs=1e-6)
        # trapezoidal ∫V dx between samples reproduces the change in M
        xs, vs, ms = m["x"], m["V"], m["M"]
        integral = sum((xs[i + 1] - xs[i]) * (vs[i] + vs[i + 1]) / 2 for i in range(len(xs) - 1))
        assert ms[-1] - ms[0] == pytest.approx(integral, abs=0.02 * max(abs(v) for v in ms))
    col1 = _member(res, "Col1")
    # Col1 carries the column point load in compression below it only: the jump in N is the 20 kN load
    jump = [col1["N"][i + 1] - col1["N"][i] for i in range(len(col1["x"]) - 1)]
    assert max(jump) == pytest.approx(20.0)
