"""Ribbed slab check: one-way ribbed floors on Maxpan clay hollow blocks, to BS EN 1992-1-1 (UK NA).

Follows the worked example the client chose (LN11 "Design of Ribbed and Hollow Block Floors",
Example 3): the user picks the Maxpan size and the rib width; the floor is designed one rib at a
time. A rib is a T-beam: web bw, depth h = pan height + topping hf, flange the topping over the
rib spacing s = pan width + bw. Its loads per metre are the concrete and the pans' own weight plus
the floor loads over the rib spacing; it is analysed like a beam (matrix stiffness, with pattern
loading on continuous spans) and designed like a beam: sagging as a flanged section, hogging as a
rectangle of the web width, shear by the concrete alone or with links, deflection per span,
minimum and maximum steel, bar spacing, crack control and the mesh in the topping.

Lengths in mm, forces in N and moments in N·mm inside the checks; kN, kNm, m in the report.
"""
import math
from dataclasses import dataclass

from . import durability, fire, flexure, tables
from .analysis import SUPPORT_TYPES
from .beam import DEFLECTION_K, L0_FACTOR, SPAN_KINDS, SUPPORT_NAMES, spans_of
from .inputs import Reader, ValidationError
from .materials import BAR_SIZES, CONCRETE_TABLE, DUCTILITY_CLASSES, LINK_SIZES, Concrete, Reinforcement, bar_area
from .results import FAIL, INFO, NA, PASS, CheckResult, summarise
from .slab import (CONCRETE_DENSITY, GROUPS, _read_loads, _scope_checks, analyse_one_way, analysis_plot, kN, kNm, _m)
from .tables import MAXPANS, MESHES, PSI_CATEGORIES

__all__ = ["check_ribbed", "analyse_ribbed", "parse_ribbed", "ValidationError"]

G_ACC = 9.81e-3  # kN per kg

ASSUMPTIONS = [
    "Design to BS EN 1992-1-1 with UK National Annex values; rectangular stress block for concrete up to C50/60.",
    "One-way ribbed floor on Maxpan clay blocks, designed one rib at a time; the blocks add weight but no strength.",
    "Design loads G = 1.35·gk and Q = 1.5·qk per rib. Further loads are per rib; design values are used as entered.",
    "Linear elastic analysis of one rib with the T-section stiffness, without redistribution (δ = 1.0); continuous "
    "ribs use pattern loading (all spans loaded, then alternate spans) for the envelope.",
    "Sagging: T-section with the effective flange width; hogging: rectangle of the rib width (flange in tension).",
    "Shear resisted by the concrete of the rib (vRd,c); links are designed only where the concrete is not enough.",
    "Deflection by span to effective depth ratios with the flanged-section factor F1.",
    "Light fabric in the topping of at least 0.13 % of the topping section for crack control.",
    "Durability covers follow BS 8500 for a 50-year working life and 20 mm maximum aggregate.",
]


@dataclass
class RibbedInput:
    project: dict
    concrete: Concrete
    steel: Reinforcement
    dg: float
    maxpan: str
    pan: dict
    bw: float              # rib width, mm
    hf: float              # topping, mm
    ph: float              # pan height, mm
    h: float               # overall depth, mm
    spacing: float         # rib centres, mm
    length: float          # m
    supports: list
    preset: str
    bottom_n: int
    bottom_dia: int
    top_n: int
    top_dia: int | None
    link_dia: int | None
    legs: int
    cover: float
    delta_c_dev: float
    mesh: str | None
    mode: str
    gk: float              # finishes and services, kN/m²
    qk: float              # kN/m²
    self_weight: bool
    category: str
    loads: list            # further loads per rib
    pattern: bool
    partitions: bool
    m_sag: float | None    # N·mm per rib (direct)
    m_hog: float | None
    v_ed: float | None     # N per rib (direct)
    E_gpa: float | None
    exposure: str
    cement_group: str
    fire_period: str

    @property
    def qk_rib(self):
        return self.qk * self.spacing / 1000.0


