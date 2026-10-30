"""Numeric tables transcribed from 'How to Design Concrete Structures using Eurocode 2'.

Each array notes its chapter, table and printed page so it can be checked against
the PDF. Categorical tables (Ch 2 Table 8, Ch 5 Table 2) live in durability.py and
fire.py.
"""
import numpy as np

# Ch 2, Table 4 (p.11): concrete properties.
# Columns: fck [MPa], fck,cube [MPa], fctm [MPa], Ecm [GPa]
CONCRETE_CLASSES = ("C12/15", "C16/20", "C20/25", "C25/30", "C28/35", "C30/37",
                    "C32/40", "C35/45", "C40/50", "C45/55", "C50/60")
CONCRETE_PROPS = np.array([
    [12, 15, 1.6, 27],
    [16, 20, 1.9, 29],
    [20, 25, 2.2, 30],
    [25, 30, 2.6, 31],
    [28, 35, 2.8, 32],
    [30, 37, 2.9, 33],
    [32, 40, 3.0, 34],
    [35, 45, 3.2, 34],
    [40, 50, 3.5, 35],
    [45, 55, 3.8, 36],
    [50, 60, 4.1, 37],
])

# Ch 1, Table 3 (p.3): ψ factors for imposed loads in buildings (UK NA).
# Columns: ψ0, ψ1, ψ2
PSI_CATEGORIES = ("A", "B", "C", "D", "E", "F", "G", "H")
PSI_LABELS = ("Domestic, residential areas", "Office areas", "Congregation areas",
              "Shopping areas", "Storage areas", "Traffic area, vehicle ≤ 30 kN",
              "Traffic area, 30–160 kN", "Roofs")
PSI = np.array([
    [0.7, 0.5, 0.3],
    [0.7, 0.5, 0.3],
    [0.7, 0.7, 0.6],
    [0.7, 0.7, 0.6],
    [1.0, 0.9, 0.8],
    [0.7, 0.7, 0.6],
    [0.7, 0.5, 0.3],
    [0.7, 0.0, 0.0],
])

# Ch 5, Table 4 (p.37): effective length factor F = l0/l for braced columns.
# Rows are k2, columns are k1; np.inf stands for "Pinned".
TABLE4_K = np.array([0.10, 0.20, 0.30, 0.40, 0.50, 0.70, 1.00, 2.00, 5.00, 9.00, np.inf])
TABLE4_F = np.array([
    [0.59, 0.62, 0.64, 0.66, 0.67, 0.69, 0.71, 0.73, 0.75, 0.76, 0.77],
    [0.62, 0.65, 0.68, 0.69, 0.71, 0.73, 0.74, 0.77, 0.79, 0.80, 0.81],
    [0.64, 0.68, 0.70, 0.72, 0.73, 0.75, 0.77, 0.80, 0.82, 0.83, 0.84],
    [0.66, 0.69, 0.72, 0.74, 0.75, 0.77, 0.79, 0.82, 0.84, 0.85, 0.86],
    [0.67, 0.71, 0.73, 0.75, 0.76, 0.78, 0.80, 0.83, 0.86, 0.86, 0.87],
    [0.69, 0.73, 0.75, 0.77, 0.78, 0.80, 0.82, 0.85, 0.88, 0.89, 0.90],
    [0.71, 0.74, 0.77, 0.79, 0.80, 0.82, 0.84, 0.88, 0.90, 0.91, 0.92],
    [0.73, 0.77, 0.80, 0.82, 0.83, 0.85, 0.88, 0.91, 0.93, 0.94, 0.95],
    [0.75, 0.79, 0.82, 0.84, 0.86, 0.88, 0.90, 0.93, 0.96, 0.97, 0.98],
    [0.76, 0.80, 0.83, 0.85, 0.86, 0.89, 0.91, 0.94, 0.97, 0.98, 0.99],
    [0.77, 0.81, 0.84, 0.86, 0.87, 0.90, 0.92, 0.95, 0.98, 0.99, 1.00],
])

# Ch 5, Table 5 (p.41): exponent a for biaxial bending (linear interpolation allowed).
TABLE5_N_RATIO = np.array([0.1, 0.7, 1.0])
TABLE5_A = np.array([1.0, 1.5, 2.0])

# Ch 10, Table 13 (p.88–89): bars in compression, good bond, as multiples of φ.
# Columns: anchorage (straight), lap 50% in one location, lap 100% in one location
LAP_CLASSES = ("C20/25", "C25/30", "C28/35", "C30/37", "C32/40", "C35/45",
               "C40/50", "C45/55", "C50/60")
COMPRESSION_BOND = np.array([
    [47, 66, 70],
    [40, 57, 61],
    [37, 52, 56],
    [36, 50, 54],
    [34, 48, 51],
    [32, 45, 48],
    [30, 41, 44],
    [27, 38, 41],
    [25, 38, 41],
])


