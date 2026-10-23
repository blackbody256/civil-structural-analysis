"""Column check: braced or unbraced rectangular columns to BS EN 1992-1-1.

check_column(data) validates a request, runs every check in the order of the column
design procedure and returns a JSON-ready report. Internally lengths are in mm,
forces in N and moments in N·mm; the report uses kN, kNm and mm.
"""
import math
from dataclasses import dataclass

from . import durability, fire, tables
from . import slenderness as sl
from .geometry import RectSection
from .inputs import Reader, ValidationError
from .interaction import EPS_C3, SectionModel
from .materials import BAR_SIZES, CONCRETE_TABLE, DUCTILITY_CLASSES, LINK_SIZES, Concrete, Reinforcement
from .references import refs
from .results import FAIL, INFO, NA, PASS, WARN, CheckResult, summarise

AXES = ("y", "z")
AXIS_NAME = {"y": "y–y", "z": "z–z"}
DIM_SYMBOL = {"y": "h", "z": "b"}

GROUPS = (
    "Scope & materials",
    "Durability & cover",
    "Fire resistance",
    "Slenderness",
    "Design moments",
    "Resistance",
    "Detailing",
)

ASSUMPTIONS = [
    "Design to BS EN 1992-1-1 with UK National Annex values.",
    "Resistance by strain compatibility with a rectangular stress block of depth 0.8x at fcd; "
    "εcu = 0.0035 with the neutral axis in the section and 0.00175 at mid-depth otherwise; bars are "
    "modelled at their actual positions; concrete displaced by bars is not deducted.",
    "First-order moments include the geometric imperfection ei = max(l0/400, h/30, 20 mm).",
    "Second-order effects by the nominal curvature method when λ ≥ λlim.",
    "Durability covers follow BS 8500 for a 50-year working life and 20 mm maximum aggregate.",
    "Fire resistance by the tabulated method A of BS EN 1992-1-2, valid for braced columns only.",
]


# ---------------------------------------------------------------- input parsing

class _Reader(Reader):
    """The shared reader plus end stiffness values, which may be the word 'pinned'."""

    def stiffness(self, path):
        raw = self.raw(path)
        if isinstance(raw, str) and raw.strip().lower() == "pinned":
            return sl.PINNED
        return self.number(path, lo=0, hi=1e6, default=1.0)


@dataclass
class AxisRestraint:
    method: str           # "k" (end stiffness) or "factor" (F entered / Fig 5 case)
    k_top: float
    k_bottom: float
    F: float | None
    case: str | None


@dataclass
class AxisMoments:
    m_top: float          # N·mm, magnitude
    m_bottom: float
    curvature: str        # "single" or "double"


@dataclass
class ColumnInput:
    project: dict
    concrete: Concrete
    steel: Reinforcement
    dg: float
    section: RectSection
    l: float
    cross_ties: bool
    delta_c_dev: float
    braced: bool
    restraint: dict
    n_ed: float
    moments: dict
    bending: str              # "uniaxial" (moments about y–y only) or "biaxial"
    phi_ef: float
    lambda_lim_method: str
    exposure: str
    cement_group: str
    fire_period: str
    fire_exposure: str
    mu_fi: float
    floor: str


def parse_input(data):
    r = _Reader(data)
    project = {k: r.text(f"project.{k}") for k in ("name", "ref", "engineer", "date")}

    concrete_class = r.choice("materials.concrete", CONCRETE_TABLE)
    fyk = r.number("materials.fyk", lo=200, hi=700)
    ductility = r.choice("materials.ductility", DUCTILITY_CLASSES, default="B")
    dg = r.number("materials.dg", lo=5, hi=63, default=20)
    gamma_c = r.number("materials.gamma_c", lo=1.0, hi=2.0, default=1.5)
    gamma_s = r.number("materials.gamma_s", lo=1.0, hi=1.5, default=1.15)
    alpha_cc = r.number("materials.alpha_cc", lo=0.8, hi=1.0, default=0.85)

    b = r.number("geometry.b", lo=100, hi=3000)
    h = r.number("geometry.h", lo=100, hi=3000)
    length = r.number("geometry.l", lo=0.5, hi=30)

    bar_dia = r.choice("reinforcement.bar_dia", BAR_SIZES, default=16)
    n_b = r.number("reinforcement.n_b", lo=2, hi=20, integer=True)
    n_h = r.number("reinforcement.n_h", lo=2, hi=20, integer=True)
    link_dia = r.choice("reinforcement.link_dia", LINK_SIZES, default=8)
    cross_ties = r.flag("reinforcement.cross_ties")
    cover = r.number("reinforcement.cover", lo=0, hi=150)
    delta_c_dev = r.number("reinforcement.delta_c_dev", lo=0, hi=20, default=10)

    braced = r.flag("restraint.braced", default=True)
    restraint = {}
    for axis in AXES:
        base = f"restraint.{axis}"
        method = r.choice(f"{base}.method", ("k", "factor"), default="k")
        if method == "factor":
            case = r.raw(f"{base}.case")
            case = case if case in sl.FIG5_CASES else None
            factor = r.number(f"{base}.F", lo=0.3, hi=5.0)
            restraint[axis] = AxisRestraint("factor", sl.PINNED, sl.PINNED, factor, case)
        else:
            k_top, k_bottom = r.stiffness(f"{base}.k_top"), r.stiffness(f"{base}.k_bottom")
            if not braced and math.isinf(k_top) and math.isinf(k_bottom):
                r.errors[f"{base}.k_top"] = "An unbraced column pinned at both ends is a mechanism."
            restraint[axis] = AxisRestraint("k", k_top, k_bottom, None, None)

    n_ed = r.number("actions.NEd", lo=0.001, hi=1e6)
    moments = {}
    for axis in AXES:
        prefix = f"actions.M{axis}"
        moments[axis] = AxisMoments(
            abs(r.number(f"{prefix}_top", lo=-1e6, hi=1e6, default=0.0)) * 1e6,
            abs(r.number(f"{prefix}_bottom", lo=-1e6, hi=1e6, default=0.0)) * 1e6,
            r.choice(f"{prefix}_curvature", ("single", "double"), default="single"),
        )
    has = {a: moments[a].m_top > 0 or moments[a].m_bottom > 0 for a in AXES}
    bending = r.choice("actions.bending", ("uniaxial", "biaxial"), default="biaxial" if has["z"] else "uniaxial")
    if bending == "uniaxial":
        moments["z"] = AxisMoments(0.0, 0.0, "single")
    else:
        if not has["y"]:
            r.errors["actions.My_top"] = "Biaxial bending needs a moment about y–y."
        if not has["z"]:
            r.errors["actions.Mz_top"] = "Enter a moment about z–z, or choose uniaxial bending."
    phi_ef = r.number("actions.phi_ef", lo=0, hi=6, default=1.7)
    lambda_lim_method = r.choice("actions.lambda_lim_method", ("simplified", "refined"), default="simplified")

    exposure_ids = [row["id"] for row in durability.rows_for("vertical")]
    exposure = r.choice("durability.exposure", exposure_ids, default="XC1")
    cement_group = r.choice("durability.cement_group",
                            list(durability.ROWS_BY_ID[exposure]["groups"]),
                            default=next(iter(durability.ROWS_BY_ID[exposure]["groups"])))
    fire_period = r.choice("durability.fire_period", fire.FIRE_PERIODS, default="none")
    fire_exposure = r.choice("durability.fire_exposure", ("multi", "one"), default="multi")
    mu_fi = r.choice("durability.mu_fi", (0.5, 0.7), default=0.7)
    floor = r.choice("durability.floor", ("intermediate", "top"), default="intermediate")

    if not r.errors:
        axis_distance = cover + link_dia + bar_dia / 2
        if 2 * axis_distance >= min(b, h):
            r.errors["reinforcement.cover"] = "Cover, link and bar do not fit within the section."
    if r.errors:
        raise ValidationError(r.errors)

    return ColumnInput(
        project=project,
        concrete=Concrete.from_class(concrete_class, gamma_c, alpha_cc),
        steel=Reinforcement(fyk, ductility, gamma_s),
        dg=dg,
        section=RectSection(b, h, cover, link_dia, bar_dia, n_b, n_h),
        l=length * 1000.0,
        cross_ties=cross_ties,
        delta_c_dev=delta_c_dev,
        braced=braced,
        restraint=restraint,
        n_ed=n_ed * 1e3,
        moments=moments,
        phi_ef=phi_ef,
        lambda_lim_method=lambda_lim_method,
        bending=bending,
        exposure=exposure,
        cement_group=cement_group,
        fire_period=fire_period,
        fire_exposure=fire_exposure,
        mu_fi=mu_fi,
        floor=floor,
    )


