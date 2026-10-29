"""Beam check: rectangular or flanged (T or L) beams to BS EN 1992-1-1 (UK National Annex).

check_beam(data) validates a request and runs the beam procedure in order: durability and
fire, design actions, bending, shear, deflection and detailing. One section is checked per
run: mid-span (sagging) or over a support (hogging). Internally lengths are in mm, forces
in N and moments in N·mm; the report uses kN, kNm and mm.
"""
import math
from dataclasses import dataclass

from . import durability, fire, flexure, tables
from .actions import psi_factors
from .analysis import BeamAnalysis, solve_beam
from .tables import PSI_CATEGORIES
from .inputs import Reader, ValidationError
from .materials import BAR_SIZES, CONCRETE_TABLE, DUCTILITY_CLASSES, LINK_SIZES, Concrete, Reinforcement, bar_area
from .results import FAIL, INFO, NA, PASS, WARN, CheckResult, summarise

__all__ = ["check_beam", "parse_input", "ValidationError"]

GROUPS = (
    "Scope & materials",
    "Durability & cover",
    "Fire resistance",
    "Design actions",
    "Bending",
    "Shear",
    "Deflection",
    "Detailing",
)
SYSTEMS = {
    "simple": "Simply supported",
    "end": "Continuous, end span",
    "interior": "Continuous, interior span",
    "cantilever": "Cantilever",
}
DEFLECTION_K = {"simple": 1.0, "end": 1.3, "interior": 1.5, "cantilever": 0.4}
# distance between points of zero moment, l0 = factor × span (for the effective flange width)
L0_FACTOR = {"simple": 1.0, "end": 0.85, "interior": 0.70, "cantilever": 1.0}
CONCRETE_DENSITY = 25.0  # kN/m³, reinforced concrete


@dataclass
class BeamInput:
    project: dict
    concrete: Concrete
    steel: Reinforcement
    dg: float
    shape: str            # "rectangular" or "flanged"
    flange: str           # "T" (both sides) or "L" (one side)
    b: float              # width, or web width bw for a flanged beam
    h: float
    hf: float | None
    beff_method: str
    beff_input: float | None
    b1: float | None      # half the clear distance to the next web, each side
    b2: float | None
    span: float           # effective span, mm
    system: str
    location: str         # "span" (sagging) or "support" (hogging)
    n_t: int
    phi_t: int
    layers: int
    n_c: int
    phi_c: int
    link_dia: int
    legs: int
    cover: float
    delta_c_dev: float
    mode: str             # "loads" (UDL) or "direct" (MEd, VEd)
    gk: float | None      # kN/m
    qk: float | None
    self_weight: bool
    category: str
    combination: str
    m_ed: float | None    # N·mm, direct mode
    v_ed: float | None    # N
    partitions: bool
    kprime_limit: bool
    exposure: str
    cement_group: str
    fire_period: str
    analysis_loads: list | None = None
    analysis_supports: list | None = None
    analysis_inertia: list | None = None
    has_slab: bool = False
    slab_type: str = "one_way"
    slab_gk: float = 0.0
    slab_qk: float = 0.0
    slab_lx: float = 0.0
    slab_ly: float = 0.0
    slab_trib: float = 0.0


def parse_input(data):
    r = Reader(data)
    project = r.project()
    shape = r.choice("section.shape", ("rectangular", "flanged"), default="rectangular")
    flange = r.choice("section.flange", ("T", "L"), default="T")
    b = r.number("section.b", lo=100, hi=2000)
    h = r.number("section.h", lo=150, hi=3000)
    hf = beff_input = b1 = b2 = None
    beff_method = "calculate"
    if shape == "flanged":
        hf = r.number("section.hf", lo=50, hi=1000)
        beff_method = r.choice("section.beff_method", ("calculate", "enter"), default="calculate")
        if beff_method == "enter":
            beff_input = r.number("section.beff", lo=100, hi=20000)
        else:
            b1 = r.number("section.b1", lo=0, hi=20000)
            b2 = r.number("section.b2", lo=0, hi=20000) if flange == "T" else 0.0

    concrete_class = r.choice("materials.concrete", CONCRETE_TABLE)
    fyk = r.number("materials.fyk", lo=200, hi=700)
    ductility = r.choice("materials.ductility", DUCTILITY_CLASSES, default="B")
    dg = r.number("materials.dg", lo=5, hi=63, default=20)
    gamma_c = r.number("materials.gamma_c", lo=1.0, hi=2.0, default=1.5)
    gamma_s = r.number("materials.gamma_s", lo=1.0, hi=1.5, default=1.15)
    alpha_cc = r.number("materials.alpha_cc", lo=0.8, hi=1.0, default=0.85)

    span = r.number("span.l", lo=0.5, hi=30)
    system = r.choice("span.system", SYSTEMS, default="simple")
    location = r.choice("span.location", ("span", "support"),
                        default="support" if system == "cantilever" else "span")
    if system == "simple" and location == "support":
        r.errors["span.location"] = "A simply supported beam has no support moment; check mid-span."
    if system == "cantilever" and location == "span":
        r.errors["span.location"] = "A cantilever is checked at its support."

    n_t = r.number("reinforcement.tension_n", lo=2, hi=20, integer=True)
    phi_t = r.choice("reinforcement.tension_dia", BAR_SIZES, default=20)
    layers = r.number("reinforcement.layers", lo=1, hi=2, integer=True, default=1)
    n_c = r.number("reinforcement.compression_n", lo=2, hi=20, integer=True)
    phi_c = r.choice("reinforcement.compression_dia", BAR_SIZES, default=12)
    link_dia = r.choice("reinforcement.link_dia", LINK_SIZES, default=8)
    legs = r.number("reinforcement.legs", lo=2, hi=6, integer=True, default=2)
    cover = r.number("reinforcement.cover", lo=0, hi=150)
    delta_c_dev = r.number("reinforcement.delta_c_dev", lo=0, hi=20, default=10)

    mode = r.choice("actions.mode", ("loads", "direct", "analysis"), default="loads")
    gk = qk = m_ed = v_ed = None
    category, combination = "B", "6.10ab"
    analysis_loads = []
    analysis_supports = None
    analysis_inertia = None
    if mode == "loads":
        gk = r.number("actions.gk", lo=0, hi=10000)
        qk = r.number("actions.qk", lo=0, hi=10000)
        category = r.choice("actions.category", PSI_CATEGORIES, default="B")
        combination = r.choice("actions.combination", ("6.10ab", "6.10"), default="6.10ab")
    elif mode == "analysis":
        raw_loads = r.raw("actions.loads")
        if isinstance(raw_loads, list):
            for ld in raw_loads:
                if not isinstance(ld, dict):
                    continue
                ltype = ld.get("type", "point")
                if ltype == "point":
                    w_val = float(ld.get("W", ld.get("w", 0.0)) or 0.0)
                    x_val = float(ld.get("x", ld.get("l1", 0.0)) or 0.0)
                    if w_val != 0.0:
                        analysis_loads.append({"type": "point", "W": abs(w_val), "x": max(0.0, min(x_val, span))})
                elif ltype == "udl":
                    w_val = float(ld.get("w", ld.get("W", 0.0)) or 0.0)
                    l1_val = float(ld.get("l1", 0.0) or 0.0)
                    l2_val = float(ld.get("l2", span) or span)
                    if w_val != 0.0:
                        analysis_loads.append({
                            "type": "udl",
                            "w": abs(w_val),
                            "l1": max(0.0, min(l1_val, span)),
                            "l2": max(0.0, min(l2_val, span))
                        })
                elif ltype == "moment":
                    m_val = float(ld.get("M0", ld.get("m", 0.0)) or 0.0)
                    x_val = float(ld.get("x", ld.get("l1", 0.0)) or 0.0)
                    if m_val != 0.0:
                        analysis_loads.append({"type": "moment", "M0": m_val, "x": max(0.0, min(x_val, span))})
                elif ltype == "linear":
                    w1 = float(ld.get("w1", 0.0) or 0.0)
                    w2 = float(ld.get("w2", 0.0) or 0.0)
                    l1_val = float(ld.get("l1", 0.0) or 0.0)
                    l2_val = float(ld.get("l2", span) or span)
                    if w1 != 0.0 or w2 != 0.0:
                        analysis_loads.append({
                            "type": "linear",
                            "w1": abs(w1),
                            "w2": abs(w2),
                            "l1": max(0.0, min(l1_val, span)),
                            "l2": max(0.0, min(l2_val, span))
                        })
        raw_supps = r.raw("actions.supports")
        if isinstance(raw_supps, list) and len(raw_supps) > 0:
            analysis_supports = [
                {"x": float(sp["x"]), "fix_v": int(sp.get("fix_v", 1)), "fix_m": int(sp.get("fix_m", 0))}
                for sp in raw_supps if isinstance(sp, dict) and "x" in sp
            ]
        raw_in = r.raw("actions.inertia")
        if isinstance(raw_in, list) and len(raw_in) > 0:
            analysis_inertia = [
                {"x1": float(it.get("x1", 0.0)), "x2": float(it.get("x2", span)), "I": float(it["I"])}
                for it in raw_in if isinstance(it, dict) and "I" in it
            ]
    else:
        m_ed = r.number("actions.MEd", lo=0.001, hi=1e6)
        v_ed = r.number("actions.VEd", lo=0, hi=1e6)
    self_weight = r.flag("actions.self_weight", default=True)
    has_slab = r.flag("actions.has_slab", default=False)
    slab_type = r.choice("actions.slab_type", ("one_way", "two_way_long", "two_way_short"), default="one_way")
    slab_gk = r.number("actions.slab_gk", lo=0, hi=1000, default=0.0) if has_slab else 0.0
    slab_qk = r.number("actions.slab_qk", lo=0, hi=1000, default=0.0) if has_slab else 0.0
    slab_lx = r.number("actions.slab_lx", lo=0, hi=100, default=0.0) if has_slab else 0.0
    slab_ly = r.number("actions.slab_ly", lo=0, hi=100, default=0.0) if has_slab else 0.0
    slab_trib = r.number("actions.slab_trib", lo=0, hi=100, default=0.0) if has_slab else 0.0
    partitions = r.flag("actions.partitions")
    kprime_limit = r.flag("actions.kprime_limit", default=True)

    exposure_ids = [row["id"] for row in durability.EXPOSURE_ROWS]
    exposure = r.choice("durability.exposure", exposure_ids, default="XC1")
    cement_group = r.choice("durability.cement_group", list(durability.ROWS_BY_ID[exposure]["groups"]),
                            default=next(iter(durability.ROWS_BY_ID[exposure]["groups"])))
    fire_period = r.choice("durability.fire_period", fire.FIRE_PERIODS, default="none")

    if not r.errors:
        if shape == "flanged" and hf >= h:
            r.errors["section.hf"] = "The flange must be thinner than the overall depth."
        if beff_input is not None and beff_input < b:
            r.errors["section.beff"] = "The effective flange width cannot be less than the web width."
        per_layer = math.ceil(n_t / layers)
        room = b - 2 * (cover + link_dia)
        if per_layer * phi_t > room:
            r.errors["reinforcement.tension_n"] = (f"{per_layer} bars of {phi_t} mm do not fit in one layer "
                                                   f"({room:.0f} mm between the links).")
        if n_c * phi_c > room:
            r.errors["reinforcement.compression_n"] = "These bars do not fit between the links."
    if r.errors:
        raise ValidationError(r.errors)

    return BeamInput(
        project=project, concrete=Concrete.from_class(concrete_class, gamma_c, alpha_cc),
        steel=Reinforcement(fyk, ductility, gamma_s), dg=dg, shape=shape, flange=flange, b=b, h=h, hf=hf,
        beff_method=beff_method, beff_input=beff_input, b1=b1, b2=b2, span=span * 1000.0, system=system,
        location=location, n_t=n_t, phi_t=phi_t, layers=layers, n_c=n_c, phi_c=phi_c, link_dia=link_dia,
        legs=legs, cover=cover, delta_c_dev=delta_c_dev, mode=mode, gk=gk, qk=qk, self_weight=self_weight,
        category=category, combination=combination,
        m_ed=None if m_ed is None else m_ed * 1e6, v_ed=None if v_ed is None else v_ed * 1e3,
        partitions=partitions, kprime_limit=kprime_limit, exposure=exposure, cement_group=cement_group,
        fire_period=fire_period, analysis_loads=analysis_loads,
        analysis_supports=analysis_supports, analysis_inertia=analysis_inertia,
        has_slab=has_slab, slab_type=slab_type, slab_gk=slab_gk, slab_qk=slab_qk,
        slab_lx=slab_lx, slab_ly=slab_ly, slab_trib=slab_trib,
    )


