import pytest

from ec2 import durability, fire


@pytest.mark.parametrize("row, group, cls, cover", [
    ("XC1", "All", "C20/25", 15),
    ("XC1", "All", "C40/50", 15),
    ("XC3/4", "All except IVB", "C40/50", 20),
    ("XC3/4", "All except IVB", "C30/37", 25),
    ("XC3/4", "All except IVB", "C28/35", 30),
    ("XC3/4", "All except IVB", "C25/30", 35),
    ("XC3/4-XF1", "All except IVB", "C28/35", 30),
    ("XD1", "All", "C32/40", 30),
    ("XS1-XF1", "CEM I, IIA, IIB-S, SRPC", "C40/50", 35),
    ("XS1-XF1", "IIIB", "C32/40", 30),
    ("XD3-XF2", "IIIB, IVB-V", "C32/40", 40),
])
def test_table8_minimum_cover(row, group, cls, cover):
    res = durability.durability_cover(row, group, cls)
    assert res["status"] == "ok"
    assert res["cover"] == cover


@pytest.mark.parametrize("row, group, cls", [
    ("XC1", "All", "C16/20"),
    ("XC3/4", "All except IVB", "C20/25"),
    ("XC3/4-XF1", "All except IVB", "C25/30"),
    ("XD3-XF2", "CEM I, IIA, IIB-S, SRPC", "C30/37"),
])
def test_table8_class_too_weak(row, group, cls):
    assert durability.durability_cover(row, group, cls)["status"] == "too_weak"


def test_table8_flags_bs8500_cells_below_the_found_cover():
    res = durability.durability_cover("XS1-XF1", "CEM I, IIA, IIB-S, SRPC", "C45/55")
    assert res["cover"] == 35 and res["bs8500_below"] == [30]


def test_columns_only_see_vertical_rows():
    ids = {r["id"] for r in durability.rows_for("vertical")}
    assert "XC3/4" in ids and "XC3/4-XF3" not in ids and "XD3" not in ids


@pytest.mark.parametrize("b, a, bars, ok", [
    (300, 46, 8, True),    # 250/46
    (300, 40, 8, False),   # needs 350/40 or 250/46
    (350, 40, 8, True),    # 350/40
    (240, 50, 8, False),   # narrower than 250
])
def test_table2_r60(b, a, bars, ok):
    assert fire.check_column_fire("R60", "multi", 0.7, b, a, bars)[0] is ok


def test_table2_minimum_eight_bars():
    assert fire.check_column_fire("R120", "multi", 0.5, 400, 50, 8)[0] is True
    assert fire.check_column_fire("R120", "multi", 0.5, 400, 50, 4)[0] is False


def test_table2_one_side_exposure():
    assert fire.check_column_fire("R90", "one", 0.7, 160, 25, 4)[0] is True
    assert fire.check_column_fire("R240", "one", 0.7, 290, 70, 4)[0] is False