# ---------------------------------------------------------------- formatting

def kN(n):
    return f"{n / 1e3:.1f}"


def kNm(m):
    return f"{m / 1e6:.1f}"


def _k_text(k):
    return "pinned" if math.isinf(k) else f"{k:.2f}"


def _cmp(ok):
    return "≤" if ok else ">"


# ---------------------------------------------------------------- axis analysis

@dataclass
class Axis:
    name: str
    depth: float
    width: float
    F: float
    F_table: float | None
    l0: float
    lam: float
    e_i: float
    m01: float
    m02: float
    rm: float
    A: float
    B: float
    C: float
    lam_lim: float
    slender: bool
    d: float
    i_s: float
    second: dict | None
    m_ed: float
    model: SectionModel
    m_rd: float | None


def _effective_length_factor(inp, r):
    if r.method == "factor":
        return r.F, None
    if inp.braced:
        return sl.factor_braced(r.k_top, r.k_bottom), tables.table4_factor(r.k_top, r.k_bottom)
    return sl.factor_unbraced(r.k_top, r.k_bottom), None


def _second_order(inp, ax_lam, d, l0, m01, m02, n, omega):
    return sl.nominal_curvature(
        n=n, omega=omega, fck=inp.concrete.fck, lam=ax_lam, phi_ef=inp.phi_ef,
        eps_yd=inp.steel.eps_yd, d=d, l0=l0, n_ed=inp.n_ed, m01=m01, m02=m02)


def analyse_axis(inp, axis, n, omega):
    sec, conc, steel = inp.section, inp.concrete, inp.steel
    depth, width, layers = sec.layers(axis)
    r = inp.restraint[axis]
    F, F_table = _effective_length_factor(inp, r)
    l0 = F * inp.l
    lam = sl.slenderness(l0, depth)
    e_i = sl.imperfection_eccentricity(l0, depth)
    act = inp.moments[axis]
    m01, m02 = sl.first_order_moments(act.m_top, act.m_bottom, act.curvature, inp.n_ed, e_i)
    rm = m01 / m02
    C = 1.7 - rm if inp.braced else 0.7
    if inp.lambda_lim_method == "refined":
        A, B = 1.0 / (1.0 + 0.2 * inp.phi_ef), math.sqrt(1.0 + 2.0 * omega)
    else:
        A, B = 0.7, 1.1
    lam_lim = sl.lambda_limit(A, B, C, n)
    slender = lam >= lam_lim
    i_s = sec.steel_gyration_radius(axis)
    d = depth / 2 + i_s
    second = _second_order(inp, lam, d, l0, m01, m02, n, omega) if slender else None
    m_ed = second["MEd"] if slender else m02
    model = SectionModel(depth, width, layers, conc.fcd, steel.fyd, steel.Es)
    return Axis(axis, depth, width, F, F_table, l0, lam, e_i, m01, m02, rm, A, B, C, lam_lim,
                slender, d, i_s, second, m_ed, model, model.moment_capacity(inp.n_ed))


def _design_moment_for(inp, ax, n, omega):
    if not ax.slender:
        return ax.m02
    return _second_order(inp, ax.lam, ax.d, ax.l0, ax.m01, ax.m02, n, omega)["MEd"]


def required_steel(inp, ax, n):
    """As,req for the same bar layout, iterating Kr with the steel area as in Fig 3.

    Returns None when no amount of steel in this layout carries NEd.
    """
    sec, conc, steel = inp.section, inp.concrete, inp.steel
    depth, width, layers = sec.layers(ax.name)

    def adequate(scale):
        model = SectionModel(depth, width, layers, conc.fcd, steel.fyd, steel.Es, steel_scale=scale)
        m_rd = model.moment_capacity(inp.n_ed)
        if m_rd is None:
            return False
        omega = scale * sec.As * steel.fyd / (sec.Ac * conc.fcd)
        return m_rd >= _design_moment_for(inp, ax, n, omega)

    if adequate(0.0):
        return 0.0
    hi = 1.0
    while not adequate(hi):
        hi *= 2.0
        if hi > 64:
            return None
    lo = 0.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if adequate(mid):
            hi = mid
        else:
            lo = mid
    return hi * sec.As


