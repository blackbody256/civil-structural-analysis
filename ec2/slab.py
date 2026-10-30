"""Slab check: solid one-way and two-way slabs to BS EN 1992-1-1 (UK National Annex).

Checks solid reinforced concrete slabs per metre width (b = 1000 mm).
Follows "How to Design Concrete Structures using Eurocode 2" (The Concrete Centre).
"""
import copy
import math
from dataclasses import dataclass

from . import durability, fire, flexure, tables
from .actions import psi_factors
from .analysis import SUPPORT_TYPES, AnalysisError, analyse
from .beam import DEFLECTION_K, SPAN_KINDS, SUPPORT_NAMES, Span, spans_of
from .inputs import Reader, ValidationError
from .materials import BAR_SIZES, CONCRETE_TABLE, DUCTILITY_CLASSES, Concrete, Reinforcement, bar_area
from .results import FAIL, INFO, NA, PASS, WARN, CheckResult, summarise
from .tables import PSI_CATEGORIES

__all__ = ["check_slab", "analyse_input", "parse_input", "ValidationError", "GROUPS", "ASSUMPTIONS"]

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

CONCRETE_DENSITY = 25.0  # kN/m³, reinforced concrete
GAMMA_G, GAMMA_Q = 1.35, 1.5
LOAD_TYPES = ("point", "udl", "linear", "moment")
LOAD_CASES = {"Ed": "design value", "G": "permanent", "Q": "variable"}
ULS = {"Ed": 1.0, "G": GAMMA_G, "Q": GAMMA_Q}

ASSUMPTIONS = [
    "Design to BS EN 1992-1-1 with UK National Annex values; rectangular stress block for concrete up to C50/60.",
    "Design loads G = 1.35·gk and Q = 1.5·qk per metre width. Further loads entered as design values are used as they are.",
    "Linear elastic analysis per metre width; moments, shears, reactions and deflections without redistribution (δ = 1.0).",
    "Continuous one-way slabs use pattern loading (Case A: all spans loaded; Case B/C: alternate spans loaded) to obtain the envelope.",
    "Two-way slabs supported on four edges use tabulated bending moment coefficients for restrained panels.",
    "Shear resistance of slabs without shear reinforcement (vRd,c) to EC2 Cl 6.2.2. No shear links in slabs.",
    "No compression reinforcement in slabs (K ≤ K'). Deflection by span-to-effective-depth ratio.",
    "Durability covers follow BS 8500 for a 50-year working life and 20 mm maximum aggregate.",
    "Fire resistance by the tabulated method of BS EN 1992-1-2 for solid slabs.",
]


@dataclass
class BarLayer:
    dia: int | None
    spacing: float | None

    @property
    def As(self) -> float:
        """Area in mm²/m width."""
        if not self.dia or self.dia == "none" or not self.spacing or self.spacing <= 0:
            return 0.0
        return (math.pi * float(self.dia) ** 2 / 4.0) * 1000.0 / float(self.spacing)

    @property
    def label(self) -> str:
        if not self.dia or self.dia == "none" or not self.spacing:
            return "None"
        return f"H{self.dia} @ {self.spacing:g}"


@dataclass
class SlabInput:
    project: dict
    slab_type: str  # "one_way" or "two_way"
    h: float        # mm
    concrete: Concrete
    steel: Reinforcement
    dg: float
    # One-way span:
    length: float | None
    supports: list
    preset: str
    # Two-way panel:
    lx: float | None
    ly: float | None
    edges: dict | None  # {"top": ..., "bottom": ..., "left": ..., "right": ...}
    # Reinforcement:
    bottom_x: BarLayer
    bottom_y: BarLayer
    top_x: BarLayer
    top_y: BarLayer
    cover: float
    delta_c_dev: float
    # Actions:
    mode: str  # "analysis" or "direct"
    gk: float
    qk: float
    self_weight: bool
    category: str
    loads: list
    pattern: bool
    partitions: bool
    m_sag: float | None  # N·mm/m (direct)
    m_hog: float | None  # N·mm/m (direct)
    v_ed: float | None   # N/m (direct)
    # Stiffness:
    E_gpa: float | None
    # Durability & fire:
    exposure: str
    cement_group: str
    fire_period: str


def _upgrade(data):
    if not isinstance(data, dict):
        return {}
    d = copy.deepcopy(data)
    d.setdefault("project", {})
    d.setdefault("slab", {})
    d.setdefault("materials", {})
    d.setdefault("reinforcement", {})
    d.setdefault("actions", {})
    d.setdefault("stiffness", {})
    d.setdefault("durability", {})
    return d


def _read_loads(r, length):
    raw = r.raw("actions.loads")
    if not isinstance(raw, list) or not length:
        return []
    loads = []
    for i, _ in enumerate(raw):
        t = r.choice(f"actions.loads.{i}.type", LOAD_TYPES, default="point")
        case = r.choice(f"actions.loads.{i}.case", tuple(LOAD_CASES), default="G")
        if t == "point":
            p = r.number(f"actions.loads.{i}.P", lo=-1e6, hi=1e6)
            if p is None:
                p = r.number(f"actions.loads.{i}.W", lo=-1e6, hi=1e6)
            x = r.number(f"actions.loads.{i}.x", lo=0, hi=length)
            if p is not None and x is not None:
                loads.append({"type": "point", "P": p, "x": x, "case": case})
        elif t == "udl":
            w = r.number(f"actions.loads.{i}.w", lo=-1e6, hi=1e6)
            x1 = r.number(f"actions.loads.{i}.x1", lo=0, hi=length, default=0.0)
            x2 = r.number(f"actions.loads.{i}.x2", lo=0, hi=length, default=length)
            if w is not None and x1 is not None and x2 is not None:
                if x2 < x1:
                    x1, x2 = x2, x1
                loads.append({"type": "udl", "w": w, "x1": x1, "x2": x2, "case": case})
        elif t == "linear":
            w1 = r.number(f"actions.loads.{i}.w1", lo=-1e6, hi=1e6)
            w2 = r.number(f"actions.loads.{i}.w2", lo=-1e6, hi=1e6)
            x1 = r.number(f"actions.loads.{i}.x1", lo=0, hi=length, default=0.0)
            x2 = r.number(f"actions.loads.{i}.x2", lo=0, hi=length, default=length)
            if w1 is not None and w2 is not None and x1 is not None and x2 is not None:
                if x2 < x1:
                    x1, x2 = x2, x1
                    w1, w2 = w2, w1
                loads.append({"type": "linear", "w1": w1, "w2": w2, "x1": x1, "x2": x2, "case": case})
        elif t == "moment":
            m = r.number(f"actions.loads.{i}.M", lo=-1e6, hi=1e6)
            x = r.number(f"actions.loads.{i}.x", lo=0, hi=length)
            if m is not None and x is not None:
                loads.append({"type": "moment", "M": m, "x": x, "case": case})
    return loads


