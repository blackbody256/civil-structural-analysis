"""Column pipeline against a hand-calculated example (300 × 300, C30/37, 8H16)."""
import math

import pytest

from conftest import by_id
from ec2.column import ValidationError, check_column, parse_input, required_steel, analyse_axis
from ec2.interaction import SectionModel


def test_hand_calculated_example(example):
    report = check_column(example)
    y = report["derived"]["axes"]["y"]
    # Exp 5.15 with k1 = k2 = 0.2: F = 0.5·(1 + 0.2/0.65)
    assert y["F"] == pytest.approx(0.6538, abs=1e-4)
    assert y["l0"] == pytest.approx(2288.5, abs=0.5)
    assert y["lam"] == pytest.approx(26.42, abs=0.01)
    # ei = 20 mm governs: M02 = 30 + 0.020·1500, M01 = 15 + 30
    assert (y["e_i"], y["M02"], y["M01"]) == (20.0, pytest.approx(60.0), pytest.approx(45.0))
    # C = 1.7 − 0.75; n = 1500e3/(90000·17); λlim = 15.4·C/√n
    assert y["C"] == pytest.approx(0.95)
    assert report["derived"]["n"] == pytest.approx(0.98039, abs=1e-5)
    assert y["lam_lim"] == pytest.approx(14.776, abs=0.005)
    assert y["slender"] is True
    # Fig 3: ω = 0.4571, Kr = 0.4510, Kφ = 1.5440, d = 150 + 90.07, e2 = 7.34 mm
    assert y["Kr"] == pytest.approx(0.45095, abs=5e-5)
    assert y["Kphi"] == pytest.approx(1.54404, abs=5e-5)
    assert y["e2"] == pytest.approx(7.338, abs=0.005)
    assert y["M2"] == pytest.approx(11.007, abs=0.005)
    assert y["MEd"] == pytest.approx(65.007, abs=0.005)
    assert y["MRd"] == pytest.approx(71.9, abs=0.1)
    assert report["summary"]["verdict"] == "pass"


def test_required_steel_is_consistent(example):
    inp = parse_input(example)
    sec, conc, steel = inp.section, inp.concrete, inp.steel
    n = inp.n_ed / (sec.Ac * conc.fcd)
    omega = sec.As * steel.fyd / (sec.Ac * conc.fcd)
    ax = analyse_axis(inp, "y", n, omega)
    as_req = required_steel(inp, ax, n)
    assert 0 < as_req < sec.As
    depth, width, layers = sec.layers("y")
    scaled = SectionModel(depth, width, layers, conc.fcd, steel.fyd, steel.Es, steel_scale=as_req / sec.As)
    from ec2.column import _design_moment_for
    m_ed = _design_moment_for(inp, ax, n, as_req * steel.fyd / (sec.Ac * conc.fcd))
    assert scaled.moment_capacity(inp.n_ed) == pytest.approx(m_ed, rel=1e-3)


def test_every_check_has_status_reference_and_markup(example):
    for c in check_column(example)["checks"]:
        assert c["status"] in {"pass", "fail", "warn", "info", "na"}
        assert c["refs"], c["id"]
        assert set(c["markup"]) == {"result", "working", "note"}


def test_biaxial_runs_only_with_moments_about_both_axes(example):
    assert by_id(check_column(example))["biaxial"]["status"] == "na"
    example["actions"].update(Mz_top=10, Mz_bottom=5)
    biaxial = by_id(check_column(example))["biaxial"]
    assert biaxial["status"] in {"pass", "fail"}
    assert biaxial["value"] == pytest.approx(1.0, abs=0.05)


def test_double_curvature_raises_lambda_lim(example):
    single = check_column(example)["derived"]["axes"]["y"]
    example["actions"]["My_curvature"] = "double"
    double = check_column(example)["derived"]["axes"]["y"]
    assert double["M01"] == pytest.approx(-15 + 30)
    assert double["C"] > single["C"] and double["lam_lim"] > single["lam_lim"]