def parse_ribbed(data):
    r = Reader(data if isinstance(data, dict) else {})
    project = r.project()
    maxpan = r.choice("slab.maxpan", MAXPANS, default='6"')
    pan = MAXPANS[maxpan]
    bw = r.number("slab.bw", lo=75, hi=600)
    hf = r.number("slab.hf", lo=40, hi=200, default=50)

    concrete_class = r.choice("materials.concrete", CONCRETE_TABLE, default="C25/30")
    fyk = r.number("materials.fyk", lo=200, hi=700, default=500)
    ductility = r.choice("materials.ductility", DUCTILITY_CLASSES, default="B")
    dg = r.number("materials.dg", lo=5, hi=63, default=20)
    gamma_c = r.number("materials.gamma_c", lo=1.0, hi=2.0, default=1.5)
    gamma_s = r.number("materials.gamma_s", lo=1.0, hi=1.5, default=1.15)
    alpha_cc = r.number("materials.alpha_cc", lo=0.8, hi=1.0, default=0.85)

    length = r.number("span.l", lo=0.5, hi=60)
    preset = r.raw("span.preset") or "custom"
    supports = []
    raw = r.raw("span.supports")
    if not isinstance(raw, list) or not raw:
        r.errors["span.supports"] = "Add at least one support."
    else:
        for i, _ in enumerate(raw):
            x = r.number(f"span.supports.{i}.x", lo=0, hi=length if length else None)
            kind = r.choice(f"span.supports.{i}.type", SUPPORT_TYPES, default="pin")
            if x is not None:
                supports.append({"x": x, "type": kind})
        supports.sort(key=lambda s: s["x"])

    def optional_size(path, sizes):
        raw_dia = r.raw(path)
        if raw_dia in (None, "", "none", 0, "0"):
            return None
        return r.choice(path, sizes, default=sizes[0])

    bottom_n = r.number("reinforcement.bottom_n", lo=1, hi=6, integer=True, default=2)
    bottom_dia = r.choice("reinforcement.bottom_dia", BAR_SIZES, default=10)
    top_dia = optional_size("reinforcement.top_dia", BAR_SIZES)
    top_n = r.number("reinforcement.top_n", lo=1, hi=6, integer=True, default=2) if top_dia else 0
    link_dia = optional_size("reinforcement.link_dia", LINK_SIZES)
    legs = r.number("reinforcement.legs", lo=2, hi=4, integer=True, default=2) if link_dia else 0
    cover = r.number("reinforcement.cover", lo=0, hi=100, default=25)
    delta_c_dev = r.number("reinforcement.delta_c_dev", lo=0, hi=20, default=10)
    mesh = r.raw("reinforcement.mesh")
    mesh = None if mesh in (None, "", "none") else r.choice("reinforcement.mesh", MESHES, default="A98")

    mode = r.choice("actions.mode", ("analysis", "direct"), default="analysis")
    category = r.choice("actions.category", PSI_CATEGORIES, default="B")
    self_weight = r.flag("actions.self_weight", default=True)
    gk = r.number("actions.gk", lo=0, hi=1000, default=0.0)
    qk = r.number("actions.qk", lo=0, hi=1000, default=0.0)
    pattern = r.flag("actions.pattern", default=True)
    partitions = r.flag("actions.partitions", default=False)
    loads, m_sag, m_hog, v_ed = [], None, None, None
    if mode == "analysis":
        loads = _read_loads(r, length)
    else:
        m_sag = r.number("actions.M_sag", lo=0, hi=1e5, default=0.0)
        m_hog = r.number("actions.M_hog", lo=0, hi=1e5, default=0.0)
        v_ed = r.number("actions.VEd", lo=0, hi=1e5, default=0.0)
        if not (m_sag or m_hog) and not r.errors:
            r.errors["actions.M_sag"] = "Enter a sagging or a hogging moment per rib."

    E_gpa = None
    if r.choice("stiffness.E_method", ("concrete", "enter"), default="concrete") == "enter":
        E_gpa = r.number("stiffness.E", lo=1, hi=300)

    exposure_ids = [row["id"] for row in durability.EXPOSURE_ROWS]
    exposure = r.choice("durability.exposure", exposure_ids, default="XC1")
    cement_group = r.choice("durability.cement_group", list(durability.ROWS_BY_ID[exposure]["groups"]),
                            default=next(iter(durability.ROWS_BY_ID[exposure]["groups"])))
    fire_period = r.choice("durability.fire_period", fire.FIRE_PERIODS, default="none")

    if not r.errors:
        room = bw - 2 * (cover + (link_dia or 0))
        if bottom_n * bottom_dia > room:
            r.errors["reinforcement.bottom_n"] = (f"{bottom_n} bars of {bottom_dia} mm do not fit in the rib "
                                                  f"({room:.0f} mm between the {'links' if link_dia else 'sides'}).")
        if top_dia and top_n * top_dia > room:
            r.errors["reinforcement.top_n"] = "These top bars do not fit in the rib."
    if r.errors:
        raise ValidationError(r.errors)

    ph = float(pan["height"])
    return RibbedInput(
        project=project, concrete=Concrete.from_class(concrete_class, gamma_c, alpha_cc),
        steel=Reinforcement(fyk, ductility, gamma_s), dg=dg, maxpan=maxpan, pan=pan, bw=bw, hf=hf, ph=ph,
        h=ph + hf, spacing=float(pan["width"]) + bw, length=length, supports=supports, preset=preset,
        bottom_n=bottom_n, bottom_dia=bottom_dia, top_n=top_n, top_dia=top_dia, link_dia=link_dia, legs=legs,
        cover=cover, delta_c_dev=delta_c_dev, mesh=mesh, mode=mode, gk=gk, qk=qk, self_weight=self_weight,
        category=category, loads=loads, pattern=pattern, partitions=partitions,
        m_sag=None if m_sag is None else m_sag * 1e6, m_hog=None if m_hog is None else m_hog * 1e6,
        v_ed=None if v_ed is None else v_ed * 1e3, E_gpa=E_gpa, exposure=exposure,
        cement_group=cement_group, fire_period=fire_period,
    )


# ---------------------------------------------------------------- geometry and loads

@dataclass
class RibGeometry:
    spans: list
    critical: object
    b1: float
    l0: float
    beff_part: float
    beff: float
    d_bot: float
    d_top: float
    a_bot: float          # axis distance of the bottom bars from the soffit
    a_top: float
    As_bot: float
    As_top: float
    Ac: float             # area of one rib's T-section, mm²
    I: float              # second moment of area of one rib, m⁴
    clear_bot: float
    clear_top: float
    pitch_bot: float