def parse_input(data):
    r = Reader(_upgrade(data))
    project = r.project()

    slab_type = r.choice("slab.type", ("one_way", "two_way"), default="one_way")
    h = r.number("slab.h", lo=50, hi=1000)

    concrete_class = r.choice("materials.concrete", CONCRETE_TABLE, default="C30/37")
    fyk = r.number("materials.fyk", lo=200, hi=700, default=500)
    ductility = r.choice("materials.ductility", DUCTILITY_CLASSES, default="B")
    dg = r.number("materials.dg", lo=5, hi=63, default=20)
    gamma_c = r.number("materials.gamma_c", lo=1.0, hi=2.0, default=1.5)
    gamma_s = r.number("materials.gamma_s", lo=1.0, hi=1.5, default=1.15)
    alpha_cc = r.number("materials.alpha_cc", lo=0.8, hi=1.0, default=0.85)

    length = None
    supports = []
    preset = "simply_supported"
    lx = ly = None
    edges = None

    if slab_type == "one_way":
        length = r.number("span.l", lo=0.5, hi=60)
        preset = r.choice("span.preset", ("simply_supported", "two_spans", "three_spans", "cantilever", "custom"),
                          default="simply_supported")
        raw_supp = r.raw("span.supports")
        if not isinstance(raw_supp, list) or not raw_supp:
            r.errors["span.supports"] = "Add at least one support."
        else:
            for i, _ in enumerate(raw_supp):
                x = r.number(f"span.supports.{i}.x", lo=0, hi=length if length else None)
                kind = r.choice(f"span.supports.{i}.type", SUPPORT_TYPES, default="pin")
                if x is not None:
                    supports.append({"x": x, "type": kind})
            supports.sort(key=lambda s: s["x"])
    else:
        lx = r.number("panel.lx", lo=0.5, hi=60)
        ly = r.number("panel.ly", lo=0.5, hi=60)
        if lx is not None and ly is not None:
            if lx > ly:
                r.errors["panel.lx"] = "lx must be the shorter span (lx ≤ ly)."
            elif ly / lx > 2.0 + 1e-6:
                r.errors["panel.ly"] = "ly/lx is more than 2: design it as a one-way slab."
        edges = {}
        for edge in ("top", "bottom", "left", "right"):
            edges[edge] = r.choice(f"panel.edges.{edge}", ("continuous", "discontinuous"), default="continuous")

    def read_bar(pos, optional=False):
        raw_dia = r.raw(f"reinforcement.{pos}_dia")
        if optional and (raw_dia is None or raw_dia == "" or raw_dia == "none" or raw_dia == 0):
            return BarLayer(None, None)
        dia = r.choice(f"reinforcement.{pos}_dia", BAR_SIZES, default=10)
        s = r.number(f"reinforcement.{pos}_s", lo=50, hi=1000, default=200)
        return BarLayer(dia, s)

    bottom_x = read_bar("bottom_x")
    bottom_y = read_bar("bottom_y")
    top_x = read_bar("top_x", optional=True)
    top_y = read_bar("top_y", optional=True)
    cover = r.number("reinforcement.cover", lo=0, hi=150, default=25)
    delta_c_dev = r.number("reinforcement.delta_c_dev", lo=0, hi=20, default=10)

    mode = r.choice("actions.mode", ("analysis", "direct"), default="analysis")
    category = r.choice("actions.category", PSI_CATEGORIES, default="B")
    self_weight = r.flag("actions.self_weight", default=True)
    gk = r.number("actions.gk", lo=0, hi=1000, default=0.0)
    qk = r.number("actions.qk", lo=0, hi=1000, default=0.0)
    pattern = r.flag("actions.pattern", default=True)
    partitions = r.flag("actions.partitions", default=False)
    loads = []
    m_sag = m_hog = v_ed = None

    if mode == "analysis":
        if slab_type == "one_way":
            loads = _read_loads(r, length)
        sw_val = (CONCRETE_DENSITY * h / 1000.0) if self_weight and h else 0.0
        if not (gk or qk or sw_val or loads) and not r.errors:
            r.errors["actions.gk"] = "The slab carries no load: enter gk, qk or another load."
    else:
        m_sag = r.number("actions.M_sag", lo=0, hi=1e6, default=0.0)
        m_hog = r.number("actions.M_hog", lo=0, hi=1e6, default=0.0)
        v_ed = r.number("actions.VEd", lo=0, hi=1e6, default=0.0)
        if not (m_sag or m_hog) and not r.errors:
            r.errors["actions.M_sag"] = "Enter a sagging or a hogging moment."

    E_gpa = None
    if r.choice("stiffness.E_method", ("concrete", "enter"), default="concrete") == "enter":
        E_gpa = r.number("stiffness.E", lo=1, hi=300)

    exposure_ids = [row["id"] for row in durability.EXPOSURE_ROWS]
    exposure = r.choice("durability.exposure", exposure_ids, default="XC1")
    cement_group = r.choice("durability.cement_group", list(durability.ROWS_BY_ID[exposure]["groups"]),
                            default=next(iter(durability.ROWS_BY_ID[exposure]["groups"])))
    fire_period = r.choice("durability.fire_period", fire.FIRE_PERIODS, default="none")

    if r.errors:
        raise ValidationError(r.errors)

    return SlabInput(
        project=project, slab_type=slab_type, h=h,
        concrete=Concrete.from_class(concrete_class, gamma_c, alpha_cc),
        steel=Reinforcement(fyk, ductility, gamma_s), dg=dg,
        length=length, supports=supports, preset=preset,
        lx=lx, ly=ly, edges=edges,
        bottom_x=bottom_x, bottom_y=bottom_y, top_x=top_x, top_y=top_y,
        cover=cover, delta_c_dev=delta_c_dev,
        mode=mode, gk=gk, qk=qk, self_weight=self_weight, category=category,
        loads=loads, pattern=pattern, partitions=partitions,
        m_sag=None if m_sag is None else m_sag * 1e6,
        m_hog=None if m_hog is None else m_hog * 1e6,
        v_ed=None if v_ed is None else v_ed * 1e3,
        E_gpa=E_gpa, exposure=exposure, cement_group=cement_group, fire_period=fire_period,
    )


def kN(n):
    return f"{n / 1e3:.2f}" if n is not None else "—"


def kNm(m):
    return f"{m / 1e6:.2f}" if m is not None else "—"


def _m(x):
    return f"{x:.2f}"


def _analysis_loads_one_way(inp, n_g, n_q_spans, factors):
    """Build loads for one-way analysis."""
    loads = []
    # Permanent load across whole length:
    if n_g > 0:
        loads.append({"type": "udl", "w": n_g * factors["G"], "x1": 0.0, "x2": inp.length, "line": True})
    # Variable load per span:
    for (x1, x2) in n_q_spans:
        loads.append({"type": "udl", "w": inp.qk * factors["Q"], "x1": x1, "x2": x2, "line": True})
    # Further loads on strip:
    for ld in inp.loads:
        f = factors[ld["case"]]
        item = dict(ld)
        for key in ("P", "W", "M", "w", "w1", "w2"):
            if key in item:
                item[key] = item[key] * f
        loads.append(item)
    return loads


def analyse_one_way(inp):
    """Run analysis for a 1 m wide one-way slab strip."""
    b = 1000.0  # mm
    h = inp.h    # mm
    sw = (CONCRETE_DENSITY * h / 1000.0) if inp.self_weight else 0.0
    n_g = inp.gk + sw
    n_q = inp.qk
    psi0, _, psi2 = psi_factors(inp.category)

    # Elastic modulus and gross inertia (1 m width):
    E = (inp.E_gpa or inp.concrete.Ecm) * 1e6  # kPa
    inertia = 1.0 * (h / 1000.0) ** 3 / 12.0   # m⁴ per metre width

    spans = spans_of(inp.length, inp.supports)
    internal_spans = [s for s in spans if s.kind != "cantilever"]
    is_continuous = len(internal_spans) >= 2 and inp.pattern

    # Case A: all spans loaded
    spans_all = [(s.x1, s.x2) for s in spans]
    loads_A = _analysis_loads_one_way(inp, n_g, spans_all, ULS)

    try:
        res_A = analyse(inp.length, inp.supports, loads_A, E, inertia)
    except AnalysisError as err:
        raise ValidationError({"span.supports": str(err)}) from None

    cases = {"A": res_A}

    if is_continuous:
        # Case B: odd spans also loaded
        spans_odd = [(s.x1, s.x2) for s in spans if s.i % 2 == 1]
        loads_B = _analysis_loads_one_way(inp, n_g, spans_odd, ULS)
        res_B = analyse(inp.length, inp.supports, loads_B, E, inertia)
        cases["B"] = res_B

        # Case C: even spans also loaded
        spans_even = [(s.x1, s.x2) for s in spans if s.i % 2 == 0]
        loads_C = _analysis_loads_one_way(inp, n_g, spans_even, ULS)
        res_C = analyse(inp.length, inp.supports, loads_C, E, inertia)
        cases["C"] = res_C

    # Quasi-permanent run (Case A loads with G=1.0, Q=psi2):
    qp_factors = {"Ed": 1.0 / GAMMA_G, "G": 1.0, "Q": psi2}
    loads_qp = _analysis_loads_one_way(inp, n_g, spans_all, qp_factors)
    res_qp = analyse(inp.length, inp.supports, loads_qp, E, inertia)

    # Envelope over all cases:
    # Largest sagging moment:
    M_sag = 0.0
    x_sag = 0.0
    case_sag = "A"
    # Largest hogging moment:
    M_hog = 0.0
    x_hog = 0.0
    case_hog = "A"
    # Largest shear:
    V_ed = 0.0
    x_v = 0.0
    case_v = "A"

    for cname, res in cases.items():
        # Sagging
        m_max = max(res["M"])
        if m_max > M_sag:
            M_sag = m_max
            x_sag = res["x"][res["M"].index(m_max)]
            case_sag = cname

        # Hogging
        m_min = min(res["M"])
        if -m_min > M_hog:
            M_hog = -m_min
            x_hog = res["x"][res["M"].index(m_min)]
            case_hog = cname

        # Shear
        idx_v = max(range(len(res["V"])), key=lambda i: abs(res["V"][i]))
        v_max = abs(res["V"][idx_v])
        if v_max > V_ed:
            V_ed = v_max
            x_v = res["x"][idx_v]
            case_v = cname

    tol = max(1e-3 * max(M_sag, M_hog), 0.01)
    M_sag = M_sag if M_sag > tol else 0.0
    M_hog = M_hog if M_hog > tol else 0.0
    V_ed = V_ed if V_ed > 0.01 else 0.0

    # Determine if shear section is in hogging or sagging:
    i_v = min(range(len(res_A["x"])), key=lambda i: abs(res_A["x"][i] - x_v))
    v_hogging = cases[case_v]["M"][i_v] < -tol

    # Per-span peak sagging and quasi-permanent ratios for deflection:
    span_actions = []
    for s in spans:
        span_m_max = -math.inf
        span_x_max = s.x1
        for cname, res in cases.items():
            for x, m in zip(res["x"], res["M"]):
                if s.x1 - 1e-6 <= x <= s.x2 + 1e-6:
                    if m > span_m_max:
                        span_m_max = m
                        span_x_max = x
        span_m_max = max(span_m_max, 0.0)
        # Quasi-permanent moment at span_x_max:
        idx_qp = min(range(len(res_qp["x"])), key=lambda i: abs(res_qp["x"][i] - span_x_max))
        m_qp = max(res_qp["M"][idx_qp], 0.0)
        qp_ratio = min(max(m_qp / span_m_max, 0.05), 1.0) if span_m_max > 1e-6 else 0.5
        span_actions.append({
            "span": s,
            "MEd": span_m_max * 1e6,  # N·mm
            "Mqp": m_qp * 1e6,
            "qp_ratio": qp_ratio,
        })

    return {
        "n_g": n_g, "n_q": n_q, "sw": sw, "psi2": psi2,
        "is_continuous": is_continuous, "spans": spans,
        "cases": cases, "res_A": res_A, "res_qp": res_qp,
        "M_sag": M_sag * 1e6, "x_sag": x_sag, "case_sag": case_sag,
        "M_hog": M_hog * 1e6, "x_hog": x_hog, "case_hog": case_hog,
        "VEd": V_ed * 1e3, "x_v": x_v, "case_v": case_v,
        "v_hogging": v_hogging,
        "span_actions": span_actions,
        "E": E, "inertia": inertia,
    }


