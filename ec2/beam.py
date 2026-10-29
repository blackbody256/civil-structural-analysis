"""Beam check: rectangular or flanged (T or L) beams to BS EN 1992-1-1 (UK National Annex).

check_beam(data) validates a request and then works in three steps:

1. Loading: the design line load w = 1.35·gk + 1.5·qk from the loads on the beam, its
   self-weight and, when the beam carries a slab, the slab load (tributary width for a one-way
   slab, equivalent uniform loads for a two-way slab). Further point loads, part-length loads,
   varying loads and moments can be added.
2. Analysis: the beam is analysed by the matrix stiffness method (ec2.analysis) for w and the
   other loads, giving reactions, shear forces, bending moments and deflections.
3. Design: every critical value the analysis gives is designed for: the largest sagging moment
   (bottom steel), the largest hogging moment (top steel) and the largest shear. A moment or
   shear that is zero is not designed for.

Inside the checks lengths are in mm, forces in N and moments in N·mm; the analysis and the
report use m, kN and kNm.
"""
import copy
import math
from dataclasses import dataclass

from . import durability, fire, flexure, tables
from .actions import psi_factors
from .analysis import SUPPORT_TYPES, AnalysisError, analyse
from .inputs import Reader, ValidationError
from .materials import BAR_SIZES, CONCRETE_TABLE, DUCTILITY_CLASSES, LINK_SIZES, Concrete, Reinforcement, bar_area
from .results import FAIL, INFO, NA, PASS, WARN, CheckResult, summarise
from .tables import PSI_CATEGORIES

__all__ = ["check_beam", "analyse_input", "parse_input", "ValidationError"]

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
SPAN_KINDS = {"simple": "simply supported", "end": "end span", "interior": "interior span", "cantilever": "cantilever"}
DEFLECTION_K = {"simple": 1.0, "end": 1.3, "interior": 1.5, "cantilever": 0.4}
# distance between points of zero moment as a share of the span (effective flange width)
L0_FACTOR = {"simple": 1.0, "end": 0.85, "interior": 0.70, "cantilever": 1.0}
CONCRETE_DENSITY = 25.0  # kN/m³, reinforced concrete
GAMMA_G, GAMMA_Q = 1.35, 1.5
LOAD_TYPES = ("point", "udl", "linear", "moment")
LOAD_CASES = {"Ed": "design value", "G": "permanent", "Q": "variable"}
SLAB_TYPES = {
    "one_way": "one-way slab",
    "two_way_long": "two-way slab, beam along the long side Ly",
    "two_way_short": "two-way slab, beam along the short side Lx",
}
SUPPORT_NAMES = {"pin": "pinned", "roller": "roller", "fixed": "fixed"}


@dataclass
class Bars:
    n: int
    dia: int
    layers: int


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
    length: float         # m
    supports: list        # [{"x": m, "type": "pin" | "roller" | "fixed"}]
    bottom: Bars
    top: Bars
    link_dia: int
    legs: int
    cover: float
    delta_c_dev: float
    mode: str             # "analysis" (loads analysed) or "direct" (design actions entered)
    gk: float             # kN/m over the whole beam
    qk: float
    self_weight: bool
    category: str
    slab: dict | None
    loads: list           # further loads, with "case" Ed, G or Q
    E_gpa: float | None   # entered elastic modulus, else Ecm
    segments: list        # entered second moments of area [{"x1", "x2", "I" (×10⁶ mm⁴)}]
    m_sag: float | None   # N·mm, direct mode
    m_hog: float | None
    v_ed: float | None    # N
    partitions: bool
    kprime_limit: bool
    exposure: str
    cement_group: str
    fire_period: str


# ---------------------------------------------------------------- reading the request

def _upgrade(data):
    """Read inputs saved before the analysis was added (one section per run, coefficients)."""
    data = copy.deepcopy(data) if isinstance(data, dict) else {}
    span = data.setdefault("span", {})
    re = data.setdefault("reinforcement", {})
    act = data.setdefault("actions", {})
    location = span.get("location", "span")
    if "bottom_n" not in re and "tension_n" in re:
        tension = {"n": re.get("tension_n"), "dia": re.get("tension_dia"), "layers": re.get("layers", 1)}
        compression = {"n": re.get("compression_n"), "dia": re.get("compression_dia"), "layers": 1}
        bottom, top = (compression, tension) if location == "support" else (tension, compression)
        for face, bars in (("bottom", bottom), ("top", top)):
            for k, v in bars.items():
                re[f"{face}_{k}"] = v
    if "supports" not in span:
        length = span.get("l")
        old = act.get("supports")
        if isinstance(old, list) and old:
            span["supports"] = [{"x": s.get("x", 0), "type": "fixed" if s.get("fix_m") else "pin"} for s in old]
        elif length is not None:
            preset = {"simple": [(0, "pin"), (1, "roller")], "cantilever": [(0, "fixed")],
                      "end": [(0, "pin"), (1, "fixed")], "interior": [(0, "fixed"), (1, "fixed")]}
            span["supports"] = [{"x": f * float(length), "type": t}
                                for f, t in preset.get(span.get("system", "simple"), preset["simple"])]
    if act.get("mode") == "loads":
        act["mode"] = "analysis"
    if act.get("mode") == "direct" and "MEd" in act and "M_sag" not in act:
        act["M_hog" if location == "support" else "M_sag"] = act.get("MEd")
    if isinstance(act.get("loads"), list):
        for ld in act["loads"]:
            if not isinstance(ld, dict):
                continue
            ld.setdefault("case", "Ed")
            for old_key, new_key in (("l1", "x1"), ("l2", "x2"), ("M0", "M")):
                if old_key in ld and new_key not in ld:
                    ld[new_key] = ld.pop(old_key)
            if ld.get("type") in ("point", "moment") and "x" not in ld and "x1" in ld:
                ld["x"] = ld["x1"]
    if act.get("has_slab") and "slab" not in act:
        act["slab"] = {"on": True, "type": act.get("slab_type", "one_way"), "gk": act.get("slab_gk"),
                       "qk": act.get("slab_qk"), "trib": act.get("slab_trib"), "lx": act.get("slab_lx"),
                       "ly": act.get("slab_ly"), "sides": 1}
    if isinstance(act.get("inertia"), list) and "stiffness" not in data:
        data["stiffness"] = {"I_method": "enter",
                             "segments": [{"x1": s.get("x1"), "x2": s.get("x2"), "I": float(s.get("I", 0)) * 1e6}
                                          for s in act["inertia"]]}
    return data


def _read_loads(r, length):
    raw = r.raw("actions.loads")
    if not isinstance(raw, list):
        return []
    hi = length if length else None
    loads = []
    for i, _ in enumerate(raw):
        p = f"actions.loads.{i}"
        before = len(r.errors)
        kind = r.choice(f"{p}.type", LOAD_TYPES, default="point")
        item = {"type": kind, "case": r.choice(f"{p}.case", LOAD_CASES, default="Ed")}
        if kind in ("point", "moment"):
            key = "W" if kind == "point" else "M"
            item[key] = r.number(f"{p}.{key}", lo=-1e5, hi=1e5)
            item["x"] = r.number(f"{p}.x", lo=0, hi=hi)
            zero = not item[key]
        else:
            for key in (("w",) if kind == "udl" else ("w1", "w2")):
                item[key] = r.number(f"{p}.{key}", lo=-1e4, hi=1e4)
            item["x1"] = r.number(f"{p}.x1", lo=0, hi=hi)
            item["x2"] = r.number(f"{p}.x2", lo=0, hi=hi)
            if len(r.errors) == before and item["x2"] <= item["x1"]:
                r.errors[f"{p}.x2"] = "Must be beyond the start of the load."
            zero = not any(item.get(k) for k in ("w", "w1", "w2"))
        if len(r.errors) == before and not zero:
            loads.append(item)
    return loads


