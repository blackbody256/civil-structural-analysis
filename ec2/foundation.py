"""Pad foundation check, following Chapter 6 of the guide (Foundations) with BS EN 1992-1-1 (UK NA).

A rectangular pad L × B × h under a rectangular column cx × cy at its centre, with characteristic
column loads Gk, Qk and moments MGk, MQk about the base's y axis (the moment acts along L).
The checks run in the order of the chapter:

  bearing    prescriptive method: the largest characteristic pressure (Figure 2, trapezoidal or,
             when e > L/6, triangular) against the presumed allowable bearing value (Table 5);
  EQU        overturning about the toe, 0.9·Gk stabilising against 1.1·MGk + 1.5·MQk;
  bending    STR, 1.35·Gk + 1.5·Qk: the net ground pressure on the cantilever at each column face;
  shear      beam shear at d from each column face, vEd ≤ vRd,c (Table 6, no links);
  punching   at the column face (vEd,max ≤ vRd,max, Table 7) and on control perimeters between 0.5d
             and 2d, the ground reaction inside each perimeter deducted (Figure 4), vRd = vRd,c·2d/a;
  detailing  minimum and maximum steel, bar spacing and crack control.

Lengths in mm, forces in N, moments in N·mm and pressures in N/mm² (MPa) inside the checks;
kN, kNm, m and kPa in the report.
"""
import math
from dataclasses import dataclass

import numpy as np

from . import actions, durability, flexure, tables
from .inputs import Reader, ValidationError
from .materials import BAR_SIZES, CONCRETE_TABLE, DUCTILITY_CLASSES, Concrete, Reinforcement, bar_area
from .results import FAIL, INFO, NA, PASS, WARN, CheckResult, summarise
from .tables import PRESUMED_BEARING_BY_ID, PSI_CATEGORIES

__all__ = ["check_foundation", "parse_foundation", "pressure", "ValidationError"]

GROUPS = ("Scope & materials", "Durability & cover", "Design actions", "Bearing & stability", "Bending",
          "Beam shear", "Punching shear", "Detailing")
CONCRETE_DENSITY = 25.0          # kN/m³
GROUND_COVER = {"blinding": 40, "soil": 75}   # EC2 4.4.1.3(4): k1, k2

ASSUMPTIONS = [
    "Design to BS EN 1992-1-1 with UK National Annex values; rectangular stress block for concrete up to C50/60.",
    "Rectangular pad with the column at its centre; the moment acts along the length L only. Moments are at the "
    "underside of the base (include any horizontal force times the depth).",
    "Bearing by the prescriptive method: characteristic actions (Gk + Qk, moments added at 1.0) with the weight of "
    "the base and the soil over it, against the presumed allowable bearing value, taken as a gross pressure. "
    "Groundwater below the base.",
    "Overturning (EQU): 0.9 × (Gk + base + soil) stabilising; 1.1·MGk + 1.5·MQk destabilising; the imposed axial "
    "load is ignored as it would help.",
    "Structural design (STR): NEd = 1.35·Gk + 1.5·Qk and MEd = 1.35·MGk + 1.5·MQk. The weight of the base and "
    "the soil is carried directly by the ground and causes no bending or shear.",
    "Linear ground pressure: trapezoidal when e ≤ L/6, triangular over 3(L/2 − e) when it is larger.",
    "Bending at the column faces over the full width; beam shear at d from the faces; no shear reinforcement.",
    "Punching: control perimeters with rounded corners from 0.5d to 2d, the ground reaction inside each one "
    "deducted, β = 1 + k·MEd·u/(VEd,red·W); vRd,max = 0.5·ν·fcd at the column face.",
    "Crack control with wmax = 0.3 mm and the quasi-permanent steel stress. Bars fully anchored beyond the faces "
    "(bends may be needed) are assumed.",
    "Durability covers follow BS 8500 for a 50-year working life and 20 mm maximum aggregate.",
]


@dataclass
class FoundationInput:
    project: dict
    concrete: Concrete
    steel: Reinforcement
    dg: float
    cx: float              # column dimension along L, mm
    cy: float              # column dimension along B, mm
    L: float               # base length (direction of the moment), mm
    B: float               # base width, mm
    h: float               # base depth, mm
    hs: float              # depth of soil over the base, mm
    gamma_soil: float      # kN/m³
    soil: str
    q_allow: float | None  # kPa
    Gk: float              # kN
    Qk: float
    MGk: float             # kNm
    MQk: float
    category: str
    x_dia: int             # bottom layer, bars along L
    x_s: float
    y_dia: int             # second layer, bars along B
    y_s: float
    cover: float
    delta_c_dev: float
    cast: str              # "blinding" or "soil"
    exposure: str
    cement_group: str


