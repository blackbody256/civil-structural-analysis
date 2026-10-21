"""Effective length, slenderness and design moments for columns (Ch 5, Figs 2–6).

Lengths are in mm, forces in N and moments in N·mm.
"""
import math

from .tables import table5_exponent

PINNED = math.inf
SQRT12 = math.sqrt(12.0)          # i = h/√12, so λ = 3.46·l0/h
N_BAL = 0.4                       # n at maximum moment of resistance (Fig 3)
CURVATURE_C = 10.0                # c for a constant cross-section (≈ π²)

# Idealised isolated members, Ch 5 Fig 5 (a–e): effective length factor F = l0/l
FIG5_CASES = {
    "a": ("Pinned both ends", 1.0),
    "b": ("Cantilever: fixed base, free top", 2.0),
    "c": ("Fixed base, pinned top", 0.7),
    "d": ("Fixed both ends", 0.5),
    "e": ("Fixed base, top fixed in rotation but free to sway", 1.0),
}


def _flex(k):
    return 2.0 if math.isinf(k) else 1.0 + k / (0.45 + k)


def factor_braced(k1, k2):
    """Exp (5.15); reproduces Table 4."""
    return 0.5 * math.sqrt(_flex(k1) * _flex(k2))


def factor_unbraced(k1, k2):
    """Exp (5.16) for unbraced members (Ch 5, 'Unbraced columns')."""
    if math.isinf(k1) and math.isinf(k2):
        raise ValueError("An unbraced column pinned at both ends is a mechanism.")
    if math.isinf(k1):
        coupled = k2
    elif math.isinf(k2):
        coupled = k1
    else:
        coupled = k1 * k2 / (k1 + k2) if k1 + k2 > 0 else 0.0
    ratio = lambda k: 1.0 if math.isinf(k) else k / (1.0 + k)
    return max(math.sqrt(1.0 + 10.0 * coupled), (1.0 + ratio(k1)) * (1.0 + ratio(k2)))


def stiffness_k(column_I, column_l, beams):
    """Relative flexibility k = (EIc/lc) / Σ(2EIb/lb) ≥ 0.1 (PD 6687 simplification).

    beams: iterable of (Ib, lb). With no beams the end is unrestrained (pinned).
    """
    restraint = sum(2.0 * ib / lb for ib, lb in beams)
    if restraint <= 0:
        return PINNED
    return max(0.1, (column_I / column_l) / restraint)


def slenderness(l0, depth):
    return SQRT12 * l0 / depth


def imperfection_eccentricity(l0, depth):
    """ei = max(l0/400, h/30, 20 mm), Ch 5 'Design moments'."""
    return max(l0 / 400.0, depth / 30.0, 20.0)


def first_order_moments(m_top, m_bottom, curvature, n_ed, e_i):
    """M01 and M02 including imperfections; |M02| ≥ |M01|.

    M01 is negative when the end moments give tension on opposite faces (double curvature).
    """
    m_max = max(abs(m_top), abs(m_bottom))
    m_min = min(abs(m_top), abs(m_bottom))
    sign = 1.0 if curvature == "single" else -1.0
    return sign * m_min + e_i * n_ed, m_max + e_i * n_ed


def lambda_limit(A, B, C, n):
    """λlim = 20·A·B·C/√n (Ch 5 'Slenderness')."""
    return 20.0 * A * B * C / math.sqrt(n)


def nominal_curvature(*, n, omega, fck, lam, phi_ef, eps_yd, d, l0, n_ed, m01, m02):
    """Second-order moment and design moment of a slender column (Fig 3)."""
    n_u = 1.0 + omega
    k_r = min(1.0, max(0.0, (n_u - n) / (n_u - N_BAL)))
    beta = 0.35 + fck / 200.0 - lam / 150.0
    k_phi = max(1.0, 1.0 + beta * phi_ef)
    inv_r0 = eps_yd / (0.45 * d)
    e2 = k_r * k_phi * inv_r0 * l0**2 / CURVATURE_C
    m2 = n_ed * e2
    m0e = max(0.6 * m02 + 0.4 * m01, 0.4 * m02)
    m_ed = max(m02, m0e + m2, m01 + 0.5 * m2)
    return {
        "n_u": n_u, "Kr": k_r, "beta": beta, "Kphi": k_phi, "inv_r0": inv_r0,
        "e2": e2, "M2": m2, "M0e": m0e, "MEd": m_ed,
    }


def biaxial_exponent(n_ratio):
    """Exponent a from Table 5, interpolated linearly and held constant outside 0.1–1.0."""
    return table5_exponent(n_ratio)