# ---------------------------------------------------------------- formatting

def kN(n):
    return f"{n / 1e3:.1f}"


def kNm(m):
    return f"{m / 1e6:.1f}"


def _cmp(ok):
    return "≤" if ok else ">"


def _spread(lo, hi, n):
    return [0.5 * (lo + hi)] if n == 1 else [lo + (hi - lo) * i / (n - 1) for i in range(n)]


# ---------------------------------------------------------------- geometry

@dataclass
class Geometry:
    beff: float           # effective flange width (= b for a rectangular beam)
    l0: float
    beff_parts: list      # [(b_i, beff_i)] for the working
    d: float
    d2: float
    a_tension: float      # centroid of the tension bars from the tension face
    a_bottom: float       # axis distance of the bottom bars (fire)
    As: float
    As2: float
    per_layer: int
    clear: float          # clear gap between tension bars in a layer
    pitch: float          # centre-to-centre spacing of tension bars in a layer
    layer_gap: float      # clear vertical gap between two layers
    Ac: float
    bars: list


def geometry(inp):
    sec_face = inp.cover + inp.link_dia
    a1 = sec_face + inp.phi_t / 2
    per_layer = math.ceil(inp.n_t / inp.layers)
    second = inp.n_t - per_layer
    layer_gap = max(inp.phi_t, inp.dg + 5, 20)
    a2 = a1 + inp.phi_t + layer_gap
    a_tension = (per_layer * a1 + second * a2) / inp.n_t
    d = inp.h - a_tension
    d2 = sec_face + inp.phi_c / 2
    width = inp.b - 2 * sec_face
    pitch = (width - inp.phi_t) / (per_layer - 1) if per_layer > 1 else 0.0
    clear = pitch - inp.phi_t if per_layer > 1 else width - inp.phi_t

    l0 = L0_FACTOR[inp.system] * inp.span
    parts = []
    if inp.shape == "rectangular":
        beff = inp.b
    elif inp.beff_method == "enter":
        beff = inp.beff_input
    else:
        beff = inp.b
        for bi in ([inp.b1, inp.b2] if inp.flange == "T" else [inp.b1]):
            part = min(0.2 * bi + 0.1 * l0, 0.2 * l0, bi)
            parts.append((bi, part))
            beff += part
    Ac = inp.b * inp.h + ((beff - inp.b) * inp.hf if inp.shape == "flanged" else 0.0)

    tension_top = inp.location == "support"
    y = (lambda dist: inp.h - dist) if tension_top else (lambda dist: dist)
    yc = (lambda dist: dist) if tension_top else (lambda dist: inp.h - dist)
    lo, hi = -inp.b / 2 + sec_face + inp.phi_t / 2, inp.b / 2 - sec_face - inp.phi_t / 2
    bars = [{"x": x, "y": y(a1), "dia": inp.phi_t, "kind": "tension"} for x in _spread(lo, hi, per_layer)]
    bars += [{"x": x, "y": y(a2), "dia": inp.phi_t, "kind": "tension"} for x in _spread(lo, hi, second)] if second else []
    clo, chi = -inp.b / 2 + sec_face + inp.phi_c / 2, inp.b / 2 - sec_face - inp.phi_c / 2
    bars += [{"x": x, "y": yc(d2), "dia": inp.phi_c, "kind": "compression"} for x in _spread(clo, chi, inp.n_c)]
    return Geometry(beff=beff, l0=l0, beff_parts=parts, d=d, d2=d2, a_tension=a_tension,
                    a_bottom=d2 if tension_top else a_tension,
                    As=inp.n_t * bar_area(inp.phi_t), As2=inp.n_c * bar_area(inp.phi_c), per_layer=per_layer,
                    clear=clear, pitch=pitch, layer_gap=layer_gap, Ac=Ac, bars=bars)


# ---------------------------------------------------------------- design actions