def parse_foundation(data):
    r = Reader(data if isinstance(data, dict) else {})
    project = r.project()
    concrete_class = r.choice("materials.concrete", CONCRETE_TABLE, default="C30/37")
    fyk = r.number("materials.fyk", lo=200, hi=700, default=500)
    ductility = r.choice("materials.ductility", DUCTILITY_CLASSES, default="B")
    dg = r.number("materials.dg", lo=5, hi=63, default=20)
    gamma_c = r.number("materials.gamma_c", lo=1.0, hi=2.0, default=1.5)
    gamma_s = r.number("materials.gamma_s", lo=1.0, hi=1.5, default=1.15)
    alpha_cc = r.number("materials.alpha_cc", lo=0.8, hi=1.0, default=0.85)

    cx = r.number("column.cx", lo=100, hi=3000)
    cy = r.number("column.cy", lo=100, hi=3000)
    L = r.number("base.L", lo=0.3, hi=20)
    B = r.number("base.B", lo=0.3, hi=20)
    h = r.number("base.h", lo=150, hi=3000)
    hs = r.number("base.soil_depth", lo=0, hi=10, default=0.0)
    gamma_soil = r.number("base.gamma_soil", lo=10, hi=25, default=18.0)

    soil = r.choice("soil.type", [*PRESUMED_BEARING_BY_ID, "custom"], default="custom")
    q_allow = r.number("soil.q_allow", lo=1, hi=5000, optional=soil == "very_soft_clay")

    Gk = r.number("actions.Gk", lo=0, hi=1e5)
    Qk = r.number("actions.Qk", lo=0, hi=1e5, default=0.0)
    MGk = r.number("actions.MGk", lo=0, hi=1e5, default=0.0)
    MQk = r.number("actions.MQk", lo=0, hi=1e5, default=0.0)
    category = r.choice("actions.category", PSI_CATEGORIES, default="B")

    x_dia = r.choice("reinforcement.x_dia", BAR_SIZES, default=16)
    x_s = r.number("reinforcement.x_s", lo=50, hi=500)
    y_dia = r.choice("reinforcement.y_dia", BAR_SIZES, default=16)
    y_s = r.number("reinforcement.y_s", lo=50, hi=500)
    cover = r.number("reinforcement.cover", lo=0, hi=200, default=50)
    delta_c_dev = r.number("reinforcement.delta_c_dev", lo=0, hi=20, default=10)
    cast = r.choice("reinforcement.cast", GROUND_COVER, default="blinding")

    exposure_ids = [row["id"] for row in durability.EXPOSURE_ROWS]
    exposure = r.choice("durability.exposure", exposure_ids, default="XC2")
    cement_group = r.choice("durability.cement_group", list(durability.ROWS_BY_ID[exposure]["groups"]),
                            default=next(iter(durability.ROWS_BY_ID[exposure]["groups"])))

    if not r.errors:
        if cx >= L * 1000:
            r.errors["column.cx"] = "The column must be smaller than the base length L."
        if cy >= B * 1000:
            r.errors["column.cy"] = "The column must be smaller than the base width B."
        if Gk + Qk <= 0:
            r.errors["actions.Gk"] = "Enter the column load."
        if cover + x_dia + y_dia >= h:
            r.errors["reinforcement.cover"] = "The cover and the two layers of bars do not fit in the depth."
    if r.errors:
        raise ValidationError(r.errors)
    return FoundationInput(
        project=project, concrete=Concrete.from_class(concrete_class, gamma_c, alpha_cc),
        steel=Reinforcement(fyk, ductility, gamma_s), dg=dg, cx=cx, cy=cy, L=L * 1000, B=B * 1000, h=h,
        hs=hs * 1000, gamma_soil=gamma_soil, soil=soil, q_allow=q_allow, Gk=Gk, Qk=Qk, MGk=MGk, MQk=MQk,
        category=category, x_dia=x_dia, x_s=x_s, y_dia=y_dia, y_s=y_s, cover=cover, delta_c_dev=delta_c_dev,
        cast=cast, exposure=exposure, cement_group=cement_group)


# ---------------------------------------------------------------- pressures and actions

def pressure(N, M, L, B):
    """Linear ground pressure under a base L × B for an axial load N and a moment M along L.

    Trapezoidal when e = M/N ≤ L/6, triangular over the contact length 3(L/2 − e) when e is larger
    (no tension between the base and the ground). Returns p1 at the heavily loaded edge, p2 at the
    other edge, the contact length and at(u), the pressure at a distance u from the heavily loaded edge.
    Any consistent units: N in N and lengths in mm give N/mm².
    """
    e = M / N if N > 0 else math.inf
    if e <= L / 6:
        p_avg = N / (B * L)
        p1, p2, contact, shape = p_avg * (1 + 6 * e / L), p_avg * (1 - 6 * e / L), L, "trapezoidal"
        at = lambda u: p1 - (p1 - p2) * np.asarray(u) / L
    elif e < L / 2:
        contact = 3 * (L / 2 - e)
        p1, p2, shape = 2 * N / (3 * B * (L / 2 - e)), 0.0, "triangular"
        at = lambda u: p1 * np.clip(1 - np.asarray(u) / contact, 0, None)
    else:
        return {"e": e, "p1": math.inf, "p2": 0.0, "contact": 0.0, "shape": "overturned", "at": None}
    return {"e": e, "p1": p1, "p2": p2, "contact": contact, "shape": shape, "at": at}


def _integral(f, a, b, n=800):
    if b <= a:
        return 0.0
    u = np.linspace(a, b, n + 1)
    return float(np.trapezoid(f(u), u))


def actions_of(inp):
    """Characteristic (bearing), EQU and design (STR) actions, and the ground pressures."""
    area = inp.L * inp.B / 1e6                                        # m²
    w_base = CONCRETE_DENSITY * area * inp.h / 1000                    # kN
    w_soil = inp.gamma_soil * (area - inp.cx * inp.cy / 1e6) * inp.hs / 1000
    P = inp.Gk + inp.Qk + w_base + w_soil
    M = inp.MGk + inp.MQk
    sls = pressure(P * 1e3, M * 1e6, inp.L, inp.B)
    NEd = 1.35 * inp.Gk + 1.5 * inp.Qk
    MEd = 1.35 * inp.MGk + 1.5 * inp.MQk
    uls = pressure(NEd * 1e3, MEd * 1e6, inp.L, inp.B)
    psi2 = actions.psi_factors(inp.category)[2]
    return {"area": area, "w_base": w_base, "w_soil": w_soil, "P": P, "M": M, "sls": sls, "NEd": NEd, "MEd": MEd,
            "uls": uls, "psi2": psi2, "qp_ratio": (inp.Gk + psi2 * inp.Qk) / NEd if NEd else 1.0,
            "stab": inp.Gk + w_base + w_soil}