def geometry(inp, critical_x=None):
    spans = spans_of(inp.length, inp.supports) if inp.length and inp.supports else []
    inside = [s for s in spans if s.kind != "cantilever"] or spans
    critical = next((s for s in inside if critical_x is not None and s.x1 <= critical_x <= s.x2), inside[0] if inside else None)
    l0 = L0_FACTOR[critical.kind] * critical.l * 1000 if critical else 0.0
    b1 = (inp.spacing - inp.bw) / 2
    part = min(0.2 * b1 + 0.1 * l0, 0.2 * l0, b1) if l0 else b1
    beff = inp.bw + 2 * part
    link = inp.link_dia or 0
    a_bot = inp.cover + link + inp.bottom_dia / 2
    a_top = inp.cover + link + (inp.top_dia or 10) / 2
    width = inp.bw - 2 * (inp.cover + link)

    def spacing_of(n, dia):
        if n <= 1:
            return width - dia, 0.0
        pitch = (width - dia) / (n - 1)
        return pitch - dia, pitch

    clear_bot, pitch_bot = spacing_of(inp.bottom_n, inp.bottom_dia)
    clear_top = spacing_of(inp.top_n, inp.top_dia)[0] if inp.top_dia else 0.0
    # T-section of one rib: flange over the rib spacing, web the rib
    af, aw = inp.spacing * inp.hf, inp.bw * inp.ph
    y = (af * (inp.h - inp.hf / 2) + aw * inp.ph / 2) / (af + aw)
    I = (inp.spacing * inp.hf**3 / 12 + af * (inp.h - inp.hf / 2 - y) ** 2
         + inp.bw * inp.ph**3 / 12 + aw * (inp.ph / 2 - y) ** 2)
    return RibGeometry(spans=spans, critical=critical, b1=b1, l0=l0, beff_part=part, beff=beff,
                       d_bot=inp.h - a_bot, d_top=inp.h - a_top, a_bot=a_bot, a_top=a_top,
                       As_bot=inp.bottom_n * bar_area(inp.bottom_dia),
                       As_top=inp.top_n * bar_area(inp.top_dia) if inp.top_dia else 0.0,
                       Ac=af + aw, I=I * 1e-12, clear_bot=clear_bot, clear_top=clear_top, pitch_bot=pitch_bot)


def rib_loads(inp):
    """Line loads on one rib (kN/m), as in the worked example."""
    s = inp.spacing / 1000
    sw_c = CONCRETE_DENSITY * (inp.bw * inp.ph + inp.spacing * inp.hf) / 1e6 if inp.self_weight else 0.0
    sw_pan = inp.pan["mass"] * G_ACC / (inp.pan["length"] / 1000) if inp.self_weight else 0.0
    finishes = inp.gk * s
    n_g = sw_c + sw_pan + finishes
    n_q = inp.qk * s
    return {"s": s, "sw_c": sw_c, "sw_pan": sw_pan, "finishes": finishes, "n_g": n_g, "n_q": n_q,
            "w": 1.35 * n_g + 1.5 * n_q}


# ---------------------------------------------------------------- checks

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
    outer = inp.link_dia or max(inp.bottom_dia, inp.top_dia or 0)
    c_bond = max(outer, 10)
    required = max(res["cover"], c_bond) + dc
    ok = inp.cover >= required
    lines = head + [
        f"Minimum cover for durability: cmin,dur = {res['cover']} mm",
        f"Minimum cover for bond: cmin,b = φ of the outer bar = {outer} mm "
        f"({'links' if inp.link_dia else 'main bars, no links'}), at least 10 mm",
        f"cnom,req = max({res['cover']}, {c_bond}) + Δcdev = {required:g} mm; provided cnom = {inp.cover:g} mm",
    ]
    return [CheckResult("cover", GROUPS[1], "Durability and cover", PASS if ok else FAIL,
                        result=f"{inp.cover:g} {'≥' if ok else '<'} {required:g} mm", value=inp.cover, limit=required,
                        unit="mm", utilisation=required / max(inp.cover, 1.0), working=lines, target="cover",
                        note="" if ok else "Increase the nominal cover.")]


def _fire_checks(inp, geo):
    if inp.fire_period == "none":
        return [CheckResult("fire", GROUPS[2], "Fire resistance", NA, result="Not required",
                            note="No fire resistance period specified.")]
    inside = [s for s in geo.spans if s.kind != "cantilever"]
    support = "continuous" if len(inside) > 1 or any(s["type"] == "fixed" for s in inp.supports) else "simple"
    ok_rib, gov, evaluated = fire.check_beam_fire(inp.fire_period, support, inp.bw, geo.a_bot)
    hs = fire.SLAB_FIRE_TABLE[inp.fire_period]["hs"]
    ok_flange = inp.hf >= hs
    lines = [f"{inp.fire_period}: each rib is checked as a {'continuous' if support == 'continuous' else 'simply supported'} "
             f"beam and the topping as a slab",
             f"Rib: width bw = {inp.bw:g} mm, axis distance of the bottom bars a = {geo.a_bot:.0f} mm"]
    lines += [f"  Option bmin/a = {o['b_min']}/{o['a']}: {'satisfied' if o['ok'] else 'not satisfied'}" for o in evaluated]
    lines.append(f"Topping: hf = {inp.hf:g} mm {'≥' if ok_flange else '<'} hs,min = {hs} mm")
    ok = ok_rib and ok_flange
    return [CheckResult("fire", GROUPS[2], f"Fire resistance {inp.fire_period}", PASS if ok else FAIL,
                        result=f"rib {inp.bw:g}/{geo.a_bot:.0f} vs {gov['b_min']}/{gov['a']} mm; topping {inp.hf:g}/{hs} mm",
                        utilisation=max(gov["b_min"] / inp.bw, gov["a"] / geo.a_bot, hs / inp.hf), working=lines,
                        target="cover", note="" if ok else "Widen the ribs, increase the cover or thicken the topping.")]


