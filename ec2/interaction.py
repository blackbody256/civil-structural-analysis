"""Axial load + bending resistance by strain compatibility (Ch 5, Figs 7 and 8).

Assumptions, as stated in the guide for concrete up to C50/60:
- rectangular stress block of depth 0.8x at fcd, limited to the section depth;
- εcu = 0.0035 while the neutral axis lies within the section; once it lies outside,
  the strain profile pivots about 0.00175 at mid-depth (the "hinge point"), giving a
  uniform 0.00175 in pure compression;
- reinforcement elastic-perfectly plastic with fyd = fyk/γs and Es = 200 GPa;
- concrete displaced by the bars is not deducted, matching the guide's expressions for As.

Forces are in N and N·mm. Compression is positive and moments are taken about mid-depth.
"""
import math

EPS_CU = 0.0035
EPS_C3 = 0.00175
BLOCK_DEPTH = 0.8


class SectionModel:
    def __init__(self, depth, width, layers, fcd, fyd, Es, steel_scale=1.0):
        self.depth = depth
        self.width = width
        self.layers = [(dist, area * steel_scale) for dist, area in layers]
        self.fcd = fcd
        self.fyd = fyd
        self.Es = Es

    @property
    def As(self):
        return sum(area for _, area in self.layers)

    def strain(self, dist, x):
        if x <= self.depth:
            return EPS_CU * (x - dist) / x
        return EPS_C3 * (x - dist) / (x - self.depth / 2)

    def stress(self, eps):
        return max(-self.fyd, min(self.fyd, self.Es * eps))

    def forces(self, x):
        """(N, M) for a neutral-axis depth x measured from the compression face."""
        s = min(BLOCK_DEPTH * x, self.depth)
        fc = self.fcd * self.width * s
        n, m = fc, fc * (self.depth / 2 - s / 2)
        for dist, area in self.layers:
            f = area * self.stress(self.strain(dist, x))
            n += f
            m += f * (self.depth / 2 - dist)
        return n, m

    def n_max(self):
        """Pure compression: uniform strain 0.00175 (Fig 8a)."""
        return self.fcd * self.width * self.depth + self.As * self.stress(EPS_C3)

    def n_min(self):
        return -self.As * self.fyd

    def _depth_for(self, n_target):
        lo, hi = 1e-6 * self.depth, 1e7 * self.depth
        for _ in range(200):
            mid = math.sqrt(lo * hi)
            if self.forces(mid)[0] < n_target:
                lo = mid
            else:
                hi = mid
        return hi

    def moment_capacity(self, n_ed):
        """MRd at the axial load n_ed, or None if n_ed is outside the section's range."""
        if n_ed > self.n_max() * (1 + 1e-9) or n_ed < self.n_min():
            return None
        if n_ed >= self.n_max():
            n_ed = self.n_max()
        return self.forces(self._depth_for(n_ed))[1]

    def curve(self):
        """Interaction points (M, N) for N ≥ 0, from pure bending up to pure compression."""
        points = []
        x0 = self._depth_for(0.0)
        start = math.log(x0 / self.depth)
        stop = math.log(1.25)
        for i in range(121):
            x = self.depth * math.exp(start + (stop - start) * i / 120)
            n, m = self.forces(x)
            points.append((m, n))
        for ratio in (1.3, 1.4, 1.6, 2, 3, 5, 10, 30, 100, 1000):
            n, m = self.forces(self.depth * ratio)
            points.append((m, n))
        points.append((0.0, self.n_max()))
        return [(max(m, 0.0), n) for m, n in points]