def design_actions(inp, geo):
    """MEd and VEd at the section checked, with the loads behind them (kN, m)."""
    l = inp.span / 1000
    out = {"l": l, "mode": inp.mode, "delta": 1.0}
    continuous = inp.system in ("end", "interior")
    if continuous and inp.location == "support":
        out["delta"] = 0.85          # the support coefficients include 15 % redistribution
    if inp.mode == "direct":
        out.update(MEd=inp.m_ed, VEd=inp.v_ed, w=None, qp_ratio=None)
        return out
    area = inp.b * (inp.h - (inp.hf or 0)) if inp.shape == "flanged" else inp.b * inp.h
    sw = CONCRETE_DENSITY * area / 1e6 if inp.self_weight else 0.0

    # Slab load calculation if slab is placed on top of beam
    slab_info = None
    w_slab_moment = 0.0
    w_slab_shear = 0.0
    if inp.has_slab:
        w_slab_area = 1.35 * (inp.slab_gk or 0.0) + 1.5 * (inp.slab_qk or 0.0)
        lx = inp.slab_lx if inp.slab_lx and inp.slab_lx > 0 else l
        ly = inp.slab_ly if inp.slab_ly and inp.slab_ly > 0 else l
        if inp.slab_type == "one_way":
            b_trib = inp.slab_trib if inp.slab_trib and inp.slab_trib > 0 else (inp.slab_lx / 2.0 if inp.slab_lx and inp.slab_lx > 0 else l / 2.0)
            w_slab_moment = w_slab_area * b_trib
            w_slab_shear = w_slab_area * b_trib
            slab_desc = f"One-way slab (tributary width btrib = {b_trib:.2f} m): w = wslab × btrib"
        elif inp.slab_type == "two_way_long":
            r_ratio = min(1.0, max(0.01, lx / ly))
            w_slab_moment = w_slab_area * (lx / 6.0) * (3.0 - r_ratio**2)
            w_slab_shear = w_slab_area * (lx / 4.0) * (2.0 - r_ratio)
            slab_desc = f"Two-way slab on long beam Ly={ly:.2f} m (Lx={lx:.2f} m): weq,moment = wslab × (Lx/6)·[3 - (Lx/Ly)²], weq,shear = wslab × (Lx/4)·[2 - Lx/Ly]"
        else:  # two_way_short
            w_slab_moment = w_slab_area * (lx / 3.0)
            w_slab_shear = w_slab_area * (lx / 4.0)
            slab_desc = f"Two-way slab on short beam Lx={lx:.2f} m: weq,moment = wslab × (Lx/3), weq,shear = wslab × (Lx/4)"
        slab_info = {
            "w_slab_area": w_slab_area,
            "w_slab_moment": w_slab_moment,
            "w_slab_shear": w_slab_shear,
            "desc": slab_desc,
            "type": inp.slab_type,
            "lx": lx,
            "ly": ly
        }

    if inp.mode == "analysis":
        E_kpa = inp.concrete.Ecm * 1e6
        b_m = inp.b / 1000.0
        h_m = inp.h / 1000.0
        if inp.shape == "rectangular":
            I_m4 = b_m * h_m**3 / 12.0
        else:
            hf_m = (inp.hf or 0.0) / 1000.0
            beff_m = geo.beff / 1000.0
            bw_m = b_m
            hw_m = h_m - hf_m
            Af = beff_m * hf_m
            Aw = bw_m * hw_m
            Atot = Af + Aw
            if Atot > 0:
                y_bar = (Af * (h_m - hf_m / 2.0) + Aw * (hw_m / 2.0)) / Atot
                I_m4 = ((beff_m * hf_m**3 / 12.0 + Af * (h_m - hf_m / 2.0 - y_bar)**2) +
                        (bw_m * hw_m**3 / 12.0 + Aw * (hw_m / 2.0 - y_bar)**2))
            else:
                I_m4 = b_m * h_m**3 / 12.0

        sw_uls = 1.35 * sw if inp.self_weight else 0.0
        loads_to_solve = list(inp.analysis_loads or [])
        if inp.has_slab and w_slab_moment > 0:
            loads_to_solve.append({"type": "udl", "w": w_slab_moment, "l1": 0.0, "l2": l})

        analysis_res = solve_beam(
            span_m=l,
            system=inp.system,
            loads=loads_to_solve,
            supports=inp.analysis_supports,
            E_kpa=E_kpa,
            I_m4=inp.analysis_inertia or I_m4,
            self_weight=sw_uls
        )

        if inp.location == "support":
            m_kNm = abs(analysis_res["max_hogging_kNm"]) if analysis_res["max_hogging_kNm"] < 0 else analysis_res["abs_max_M_kNm"]
        else:
            m_kNm = analysis_res["max_sagging_kNm"] if analysis_res["max_sagging_kNm"] > 0 else analysis_res["abs_max_M_kNm"]
        v_kN = analysis_res["abs_max_V_kN"]

        # Ensure that if non-zero M and V were obtained from analysis, we use them
        if m_kNm == 0.0 and analysis_res["abs_max_M_kNm"] > 0:
            m_kNm = analysis_res["abs_max_M_kNm"]
        if v_kN == 0.0 and analysis_res["abs_max_V_kN"] > 0:
            v_kN = analysis_res["abs_max_V_kN"]

        out.update(
            sw=sw, sw_uls=sw_uls, MEd=m_kNm * 1e6, VEd=v_kN * 1e3, w=w_slab_moment if inp.has_slab else None,
            qp_ratio=None, analysis_res=analysis_res, E_kpa=E_kpa, I_m4=I_m4, slab_info=slab_info
        )
        return out
    gk = (inp.gk or 0.0) + sw
    psi0, _, psi2 = psi_factors(inp.category)
    # Eurocode combination: strictly G = 1.35 gk and Q = 1.5 qk (0.925 factor removed)
    G = 1.35 * gk
    Q = 1.5 * (inp.qk or 0.0)
    governing = "6.10"
    w = G + Q + w_slab_moment
    w_shear = G + Q + w_slab_shear
    if inp.system == "simple":
        m, v, how = w * l**2 / 8, w_shear * l / 2, ("M = w·l²/8", "V = w·l/2")
    elif inp.system == "cantilever":
        m, v, how = w * l**2 / 2, w_shear * l, ("M = w·l²/2", "V = w·l")
    elif inp.location == "span":
        cg, cq = tables.BEAM_SPAN_MOMENT[inp.system]
        m, how_m = (cg * G + cq * Q + cg * w_slab_moment) * l**2, f"M = ({cg:.3f}·G + {cq:.3f}·Q)·l²"
        cv = tables.BEAM_SUPPORT_SHEAR[inp.system]
        v, how = cv * w_shear * l, (how_m, f"V = {cv:.2f}·w·l")
    else:
        cm = tables.BEAM_SUPPORT_MOMENT[inp.system]
        cv = tables.BEAM_SUPPORT_SHEAR[inp.system]
        m, v, how = cm * w * l**2, cv * w_shear * l, (f"M = {cm:.3f}·w·l²", f"V = {cv:.2f}·w·l")
    out.update(sw=sw, gk=gk, qk=inp.qk or 0.0, G=G, Q=Q, w=w, governing=governing, psi0=psi0, psi2=psi2,
               MEd=m * 1e6, VEd=v * 1e3, how=how, qp_ratio=(gk + psi2 * (inp.qk or 0.0)) / w if w else 0.0,
               slab_info=slab_info)
    return out