def _actions_check(inp, geo, ld, act):
    if inp.mode == "direct":
        return [CheckResult("actions", GROUPS[3], "Design actions per rib", INFO,
                            result=f"M+Ed = {kNm(act['M_sag'])} kNm, M−Ed = {kNm(act['M_hog'])} kNm, VEd = {kN(act['VEd'])} kN",
                            working=["Design values per rib entered directly; a value entered as zero is not designed for."])]
    s = ld["s"]
    lines = [f"Maxpan {inp.maxpan}: {inp.pan['width']} × {inp.pan['length']} × {inp.pan['height']} mm, "
             f"{inp.pan['mass']:.2f} kg each",
             f"Rib width bw = {inp.bw:g} mm, topping hf = {inp.hf:g} mm, overall depth h = {inp.ph:g} + {inp.hf:g} = "
             f"{inp.h:g} mm; ribs at s = {inp.pan['width']} + {inp.bw:g} = {inp.spacing:g} mm centres",
             "Loads on one rib:"]
    if inp.self_weight:
        lines += [f"  Self-weight of concrete = (bw·hp + s·hf)·25 = ({inp.bw / 1000:g}×{inp.ph / 1000:g} + "
                  f"{s:g}×{inp.hf / 1000:g})×25 = {ld['sw_c']:.3f} kN/m",
                  f"  Self-weight of Maxpans = {inp.pan['mass']:.2f} × 9.81×10⁻³ / {inp.pan['length'] / 1000:g} = "
                  f"{ld['sw_pan']:.3f} kN/m (one pan every {inp.pan['length']} mm along the rib)"]
    lines += [f"  Finishes and services = {inp.gk:g} × {s:g} = {ld['finishes']:.3f} kN/m",
              f"  gk = {ld['n_g']:.3f} kN/m; qk = {inp.qk:g} × {s:g} = {ld['n_q']:.3f} kN/m (category {inp.category})",
              f"  w = 1.35·gk + 1.5·qk = 1.35 × {ld['n_g']:.3f} + 1.5 × {ld['n_q']:.3f} = {ld['w']:.2f} kN/m"]
    for item in inp.loads:
        lines.append(f"  Further load per rib: {item['type']} ({item['case']})")
    supp = ", ".join(f"{SUPPORT_NAMES[x['type']]} at {_m(x['x'])} m" for x in inp.supports)
    lines.append(f"Rib {_m(inp.length)} m long on {len(inp.supports)} support{'s' if len(inp.supports) > 1 else ''}: {supp}; "
                 f"T-section I = {geo.I * 1e12 / 1e6:.0f}×10⁶ mm⁴")
    if act["is_continuous"]:
        for c, label in (("A", "all spans loaded"), ("B", "odd spans loaded"), ("C", "even spans loaded")):
            res = act["cases"][c]
            lines.append(f"  Case {c} ({label}): M+ = {max(res['M']):.2f} kNm, M− = {-min(res['M']):.2f} kNm, "
                         f"|V| = {max(abs(v) for v in res['V']):.2f} kN")
    lines.append(f"Design values per rib: M+Ed = {kNm(act['M_sag'])} kNm at x = {_m(act['x_sag'])} m, "
                 f"M−Ed = {kNm(act['M_hog'])} kNm at x = {_m(act['x_hog'])} m, VEd = {kN(act['VEd'])} kN at x = {_m(act['x_v'])} m")
    return [CheckResult("actions", GROUPS[3], "Design actions per rib", INFO,
                        result=f"w = {ld['w']:.2f} kN/m; M+Ed = {kNm(act['M_sag'])}, M−Ed = {kNm(act['M_hog'])} kNm, "
                               f"VEd = {kN(act['VEd'])} kN", working=lines)]


def _design(inp, geo, M, sagging):
    conc, steel = inp.concrete, inp.steel
    kp = flexure.k_prime(1.0, True)
    if sagging:
        res = flexure.flanged(M, geo.beff, inp.bw, inp.hf, geo.d_bot, conc.fck, steel.fyd, kp)
        res.update(d=geo.d_bot, width=geo.beff, As_prov=geo.As_bot, flange=True)
    else:
        res = flexure.rectangular(M, inp.bw, geo.d_top, geo.a_bot, conc.fck, steel.fyd, kp)
        res.update(d=geo.d_top, width=inp.bw, As_prov=geo.As_top, flange=False)
    return res


