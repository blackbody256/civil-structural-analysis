"""Matrix stiffness beam analysis against the client's example and standard beam formulas."""
import pytest

from ec2.analysis import AnalysisError, analyse

# The client's example (BeamViz Pro): fixed at 0, rollers at 10 m and 20 m, 1.5I over the first 6 m.
CLIENT_SUPPORTS = [{"x": 0, "type": "fixed"}, {"x": 10, "type": "roller"}, {"x": 20, "type": "roller"}]
CLIENT_LOADS = [{"type": "linear", "w1": 30, "w2": 0, "x1": 0, "x2": 6}, {"type": "point", "W": 200, "x": 6},
                {"type": "moment", "M": 90, "x": 10}, {"type": "point", "W": 150, "x": 15}]
CLIENT_I = [{"x1": 0, "x2": 6, "I": 0.0087}, {"x1": 6, "x2": 20, "I": 0.0058}]


@pytest.fixture(scope="module")
def client():
    return analyse(20, CLIENT_SUPPORTS, CLIENT_LOADS, E=28e6, inertia=CLIENT_I)


def event(res, name, x):
    return next(e for e in res["events"][name] if abs(e["x"] - x) < 1e-9 and not e.get("peak"))


def test_client_example_reactions(client):
    rx = {r["x"]: r for r in client["reactions"]}
    assert rx[0.0]["Ry"] == pytest.approx(146.33, abs=0.005)
    assert rx[0.0]["M"] == pytest.approx(281.19, abs=0.005)
    assert rx[10.0]["Ry"] == pytest.approx(243.46, abs=0.005)
    assert rx[20.0]["Ry"] == pytest.approx(50.21, abs=0.005)
    assert rx[10.0]["M"] is None


def test_client_example_shear_and_moment(client):
    # the values in the client's diagrams (moments to the 0.03 kNm the printed values are rounded to)
    assert event(client, "V", 0)["right"] == pytest.approx(146.33, abs=0.005)
    assert event(client, "V", 6)["left"] == pytest.approx(56.33, abs=0.005)
    assert event(client, "V", 6)["right"] == pytest.approx(-143.67, abs=0.005)
    assert event(client, "V", 10)["right"] == pytest.approx(99.79, abs=0.005)
    assert event(client, "V", 15)["right"] == pytest.approx(-50.21, abs=0.005)
    assert event(client, "M", 0)["right"] == pytest.approx(-281.19, abs=0.005)
    assert event(client, "M", 6)["left"] == pytest.approx(236.79, abs=0.03)
    assert event(client, "M", 10)["left"] == pytest.approx(-337.89, abs=0.03)
    assert event(client, "M", 10)["right"] == pytest.approx(-247.89, abs=0.03)
    assert event(client, "M", 15)["left"] == pytest.approx(251.06, abs=0.03)
    assert event(client, "M", 20)["left"] == pytest.approx(0, abs=1e-6)
    assert len(client["events"]["zeros"]) == 3


def test_client_example_statics(client):
    # the moments follow exactly from the reactions: M(6) = −281.19 + 146.33·6 − 90·(6 − 2)
    rx = client["reactions"][0]
    assert event(client, "M", 6)["left"] == pytest.approx(-rx["M"] + rx["Ry"] * 6 - 90 * 4, abs=1e-6)
    assert sum(r["Ry"] for r in client["reactions"]) == pytest.approx(90 + 200 + 150)


def test_client_example_model_numbering(client):
    """Nodes, elements and degrees of freedom numbered as in the client's analytical model."""
    assert [n["x"] for n in client["nodes"]] == [0, 6, 10, 20]
    assert [n["dofs"] for n in client["nodes"]] == [[5, 6], [1, 2], [7, 3], [8, 4]]
    assert client["free_dofs"] == 4
    assert [r["node"] for r in client["reactions"]] == [1, 3, 4]
    q = client["elements"][0]["Q"]
    assert q == pytest.approx([146.33, 281.19, -56.33, 236.77], abs=0.01)


def test_simply_supported_udl():
    res = analyse(10, [{"x": 0, "type": "pin"}, {"x": 10, "type": "roller"}],
                  [{"type": "udl", "w": 10, "x1": 0, "x2": 10}], E=30e6, inertia=0.001)
    assert [r["Ry"] for r in res["reactions"]] == pytest.approx([50, 50])
    assert res["envelope"]["sagging"]["M"] == pytest.approx(10 * 100 / 8)
    assert res["envelope"]["sagging"]["x"] == pytest.approx(5)
    assert res["envelope"]["hogging"]["M"] == pytest.approx(0, abs=1e-6)
    assert res["envelope"]["deflection"]["d"] == pytest.approx(5 * 10 * 10**4 / (384 * 30e6 * 0.001) * 1000, rel=1e-6)


def test_two_equal_spans():
    res = analyse(12, [{"x": 0, "type": "pin"}, {"x": 6, "type": "roller"}, {"x": 12, "type": "roller"}],
                  [{"type": "udl", "w": 10, "x1": 0, "x2": 12}])
    assert [r["Ry"] for r in res["reactions"]] == pytest.approx([3 * 60 / 8, 10 * 60 / 8, 3 * 60 / 8])
    assert res["envelope"]["hogging"]["M"] == pytest.approx(-10 * 36 / 8)
    assert res["envelope"]["sagging"]["M"] == pytest.approx(9 / 128 * 10 * 36, rel=1e-6)


def test_fixed_ends_and_cantilever():
    fixed = analyse(8, [{"x": 0, "type": "fixed"}, {"x": 8, "type": "fixed"}], [{"type": "udl", "w": 12, "x1": 0, "x2": 8}])
    assert fixed["envelope"]["hogging"]["M"] == pytest.approx(-12 * 64 / 12)
    assert fixed["envelope"]["sagging"]["M"] == pytest.approx(12 * 64 / 24)
    cant = analyse(3, [{"x": 0, "type": "fixed"}], [{"type": "point", "W": 20, "x": 3}])
    assert cant["envelope"]["hogging"]["M"] == pytest.approx(-60)
    assert cant["reactions"][0]["Ry"] == pytest.approx(20)
    assert cant["envelope"]["sagging"]["M"] == pytest.approx(0, abs=1e-6)


def test_clockwise_moment_sign():
    res = analyse(10, [{"x": 0, "type": "pin"}, {"x": 10, "type": "roller"}], [{"type": "moment", "M": 100, "x": 5}])
    assert [r["Ry"] for r in res["reactions"]] == pytest.approx([-10, 10])
    assert event(res, "M", 5)["left"] == pytest.approx(-50)
    assert event(res, "M", 5)["right"] == pytest.approx(50)


def test_part_and_varying_loads_balance():
    loads = [{"type": "udl", "w": 8, "x1": 2, "x2": 5}, {"type": "linear", "w1": 0, "w2": 12, "x1": 4, "x2": 9}]
    res = analyse(9, [{"x": 0, "type": "pin"}, {"x": 9, "type": "roller"}], loads)
    total = 8 * 3 + 12 * 5 / 2
    assert sum(r["Ry"] for r in res["reactions"]) == pytest.approx(total)
    # moments about the left support: 24 × 3.5 + 30 × (4 + 2/3·5) = Rb × 9
    assert res["reactions"][1]["Ry"] == pytest.approx((24 * 3.5 + 30 * (4 + 10 / 3)) / 9)


def test_unstable_beam_is_rejected():
    with pytest.raises(AnalysisError):
        analyse(10, [{"x": 5, "type": "roller"}], [{"type": "point", "W": 10, "x": 2}])
    with pytest.raises(AnalysisError):
        analyse(10, [], [])