@dataclass
class Geometry:
    dx: float              # effective depth of the bars along L (bottom layer)
    dy: float              # of the bars along B (second layer)
    d: float               # average
    ax: float              # cantilever beyond the column face along L
    ay: float              # along B
    As_x: float            # mm²/m
    As_y: float
    As_x_total: float      # over the full width B
    As_y_total: float      # over the full length L


def geometry(inp):
    dx = inp.h - inp.cover - inp.x_dia / 2
    dy = inp.h - inp.cover - inp.x_dia - inp.y_dia / 2
    As_x = bar_area(inp.x_dia) * 1000 / inp.x_s
    As_y = bar_area(inp.y_dia) * 1000 / inp.y_s
    return Geometry(dx=dx, dy=dy, d=(dx + dy) / 2, ax=(inp.L - inp.cx) / 2, ay=(inp.B - inp.cy) / 2,
                    As_x=As_x, As_y=As_y, As_x_total=As_x * inp.B / 1000, As_y_total=As_y * inp.L / 1000)


def face_actions(inp, geo, act):
    """Design moments at the column faces and beam shears at d from them (N·mm, N)."""
    uls = act["uls"]
    out = {}
    if uls["at"] is None:
        return None
    # along L: the cantilever on the heavily loaded side
    a = geo.ax
    out["Mx"] = inp.B * _integral(lambda u: uls["at"](u) * (a - u), 0, a)
    out["Vx"] = inp.B * _integral(uls["at"], 0, a - geo.dx) if a > geo.dx else 0.0
    out["px_face"] = float(uls["at"](a))
    out["px_d"] = float(uls["at"](a - geo.dx)) if a > geo.dx else None
    # along B: the pressure only varies along L, so the load per metre run across B is NEd/B
    n_per_mm = act["NEd"] * 1e3 / inp.B
    out["My"] = n_per_mm * geo.ay**2 / 2
    out["Vy"] = n_per_mm * (geo.ay - geo.dy) if geo.ay > geo.dy else 0.0
    return out


def _perimeter_load(inp, uls, a):
    """Ground reaction inside the control perimeter at a from the column faces (rounded corners), N."""
    half = inp.cx / 2 + a

    def width(x):
        x = np.abs(x)
        corner = np.sqrt(np.clip(a**2 - (x - inp.cx / 2) ** 2, 0, None))
        return np.where(x <= inp.cx / 2, inp.cy + 2 * a, inp.cy + 2 * corner)

    # x from the base centre towards the heavily loaded edge: u = L/2 − x
    return _integral(lambda x: uls["at"](inp.L / 2 - x) * width(x), -half, half)


def punching(inp, geo, act):
    """Punching shear at the column face and on control perimeters from 0.5d to 2d."""
    uls = act["uls"]
    conc = inp.concrete
    d = geo.d
    NEd, MEd = act["NEd"] * 1e3, act["MEd"] * 1e6
    rho = min(math.sqrt(geo.As_x / (1000 * geo.dx) * geo.As_y / (1000 * geo.dy)), 0.02)
    v_c = flexure.vrd_c(conc.fck, d, rho)
    ratio = inp.cx / inp.cy
    k_beta = float(np.interp(ratio, tables.PUNCHING_K_RATIO, tables.PUNCHING_K))

    def at_distance(a):
        u = 2 * (inp.cx + inp.cy) + 2 * math.pi * a
        W = inp.cx**2 / 2 + inp.cx * inp.cy + 2 * inp.cy * a + 4 * a**2 + math.pi * a * inp.cx
        dV = _perimeter_load(inp, uls, a)
        V_red = NEd - dV
        beta = 1 + k_beta * MEd / V_red * u / W if MEd and V_red > 0 else 1.0
        v_ed = beta * V_red / (u * d) if V_red > 0 else 0.0
        v_rd = v_c * 2 * d / a
        return {"a": a, "u": u, "W": W, "dV": dV, "V_red": V_red, "beta": beta, "v_ed": v_ed, "v_rd": v_rd,
                "util": v_ed / v_rd, "inside": inp.cx + 2 * a <= inp.L and inp.cy + 2 * a <= inp.B}

    perimeters = [at_distance(f * d) for f in np.arange(0.5, 2.0001, 0.05)]
    inside = [p for p in perimeters if p["inside"]]
    critical = max(inside, key=lambda p: p["util"]) if inside else None
    basic = at_distance(2 * d)
    # at the column face: the reaction under the column itself deducted
    u0 = 2 * (inp.cx + inp.cy)
    dV0 = _integral(lambda x: uls["at"](inp.L / 2 - x) * inp.cy, -inp.cx / 2, inp.cx / 2)
    v_max = basic["beta"] * (NEd - dV0) / (u0 * d)
    nu = 0.6 * (1 - conc.fck / 250)
    v_rd_max = 0.5 * nu * conc.fck / 1.5
    return {"rho": rho, "v_c": v_c, "k": min(1 + math.sqrt(200 / d), 2.0), "k_beta": k_beta, "critical": critical,
            "basic": basic, "at_d": at_distance(d), "perimeters": perimeters, "u0": u0, "dV0": dV0, "v_max": v_max,
            "nu": nu, "v_rd_max": v_rd_max}


# ---------------------------------------------------------------- checks

def kN(n):
    return f"{n / 1e3:.1f}"


def kNm(m):
    return f"{m / 1e6:.1f}"


def kPa(p):
    return f"{p * 1e3:.1f}"