def _bending_checks(inp, geo, act, sagging):
    tag, word = ("sag", "Sagging") if sagging else ("hog", "Hogging")
    M = act["M_sag"] if sagging else act["M_hog"]
    if not M:
        return [CheckResult(f"bending_{tag}", GROUPS[4], f"{word}: rib reinforcement", NA,
                            result=f"No {word.lower()} moment",
                            working=[f"The analysis gives no {word.lower()} moment, so none is designed for"])], None
    if not sagging and not inp.top_dia:
        return [CheckResult("bending_hog", GROUPS[4], "Hogging: rib reinforcement", FAIL, result="No top bars",
                            working=[f"M−Ed = {kNm(M)} kNm per rib over the supports, but no top bars are entered"],
                            note="Add top bars in the ribs over the supports.", target="bars")], None
    conc, steel = inp.concrete, inp.steel
    res = _design(inp, geo, M, sagging)
    d = res["d"]
    bars = f"{inp.bottom_n}H{inp.bottom_dia}" if sagging else f"{inp.top_n}H{inp.top_dia}"
    lines = [f"{'M+Ed' if sagging else 'M−Ed'} = {kNm(M)} kNm per rib"]
    if sagging:
        lines += [f"Effective flange width: b1 = (s − bw)/2 = {geo.b1:.0f} mm; l0 = {L0_FACTOR[geo.critical.kind]:g} × "
                  f"{geo.critical.l * 1000:.0f} = {geo.l0:.0f} mm ({SPAN_KINDS[geo.critical.kind]})",
                  f"beff,i = min(0.2·b1 + 0.1·l0, 0.2·l0, b1) = min({0.2 * geo.b1 + 0.1 * geo.l0:.0f}, {0.2 * geo.l0:.0f}, "
                  f"{geo.b1:.0f}) = {geo.beff_part:.0f} mm; beff = bw + 2·beff,i = {geo.beff:.0f} mm"]
    else:
        lines.append(f"Flange in tension over the support: designed as a rectangle of the rib width bw = {inp.bw:g} mm")
    link = f" − {inp.link_dia}" if inp.link_dia else ""
    lines.append(f"d = h − cnom{' − φlink' if inp.link_dia else ''} − φ/2 = {inp.h:g} − {inp.cover:g}{link} − "
                 f"{(inp.bottom_dia if sagging else inp.top_dia) / 2:g} = {d:.0f} mm")
    lines.append(f"K = M/(b·d²·fck) = {kNm(M)}×10⁶ / ({res['width']:.0f} × {d:.0f}² × {conc.fck:g}) = {res['K']:.4f}; "
                 f"K′ = {res['kp']:.3f}")
    if not res["ok"]:
        lines.append("The rib is too small for this moment")
        return [CheckResult(f"bending_{tag}", GROUPS[4], f"{word}: rib reinforcement", FAIL, result="Rib too small",
                            working=lines, note="Use deeper Maxpans or wider ribs.", target="section")], res
    if sagging and res.get("in_flange"):
        lines += [f"z = d/2·[1 + √(1 − 3.53K)] ≤ 0.95d = {res['z']:.1f} mm; x = 2.5(d − z) = {res['x']:.1f} mm",
                  f"x ≤ 1.25·hf = {1.25 * inp.hf:.1f} mm: neutral axis in the flange, designed as a rectangle of width beff"]
    elif sagging:
        lines.append(f"Neutral axis in the web: MR,f = 0.57·fck·(beff − bw)·hf·(d − 0.5hf) = {kNm(res['MRf'])} kNm")
    elif res.get("compression"):
        lines.append(f"K > K′: compression steel As2 = {res['As2']:.0f} mm² needed in the bottom of the rib")
    else:
        lines.append(f"z = d/2·[1 + √(1 − 3.53K)] ≤ 0.95d = {res['z']:.1f} mm")
    As_prov = res["As_prov"]
    ok = As_prov >= res["As"]
    lines += [f"As,req = {res['As']:.0f} mm² per rib", f"Provided {bars} = {As_prov:.0f} mm² per rib"]
    if not sagging and res.get("compression"):
        ok = ok and geo.As_bot >= res["As2"]
        lines.append(f"Bottom bars {inp.bottom_n}H{inp.bottom_dia} = {geo.As_bot:.0f} mm² {'≥' if geo.As_bot >= res['As2'] else '<'} "
                     f"As2 = {res['As2']:.0f} mm²")
    return [CheckResult(f"bending_{tag}", GROUPS[4], f"{word}: rib reinforcement", PASS if ok else FAIL,
                        result=f"{As_prov:.0f} {'≥' if ok else '<'} {res['As']:.0f} mm²", value=As_prov, limit=res["As"],
                        unit="mm²", utilisation=res["As"] / max(As_prov, 1.0), working=lines, target="bars",
                        note="" if ok else "Add bars or use larger bars in the ribs.")], res