def _moment_without_imperfection(inp, ax):
    act = inp.moments[ax.name]
    m01, m02 = sl.first_order_moments(act.m_top, act.m_bottom, act.curvature, inp.n_ed, 0.0)
    if not ax.slender:
        return m02
    m2 = ax.second["M2"]
    m0e = max(0.6 * m02 + 0.4 * m01, 0.4 * m02)
    return max(m02, m0e + m2, m01 + 0.5 * m2)


# ---------------------------------------------------------------- checks

def _scope_checks(inp):
    conc, steel, sec = inp.concrete, inp.steel, inp.section
    steel_ok = 400 <= steel.fyk <= 600
    k_req, eps_req = DUCTILITY_CLASSES[steel.ductility]
    scope = CheckResult(
        "scope", GROUPS[0], "Materials within scope", PASS if steel_ok else FAIL,
        result=f"{conc.name}, fyk = {steel.fyk:g} MPa",
        working=[
            f"Concrete {conc.name}: fck = {conc.fck:g} MPa ≤ 50 MPa (classes up to C50/60)",
            f"fcd = αcc·fck/γc = {conc.alpha_cc:g} × {conc.fck:g} / {conc.gamma_c:g} = {conc.fcd:.2f} MPa",
            f"Reinforcement fyk = {steel.fyk:g} MPa; EC2 covers 400 ≤ fyk ≤ 600 MPa",
            f"fyd = fyk/γs = {steel.fyk:g} / {steel.gamma_s:g} = {steel.fyd:.1f} MPa",
            f"Ductility class {steel.ductility}: k {k_req}, εuk {eps_req} %",
        ],
        refs=refs("ch3_scope", "ch1_scope_steel", "ch2_concrete", "ch2_steel"),
        note="" if steel_ok else "Eurocode 2 gives no rules for plain or mild-steel bars; "
                                 "the remaining results are indicative only.",
        target="section",
    )
    long_side, short_side = max(sec.b, sec.h), min(sec.b, sec.h)
    ratio = long_side / short_side
    wall = CheckResult(
        "wall", GROUPS[0], "Column, not a wall", PASS if ratio <= 4 else WARN,
        result=f"{ratio:.2f} {_cmp(ratio <= 4)} 4", value=ratio, limit=4.0,
        working=[f"Long side / short side = {long_side:.0f} / {short_side:.0f} = {ratio:.2f}"],
        refs=refs("ch5_walls"),
        note="" if ratio <= 4 else "A section longer than four times its thickness is a wall; "
                                   "wall rules for reinforcement and fire resistance apply.",
        target="section",
    )
    return [scope, wall]


def _cover_checks(inp):
    sec, conc = inp.section, inp.concrete
    dc = inp.delta_c_dev
    row = durability.ROWS_BY_ID[inp.exposure]
    res = durability.durability_cover(inp.exposure, inp.cement_group, conc.name)
    head = [f"Exposure {row['classes']}: {row['example']} (cement group: {inp.cement_group})"]
    if res["status"] == "ok":
        spec = res["spec"]
        required = res["cover"] + dc
        ok = sec.cover >= required
        mix = f"max w/c {spec['wc']:.2f}, min cement {spec['cement']} kg/m³"
        if spec["designated"]:
            mix += f" or {spec['designated']}"
        if spec["notes"]:
            mix += f" ({spec['notes']})"
        notes = [row.get("note", "")]
        if not ok and res["bs8500_below"]:
            notes.append(f"BS 8500 may allow {res['bs8500_below'][-1]} + Δcdev with a higher concrete class.")
        dur = CheckResult(
            "cover_durability", GROUPS[1], "Cover for durability", PASS if ok else FAIL,
            result=f"{sec.cover:g} {'≥' if ok else '<'} {required:g} mm", value=sec.cover, limit=required,
            unit="mm", utilisation=required / sec.cover if sec.cover else math.inf,
            working=head + [
                f"{conc.name} needs a nominal cover of {res['cover']} + Δcdev for this exposure "
                f"(minimum class {spec['class']} at that cover)",
                f"cnom,req = {res['cover']} + {dc:g} = {required:g} mm; provided cnom = {sec.cover:g} mm",
                f"Specify concrete with {mix}",
            ],
            refs=refs("ch2_table8", "ch2_cover"), note=" ".join(n for n in notes if n), target="cover")
    else:
        spec = res["spec"]
        dur = CheckResult(
            "cover_durability", GROUPS[1], "Cover for durability", FAIL,
            result=f"{conc.name} below minimum {spec['class']}",
            working=head + [f"This exposure needs at least {spec['class']} "
                            f"(with {res['cover']} + Δcdev cover); {conc.name} is not recommended."],
            refs=refs("ch2_table8"), note="Increase the concrete strength class.", target="cover")

    extra = 5 if inp.dg > 32 else 0
    c_b_link = sec.link_dia + extra
    req_link = max(c_b_link, 10) + dc
    ok_link = sec.cover >= req_link
    bond = CheckResult(
        "cover_bond", GROUPS[1], "Cover for bond (links)", PASS if ok_link else FAIL,
        result=f"{sec.cover:g} {'≥' if ok_link else '<'} {req_link:g} mm", value=sec.cover, limit=req_link,
        unit="mm", utilisation=req_link / sec.cover if sec.cover else math.inf,
        working=[
            f"cmin,b = φlink{' + 5 (aggregate > 32 mm)' if extra else ''} = {c_b_link:g} mm; "
            f"absolute minimum 10 mm",
            f"cnom ≥ max({c_b_link:g}, 10) + Δcdev = {req_link:g} mm; provided {sec.cover:g} mm",
        ],
        refs=refs("ch2_cover_bond", "ch2_cover", clauses=("4.4.1.2",)), target="cover")

    c_main = sec.cover + sec.link_dia
    req_main = sec.bar_dia + extra + dc
    ok_main = c_main >= req_main
    main = CheckResult(
        "cover_main", GROUPS[1], "Cover to main bars", PASS if ok_main else FAIL,
        result=f"{c_main:g} {'≥' if ok_main else '<'} {req_main:g} mm", value=c_main, limit=req_main,
        unit="mm", utilisation=req_main / c_main,
        working=[
            f"Cover to main bars = cnom + φlink = {sec.cover:g} + {sec.link_dia:g} = {c_main:g} mm",
            f"Required ≥ φ + Δcdev = {sec.bar_dia:g}{' + 5' if extra else ''} + {dc:g} = {req_main:g} mm",
        ],
        refs=refs("ch10_cover", "ch2_cover_bond"), target="cover")
    return [dur, bond, main]