def _scope_checks(inp):
    fck, fyk = inp.concrete.fck, inp.steel.fyk
    ok_fck, ok_fyk = fck <= 50, 400 <= fyk <= 600
    return [CheckResult("scope", GROUPS[0], "Eurocode 2 scope", PASS if ok_fck and ok_fyk else FAIL,
                        result=f"fck = {fck:g} MPa, fyk = {fyk:g} MPa", utilisation=fck / 50,
                        working=[f"Concrete {inp.concrete.name}: fck = {fck:g} MPa ≤ 50 MPa"
                                 + ("" if ok_fck else " (outside the scope)"),
                                 f"Reinforcement fyk = {fyk:g} MPa, class {inp.steel.ductility}; the scope is 400–600 MPa"
                                 + ("" if ok_fyk else " (outside the scope)")])]


def _cover_checks(inp):
    dc = inp.delta_c_dev
    row = durability.ROWS_BY_ID[inp.exposure]
    res = durability.durability_cover(inp.exposure, inp.cement_group, inp.concrete.name)
    head = [f"Exposure {row['classes']}: {row['example']} (cement group: {inp.cement_group})"]
    if res["status"] != "ok":
        return [CheckResult("cover", GROUPS[1], "Durability and cover", FAIL,
                            result=f"{inp.concrete.name} below minimum {res['spec']['class']}",
                            working=head + [f"This exposure needs at least {res['spec']['class']}; "
                                            f"{inp.concrete.name} is not recommended."],
                            note="Increase the concrete strength class.", target="cover")]
    ground = GROUND_COVER[inp.cast]
    required = max(res["cover"] + dc, inp.x_dia + dc, ground)
    ok = inp.cover >= required
    lines = head + [
        f"Durability: cmin,dur + Δcdev = {res['cover']} + {dc:g} = {res['cover'] + dc:g} mm",
        f"Bond: cmin,b + Δcdev = φ of the bottom bars + Δcdev = {inp.x_dia} + {dc:g} = {inp.x_dia + dc:g} mm",
        f"Cast {'on blinding (prepared ground)' if inp.cast == 'blinding' else 'directly against the soil'}: "
        f"cnom ≥ {ground} mm",
        f"cnom,req = {required:g} mm; provided cnom = {inp.cover:g} mm",
    ]
    return [CheckResult("cover", GROUPS[1], "Durability and cover", PASS if ok else FAIL,
                        result=f"{inp.cover:g} {'≥' if ok else '<'} {required:g} mm", value=inp.cover, limit=required,
                        unit="mm", utilisation=required / max(inp.cover, 1.0), working=lines, target="cover",
                        note="" if ok else ("Increase the nominal cover." if inp.cast == "blinding"
                                            else "Increase the cover to 75 mm, or cast the base on blinding."))]


def _actions_check(inp, act):
    sls, uls = act["sls"], act["uls"]
    lines = [f"Base {inp.L / 1000:g} × {inp.B / 1000:g} m, {inp.h:g} mm deep: A = {act['area']:.2f} m²; "
             f"column {inp.cx:g} × {inp.cy:g} mm at the centre",
             f"Base own weight = 25 × {act['area']:.2f} × {inp.h / 1000:g} = {act['w_base']:.1f} kN"]
    if inp.hs:
        lines.append(f"Soil over the base = {inp.gamma_soil:g} × ({act['area']:.2f} − {inp.cx * inp.cy / 1e6:.2f}) × "
                     f"{inp.hs / 1000:g} = {act['w_soil']:.1f} kN")
    lines += [f"Characteristic (bearing): P = Gk + Qk + base + soil = {inp.Gk:g} + {inp.Qk:g} + {act['w_base']:.1f} + "
              f"{act['w_soil']:.1f} = {act['P']:.1f} kN; M = MGk + MQk = {act['M']:g} kNm; "
              f"e = M/P = {sls['e']:.0f} mm",
              f"Design (STR): NEd = 1.35 × {inp.Gk:g} + 1.5 × {inp.Qk:g} = {act['NEd']:.1f} kN; "
              f"MEd = 1.35 × {inp.MGk:g} + 1.5 × {inp.MQk:g} = {act['MEd']:.1f} kNm; e = {uls['e']:.0f} mm"]
    if uls["at"] is not None:
        lines.append(f"Net design ground pressure ({uls['shape']}): {kPa(uls['p1'])} kPa at the heavily loaded edge, "
                     f"{kPa(uls['p2'])} kPa at the other")
    return [CheckResult("actions", GROUPS[2], "Design actions", INFO,
                        result=f"P = {act['P']:.0f} kN; NEd = {act['NEd']:.0f} kN, MEd = {act['MEd']:.1f} kNm",
                        working=lines)]