def _scope_checks(inp):
    fck = inp.concrete.fck
    fyk = inp.steel.fyk
    ok_fck = fck <= 50.0
    ok_fyk = 400.0 <= fyk <= 600.0
    ok = ok_fck and ok_fyk

    lines = [
        f"Concrete class {inp.concrete.name}: fck = {fck:g} MPa ≤ 50 MPa ({'satisfied' if ok_fck else 'outside standard scope'})",
        f"Reinforcement: fyk = {fyk:g} MPa, class {inp.steel.ductility} (Eurocode 2 scope is 400–600 MPa: {'satisfied' if ok_fyk else 'outside standard scope'})",
    ]
    res_str = f"fck = {fck:g} MPa, fyk = {fyk:g} MPa"
    return [CheckResult("scope", GROUPS[0], "Eurocode 2 scope", PASS if ok else FAIL,
                        result=res_str, utilisation=fck / 50.0, working=lines)]


def _cover_checks(inp):
    dur = durability.durability_cover(inp.exposure, inp.cement_group, inp.concrete.name)
    c_dur = dur["cover"]
    all_dias = [bar.dia for bar in (inp.bottom_x, inp.bottom_y, inp.top_x, inp.top_y)
                if bar.dia and bar.dia != "none"]
    phi_max = max(all_dias) if all_dias else 10
    c_min_b = max(phi_max, 10)
    c_min = max(c_dur, c_min_b)
    c_nom_req = c_min + inp.delta_c_dev

    ok = inp.cover >= c_nom_req
    lines = [
        f"Exposure {durability.ROWS_BY_ID[inp.exposure]['classes']} ({inp.cement_group}), intended life 50 years",
        f"Minimum cover for durability: cmin,dur = {c_dur:g} mm",
        f"Minimum cover for bond: cmin,b = max(φmax, 10) = max({phi_max}, 10) = {c_min_b:g} mm (no links)",
        f"Nominal cover required: cnom,req = max(cmin,dur, cmin,b) + Δcdev = {c_min:g} + {inp.delta_c_dev:g} = {c_nom_req:g} mm",
        f"Provided nominal cover: cnom = {inp.cover:g} mm ({'satisfied' if ok else 'insufficient'})",
    ]
    return [CheckResult("cover", GROUPS[1], "Durability and cover", PASS if ok else FAIL,
                        result=f"{inp.cover:g} vs {c_nom_req:g} mm",
                        utilisation=c_nom_req / max(inp.cover, 1.0),
                        working=lines, target="cover",
                        note="" if ok else "Increase the nominal concrete cover.")]


def _fire_checks(inp):
    a = inp.cover + (inp.bottom_x.dia or 10) / 2.0
    ly_lx = (inp.ly / inp.lx) if (inp.slab_type == "two_way" and inp.lx and inp.ly) else None
    ok, req, lines = fire.check_slab_fire(inp.fire_period, inp.slab_type, inp.h, a, ly_lx=ly_lx)
    if inp.fire_period == "none":
        return [CheckResult("fire", GROUPS[2], "Fire resistance", PASS, result="none", working=lines)]

    res_str = f"h = {inp.h:g}/{req['hs']} mm, a = {a:.1f}/{req['a']} mm"
    util = max(req["hs"] / max(inp.h, 1.0), req["a"] / max(a, 1.0))
    return [CheckResult("fire", GROUPS[2], f"Fire resistance {inp.fire_period}", PASS if ok else FAIL,
                        result=res_str, utilisation=util, working=lines, target="h",
                        note="" if ok else "Increase the slab thickness or the bar axis distance (cover).")]


def _actions_checks_one_way(inp, act):
    if inp.mode == "direct":
        return [CheckResult(
            "actions", GROUPS[3], "Design actions", INFO,
            result=f"M+Ed = {kNm(act['M_sag'])} kNm/m, M−Ed = {kNm(act['M_hog'])} kNm/m, VEd = {kN(act['VEd'])} kN/m",
            working=[f"Direct design values: M+Ed = {kNm(act['M_sag'])} kNm/m, M−Ed = {kNm(act['M_hog'])} kNm/m, VEd = {kN(act['VEd'])} kN/m",
                     "A moment or shear entered as zero is not designed for."])]

    supp_str = ", ".join(f"{SUPPORT_NAMES[s['type']]} at {_m(s['x'])} m" for s in inp.supports)
    lines = [
        f"One-way slab strip 1 m wide, span length {_m(inp.length)} m on {len(inp.supports)} support{'s' if len(inp.supports) > 1 else ''}: {supp_str}",
        f"Loads per metre width: gk = {inp.gk:g} kN/m²" + (f" + self-weight {act['sw']:.2f} kN/m²" if inp.self_weight else "") +
        f", qk = {inp.qk:g} kN/m² (category {inp.category})",
        f"Design combinations: 1.35·n_g = {1.35 * act['n_g']:.3f} kN/m, 1.5·n_q = {1.5 * act['n_q']:.3f} kN/m",
    ]
    if act["is_continuous"]:
        lines += [
            "Pattern loading on continuous slab:",
            f"  Case A (all spans loaded): M+ = {kNm(max(act['cases']['A']['M']))} kNm/m, M− = {kNm(-min(act['cases']['A']['M']))} kNm/m, |V| = {kN(max(abs(v) for v in act['cases']['A']['V']))} kN/m",
            f"  Case B (odd spans loaded): M+ = {kNm(max(act['cases']['B']['M']))} kNm/m, M− = {kNm(-min(act['cases']['B']['M']))} kNm/m, |V| = {kN(max(abs(v) for v in act['cases']['B']['V']))} kN/m",
            f"  Case C (even spans loaded): M+ = {kNm(max(act['cases']['C']['M']))} kNm/m, M− = {kNm(-min(act['cases']['C']['M']))} kNm/m, |V| = {kN(max(abs(v) for v in act['cases']['C']['V']))} kN/m",
            f"Governing envelope: M+Ed = {kNm(act['M_sag'])} kNm/m (Case {act['case_sag']} at x = {_m(act['x_sag'])} m), "
            f"M−Ed = {kNm(act['M_hog'])} kNm/m (Case {act['case_hog']} at x = {_m(act['x_hog'])} m), "
            f"VEd = {kN(act['VEd'])} kN/m (Case {act['case_v']} at x = {_m(act['x_v'])} m)",
        ]
    else:
        lines += [
            f"Single span (Case A): M+Ed = {kNm(act['M_sag'])} kNm/m at x = {_m(act['x_sag'])} m, "
            f"M−Ed = {kNm(act['M_hog'])} kNm/m at x = {_m(act['x_hog'])} m, VEd = {kN(act['VEd'])} kN/m at x = {_m(act['x_v'])} m",
        ]

    res_str = f"M+Ed = {kNm(act['M_sag'])} kNm/m, M−Ed = {kNm(act['M_hog'])} kNm/m, VEd = {kN(act['VEd'])} kN/m"
    return [CheckResult("actions", GROUPS[3], "Design actions", INFO, result=res_str, working=lines)]