def _shear_checks(inp, geo, act, res_sag, res_hog):
    V = act["VEd"]
    if not V:
        return [CheckResult("shear", GROUPS[5], "Shear in the rib", NA, result="No shear force",
                            working=["The analysis gives no shear force"])]
    conc, steel = inp.concrete, inp.steel
    hog = act.get("v_hogging") and inp.top_dia
    d = geo.d_top if hog else geo.d_bot
    As = geo.As_top if hog else geo.As_bot
    rho = min(As / (inp.bw * d), 0.02)
    k = min(1 + math.sqrt(200 / d), 2.0)
    v_c = flexure.vrd_c(conc.fck, d, rho)
    VRd_c = v_c * inp.bw * d
    where = f" at x = {_m(act['x_v'])} m" if act.get("x_v") is not None else ""
    lines = [f"VEd = {kN(V)} kN per rib{where}; tension bars there: {'top' if hog else 'bottom'}, d = {d:.0f} mm",
             f"k = min(1 + √(200/d), 2.0) = {k:.3f}; ρl = As/(bw·d) = {As:.0f}/({inp.bw:g} × {d:.0f}) = {rho:.4f}",
             f"VRd,c = max[0.12·k·(100·ρl·fck)^(1/3), 0.035·k^1.5·√fck]·bw·d = {v_c:.3f} × {inp.bw:g} × {d:.0f} = "
             f"{VRd_c / 1e3:.2f} kN"]
    if V <= VRd_c:
        lines.append(f"VEd = {kN(V)} ≤ VRd,c = {VRd_c / 1e3:.2f} kN: no shear reinforcement needed")
        return [CheckResult("shear", GROUPS[5], "Shear in the rib", PASS, result=f"{kN(V)} ≤ {VRd_c / 1e3:.2f} kN",
                            value=V / 1e3, limit=VRd_c / 1e3, unit="kN", utilisation=V / VRd_c, working=lines,
                            target="section")]
    if not inp.link_dia:
        lines.append(f"VEd > VRd,c: the concrete alone is not enough")
        return [CheckResult("shear", GROUPS[5], "Shear in the rib", FAIL, result=f"{kN(V)} > {VRd_c / 1e3:.2f} kN",
                            utilisation=V / VRd_c, working=lines, target="section",
                            note="Provide links in the ribs, or widen or deepen them.")]
    z = 0.9 * d
    v_ed = V / (inp.bw * z)
    cot, v25, v10 = flexure.vertical_shear(v_ed, conc.fck)
    lines.append(f"VEd > VRd,c: links needed. vEd = VEd/(bw·z) = {v_ed:.2f} MPa; vRd,max = {v25:.2f} MPa (cot θ = 2.5), "
                 f"{v10:.2f} MPa (cot θ = 1.0)")
    if cot is None:
        return [CheckResult("shear", GROUPS[5], "Shear in the rib", FAIL, result=f"vEd {v_ed:.2f} > vRd,max {v10:.2f} MPa",
                            utilisation=v_ed / v10, working=lines, target="section", note="Widen the ribs.")]
    asw = inp.legs * bar_area(inp.link_dia)
    need = max(v_ed * inp.bw / (steel.fyd * cot), flexure.rho_w_min(conc.fck, steel.fyk) * inp.bw)
    s = int(min(asw / need, 0.75 * d) // 25 * 25)
    ok = s >= 50
    lines.append(f"Asw/s ≥ {need:.3f} mm²/mm; H{inp.link_dia} ({inp.legs} legs) Asw = {asw:.0f} mm² → s = {s} mm "
                 f"(≤ 0.75d = {0.75 * d:.0f} mm)")
    return [CheckResult("shear", GROUPS[5], "Shear in the rib", PASS if ok else FAIL,
                        result=f"H{inp.link_dia} links @ {s} mm", utilisation=v_ed / v10, working=lines, target="links",
                        note="" if ok else "Links too close: use larger links.")]


def _steel_stress(inp, res, qp):
    ratio = res["As"] / max(res["As_prov"], 1.0)
    if qp is None:
        return 310 * ratio, f"σs ≈ 310·As,req/As,prov = {310 * ratio:.0f} MPa (loads not given)"
    s = max(10.0, inp.steel.fyd * qp * ratio)
    return s, f"σs = fyd·(Mqp/MEd)·As,req/As,prov = {inp.steel.fyd:.1f} × {qp:.3f} × {ratio:.3f} = {s:.0f} MPa"


def _deflection_checks(inp, geo, act):
    lines, utils, statuses = [], [], []
    conc = inp.concrete
    for item in act.get("span_actions", []):
        span, M = item["span"], item["MEd"]
        name = span.label()
        if span.kind == "cantilever" or M <= 1e4:
            lines.append(f"{name[0].upper()}{name[1:]}: no sagging moment, not checked")
            continue
        res = _design(inp, geo, M, True)
        if not res["ok"]:
            lines.append(f"{name[0].upper()}{name[1:]}: not assessed, the rib is too small")
            continue
        d = res["d"]
        area = geo.beff * inp.hf + inp.bw * (d - inp.hf)
        rho = res["As"] / area
        K = DEFLECTION_K[span.kind]
        basic = flexure.basic_span_depth(K, conc.fck, rho, 0.0)
        f1 = max(0.8, 1 - 0.1 * (geo.beff / inp.bw - 1))
        f2 = 7 / span.l if inp.partitions and span.l > 7 else 1.0
        sigma, sigma_line = _steel_stress(inp, res, item["qp_ratio"])
        f3 = min(310 / sigma, 1.5)
        allowed = basic * f1 * f2 * f3
        actual = span.l * 1000 / d
        ok = actual <= allowed
        lines += [f"{name[0].upper()}{name[1:]}: M = {kNm(M)} kNm, d = {d:.0f} mm, K = {K:g}",
                  f"  ρ = As,req/(beff·hf + bw·(d − hf)) = {100 * rho:.3f} %; basic l/d = {basic:.1f}",
                  f"  F1 = 1 − 0.1·(beff/bw − 1) ≥ 0.8 = {f1:.2f}" + (f"; F2 = 7/l = {f2:.2f}" if f2 < 1 else ""),
                  f"  {sigma_line}; F3 = 310/σs ≤ 1.5 = {f3:.2f}",
                  f"  Allowable l/d = {allowed:.1f}; actual l/d = {span.l * 1000:.0f}/{d:.0f} = {actual:.1f} "
                  f"{'≤' if ok else '>'} {allowed:.1f}"]
        utils.append(actual / allowed)
        statuses.append(ok)
    if not utils:
        return [CheckResult("deflection", GROUPS[6], "Span to depth ratio", NA, result="Not assessed",
                            working=lines or ["No span to check"])]
    ok = all(statuses)
    return [CheckResult("deflection", GROUPS[6], "Span to depth ratio", PASS if ok else FAIL,
                        result=f"worst l/d at {max(utils):.2f} of the limit", utilisation=max(utils), working=lines,
                        target="section", note="" if ok else "Use deeper Maxpans or more bottom steel.")]


def _detailing_checks(inp, geo, act, res_sag, res_hog):
    conc, steel = inp.concrete, inp.steel
    out = []
    for res, label, As, d, tag in ((res_sag, "bottom", geo.As_bot, geo.d_bot, "bottom"),
                                   (res_hog, "top", geo.As_top, geo.d_top, "top")):
        if not res:
            continue
        as_min = max(0.26 * conc.fctm / steel.fyk * inp.bw * d, 0.0013 * inp.bw * d)
        ok = As >= as_min
        out.append(CheckResult(
            f"as_min_{tag}", GROUPS[7], f"Minimum {label} reinforcement", PASS if ok else FAIL,
            result=f"{As:.0f} {'≥' if ok else '<'} {as_min:.0f} mm²", utilisation=as_min / max(As, 1.0),
            working=[f"As,min = 0.26·fctm·bt·d/fyk ≥ 0.0013·bt·d with bt = bw = {inp.bw:g} mm: "
                     f"max({0.26 * conc.fctm / steel.fyk * inp.bw * d:.0f}, {0.0013 * inp.bw * d:.0f}) = {as_min:.0f} mm²"],
            target="bars"))
    total = geo.As_bot + geo.As_top
    as_max = 0.04 * geo.Ac
    ok = total <= as_max
    out.append(CheckResult("as_max", GROUPS[7], "Maximum reinforcement", PASS if ok else FAIL,
                           result=f"{total:.0f} {'≤' if ok else '>'} {as_max:.0f} mm²", utilisation=total / as_max,
                           working=[f"As,max = 0.04·Ac of one rib = 0.04 × {geo.Ac:.0f} = {as_max:.0f} mm²"],
                           target="bars"))
    for name, n, dia, clear in (("bottom", inp.bottom_n, inp.bottom_dia, geo.clear_bot),
                                ("top", inp.top_n, inp.top_dia, geo.clear_top)):
        if not dia or n < 2:
            continue
        s_min = max(dia, inp.dg + 5, 20)
        ok = clear >= s_min
        out.append(CheckResult(f"bar_spacing_{name}", GROUPS[7], f"Clear spacing, {name} bars in the rib",
                               PASS if ok else FAIL, result=f"{clear:.0f} {'≥' if ok else '<'} {s_min:.0f} mm",
                               utilisation=s_min / clear if clear > 0 else math.inf,
                               working=[f"{n} bars of {dia} mm in a rib {inp.bw:g} mm wide: clear gap = {clear:.0f} mm",
                                        f"Minimum = max(φ, dg + 5, 20) = {s_min:.0f} mm"], target="bars"))
    need = 0.0013 * 1000 * inp.hf
    have = MESHES.get(inp.mesh, 0) if inp.mesh else 0
    ok = have >= need
    out.append(CheckResult("mesh", GROUPS[7], "Fabric in the topping", PASS if ok else FAIL,
                           result=f"{inp.mesh or 'none'}: {have} {'≥' if ok else '<'} {need:.0f} mm²/m",
                           utilisation=need / have if have else math.inf,
                           working=[f"Light fabric in the topping for crack control: As ≥ 0.13 %·b·hf = 0.0013 × 1000 × "
                                    f"{inp.hf:g} = {need:.0f} mm²/m", f"Provided {inp.mesh or 'no fabric'} = {have} mm²/m"],
                           note="" if ok else "Add a mesh such as A98 or A142 in the topping."))
    for res, name, dia, qp in ((res_sag, "bottom", inp.bottom_dia, act.get("qp_sag")),
                               (res_hog, "top", inp.top_dia, act.get("qp_hog"))):
        if not (res and res["ok"]):
            continue
        w_max = 0.4 if inp.exposure == "XC1" else 0.3
        sigma, line = _steel_stress(inp, res, qp)
        size, spacing = tables.crack_limits(sigma, w_max)
        if size is None:
            ok, result, tail = False, f"σs = {sigma:.0f} > 360 MPa", "Steel stress above the tabulated range"
        else:
            ok = dia <= size
            result = f"φ{dia} {'≤' if ok else '>'} {size:.0f} mm"
            tail = f"wmax = {w_max} mm: maximum bar size {size:.0f} mm"
        out.append(CheckResult(f"cracking_{name}", GROUPS[7], f"Crack control, {name} bars", PASS if ok else FAIL,
                               result=result, working=[line, tail], target="bars",
                               note="" if ok else "Use smaller bars or more steel to lower the stress."))
    return out


def _input_echo(inp, geo, ld):
    supp = ", ".join(f"{SUPPORT_NAMES[s['type']]} at {_m(s['x'])} m" for s in inp.supports)
    rows = [("Slab type", "One-way ribbed slab on Maxpan clay blocks"),
            ("Maxpan", f"{inp.maxpan}: {inp.pan['height']} mm high, {inp.pan['mass']:.2f} kg"),
            ("Ribs", f"bw = {inp.bw:g} mm at {inp.spacing:g} mm centres; topping {inp.hf:g} mm; h = {inp.h:g} mm"),
            ("Concrete", inp.concrete.name), ("fyk", f"{inp.steel.fyk:g} MPa (class {inp.steel.ductility})"),
            ("Span & supports", f"L = {_m(inp.length)} m; {supp}"),
            ("Bars per rib", f"bottom {inp.bottom_n}H{inp.bottom_dia}; top "
                             + (f"{inp.top_n}H{inp.top_dia}" if inp.top_dia else "none")
                             + (f"; links H{inp.link_dia} ({inp.legs} legs)" if inp.link_dia else "; no links")),
            ("Topping fabric", inp.mesh or "none"),
            ("Nominal cover", f"{inp.cover:g} mm (Δcdev = {inp.delta_c_dev:g} mm)")]
    if inp.mode == "analysis":
        rows.append(("Loads", f"finishes gk = {inp.gk:g} kN/m², qk = {inp.qk:g} kN/m² (category {inp.category})"
                              + ("; self-weight of concrete and Maxpans added" if inp.self_weight else "")))
    rows.append(("Exposure & fire", f"{inp.exposure} ({inp.cement_group}), fire: {inp.fire_period}"))
    return [{"label": k, "value": v} for k, v in rows]


def _section_plot(inp, geo):
    return {"slab_type": "ribbed", "shape": "ribbed", "bw": inp.bw, "hf": inp.hf, "ph": inp.ph, "h": inp.h,
            "spacing": inp.spacing, "beff": geo.beff, "cover": inp.cover, "link_dia": inp.link_dia, "maxpan": inp.maxpan,
            "bottom": {"n": inp.bottom_n, "dia": inp.bottom_dia, "As": geo.As_bot},
            "top": {"n": inp.top_n, "dia": inp.top_dia, "As": geo.As_top}, "mesh": inp.mesh}


def _actions(inp, geo, ld):
    if inp.mode == "direct":
        return {"M_sag": inp.m_sag, "x_sag": None, "M_hog": inp.m_hog, "x_hog": None, "VEd": inp.v_ed, "x_v": None,
                "v_hogging": bool(inp.m_hog) and not inp.m_sag, "span_actions": [], "res_A": None,
                "is_continuous": False, "qp_sag": None, "qp_hog": None}
    act = analyse_one_way(inp, n_g=ld["n_g"], n_q=ld["n_q"], inertia=geo.I)
    res_A, res_qp = act["res_A"], act["res_qp"]

    def qp_at(x, sagging):
        if x is None:
            return None
        i = min(range(len(res_A["x"])), key=lambda j: abs(res_A["x"][j] - x))
        m, mq = res_A["M"][i], res_qp["M"][i]
        return min(max(mq / m, 0.05), 1.0) if abs(m) > 1e-9 and (m > 0) == sagging else None

    act["qp_sag"] = qp_at(act["x_sag"], True)
    act["qp_hog"] = qp_at(act["x_hog"], False)
    return act


def check_ribbed(data):
    inp = parse_ribbed(data)
    geo = geometry(inp)
    ld = rib_loads(inp)
    act = _actions(inp, geo, ld)
    if act.get("x_sag") is not None and act["M_sag"]:
        geo = geometry(inp, act["x_sag"])       # effective flange width from the span with the sagging peak
    checks = _scope_checks(inp) + _cover_checks(inp) + _fire_checks(inp, geo) + _actions_check(inp, geo, ld, act)
    sag, res_sag = _bending_checks(inp, geo, act, True)
    hog, res_hog = _bending_checks(inp, geo, act, False)
    checks += sag + hog + _shear_checks(inp, geo, act, res_sag, res_hog) + _deflection_checks(inp, geo, act)
    checks += _detailing_checks(inp, geo, act, res_sag, res_hog)
    plots = {"section": _section_plot(inp, geo), "model": {"length": inp.length, "supports": inp.supports},
             "analysis": analysis_plot(inp, act, geo.I) if act.get("res_A") else None}
    summary = summarise(checks)
    return {
        "element": "slab",
        "project": inp.project,
        "summary": summary,
        "verdict": summary["verdict"],
        "groups": list(GROUPS),
        "checks": [c.to_dict() for c in checks],
        "inputs": _input_echo(inp, geo, ld),
        "assumptions": list(ASSUMPTIONS),
        "derived": {
            "slab_type": "ribbed", "h": inp.h, "bw": inp.bw, "beff": geo.beff, "spacing": inp.spacing,
            "maxpan": inp.maxpan, "w": ld["w"], "n_g": ld["n_g"], "n_q": ld["n_q"],
            "MEd_sag": (act["M_sag"] or 0) / 1e6, "MEd_hog": (act["M_hog"] or 0) / 1e6, "VEd": (act["VEd"] or 0) / 1e3,
            "x_sag": act.get("x_sag"), "x_hog": act.get("x_hog"), "x_v": act.get("x_v"),
            "bottom": {"n": inp.bottom_n, "dia": inp.bottom_dia, "As": geo.As_bot, "d": geo.d_bot},
            "top": {"n": inp.top_n, "dia": inp.top_dia, "As": geo.As_top, "d": geo.d_top},
            "sag": None if not res_sag else {"K": res_sag["K"], "As_req": res_sag["As"] if res_sag["ok"] else None},
            "hog": None if not res_hog else {"K": res_hog["K"], "As_req": res_hog["As"] if res_hog["ok"] else None},
        },
        "plots": plots,
    }


def analyse_ribbed(data):
    """Loading and analysis only (live preview), with safe defaults for the design inputs."""
    d = dict(data) if isinstance(data, dict) else {}
    d["reinforcement"] = {"bottom_n": 1, "bottom_dia": 8, "top_dia": "none", "link_dia": "none", "cover": 20,
                          "delta_c_dev": 10, "mesh": "A98"}
    d["durability"] = {"exposure": "XC1", "cement_group": "All", "fire_period": "none"}
    mat = d.get("materials") if isinstance(d.get("materials"), dict) else {}
    d["materials"] = {"concrete": mat.get("concrete", "C25/30"), "fyk": 500, "ductility": "B", "dg": 20}
    inp = parse_ribbed(d)
    geo = geometry(inp)
    ld = rib_loads(inp)
    act = _actions(inp, geo, ld)
    plots = {"section": _section_plot(inp, geo), "model": {"length": inp.length, "supports": inp.supports},
             "analysis": analysis_plot(inp, act, geo.I) if act.get("res_A") else None}
    plots["loads"] = {"w": ld["w"], "sw": ld["sw_c"] + ld["sw_pan"], "g": ld["n_g"], "q": ld["n_q"],
                      "rib": {k: ld[k] for k in ("s", "sw_c", "sw_pan", "finishes")}}
    return plots
