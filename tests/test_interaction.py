"""Section resistance against analytic values and the guide's column charts (Ch 5, Fig 9)."""
import pytest

from ec2.interaction import SectionModel

FYK = 500.0
FYD = FYK / 1.15
FCD_RATIO = 0.85 / 1.5


def chart_model(d2h, omega_k):
    """Unit section (b = h = 1, fck = 1) with As/2 at each face, as assumed by Fig 9."""
    area = omega_k / FYK  # As·fyk/(b·h·fck) = omega_k
    return SectionModel(1.0, 1.0, [(d2h, area / 2), (1 - d2h, area / 2)], FCD_RATIO, FYD, 200_000.0)


def test_pure_compression_uses_strain_00175():
    model = SectionModel(300, 300, [(46, 804.0), (254, 804.0)], 17.0, FYD, 200_000.0)
    assert model.n_max() == pytest.approx(17.0 * 90000 + 350.0 * 1608.0)


def test_balance_point_is_analytic():
    # d2/h = 0.15: at balance both layers yield, x = 0.0035·d/(0.0035 + εyd)
    model = chart_model(0.15, 1.0)
    x = 0.0035 * 0.85 / (0.0035 + FYD / 200_000.0)
    n_bal, m_bal = model.forces(x)
    concrete = FCD_RATIO * 0.8 * x
    assert n_bal == pytest.approx(concrete, rel=1e-9)
    assert m_bal == pytest.approx(concrete * (0.5 - 0.4 * x) + (FYD / FYK) * 0.35, rel=1e-9)
    assert (n_bal, m_bal) == (pytest.approx(0.238, abs=0.001), pytest.approx(0.373, abs=0.001))


@pytest.mark.parametrize("d2h, omega_k, n, m_chart", [
    (0.05, 1.0, 0.0, 0.39),   # Fig 9a
    (0.10, 1.0, 0.0, 0.35),   # Fig 9b
    (0.10, 0.4, 0.4, 0.17),   # Fig 9b
    (0.15, 0.5, 0.5, 0.16),   # Fig 9c
    (0.25, 1.0, 0.0, 0.23),   # Fig 9e
])
def test_moment_capacity_matches_chart_readings(d2h, omega_k, n, m_chart):
    """Values read off the printed charts; agreement within reading accuracy."""
    assert chart_model(d2h, omega_k).moment_capacity(n) == pytest.approx(m_chart, rel=0.06)


def test_flat_top_at_squash_load():
    """Once both layers are elastic, N stays at NRd,max while M falls (flat tops of Fig 9)."""
    model = chart_model(0.1, 0.3)
    assert model.moment_capacity(model.n_max() * 1.01) is None
    m_corner = model.moment_capacity(model.n_max())
    n_far, m_far = model.forces(10.0)
    assert n_far == pytest.approx(model.n_max(), rel=1e-9)
    assert 0 < m_far < m_corner


def test_neutral_axis_solution_is_in_equilibrium():
    model = SectionModel(300, 300, [(46, 603.2), (150, 402.1), (254, 603.2)], 17.0, FYD, 200_000.0)
    m = model.moment_capacity(1.5e6)
    x = model._depth_for(1.5e6)
    assert model.forces(x)[0] == pytest.approx(1.5e6, rel=1e-6)
    assert m == pytest.approx(71.9e6, rel=0.002)


def test_curve_runs_from_pure_bending_to_pure_compression():
    curve = chart_model(0.1, 0.5).curve()
    assert curve[0][1] == pytest.approx(0.0, abs=1e-9)
    assert curve[-1] == (0.0, pytest.approx(chart_model(0.1, 0.5).n_max()))
    assert all(m >= 0 for m, _ in curve)