def _actions_checks(inp, geo, act):
    out = []
    if act["mode"] == "direct":
        out.append(CheckResult(
            "actions", GROUPS[3], "Design actions", INFO, result=f"MEd = {kNm(act['MEd'])} kNm, VEd = {kN(act['VEd'])} kN",
            working=[f"Entered from the analysis: MEd = {kNm(act['MEd'])} kNm "
                     f"({'hogging' if inp.location == 'support' else 'sagging'}), VEd = {kN(act['VEd'])} kN"]))
        return out
    if act["mode"] == "analysis":
        ares = act["analysis_res"]
        lines = [
            f"Span l = {act['l']:.2f} m, {SYSTEMS[inp.system].lower()}",
            f"Matrix Stiffness FEA: {ares['analysis'].num_nodes} nodes, {ares['analysis'].num_elements} elements",
            f"Gross concrete section: E = {act['E_kpa']/1e6:.1f} GPa, I = {act['I_m4']:.6f} m⁴"
        ]
        if inp.self_weight:
            what = "web below the flange" if inp.shape == "flanged" else "beam"
            lines.append(f"Self-weight of the {what} = {CONCRETE_DENSITY:g} × {inp.b:g} × "
                         f"{inp.h - (inp.hf or 0):g}/10⁶ = {act['sw']:.2f} kN/m")
            lines.append(f"Factored self-weight (ULS γG = 1.35) = {act['sw_uls']:.2f} kN/m")
        if inp.analysis_loads:
            ld_strs = []
            for ld in inp.analysis_loads:
                t = ld["type"]
                if t == "point":
                    ld_strs.append(f"Point load W = {ld['W']:.1f} kN at x = {ld['x']:.2f} m")
                elif t == "udl":
                    ld_strs.append(f"UDL w = {ld['w']:.1f} kN/m from x = {ld['l1']:.2f} to {ld['l2']:.2f} m")
                elif t == "moment":
                    ld_strs.append(f"Moment M0 = {ld['M0']:.1f} kNm at x = {ld['x']:.2f} m")
                elif t == "linear":
                    ld_strs.append(f"Varying load w = {ld['w1']:.1f} → {ld['w2']:.1f} kN/m from x = {ld['l1']:.2f} to {ld['l2']:.2f} m")
            lines.append("Applied loads: " + "; ".join(ld_strs))

        lines.append(f"Peak sagging moment = {ares['max_sagging_kNm']:.1f} kNm, peak hogging = {ares['max_hogging_kNm']:.1f} kNm")
        lines.append(f"Governing design actions: MEd = {kNm(act['MEd'])} kNm "
                     f"({'hogging' if inp.location == 'support' else 'sagging'}), VEd = {kN(act['VEd'])} kN")
        lines.append(f"Maximum calculated elastic deflection δmax = {ares['max_deflection_mm']:.2f} mm")

        r_strs = [f"Node {r['node']} ({r['x']:.2f} m): Ry = {abs(r['Ry']):.1f} kN" +
                  (f", M = {abs(r['M']):.1f} kNm" if abs(r["M"]) > 0.05 else "") for r in ares["reactions"]]
        lines.append("Support reactions: " + ", ".join(r_strs))

        out.append(CheckResult(
            "actions", GROUPS[3], "Design actions (Matrix Analysis)", INFO,
            result=f"MEd = {kNm(act['MEd'])} kNm, VEd = {kN(act['VEd'])} kN, δmax = {ares['max_deflection_mm']:.2f} mm",
            working=lines
        ))
        return out
    lines = [f"Span l = {act['l']:.2f} m, {SYSTEMS[inp.system].lower()}"]
    if inp.self_weight:
        what = "web below the flange" if inp.shape == "flanged" else "beam"
        lines.append(f"Self-weight of the {what} = {CONCRETE_DENSITY:g} × {inp.b:g} × "
                     f"{inp.h - (inp.hf or 0):g}/10⁶ = {act['sw']:.2f} kN/m")
    sw_text = f" + {act['sw']:.2f}" if inp.self_weight else ""
    lines += [f"gk = {inp.gk:g}{sw_text} = {act['gk']:.2f} kN/m, "
              f"qk = {inp.qk:g} kN/m, ψ0 = {act['psi0']:g}, ψ2 = {act['psi2']:g}"]
    if act.get("slab_info"):
        si = act["slab_info"]
        lines.append(f"Slab load transfer: {si['desc']}")
        lines.append(f"Slab area design load (ULS): wslab = 1.35·gk,slab + 1.5·qk,slab = {si['w_slab_area']:.2f} kN/m²")
        lines.append(f"Equivalent UDL from slab: weq,moment = {si['w_slab_moment']:.2f} kN/m, weq,shear = {si['w_slab_shear']:.2f} kN/m")
    lines.append(f"G = 1.35·gk = {act['G']:.2f}, Q = 1.5·qk = {act['Q']:.2f} kN/m")
    slab_w_str = f" + {act['slab_info']['w_slab_moment']:.2f} (slab)" if act.get("slab_info") else ""
    lines += [f"w = G + Q{slab_w_str} = {act['w']:.2f} kN/m",
              f"{act['how'][0]} = {kNm(act['MEd'])} kNm ({'hogging' if inp.location == 'support' else 'sagging'})",
              f"{act['how'][1]} = {kN(act['VEd'])} kN"]
    out.append(CheckResult("actions", GROUPS[3], "Design actions", INFO,
                           result=f"MEd = {kNm(act['MEd'])} kNm, VEd = {kN(act['VEd'])} kN", working=lines))
    if inp.system in ("end", "interior"):
        ok = inp.qk <= act["gk"]
        out.append(CheckResult(
            "coefficients", GROUPS[3], "Conditions for the moment coefficients", PASS if ok else WARN,
            result="Qk ≤ Gk" if ok else "Qk > Gk",
            working=[f"qk = {inp.qk:g} {'≤' if ok else '>'} gk = {act['gk']:.2f} kN/m",
                     "Also assumed: three or more spans, shortest span at least 0.85 × the longest, "
                     "uniformly distributed loads"],
            note="" if ok else "The coefficients are not valid; use moments from a frame analysis instead."))
    return out


# ---------------------------------------------------------------- checks

def _scope_checks(inp):
    conc, steel = inp.concrete, inp.steel
    ok = 400 <= steel.fyk <= 600
    k_req, eps_req = DUCTILITY_CLASSES[steel.ductility]
    return [CheckResult(
        "scope", GROUPS[0], "Materials within scope", PASS if ok else FAIL,
        result=f"{conc.name}, fyk = {steel.fyk:g} MPa",
        working=[f"Concrete {conc.name}: fck = {conc.fck:g} MPa ≤ 50 MPa (classes up to C50/60)",
                 f"fcd = αcc·fck/γc = {conc.alpha_cc:g} × {conc.fck:g} / {conc.gamma_c:g} = {conc.fcd:.2f} MPa",
                 f"fyd = fyk/γs = {steel.fyk:g} / {steel.gamma_s:g} = {steel.fyd:.1f} MPa",
                 f"Ductility class {steel.ductility}: k {k_req}, εuk {eps_req} %"],
        note="" if ok else "Eurocode 2 gives no rules for plain or mild-steel bars; the results are indicative only.",
        target="section")]


def _cover_checks(inp):
    conc, dc = inp.concrete, inp.delta_c_dev
    row = durability.ROWS_BY_ID[inp.exposure]
    res = durability.durability_cover(inp.exposure, inp.cement_group, conc.name)
    head = [f"Exposure {row['classes']}: {row['example']} (cement group: {inp.cement_group})"]
    if res["status"] == "ok":
        spec = res["spec"]
        required = res["cover"] + dc
        ok = inp.cover >= required
        mix = f"max w/c {spec['wc']:.2f}, min cement {spec['cement']} kg/m³" + (
            f" or {spec['designated']}" if spec["designated"] else "") + (f" ({spec['notes']})" if spec["notes"] else "")
        dur = CheckResult(
            "cover_durability", GROUPS[1], "Cover for durability", PASS if ok else FAIL,
            result=f"{inp.cover:g} {'≥' if ok else '<'} {required:g} mm", value=inp.cover, limit=required, unit="mm",
            utilisation=required / inp.cover if inp.cover else math.inf,
            working=head + [f"{conc.name} needs a nominal cover of {res['cover']} + Δcdev for this exposure",
                            f"cnom,req = {res['cover']} + {dc:g} = {required:g} mm; provided cnom = {inp.cover:g} mm",
                            f"Specify concrete with {mix}"],
            note=row.get("note", ""), target="cover")
    else:
        dur = CheckResult(
            "cover_durability", GROUPS[1], "Cover for durability", FAIL,
            result=f"{conc.name} below minimum {res['spec']['class']}",
            working=head + [f"This exposure needs at least {res['spec']['class']} (with {res['cover']} + Δcdev cover); "
                            f"{conc.name} is not recommended."],
            note="Increase the concrete strength class.", target="cover")
    extra = 5 if inp.dg > 32 else 0
    req_link = max(inp.link_dia + extra, 10) + dc
    ok_link = inp.cover >= req_link
    bond = CheckResult(
        "cover_bond", GROUPS[1], "Cover for bond (links)", PASS if ok_link else FAIL,
        result=f"{inp.cover:g} {'≥' if ok_link else '<'} {req_link:g} mm", value=inp.cover, limit=req_link, unit="mm",
        utilisation=req_link / inp.cover if inp.cover else math.inf,
        working=[f"cmin,b = φlink{' + 5' if extra else ''} = {inp.link_dia + extra:g} mm; absolute minimum 10 mm",
                 f"cnom ≥ max({inp.link_dia + extra:g}, 10) + Δcdev = {req_link:g} mm; provided {inp.cover:g} mm"],
        target="cover")
    phi = max(inp.phi_t, inp.phi_c)
    c_main = inp.cover + inp.link_dia
    req_main = phi + extra + dc
    ok_main = c_main >= req_main
    main = CheckResult(
        "cover_main", GROUPS[1], "Cover to main bars", PASS if ok_main else FAIL,
        result=f"{c_main:g} {'≥' if ok_main else '<'} {req_main:g} mm", value=c_main, limit=req_main, unit="mm",
        utilisation=req_main / c_main,
        working=[f"Cover to main bars = cnom + φlink = {inp.cover:g} + {inp.link_dia} = {c_main:g} mm",
                 f"Required ≥ φ + Δcdev = {phi}{' + 5' if extra else ''} + {dc:g} = {req_main:g} mm"],
        target="cover")
    return [dur, bond, main]