def _flex_variable(k):
    """Map k to k/(0.45 + k), the variable in Exp (5.15); Pinned maps to 1."""
    k = np.maximum(np.asarray(k, dtype=float), TABLE4_K[0])
    return np.where(np.isinf(k), 1.0, k / (0.45 + np.where(np.isinf(k), 1.0, k)))


def table4_factor(k1, k2):
    """Bilinear interpolation in Table 4 (performed in the k/(0.45+k) variable)."""
    grid = _flex_variable(TABLE4_K)
    t1, t2 = float(_flex_variable(k1)), float(_flex_variable(k2))
    by_row = np.array([np.interp(t1, grid, row) for row in TABLE4_F])
    return float(np.interp(t2, grid, by_row))


def table5_exponent(n_ratio):
    return float(np.interp(n_ratio, TABLE5_N_RATIO, TABLE5_A))


def compression_lap(class_name, percent_lapped=100):
    """Lap length multiple of φ for compression bars (None for classes below C20/25)."""
    if class_name not in LAP_CLASSES:
        return None
    column = 2 if percent_lapped > 50 else 1
    return int(COMPRESSION_BOND[LAP_CLASSES.index(class_name), column])


# ---------------------------------------------------------------- beams and slabs

# Ch 4, Table 3 (p.27): moment and shear coefficients for beams of 3 or more similar spans
# with Qk ≤ Gk. Moments are coefficient × (load on the span) × span, with G and Q the total
# ULS permanent and variable loads on the span; shears are coefficient × (G + Q).
BEAM_SPAN_MOMENT = {"end": (0.090, 0.100), "interior": (0.066, 0.086)}        # (on G, on Q)
BEAM_SUPPORT_MOMENT = {"end": 0.094, "interior": 0.075}                      # × (G + Q)·l, hogging
BEAM_SUPPORT_SHEAR = {"end": 0.63, "interior": 0.55}                         # × (G + Q)

# Ch 4, Table 4 (p.27): K' against the redistribution ratio δ; K' = 0.60δ − 0.18δ² − 0.21
KPRIME_DELTA = np.array([1.00, 0.90, 0.85, 0.80, 0.75, 0.70])
KPRIME = np.array([0.208, 0.182, 0.168, 0.153, 0.137, 0.120])
KPRIME_UK_LIMIT = 0.168          # often recommended in the UK to ensure a ductile failure

# Ch 4, Table 7 (p.28): strut capacity vRd,max (MPa) at cot θ = 2.5 and cot θ = 1.0
STRUT_FCK = np.array([20, 25, 28, 30, 32, 35, 40, 45, 50])
STRUT_COT25 = np.array([2.54, 3.10, 3.43, 3.64, 3.84, 4.15, 4.63, 5.08, 5.51])
STRUT_COT10 = np.array([3.68, 4.50, 4.97, 5.28, 5.58, 6.02, 6.72, 7.38, 8.00])

# Ch 4, Table 9 (p.31): minimum shear reinforcement ratio ρw,min × 10³ (fyk = 500 MPa)
RHO_W_MIN = np.array([0.72, 0.80, 0.85, 0.88, 0.91, 0.95, 1.01, 1.07, 1.13])

# Ch 2, Table 11 (p.15): maximum bar size or spacing to limit crack width
CRACK_STRESS = np.array([160, 200, 240, 280, 320, 360])
CRACK_LIMITS = {   # wmax: (max bar size, max bar spacing) in mm
    0.4: (np.array([40, 32, 20, 16, 12, 10]), np.array([300, 300, 250, 200, 150, 100])),
    0.3: (np.array([32, 25, 16, 12, 10, 8]), np.array([300, 250, 200, 150, 100, 50])),
}


def crack_limits(sigma_s, w_max):
    """Largest bar size and spacing for a steel stress, interpolated in Table 11.

    Returns (None, None) above 360 MPa, where the table gives no limit.
    """
    if sigma_s > CRACK_STRESS[-1]:
        return None, None
    sizes, spacings = CRACK_LIMITS[w_max]
    stress = max(float(sigma_s), float(CRACK_STRESS[0]))
    return float(np.interp(stress, CRACK_STRESS, sizes)), float(np.interp(stress, CRACK_STRESS, spacings))


# ---------------------------------------------------------------- two-way slabs

# Ch 3, Table 8 (p.22): bending moment coefficients for two-way spanning rectangular
# slabs supported by beams on four edges, with provision for torsion at corners
# (matches BS 8110-1 Table 3.14).
# Short-span coefficients βsx are given for ly/lx ratios; long-span coefficients βsy
# are independent of ly/lx. Where an edge in that direction is discontinuous, the support
# coefficient is None.
SLAB_LY_LX = np.array([1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.75, 2.0])