def _bearing_checks(inp, act):
    sls = act["sls"]
    soil = PRESUMED_BEARING_BY_ID.get(inp.soil)
    lines = []
    if soil:
        lines.append(f"Ground: {soil['soil']}; presumed allowable bearing value {soil['range']} kPa")
    if soil and soil["value"] is None:
        lines.append("No presumed bearing value: the foundation needs a specialist geotechnical design")
        return [CheckResult("bearing", GROUPS[3], "Bearing pressure", FAIL, result="No presumed value",
                            working=lines, target="section", note="Get a site-specific bearing value from a "
                            "geotechnical engineer, or found the base on firmer ground.")]
    q = inp.q_allow
    e, L = sls["e"], inp.L
    if sls["at"] is None:
        lines.append(f"e = {e:.0f} mm ≥ L/2 = {L / 2:.0f} mm: the base overturns")
        return [CheckResult("bearing", GROUPS[3], "Bearing pressure", FAIL, result="e ≥ L/2", working=lines,
                            target="section", note="Make the base longer.")]
    p_avg = act["P"] * 1e3 / (inp.L * inp.B)
    if sls["shape"] == "trapezoidal":
        lines += [f"e = {e:.0f} mm ≤ L/6 = {L / 6:.0f} mm: trapezoidal pressure",
                  f"pmax = P/A·(1 + 6e/L) = {kPa(p_avg)} × (1 + 6 × {e:.0f}/{L:.0f}) = {kPa(sls['p1'])} kPa; "
                  f"pmin = {kPa(sls['p2'])} kPa"]
    else:
        lines += [f"e = {e:.0f} mm > L/6 = {L / 6:.0f} mm: part of the base lifts off; triangular pressure over "
                  f"3(L/2 − e) = {sls['contact']:.0f} mm",
                  f"pmax = 2P/[3B(L/2 − e)] = {kPa(sls['p1'])} kPa"]
    ok = sls["p1"] * 1e3 <= q
    lines.append(f"pmax = {kPa(sls['p1'])} kPa {'≤' if ok else '>'} allowable {q:g} kPa")
    status = PASS if ok else FAIL
    note = "" if ok else "Make the base larger."
    if ok and sls["shape"] == "triangular":
        status = WARN
        note = "e > L/6 at SLS: make sure the rotation of the base is acceptable, or lengthen it."
    return [CheckResult("bearing", GROUPS[3], "Bearing pressure", status,
                        result=f"{kPa(sls['p1'])} {'≤' if ok else '>'} {q:g} kPa", value=sls["p1"] * 1e3, limit=q,
                        unit="kPa", utilisation=sls["p1"] * 1e3 / q, working=lines, target="section", note=note)]


def _overturning_checks(inp, act):
    if not act["M"]:
        return [CheckResult("overturning", GROUPS[3], "Overturning (EQU)", NA, result="No moment",
                            working=["No moment on the base, so it cannot overturn"])]
    stab = 0.9 * act["stab"] * inp.L / 2000
    dst = 1.1 * inp.MGk + 1.5 * inp.MQk
    ok = dst <= stab
    lines = [f"Stabilising: 0.9 × (Gk + base + soil) × L/2 = 0.9 × {act['stab']:.1f} × {inp.L / 2000:g} = {stab:.1f} kNm "
             f"(about the toe; the imposed load is ignored)",
             f"Destabilising: 1.1·MGk + 1.5·MQk = 1.1 × {inp.MGk:g} + 1.5 × {inp.MQk:g} = {dst:.1f} kNm",
             f"{dst:.1f} {'≤' if ok else '>'} {stab:.1f} kNm"]
    return [CheckResult("overturning", GROUPS[3], "Overturning (EQU)", PASS if ok else FAIL,
                        result=f"{dst:.1f} {'≤' if ok else '>'} {stab:.1f} kNm", utilisation=dst / stab,
                        working=lines, target="section", note="" if ok else "Make the base longer or heavier.")]


def _bending_checks(inp, geo, act, fa):
    conc, steel = inp.concrete, inp.steel
    kp = flexure.k_prime(1.0, True)
    out, results = [], {}
    for axis, M, width, d, a, dia, s, As_m, As_total, face in (
            ("x", fa["Mx"], inp.B, geo.dx, geo.ax, inp.x_dia, inp.x_s, geo.As_x, geo.As_x_total, inp.cx),
            ("y", fa["My"], inp.L, geo.dy, geo.ay, inp.y_dia, inp.y_s, geo.As_y, geo.As_y_total, inp.cy)):
        along = "L" if axis == "x" else "B"
        title = f"Bending, bars along {along}"
        lines = []
        if axis == "x":
            uls = act["uls"]
            lines.append(f"Cantilever beyond the column face a = (L − cx)/2 = ({inp.L:.0f} − {inp.cx:g})/2 = {a:.0f} mm, "
                         f"on the heavily loaded side: pressure {kPa(uls['p1'])} kPa at the edge, "
                         f"{kPa(fa['px_face'])} kPa at the face")
            lines.append(f"MEd = B·∫p·(a − u)du = {kNm(M)} kNm over B = {inp.B / 1000:g} m")
        else:
            lines.append(f"Cantilever a = (B − cy)/2 = ({inp.B:.0f} − {inp.cy:g})/2 = {a:.0f} mm; load across B "
                         f"NEd/B = {act['NEd']:.1f}/{inp.B / 1000:g} = {act['NEd'] / inp.B * 1000:.1f} kN/m")
            lines.append(f"MEd = (NEd/B)·a²/2 = {kNm(M)} kNm over L = {inp.L / 1000:g} m")
        layer = "bottom layer" if axis == "x" else "second layer, on the bars along L"
        lines.append(f"d = h − cnom − {'φ/2' if axis == 'x' else 'φx − φ/2'} = {d:.0f} mm ({layer})")
        res = flexure.rectangular(M, width, d, 0, conc.fck, steel.fyd, kp)
        lines.append(f"K = M/(b·d²·fck) = {kNm(M)}×10⁶ / ({width:.0f} × {d:.0f}² × {conc.fck:g}) = {res['K']:.4f}; "
                     f"K′ = {kp:.3f}")
        if res["compression"]:
            lines.append("K > K′: the base is too shallow (no compression steel in a pad)")
            out.append(CheckResult(f"bending_{axis}", GROUPS[4], title, FAIL, result="Base too shallow",
                                   utilisation=res["K"] / kp, working=lines, target="section",
                                   note="Make the base deeper."))
            results[axis] = None
            continue
        need = res["As"]
        ok = As_total >= need
        lines += [f"z = d/2·[1 + √(1 − 3.53K)] ≤ 0.95d = {res['z']:.0f} mm",
                  f"As,req = M/(fyd·z) = {need:.0f} mm² ({need / width * 1000:.0f} mm²/m)",
                  f"Provided H{dia} @ {s:g} = {As_m:.0f} mm²/m × {width / 1000:g} m = {As_total:.0f} mm²"]
        out.append(CheckResult(f"bending_{axis}", GROUPS[4], title, PASS if ok else FAIL,
                               result=f"{As_total:.0f} {'≥' if ok else '<'} {need:.0f} mm²", value=As_total, limit=need,
                               unit="mm²", utilisation=need / max(As_total, 1.0), working=lines, target="bars",
                               note="" if ok else "Use larger bars or close the spacing."))
        results[axis] = res
    return out, results