def _read_slab(r):
    kind = r.choice("actions.slab.type", SLAB_TYPES, default="one_way")
    slab = {"type": kind, "gk": r.number("actions.slab.gk", lo=0, hi=100), "qk": r.number("actions.slab.qk", lo=0, hi=100)}
    if kind == "one_way":
        slab["trib"] = r.number("actions.slab.trib", lo=0.1, hi=50)
    else:
        slab["lx"] = r.number("actions.slab.lx", lo=0.5, hi=50)
        slab["ly"] = r.number("actions.slab.ly", lo=0.5, hi=50)
        slab["sides"] = r.number("actions.slab.sides", lo=1, hi=2, integer=True, default=1)
        if slab["lx"] and slab["ly"] and slab["lx"] > slab["ly"]:
            r.errors["actions.slab.lx"] = "Lx is the shorter side of the slab panel."
    return slab


def _read_segments(r, length):
    raw = r.raw("stiffness.segments")
    if not isinstance(raw, list) or not raw:
        r.errors["stiffness.segments"] = "Enter the second moment of area along the beam."
        return []
    segments = []
    for i, _ in enumerate(raw):
        p = f"stiffness.segments.{i}"
        seg = {"x1": r.number(f"{p}.x1", lo=0), "x2": r.number(f"{p}.x2", lo=0), "I": r.number(f"{p}.I", lo=1, hi=1e9)}
        if None not in seg.values():
            segments.append(seg)
    segments.sort(key=lambda s: s["x1"])
    if length and not r.errors:
        reach = 0.0
        for seg in segments:
            if seg["x1"] > reach + 1e-6:
                break
            reach = max(reach, seg["x2"])
        if reach < length - 1e-6:
            r.errors["stiffness.segments"] = f"The segments must cover the whole beam, from 0 to {length:g} m."
    return segments


def parse_input(data):
    r = Reader(_upgrade(data))
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

    length = r.number("span.l", lo=0.5, hi=60)
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

    def bars(face, dia):
        return Bars(r.number(f"reinforcement.{face}_n", lo=2, hi=20, integer=True),
                    r.choice(f"reinforcement.{face}_dia", BAR_SIZES, default=dia),
                    r.number(f"reinforcement.{face}_layers", lo=1, hi=2, integer=True, default=1))

    bottom, top = bars("bottom", 20), bars("top", 12)
    link_dia = r.choice("reinforcement.link_dia", LINK_SIZES, default=8)
    legs = r.number("reinforcement.legs", lo=2, hi=6, integer=True, default=2)
    cover = r.number("reinforcement.cover", lo=0, hi=150)
    delta_c_dev = r.number("reinforcement.delta_c_dev", lo=0, hi=20, default=10)

    mode = r.choice("actions.mode", ("analysis", "direct"), default="analysis")
    category = r.choice("actions.category", PSI_CATEGORIES, default="B")
    self_weight = r.flag("actions.self_weight", default=True)
    gk = qk = 0.0
    slab, loads, m_sag, m_hog, v_ed = None, [], None, None, None
    if mode == "analysis":
        gk = r.number("actions.gk", lo=0, hi=10000, default=0.0)
        qk = r.number("actions.qk", lo=0, hi=10000, default=0.0)
        loads = _read_loads(r, length)
        if r.flag("actions.slab.on"):
            slab = _read_slab(r)
        if not (gk or qk or self_weight or slab or loads) and not r.errors:
            r.errors["actions.gk"] = "The beam carries no load: enter gk, qk or another load."
    else:
        m_sag = r.number("actions.M_sag", lo=0, hi=1e6, default=0.0)
        m_hog = r.number("actions.M_hog", lo=0, hi=1e6, default=0.0)
        v_ed = r.number("actions.VEd", lo=0, hi=1e6, default=0.0)
        if not (m_sag or m_hog) and not r.errors:
            r.errors["actions.M_sag"] = "Enter a sagging or a hogging moment."
    partitions = r.flag("actions.partitions")
    kprime_limit = r.flag("actions.kprime_limit", default=True)

    E_gpa = None
    if r.choice("stiffness.E_method", ("concrete", "enter"), default="concrete") == "enter":
        E_gpa = r.number("stiffness.E", lo=1, hi=300)
    segments = []
    if mode == "analysis" and r.choice("stiffness.I_method", ("section", "enter"), default="section") == "enter":
        segments = _read_segments(r, length)

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
        room = b - 2 * (cover + link_dia)
        for face, bar in (("bottom", bottom), ("top", top)):
            per_layer = math.ceil(bar.n / bar.layers)
            if per_layer * bar.dia > room:
                r.errors[f"reinforcement.{face}_n"] = (f"{per_layer} bars of {bar.dia} mm do not fit in one layer "
                                                       f"({room:.0f} mm between the links).")
    if r.errors:
        raise ValidationError(r.errors)

    return BeamInput(
        project=project, concrete=Concrete.from_class(concrete_class, gamma_c, alpha_cc),
        steel=Reinforcement(fyk, ductility, gamma_s), dg=dg, shape=shape, flange=flange, b=b, h=h, hf=hf,
        beff_method=beff_method, beff_input=beff_input, b1=b1, b2=b2, length=length, supports=supports,
        bottom=bottom, top=top, link_dia=link_dia, legs=legs, cover=cover, delta_c_dev=delta_c_dev, mode=mode,
        gk=gk, qk=qk, self_weight=self_weight, category=category, slab=slab, loads=loads, E_gpa=E_gpa,
        segments=segments, m_sag=None if m_sag is None else m_sag * 1e6,
        m_hog=None if m_hog is None else m_hog * 1e6, v_ed=None if v_ed is None else v_ed * 1e3,
        partitions=partitions, kprime_limit=kprime_limit, exposure=exposure, cement_group=cement_group,
        fire_period=fire_period,
    )


# ---------------------------------------------------------------- formatting

def kN(n):
    return f"{n / 1e3:.1f}"


def kNm(m):
    return f"{m / 1e6:.1f}"