SLAB_CASES = [
    {
        "id": "interior",
        "label": "Interior panels",
        "bsx_sup": np.array([0.031, 0.037, 0.042, 0.046, 0.050, 0.053, 0.059, 0.063]),
        "bsx_mid": np.array([0.024, 0.028, 0.032, 0.035, 0.037, 0.040, 0.044, 0.048]),
        "bsy_sup": 0.032,
        "bsy_mid": 0.024,
    },
    {
        "id": "one_short_discontinuous",
        "label": "One short edge discontinuous",
        "bsx_sup": np.array([0.039, 0.044, 0.048, 0.052, 0.055, 0.058, 0.063, 0.067]),
        "bsx_mid": np.array([0.029, 0.033, 0.036, 0.039, 0.041, 0.043, 0.047, 0.050]),
        "bsy_sup": 0.037,
        "bsy_mid": 0.028,
    },
    {
        "id": "one_long_discontinuous",
        "label": "One long edge discontinuous",
        "bsx_sup": np.array([0.039, 0.049, 0.056, 0.062, 0.068, 0.073, 0.082, 0.089]),
        "bsx_mid": np.array([0.030, 0.036, 0.042, 0.047, 0.051, 0.055, 0.062, 0.067]),
        "bsy_sup": 0.037,
        "bsy_mid": 0.028,
    },
    {
        "id": "two_adjacent_discontinuous",
        "label": "Two adjacent edges discontinuous",
        "bsx_sup": np.array([0.047, 0.056, 0.063, 0.069, 0.074, 0.078, 0.087, 0.093]),
        "bsx_mid": np.array([0.036, 0.042, 0.047, 0.051, 0.055, 0.059, 0.065, 0.070]),
        "bsy_sup": 0.045,
        "bsy_mid": 0.034,
    },
    {
        "id": "two_short_discontinuous",
        "label": "Two short edges discontinuous",
        "bsx_sup": np.array([0.046, 0.050, 0.054, 0.057, 0.060, 0.062, 0.067, 0.070]),
        "bsx_mid": np.array([0.034, 0.038, 0.040, 0.043, 0.045, 0.047, 0.050, 0.053]),
        "bsy_sup": None,
        "bsy_mid": 0.034,
    },
    {
        "id": "two_long_discontinuous",
        "label": "Two long edges discontinuous",
        "bsx_sup": None,
        "bsx_mid": np.array([0.034, 0.046, 0.056, 0.065, 0.072, 0.078, 0.091, 0.100]),
        "bsy_sup": 0.045,
        "bsy_mid": 0.034,
    },
    {
        "id": "three_discontinuous_one_long_continuous",
        "label": "Three edges discontinuous (one long edge continuous)",
        "bsx_sup": np.array([0.057, 0.065, 0.071, 0.076, 0.081, 0.084, 0.092, 0.098]),
        "bsx_mid": np.array([0.043, 0.048, 0.053, 0.057, 0.060, 0.063, 0.069, 0.074]),
        "bsy_sup": None,
        "bsy_mid": 0.044,
    },
    {
        "id": "three_discontinuous_one_short_continuous",
        "label": "Three edges discontinuous (one short edge continuous)",
        "bsx_sup": None,
        "bsx_mid": np.array([0.042, 0.054, 0.063, 0.071, 0.078, 0.084, 0.096, 0.105]),
        "bsy_sup": 0.058,
        "bsy_mid": 0.044,
    },
    {
        "id": "four_discontinuous",
        "label": "Four edges discontinuous",
        "bsx_sup": None,
        "bsx_mid": np.array([0.055, 0.065, 0.074, 0.081, 0.087, 0.092, 0.103, 0.111]),
        "bsy_sup": None,
        "bsy_mid": 0.056,
    },
]

# Note: The guide does not provide shear coefficients (βvx, βvy) for two-way slabs.
# See ec2/slab.py for the conservative shear estimates (VEd = 0.5·n·lx or 0.6·n·lx).


def two_way_coefficients(case_id, ly_lx):
    """Bending moment coefficients βsx, βsy for a restrained two-way slab.

    Linearly interpolated in ly/lx. If ly/lx > 2.0, raises ValueError.
    """
    if ly_lx < 1.0 - 1e-9:
        raise ValueError(f"ly/lx = {ly_lx:g} < 1.0 (lx must be the shorter span)")
    if ly_lx > 2.0 + 1e-9:
        raise ValueError(f"ly/lx = {ly_lx:g} > 2.0 (design as a one-way slab)")

    case = next((c for c in SLAB_CASES if c["id"] == case_id), None)
    if case is None:
        raise ValueError(f"Unknown slab case: {case_id}")

    r = float(np.clip(ly_lx, 1.0, 2.0))
    bsx_sup = float(np.interp(r, SLAB_LY_LX, case["bsx_sup"])) if case["bsx_sup"] is not None else None
    bsx_mid = float(np.interp(r, SLAB_LY_LX, case["bsx_mid"]))
    bsy_sup = float(case["bsy_sup"]) if case["bsy_sup"] is not None else None
    bsy_mid = float(case["bsy_mid"])

    return {
        "bsx_sup": bsx_sup,
        "bsx_mid": bsx_mid,
        "bsy_sup": bsy_sup,
        "bsy_mid": bsy_mid,
    }