def _beam_shear_checks(inp, geo, act, fa):
    conc = inp.concrete
    out = []
    for axis, V, width, d, a, As_m in (("x", fa["Vx"], inp.B, geo.dx, geo.ax, geo.As_x),
                                       ("y", fa["Vy"], inp.L, geo.dy, geo.ay, geo.As_y)):
        along = "L" if axis == "x" else "B"
        title = f"Beam shear, along {along}"
        if a <= d:
            out.append(CheckResult(f"shear_{axis}", GROUPS[5], title, NA, result="d beyond the edge",
                                   working=[f"a = {a:.0f} mm ≤ d = {d:.0f} mm: the section at d from the face is outside "
                                            "the base, so there is no beam shear"]))
            continue
        rho = min(As_m / (1000 * d), 0.02)
        v_c = flexure.vrd_c(conc.fck, d, rho)
        v_ed = V / (width * d)
        ok = v_ed <= v_c
        k = min(1 + math.sqrt(200 / d), 2.0)
        if axis == "x":
            how = (f"VEd = B·∫p du from the edge to d from the face = {kN(V)} kN "
                   f"(pressure {kPa(fa['px_d'])} kPa at d from the face)")
        else:
            how = f"VEd = (NEd/B)·(a − d) = {act['NEd'] / inp.B * 1000:.1f} × {(a - d) / 1000:.3f} = {kN(V)} kN"
        lines = [f"Section at d = {d:.0f} mm from the column face (a − d = {a - d:.0f} mm)", how,
                 f"vEd = VEd/(b·d) = {kN(V)}×10³ / ({width:.0f} × {d:.0f}) = {v_ed:.3f} MPa",
                 f"k = 1 + √(200/d) = {k:.3f}; ρl = {As_m:.0f}/(1000 × {d:.0f}) = {rho:.4f}",
                 f"vRd,c = max[0.12·k·(100·ρl·fck)^(1/3), 0.035·k^1.5·√fck] = {v_c:.3f} MPa",
                 f"vEd = {v_ed:.3f} {'≤' if ok else '>'} vRd,c = {v_c:.3f} MPa"]
        out.append(CheckResult(f"shear_{axis}", GROUPS[5], title, PASS if ok else FAIL,
                               result=f"{v_ed:.3f} {'≤' if ok else '>'} {v_c:.3f} MPa", value=v_ed, limit=v_c, unit="MPa",
                               utilisation=v_ed / v_c, working=lines, target="section",
                               note="" if ok else "Make the base deeper or add bottom steel."))
    return out


def _punching_checks(inp, geo, act, pu):
    conc = inp.concrete
    d = geo.d
    v_max, v_rd_max = pu["v_max"], pu["v_rd_max"]
    ok = v_max <= v_rd_max
    face = CheckResult(
        "punching_face", GROUPS[6], "Punching at the column face", PASS if ok else FAIL,
        result=f"{v_max:.2f} {'≤' if ok else '>'} {v_rd_max:.2f} MPa", value=v_max, limit=v_rd_max, unit="MPa",
        utilisation=v_max / v_rd_max, target="section",
        working=[f"deff = (dx + dy)/2 = ({geo.dx:.0f} + {geo.dy:.0f})/2 = {d:.0f} mm; u0 = 2(cx + cy) = {pu['u0']:.0f} mm",
                 f"Ground reaction under the column ΔVEd = {kN(pu['dV0'])} kN; β = {pu['basic']['beta']:.3f} "
                 f"(at the basic perimeter 2d)",
                 f"vEd,max = β·(VEd − ΔVEd)/(u0·deff) = {pu['basic']['beta']:.3f} × ({act['NEd']:.1f} − {kN(pu['dV0'])})×10³ / "
                 f"({pu['u0']:.0f} × {d:.0f}) = {v_max:.2f} MPa",
                 f"vRd,max = 0.5·ν·fcd, ν = 0.6(1 − fck/250) = {pu['nu']:.3f}, fcd = fck/1.5: {v_rd_max:.2f} MPa"],
        note="" if ok else "Make the column or the base bigger.")
    crit = pu["critical"]
    head = [f"deff = {d:.0f} mm; ρl = √(ρx·ρy) = {pu['rho']:.4f}; k = {pu['k']:.3f}; "
            f"vRd,c = max[0.12·k·(100·ρl·fck)^(1/3), 0.035·k^1.5·√fck] = {pu['v_c']:.3f} MPa"]
    if act["MEd"]:
        head.append(f"Moment: β = 1 + k·(MEd/VEd,red)·(u/W), k = {pu['k_beta']:.2f} for cx/cy = {inp.cx / inp.cy:.2f}; "
                    f"W = c1²/2 + c1·c2 + 2·c2·a + 4a² + π·a·c1")
    if crit is None:
        return [face, CheckResult("punching", GROUPS[6], "Punching on the control perimeters", NA,
                                  result="Perimeters outside the base",
                                  working=head + ["Every control perimeter from 0.5d to 2d falls outside the base: beam "
                                                  "shear governs"])]
    rows = []
    for p in (pu["at_d"], pu["basic"]):
        if p["inside"]:
            rows.append(p)
    if all(abs(crit["a"] - p["a"]) > 1e-6 for p in rows):
        rows.append(crit)
    rows.sort(key=lambda p: p["a"])
    lines = list(head)
    for p in rows:
        tag = " (critical)" if p is crit or abs(p["a"] - crit["a"]) < 1e-6 else ""
        lines.append(f"a = {p['a'] / d:.2f}d = {p['a']:.0f} mm{tag}: u = {p['u']:.0f} mm, ΔVEd = {kN(p['dV'])} kN, "
                     f"VEd,red = {kN(p['V_red'])} kN, β = {p['beta']:.3f}; vEd = {p['v_ed']:.3f} MPa, "
                     f"vRd = vRd,c·2d/a = {p['v_rd']:.3f} MPa")
    ok = crit["util"] <= 1
    lines.append(f"Critical perimeter at a = {crit['a']:.0f} mm: vEd = {crit['v_ed']:.3f} {'≤' if ok else '>'} "
                 f"vRd = {crit['v_rd']:.3f} MPa")
    return [face, CheckResult("punching", GROUPS[6], "Punching on the control perimeters", PASS if ok else FAIL,
                              result=f"{crit['v_ed']:.3f} {'≤' if ok else '>'} {crit['v_rd']:.3f} MPa at {crit['a'] / d:.2f}d",
                              value=crit["v_ed"], limit=crit["v_rd"], unit="MPa", utilisation=crit["util"], working=lines,
                              target="perimeter", note="" if ok else "Make the base deeper (shear links are not "
                              "recommended in foundations).")]