def _fire_checks(inp):
    sec = inp.section
    if inp.fire_period == "none":
        na = "No fire resistance period specified."
        return [CheckResult("fire_table", GROUPS[2], "Fire resistance", NA, result="Not required",
                            note=na, refs=refs("ch5_table2"), target="cover"),
                CheckResult("fire_validity", GROUPS[2], "Conditions for the fire table", NA, result="Not required",
                            note=na, refs=refs("ch5_table2"))]
    if not inp.braced:
        na = "The tabulated fire method covers braced columns only."
        return [CheckResult("fire_table", GROUPS[2], "Fire resistance", NA, result="Not applicable",
                            note=na, refs=refs("ch5_table2", "ch5_unbraced"), target="cover"),
                CheckResult("fire_validity", GROUPS[2], "Conditions for the fire table", NA, result="Not applicable",
                            note=na, refs=refs("ch5_table2"))]

    b_min, a = min(sec.b, sec.h), sec.axis_distance
    ok, gov, evaluated = fire.check_column_fire(
        inp.fire_period, inp.fire_exposure, inp.mu_fi, b_min, a, sec.n_bars)
    side = "more than one side" if inp.fire_exposure == "multi" else "one side"
    mu = f", μfi = {inp.mu_fi:g}" if inp.fire_exposure == "multi" else ""
    lines = [
        f"{inp.fire_period}, column exposed on {side}{mu}",
        f"a = cnom + φlink + φ/2 = {sec.cover:g} + {sec.link_dia:g} + {sec.bar_dia:g}/2 = {a:.0f} mm; "
        f"bmin = {b_min:.0f} mm; {sec.n_bars} bars",
    ]
    for o in evaluated:
        extra = f", minimum {o['min_bars']} bars" if o["min_bars"] else ""
        extra += f", {o['note']}" if o["note"] else ""
        lines.append(f"Option bmin/a = {o['b_min']}/{o['a']}{extra}: {'satisfied' if o['ok'] else 'not satisfied'}")
    table = CheckResult(
        "fire_table", GROUPS[2], f"Fire resistance {inp.fire_period}", PASS if ok else FAIL,
        result=f"{b_min:.0f}/{a:.0f} vs {gov['b_min']}/{gov['a']} mm",
        utilisation=max(gov["b_min"] / b_min, gov["a"] / a), working=lines,
        refs=refs("ch5_table2"), target="cover",
        note="" if ok else "Increase the column size or the axis distance a (larger cover).")

    l0_fi = (0.5 if inp.floor == "intermediate" else 0.7) * inp.l
    conditions = [(f"l0,fi = {0.5 if inp.floor == 'intermediate' else 0.7:g} × l = {l0_fi:.0f} mm "
                   f"({inp.floor} floor) ≤ 3000 mm", l0_fi <= 3000)]
    for axis in AXES:
        depth = sec.h if axis == "y" else sec.b
        act = inp.moments[axis]
        e = max(act.m_top, act.m_bottom) / inp.n_ed
        conditions.append((f"e{axis} = M0Ed/NEd = {e:.0f} mm ≤ 0.15·{DIM_SYMBOL[axis]} = {0.15 * depth:.0f} mm",
                           e <= 0.15 * depth))
    rho = sec.As / sec.Ac
    conditions.append((f"As/Ac = {100 * rho:.2f} % ≤ 4 %", rho <= 0.04))
    valid = all(ok for _, ok in conditions)
    validity = CheckResult(
        "fire_validity", GROUPS[2], "Conditions for the fire table", PASS if valid else WARN,
        result="Conditions met" if valid else "Outside the table limits",
        working=[f"{text}: {'yes' if ok else 'no'}" for text, ok in conditions],
        refs=refs("ch5_table2"),
        note="" if valid else "The tabulated method is not valid here; use method B or BS EN 1992-1-2 Annex C.")
    return [table, validity]


def _effective_length_lines(inp, ax):
    r = inp.restraint[ax.name]
    if r.method == "factor":
        source = sl.FIG5_CASES[r.case][0].lower() if r.case else "entered directly"
        lines = [f"Effective length factor F = {ax.F:.2f} ({source})"]
    elif inp.braced:
        lines = [f"Braced; end stiffness k1 (top) = {_k_text(r.k_top)}, k2 (bottom) = {_k_text(r.k_bottom)}",
                 f"F = 0.5·√[(1 + k1/(0.45 + k1))·(1 + k2/(0.45 + k2))] = {ax.F:.3f} "
                 f"(braced)"]
    else:
        lines = [f"Unbraced; end stiffness k1 (top) = {_k_text(r.k_top)}, k2 (bottom) = {_k_text(r.k_bottom)}",
                 f"F = max{{√(1 + 10·k1·k2/(k1 + k2)); (1 + k1/(1 + k1))·(1 + k2/(1 + k2))}} = {ax.F:.3f} "
                 f"(unbraced)"]
    lines.append(f"l0 = F·l = {ax.F:.3f} × {inp.l:.0f} = {ax.l0:.0f} mm")
    return lines


