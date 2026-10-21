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
