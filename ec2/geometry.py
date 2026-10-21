"""Rectangular column section with a symmetric perimeter bar layout.

Coordinates are in mm from the centroid: x runs along b, y runs along h.
Bending about the y–y axis (My) works over the depth h; bending about the
z–z axis (Mz) works over the depth b.
"""
import math
from dataclasses import dataclass

from .materials import bar_area


@dataclass(frozen=True)
class Bar:
    x: float
    y: float
    dia: float
    corner: bool


def _spread(lo, hi, n):
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


@dataclass(frozen=True)
class RectSection:
    b: float
    h: float
    cover: float      # nominal cover to the links
    link_dia: float
    bar_dia: float
    n_b: int          # bars along each b-face, corners included
    n_h: int          # bars along each h-face, corners included

    @property
    def Ac(self):
        return self.b * self.h

    @property
    def axis_distance(self):
        """a = cnom + φlink + φbar/2 (Ch 2 Fig 4, Ch 5 Fig 1)."""
        return self.cover + self.link_dia + self.bar_dia / 2

    @property
    def n_bars(self):
        return 2 * self.n_b + 2 * (self.n_h - 2)

    @property
    def As(self):
        return self.n_bars * bar_area(self.bar_dia)

    def bars(self):
        a = self.axis_distance
        xs = _spread(-self.b / 2 + a, self.b / 2 - a, self.n_b)
        ys = _spread(-self.h / 2 + a, self.h / 2 - a, self.n_h)
        bars = []
        for y in (ys[-1], ys[0]):
            for i, x in enumerate(xs):
                bars.append(Bar(x, y, self.bar_dia, i in (0, len(xs) - 1)))
        for x in (xs[0], xs[-1]):
            for y in ys[1:-1]:
                bars.append(Bar(x, y, self.bar_dia, False))
        return bars

    def layers(self, axis):
        """Section data for bending about `axis` ('y' or 'z').

        Returns (depth, width, [(distance from the compression face, steel area), ...]).
        """
        if axis == "y":
            depth, width, coord = self.h, self.b, (lambda bar: bar.y)
        else:
            depth, width, coord = self.b, self.h, (lambda bar: bar.x)
        rows = {}
        for bar in self.bars():
            dist = round(depth / 2 - coord(bar), 6)
            rows[dist] = rows.get(dist, 0.0) + bar_area(bar.dia)
        return depth, width, sorted(rows.items())

    def steel_gyration_radius(self, axis):
        """i_s, radius of gyration of the total reinforcement about the axis."""
        coords = [bar.y if axis == "y" else bar.x for bar in self.bars()]
        return math.sqrt(sum(c * c for c in coords) / len(coords))

    def clear_spacings(self):
        """Clear gaps between adjacent bars along a b-face and along an h-face."""
        a = self.axis_distance
        s_b = (self.b - 2 * a) / (self.n_b - 1) - self.bar_dia
        s_h = (self.h - 2 * a) / (self.n_h - 1) - self.bar_dia
        return s_b, s_h

    def max_unrestrained_gap(self):
        """Largest clear distance from an intermediate bar to the nearest corner bar.

        Applies when only the corner bars are held by the perimeter link.
        """
        a = self.axis_distance
        worst = 0.0
        for length, n in ((self.b, self.n_b), (self.h, self.n_h)):
            if n < 3:
                continue
            pitch = (length - 2 * a) / (n - 1)
            worst = max(worst, ((n - 1) // 2) * pitch - self.bar_dia)
        return worst