def _slenderness_checks(inp, axes, n):
    out = []
    for ax in axes.values():
        sym = DIM_SYMBOL[ax.name]
        c_line = (f"rm = M01/M02 = {kNm(ax.m01)} / {kNm(ax.m02)} = {ax.rm:.3f}; C = 1.7 − rm = {ax.C:.3f}"
                  if inp.braced else "Unbraced column: C = 0.7")
        ab = "default values" if inp.lambda_lim_method == "simplified" else "from φef and ω"
        verdict = ("slender: second-order effects are added" if ax.slender
                   else "not slender: second-order effects ignored, MEd = M02")
        out.append(CheckResult(
            f"slenderness_{ax.name}", GROUPS[3], f"Slenderness about {AXIS_NAME[ax.name]}", INFO,
            result=f"λ = {ax.lam:.1f} {'≥' if ax.slender else '<'} λlim = {ax.lam_lim:.1f}: "
                   f"{'slender' if ax.slender else 'not slender'}",
            value=ax.lam, limit=ax.lam_lim,
            working=_effective_length_lines(inp, ax) + [
                f"λ = 3.46·l0/{sym} = 3.46 × {ax.l0:.0f} / {ax.depth:.0f} = {ax.lam:.1f}",
                f"n = NEd/(Ac·fcd) = {kN(inp.n_ed)}×10³ / ({inp.section.Ac:.0f} × {inp.concrete.fcd:.2f}) = {n:.3f}",
                c_line,
                f"A = {ax.A:.2f}, B = {ax.B:.2f} ({ab})",
                f"λlim = 20·A·B·C/√n = 20 × {ax.A:.2f} × {ax.B:.2f} × {ax.C:.3f} / √{n:.3f} = {ax.lam_lim:.1f}",
                f"λ = {ax.lam:.1f} {'≥' if ax.slender else '<'} λlim = {ax.lam_lim:.1f}: {verdict}",
            ],
            refs=refs("ch5_fig2", "ch5_eff_length", "ch5_table4", "ch5_slenderness",
                      clauses=("5.8.3.1", "5.8.3.2")),
            target="elevation"))
    return out


def _moment_checks(inp, axes, n, omega):
    out = []
    for ax in axes.values():
        act = inp.moments[ax.name]
        sym = DIM_SYMBOL[ax.name]
        sign = "+" if act.curvature == "single" else "−"
        applied = (f"Mtop = {kNm(act.m_top)} kNm, Mbottom = {kNm(act.m_bottom)} kNm ({act.curvature} curvature)"
                   if inp.bending == "biaxial" or ax.name == "y"
                   else "Uniaxial bending: no applied moment about z–z, only the imperfection")
        lines = [
            applied,
            f"ei = max(l0/400, {sym}/30, 20) = max({ax.l0 / 400:.1f}, {ax.depth / 30:.1f}, 20) = {ax.e_i:.1f} mm",
            f"M02 = max|M| + ei·NEd = {kNm(max(act.m_top, act.m_bottom))} + {ax.e_i:.1f} × {kN(inp.n_ed)}/10³ "
            f"= {kNm(ax.m02)} kNm",
            f"M01 = {sign}min|M| + ei·NEd = {kNm(ax.m01)} kNm",
        ]
        if ax.slender:
            s = ax.second
            lines += [
                f"ω = As·fyd/(Ac·fcd) = {inp.section.As:.0f} × {inp.steel.fyd:.1f} / "
                f"({inp.section.Ac:.0f} × {inp.concrete.fcd:.2f}) = {omega:.3f}; nu = 1 + ω = {s['n_u']:.3f}",
                f"Kr = (nu − n)/(nu − nbal) = ({s['n_u']:.3f} − {n:.3f})/({s['n_u']:.3f} − 0.4) = {s['Kr']:.3f} (≤ 1)",
                f"β = 0.35 + fck/200 − λ/150 = 0.35 + {inp.concrete.fck:g}/200 − {ax.lam:.1f}/150 = {s['beta']:.3f}",
                f"Kφ = 1 + β·φef = 1 + {s['beta']:.3f} × {inp.phi_ef:.2f} = {s['Kphi']:.3f} (≥ 1)",
                f"d = {sym}/2 + i_s = {ax.depth / 2:.0f} + {ax.i_s:.1f} = {ax.d:.1f} mm",
                f"e2 = 0.1·Kr·Kφ·fyd/(0.45·d·Es)·l0² = 0.1 × {s['Kr']:.3f} × {s['Kphi']:.3f} × {inp.steel.fyd:.1f}"
                f" / (0.45 × {ax.d:.1f} × {inp.steel.Es:.0f}) × {ax.l0:.0f}² = {s['e2']:.1f} mm",
                f"M2 = NEd·e2 = {kN(inp.n_ed)} × {s['e2']:.1f}/10³ = {kNm(s['M2'])} kNm",
                f"M0e = 0.6·M02 + 0.4·M01 ≥ 0.4·M02 = {kNm(s['M0e'])} kNm",
                f"MEd = max(M02, M0e + M2, M01 + 0.5·M2) = max({kNm(ax.m02)}, {kNm(s['M0e'] + s['M2'])}, "
                f"{kNm(ax.m01 + 0.5 * s['M2'])}) = {kNm(ax.m_ed)} kNm",
            ]
        else:
            lines.append(f"Not slender about {AXIS_NAME[ax.name]}: MEd = M02 = {kNm(ax.m_ed)} kNm")
        out.append(CheckResult(
            f"moments_{ax.name}", GROUPS[4], f"Design moment about {AXIS_NAME[ax.name]}", INFO,
            result=f"MEd = {kNm(ax.m_ed)} kNm", value=ax.m_ed / 1e6, unit="kNm", working=lines,
            refs=refs("ch5_design_moments", "ch5_fig3", "ch5_creep", clauses=("5.8.8",)),
            target="elevation"))
    return out


