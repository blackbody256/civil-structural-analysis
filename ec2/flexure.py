"""Bending, shear and deflection of beams and slabs to BS EN 1992-1-1 (UK National Annex).

Simplified rectangular stress block, concrete up to C50/60. Lengths in mm, forces in N,
moments in N·mm and stresses in MPa.
"""
import math

from .tables import KPRIME_UK_LIMIT


def k_prime(delta=1.0, uk_limit=True):
    """K' = 0.60δ − 0.18δ² − 0.21, optionally limited to 0.168 for a ductile failure."""
    kp = 0.60 * delta - 0.18 * delta**2 - 0.21
    return min(kp, KPRIME_UK_LIMIT) if uk_limit else kp


def lever_arm(K, d):
    """z = d/2·[1 + √(1 − 3.53K)] ≤ 0.95d."""
    return min(d / 2 * (1 + math.sqrt(max(0.0, 1 - 3.53 * K))), 0.95 * d)


def rectangular(M, b, d, d2, fck, fyd, kp):
    """Tension (and, if K > K', compression) steel for a rectangular section."""
    K = M / (b * d**2 * fck)
    if K <= kp:
        z = lever_arm(K, d)
        return {"K": K, "kp": kp, "z": z, "x": 2.5 * (d - z), "As": M / (fyd * z), "As2": 0.0,
                "compression": False, "ok": True}
    z = lever_arm(kp, d)
    x = 2.5 * (d - z)
    fsc = min(700 * (x - d2) / x, fyd)
    if fsc <= 0:
        return {"K": K, "kp": kp, "z": z, "x": x, "fsc": fsc, "As": math.inf, "As2": math.inf,
                "compression": True, "ok": False}
    As2 = (K - kp) * fck * b * d**2 / (fsc * (d - d2))
    As = kp * fck * b * d**2 / (fyd * z) + As2 * fsc / fyd
    return {"K": K, "kp": kp, "z": z, "x": x, "fsc": fsc, "As": As, "As2": As2, "compression": True, "ok": True}


def flanged(M, beff, bw, hf, d, fck, fyd, kp):
    """Tension steel for a flanged section in sagging (flange in compression)."""
    K = M / (beff * d**2 * fck)
    out = {"K": K, "kp": kp, "As2": 0.0, "compression": False}
    if K <= kp:
        z = lever_arm(K, d)
        x = 2.5 * (d - z)
        out.update(z=z, x=x)
        if x <= 1.25 * hf:
            return {**out, "in_flange": True, "As": M / (fyd * z), "ok": True}
    mrf = 0.57 * fck * (beff - bw) * hf * (d - 0.5 * hf)
    kf = (M - mrf) / (fck * bw * d**2)
    out.update(in_flange=False, MRf=mrf, Kf=kf)
    if kf > kp:
        return {**out, "As": math.inf, "ok": False}
    if M <= mrf:
        return {**out, "As": M / (fyd * (d - 0.5 * hf)), "z_web": None, "ok": True}
    z_web = lever_arm(kf, d)
    As = mrf / (fyd * (d - 0.5 * hf)) + (M - mrf) / (fyd * z_web)
    return {**out, "z_web": z_web, "As": As, "ok": True}


def strut_capacity(fck, cot):
    """vRd,max = ν1·fcd/(cot θ + tan θ) with ν1 = 0.6(1 − fck/250), fcd = fck/1.5 (αcw = 1)."""
    return 0.4 * fck * (1 - fck / 250) / (cot + 1 / cot)


def vertical_shear(v_ed, fck):
    """Strut angle for a shear stress vEd: cot θ = 2.5 when possible, else the steeper angle.

    Returns (cot θ, vRd,max at cot θ = 2.5, at cot θ = 1.0); cot θ is None if vEd > vRd,max(1.0).
    """
    v25, v10 = strut_capacity(fck, 2.5), strut_capacity(fck, 1.0)
    if v_ed <= v25:
        return 2.5, v25, v10
    if v_ed <= v10:
        theta = 0.5 * math.asin(v_ed / (0.20 * fck * (1 - fck / 250)))
        return 1 / math.tan(theta), v25, v10
    return None, v25, v10


def rho_w_min(fck, fyk):
    """Minimum shear reinforcement ratio 0.08·√fck/fyk."""
    return 0.08 * math.sqrt(fck) / fyk


def basic_span_depth(K, fck, rho, rho_c=0.0):
    """Basic span/effective depth ratio (EC2 Expressions 7.16a and 7.16b)."""
    rho0 = math.sqrt(fck) / 1000
    rf = math.sqrt(fck)
    if rho <= rho0:
        return K * (11 + 1.5 * rf * rho0 / rho + 3.2 * rf * (rho0 / rho - 1) ** 1.5)
    return K * (11 + 1.5 * rf * rho0 / max(rho - rho_c, 1e-9) + rf / 12 * math.sqrt(rho_c / rho0))


def vrd_c(fck, d, rho_l):
    """Concrete shear resistance without shear reinforcement (MPa), EC2 Cl 6.2.2.

    k = min(1 + √(200/d), 2.0); ρl = min(As/(b·d), 0.02)
    vRd,c = 0.12·k·(100·ρl·fck)^(1/3) ≥ 0.035·k^1.5·√fck
    """
    k = min(1.0 + math.sqrt(200.0 / d), 2.0)
    rho = min(rho_l, 0.02)
    v = 0.12 * k * (100.0 * rho * fck) ** (1.0 / 3.0)
    vmin = 0.035 * (k ** 1.5) * math.sqrt(fck)
    return max(v, vmin)