def _m(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _cmp(ok):
    return "≤" if ok else ">"


def _spread(lo, hi, n):
    return [0.5 * (lo + hi)] if n == 1 else [lo + (hi - lo) * i / (n - 1) for i in range(n)]


# ---------------------------------------------------------------- spans and geometry

@dataclass
class Span:
    i: int
    x1: float             # m
    x2: float
    kind: str             # simple, end, interior or cantilever

    @property
    def l(self):
        return self.x2 - self.x1

    def label(self):
        return f"span {self.i} ({_m(self.x1)}–{_m(self.x2)} m, {SPAN_KINDS[self.kind]})"


def spans_of(length, supports):
    """Spans between supports, and cantilevers beyond the end supports."""
    xs = [s["x"] for s in supports]
    fixed = {s["x"] for s in supports if s["type"] == "fixed"}
    out = []
    if xs[0] > 1e-6:
        out.append(("cantilever", 0.0, xs[0]))
    for j, (a, b) in enumerate(zip(xs, xs[1:])):
        cont_a = a in fixed or j > 0
        cont_b = b in fixed or j < len(xs) - 2
        out.append(({2: "interior", 1: "end", 0: "simple"}[cont_a + cont_b], a, b))
    if xs[-1] < length - 1e-6:
        out.append(("cantilever", xs[-1], length))
    return [Span(i + 1, a, b, kind) for i, (kind, a, b) in enumerate(out) if b - a > 1e-6]


@dataclass
class Face:
    """The longitudinal bars at the bottom or the top of the section."""
    name: str
    n: int
    dia: int
    layers: int
    per_layer: int
    second: int
    a1: float             # axis distance of the outer layer from its face
    a2: float             # axis distance of the inner layer
    a: float              # centroid of the bars from its face
    d: float              # effective depth with this face in tension
    As: float
    clear: float          # clear gap between bars in a layer
    pitch: float          # centre-to-centre spacing in a layer
    layer_gap: float


def _face(inp, bars, name):
    sec_face = inp.cover + inp.link_dia
    a1 = sec_face + bars.dia / 2
    per_layer = math.ceil(bars.n / bars.layers)
    second = bars.n - per_layer
    layer_gap = max(bars.dia, inp.dg + 5, 20)
    a2 = a1 + bars.dia + layer_gap
    a = (per_layer * a1 + second * a2) / bars.n
    width = inp.b - 2 * sec_face
    pitch = (width - bars.dia) / (per_layer - 1) if per_layer > 1 else 0.0
    clear = pitch - bars.dia if per_layer > 1 else width - bars.dia
    return Face(name, bars.n, bars.dia, bars.layers, per_layer, second, a1, a2, a, inp.h - a,
                bars.n * bar_area(bars.dia), clear, pitch, layer_gap)


@dataclass
class Geometry:
    spans: list
    critical: Span        # the span with the largest sagging moment
    beff: float           # effective flange width (= b for a rectangular beam)
    l0: float             # mm
    beff_parts: list
    bottom: Face
    top: Face
    Ac: float
    I_gross: float        # m⁴
    bars: list


def geometry(inp, critical_x=None):
    spans = spans_of(inp.length, inp.supports)
    inside = [s for s in spans if s.kind != "cantilever"] or spans
    critical = next((s for s in inside if critical_x is not None and s.x1 <= critical_x <= s.x2), inside[0])
    l0 = L0_FACTOR[critical.kind] * critical.l * 1000
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
    flanged = inp.shape == "flanged"
    Ac = inp.b * inp.h + ((beff - inp.b) * inp.hf if flanged else 0.0)
    if flanged:
        hw = inp.h - inp.hf
        af, aw = beff * inp.hf, inp.b * hw
        y = (af * (inp.h - inp.hf / 2) + aw * hw / 2) / (af + aw)
        I = (beff * inp.hf**3 / 12 + af * (inp.h - inp.hf / 2 - y) ** 2 + inp.b * hw**3 / 12 + aw * (hw / 2 - y) ** 2)
    else:
        I = inp.b * inp.h**3 / 12
    bottom, top = _face(inp, inp.bottom, "bottom"), _face(inp, inp.top, "top")
    bars = []
    for face, at in ((bottom, lambda dist: dist), (top, lambda dist: inp.h - dist)):
        lo = -inp.b / 2 + inp.cover + inp.link_dia + face.dia / 2
        bars += [{"x": x, "y": at(face.a1), "dia": face.dia, "kind": face.name} for x in _spread(lo, -lo, face.per_layer)]
        if face.second:
            bars += [{"x": x, "y": at(face.a2), "dia": face.dia, "kind": face.name} for x in _spread(lo, -lo, face.second)]
    return Geometry(spans=spans, critical=critical, beff=beff, l0=l0, beff_parts=parts, bottom=bottom, top=top,
                    Ac=Ac, I_gross=I * 1e-12, bars=bars)


# ---------------------------------------------------------------- loading and analysis

def _slab_load(slab):
    """Line loads on the beam from the slab: (factor for bending, factor for shear, description)."""
    kind = slab["type"]
    if kind == "one_way":
        t = slab["trib"]
        return t, t, [f"One-way slab, tributary width btrib = {_m(t)} m: w = wslab × btrib"]
    lx, ly, n = slab["lx"], slab["ly"], slab["sides"]
    sides = f" × {n} (slab on both sides)" if n == 2 else ""
    if kind == "two_way_long":
        r = lx / ly
        fm, fv = n * lx / 6 * (3 - r**2), n * lx / 4 * (2 - r)
        return fm, fv, [
            f"Two-way slab Lx × Ly = {_m(lx)} × {_m(ly)} m, beam along Ly (trapezoidal load):",
            f"weq,moment = wslab × (Lx/6)·[3 − (Lx/Ly)²]{sides} = wslab × {fm:.3f} m",
            f"weq,shear = wslab × (Lx/4)·[2 − Lx/Ly]{sides} = wslab × {fv:.3f} m"]
    fm, fv = n * lx / 3, n * lx / 4
    return fm, fv, [
        f"Two-way slab Lx × Ly = {_m(lx)} × {_m(ly)} m, beam along Lx (triangular load):",
        f"weq,moment = wslab × Lx/3{sides} = wslab × {fm:.3f} m",
        f"weq,shear = wslab × Lx/4{sides} = wslab × {fv:.3f} m"]


def loading(inp):
    """The line loads (kN/m) for bending, shear and the quasi-permanent combination."""
    web = inp.b * (inp.h - inp.hf) if inp.shape == "flanged" else inp.b * inp.h
    sw = CONCRETE_DENSITY * web / 1e6 if inp.self_weight else 0.0
    psi0, _, psi2 = psi_factors(inp.category)
    g, q = inp.gk + sw, inp.qk
    out = {"sw": sw, "g": g, "q": q, "psi2": psi2, "slab": None}
    fm = fv = 0.0
    if inp.slab:
        fm, fv, lines = _slab_load(inp.slab)
        out["slab"] = {"fm": fm, "fv": fv, "lines": lines, "w_area": GAMMA_G * inp.slab["gk"] + GAMMA_Q * inp.slab["qk"],
                       "gk": inp.slab["gk"], "qk": inp.slab["qk"]}
    sg, sq = (inp.slab["gk"], inp.slab["qk"]) if inp.slab else (0.0, 0.0)
    out["w_m"] = GAMMA_G * (g + sg * fm) + GAMMA_Q * (q + sq * fm)
    out["w_v"] = GAMMA_G * (g + sg * fv) + GAMMA_Q * (q + sq * fv)
    out["w_qp"] = g + sg * fm + psi2 * (q + sq * fm)
    return out


ULS = {"Ed": 1.0, "G": GAMMA_G, "Q": GAMMA_Q}


def _analysis_loads(inp, line_w, factors):
    loads = [{"type": "udl", "w": line_w, "x1": 0.0, "x2": inp.length, "line": True}] if line_w > 0 else []
    for ld in inp.loads:
        f = factors[ld["case"]]
        item = dict(ld)
        for key in ("W", "M", "w", "w1", "w2"):
            if key in item:
                item[key] = item[key] * f
        loads.append(item)
    return loads


def run_analysis(inp, geo, ld):
    E = (inp.E_gpa or inp.concrete.Ecm) * 1e6                     # kPa
    inertia = ([{"x1": s["x1"], "x2": s["x2"], "I": s["I"] * 1e-6} for s in inp.segments]
               if inp.segments else geo.I_gross)
    qp = {"Ed": 1 / GAMMA_G, "G": 1.0, "Q": ld["psi2"]}
    try:
        res_m = analyse(inp.length, inp.supports, _analysis_loads(inp, ld["w_m"], ULS), E, inertia)
        res_v = (res_m if abs(ld["w_v"] - ld["w_m"]) < 1e-9
                 else analyse(inp.length, inp.supports, _analysis_loads(inp, ld["w_v"], ULS), E, inertia))
        res_qp = analyse(inp.length, inp.supports, _analysis_loads(inp, ld["w_qp"], qp), E, inertia)
    except AnalysisError as err:
        raise ValidationError({"span.supports": str(err)}) from None
    return res_m, res_v, res_qp, E, inertia


def _peak(res, lo, hi, sagging):
    """Index of the largest sagging (or hogging) moment between x = lo and x = hi."""
    best = None
    for i, (x, m) in enumerate(zip(res["x"], res["M"])):
        if lo - 1e-9 <= x <= hi + 1e-9 and (best is None or (m > res["M"][best] if sagging else m < res["M"][best])):
            best = i
    return best


def design_actions(inp, geo):
    """Design moments and shear for every critical section, with the analysis behind them."""
    act = {"mode": inp.mode, "loads": None, "res_m": None}
    if inp.mode == "direct":
        act.update(M_sag=inp.m_sag, M_hog=inp.m_hog, VEd=inp.v_ed, x_sag=None, x_hog=None, x_v=None,
                   qp_sag=None, qp_hog=None, v_hogging=inp.m_hog > 0 and not inp.m_sag)
        return act
    ld = loading(inp)
    res_m, res_v, res_qp, E, inertia = run_analysis(inp, geo, ld)
    env = res_m["envelope"]
    m_sag, m_hog = env["sagging"]["M"], -env["hogging"]["M"]
    tol = max(1e-3 * max(m_sag, m_hog), 0.01)
    m_sag, m_hog = (m_sag if m_sag > tol else 0.0), (m_hog if m_hog > tol else 0.0)
    v_ed = res_v["envelope"]["shear"]["V"]
    v_ed = v_ed if v_ed > 0.01 else 0.0
    x_v = res_v["envelope"]["shear"]["x"]
    i_v = min(range(len(res_m["x"])), key=lambda i: abs(res_m["x"][i] - x_v))

    def ratio(i):
        m = res_m["M"][i]
        return min(max(res_qp["M"][i] / m, 0.05), 1.0) if abs(m) > 1e-9 else None

    i_sag, i_hog = env["sagging"]["i"], env["hogging"]["i"]
    act.update(loads=ld, res_m=res_m, res_v=res_v, res_qp=res_qp, E=E, inertia=inertia,
               M_sag=m_sag * 1e6, x_sag=env["sagging"]["x"], M_hog=m_hog * 1e6, x_hog=env["hogging"]["x"],
               VEd=v_ed * 1e3, x_v=x_v, qp_sag=ratio(i_sag), qp_hog=ratio(i_hog),
               v_hogging=res_m["M"][i_v] < -tol)
    return act


def _actions_checks(inp, geo, act):
    if act["mode"] == "direct":
        return [CheckResult(
            "actions", GROUPS[3], "Design actions", INFO,
            result=f"M+Ed = {kNm(act['M_sag'])} kNm, M−Ed = {kNm(act['M_hog'])} kNm, VEd = {kN(act['VEd'])} kN",
            working=[f"Entered from the analysis: sagging M+Ed = {kNm(act['M_sag'])} kNm, "
                     f"hogging M−Ed = {kNm(act['M_hog'])} kNm, VEd = {kN(act['VEd'])} kN",
                     "A moment or shear entered as zero is not designed for"])]
    ld, res = act["loads"], act["res_m"]
    lines = [f"Beam {_m(inp.length)} m long on {len(inp.supports)} support{'s' if len(inp.supports) > 1 else ''}: "
             + ", ".join(f"{SUPPORT_NAMES[s['type']]} at {_m(s['x'])} m" for s in inp.supports)]
    if inp.self_weight:
        what = "web below the flange" if inp.shape == "flanged" else "beam"
        depth = inp.h - inp.hf if inp.shape == "flanged" else inp.h
        lines.append(f"Self-weight of the {what} = {CONCRETE_DENSITY:g} × {inp.b:g} × {depth:g}/10⁶ = {ld['sw']:.2f} kN/m")
    sw_text = f" + {ld['sw']:.2f}" if inp.self_weight else ""
    lines.append(f"Permanent gk = {inp.gk:g}{sw_text} = {ld['g']:.2f} kN/m; variable qk = {inp.qk:g} kN/m "
                 f"(category {inp.category}, ψ2 = {ld['psi2']:g})")
    slab = ld["slab"]
    if slab:
        lines += slab["lines"]
        lines.append(f"wslab = 1.35·gk,slab + 1.5·qk,slab = 1.35 × {slab['gk']:g} + 1.5 × {slab['qk']:g} "
                     f"= {slab['w_area']:.2f} kN/m²")
    G = GAMMA_G * (ld["g"] + (slab["gk"] * slab["fm"] if slab else 0))
    Q = GAMMA_Q * (ld["q"] + (slab["qk"] * slab["fm"] if slab else 0))
    if slab:
        lines.append(f"w = 1.35·gk + 1.5·qk + wslab × {slab['fm']:.3f} = 1.35 × {ld['g']:.2f} + 1.5 × {ld['q']:.2f} "
                     f"+ {slab['w_area'] * slab['fm']:.2f} = {ld['w_m']:.2f} kN/m (for bending)")
        if abs(ld["w_v"] - ld["w_m"]) > 1e-9:
            lines.append(f"w = 1.35·gk + 1.5·qk + wslab × {slab['fv']:.3f} = {ld['w_v']:.2f} kN/m (for shear and reactions)")
    else:
        lines.append(f"G = 1.35·gk = {G:.2f} kN/m, Q = 1.5·qk = {Q:.2f} kN/m; w = G + Q = {ld['w_m']:.2f} kN/m")
    for item in inp.loads:
        lines.append("Further load: " + _describe_load(item))
    lines.append(f"Matrix stiffness analysis: {len(res['nodes'])} nodes, {len(res['elements'])} element{'s' if len(res['elements']) > 1 else ''}, "
                 f"{res['free_dofs']} free degrees of freedom; E = {act['E'] / 1e6:g} GPa, "
                 + ("I as entered along the beam" if inp.segments else f"I = {geo.I_gross * 1e12 / 1e6:.0f}×10⁶ mm⁴ "
                    "(gross section)"))
    lines.append("Reactions: " + "; ".join(
        f"node {r['node']} ({_m(r['x'])} m) Ry = {r['Ry']:.2f} kN" + (f", M = {r['M']:.2f} kNm" if r["M"] is not None else "")
        for r in act["res_v"]["reactions"]))
    parts = []
    if act["M_sag"]:
        parts.append(f"M+Ed = {kNm(act['M_sag'])} kNm at x = {_m(act['x_sag'])} m")
    else:
        parts.append("no sagging moment")
    if act["M_hog"]:
        parts.append(f"M−Ed = {kNm(act['M_hog'])} kNm at x = {_m(act['x_hog'])} m")
    else:
        parts.append("no hogging moment")
    parts.append(f"VEd = {kN(act['VEd'])} kN at x = {_m(act['x_v'])} m" if act["VEd"] else "no shear")
    lines.append("Design values from the analysis: " + "; ".join(parts))
    result = ", ".join(p for p in (f"M+Ed = {kNm(act['M_sag'])} kNm" if act["M_sag"] else "",
                                   f"M−Ed = {kNm(act['M_hog'])} kNm" if act["M_hog"] else "",
                                   f"VEd = {kN(act['VEd'])} kN" if act["VEd"] else "") if p)
    return [CheckResult("actions", GROUPS[3], "Design actions from the analysis", INFO, result=result, working=lines)]


def _describe_load(ld):
    case = {"Ed": "design value", "G": "permanent, × 1.35", "Q": "variable, × 1.5"}[ld["case"]]
    if ld["type"] == "point":
        return f"point load {ld['W']:g} kN at x = {_m(ld['x'])} m ({case})"
    if ld["type"] == "moment":
        return f"moment {ld['M']:g} kNm clockwise at x = {_m(ld['x'])} m ({case})"
    if ld["type"] == "udl":
        return f"uniform load {ld['w']:g} kN/m from x = {_m(ld['x1'])} to {_m(ld['x2'])} m ({case})"
    return f"varying load {ld['w1']:g} → {ld['w2']:g} kN/m from x = {_m(ld['x1'])} to {_m(ld['x2'])} m ({case})"


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
    phi = max(inp.bottom.dia, inp.top.dia)
    c_main = inp.cover + inp.link_dia
    req_main = phi + extra + dc
    ok_main = c_main >= req_main
    main = CheckResult(
        "cover_main", GROUPS[1], "Cover to main bars", PASS if ok_main else FAIL,
        result=f"{c_main:g} {'≥' if ok_main else '<'} {req_main:g} mm", value=c_main, limit=req_main, unit="mm",
        utilisation=req_main / c_main,
        working=[f"Cover to main bars = cnom + φlink = {inp.cover:g} + {inp.link_dia} = {c_main:g} mm",
                 f"Required ≥ φ + Δcdev = {phi}{' + 5' if extra else ''} + {dc:g} = {req_main:g} mm (largest bar φ{phi})"],
        target="cover")
    return [dur, bond, main]


def _fire_checks(inp, geo):
    if inp.fire_period == "none":
        return [CheckResult("fire", GROUPS[2], "Fire resistance", NA, result="Not required",
                            note="No fire resistance period specified.", target="cover")]
    spans = [s for s in geo.spans if s.kind != "cantilever"]
    continuous = bool(spans) and (len(spans) > 1 or any(s["type"] == "fixed" for s in inp.supports))
    support = "continuous" if continuous else "simple"
    a = geo.bottom.a
    ok, gov, evaluated = fire.check_beam_fire(inp.fire_period, support, inp.b, a)
    kind = "continuous beam" if continuous else (
        "simply supported beam" if spans else "cantilever, taken as a simply supported beam")
    lines = [f"{inp.fire_period}, {kind} exposed on three sides",
             f"Axis distance of the bottom bars a = {a:.0f} mm; web width b = {inp.b:g} mm"]
    lines += [f"Option bmin/a = {o['b_min']}/{o['a']}: {'satisfied' if o['ok'] else 'not satisfied'}" for o in evaluated]
    return [CheckResult(
        "fire", GROUPS[2], f"Fire resistance {inp.fire_period}", PASS if ok else FAIL,
        result=f"{inp.b:g}/{a:.0f} vs {gov['b_min']}/{gov['a']} mm",
        utilisation=max(gov["b_min"] / inp.b, gov["a"] / a), working=lines, target="cover",
        note="Corner bars in a single layer also need a side axis distance of a + 10 mm."
        if ok else "Widen the web or increase the axis distance (larger cover).")]


def _design(inp, geo, M, sagging):
    """Bending design for a moment M (N·mm): sagging puts the bottom bars in tension."""
    conc, steel = inp.concrete, inp.steel
    kp = flexure.k_prime(1.0, inp.kprime_limit)
    t, c = (geo.bottom, geo.top) if sagging else (geo.top, geo.bottom)
    flange = sagging and inp.shape == "flanged"
    if flange:
        res = flexure.flanged(M, geo.beff, inp.b, inp.hf, t.d, conc.fck, steel.fyd, kp)
    else:
        res = flexure.rectangular(M, inp.b, t.d, c.a1, conc.fck, steel.fyd, kp)
    res.update(width=geo.beff if flange else inp.b, d=t.d, d2=c.a1, t=t, c=c, flange=flange, M=M)
    return res


def _bending_checks(inp, geo, act, sagging):
    """Bending design, tension and compression steel for the sagging or the hogging peak."""
    tag, word = ("sag", "Sagging") if sagging else ("hog", "Hogging")
    M = act["M_sag"] if sagging else act["M_hog"]
    x = act["x_sag"] if sagging else act["x_hog"]
    if not M:
        return [CheckResult(f"bending_{tag}", GROUPS[4], f"{word}: bending design", NA,
                            result=f"No {word.lower()} moment",
                            working=[f"The analysis gives no {word.lower()} moment, so none is designed for"])], None
    conc, steel = inp.concrete, inp.steel
    res = _design(inp, geo, M, sagging)
    t, c, d = res["t"], res["c"], res["d"]
    symbol = "M+Ed" if sagging else "M−Ed"
    where = f" at x = {_m(x)} m" if x is not None else ""
    lines = [f"{symbol} = {kNm(M)} kNm{where} ({'tension in the bottom bars' if sagging else 'tension in the top bars'})"]
    layer = f" − layer offset ({t.layers} layers)" if t.layers == 2 else ""
    lines.append(f"d = h − cnom − φlink − φ/2{layer} = {inp.h:g} − {inp.cover:g} − {inp.link_dia} − {t.dia / 2:g}"
                 f"{f' − {t.a - t.a1:.0f}' if t.layers == 2 else ''} = {d:.0f} mm")
    if res["flange"]:
        if inp.beff_method == "enter":
            lines.append(f"beff = {geo.beff:.0f} mm (entered)")
        else:
            lines.append(f"l0 = {L0_FACTOR[geo.critical.kind]:g} × l = {L0_FACTOR[geo.critical.kind]:g} × "
                         f"{geo.critical.l * 1000:.0f} = {geo.l0:.0f} mm ({geo.critical.label()})")
            for i, (bi, part) in enumerate(geo.beff_parts, start=1):
                lines.append(f"beff,{i} = min(0.2·b{i} + 0.1·l0, 0.2·l0, b{i}) = min({0.2 * bi + 0.1 * geo.l0:.0f}, "
                             f"{0.2 * geo.l0:.0f}, {bi:g}) = {part:.0f} mm")
            lines.append(f"beff = bw + Σ beff,i = {geo.beff:.0f} mm")
    elif not sagging and inp.shape == "flanged":
        lines.append("Flange in tension: designed as a rectangle of the web width bw")
    raw_kp = flexure.k_prime(1.0, uk_limit=False)
    kp_text = (f"{raw_kp:.3f}, limited to {res['kp']:.3f} for a ductile failure" if res["kp"] < raw_kp
               else f"{res['kp']:.3f}")
    lines += [f"K = M/(b·d²·fck) = {kNm(M)}×10⁶ / ({res['width']:.0f} × {d:.0f}² × {conc.fck:g}) = {res['K']:.4f}",
              f"K′ = 0.60δ − 0.18δ² − 0.21 = {kp_text} (δ = 1.0: moments from an elastic analysis)"]
    if "z" in res and res.get("in_flange", True) and not res.get("compression"):
        lines += [f"z = d/2·[1 + √(1 − 3.53K)] ≤ 0.95d = {res['z']:.0f} mm", f"x = 2.5(d − z) = {res['x']:.0f} mm"]
    if res["flange"]:
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
    summary = "compression reinforcement needed" if res.get("compression") else "no compression reinforcement needed"
    out = [CheckResult(f"bending_{tag}", GROUPS[4], f"{word}: bending design", INFO if res["ok"] else FAIL,
                       result=f"K = {res['K']:.3f} {'≤' if res['K'] <= res['kp'] else '>'} K′ = {res['kp']:.3f}",
                       working=lines + [f"So {summary}"] if res["ok"] else lines,
                       note="" if res["ok"] else "Redesign the section: it is too small for this moment.",
                       target="section")]
    face, other = t.name, c.name
    if not res["ok"]:
        out.append(CheckResult(f"tension_{tag}", GROUPS[4], f"{word}: {face} reinforcement", FAIL,
                               result="Section too small", note="Increase the depth or the width of the section.",
                               target="bars"))
        out.append(CheckResult(f"compression_{tag}", GROUPS[4], f"{word}: compression reinforcement", NA,
                               result="Not assessed"))
        return out, res
    as_req, ok = res["As"], t.As >= res["As"]
    if res["flange"] and not res.get("in_flange"):
        how = f"As = MR,f/(fyd·(d − 0.5hf)) + (M − MR,f)/(fyd·z) = {as_req:.0f} mm²"
    elif res.get("compression"):
        how = f"As = K′·fck·b·d²/(fyd·z) + As2·fsc/fyd = {as_req:.0f} mm²"
    else:
        how = f"As = M/(fyd·z) = {kNm(M)}×10⁶ / ({steel.fyd:.1f} × {res['z']:.0f}) = {as_req:.0f} mm²"
    out.append(CheckResult(
        f"tension_{tag}", GROUPS[4], f"{word}: {face} reinforcement", PASS if ok else FAIL,
        result=f"{t.As:.0f} {'≥' if ok else '<'} {as_req:.0f} mm²", value=t.As, limit=as_req, unit="mm²",
        utilisation=as_req / t.As, working=[how, f"Provided {t.n}H{t.dia} ({face}) = {t.As:.0f} mm²"], target="bars",
        note="" if ok else f"Add {face} bars or use larger bars."))
    if res.get("compression"):
        ok2 = c.As >= res["As2"]
        out.append(CheckResult(
            f"compression_{tag}", GROUPS[4], f"{word}: compression reinforcement", PASS if ok2 else FAIL,
            result=f"{c.As:.0f} {'≥' if ok2 else '<'} {res['As2']:.0f} mm²", value=c.As, limit=res["As2"],
            unit="mm²", utilisation=res["As2"] / c.As,
            working=[f"As2 = (K − K′)·fck·b·d²/(fsc·(d − d2)) = {res['As2']:.0f} mm² (d2 = {res['d2']:.0f} mm)",
                     f"Provided {c.n}H{c.dia} ({other}) = {c.As:.0f} mm²"], target="bars"))
    else:
        out.append(CheckResult(
            f"compression_{tag}", GROUPS[4], f"{word}: compression reinforcement", NA, result="Not needed (K ≤ K′)",
            working=[f"K ≤ K′; the {c.n}H{c.dia} {other} bars are not needed in compression"]))
    return out, res


def _shear_checks(inp, geo, act, res_sag, res_hog):
    if not act["VEd"]:
        return [CheckResult("strut", GROUPS[5], "Concrete strut capacity", NA, result="No shear force",
                            working=["The analysis gives no shear force, so none is designed for"])], None
    conc, steel = inp.concrete, inp.steel
    face = geo.top if act["v_hogging"] else geo.bottom
    d, bw = face.d, inp.b
    z = 0.9 * d
    v_ed = act["VEd"] / (bw * z)
    cot, v25, v10 = flexure.vertical_shear(v_ed, conc.fck)
    fywd = steel.fyd
    out = []
    where = f" at x = {_m(act['x_v'])} m" if act["x_v"] is not None else ""
    lines = [f"VEd = {kN(act['VEd'])} kN{where}; d = {d:.0f} mm to the {face.name} bars "
             f"({'hogging' if act['v_hogging'] else 'sagging'} there)",
             f"vEd = VEd/(bw·z) = {kN(act['VEd'])}×10³ / ({bw:g} × 0.9 × {d:.0f}) = {v_ed:.2f} MPa",
             f"vRd,max = 0.4·fck·(1 − fck/250)/(cot θ + tan θ): {v25:.2f} MPa at cot θ = 2.5, {v10:.2f} MPa at cot θ = 1.0"]
    if cot is None:
        out.append(CheckResult("strut", GROUPS[5], "Concrete strut capacity", FAIL,
                               result=f"vEd {v_ed:.2f} > vRd,max {v10:.2f} MPa", utilisation=v_ed / v10,
                               working=lines, note="Increase the web width or the concrete class.", target="section"))
        out.append(CheckResult("links", GROUPS[5], "Shear links (calculated)", NA, result="Not assessed"))
        return out, None
    if cot == 2.5:
        lines.append("vEd ≤ vRd,max at cot θ = 2.5, so θ = 21.8° (cot θ = 2.5)")
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
                 f"Provide H{inp.link_dia} links ({inp.legs} legs) at {s_near} mm where the shear is largest "
                 f"(multiple of 25 mm)",
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

    if inp.shape == "flanged" and res_sag and res_sag["ok"]:
        out.append(_longitudinal_shear(inp, geo, act, res_sag))
    return out, links


def _longitudinal_shear(inp, geo, act, res):
    conc, steel = inp.concrete, inp.steel
    dx = geo.l0 / 4
    z = res["z"] if res.get("in_flange") else res["d"] - 0.5 * inp.hf
    outstand = (geo.beff - inp.b) / 2 if inp.flange == "T" else geo.beff - inp.b
    delta_f = 0.75 * act["M_sag"] / z * outstand / geo.beff
    v = delta_f / (inp.hf * dx)
    fctd = 0.7 * conc.fctm / conc.gamma_c
    v_max = 0.16 * conc.fck * (1 - conc.fck / 250)
    lines = [f"Δx = half the distance from zero to maximum moment = l0/4 = {dx:.0f} mm",
             f"ΔFd = (0.75·M/z)·(outstand/beff) = (0.75 × {kNm(act['M_sag'])}×10⁶ / {z:.0f}) × "
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


def _steel_stress(inp, res, qp_ratio):
    """Service stress in the tension steel, used for deflection and crack control."""
    t = res["t"]
    ratio = res["As"] / t.As
    if qp_ratio is None:
        return 310 * ratio, [f"σs ≈ 310·As,req/As,prov = 310 × {res['As']:.0f}/{t.As:.0f} = {310 * ratio:.0f} MPa "
                             f"(loads not given)"]
    su = inp.steel.fyd * qp_ratio
    s = max(10.0, su * ratio)
    return s, [f"σsu = fyd·Mqp/MEd = {inp.steel.fyd:.1f} × {qp_ratio:.3f} = {su:.0f} MPa "
               f"(quasi-permanent to design moment from the analysis)",
               f"σs = σsu·As,req/As,prov = {su:.0f} × {res['As']:.0f}/{t.As:.0f} = {s:.0f} MPa"]


def _deflection_checks(inp, geo, act):
    lines, util, status, worst_line = [], [], [], None
    res_m, res_qp = act["res_m"], act.get("res_qp")
    for span in geo.spans:
        sagging = span.kind != "cantilever"
        if res_m:
            i = _peak(res_m, span.x1, span.x2, sagging)
            m = res_m["M"][i] if i is not None else 0.0
            M = (m if sagging else -m) * 1e6
            qp = min(max(res_qp["M"][i] / m, 0.05), 1.0) if i is not None and abs(m) > 1e-9 else None
        else:
            M = act["M_sag"] if sagging else act["M_hog"]
            qp = None
        name = span.label()
        if M <= max(1e-3 * max(act["M_sag"], act["M_hog"]), 1e4):
            lines.append(f"{name[0].upper()}{name[1:]}: no {'sagging' if sagging else 'hogging'} moment, not checked")
            continue
        res = _design(inp, geo, M, sagging)
        if not res["ok"]:
            lines.append(f"{name[0].upper()}{name[1:]}: not assessed, the section is too small for the moment")
            status.append(NA)
            continue
        conc, d, t = inp.concrete, res["d"], res["t"]
        area = geo.beff * inp.hf + inp.b * (d - inp.hf) if res["flange"] else inp.b * d
        rho, rho_c = res["As"] / area, res["As2"] / area
        K = DEFLECTION_K[span.kind]
        basic = flexure.basic_span_depth(K, conc.fck, rho, rho_c)
        rho0 = math.sqrt(conc.fck) / 1000
        f1 = max(0.8, 1 - 0.1 * (geo.beff / inp.b - 1)) if res["flange"] else 1.0
        f2 = 7 / span.l if inp.partitions and span.l > 7 and span.kind != "cantilever" else 1.0
        sigma, sigma_lines = _steel_stress(inp, res, qp)
        f3 = min(310 / sigma, 1.5)
        allowed = basic * f1 * f2 * f3
        actual = span.l * 1000 / d
        ok = actual <= allowed
        head = f"{name[0].upper()}{name[1:]}: M = {kNm(M)} kNm, {t.name} bars, d = {d:.0f} mm"
        lines += [head,
                  f"  ρ = As,req/{'(beff·hf + bw·(d − hf))' if res['flange'] else '(b·d)'} = {100 * rho:.3f} %, "
                  f"ρ′ = {100 * rho_c:.3f} %, ρ0 = √fck/1000 = {100 * rho0:.3f} %",
                  (f"  ρ ≤ ρ0: basic l/d = K·[11 + 1.5√fck·ρ0/ρ + 3.2√fck·(ρ0/ρ − 1)^1.5] = {basic:.1f} (K = {K:g})"
                   if rho <= rho0 else
                   f"  ρ > ρ0: basic l/d = K·[11 + 1.5√fck·ρ0/(ρ − ρ′) + √fck·√(ρ′/ρ0)/12] = {basic:.1f} (K = {K:g})")]
        if res["flange"]:
            lines.append(f"  F1 = 1 − 0.1·(beff/bw − 1) ≥ 0.8 = {f1:.2f}")
        if f2 < 1:
            lines.append(f"  F2 = 7/leff = 7/{span.l:.2f} = {f2:.2f} (span over 7 m carrying brittle partitions)")
        lines += ["  " + s for s in sigma_lines]
        lines += [f"  F3 = 310/σs ≤ 1.5 = {f3:.2f}; allowable l/d = {basic:.1f} × {f1:.2f} × {f2:.2f} × {f3:.2f} "
                  f"= {allowed:.1f}",
                  f"  Actual l/d = {span.l * 1000:.0f}/{d:.0f} = {actual:.1f} {_cmp(ok)} {allowed:.1f}"]
        status.append(PASS if ok else FAIL)
        util.append(actual / allowed)
        if worst_line is None or actual / allowed >= max(util):
            worst_line = f"l/d {actual:.1f} {_cmp(ok)} {allowed:.1f}" + (f" ({name.split(' (')[0]})" if len(geo.spans) > 1 else "")
    out = []
    if not util:
        out.append(CheckResult("deflection", GROUPS[6], "Span to depth ratio", NA, result="Not assessed",
                               working=lines or ["No span to check"]))
    else:
        bad = FAIL in status
        out.append(CheckResult("deflection", GROUPS[6], "Span to depth ratio", FAIL if bad else PASS,
                               result=worst_line, utilisation=max(util), working=lines, target="section",
                               note="Increase the depth or add tension reinforcement." if bad else ""))
    if res_m:
        e = res_m["envelope"]["deflection"]
        span = next((s for s in geo.spans if s.x1 <= e["x"] <= s.x2), geo.spans[0])
        ratio = span.l * 1000 / abs(e["d"]) if abs(e["d"]) > 1e-9 else math.inf
        out.append(CheckResult(
            "elastic_deflection", GROUPS[6], "Elastic deflection (for information)", INFO,
            result=f"δ = {abs(e['d']):.2f} mm at x = {_m(e['x'])} m",
            working=[f"Largest deflection from the analysis under the design loads: δ = {abs(e['d']):.2f} mm at "
                     f"x = {_m(e['x'])} m, in {span.label()}: l/δ = {ratio:.0f}",
                     f"Gross section and short-term E = {act['E'] / 1e6:g} GPa, without creep or cracking; "
                     "the span-to-depth check above is the code check"]))
    return out


def _detailing_checks(inp, geo, act, res_sag, res_hog):
    conc, steel = inp.concrete, inp.steel
    out = []
    for res, sagging in ((res_sag, True), (res_hog, False)):
        if not res:
            continue
        t = res["t"]
        tag = "bottom" if sagging else "top"
        bt = geo.beff if (inp.shape == "flanged" and not sagging) else inp.b
        as_min = max(0.26 * conc.fctm / steel.fyk * bt * t.d, 0.0013 * bt * t.d)
        ok = t.As >= as_min
        out.append(CheckResult(
            f"as_min_{tag}", GROUPS[7], f"Minimum {tag} reinforcement", PASS if ok else FAIL,
            result=f"{t.As:.0f} {'≥' if ok else '<'} {as_min:.0f} mm²", value=t.As, limit=as_min, unit="mm²",
            utilisation=as_min / t.As,
            working=[f"{tag.capitalize()} bars in tension ({'sagging' if sagging else 'hogging'}): As,min = "
                     f"0.26·fctm·bt·d/fyk ≥ 0.0013·bt·d = max({0.26 * conc.fctm / steel.fyk * bt * t.d:.0f}, "
                     f"{0.0013 * bt * t.d:.0f}) = {as_min:.0f} mm² (bt = {bt:.0f} mm)"], target="bars"))
    as_max = 0.04 * geo.Ac
    total = geo.bottom.As + geo.top.As
    ok = total <= as_max
    out.append(CheckResult(
        "as_max", GROUPS[7], "Maximum reinforcement", PASS if ok else FAIL,
        result=f"{total:.0f} {_cmp(ok)} {as_max:.0f} mm²", value=total, limit=as_max, unit="mm²",
        utilisation=total / as_max,
        working=[f"As,max = 0.04·Ac = 0.04 × {geo.Ac:.0f} = {as_max:.0f} mm² (bottom + top bars)"],
        target="bars"))
    for face in (geo.bottom, geo.top):
        s_min = max(face.dia, inp.dg + 5, 20)
        ok = face.clear >= s_min
        out.append(CheckResult(
            f"bar_spacing_{face.name}", GROUPS[7], f"Clear spacing, {face.name} bars", PASS if ok else FAIL,
            result=f"{face.clear:.0f} {'≥' if ok else '<'} {s_min:.0f} mm", value=face.clear, limit=s_min, unit="mm",
            utilisation=s_min / face.clear if face.clear > 0 else math.inf,
            working=[f"{face.per_layer} bars of {face.dia} mm in a layer: clear gap = {face.clear:.0f} mm",
                     f"Minimum = max(φ, dg + 5, 20) = max({face.dia}, {inp.dg + 5:g}, 20) = {s_min:.0f} mm"]
            + ([f"Vertical gap between the two layers = {face.layer_gap:.0f} mm"] if face.layers == 2 else []),
            target="bars"))
    for res, sagging in ((res_sag, True), (res_hog, False)):
        if not (res and res["ok"]):
            continue
        t = res["t"]
        w_max = 0.4 if inp.exposure in ("XC1",) else 0.3
        sigma, sigma_lines = _steel_stress(inp, res, act["qp_sag"] if sagging else act["qp_hog"])
        size, spacing = tables.crack_limits(sigma, w_max)
        if size is None:
            ok, result, tail = False, f"σs = {sigma:.0f} > 360 MPa", ["Steel stress above the tabulated range"]
        else:
            ok = t.dia <= size or (t.per_layer > 1 and t.pitch <= spacing)
            result = (f"φ{t.dia} ≤ {size:.0f} mm" if t.dia <= size
                      else f"spacing {t.pitch:.0f} {_cmp(t.pitch <= spacing)} {spacing:.0f} mm")
            tail = [f"wmax = {w_max} mm: maximum bar size {size:.0f} mm or maximum spacing {spacing:.0f} mm",
                    f"Provided φ{t.dia} at {t.pitch:.0f} mm centres: {'satisfied' if ok else 'neither limit is met'}"]
        out.append(CheckResult(
            f"cracking_{t.name}", GROUPS[7], f"Crack control, {t.name} bars", PASS if ok else FAIL, result=result,
            working=sigma_lines + tail, target="bars",
            note="" if ok else "Use smaller bars at closer spacing, or add reinforcement to lower the stress."))
    return out


def _input_echo(inp, geo):
    supports = ", ".join(f"{SUPPORT_NAMES[s['type']]} at {_m(s['x'])} m" for s in inp.supports)
    rows = [("Section", "Rectangular" if inp.shape == "rectangular" else
             f"Flanged ({'T' if inp.flange == 'T' else 'L'}): beff = {geo.beff:.0f} mm, hf = {inp.hf:g} mm"),
            ("Width × depth", f"{inp.b:g} × {inp.h:g} mm" + (" (web)" if inp.shape == "flanged" else "")),
            ("Concrete", inp.concrete.name), ("fyk", f"{inp.steel.fyk:g} MPa (class {inp.steel.ductility})"),
            ("Beam", f"{_m(inp.length)} m; supports: {supports}"),
            ("Spans", "; ".join(s.label() for s in geo.spans)),
            ("Bottom bars", f"{inp.bottom.n}H{inp.bottom.dia} in {inp.bottom.layers} layer{'s' if inp.bottom.layers > 1 else ''}"),
            ("Top bars", f"{inp.top.n}H{inp.top.dia} in {inp.top.layers} layer{'s' if inp.top.layers > 1 else ''}"),
            ("Links", f"H{inp.link_dia}, {inp.legs} legs (spacing calculated)"),
            ("Nominal cover", f"{inp.cover:g} mm (Δcdev = {inp.delta_c_dev:g} mm)")]
    if inp.mode == "analysis":
        rows.append(("Loads on the beam", f"gk = {inp.gk:g} kN/m{' + self-weight' if inp.self_weight else ''}, "
                                          f"qk = {inp.qk:g} kN/m (category {inp.category}); G = 1.35gk, Q = 1.5qk"))
        if inp.slab:
            s = inp.slab
            size = f"btrib = {_m(s['trib'])} m" if s["type"] == "one_way" else f"Lx × Ly = {_m(s['lx'])} × {_m(s['ly'])} m"
            rows.append(("Slab", f"{SLAB_TYPES[s['type']]}, {size}, gk = {s['gk']:g}, qk = {s['qk']:g} kN/m²"))
        for item in inp.loads:
            rows.append(("Further load", _describe_load(item)))
        rows.append(("Stiffness", (f"E = {inp.E_gpa:g} GPa" if inp.E_gpa else f"E = Ecm = {inp.concrete.Ecm:g} GPa")
                     + (", I entered: " + "; ".join(f"{_m(s['x1'])}–{_m(s['x2'])} m: {s['I']:g}×10⁶ mm⁴" for s in inp.segments)
                        if inp.segments else ", I of the gross section")))
    else:
        rows.append(("Design actions", f"M+Ed = {kNm(inp.m_sag)} kNm, M−Ed = {kNm(inp.m_hog)} kNm, VEd = {kN(inp.v_ed)} kN"))
    rows += [("Exposure", f"{durability.ROWS_BY_ID[inp.exposure]['classes']} ({inp.cement_group})"),
             ("Fire", "None" if inp.fire_period == "none" else inp.fire_period)]
    return [{"label": k, "value": v} for k, v in rows]


ASSUMPTIONS = [
    "Design to BS EN 1992-1-1 with UK National Annex values; rectangular stress block for concrete up to C50/60.",
    "Design loads G = 1.35·gk and Q = 1.5·qk. Further loads entered as design values are used as they are.",
    "Moments, shears, reactions and deflections from a linear elastic matrix stiffness analysis, without "
    "redistribution (δ = 1.0).",
    "Every critical value from the analysis is designed for: the largest sagging moment with the bottom bars, the "
    "largest hogging moment with the top bars and the largest shear. Zero values are not designed for.",
    "Shear by the variable strut inclination method with vertical links (cot θ = 2.5 where possible).",
    "Deflection by span to effective depth ratios for each span; the service steel stress comes from the "
    "quasi-permanent to design moment ratio of the analysis (310 MPa when only design actions are given).",
    "Crack widths limited to 0.3 mm (0.4 mm in exposure XC1) through the bar size or bar spacing.",
    "Durability covers follow BS 8500 for a 50-year working life and 20 mm maximum aggregate.",
    "Fire resistance by the tabulated method of BS EN 1992-1-2 for beams exposed on three sides.",
]


def _plots(inp, geo, act):
    section = {"shape": inp.shape, "flange": inp.flange, "b": inp.b, "h": inp.h, "hf": inp.hf, "beff": geo.beff,
               "cover": inp.cover, "link_dia": inp.link_dia, "legs": inp.legs, "bars": geo.bars}
    model = {"length": inp.length, "supports": inp.supports}
    if not act["res_m"]:
        return {"section": section, "model": model, "analysis": None}
    res_m, res_v, ld = act["res_m"], act["res_v"], act["loads"]
    segments = ([{"x1": s["x1"], "x2": s["x2"], "I": s["I"]} for s in inp.segments] if inp.segments
                else [{"x1": 0.0, "x2": inp.length, "I": geo.I_gross * 1e6}])
    analysis = {
        "length": inp.length, "E": act["E"] / 1e6, "segments": segments, "supports": inp.supports,
        "loads": _analysis_loads(inp, ld["w_m"], ULS), "w": ld["w_m"],
        "w_shear": ld["w_v"] if abs(ld["w_v"] - ld["w_m"]) > 1e-9 else None,
        "nodes": res_m["nodes"], "elements": res_m["elements"], "free_dofs": res_m["free_dofs"],
        "reactions": res_v["reactions"], "x": res_m["x"], "M": res_m["M"], "V": res_v["V"],
        "delta": res_m["delta"], "events": {"V": res_v["events"]["V"], "M": res_m["events"]["M"],
                                             "zeros": res_m["events"]["zeros"]},
        "envelope": {**res_m["envelope"], "shear": res_v["envelope"]["shear"]},
        "design": {"sag": act["M_sag"] / 1e6, "x_sag": act["x_sag"], "hog": act["M_hog"] / 1e6,
                   "x_hog": act["x_hog"], "V": act["VEd"] / 1e3, "x_v": act["x_v"]},
    }
    return {"section": section, "model": model, "analysis": analysis}


def _summary(res):
    if not res:
        return None
    return {"M": res["M"] / 1e6, "K": res["K"], "kp": res["kp"], "z": res.get("z"), "d": res["d"],
            "As_req": res["As"] if res["ok"] else None, "As2_req": res["As2"] if res["ok"] else None,
            "As": res["t"].As, "compression": bool(res.get("compression")), "ok": res["ok"], "face": res["t"].name}


def check_beam(data):
    inp = parse_input(data)
    geo = geometry(inp)
    act = design_actions(inp, geo)
    if act["x_sag"] is not None and act["M_sag"]:
        geo = geometry(inp, act["x_sag"])        # effective flange width from the span with the sagging peak
    checks = _scope_checks(inp) + _cover_checks(inp) + _fire_checks(inp, geo) + _actions_checks(inp, geo, act)
    sag_checks, res_sag = _bending_checks(inp, geo, act, True)
    hog_checks, res_hog = _bending_checks(inp, geo, act, False)
    checks += sag_checks + hog_checks
    shear, links = _shear_checks(inp, geo, act, res_sag, res_hog)
    checks += shear + _deflection_checks(inp, geo, act) + _detailing_checks(inp, geo, act, res_sag, res_hog)
    ld = act["loads"]
    return {
        "element": "beam",
        "project": inp.project,
        "summary": summarise(checks),
        "groups": list(GROUPS),
        "checks": [c.to_dict() for c in checks],
        "inputs": _input_echo(inp, geo),
        "assumptions": list(ASSUMPTIONS),
        "derived": {
            "shape": inp.shape, "flange": inp.flange, "mode": inp.mode, "length": inp.length, "beff": geo.beff,
            "l0": geo.l0, "spans": [{"i": s.i, "x1": s.x1, "x2": s.x2, "kind": s.kind} for s in geo.spans],
            "bottom": {"n": geo.bottom.n, "dia": geo.bottom.dia, "As": geo.bottom.As, "d": geo.bottom.d},
            "top": {"n": geo.top.n, "dia": geo.top.dia, "As": geo.top.As, "d": geo.top.d},
            "sag": _summary(res_sag), "hog": _summary(res_hog),
            "MEd_sag": act["M_sag"] / 1e6, "MEd_hog": act["M_hog"] / 1e6, "VEd": act["VEd"] / 1e3,
            "x_sag": act["x_sag"], "x_hog": act["x_hog"], "x_v": act["x_v"], "links": links,
            "w": ld["w_m"] if ld else None, "w_shear": ld["w_v"] if ld else None,
        },
        "plots": _plots(inp, geo, act),
    }


def analyse_input(data):
    """Loading and analysis only, without the design checks (for the live preview)."""
    d = _upgrade(data)
    d["reinforcement"] = {
        "bottom_n": 2, "bottom_dia": 10, "top_n": 2, "top_dia": 10, "link_dia": 8, "legs": 2,
        "cover": 25, "delta_c_dev": 10, "bottom_layers": 1, "top_layers": 1
    }
    d["durability"] = {"exposure": "XC1", "cement_group": "All", "fire_period": "none"}
    mat = d.setdefault("materials", {})
    conc = mat.get("concrete", "C30/37") if isinstance(mat, dict) else "C30/37"
    d["materials"] = {"concrete": conc, "fyk": 500, "ductility": "B", "dg": 20}
    inp = parse_input(d)
    geo = geometry(inp)
    act = design_actions(inp, geo)
    plots = _plots(inp, geo, act)
    ld = act["loads"]
    plots["loads"] = None if not ld else {
        "w": ld["w_m"], "w_shear": ld["w_v"], "sw": ld["sw"], "g": ld["g"], "q": ld["q"],
        "slab": None if not ld["slab"] else {k: ld["slab"][k] for k in ("fm", "fv", "w_area")}}
    return plots