def _bending_checks(inp, M_ed, layer, name, is_hogging):
    """Bending check for sagging or hogging."""
    b = 1000.0  # mm
    fck = inp.concrete.fck
    fyd = inp.steel.fyd

    if M_ed <= 0:
        return [CheckResult(f"bending_{name}", GROUPS[4], f"Bending ({name})", NA,
                            result="0.00 kNm/m", working=[f"No {name} moment (MEd = 0.00 kNm/m); check not applicable."])]

    if not layer.dia or layer.dia == "none" or not layer.spacing:
        return [CheckResult(f"bending_{name}", GROUPS[4], f"Bending ({name})", FAIL,
                            result="No bars provided",
                            working=[f"Design {name} moment MEd = {kNm(M_ed)} kNm/m.", "No top bars entered."],
                            target=f"reinforcement.{name}_dia",
                            note="Add top bars over the supports." if is_hogging else "Add bottom bars.")]

    d = inp.h - inp.cover - layer.dia / 2.0
    K = M_ed / (b * d**2 * fck)
    kp = flexure.k_prime(1.0, uk_limit=True)  # 0.168

    if K > kp:
        lines = [
            f"Design {name} moment MEd = {kNm(M_ed)} kNm/m",
            f"Effective depth d = {d:.1f} mm; concrete fck = {fck:g} MPa",
            f"K = MEd / (b·d²·fck) = {K:.4f} > K' = {kp:.3f}",
            "Compression reinforcement is not permitted in solid slabs.",
        ]
        return [CheckResult(f"bending_{name}", GROUPS[4], f"Bending ({name})", FAIL,
                            result=f"K = {K:.3f} > K' = {kp:.3f}",
                            utilisation=K / kp, working=lines, target="slab.h",
                            note="Increase the slab thickness (compression reinforcement is not used in slabs).")]

    z = flexure.lever_arm(K, d)
    As_req = M_ed / (fyd * z)
    As_prov = layer.As

    ok = As_prov >= As_req
    lines = [
        f"Design {name} moment MEd = {kNm(M_ed)} kNm/m per metre width",
        f"Effective depth d = {d:.1f} mm; lever arm z = {z:.1f} mm (≤ 0.95d = {0.95 * d:.1f} mm)",
        f"K = MEd / (b·d²·fck) = {K:.4f} ≤ K' = {kp:.3f}",
        f"Required tension steel: As,req = MEd / (fyd·z) = {M_ed:.0f} / ({fyd:.1f} × {z:.1f}) = {As_req:.0f} mm²/m",
        f"Provided reinforcement: {layer.label} → As,prov = {As_prov:.0f} mm²/m ({'satisfied' if ok else 'insufficient'})",
    ]
    res_str = f"{As_prov:.0f} vs {As_req:.0f} mm²/m"
    return [CheckResult(f"bending_{name}", GROUPS[4], f"Bending ({name})", PASS if ok else FAIL,
                        result=res_str, utilisation=As_req / max(As_prov, 1.0),
                        working=lines, target=f"reinforcement.{name}_s",
                        note="" if ok else "Increase bar diameter or decrease bar spacing.")]


def _shear_checks(inp, act):
    b = 1000.0  # mm
    V_ed = act["VEd"]  # N/m
    if V_ed <= 0:
        return [CheckResult("shear", GROUPS[5], "Shear resistance", NA,
                            result="0.00 kN/m", working=["No applied shear force (VEd = 0.00 kN/m); check not applicable."])]

    # Determine tension reinforcement and effective depth at shear section:
    v_hogging = act.get("v_hogging", False)
    if v_hogging and inp.top_x.dia and inp.top_x.dia != "none":
        layer = inp.top_x
        d = inp.h - inp.cover - layer.dia / 2.0
        face_name = "top x bars (hogging moment at shear section)"
    else:
        layer = inp.bottom_x
        d = inp.h - inp.cover - (layer.dia or 10) / 2.0
        face_name = "bottom x bars (sagging moment at shear section)"

    v_ed_mpa = V_ed / (b * d)
    rho_l = layer.As / (b * d)
    vrd_c = flexure.vrd_c(inp.concrete.fck, d, rho_l)

    ok = v_ed_mpa <= vrd_c
    lines = [
        f"Design shear force VEd = {kN(V_ed)} kN/m per metre width",
        f"Tension steel at critical shear section: {face_name} → As = {layer.As:.0f} mm²/m",
        f"Effective depth d = {d:.1f} mm; longitudinal ratio ρl = As/(b·d) = {rho_l:.4f} (≤ 0.02)",
        f"Applied shear stress: vEd = VEd / (b·d) = {V_ed:.0f} / (1000 × {d:.1f}) = {v_ed_mpa:.3f} MPa",
        f"Concrete shear capacity without links: vRd,c = {vrd_c:.3f} MPa ({'satisfied' if ok else 'exceeded'})",
    ]
    res_str = f"{v_ed_mpa:.3f} vs {vrd_c:.3f} MPa"
    return [CheckResult("shear", GROUPS[5], "Shear resistance", PASS if ok else FAIL,
                        result=res_str, utilisation=v_ed_mpa / vrd_c, working=lines, target="slab.h",
                        note="" if ok else "Increase the slab thickness (shear reinforcement is not usual in solid slabs).")]


def _deflection_checks_one_way(inp, act):
    b = 1000.0
    fck = inp.concrete.fck
    fyd = inp.steel.fyd
    results = []

    for item in act["span_actions"]:
        span = item["span"]
        MEd = item["MEd"]
        Mqp = item["Mqp"]
        qp_ratio = item["qp_ratio"]

        # Effective depth:
        d = inp.h - inp.cover - (inp.bottom_x.dia or 10) / 2.0
        if span.kind == "cantilever" and inp.top_x.dia and inp.top_x.dia != "none":
            d = inp.h - inp.cover - inp.top_x.dia / 2.0
            layer = inp.top_x
        else:
            layer = inp.bottom_x

        As_prov = layer.As
        K_sys = DEFLECTION_K[span.kind]

        if MEd > 0 and As_prov > 0:
            K_bend = min(MEd / (b * d**2 * fck), 0.168)
            z = flexure.lever_arm(K_bend, d)
            As_req = MEd / (fyd * z)
            rho = As_req / (b * d)
            basic = flexure.basic_span_depth(K_sys, fck, rho, rho_c=0.0)
            F1 = 1.0
            F2 = (7.0 / span.l) if (span.l > 7.0 and inp.partitions) else 1.0
            sigma_s = fyd * qp_ratio * (As_req / As_prov)
            F3 = min(310.0 / max(sigma_s, 1.0), 1.5)
            limiting = basic * F1 * F2 * F3
        else:
            rho = 0.0015
            basic = flexure.basic_span_depth(K_sys, fck, rho, rho_c=0.0)
            limiting = basic

        actual = (span.l * 1000.0) / d
        ok = actual <= limiting

        lines = [
            f"{span.label()}: l = {_m(span.l)} m, d = {d:.1f} mm, K = {K_sys:g}",
            f"Basic span-to-depth ratio: (l/d)basic = {basic:.1f}",
            f"Modification factors: F1 = 1.0 (rectangular); F2 = {F2:.3f}" +
            (f" (partitions, span > 7 m)" if F2 < 1.0 else "") +
            (f"; F3 = {F3:.3f} (service steel stress σs = {sigma_s:.1f} MPa)" if MEd > 0 else ""),
            f"Limiting l/d = {limiting:.1f}; Actual span-to-depth ratio: l/d = {actual:.1f} ({'satisfied' if ok else 'exceeded'})",
        ]
        res_str = f"{actual:.1f} vs {limiting:.1f}"
        results.append(CheckResult(f"deflection_span_{span.i}", GROUPS[6], f"Deflection ({span.label()})",
                                   PASS if ok else FAIL, result=res_str,
                                   utilisation=actual / limiting, working=lines, target="slab.h",
                                   note="" if ok else "Increase the slab thickness or provide more reinforcement."))
    return results


