import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The worked example used throughout: 300 × 300 braced column, C30/37, 8H16.
BASE = {
    "project": {"name": "Test", "ref": "C1"},
    "materials": {"concrete": "C30/37", "fyk": 500, "ductility": "B", "dg": 20},
    "geometry": {"b": 300, "h": 300, "l": 3.5},
    "reinforcement": {"bar_dia": 16, "n_b": 3, "n_h": 3, "link_dia": 8,
                      "cross_ties": False, "cover": 30, "delta_c_dev": 10},
    "restraint": {"braced": True, "y": {"method": "k", "k_top": 0.2, "k_bottom": 0.2},
                  "z": {"method": "k", "k_top": 0.2, "k_bottom": 0.2}},
    "actions": {"NEd": 1500, "My_top": 30, "My_bottom": 15, "My_curvature": "single",
                "Mz_top": 0, "Mz_bottom": 0, "phi_ef": 1.68},
    "durability": {"exposure": "XC1", "cement_group": "All", "fire_period": "R60",
                   "fire_exposure": "multi", "mu_fi": 0.7, "floor": "intermediate"},
}


@pytest.fixture
def example():
    return copy.deepcopy(BASE)


def by_id(report):
    return {c["id"]: c for c in report["checks"]}