def test_unbraced_column_uses_exp_516_and_c_07(example):
    example["restraint"]["braced"] = False
    report = check_column(example)
    y = report["derived"]["axes"]["y"]
    assert y["C"] == 0.7
    # Exp 5.16, k1 = k2 = 0.2: max{√(1 + 10·0.1); (1 + 0.2/1.2)²}
    assert y["F"] == pytest.approx(max(math.sqrt(2.0), (1 + 0.2 / 1.2) ** 2), abs=1e-9)
    assert by_id(report)["fire_table"]["status"] == "na"


def test_detailing_failures(example):
    example["reinforcement"].update(bar_dia=25, link_dia=6, n_b=6, n_h=6)
    checks = by_id(check_column(example))
    assert checks["link_dia"]["status"] == "fail"       # 6 < 25/4
    assert checks["bar_spacing"]["status"] == "fail"    # clear gap < max(φ, dg + 5, 20)


@pytest.mark.parametrize("b, h, phi, s_max, near, far", [
    (300, 300, 25, 180, 175, 300),   # 0.6·b governs: 1.67 × 180 = 300.6
    (300, 300, 16, 180, 175, 300),   # 12φ = 192, 0.6·b = 180
    (350, 350, 12, 144, 125, 225),   # 12φ governs: 1.67 × 144 = 240.5
    (500, 500, 25, 240, 225, 400),   # 240 mm governs
])
def test_link_spacing_is_calculated(example, b, h, phi, s_max, near, far):
    example["geometry"].update(b=b, h=h)
    example["reinforcement"].update(bar_dia=phi, link_dia=8)
    report = check_column(example)
    links = report["derived"]["links"]
    assert (links["s_max"], links["near"], links["far"]) == (pytest.approx(s_max), near, far)
    assert by_id(report)["link_spacing"]["status"] == "info"


def test_unrestrained_bars_need_cross_ties(example):
    example["geometry"].update(b=500, h=500)
    example["reinforcement"].update(n_b=3, n_h=3)
    assert by_id(check_column(example))["bar_restraint"]["status"] == "fail"
    example["reinforcement"]["cross_ties"] = True
    assert by_id(check_column(example))["bar_restraint"]["status"] == "pass"


def test_durability_and_scope_failures(example):
    example["durability"].update(exposure="XC3/4", cement_group="All except IVB")
    example["materials"]["concrete"] = "C25/30"   # needs 35 + 10 mm
    assert by_id(check_column(example))["cover_durability"]["status"] == "fail"
    example["materials"]["fyk"] = 250
    assert by_id(check_column(example))["scope"]["status"] == "fail"


def test_wall_proportions_warn(example):
    example["geometry"].update(b=200, h=900)
    assert by_id(check_column(example))["wall"]["status"] == "warn"


def test_validation_errors(example):
    example["geometry"]["b"] = 50
    example["reinforcement"]["n_b"] = 1.5
    with pytest.raises(ValidationError) as err:
        check_column(example)
    assert set(err.value.errors) == {"geometry.b", "reinforcement.n_b"}


def test_cover_must_fit_section(example):
    example["reinforcement"]["cover"] = 140
    with pytest.raises(ValidationError) as err:
        check_column(example)
    assert "reinforcement.cover" in err.value.errors


def test_uniaxial_bending_ignores_z_moments(example):
    example["actions"].update(bending="uniaxial", Mz_top=40, Mz_bottom=20)
    report = check_column(example)
    z = report["derived"]["axes"]["z"]
    assert (z["M_top"], z["M_bottom"]) == (0, 0)
    assert z["M02"] == pytest.approx(20e-3 * 1500)          # imperfection only: ei·NEd
    assert by_id(report)["biaxial"]["status"] == "na"


def test_biaxial_bending_needs_moments_about_both_axes(example):
    example["actions"].update(bending="biaxial", Mz_top=0, Mz_bottom=0)
    with pytest.raises(ValidationError) as err:
        check_column(example)
    assert "actions.Mz_top" in err.value.errors
    example["actions"].update(Mz_top=10, Mz_bottom=5)
    assert by_id(check_column(example))["biaxial"]["status"] in {"pass", "fail"}


def test_bending_defaults_from_the_moments(example):
    assert check_column(example)["derived"]["bending"] == "uniaxial"
    example["actions"].update(Mz_top=10)
    assert check_column(example)["derived"]["bending"] == "biaxial"