def _detailing_checks(inp, is_two_way=False):
    b = 1000.0
    h = inp.h
    fctm = inp.concrete.fctm
    fyk = inp.steel.fyk
    checks = []

    # 1. Minimum and maximum reinforcement per tension face:
    d = h - inp.cover - (inp.bottom_x.dia or 10) / 2.0
    As_min = max(0.26 * (fctm / fyk) * b * d, 0.0013 * b * d)
    As_max = 0.04 * b * h

    As_bx = inp.bottom_x.As
    ok_min_bx = As_bx >= As_min
    ok_max_bx = As_bx <= As_max
    lines_bx = [
        f"Bottom x bars: {inp.bottom_x.label} → As = {As_bx:.0f} mm²/m",
        f"As,min = max(0.26·fctm/fyk, 0.0013)·b·d = max({0.26 * fctm / fyk * 1000 * d:.0f}, {0.0013 * 1000 * d:.0f}) = {As_min:.0f} mm²/m",
        f"As,max = 0.04·b·h = 0.04 × 1000 × {h:g} = {As_max:.0f} mm²/m",
    ]
    checks.append(CheckResult("detailing_as_min_bottom_x", GROUPS[7], "Minimum reinforcement (bottom x)",
                              PASS if ok_min_bx else FAIL, result=f"{As_bx:.0f} vs {As_min:.0f} mm²/m",
                              utilisation=As_min / max(As_bx, 1.0), working=lines_bx,
                              target="reinforcement.bottom_x_s",
                              note="" if ok_min_bx else "Increase bar diameter or decrease bar spacing."))

    checks.append(CheckResult("detailing_as_max", GROUPS[7], "Maximum reinforcement",
                              PASS if ok_max_bx else FAIL, result=f"{As_bx:.0f} vs {As_max:.0f} mm²/m",
                              utilisation=As_bx / As_max, working=[f"Provided As = {As_bx:.0f} mm²/m ≤ As,max = {As_max:.0f} mm²/m"],
                              target="reinforcement.bottom_x_dia"))

    # Top x bars minimum check if provided:
    if inp.top_x.dia and inp.top_x.dia != "none":
        As_tx = inp.top_x.As
        ok_tx = As_tx >= As_min
        checks.append(CheckResult("detailing_as_min_top_x", GROUPS[7], "Minimum reinforcement (top x)",
                                  PASS if ok_tx else FAIL, result=f"{As_tx:.0f} vs {As_min:.0f} mm²/m",
                                  utilisation=As_min / max(As_tx, 1.0),
                                  working=[f"Top x bars: {inp.top_x.label} → As = {As_tx:.0f} mm²/m vs As,min = {As_min:.0f} mm²/m"],
                                  target="reinforcement.top_x_s",
                                  note="" if ok_tx else "Increase bar diameter or decrease bar spacing."))

    # 2. Secondary (distribution) reinforcement:
    if not is_two_way:
        As_sec_min = 0.20 * As_bx
        As_by = inp.bottom_y.As
        ok_sec = As_by >= As_sec_min
        lines_sec = [
            f"Secondary transverse reinforcement (bottom y): {inp.bottom_y.label} → As = {As_by:.0f} mm²/m",
            f"Required secondary reinforcement: ≥ 20% of main bars = 0.20 × {As_bx:.0f} = {As_sec_min:.0f} mm²/m ({'satisfied' if ok_sec else 'insufficient'})",
        ]
        checks.append(CheckResult("detailing_secondary_steel", GROUPS[7], "Secondary reinforcement",
                                  PASS if ok_sec else FAIL, result=f"{As_by:.0f} vs {As_sec_min:.0f} mm²/m",
                                  utilisation=As_sec_min / max(As_by, 1.0), working=lines_sec,
                                  target="reinforcement.bottom_y_s",
                                  note="" if ok_sec else "Secondary transverse steel must be at least 20% of the principal steel."))

    # 3. Maximum bar spacing:
    # Principal bars: min(2h, 250) mm in maximum moment area
    s_max_main = min(2.0 * h, 250.0)
    # Secondary bars: min(3h, 400) mm
    s_max_sec = min(3.0 * h, 400.0)

    # In two-way slabs, both x and y are principal bars: min(2h, 250)
    if is_two_way:
        s_max_y = s_max_main
    else:
        s_max_y = s_max_sec

    s_bx = inp.bottom_x.spacing or 0.0
    ok_s_bx = s_bx <= s_max_main
    checks.append(CheckResult("detailing_spacing_bottom_x", GROUPS[7], "Maximum spacing (bottom x)",
                              PASS if ok_s_bx else FAIL, result=f"{s_bx:g} vs {s_max_main:g} mm",
                              utilisation=s_bx / s_max_main,
                              working=[f"Bottom x bar spacing: s = {s_bx:g} mm ≤ min(2h, 250) = {s_max_main:g} mm"],
                              target="reinforcement.bottom_x_s",
                              note="" if ok_s_bx else f"Spacing exceeds maximum allowable {s_max_main:g} mm."))

    s_by = inp.bottom_y.spacing or 0.0
    ok_s_by = s_by <= s_max_y
    checks.append(CheckResult("detailing_spacing_bottom_y", GROUPS[7], "Maximum spacing (bottom y)",
                              PASS if ok_s_by else FAIL, result=f"{s_by:g} vs {s_max_y:g} mm",
                              utilisation=s_by / s_max_y,
                              working=[f"Bottom y bar spacing: s = {s_by:g} mm ≤ {s_max_y:g} mm"],
                              target="reinforcement.bottom_y_s",
                              note="" if ok_s_by else f"Spacing exceeds maximum allowable {s_max_y:g} mm."))

    # 4. Minimum clear spacing:
    # clear gap = spacing - phi >= max(phi, dg + 5, 20)
    s_min_clear = max(inp.bottom_x.dia or 10, inp.dg + 5.0, 20.0)
    clear_bx = (inp.bottom_x.spacing or 0.0) - (inp.bottom_x.dia or 10)
    ok_clear = clear_bx >= s_min_clear
    checks.append(CheckResult("detailing_clear_spacing", GROUPS[7], "Minimum clear bar spacing",
                              PASS if ok_clear else FAIL, result=f"{clear_bx:g} vs {s_min_clear:g} mm",
                              utilisation=s_min_clear / max(clear_bx, 1.0),
                              working=[f"Clear gap between bottom x bars: s − φ = {inp.bottom_x.spacing} − {inp.bottom_x.dia} = {clear_bx:g} mm",
                                       f"Required: max(φ, dg + 5, 20) = max({inp.bottom_x.dia}, {inp.dg + 5:g}, 20) = {s_min_clear:g} mm"],
                              target="reinforcement.bottom_x_s",
                              note="" if ok_clear else "Increase bar spacing."))

    # 5. Crack control:
    if h <= 200.0:
        checks.append(CheckResult("crack_control", GROUPS[7], "Crack control", PASS,
                                  result=f"h = {h:g} mm ≤ 200 mm",
                                  working=[f"Slab depth h = {h:g} mm ≤ 200 mm.",
                                           "Slabs not thicker than 200 mm with the minimum reinforcement need no further crack control."],
                                  note="slabs not thicker than 200 mm with the minimum reinforcement need no further crack control"))
    else:
        # Evaluate steel stress σs for bottom bars:
        wmax = 0.4 if inp.exposure == "XC1" else 0.3
        sigma_s = 250.0  # nominal steel stress for crack limit check
        max_bar, max_pitch = tables.crack_limits(sigma_s, wmax)
        dia_bx = inp.bottom_x.dia or 10
        ok_crack_dia = (max_bar is None) or (dia_bx <= max_bar)
        ok_crack_pitch = (max_pitch is None) or (s_bx <= max_pitch)
        ok_crack = ok_crack_dia and ok_crack_pitch
        lines_crack = [
            f"Slab depth h = {h:g} mm > 200 mm: crack control checked against Table 11",
            f"Exposure {inp.exposure} (wmax = {wmax} mm), estimated steel stress σs ≈ {sigma_s:.0f} MPa",
            f"Maximum bar size: {max_bar:.1f} mm vs provided H{dia_bx} ({'satisfied' if ok_crack_dia else 'exceeded'})",
            f"Maximum bar spacing: {max_pitch:.1f} mm vs provided {s_bx:g} mm ({'satisfied' if ok_crack_pitch else 'exceeded'})",
        ]
        checks.append(CheckResult("crack_control", GROUPS[7], "Crack control (bar size and spacing)",
                                  PASS if ok_crack else FAIL,
                                  result=f"H{dia_bx} @ {s_bx:g} vs H{max_bar:.0f} @ {max_pitch:.0f} mm",
                                  working=lines_crack, target="reinforcement.bottom_x_dia",
                                  note="" if ok_crack else "Reduce bar size or bar spacing to satisfy Table 11 crack limits."))

    return checks


