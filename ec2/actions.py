"""Combinations of actions for buildings (Chapter 1, Tables 3–5, UK National Annex)."""
from .tables import PSI, PSI_CATEGORIES, PSI_LABELS

GAMMA_G = 1.35
GAMMA_Q = 1.5
XI = 1.0  # 0.925 reduction removed; strictly G = 1.35gk, Q = 1.5qk


def psi_factors(category):
    psi0, psi1, psi2 = PSI[PSI_CATEGORIES.index(category)]
    return float(psi0), float(psi1), float(psi2)


def categories():
    return [{"id": c, "label": label, "psi": [float(v) for v in PSI[i]]}
            for i, (c, label) in enumerate(zip(PSI_CATEGORIES, PSI_LABELS))]


def uls_combination(gk, qk, category="B", expression="6.10ab"):
    """Design load for one variable action.

    Strictly uses G = 1.35Gk and Q = 1.5Qk (0.925 factor removed).
    """
    psi0, _, psi2 = psi_factors(category)
    quasi_permanent = gk + psi2 * qk
    if expression == "6.10":
        value = GAMMA_G * gk + GAMMA_Q * qk
        governing = "6.10"
        working = [f"Exp (6.10): 1.35 × {gk:g} + 1.5 × {qk:g} = {value:.1f} kN"]
    else:
        a = GAMMA_G * gk + GAMMA_Q * psi0 * qk
        b = XI * GAMMA_G * gk + GAMMA_Q * qk
        value = max(a, b)
        governing = "6.10a" if a >= b else "6.10b"
        working = [
            f"Exp (6.10a): 1.35 × {gk:g} + 1.5 × {psi0:g} × {qk:g} = {a:.1f} kN",
            f"Exp (6.10b): 1.35 × {gk:g} + 1.5 × {qk:g} = {b:.1f} kN",
            f"Less favourable: Exp ({governing}) = {value:.1f} kN",
        ]
    working.append(f"Quasi-permanent: {gk:g} + {psi2:g} × {qk:g} = {quasi_permanent:.1f} kN")
    return {
        "value": value,
        "governing": governing,
        "quasi_permanent": quasi_permanent,
        "qp_ratio": quasi_permanent / value if value else 0.0,
        "working": working,
    }
