import math

import numpy as np
import pytest

from ec2 import slenderness as sl
from ec2 import tables
from ec2.materials import CONCRETE_TABLE, Concrete


def test_exp_515_reproduces_every_cell_of_table4():
    for i, k2 in enumerate(tables.TABLE4_K):
        for j, k1 in enumerate(tables.TABLE4_K):
            assert sl.factor_braced(k1, k2) == pytest.approx(tables.TABLE4_F[i, j], abs=0.0051), (k1, k2)


def test_table4_interpolation_hits_grid_points_and_lies_between():
    assert tables.table4_factor(0.1, 0.1) == pytest.approx(0.59)
    assert tables.table4_factor(math.inf, math.inf) == pytest.approx(1.00)
    assert tables.table4_factor(0.2, 0.5) == pytest.approx(0.71)
    mid = tables.table4_factor(0.25, 0.25)
    assert 0.65 < mid < 0.70
    assert mid == pytest.approx(sl.factor_braced(0.25, 0.25), abs=0.005)


def test_table5_exponent_interpolation():
    assert tables.table5_exponent(0.05) == 1.0
    assert tables.table5_exponent(0.4) == pytest.approx(1.25)
    assert tables.table5_exponent(0.85) == pytest.approx(1.75)
    assert tables.table5_exponent(1.4) == 2.0


def test_concrete_properties_match_chapter2_table4():
    assert CONCRETE_TABLE["C30/37"] == (30.0, 37.0, 2.9, 33.0)
    assert CONCRETE_TABLE["C28/35"] == (28.0, 35.0, 2.8, 32.0)
    assert Concrete.from_class("C30/37").fcd == pytest.approx(17.0)
    assert isinstance(tables.CONCRETE_PROPS, np.ndarray) and tables.CONCRETE_PROPS.shape == (11, 4)


def test_compression_laps_from_table13():
    assert tables.compression_lap("C30/37") == 54
    assert tables.compression_lap("C25/30") == 61
    assert tables.compression_lap("C30/37", 50) == 50
    assert tables.compression_lap("C16/20") is None


def test_unbraced_effective_length_limits():
    assert sl.factor_unbraced(0.0, 0.0) == pytest.approx(1.0)          # Fig 5 e)
    assert sl.factor_unbraced(0.0, math.inf) == pytest.approx(2.0)     # Fig 5 b) cantilever
    with pytest.raises(ValueError):
        sl.factor_unbraced(math.inf, math.inf)


def test_braced_effective_length_limits():
    assert sl.factor_braced(0.0, 0.0) == pytest.approx(0.5)            # Fig 5 d)
    assert sl.factor_braced(math.inf, math.inf) == pytest.approx(1.0)  # Fig 5 a)


def test_pd6687_stiffness():
    column = 300 * 300**3 / 12
    beam = 300 * 500**3 / 12
    k = sl.stiffness_k(column, 3500, [(beam, 6000), (beam, 6000)])
    assert k == pytest.approx(0.1)  # 0.093 limited to the 0.1 minimum
    assert math.isinf(sl.stiffness_k(column, 3500, []))