def _resistance_checks(inp, axes, n):
    sec, conc, steel = inp.section, inp.concrete, inp.steel
    model = axes["y"].model
    n_max = model.n_max()
    sigma = model.stress(EPS_C3)
    ok_n = inp.n_ed <= n_max
    out = [CheckResult(
        "axial", GROUPS[5], "Axial resistance", PASS if ok_n else FAIL,
        result=f"{kN(inp.n_ed)} {_cmp(ok_n)} {kN(n_max)} kN", value=inp.n_ed / 1e3, limit=n_max / 1e3,
        unit="kN", utilisation=inp.n_ed / n_max,
        working=[
            f"Pure compression at εc = 0.00175: σs = min(Es × 0.00175, fyd) = {sigma:.0f} MPa",
            f"NRd,max = fcd·Ac + σs·As = {conc.fcd:.2f} × {sec.Ac:.0f} + {sigma:.0f} × {sec.As:.0f} = {kN(n_max)} kN",
            f"NEd = {kN(inp.n_ed)} kN {_cmp(ok_n)} NRd,max",
        ],
        refs=refs("ch5_fig7_8", "ch5_resistance"), target="section",
        note="" if ok_n else "Increase the section size, the concrete class or the reinforcement.")]

    as_req = {}
    for ax in axes.values():
        sym = DIM_SYMBOL[ax.name]
        req = required_steel(inp, ax, n)
        as_req[ax.name] = req
        d2 = sec.axis_distance
        chart = (f"Normalised: N/(bhfck) = {inp.n_ed / (sec.Ac * conc.fck):.3f}, "
                 f"M/(bh·{sym}·fck) = {ax.m_ed / (sec.Ac * ax.depth * conc.fck):.3f}, "
                 f"d2/{sym} = {d2 / ax.depth:.2f}, As·fyk/(bhfck) = {sec.As * steel.fyk / (sec.Ac * conc.fck):.3f}")
        req_text = ("no steel needed for strength" if req == 0 else
                    f"{req:.0f} mm²" if req is not None else "not achievable with this section")
        if ax.m_rd is None:
            out.append(CheckResult(
                f"bending_{ax.name}", GROUPS[5], f"Axial + bending about {AXIS_NAME[ax.name]}", FAIL,
                result="NEd exceeds the section capacity", working=[chart],
                refs=refs("ch5_fig7_8", "ch5_resistance", "ch5_fig9"), target="section",
                note="The axial load alone exceeds the resistance of the section."))
            continue
        ok = ax.m_ed <= ax.m_rd
        out.append(CheckResult(
            f"bending_{ax.name}", GROUPS[5], f"Axial + bending about {AXIS_NAME[ax.name]}", PASS if ok else FAIL,
            result=f"MEd {kNm(ax.m_ed)} {_cmp(ok)} MRd {kNm(ax.m_rd)} kNm", value=ax.m_ed / 1e6,
            limit=ax.m_rd / 1e6, unit="kNm", utilisation=ax.m_ed / ax.m_rd if ax.m_rd > 0 else math.inf,
            working=[
                f"Strain compatibility with {len(sec.layers(ax.name)[2])} bar layers, As,prov = {sec.As:.0f} mm² "
                f"({sec.n_bars}H{sec.bar_dia})",
                f"Neutral axis solved for N = NEd = {kN(inp.n_ed)} kN, giving MRd = {kNm(ax.m_rd)} kNm",
                f"MEd = {kNm(ax.m_ed)} kNm {_cmp(ok)} MRd = {kNm(ax.m_rd)} kNm",
                f"As,req = {req_text}; As,prov = {sec.As:.0f} mm² (same bar layout, Kr iterated)",
                chart,
            ],
            refs=refs("ch5_fig7_8", "ch5_resistance", "ch5_fig9", clauses=("6.1",)), target="section"))

    out.append(_biaxial_check(inp, axes))
    return out, as_req


def _biaxial_check(inp, axes):
    sec, conc, steel = inp.section, inp.concrete, inp.steel
    title = "Biaxial bending"
    if inp.bending == "uniaxial":
        return CheckResult(
            "biaxial", GROUPS[5], title, NA, result="Not required: uniaxial bending",
            note="Moments act about y–y only; each axis is checked on its own, with the imperfection "
                 "taken in each direction in turn.",
            refs=refs("ch5_biaxial"), target="section")
    ay, az = axes["y"], axes["z"]
    if ay.m_rd is None or az.m_rd is None or ay.m_rd <= 0 or az.m_rd <= 0:
        return CheckResult("biaxial", GROUPS[5], title, NA, result="Axial resistance exceeded",
                           refs=refs("ch5_biaxial"), target="section")
    n_rd = sec.Ac * conc.fcd + sec.As * steel.fyd
    ratio = inp.n_ed / n_rd
    a = sl.biaxial_exponent(ratio)
    my0, mz0 = _moment_without_imperfection(inp, ay), _moment_without_imperfection(inp, az)
    cases = [("y–y", ay.m_ed, mz0), ("z–z", my0, az.m_ed)]
    lines = ["(MEdz/MRdz)^a + (MEdy/MRdy)^a ≤ 1.0",
             f"NRd = Ac·fcd + As·fyd = {sec.Ac:.0f} × {conc.fcd:.2f} + {sec.As:.0f} × {steel.fyd:.1f} = {kN(n_rd)} kN",
             f"NEd/NRd = {ratio:.3f}, so a = {a:.2f} (interpolated)"]
    values = []
    for where, my, mz in cases:
        v = (mz / az.m_rd) ** a + (my / ay.m_rd) ** a
        values.append(v)
        lines.append(f"Imperfection about {where} only: ({kNm(mz)}/{kNm(az.m_rd)})^{a:.2f} + "
                     f"({kNm(my)}/{kNm(ay.m_rd)})^{a:.2f} = {v:.3f}")
    value = max(values)
    ok = value <= 1.0
    lines.append(f"Governing value {value:.3f} {_cmp(ok)} 1.0")
    return CheckResult(
        "biaxial", GROUPS[5], title, PASS if ok else FAIL, result=f"{value:.3f} {_cmp(ok)} 1.0",
        value=value, limit=1.0, utilisation=value, working=lines,
        refs=refs("ch5_biaxial", "ch5_table5", clauses=("5.8.9",)), target="section",
        note="Imperfections are applied only in the more unfavourable direction (EC2 5.8.9(2)).")