def _fire_checks(inp, geo):
    if inp.fire_period == "none":
        return [CheckResult("fire", GROUPS[2], "Fire resistance", NA, result="Not required",
                            note="No fire resistance period specified.", target="cover")]
    support = "continuous" if inp.system in ("end", "interior") else "simple"
    ok, gov, evaluated = fire.check_beam_fire(inp.fire_period, support, inp.b, geo.a_bottom)
    kind = {"continuous": "continuous beam", "simple": "simply supported beam"}[support]
    if inp.system == "cantilever":
        kind = "cantilever, taken as a simply supported beam"
    lines = [f"{inp.fire_period}, {kind} exposed on three sides",
             f"Axis distance of the bottom bars a = {geo.a_bottom:.0f} mm; web width b = {inp.b:g} mm"]
    lines += [f"Option bmin/a = {o['b_min']}/{o['a']}: {'satisfied' if o['ok'] else 'not satisfied'}" for o in evaluated]
    return [CheckResult(
        "fire", GROUPS[2], f"Fire resistance {inp.fire_period}", PASS if ok else FAIL,
        result=f"{inp.b:g}/{geo.a_bottom:.0f} vs {gov['b_min']}/{gov['a']} mm",
        utilisation=max(gov["b_min"] / inp.b, gov["a"] / geo.a_bottom), working=lines, target="cover",
        note="Corner bars in a single layer also need a side axis distance of a + 10 mm."
        if ok else "Widen the web or increase the axis distance (larger cover).")]


def _bending(inp, geo, act):
    conc, steel = inp.concrete, inp.steel
    kp = flexure.k_prime(act["delta"], inp.kprime_limit)
    sagging_flange = inp.shape == "flanged" and inp.location == "span"
    M, d = act["MEd"], geo.d
    if sagging_flange:
        res = flexure.flanged(M, geo.beff, inp.b, inp.hf, d, conc.fck, steel.fyd, kp)
        width = geo.beff
    else:
        res = flexure.rectangular(M, inp.b, d, geo.d2, conc.fck, steel.fyd, kp)
        width = inp.b
    res["width"] = width
    return res


def _bending_checks(inp, geo, act, res):
    conc, steel = inp.concrete, inp.steel
    M, d = act["MEd"], geo.d
    out = []
    layer_text = (f"; two layers, centroid {geo.a_tension:.0f} mm from the tension face" if inp.layers == 2 else "")
    lines = [f"d = h − cnom − φlink − φ/2{' − layer offset' if inp.layers == 2 else ''} = {d:.0f} mm{layer_text}"]
    if inp.shape == "flanged" and inp.location == "span":
        if inp.beff_method == "enter":
            lines.append(f"beff = {geo.beff:.0f} mm (entered)")
        else:
            lines.append(f"l0 = {L0_FACTOR[inp.system]:g} × l = {geo.l0:.0f} mm")
            for i, (bi, part) in enumerate(geo.beff_parts, start=1):
                lines.append(f"beff,{i} = min(0.2·b{i} + 0.1·l0, 0.2·l0, b{i}) = min({0.2 * bi + 0.1 * geo.l0:.0f}, "
                             f"{0.2 * geo.l0:.0f}, {bi:g}) = {part:.0f} mm")
            lines.append(f"beff = bw + Σ beff,i = {geo.beff:.0f} mm")
    delta_note = " (δ = 0.85: support moments include 15 % redistribution)" if act["delta"] < 1 else ""
    raw_kp = flexure.k_prime(act["delta"], uk_limit=False)
    kp_text = (f"{raw_kp:.3f}, limited to {res['kp']:.3f} for a ductile failure" if res["kp"] < raw_kp
               else f"{res['kp']:.3f}")
    lines += [f"K = M/(b·d²·fck) = {kNm(M)}×10⁶ / ({res['width']:.0f} × {d:.0f}² × {conc.fck:g}) = {res['K']:.4f}",
              f"K′ = 0.60δ − 0.18δ² − 0.21 = {kp_text}{delta_note}"]
    if "z" in res and res.get("in_flange", True) and not res.get("compression"):
        lines += [f"z = d/2·[1 + √(1 − 3.53K)] ≤ 0.95d = {res['z']:.0f} mm",
                  f"x = 2.5(d − z) = {res['x']:.0f} mm"]
    if inp.shape == "flanged" and inp.location == "span":
        if res.get("in_flange"):
            lines.append(f"x = {res['x']:.0f} ≤ 1.25·hf = {1.25 * inp.hf:.0f} mm: neutral axis in the flange, "
                         f"designed as a rectangle of width beff")
        else:
            lines += [f"Neutral axis in the web: MR,f = 0.57·fck·(beff − bw)·hf·(d − 0.5hf) = {kNm(res['MRf'])} kNm",
                      f"Kf = (M − MR,f)/(fck·bw·d²) = {res['Kf']:.4f} {'≤' if res['ok'] else '>'} K′ = {res['kp']:.3f}"]
            if res["ok"] and res.get("z_web"):
                lines.append(f"z = d/2·[1 + √(1 − 3.53Kf)] = {res['z_web']:.0f} mm")
    elif res.get("compression"):
        if res["ok"]:
            lines += [f"K > K′: compression reinforcement needed; z = d/2·[1 + √(1 − 3.53K′)] = {res['z']:.0f} mm",
                      f"x = 2.5(d − z) = {res['x']:.0f} mm; fsc = 700·(x − d2)/x ≤ fyd = {res['fsc']:.0f} MPa"]
        else:
            lines.append("K > K′ and the compression bars lie below the neutral axis: compression steel cannot help")
    summary = ("compression reinforcement needed" if res.get("compression")
               else "no compression reinforcement needed")
    out.append(CheckResult("bending_design", GROUPS[4], "Bending design", INFO if res["ok"] else FAIL,
                           result=f"K = {res['K']:.3f} {'≤' if res['K'] <= res['kp'] else '>'} K′ = {res['kp']:.3f}",
                           working=lines + [f"So {summary}"] if res["ok"] else lines,
                           note="" if res["ok"] else "Redesign the section: it is too small for this moment.",
                           target="section"))
    if not res["ok"]:
        out.append(CheckResult("tension", GROUPS[4], "Tension reinforcement", FAIL, result="Section too small",
                               note="Increase the depth or the width of the section.", target="bars"))
        out.append(CheckResult("compression", GROUPS[4], "Compression reinforcement", NA, result="Not assessed"))
        return out

    as_req, ok = res["As"], geo.As >= res["As"]
    if inp.shape == "flanged" and inp.location == "span" and not res.get("in_flange"):
        how = (f"As = MR,f/(fyd·(d − 0.5hf)) + (M − MR,f)/(fyd·z) = {as_req:.0f} mm²")
    elif res.get("compression"):
        how = f"As = K′·fck·b·d²/(fyd·z) + As2·fsc/fyd = {as_req:.0f} mm²"
    else:
        how = f"As = M/(fyd·z) = {kNm(M)}×10⁶ / ({steel.fyd:.1f} × {res['z']:.0f}) = {as_req:.0f} mm²"
    where = "top" if inp.location == "support" else "bottom"
    out.append(CheckResult(
        "tension", GROUPS[4], "Tension reinforcement", PASS if ok else FAIL,
        result=f"{geo.As:.0f} {'≥' if ok else '<'} {as_req:.0f} mm²", value=geo.As, limit=as_req, unit="mm²",
        utilisation=as_req / geo.As,
        working=[how, f"Provided {inp.n_t}H{inp.phi_t} ({where}) = {geo.As:.0f} mm²"], target="bars",
        note="" if ok else "Add bars or use larger bars."))
    if res.get("compression"):
        ok2 = geo.As2 >= res["As2"]
        out.append(CheckResult(
            "compression", GROUPS[4], "Compression reinforcement", PASS if ok2 else FAIL,
            result=f"{geo.As2:.0f} {'≥' if ok2 else '<'} {res['As2']:.0f} mm²", value=geo.As2, limit=res["As2"],
            unit="mm²", utilisation=res["As2"] / geo.As2,
            working=[f"As2 = (K − K′)·fck·b·d²/(fsc·(d − d2)) = {res['As2']:.0f} mm² (d2 = {geo.d2:.0f} mm)",
                     f"Provided {inp.n_c}H{inp.phi_c} = {geo.As2:.0f} mm²"], target="bars"))
    else:
        out.append(CheckResult(
            "compression", GROUPS[4], "Compression reinforcement", NA, result="Not needed (K ≤ K′)",
            working=[f"K ≤ K′; the {inp.n_c}H{inp.phi_c} bars act as hangers for the links"]))
    return out