def _detailing_checks(inp, geo, act, res):
    conc, steel = inp.concrete, inp.steel
    out = []
    ratio_min = max(0.26 * conc.fctm / steel.fyk, 0.0013)
    for axis, d, As_m in (("x", geo.dx, geo.As_x), ("y", geo.dy, geo.As_y)):
        along = "L" if axis == "x" else "B"
        need = ratio_min * 1000 * d
        ok = As_m >= need
        out.append(CheckResult(f"as_min_{axis}", GROUPS[7], f"Minimum steel, bars along {along}", PASS if ok else FAIL,
                               result=f"{As_m:.0f} {'≥' if ok else '<'} {need:.0f} mm²/m", utilisation=need / As_m,
                               working=[f"As,min = max(0.26·fctm/fyk, 0.0013)·bt·d = max({0.26 * conc.fctm / steel.fyk:.5f}, "
                                        f"0.0013) × 1000 × {d:.0f} = {need:.0f} mm²/m"], target="bars",
                               note="" if ok else "Add bars."))
    worst = max(geo.As_x_total / (inp.B * inp.h), geo.As_y_total / (inp.L * inp.h))
    ok = worst <= 0.04
    out.append(CheckResult("as_max", GROUPS[7], "Maximum steel", PASS if ok else FAIL,
                           result=f"{100 * worst:.2f} {'≤' if ok else '>'} 4 % of Ac", utilisation=worst / 0.04,
                           working=[f"Along L: {geo.As_x_total:.0f} / ({inp.B:.0f} × {inp.h:g}) = "
                                    f"{100 * geo.As_x_total / (inp.B * inp.h):.2f} %; along B: {geo.As_y_total:.0f} / "
                                    f"({inp.L:.0f} × {inp.h:g}) = {100 * geo.As_y_total / (inp.L * inp.h):.2f} %",
                                    "As,max = 0.04·Ac outside laps"], target="bars"))
    s_min = max(inp.dg + 5, 20)
    for axis, dia, s in (("x", inp.x_dia, inp.x_s), ("y", inp.y_dia, inp.y_s)):
        along = "L" if axis == "x" else "B"
        need = max(dia, s_min)
        clear = s - dia
        ok = clear >= need
        out.append(CheckResult(f"spacing_{axis}", GROUPS[7], f"Clear spacing, bars along {along}", PASS if ok else FAIL,
                               result=f"{clear:.0f} {'≥' if ok else '<'} {need:.0f} mm", utilisation=need / clear if clear > 0 else None,
                               working=[f"H{dia} @ {s:g}: clear gap = {clear:.0f} mm; minimum = max(φ, dg + 5, 20) = {need:.0f} mm"],
                               target="bars", note="" if ok else "Use fewer, larger bars."))
    for axis, dia, s, As_total in (("x", inp.x_dia, inp.x_s, geo.As_x_total), ("y", inp.y_dia, inp.y_s, geo.As_y_total)):
        r = res.get(axis)
        if not r or r["As"] > As_total:
            continue                      # bending fails first: no service stress to check
        along = "L" if axis == "x" else "B"
        sigma = max(10.0, steel.fyd * act["qp_ratio"] * r["As"] / As_total)
        size, spacing = tables.crack_limits(sigma, 0.3)
        lines = [f"σs = fyd·(Gk + ψ2·Qk)/(1.35·Gk + 1.5·Qk)·As,req/As,prov = {steel.fyd:.1f} × {act['qp_ratio']:.3f} × "
                 f"{r['As']:.0f}/{As_total:.0f} = {sigma:.0f} MPa (ψ2 = {act['psi2']:g})"]
        if size is None:
            ok, result = False, f"σs = {sigma:.0f} > 360 MPa"
            lines.append("Steel stress above the tabulated range")
        else:
            ok = dia <= size or s <= spacing
            result = f"H{dia} @ {s:g} vs H{size:.0f} or @ {spacing:.0f}"
            lines.append(f"wmax = 0.3 mm: bar size ≤ {size:.0f} mm or spacing ≤ {spacing:.0f} mm; provided H{dia} @ {s:g} "
                         f"({'satisfied' if ok else 'neither satisfied'})")
        out.append(CheckResult(f"crack_{axis}", GROUPS[7], f"Crack control, bars along {along}", PASS if ok else FAIL,
                               result=result, working=lines, target="bars",
                               note="" if ok else "Use smaller bars at closer spacing."))
    return out


