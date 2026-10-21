"""Material properties used throughout the guide.

Concrete properties follow Chapter 2, Table 4 (EC2 Table 3.1). C28/35 and C32/40
are BS 8500 classes that are not in EC2 Table 3.1. Reinforcement follows Chapter 2,
Table 5. Partial factors and alpha_cc default to the UK National Annex values used
in the guide; they can be overridden for other National Annexes.
"""
import math
from dataclasses import dataclass

from .tables import CONCRETE_CLASSES, CONCRETE_PROPS

# class: (fck, fck_cube, fctm, Ecm [GPa]), a dictionary view of tables.CONCRETE_PROPS
CONCRETE_TABLE = {
    name: tuple(float(v) for v in row) for name, row in zip(CONCRETE_CLASSES, CONCRETE_PROPS)
}

# Chapter 2, Table 5: ductility class -> (min k = (ft/fy)k, min eps_uk [%])
DUCTILITY_CLASSES = {
    "A": ("≥ 1.05", "≥ 2.5"),
    "B": ("≥ 1.08", "≥ 5.0"),
    "C": ("≥ 1.15, < 1.35", "≥ 7.5"),
}

BAR_SIZES = (8, 10, 12, 16, 20, 25, 32, 40)
LINK_SIZES = (6, 8, 10, 12)


def bar_area(dia):
    return math.pi * dia**2 / 4.0


def strength_fck(class_name):
    """Characteristic cylinder strength of a class name such as 'C30/37'."""
    return CONCRETE_TABLE[class_name][0]


@dataclass(frozen=True)
class Concrete:
    name: str
    fck: float
    fck_cube: float
    fctm: float
    Ecm: float
    gamma_c: float = 1.5
    alpha_cc: float = 0.85

    @classmethod
    def from_class(cls, name, gamma_c=1.5, alpha_cc=0.85):
        fck, fck_cube, fctm, ecm = CONCRETE_TABLE[name]
        return cls(name, fck, fck_cube, fctm, ecm, gamma_c, alpha_cc)

    @property
    def fcd(self):
        return self.alpha_cc * self.fck / self.gamma_c

    @property
    def fcm(self):
        return self.fck + 8.0


@dataclass(frozen=True)
class Reinforcement:
    fyk: float = 500.0
    ductility: str = "B"
    gamma_s: float = 1.15
    Es: float = 200_000.0

    @property
    def fyd(self):
        return self.fyk / self.gamma_s

    @property
    def eps_yd(self):
        return self.fyd / self.Es