def _input_echo(inp, act):
    rows = [
        ("Slab type", "One-way solid slab (1 m strip)" if inp.slab_type == "one_way" else "Two-way solid slab"),
        ("Thickness", f"h = {inp.h:g} mm"),
        ("Concrete", inp.concrete.name),
        ("fyk", f"{inp.steel.fyk:g} MPa (class {inp.steel.ductility})"),
    ]
    if inp.slab_type == "one_way":
        supp_str = ", ".join(f"{SUPPORT_NAMES[s['type']]} at {_m(s['x'])} m" for s in inp.supports)
        rows.append(("Span & supports", f"L = {_m(inp.length)} m; {supp_str}"))
    else:
        edges_str = f"top: {inp.edges.get('top')}, bottom: {inp.edges.get('bottom')}, left: {inp.edges.get('left')}, right: {inp.edges.get('right')}"
        rows.append(("Panel dimensions", f"lx = {_m(inp.lx)} m, ly = {_m(inp.ly)} m ({edges_str})"))

    rows += [
        ("Bottom bars (x)", inp.bottom_x.label + f" (As = {inp.bottom_x.As:.0f} mm²/m)"),
        ("Bottom bars (y)", inp.bottom_y.label + f" (As = {inp.bottom_y.As:.0f} mm²/m)"),
        ("Top bars (x)", inp.top_x.label + (f" (As = {inp.top_x.As:.0f} mm²/m)" if inp.top_x.As > 0 else "")),
        ("Top bars (y)", inp.top_y.label + (f" (As = {inp.top_y.As:.0f} mm²/m)" if inp.top_y.As > 0 else "")),
        ("Nominal cover", f"{inp.cover:g} mm (Δcdev = {inp.delta_c_dev:g} mm)"),
        ("Loading", f"gk = {inp.gk:g} kN/m²" + (f" + self-weight {act.get('sw', 0):.2f} kN/m²" if inp.self_weight else "") +
                    f", qk = {inp.qk:g} kN/m² (category {inp.category})"),
        ("Exposure & fire", f"{inp.exposure} ({inp.cement_group}), fire: {inp.fire_period}"),
    ]
    return [{"label": k, "value": v} for k, v in rows]


def _plots_one_way(inp, act):
    res_A = act["res_A"]
    res_qp = act["res_qp"]
    b = 1000.0
    h = inp.h
    inertia = 1.0 * (h / 1000.0) ** 3 / 12.0

    section = {
        "shape": "rectangular",
        "slab_type": inp.slab_type,
        "b": b,
        "h": h,
        "cover": inp.cover,
        "bottom_x": {"dia": inp.bottom_x.dia, "s": inp.bottom_x.spacing, "As": inp.bottom_x.As},
        "bottom_y": {"dia": inp.bottom_y.dia, "s": inp.bottom_y.spacing, "As": inp.bottom_y.As},
        "top_x": {"dia": inp.top_x.dia, "s": inp.top_x.spacing, "As": inp.top_x.As},
        "top_y": {"dia": inp.top_y.dia, "s": inp.top_y.spacing, "As": inp.top_y.As},
    }
    model = {"length": inp.length, "supports": inp.supports}

    analysis = {
        "length": inp.length,
        "E": act["E"] / 1e6,  # GPa
        "segments": [{"x1": 0.0, "x2": inp.length, "I": inertia * 1e6}],
        "supports": inp.supports,
        "loads": _analysis_loads_one_way(inp, act["n_g"], [(s.x1, s.x2) for s in act["spans"]], ULS),
        "w": 1.35 * act["n_g"] + 1.5 * act["n_q"],
        "nodes": res_A["nodes"],
        "elements": res_A["elements"],
        "free_dofs": res_A["free_dofs"],
        "reactions": res_A["reactions"],
        "x": res_A["x"],
        "M": res_A["M"],
        "V": res_A["V"],
        "delta": res_A["delta"],
        "events": {
            "V": res_A["events"]["V"],
            "M": res_A["events"]["M"],
            "zeros": res_A["events"]["zeros"],
        },
        "envelope": {
            **res_A["envelope"],
            "shear": res_A["envelope"]["shear"],
        },
        "design": {
            "sag": act["M_sag"] / 1e6,
            "x_sag": act["x_sag"],
            "hog": act["M_hog"] / 1e6,
            "x_hog": act["x_hog"],
            "V": act["VEd"] / 1e3,
            "x_v": act["x_v"],
            "case_sag": act["case_sag"],
            "case_hog": act["case_hog"],
            "case_v": act["case_v"],
        },
    }
    return {"section": section, "model": model, "analysis": analysis}