def _input_echo(inp):
    soil = PRESUMED_BEARING_BY_ID.get(inp.soil)
    rows = [("Column", f"{inp.cx:g} × {inp.cy:g} mm (cx along L)"),
            ("Base", f"L = {inp.L / 1000:g} m × B = {inp.B / 1000:g} m × h = {inp.h:g} mm"),
            ("Soil over the base", f"{inp.hs / 1000:g} m at {inp.gamma_soil:g} kN/m³" if inp.hs else "none"),
            ("Ground", (f"{soil['soil']}; " if soil else "") + (f"allowable bearing {inp.q_allow:g} kPa" if inp.q_allow else "no value")),
            ("Column loads", f"Gk = {inp.Gk:g} kN, Qk = {inp.Qk:g} kN (category {inp.category}); MGk = {inp.MGk:g} kNm, "
                             f"MQk = {inp.MQk:g} kNm"),
            ("Concrete", inp.concrete.name), ("fyk", f"{inp.steel.fyk:g} MPa (class {inp.steel.ductility})"),
            ("Bottom bars", f"along L H{inp.x_dia} @ {inp.x_s:g} (bottom layer); along B H{inp.y_dia} @ {inp.y_s:g}"),
            ("Nominal cover", f"{inp.cover:g} mm (Δcdev = {inp.delta_c_dev:g} mm), cast "
                              + ("on blinding" if inp.cast == "blinding" else "against the soil")),
            ("Exposure", f"{inp.exposure} ({inp.cement_group})")]
    return [{"label": k, "value": v} for k, v in rows]


def _plot(inp, geo, act, fa, pu):
    sls, uls = act["sls"], act["uls"]
    pick = lambda p: {"p1": p["p1"] * 1e3 if math.isfinite(p["p1"]) else None, "p2": p["p2"] * 1e3,
                      "contact": p["contact"], "shape": p["shape"], "e": p["e"] if math.isfinite(p["e"]) else None}
    crit = pu["critical"] if pu else None
    return {"shape": "pad", "L": inp.L, "B": inp.B, "h": inp.h, "cx": inp.cx, "cy": inp.cy, "hs": inp.hs,
            "cover": inp.cover, "x": {"dia": inp.x_dia, "s": inp.x_s, "As": geo.As_x},
            "y": {"dia": inp.y_dia, "s": inp.y_s, "As": geo.As_y}, "dx": geo.dx, "dy": geo.dy, "d": geo.d,
            "q_allow": inp.q_allow, "sls": pick(sls), "uls": pick(uls), "P": act["P"], "M": act["M"],
            "NEd": act["NEd"], "MEd": act["MEd"],
            "perimeter": {"a": crit["a"] if crit else None, "a_2d": 2 * geo.d, "a_d": geo.d}}


def check_foundation(data):
    inp = parse_foundation(data)
    geo = geometry(inp)
    act = actions_of(inp)
    checks = _scope_checks(inp) + _cover_checks(inp) + _actions_check(inp, act)
    checks += _bearing_checks(inp, act) + _overturning_checks(inp, act)
    fa = face_actions(inp, geo, act)
    pu, res = None, {}
    if fa is None:
        checks.append(CheckResult("bending_x", GROUPS[4], "Structural design", FAIL, result="Base overturns at ULS",
                                  working=["e = MEd/NEd ≥ L/2: no ground pressure distribution can carry the loads"],
                                  note="Make the base longer.", target="section"))
    else:
        bending, res = _bending_checks(inp, geo, act, fa)
        pu = punching(inp, geo, act)
        checks += bending + _beam_shear_checks(inp, geo, act, fa) + _punching_checks(inp, geo, act, pu)
        checks += _detailing_checks(inp, geo, act, res)
    summary = summarise(checks)
    derived = {"NEd": act["NEd"], "MEd": act["MEd"], "P": act["P"], "M": act["M"], "w_base": act["w_base"],
               "w_soil": act["w_soil"], "dx": geo.dx, "dy": geo.dy, "d": geo.d, "ax": geo.ax, "ay": geo.ay,
               "sls_p1": act["sls"]["p1"] * 1e3 if math.isfinite(act["sls"]["p1"]) else None,
               "uls_p1": act["uls"]["p1"] * 1e3 if math.isfinite(act["uls"]["p1"]) else None,
               "uls_p2": act["uls"]["p2"] * 1e3, "q_allow": inp.q_allow}
    if fa:
        derived.update(Mx=fa["Mx"] / 1e6, My=fa["My"] / 1e6, Vx=fa["Vx"] / 1e3, Vy=fa["Vy"] / 1e3,
                       As_req_x=res["x"]["As"] if res.get("x") else None, As_req_y=res["y"]["As"] if res.get("y") else None,
                       As_x=geo.As_x_total, As_y=geo.As_y_total)
    return {
        "element": "foundation",
        "project": inp.project,
        "summary": summary,
        "verdict": summary["verdict"],
        "groups": list(GROUPS),
        "checks": [c.to_dict() for c in checks],
        "inputs": _input_echo(inp),
        "assumptions": list(ASSUMPTIONS),
        "derived": derived,
        "plots": {"section": _plot(inp, geo, act, fa, pu)},
    }