def link_spacing(sec):
    """Largest link spacing: min(12φ, 0.6·bmin, 240 mm), ×1.67 away from beams and slabs.

    The spacings to provide are rounded down to a multiple of 25 mm. 'zone' is the distance
    from a beam or slab (the larger column dimension) over which the closer spacing applies.
    """
    s_max = min(12 * sec.bar_dia, 0.6 * min(sec.b, sec.h), 240)
    far_max = 1.67 * s_max
    return {"s_max": s_max, "near": int(s_max // 25 * 25), "far_max": far_max, "far": int(far_max // 25 * 25),
            "zone": max(sec.b, sec.h)}


def _detailing_checks(inp):
    sec, conc, steel = inp.section, inp.concrete, inp.steel
    out = []
    phi, link = sec.bar_dia, sec.link_dia

    ok = phi >= 12
    out.append(CheckResult(
        "min_bar", GROUPS[6], "Minimum bar diameter", PASS if ok else FAIL,
        result=f"φ{phi} {'≥' if ok else '<'} φ12", value=phi, limit=12, unit="mm",
        working=[f"Longitudinal bars φ = {phi} mm; recommended minimum 12 mm"],
        refs=refs("ch5_steel_areas", "ch10_columns"), target="bars"))

    as_min = max(0.10 * inp.n_ed / steel.fyd, 0.002 * sec.Ac)
    ok = sec.As >= as_min
    out.append(CheckResult(
        "as_min", GROUPS[6], "Minimum reinforcement", PASS if ok else FAIL,
        result=f"{sec.As:.0f} {'≥' if ok else '<'} {as_min:.0f} mm²", value=sec.As, limit=as_min, unit="mm²",
        utilisation=as_min / sec.As,
        working=[f"As,min = max(0.10·NEd/fyd, 0.002·Ac) = max({0.10 * inp.n_ed / steel.fyd:.0f}, "
                 f"{0.002 * sec.Ac:.0f}) = {as_min:.0f} mm²",
                 f"As,prov = {sec.n_bars} × π × {phi}²/4 = {sec.As:.0f} mm²"],
        refs=refs("ch5_steel_areas", clauses=("9.5.2(2)",)), target="bars"))

    as_max = 0.04 * sec.Ac
    ok = sec.As <= as_max
    out.append(CheckResult(
        "as_max", GROUPS[6], "Maximum reinforcement", PASS if ok else FAIL,
        result=f"{sec.As:.0f} {_cmp(ok)} {as_max:.0f} mm²", value=sec.As, limit=as_max, unit="mm²",
        utilisation=sec.As / as_max,
        working=[f"As,max = 0.04·Ac = 0.04 × {sec.Ac:.0f} = {as_max:.0f} mm² outside laps "
                 f"(0.08·Ac = {2 * as_max:.0f} mm² at laps)",
                 f"ρ = As/Ac = {100 * sec.As / sec.Ac:.2f} %"],
        refs=refs("ch5_steel_areas", "ch10_columns"), target="bars"))

    s_b, s_h = sec.clear_spacings()
    s_min = max(phi, inp.dg + 5, 20)
    s_prov = min(s_b, s_h)
    ok = s_prov >= s_min
    out.append(CheckResult(
        "bar_spacing", GROUPS[6], "Clear spacing between bars", PASS if ok else FAIL,
        result=f"{s_prov:.0f} {'≥' if ok else '<'} {s_min:.0f} mm", value=s_prov, limit=s_min, unit="mm",
        utilisation=s_min / s_prov if s_prov > 0 else math.inf,
        working=[f"Clear gap along b-face = {s_b:.0f} mm ({sec.n_b} bars); along h-face = {s_h:.0f} mm "
                 f"({sec.n_h} bars)",
                 f"Minimum = max(φ, dg + 5, 20) = max({phi}, {inp.dg + 5:g}, 20) = {s_min:.0f} mm"],
        refs=refs("ch5_spacing"), target="bars"))

    link_min = max(6.0, phi / 4)
    ok = link >= link_min
    out.append(CheckResult(
        "link_dia", GROUPS[6], "Link diameter", PASS if ok else FAIL,
        result=f"φ{link} {'≥' if ok else '<'} {link_min:g} mm", value=link, limit=link_min, unit="mm",
        working=[f"φlink ≥ max(6, φ/4) = max(6, {phi}/4) = {link_min:g} mm; provided φ{link}"],
        refs=refs("ch5_steel_areas", "ch10_columns"), target="links"))

    sp = link_spacing(sec)
    out.append(CheckResult(
        "link_spacing", GROUPS[6], "Link spacing (calculated)", INFO,
        result=f"H{link} @ {sp['near']} mm, {sp['far']} mm elsewhere", value=sp["near"], limit=sp["s_max"], unit="mm",
        working=[f"s ≤ min(12φ, 0.6·bmin, 240) = min(12 × {phi}, 0.6 × {min(sec.b, sec.h):g}, 240) "
                 f"= min({12 * phi}, {0.6 * min(sec.b, sec.h):.0f}, 240) = {sp['s_max']:.0f} mm",
                 f"Provide H{link} links at {sp['near']} mm centres (rounded down to a multiple of 25 mm) "
                 f"within {sp['zone']:g} mm, the larger column dimension, of each beam or slab",
                 f"Elsewhere s ≤ 1.67 × {sp['s_max']:.0f} = {sp['far_max']:.0f} mm: provide {sp['far']} mm"],
        refs=refs("ch5_spacing", "ch10_columns", clauses=("9.5.3",)), target="links"))

    gap = sec.max_unrestrained_gap()
    if inp.cross_ties:
        restraint = CheckResult(
            "bar_restraint", GROUPS[6], "Restraint of bars by links", PASS, result="All bars tied",
            working=["Every intermediate bar is held by a cross-tie or link"],
            refs=refs("ch5_spacing", clauses=("9.5.3(6)",)), target="links")
    elif sec.n_b <= 2 and sec.n_h <= 2:
        restraint = CheckResult(
            "bar_restraint", GROUPS[6], "Restraint of bars by links", PASS, result="Corner bars only",
            working=["Only corner bars, each held by the perimeter link"],
            refs=refs("ch5_spacing", clauses=("9.5.3(6)",)), target="links")
    else:
        ok = gap <= 150
        restraint = CheckResult(
            "bar_restraint", GROUPS[6], "Restraint of bars by links", PASS if ok else FAIL,
            result=f"{gap:.0f} {_cmp(ok)} 150 mm", value=gap, limit=150, unit="mm", utilisation=gap / 150,
            working=["Only corner bars are held by the perimeter link (no cross-ties)",
                     f"Largest clear distance from an intermediate bar to a restrained bar = {gap:.0f} mm",
                     "No bar should be further than 150 mm from a restrained bar"],
            refs=refs("ch5_spacing", clauses=("9.5.3(6)",)), target="links",
            note="" if ok else "Add cross-ties to the intermediate bars or reduce the bar spacing.")
    out.append(restraint)

    mult = tables.compression_lap(conc.name, 100)
    if mult is None:
        out.append(CheckResult(
            "lap", GROUPS[6], "Compression lap length", NA, result="Not tabulated",
            note="Table 13 starts at C20/25.", refs=refs("ch10_table13")))
    else:
        lap = math.ceil(mult * phi / 10) * 10
        out.append(CheckResult(
            "lap", GROUPS[6], "Compression lap length", INFO, result=f"{lap} mm ({mult}φ)",
            value=lap, unit="mm",
            working=[f"{conc.name}, bars in compression, 100 % lapped in one location, good bond: "
                     f"{mult}φ = {mult} × {phi} = {mult * phi} mm, use {lap} mm"],
            refs=refs("ch10_table13"), target="bars"))
    return out


# ---------------------------------------------------------------- report

def _axis_summary(inp, ax, as_req):
    r = inp.restraint[ax.name]
    act = inp.moments[ax.name]
    s = ax.second or {}
    return {
        "depth": ax.depth, "F": ax.F, "F_table": ax.F_table, "l0": ax.l0, "lam": ax.lam, "lam_lim": ax.lam_lim,
        "slender": ax.slender, "e_i": ax.e_i, "rm": ax.rm, "C": ax.C,
        "M_top": act.m_top / 1e6, "M_bottom": act.m_bottom / 1e6, "curvature": act.curvature,
        "M01": ax.m01 / 1e6, "M02": ax.m02 / 1e6, "M0e": s.get("M0e", 0) / 1e6, "M2": s.get("M2", 0) / 1e6,
        "e2": s.get("e2", 0.0), "Kr": s.get("Kr"), "Kphi": s.get("Kphi"),
        "MEd": ax.m_ed / 1e6, "MRd": None if ax.m_rd is None else ax.m_rd / 1e6,
        "As_req": as_req,
        "restraint": {"method": r.method, "case": r.case,
                      "k_top": None if math.isinf(r.k_top) else r.k_top,
                      "k_bottom": None if math.isinf(r.k_bottom) else r.k_bottom},
    }


def _input_echo(inp):
    sec = inp.section
    rows = [
        ("Concrete", inp.concrete.name), ("fyk", f"{inp.steel.fyk:g} MPa (class {inp.steel.ductility})"),
        ("γc / γs / αcc", f"{inp.concrete.gamma_c:g} / {inp.steel.gamma_s:g} / {inp.concrete.alpha_cc:g}"),
        ("Max aggregate dg", f"{inp.dg:g} mm"),
        ("Section b × h", f"{sec.b:g} × {sec.h:g} mm"), ("Clear height l", f"{inp.l / 1000:g} m"),
        ("Main bars", f"{sec.n_bars}H{sec.bar_dia} ({sec.n_b} per b-face, {sec.n_h} per h-face)"),
        ("Links", f"H{sec.link_dia} @ {link_spacing(sec)['near']} mm, {link_spacing(sec)['far']} mm elsewhere "
                  f"(calculated)" + (", cross-ties to all bars" if inp.cross_ties else "")),
        ("Nominal cover", f"{sec.cover:g} mm (Δcdev = {inp.delta_c_dev:g} mm)"),
        ("Frame", "Braced" if inp.braced else "Unbraced"),
        ("NEd", f"{kN(inp.n_ed)} kN"),
    ]
    rows.append(("Bending", "Uniaxial, about y–y" if inp.bending == "uniaxial" else "Biaxial, about y–y and z–z"))
    for axis in AXES if inp.bending == "biaxial" else ("y",):
        act = inp.moments[axis]
        rows.append((f"M{axis} top / bottom", f"{kNm(act.m_top)} / {kNm(act.m_bottom)} kNm ({act.curvature} curvature)"))
    rows += [
        ("φef", f"{inp.phi_ef:.2f}"), ("λlim method", inp.lambda_lim_method),
        ("Exposure", f"{durability.ROWS_BY_ID[inp.exposure]['classes']} ({inp.cement_group})"),
        ("Fire", "None" if inp.fire_period == "none" else
         f"{inp.fire_period}, {'more than one side' if inp.fire_exposure == 'multi' else 'one side'}, "
         f"μfi = {inp.mu_fi:g}, {inp.floor} floor"),
    ]
    return [{"label": k, "value": v} for k, v in rows]


def check_column(data):
    inp = parse_input(data)
    sec, conc, steel = inp.section, inp.concrete, inp.steel
    n = inp.n_ed / (sec.Ac * conc.fcd)
    omega = sec.As * steel.fyd / (sec.Ac * conc.fcd)
    axes = {axis: analyse_axis(inp, axis, n, omega) for axis in AXES}

    checks = _scope_checks(inp) + _cover_checks(inp) + _fire_checks(inp)
    checks += _slenderness_checks(inp, axes, n) + _moment_checks(inp, axes, n, omega)
    resistance, as_req = _resistance_checks(inp, axes, n)
    checks += resistance + _detailing_checks(inp)

    curves = {}
    for axis, ax in axes.items():
        curves[axis] = {
            "curve": [[m / 1e6, nn / 1e3] for m, nn in ax.model.curve()],
            "NEd": inp.n_ed / 1e3, "MEd": ax.m_ed / 1e6, "M02": ax.m02 / 1e6,
            "MRd": None if ax.m_rd is None else ax.m_rd / 1e6, "Nmax": ax.model.n_max() / 1e3,
        }
    return {
        "element": "column",
        "project": inp.project,
        "summary": summarise(checks),
        "groups": list(GROUPS),
        "checks": [c.to_dict() for c in checks],
        "inputs": _input_echo(inp),
        "assumptions": ASSUMPTIONS,
        "derived": {
            "fcd": conc.fcd, "fyd": steel.fyd, "Ac": sec.Ac, "As": sec.As, "rho": sec.As / sec.Ac,
            "n_bars": sec.n_bars, "a": sec.axis_distance, "n": n, "omega": omega,
            "NEd": inp.n_ed / 1e3, "NRd_max": axes["y"].model.n_max() / 1e3, "braced": inp.braced,
            "l": inp.l, "axes": {axis: _axis_summary(inp, ax, as_req[axis]) for axis, ax in axes.items()},
            "links": {"dia": sec.link_dia, **link_spacing(sec)}, "bending": inp.bending,
        },
        "plots": {
            "section": {
                "b": sec.b, "h": sec.h, "cover": sec.cover, "link_dia": sec.link_dia, "bar_dia": sec.bar_dia,
                "n_b": sec.n_b, "n_h": sec.n_h, "a": sec.axis_distance,
                "bars": [{"x": bar.x, "y": bar.y, "dia": bar.dia, "corner": bar.corner} for bar in sec.bars()],
            },
            "interaction": curves,
        },
    }