class CheckDict(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def check_slab(data):
    inp = parse_input(data)

    if inp.slab_type == "one_way":
        return _check_one_way(inp)
    else:
        return _check_two_way(inp)


def _check_one_way(inp):
    if inp.mode == "analysis":
        act = analyse_one_way(inp)
    else:
        act = {
            "mode": "direct",
            "M_sag": inp.m_sag, "x_sag": None, "case_sag": "direct",
            "M_hog": inp.m_hog, "x_hog": None, "case_hog": "direct",
            "VEd": inp.v_ed, "x_v": None, "case_v": "direct",
            "v_hogging": (inp.m_hog or 0) > 0 and not (inp.m_sag or 0),
            "spans": spans_of(inp.length, inp.supports) if inp.length and inp.supports else [],
            "span_actions": [],
            "res_A": None,
            "sw": (CONCRETE_DENSITY * inp.h / 1000.0) if inp.self_weight else 0.0,
            "n_g": inp.gk + ((CONCRETE_DENSITY * inp.h / 1000.0) if inp.self_weight else 0.0),
            "n_q": inp.qk,
            "E": (inp.E_gpa or inp.concrete.Ecm) * 1e6,
        }

    checks = []
    checks += _scope_checks(inp)
    checks += _cover_checks(inp)
    checks += _fire_checks(inp)
    checks += _actions_checks_one_way(inp, act)
    checks += _bending_checks(inp, act["M_sag"], inp.bottom_x, "bottom_x", is_hogging=False)
    checks += _bending_checks(inp, act["M_hog"], inp.top_x, "top_x", is_hogging=True)
    checks += _shear_checks(inp, act)
    if act.get("span_actions"):
        checks += _deflection_checks_one_way(inp, act)
    checks += _detailing_checks(inp, is_two_way=False)

    summary = summarise(checks)
    plots = _plots_one_way(inp, act) if inp.mode == "analysis" else {
        "section": {"slab_type": inp.slab_type, "b": 1000.0, "h": inp.h, "cover": inp.cover},
        "model": {"length": inp.length, "supports": inp.supports},
        "analysis": None,
    }

    checks_dict = [CheckDict(c.to_dict()) for c in checks]
    return {
        "element": "slab",
        "project": inp.project,
        "summary": summary,
        "verdict": summary["verdict"],
        "groups": list(GROUPS),
        "checks": checks_dict,
        "working": checks_dict,
        "inputs": _input_echo(inp, act),
        "input_echo": _input_echo(inp, act),
        "assumptions": list(ASSUMPTIONS),
        "derived": {
            "slab_type": inp.slab_type,
            "h": inp.h,
            "MEd_sag": act["M_sag"] / 1e6 if act["M_sag"] else 0.0,
            "MEd_hog": act["M_hog"] / 1e6 if act["M_hog"] else 0.0,
            "VEd": act["VEd"] / 1e3 if act["VEd"] else 0.0,
            "bottom_x": {"dia": inp.bottom_x.dia, "s": inp.bottom_x.spacing, "As": inp.bottom_x.As},
            "bottom_y": {"dia": inp.bottom_y.dia, "s": inp.bottom_y.spacing, "As": inp.bottom_y.As},
            "top_x": {"dia": inp.top_x.dia, "s": inp.top_x.spacing, "As": inp.top_x.As},
            "top_y": {"dia": inp.top_y.dia, "s": inp.top_y.spacing, "As": inp.top_y.As},
        },
        "plots": plots,
    }


def map_edges_to_case(edges):
    """Map the four edge boundary conditions (top/bottom long, left/right short) to one of the 9 cases."""
    if not edges:
        return "interior"
    num_cont_long = sum(1 for e in (edges.get("top"), edges.get("bottom")) if e == "continuous")
    num_cont_short = sum(1 for e in (edges.get("left"), edges.get("right")) if e == "continuous")

    mapping = {
        (2, 2): "interior",
        (2, 1): "one_short_discontinuous",
        (1, 2): "one_long_discontinuous",
        (1, 1): "two_adjacent_discontinuous",
        (2, 0): "two_short_discontinuous",
        (0, 2): "two_long_discontinuous",
        (1, 0): "three_discontinuous_one_long_continuous",
        (0, 1): "three_discontinuous_one_short_continuous",
        (0, 0): "four_discontinuous",
    }
    return mapping[(num_cont_long, num_cont_short)]


def _check_two_way(inp):
    b = 1000.0
    h = inp.h
    sw = (CONCRETE_DENSITY * h / 1000.0) if inp.self_weight else 0.0
    n = 1.35 * (inp.gk + sw) + 1.5 * inp.qk  # kN/m²

    case_id = map_edges_to_case(inp.edges)
    case_label = next(c["label"] for c in tables.SLAB_CASES if c["id"] == case_id)
    ly_lx = inp.ly / inp.lx
    coeffs = tables.two_way_coefficients(case_id, ly_lx)

    # Moments in N·mm per metre width (1 kNm = 1e6 N·mm):
    msx_mid = coeffs["bsx_mid"] * n * (inp.lx ** 2) * 1e6
    msx_sup = (coeffs["bsx_sup"] * n * (inp.lx ** 2) * 1e6) if coeffs["bsx_sup"] is not None else 0.0
    msy_mid = coeffs["bsy_mid"] * n * (inp.lx ** 2) * 1e6
    msy_sup = (coeffs["bsy_sup"] * n * (inp.lx ** 2) * 1e6) if coeffs["bsy_sup"] is not None else 0.0

    # Shear per metre width:
    num_cont_long = sum(1 for e in (inp.edges.get("top"), inp.edges.get("bottom")) if e == "continuous")
    if num_cont_long > 0:
        VEd = 0.6 * n * inp.lx * 1e3  # N/m
        shear_basis = "0.6·n·lx (continuous long edge)"
    else:
        VEd = 0.5 * n * inp.lx * 1e3  # N/m
        shear_basis = "0.5·n·lx (discontinuous long edge)"

    # Effective depths:
    phi_bx = inp.bottom_x.dia or 10
    phi_by = inp.bottom_y.dia or 10
    phi_tx = inp.top_x.dia or 10
    phi_ty = inp.top_y.dia or 10

    d_x = h - inp.cover - phi_bx / 2.0
    d_top_x = h - inp.cover - phi_tx / 2.0
    d_y = h - inp.cover - phi_bx - phi_by / 2.0
    if inp.top_x.dia and inp.top_x.dia != "none":
        d_top_y = h - inp.cover - inp.top_x.dia - phi_ty / 2.0
    else:
        d_top_y = h - inp.cover - phi_ty / 2.0

    # Shear check:
    d_shear = d_top_x if (num_cont_long > 0 and inp.top_x.dia and inp.top_x.dia != "none") else d_x
    vEd_mpa = VEd / (b * d_shear)
    rho_l = (inp.top_x.As if (num_cont_long > 0 and inp.top_x.dia and inp.top_x.dia != "none") else inp.bottom_x.As) / (b * d_shear)
    vrd_c = flexure.vrd_c(inp.concrete.fck, d_shear, rho_l)

    checks = []
    checks += _scope_checks(inp)
    checks += _cover_checks(inp)
    checks += _fire_checks(inp)

    # Actions check:
    bsx_sup_str = f"{coeffs['bsx_sup']:.4f}" if coeffs["bsx_sup"] is not None else "None"
    bsy_sup_str = f"{coeffs['bsy_sup']:.4f}" if coeffs["bsy_sup"] is not None else "None"
    act_lines = [
        f"Two-way slab panel: lx = {_m(inp.lx)} m, ly = {_m(inp.ly)} m (aspect ratio ly/lx = {ly_lx:.2f} ≤ 2.0)",
        f"Boundary conditions: top={inp.edges.get('top')}, bottom={inp.edges.get('bottom')}, left={inp.edges.get('left')}, right={inp.edges.get('right')}",
        f"Panel edge case: {case_label}",
        f"Design load: n = 1.35·({inp.gk:g} + {sw:.2f}) + 1.5·{inp.qk:g} = {n:.3f} kN/m²",
        f"Short-span coefficients: βsx,mid = {coeffs['bsx_mid']:.4f}, βsx,sup = {bsx_sup_str}",
        f"Long-span coefficients: βsy,mid = {coeffs['bsy_mid']:.4f}, βsy,sup = {bsy_sup_str}",
        f"Moments: msx,mid = {kNm(msx_mid)} kNm/m, msx,sup = {kNm(msx_sup)} kNm/m, msy,mid = {kNm(msy_mid)} kNm/m, msy,sup = {kNm(msy_sup)} kNm/m",
        f"Design shear: VEd = {kN(VEd)} kN/m ({shear_basis})",
    ]
    res_str = f"msx = {kNm(msx_mid)}/{kNm(msx_sup)} kNm/m, msy = {kNm(msy_mid)}/{kNm(msy_sup)} kNm/m"
    checks.append(CheckResult("actions", GROUPS[3], "Design actions", INFO, result=res_str, working=act_lines))

    # Bending checks:
    checks.append(_bending_check_two_way(inp, msx_mid, inp.bottom_x, "bottom_x", d_x, False, "Short span mid-span (bottom x)"))
    checks.append(_bending_check_two_way(inp, msx_sup, inp.top_x, "top_x", d_top_x, True, "Continuous long edge (top x)"))
    checks.append(_bending_check_two_way(inp, msy_mid, inp.bottom_y, "bottom_y", d_y, False, "Long span mid-span (bottom y)"))
    checks.append(_bending_check_two_way(inp, msy_sup, inp.top_y, "top_y", d_top_y, True, "Continuous short edge (top y)"))

    # Shear check:
    ok_shear = vEd_mpa <= vrd_c
    shear_lines = [
        f"Design shear force VEd = {kN(VEd)} kN/m ({shear_basis})",
        f"Effective depth d = {d_shear:.1f} mm; longitudinal ratio ρl = {rho_l:.4f} (≤ 0.02)",
        f"Applied shear stress: vEd = VEd / (b·d) = {vEd_mpa:.3f} MPa",
        f"Concrete shear capacity without links: vRd,c = {vrd_c:.3f} MPa ({'satisfied' if ok_shear else 'exceeded'})",
    ]
    checks.append(CheckResult("shear", GROUPS[5], "Shear resistance", PASS if ok_shear else FAIL,
                              result=f"{vEd_mpa:.3f} vs {vrd_c:.3f} MPa",
                              utilisation=vEd_mpa / vrd_c, working=shear_lines, target="slab.h",
                              note="" if ok_shear else "Increase the slab thickness (shear reinforcement is not usual in solid slabs)."))

    # Deflection check (on short span lx with d_x):
    K_sys = 1.0 if num_cont_long == 0 else (1.3 if num_cont_long == 1 else 1.5)
    K_bend = min(msx_mid / (b * d_x**2 * inp.concrete.fck), 0.168)
    z_defl = flexure.lever_arm(K_bend, d_x)
    As_req_defl = msx_mid / (inp.steel.fyd * z_defl)
    rho_defl = As_req_defl / (b * d_x)
    basic_defl = flexure.basic_span_depth(K_sys, inp.concrete.fck, rho_defl, rho_c=0.0)
    F1 = 1.0
    F2 = (7.0 / inp.lx) if (inp.lx > 7.0 and inp.partitions) else 1.0
    psi0, _, psi2 = psi_factors(inp.category)
    qp_ratio = (inp.gk + sw + psi2 * inp.qk) / max(n, 1e-6)
    sigma_s = inp.steel.fyd * qp_ratio * (As_req_defl / max(inp.bottom_x.As, 1.0))
    F3 = min(310.0 / max(sigma_s, 1.0), 1.5)
    limiting_defl = basic_defl * F1 * F2 * F3
    actual_defl = (inp.lx * 1000.0) / d_x
    ok_defl = actual_defl <= limiting_defl
    defl_lines = [
        f"Two-way panel short span lx = {_m(inp.lx)} m, d = {d_x:.1f} mm, K = {K_sys:g} ({num_cont_long} continuous long edge{'s' if num_cont_long != 1 else ''})",
        f"Basic span-to-depth ratio: (l/d)basic = {basic_defl:.1f}",
        f"Modification factors: F1 = 1.0; F2 = {F2:.3f}; F3 = {F3:.3f} (service steel stress σs = {sigma_s:.1f} MPa)",
        f"Limiting l/d = {limiting_defl:.1f}; Actual span-to-depth ratio: lx/d = {actual_defl:.1f} ({'satisfied' if ok_defl else 'exceeded'})",
    ]
    checks.append(CheckResult("deflection", GROUPS[6], "Deflection (short span lx)",
                              PASS if ok_defl else FAIL, result=f"{actual_defl:.1f} vs {limiting_defl:.1f}",
                              utilisation=actual_defl / limiting_defl, working=defl_lines, target="slab.h",
                              note="" if ok_defl else "Increase the slab thickness or provide more reinforcement."))

    # Detailing checks:
    checks += _detailing_checks(inp, is_two_way=True)

    summary = summarise(checks)
    plots = {
        "section": {
            "shape": "rectangular", "slab_type": "two_way", "b": b, "h": h, "cover": inp.cover,
            "bottom_x": {"dia": inp.bottom_x.dia, "s": inp.bottom_x.spacing, "As": inp.bottom_x.As},
            "bottom_y": {"dia": inp.bottom_y.dia, "s": inp.bottom_y.spacing, "As": inp.bottom_y.As},
            "top_x": {"dia": inp.top_x.dia, "s": inp.top_x.spacing, "As": inp.top_x.As},
            "top_y": {"dia": inp.top_y.dia, "s": inp.top_y.spacing, "As": inp.top_y.As},
        },
        "panel": {
            "lx": inp.lx,
            "ly": inp.ly,
            "edges": inp.edges,
            "case": {"id": case_id, "label": case_label},
            "coefficients": coeffs,
            "moments": {
                "msx_mid": msx_mid / 1e6,
                "msx_sup": msx_sup / 1e6,
                "msy_mid": msy_mid / 1e6,
                "msy_sup": msy_sup / 1e6,
            },
            "shears": {
                "VEd": VEd / 1e3,
                "vEd": vEd_mpa,
                "vRd_c": vrd_c,
                "basis": shear_basis,
            },
        },
    }

    derived = {
        "slab_type": "two_way",
        "h": inp.h,
        "lx": inp.lx,
        "ly": inp.ly,
        "case": case_id,
        "case_label": case_label,
        "MEd_sag": msx_mid / 1e6,
        "MEd_hog": msx_sup / 1e6,
        "VEd": VEd / 1e3,
        "msx_mid": msx_mid / 1e6,
        "msx_sup": msx_sup / 1e6,
        "msy_mid": msy_mid / 1e6,
        "msy_sup": msy_sup / 1e6,
        "bottom_x": {"dia": inp.bottom_x.dia, "s": inp.bottom_x.spacing, "As": inp.bottom_x.As},
        "bottom_y": {"dia": inp.bottom_y.dia, "s": inp.bottom_y.spacing, "As": inp.bottom_y.As},
        "top_x": {"dia": inp.top_x.dia, "s": inp.top_x.spacing, "As": inp.top_x.As},
        "top_y": {"dia": inp.top_y.dia, "s": inp.top_y.spacing, "As": inp.top_y.As},
    }

    checks_dict = [CheckDict(c.to_dict()) for c in checks]
    return {
        "element": "slab",
        "project": inp.project,
        "summary": summary,
        "verdict": summary["verdict"],
        "groups": list(GROUPS),
        "checks": checks_dict,
        "working": checks_dict,
        "inputs": _input_echo(inp, {"sw": sw}),
        "input_echo": _input_echo(inp, {"sw": sw}),
        "assumptions": list(ASSUMPTIONS),
        "derived": derived,
        "plots": plots,
    }


def _bending_check_two_way(inp, M_ed, layer, name, d, is_hogging, position_label):
    b = 1000.0
    fck = inp.concrete.fck
    fyd = inp.steel.fyd

    if M_ed <= 0:
        return CheckResult(f"bending_{name}", GROUPS[4], f"Bending ({position_label})", NA,
                           result="0.00 kNm/m",
                           working=[f"No moment at {position_label} (discontinuous edge / not designed for); check not applicable."])

    if not layer.dia or layer.dia == "none" or not layer.spacing:
        return CheckResult(f"bending_{name}", GROUPS[4], f"Bending ({position_label})", FAIL,
                           result="No bars provided",
                           working=[f"Design moment MEd = {kNm(M_ed)} kNm/m at {position_label}.",
                                    f"No {name} bars entered."],
                           target=f"reinforcement.{name}_dia",
                           note=f"Add bars for {position_label}.")

    K = M_ed / (b * d**2 * fck)
    kp = flexure.k_prime(1.0, uk_limit=True)

    if K > kp:
        lines = [
            f"Design moment MEd = {kNm(M_ed)} kNm/m per metre width at {position_label}",
            f"Effective depth d = {d:.1f} mm; concrete fck = {fck:g} MPa",
            f"K = MEd / (b·d²·fck) = {K:.4f} > K' = {kp:.3f}",
            "Compression reinforcement is not permitted in solid slabs.",
        ]
        return CheckResult(f"bending_{name}", GROUPS[4], f"Bending ({position_label})", FAIL,
                           result=f"K = {K:.3f} > K' = {kp:.3f}",
                           utilisation=K / kp, working=lines, target="slab.h",
                           note="Increase the slab thickness (compression reinforcement is not used in slabs).")

    z = flexure.lever_arm(K, d)
    As_req = M_ed / (fyd * z)
    As_prov = layer.As
    ok = As_prov >= As_req

    lines = [
        f"Design moment MEd = {kNm(M_ed)} kNm/m per metre width at {position_label}",
        f"Effective depth d = {d:.1f} mm; lever arm z = {z:.1f} mm (≤ 0.95d = {0.95 * d:.1f} mm)",
        f"K = MEd / (b·d²·fck) = {K:.4f} ≤ K' = {kp:.3f}",
        f"Required tension steel: As,req = MEd / (fyd·z) = {M_ed:.0f} / ({fyd:.1f} × {z:.1f}) = {As_req:.0f} mm²/m",
        f"Provided reinforcement: {layer.label} → As,prov = {As_prov:.0f} mm²/m ({'satisfied' if ok else 'insufficient'})",
    ]
    return CheckResult(f"bending_{name}", GROUPS[4], f"Bending ({position_label})", PASS if ok else FAIL,
                       result=f"{As_prov:.0f} vs {As_req:.0f} mm²/m",
                       utilisation=As_req / max(As_prov, 1.0),
                       working=lines, target=f"reinforcement.{name}_s",
                       note="" if ok else "Increase bar diameter or decrease bar spacing.")



def analyse_input(data):
    """Analysis only, with design fields replaced by safe defaults (for live preview)."""
    d = _upgrade(data)
    d["reinforcement"] = {
        "bottom_x_dia": 10, "bottom_x_s": 200,
        "bottom_y_dia": 10, "bottom_y_s": 200,
        "top_x_dia": 10, "top_x_s": 200,
        "top_y_dia": 10, "top_y_s": 200,
        "cover": 25, "delta_c_dev": 10,
    }
    d["durability"] = {"exposure": "XC1", "cement_group": "All", "fire_period": "none"}
    mat = d.setdefault("materials", {})
    conc = mat.get("concrete", "C30/37") if isinstance(mat, dict) else "C30/37"
    d["materials"] = {"concrete": conc, "fyk": 500, "ductility": "B", "dg": 20}

    inp = parse_input(d)
    if inp.slab_type == "one_way":
        act = analyse_one_way(inp)
        plots = _plots_one_way(inp, act)
        plots["loads"] = {
            "w": 1.35 * act["n_g"] + 1.5 * act["n_q"],
            "sw": act["sw"],
            "g": act["n_g"],
            "q": act["n_q"],
        }
        return plots
    else:
        res = _check_two_way(inp)
        plots = res["plots"]
        sw = (CONCRETE_DENSITY * inp.h / 1000.0) if inp.self_weight else 0.0
        n_g = inp.gk + sw
        plots["loads"] = {
            "w": 1.35 * n_g + 1.5 * inp.qk,
            "sw": sw,
            "g": n_g,
            "q": inp.qk,
        }
        return plots