def _shear_checks(inp, geo, act, res):
    conc, steel = inp.concrete, inp.steel
    d, bw = geo.d, inp.b
    z = 0.9 * d
    v_ed = act["VEd"] / (bw * z)
    cot, v25, v10 = flexure.vertical_shear(v_ed, conc.fck)
    fywd = steel.fyd
    out = []
    lines = [f"vEd = VEd/(bw·z) = {kN(act['VEd'])}×10³ / ({bw:g} × 0.9 × {d:.0f}) = {v_ed:.2f} MPa",
             f"vRd,max = 0.4·fck·(1 − fck/250)/(cot θ + tan θ): {v25:.2f} MPa at cot θ = 2.5, {v10:.2f} MPa at cot θ = 1.0"]
    if cot is None:
        out.append(CheckResult("strut", GROUPS[5], "Concrete strut capacity", FAIL,
                               result=f"vEd {v_ed:.2f} > vRd,max {v10:.2f} MPa", utilisation=v_ed / v10,
                               working=lines, note="Increase the web width or the concrete class.", target="section"))
        out.append(CheckResult("links", GROUPS[5], "Shear links (calculated)", NA, result="Not assessed"))
        return out, None
    if cot == 2.5:
        lines.append(f"vEd ≤ vRd,max at cot θ = 2.5, so θ = 21.8° (cot θ = 2.5)")
    else:
        lines.append(f"θ = 0.5·sin⁻¹[vEd/(0.20·fck·(1 − fck/250))] = {math.degrees(math.atan(1 / cot)):.1f}°, "
                     f"cot θ = {cot:.2f}")
    out.append(CheckResult("strut", GROUPS[5], "Concrete strut capacity", PASS,
                           result=f"vEd {v_ed:.2f} ≤ vRd,max {v10:.2f} MPa", value=v_ed, limit=v10, unit="MPa",
                           utilisation=v_ed / v10, working=lines, target="section"))

    asw = inp.legs * bar_area(inp.link_dia)
    need = v_ed * bw / (fywd * cot)                      # mm²/mm
    rho_min = flexure.rho_w_min(conc.fck, steel.fyk)
    least = rho_min * bw
    s_max = 0.75 * d
    s_calc = min(asw / max(need, least), s_max)
    s_near = int(s_calc // 25 * 25)
    s_far = int(min(asw / least, s_max) // 25 * 25)
    v_rd_far = asw / s_far * z * fywd * 2.5 if s_far > 0 else 0.0
    links = {"dia": inp.link_dia, "legs": inp.legs, "near": s_near, "far": s_far, "VRd_far": v_rd_far / 1e3,
             "s_max": s_max}
    status = INFO if s_near >= 75 else WARN if s_near >= 50 else FAIL
    out.append(CheckResult(
        "links", GROUPS[5], "Shear links (calculated)", status,
        result=f"H{inp.link_dia} ({inp.legs} legs) @ {s_near} mm, {s_far} mm elsewhere",
        value=s_near, unit="mm",
        working=[f"Asw/s ≥ vEd·bw/(fywd·cot θ) = {v_ed:.2f} × {bw:g} / ({fywd:.1f} × {cot:.2f}) = {need:.3f} mm²/mm",
                 f"Minimum Asw/s = ρw,min·bw = 0.08·√fck/fyk·bw = {rho_min * 1000:.3f}×10⁻³ × {bw:g} = {least:.3f} mm²/mm",
                 f"Asw = {inp.legs} × π × {inp.link_dia}²/4 = {asw:.0f} mm²",
                 f"s ≤ Asw/(Asw/s) = {asw / max(need, least):.0f} mm and s ≤ sl,max = 0.75·d = {s_max:.0f} mm",
                 f"Provide H{inp.link_dia} links ({inp.legs} legs) at {s_near} mm near the supports (multiple of 25 mm)",
                 f"Elsewhere minimum links at {s_far} mm, enough where VEd ≤ Asw/s·z·fywd·cot θ = {v_rd_far / 1e3:.0f} kN"],
        note="" if status == INFO else "Links are very close; use more legs or a larger link diameter.",
        target="links"))
    leg_pitch = (bw - 2 * inp.cover - inp.link_dia) / (inp.legs - 1)
    st_max = min(0.75 * d, 600)
    ok = leg_pitch <= st_max
    out.append(CheckResult(
        "leg_spacing", GROUPS[5], "Spacing of link legs across the web", PASS if ok else FAIL,
        result=f"{leg_pitch:.0f} {_cmp(ok)} {st_max:.0f} mm", value=leg_pitch, limit=st_max, unit="mm",
        utilisation=leg_pitch / st_max,
        working=[f"Leg spacing = (bw − 2·cnom − φlink)/(legs − 1) = {leg_pitch:.0f} mm",
                 f"st,max = 0.75·d ≤ 600 mm = {st_max:.0f} mm"],
        note="" if ok else "Use more legs.", target="links"))

    if inp.shape == "flanged" and inp.location == "span":
        out.append(_longitudinal_shear(inp, geo, act, res))
    return out, links


def _longitudinal_shear(inp, geo, act, res):
    conc, steel = inp.concrete, inp.steel
    dx = geo.l0 / 4
    z = res["z"] if res.get("in_flange") else geo.d - 0.5 * inp.hf
    outstand = (geo.beff - inp.b) / 2 if inp.flange == "T" else geo.beff - inp.b
    delta_f = 0.75 * act["MEd"] / z * outstand / geo.beff
    v = delta_f / (inp.hf * dx)
    fctd = 0.7 * conc.fctm / conc.gamma_c
    v_max = 0.16 * conc.fck * (1 - conc.fck / 250)
    lines = [f"Δx = half the distance from zero to maximum moment = l0/4 = {dx:.0f} mm",
             f"ΔFd = (0.75·M/z)·(outstand/beff) = (0.75 × {kNm(act['MEd'])}×10⁶ / {z:.0f}) × "
             f"({outstand:.0f}/{geo.beff:.0f}) = {delta_f / 1e3:.1f} kN",
             f"vEd = ΔFd/(hf·Δx) = {v:.2f} MPa"]
    if v <= 0.4 * fctd:
        lines.append(f"vEd ≤ 0.4·fctd = 0.4 × 0.7·fctm/γc = {0.4 * fctd:.2f} MPa: no transverse steel needed "
                     f"beyond that for bending")
        return CheckResult("long_shear", GROUPS[5], "Longitudinal shear in the flange", PASS,
                           result=f"vEd {v:.2f} ≤ {0.4 * fctd:.2f} MPa", utilisation=v / v_max, working=lines,
                           target="section")
    if v <= v_max:
        cot = 2.0
        lines.append(f"vRd,max = 0.16·fck·(1 − fck/250) = {v_max:.2f} MPa at cot θf = 2.0 (flange in compression)")
    else:
        lim = 0.20 * conc.fck * (1 - conc.fck / 250)
        if v > lim:
            lines.append(f"vEd > {lim:.2f} MPa, the strut capacity at cot θf = 1.0")
            return CheckResult("long_shear", GROUPS[5], "Longitudinal shear in the flange", FAIL,
                               result=f"vEd {v:.2f} > {lim:.2f} MPa", utilisation=v / lim, working=lines,
                               note="Thicken the flange.", target="section")
        theta = 0.5 * math.asin(v / lim)
        cot = 1 / math.tan(theta)
        lines.append(f"θf = 0.5·sin⁻¹[vEd/(0.2·fck·(1 − fck/250))] = {math.degrees(theta):.1f}°")
    asf = v * inp.hf / (steel.fyd * cot) * 1000
    lines.append(f"Asf/sf = vEd·hf/(fyd·cot θf) = {asf:.0f} mm²/m of transverse steel in the flange")
    return CheckResult("long_shear", GROUPS[5], "Longitudinal shear in the flange", PASS,
                       result=f"Transverse steel ≥ {asf:.0f} mm²/m", utilisation=v / v_max if v <= v_max else None,
                       working=lines, note="The slab reinforcement across the beam may provide this.",
                       target="section")


def _steel_stress(inp, act, res, geo):
    """Service stress in the tension steel, used for deflection and crack control."""
    ratio = res["As"] / geo.As
    if act["qp_ratio"] is None or act["qp_ratio"] <= 0:
        return 310 * ratio, [f"σs ≈ 310·As,req/As,prov = 310 × {res['As']:.0f}/{geo.As:.0f} = {310 * ratio:.0f} MPa "
                             f"(loads not given)"]
    su = inp.steel.fyd * act["qp_ratio"]
    s = max(10.0, su * ratio / act["delta"])
    return s, [f"σsu = fyd·(gk + ψ2·qk)/w = {inp.steel.fyd:.1f} × ({act['gk']:.2f} + {act['psi2']:g} × {act['qk']:g})"
               f" / {act['w']:.2f} = {su:.0f} MPa",
               f"σs = σsu·(As,req/As,prov)/δ = {su:.0f} × {res['As']:.0f}/{geo.As:.0f} / {act['delta']:g} = {s:.0f} MPa"]


def _deflection_checks(inp, geo, act, res):
    if inp.location == "support" and inp.system != "cantilever":
        return [CheckResult("deflection", GROUPS[6], "Span to depth ratio", NA, result="Checked at mid-span",
                            note="Deflection is checked with the mid-span reinforcement.")]
    if not res["ok"]:
        return [CheckResult("deflection", GROUPS[6], "Span to depth ratio", NA, result="Not assessed")]
    conc, d = inp.concrete, geo.d
    flange_comp = inp.shape == "flanged" and inp.location == "span"
    area = geo.beff * inp.hf + inp.b * (d - inp.hf) if flange_comp else inp.b * d
    rho = res["As"] / area
    rho_c = res["As2"] / area
    K = DEFLECTION_K[inp.system]
    basic = flexure.basic_span_depth(K, conc.fck, rho, rho_c)
    rho0 = math.sqrt(conc.fck) / 1000
    f1 = max(0.8, 1 - 0.1 * (geo.beff / inp.b - 1)) if flange_comp else 1.0
    l_m = inp.span / 1000
    f2 = 7 / l_m if inp.partitions and l_m > 7 and inp.system != "cantilever" else 1.0
    sigma, sigma_lines = _steel_stress(inp, act, res, geo)
    f3 = min(310 / sigma, 1.5)
    allowed = basic * f1 * f2 * f3
    actual = inp.span / d
    ok = actual <= allowed
    lines = [f"ρ = As,req/{'(beff·hf + bw·(d − hf))' if flange_comp else '(b·d)'} = {100 * rho:.3f} %, "
             f"ρ′ = {100 * rho_c:.3f} %, ρ0 = √fck/1000 = {100 * rho0:.3f} %",
             f"K = {K:g} ({SYSTEMS[inp.system].lower()})",
             (f"ρ ≤ ρ0: basic l/d = K·[11 + 1.5√fck·ρ0/ρ + 3.2√fck·(ρ0/ρ − 1)^1.5] = {basic:.1f}" if rho <= rho0 else
              f"ρ > ρ0: basic l/d = K·[11 + 1.5√fck·ρ0/(ρ − ρ′) + √fck·√(ρ′/ρ0)/12] = {basic:.1f}")]
    if flange_comp:
        lines.append(f"F1 = 1 − 0.1·(beff/bw − 1) ≥ 0.8 = {f1:.2f}")
    if f2 < 1:
        lines.append(f"F2 = 7/leff = 7/{l_m:.2f} = {f2:.2f} (span over 7 m carrying brittle partitions)")
    lines += sigma_lines + [f"F3 = 310/σs ≤ 1.5 = {f3:.2f}",
                            f"Allowable l/d = {basic:.1f} × {f1:.2f} × {f2:.2f} × {f3:.2f} = {allowed:.1f}",
                            f"Actual l/d = {inp.span:.0f}/{d:.0f} = {actual:.1f}"]
    out = [CheckResult("deflection", GROUPS[6], "Span to depth ratio", PASS if ok else FAIL,
                       result=f"l/d {actual:.1f} {_cmp(ok)} {allowed:.1f}", value=actual, limit=allowed,
                       utilisation=actual / allowed, working=lines, target="section",
                       note="" if ok else "Increase the depth or add tension reinforcement.")]
    if act.get("analysis_res"):
        d_calc = act["analysis_res"]["max_deflection_mm"]
        d_lim = inp.span / (500.0 if inp.partitions else 250.0)
        lim_label = "span/500" if inp.partitions else "span/250"
        ok_d = d_calc <= d_lim
        out.append(CheckResult(
            "fea_deflection", GROUPS[6], f"Calculated deflection ({lim_label})", PASS if ok_d else FAIL,
            result=f"δ = {d_calc:.2f} mm {_cmp(ok_d)} {d_lim:.1f} mm ({lim_label})",
            value=d_calc, limit=d_lim, unit="mm", utilisation=d_calc / d_lim if d_lim > 0 else None,
            working=[
                f"Maximum deflection from Matrix Stiffness Analysis: δmax = {d_calc:.2f} mm",
                f"Allowable limit {lim_label} = {inp.span:.0f}/{(500 if inp.partitions else 250)} = {d_lim:.1f} mm",
                "Deflection satisfies serviceability limit" if ok_d else "Calculated deflection exceeds allowable limit"
            ],
            target="elevation"
        ))
    return out


def _detailing_checks(inp, geo, act, res):
    conc, steel = inp.concrete, inp.steel
    out = []
    bt = geo.beff if (inp.shape == "flanged" and inp.location == "support") else inp.b
    as_min = max(0.26 * conc.fctm / steel.fyk * bt * geo.d, 0.0013 * bt * geo.d)
    ok = geo.As >= as_min
    out.append(CheckResult(
        "as_min", GROUPS[7], "Minimum tension reinforcement", PASS if ok else FAIL,
        result=f"{geo.As:.0f} {'≥' if ok else '<'} {as_min:.0f} mm²", value=geo.As, limit=as_min, unit="mm²",
        utilisation=as_min / geo.As,
        working=[f"As,min = 0.26·fctm·bt·d/fyk ≥ 0.0013·bt·d = max({0.26 * conc.fctm / steel.fyk * bt * geo.d:.0f}, "
                 f"{0.0013 * bt * geo.d:.0f}) = {as_min:.0f} mm² (bt = {bt:.0f} mm)"], target="bars"))
    as_max = 0.04 * geo.Ac
    total = geo.As + geo.As2
    ok = total <= as_max
    out.append(CheckResult(
        "as_max", GROUPS[7], "Maximum reinforcement", PASS if ok else FAIL,
        result=f"{total:.0f} {_cmp(ok)} {as_max:.0f} mm²", value=total, limit=as_max, unit="mm²",
        utilisation=total / as_max,
        working=[f"As,max = 0.04·Ac = 0.04 × {geo.Ac:.0f} = {as_max:.0f} mm² (tension + compression bars)"],
        target="bars"))
    s_min = max(inp.phi_t, inp.dg + 5, 20)
    ok = geo.clear >= s_min
    out.append(CheckResult(
        "bar_spacing", GROUPS[7], "Clear spacing between bars", PASS if ok else FAIL,
        result=f"{geo.clear:.0f} {'≥' if ok else '<'} {s_min:.0f} mm", value=geo.clear, limit=s_min, unit="mm",
        utilisation=s_min / geo.clear if geo.clear > 0 else math.inf,
        working=[f"{geo.per_layer} bars in a layer: clear gap = {geo.clear:.0f} mm",
                 f"Minimum = max(φ, dg + 5, 20) = max({inp.phi_t}, {inp.dg + 5:g}, 20) = {s_min:.0f} mm"]
        + ([f"Vertical gap between the two layers = {geo.layer_gap:.0f} mm"] if inp.layers == 2 else []),
        target="bars"))
    if res["ok"]:
        w_max = 0.4 if inp.exposure in ("XC1",) else 0.3
        sigma, sigma_lines = _steel_stress(inp, act, res, geo)
        size, spacing = tables.crack_limits(sigma, w_max)
        if size is None:
            ok, result, tail = False, f"σs = {sigma:.0f} > 360 MPa", ["Steel stress above the tabulated range"]
        else:
            ok = inp.phi_t <= size or (geo.per_layer > 1 and geo.pitch <= spacing)
            result = (f"φ{inp.phi_t} ≤ {size:.0f} mm" if inp.phi_t <= size
                      else f"spacing {geo.pitch:.0f} {_cmp(geo.pitch <= spacing)} {spacing:.0f} mm")
            tail = [f"wmax = {w_max} mm: maximum bar size {size:.0f} mm or maximum spacing {spacing:.0f} mm",
                    f"Provided φ{inp.phi_t} at {geo.pitch:.0f} mm centres: "
                    f"{'satisfied' if ok else 'neither limit is met'}"]
        out.append(CheckResult(
            "cracking", GROUPS[7], "Crack control (bar size or spacing)", PASS if ok else FAIL, result=result,
            working=sigma_lines + tail, target="bars",
            note="" if ok else "Use smaller bars at closer spacing, or add reinforcement to lower the stress."))
    return out


def _input_echo(inp, geo):
    rows = [("Section", "Rectangular" if inp.shape == "rectangular" else
             f"Flanged ({'T' if inp.flange == 'T' else 'L'}): beff = {geo.beff:.0f} mm, hf = {inp.hf:g} mm"),
            ("Width × depth", f"{inp.b:g} × {inp.h:g} mm" + (" (web)" if inp.shape == "flanged" else "")),
            ("Concrete", inp.concrete.name), ("fyk", f"{inp.steel.fyk:g} MPa (class {inp.steel.ductility})"),
            ("Span", f"{inp.span / 1000:g} m, {SYSTEMS[inp.system].lower()}"),
            ("Section checked", "Over the support (hogging)" if inp.location == "support" else "Mid-span (sagging)"),
            ("Tension bars", f"{inp.n_t}H{inp.phi_t} in {inp.layers} layer{'s' if inp.layers > 1 else ''}"),
            ("Compression bars", f"{inp.n_c}H{inp.phi_c}"),
            ("Links", f"H{inp.link_dia}, {inp.legs} legs (spacing calculated)"),
            ("Nominal cover", f"{inp.cover:g} mm (Δcdev = {inp.delta_c_dev:g} mm)")]
    if inp.mode == "loads":
        rows.append(("Loads", f"gk = {inp.gk:g} kN/m{' + self-weight' if inp.self_weight else ''}, qk = {inp.qk:g} kN/m "
                              f"(category {inp.category}), combination {'6.10' if inp.combination == '6.10' else '6.10a/b'}"))
    elif inp.mode == "analysis":
        n_ld = len(inp.analysis_loads) if inp.analysis_loads else 0
        rows.append(("Loading method", f"Matrix Stiffness FEA ({n_ld} load{'s' if n_ld != 1 else ''}"
                                       f"{' + self-weight' if inp.self_weight else ''})"))
    else:
        rows.append(("Design actions", f"MEd = {kNm(inp.m_ed)} kNm, VEd = {kN(inp.v_ed)} kN"))
    rows += [("Exposure", f"{durability.ROWS_BY_ID[inp.exposure]['classes']} ({inp.cement_group})"),
             ("Fire", "None" if inp.fire_period == "none" else inp.fire_period)]
    return [{"label": k, "value": v} for k, v in rows]


def _diagrams(inp, act):
    """Bending moment and shear along the span (kNm, kN) for the elevation drawing."""
    l = inp.span / 1000
    m_d, v_d = act["MEd"] / 1e6, act["VEd"] / 1e3
    if act.get("analysis_res"):
        ares = act["analysis_res"]
        x_design = (0.0 if inp.system == "cantilever" else l) if inp.location == "support" else 0.5 * l
        return {
            "x": ares["x"], "M": ares["M"], "V": ares["V"], "delta": ares["delta_mm"],
            "reactions": ares["reactions"], "member_forces": ares["member_forces"],
            "key_points": ares["key_points"], "x_design": x_design, "MEd": m_d, "VEd": v_d,
            "w": act["w"], "system": inp.system, "location": inp.location, "l": l,
            "mode": "analysis"
        }
    pts = [i / 40 for i in range(41)]
    if inp.system == "cantilever":
        M = [-m_d * (1 - t) ** 2 for t in pts]
        V = [v_d * (1 - t) for t in pts]
        x_design = 0.0
    elif inp.system == "simple":
        M = [4 * m_d * t * (1 - t) for t in pts]
        V = [v_d * (1 - 2 * t) for t in pts]
        x_design = 0.5
    else:
        if act["w"] is not None:
            w = act["w"]
            span_m = (tables.BEAM_SPAN_MOMENT[inp.system][0] * act["G"]
                      + tables.BEAM_SPAN_MOMENT[inp.system][1] * act["Q"]) * l**2
            sup = tables.BEAM_SUPPORT_MOMENT[inp.system] * w * l**2
        else:  # direct: keep the shape of the coefficients, scaled to the value given
            ratio = tables.BEAM_SUPPORT_MOMENT[inp.system] / sum(tables.BEAM_SPAN_MOMENT[inp.system]) * 2
            span_m, sup = (m_d, m_d * ratio) if inp.location == "span" else (m_d / ratio, m_d)
        left = 0.0 if inp.system == "end" else -sup
        M = [left * (1 - t) * (1 - 2 * t) + 4 * span_m * t * (1 - t) - sup * t * (2 * t - 1) for t in pts]
        V = [v_d * (0.45 / 0.63 * (1 - t) - t) if inp.system == "end" else v_d * (1 - 2 * t) for t in pts]
        x_design = 0.5 if inp.location == "span" else 1.0
    return {"x": [t * l for t in pts], "M": M, "V": V, "x_design": x_design * l, "MEd": m_d, "VEd": v_d,
            "w": act["w"], "system": inp.system, "location": inp.location, "l": l}


ASSUMPTIONS = [
    "Design to BS EN 1992-1-1 with UK National Annex values; rectangular stress block for concrete up to C50/60.",
    "Shear by the variable strut inclination method with vertical links (cot θ = 2.5 where possible).",
    "Deflection by span to effective depth ratios; the service steel stress is estimated from the "
    "quasi-permanent load (or taken as 310 MPa when only design actions are given).",
    "Crack widths limited to 0.3 mm (0.4 mm in exposure XC1) through the bar size or bar spacing.",
    "Durability covers follow BS 8500 for a 50-year working life and 20 mm maximum aggregate.",
    "Fire resistance by the tabulated method of BS EN 1992-1-2 for beams exposed on three sides.",
]


def check_beam(data):
    inp = parse_input(data)
    geo = geometry(inp)
    act = design_actions(inp, geo)
    res = _bending(inp, geo, act)
    checks = _scope_checks(inp) + _cover_checks(inp) + _fire_checks(inp, geo) + _actions_checks(inp, geo, act)
    checks += _bending_checks(inp, geo, act, res)
    shear, links = _shear_checks(inp, geo, act, res)
    checks += shear + _deflection_checks(inp, geo, act, res) + _detailing_checks(inp, geo, act, res)
    assumptions = list(ASSUMPTIONS)
    if inp.system in ("end", "interior") and inp.mode == "loads":
        assumptions.insert(1, "Moments and shears of continuous beams from coefficients for three or more spans of "
                              "similar length with Qk ≤ Gk; support moments include 15 % redistribution.")
    derived = {
        "shape": inp.shape, "flange": inp.flange, "system": inp.system, "location": inp.location,
        "d": geo.d, "d2": geo.d2, "beff": geo.beff, "l0": geo.l0, "As": geo.As, "As2": geo.As2,
        "As_req": res["As"] if res["ok"] else None, "As2_req": res["As2"] if res["ok"] else None,
        "K": res["K"], "kp": res["kp"], "z": res.get("z"), "MEd": act["MEd"] / 1e6, "VEd": act["VEd"] / 1e3,
        "w": act["w"], "links": links, "l": inp.span, "mode": inp.mode,
    }
    if act.get("analysis_res"):
        ares = act["analysis_res"]
        derived.update(
            reactions=ares["reactions"],
            displacements=ares["displacements"],
            member_forces=ares["member_forces"],
            max_deflection_mm=ares["max_deflection_mm"],
            key_points=ares["key_points"],
            analysis_res={
                "abs_max_M_kNm": ares["abs_max_M_kNm"],
                "abs_max_V_kN": ares["abs_max_V_kN"],
                "max_sagging_kNm": ares["max_sagging_kNm"],
                "max_hogging_kNm": ares["max_hogging_kNm"],
                "max_deflection_mm": ares["max_deflection_mm"],
            }
        )
    return {
        "element": "beam",
        "project": inp.project,
        "summary": summarise(checks),
        "groups": list(GROUPS),
        "checks": [c.to_dict() for c in checks],
        "inputs": _input_echo(inp, geo),
        "assumptions": assumptions,
        "derived": derived,
        "plots": {
            "section": {"shape": inp.shape, "flange": inp.flange, "b": inp.b, "h": inp.h, "hf": inp.hf,
                        "beff": geo.beff, "cover": inp.cover, "link_dia": inp.link_dia, "legs": inp.legs,
                        "tension_face": "top" if inp.location == "support" else "bottom", "bars": geo.bars},
            "elevation": _diagrams(inp, act),
        },
    }
