"""A 3D view of the element for the PDF (Structural Analysis & Design): the same models as the web viewport,
drawn as a shaded projection with see-through concrete, so the reinforcement cage shows. Parts whose check
failed are drawn red. Faces and bars are painted from the back to the front."""
import math

from reportlab.graphics.shapes import Drawing, Line, Polygon, String
from reportlab.lib import colors

CONC = (0.62, 0.66, 0.70)
CONTEXT = (0.50, 0.55, 0.60)
BARS = (0.85, 0.33, 0.10)
LINKS = (0.93, 0.69, 0.13)
SUPPORT = (0.47, 0.67, 0.19)
LOAD = (0.80, 0.16, 0.30)
PRESSURE = (0.30, 0.65, 0.85)
SOIL = (0.61, 0.48, 0.31)
FAIL = (0.80, 0.12, 0.10)
EDGE = (0.20, 0.27, 0.33)


def _n(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _along(lo, hi, step, cap=300):
    if step <= 0 or hi <= lo:
        return []
    count = min(cap, int((hi - lo) / step) + 1)
    start = lo + (hi - lo - (count - 1) * step) / 2
    return [start + i * step for i in range(count)]


def _spread(lo, hi, n):
    return [(lo + hi) / 2] if n <= 1 else [lo + (hi - lo) * i / (n - 1) for i in range(n)]


class Scene:
    def __init__(self):
        self.faces = []    # (points, rgb, alpha, edge)
        self.lines = []    # (p0, p1, rgb, width_m)

    def box(self, x0, y0, z0, x1, y1, z1, rgb, alpha=1.0, edge=True):
        p = lambda x, y, z: (x, y, z)
        a, b, c, d = p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1), p(x0, y1, z1)
        e, f, g, h = p(x0, y0, z0), p(x1, y0, z0), p(x1, y1, z0), p(x0, y1, z0)
        for quad, normal in (([a, b, c, d], (0, 0, 1)), ([f, e, h, g], (0, 0, -1)), ([b, f, g, c], (1, 0, 0)),
                             ([e, a, d, h], (-1, 0, 0)), ([d, c, g, h], (0, 1, 0)), ([e, f, b, a], (0, -1, 0))):
            self.faces.append((quad, normal, rgb, alpha, edge))

    def bar(self, p0, p1, rgb, dia, pieces=6):
        for i in range(pieces):
            t0, t1 = i / pieces, (i + 1) / pieces
            q0 = tuple(p0[k] + (p1[k] - p0[k]) * t0 for k in range(3))
            q1 = tuple(p0[k] + (p1[k] - p0[k]) * t1 for k in range(3))
            self.lines.append((q0, q1, rgb, dia))

    def loop(self, pts, rgb, dia):
        for i, p in enumerate(pts):
            self.lines.append((p, pts[(i + 1) % len(pts)], rgb, dia))

    def arrow(self, tail, tip, rgb, dia):
        self.lines.append((tail, tip, rgb, dia))
        self.lines.append(("head", tail, tip, rgb, dia))

    # ------------------------------------------------------------ drawing

    def draw(self, width, height, yaw=-0.72, pitch=0.42, background=None):
        cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
        eye = (cp * sy, sp, cp * cy)                   # towards the viewer
        fwd = tuple(-v for v in eye)
        right = (fwd[1] * 0 - fwd[2] * 1, fwd[2] * 0 - fwd[0] * 0, fwd[0] * 1 - fwd[1] * 0)
        rl = math.hypot(*right) or 1
        right = tuple(v / rl for v in right)
        up = (right[1] * fwd[2] - right[2] * fwd[1], right[2] * fwd[0] - right[0] * fwd[2], right[0] * fwd[1] - right[1] * fwd[0])
        dot = lambda a, b: a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
        pts = [p for f in self.faces for p in f[0]] + [p for l in self.lines if l[0] != "head" for p in l[:2]]
        if not pts:
            return Drawing(width, height)
        xs = [dot(p, right) for p in pts]
        ys = [dot(p, up) for p in pts]
        pad = 6
        k = min((width - 2 * pad) / max(max(xs) - min(xs), 1e-6), (height - 2 * pad) / max(max(ys) - min(ys), 1e-6))
        ox = pad + (width - 2 * pad - (max(xs) - min(xs)) * k) / 2 - min(xs) * k
        oy = pad + (height - 2 * pad - (max(ys) - min(ys)) * k) / 2 - min(ys) * k
        P = lambda p: (ox + dot(p, right) * k, oy + dot(p, up) * k)
        depth = lambda p: dot(p, fwd)
        light = (0.45, 0.85, 0.35)
        ll = math.hypot(*light)
        light = tuple(v / ll for v in light)

        items = []
        for quad, normal, rgb, alpha, edge in self.faces:
            c = tuple(sum(p[i] for p in quad) / 4 for i in range(3))
            shade = 0.55 + 0.45 * max(dot(normal, light), 0) + (0.08 if dot(normal, eye) > 0 else -0.1)
            items.append((depth(c), "face", quad, tuple(min(1, v * shade) for v in rgb), alpha, edge, dot(normal, eye) > 0))
        for l in self.lines:
            if l[0] == "head":
                _, tail, tip, rgb, dia = l
                items.append((depth(tip) - 1e-3, "head", tail, tip, rgb, dia))
            else:
                p0, p1, rgb, dia = l
                items.append((depth(tuple((p0[i] + p1[i]) / 2 for i in range(3))), "line", p0, p1, rgb, dia))
        items.sort(key=lambda it: -it[0])

        d = Drawing(width, height)
        if background:
            d.add(Polygon([0, 0, width, 0, width, height, 0, height], fillColor=background, strokeColor=None))
        for it in items:
            if it[1] == "face":
                _, _, quad, rgb, alpha, edge, front = it
                flat = [v for p in quad for v in P(p)]
                fill = colors.Color(*rgb, alpha=alpha)
                stroke = colors.Color(*EDGE, alpha=0.85 if front else 0.35) if edge else None
                d.add(Polygon(flat, fillColor=fill, strokeColor=stroke, strokeWidth=0.45 if front else 0.3))
            elif it[1] == "line":
                _, _, p0, p1, rgb, dia = it
                a, b = P(p0), P(p1)
                d.add(Line(a[0], a[1], b[0], b[1], strokeColor=colors.Color(*rgb), strokeWidth=max(dia * k, 0.45), strokeLineCap=1))
            else:
                _, _, tail, tip, rgb, dia = it
                a, b = P(tail), P(tip)
                ang = math.atan2(b[1] - a[1], b[0] - a[0])
                s = max(dia * k * 3.2, 3.2)
                left = (b[0] - s * math.cos(ang - 0.4), b[1] - s * math.sin(ang - 0.4))
                rgt = (b[0] - s * math.cos(ang + 0.4), b[1] - s * math.sin(ang + 0.4))
                d.add(Polygon([b[0], b[1], *left, *rgt], fillColor=colors.Color(*rgb), strokeColor=None))
        return d


# ------------------------------------------------------------------ the elements

def _status(report):
    order = {"fail": 4, "warn": 3, "pass": 2, "info": 1, "na": 0}
    worst = {}
    for c in report["checks"]:
        t = c.get("target")
        if t and order[c["status"]] > order.get(worst.get(t, "na"), 0):
            worst[t] = c["status"]
    return lambda *targets: any(worst.get(t) == "fail" for t in targets)


def _column(report, s, failed):
    sec = report["plots"]["section"]
    der = report["derived"]
    B, H, L = sec["b"] / 1000, sec["h"] / 1000, max(_n(der.get("l"), 3000) / 1000, 0.5)
    t, hx = 0.2, max(B, H) * 1.1 + 0.2
    s.box(-hx, -t, -hx, hx, 0, hx, CONTEXT, 0.22)
    s.box(-hx, L, -hx, hx, L + t, hx, CONTEXT, 0.18)
    s.box(-B / 2, 0, -H / 2, B / 2, L, H / 2, FAIL if failed("section", "cover", "elevation") else CONC, 0.2)
    bar_rgb = FAIL if failed("bars") else BARS
    for bar in sec["bars"]:
        x, z = bar["x"] / 1000, bar["y"] / 1000
        s.bar((x, -t * 0.8, z), (x, L + t + 0.3, z), bar_rgb, bar["dia"] / 1000, pieces=10)
    links = der.get("links") or {}
    near, far = _n(links.get("near"), 200) / 1000, _n(links.get("far"), 300) / 1000
    c = (sec["cover"] + sec["link_dia"] / 2) / 1000
    y, zone = 0.05, max(B, H)
    rgb = FAIL if failed("links") else LINKS
    while y <= L - 0.04:
        s.loop([(-B / 2 + c, y, -H / 2 + c), (B / 2 - c, y, -H / 2 + c), (B / 2 - c, y, H / 2 - c), (-B / 2 + c, y, H / 2 - c)],
               rgb, sec["link_dia"] / 1000)
        y += near if (y < zone or y > L - zone) else far
    if _n(der.get("NEd")) > 0:
        s.arrow((0, L + t + 1.1, 0), (0, L + t + 0.35, 0), LOAD, 0.03)
    return -0.72, 0.36


def _beam(report, s, failed):
    sec = report["plots"]["section"]
    inp = report.get("input") or {}
    span = inp.get("span") or {}
    L = max(_n(span.get("l"), 6), 0.5)
    b, h = sec["b"] / 1000, sec["h"] / 1000
    flanged = sec.get("shape") == "flanged"
    hf = _n(sec.get("hf")) / 1000
    conc = FAIL if failed("section", "cover") else CONC
    s.box(0, 0, -b / 2, L, h - hf if flanged else h, b / 2, conc, 0.2)
    if flanged:
        bf = _n(sec.get("beff"), sec["b"]) / 1000
        z0, z1 = (-bf / 2, bf / 2) if sec.get("flange") == "T" else (-b / 2, bf - b / 2)
        s.box(0, h - hf, z0, L, h, z1, conc, 0.2)
    rgb = FAIL if failed("bars") else BARS
    for bar in sec["bars"]:
        s.bar((0.03, bar["y"] / 1000, bar["x"] / 1000), (L - 0.03, bar["y"] / 1000, bar["x"] / 1000), rgb, bar["dia"] / 1000, pieces=16)
    links = report["derived"].get("links") or {}
    step = _n(links.get("near"), 200) / 1000
    c = (sec["cover"] + sec["link_dia"] / 2) / 1000
    lrgb = FAIL if failed("links") else LINKS
    for x in _along(0.05, L - 0.05, step, 160):
        s.loop([(x, c, -b / 2 + c), (x, c, b / 2 - c), (x, h - c, b / 2 - c), (x, h - c, -b / 2 + c)], lrgb, sec["link_dia"] / 1000)
    k = max(h, 0.35) / 0.6
    for sp in span.get("supports") or []:
        x = _n(sp.get("x"))
        s.box(x - 0.15 * k, -0.3 * k, -b / 2 - 0.08, x + 0.15 * k, 0, b / 2 + 0.08, SUPPORT, 1.0)
    return -1.0, 0.3


def _slab(report, s, failed):
    inp = report.get("input") or {}
    sl, r, sp = inp.get("slab") or {}, inp.get("reinforcement") or {}, inp.get("span") or {}
    cover = _n(r.get("cover"), 25) / 1000
    if sl.get("type") == "two_way":
        p = inp.get("panel") or {}
        lx, ly, h = _n(p.get("lx"), 4), _n(p.get("ly"), 5), _n(sl.get("h"), 200) / 1000
        X, Z = ly / 2, lx / 2
        s.box(-X, 0, -Z, X, h, Z, FAIL if failed("h", "slab.h", "cover", "section") else CONC, 0.2)
        for (x0, z0, x1, z1) in ((-X - .15, -Z - .15, X + .15, -Z + .15), (-X - .15, Z - .15, X + .15, Z + .15),
                                 (-X - .15, -Z, -X + .15, Z), (X - .15, -Z, X + .15, Z)):
            s.box(x0, -0.45, z0, x1, 0, z1, CONTEXT, 0.5)
        bx, by = _n(r.get("bottom_x_dia"), 10) / 1000, _n(r.get("bottom_y_dia"), 10) / 1000
        rgb = FAIL if failed("reinforcement.bottom_x_dia", "reinforcement.bottom_x_s") else BARS
        for x in _along(-X + 0.05, X - 0.05, _n(r.get("bottom_x_s"), 200) / 1000):
            s.bar((x, cover + bx / 2, -Z + 0.03), (x, cover + bx / 2, Z - 0.03), rgb, bx, pieces=4)
        for z in _along(-Z + 0.05, Z - 0.05, _n(r.get("bottom_y_s"), 200) / 1000):
            s.bar((-X + 0.03, cover + bx + by / 2, z), (X - 0.03, cover + bx + by / 2, z), BARS, by, pieces=4)
        return -0.6, 0.55
    L = max(_n(sp.get("l"), 5), 0.5)
    if sl.get("type") == "ribbed":
        pan = (report["plots"].get("section") or {})
        ph = _n(pan.get("ph"), 150) / 1000
        bw, hf = _n(sl.get("bw"), 125) / 1000, _n(sl.get("hf"), 75) / 1000
        pitch = _n(pan.get("spacing"), 425) / 1000
        W = 3 * pitch + bw
        conc = FAIL if failed("section", "cover", "h") else CONC
        for i in range(4):
            z = -W / 2 + bw / 2 + i * pitch
            s.box(0, 0, z - bw / 2, L, ph, z + bw / 2, conc, 0.25)
            db = _n(r.get("bottom_dia"), 12) / 1000
            for zz in _spread(z - bw / 2 + cover + db, z + bw / 2 - cover - db, max(1, int(_n(r.get("bottom_n"), 2)))):
                s.bar((0.03, cover + db, zz), (L - 0.03, cover + db, zz), BARS, db, pieces=10)
        s.box(0, ph, -W / 2, L, ph + hf, W / 2, conc, 0.2)
        for supp in sp.get("supports") or []:
            x = _n(supp.get("x"))
            s.box(x - 0.1, -1.2, -W / 2 - 0.1, x + 0.1, 0, W / 2 + 0.1, CONTEXT, 0.45)
        return -1.0, -0.12
    h = _n(sl.get("h"), 200) / 1000
    W = min(4, max(2.4, L * 0.32))
    s.box(0, 0, -W / 2, L, h, W / 2, FAIL if failed("h", "slab.h", "cover", "section") else CONC, 0.2)
    for supp in sp.get("supports") or []:
        x = _n(supp.get("x"))
        s.box(x - 0.1, -1.4, -W / 2, x + 0.1, 0, W / 2, CONTEXT, 0.45)
    bx = _n(r.get("bottom_x_dia"), 10) / 1000
    rgb = FAIL if failed("reinforcement.bottom_x_dia", "reinforcement.bottom_x_s") else BARS
    for z in _along(-W / 2 + 0.05, W / 2 - 0.05, _n(r.get("bottom_x_s"), 200) / 1000):
        s.bar((0.03, cover + bx / 2, z), (L - 0.03, cover + bx / 2, z), rgb, bx, pieces=10)
    if r.get("bottom_y_dia") not in (None, "none"):
        by = _n(r.get("bottom_y_dia"), 8) / 1000
        for x in _along(0.05, L - 0.05, _n(r.get("bottom_y_s"), 250) / 1000):
            s.bar((x, cover + bx + by / 2, -W / 2 + 0.03), (x, cover + bx + by / 2, W / 2 - 0.03), BARS, by, pieces=3)
    return -0.9, 0.4


def _foundation(report, s, failed):
    inp = report.get("input") or {}
    col, base, r = inp.get("column") or {}, inp.get("base") or {}, inp.get("reinforcement") or {}
    der = report["derived"]
    L, B, h = max(_n(base.get("L"), 2), .3), max(_n(base.get("B"), 2), .3), max(_n(base.get("h"), 500), 100) / 1000
    cx, cy, ds = _n(col.get("cx"), 400) / 1000, _n(col.get("cy"), 400) / 1000, max(_n(base.get("soil_depth"), .5), 0)
    top = ds + 0.9
    s.box(-L / 2, -h, -B / 2, L / 2, 0, B / 2, FAIL if failed("section", "cover", "base") else CONC, 0.2)
    s.box(-cx / 2, 0, -cy / 2, cx / 2, top, cy / 2, FAIL if failed("column") else CONC, 0.28)
    cover = _n(r.get("cover"), 50) / 1000
    dx, dy = _n(r.get("x_dia"), 16) / 1000, _n(r.get("y_dia"), 16) / 1000
    rgb = FAIL if failed("bars") else BARS
    for z in _along(-B / 2 + cover, B / 2 - cover, _n(r.get("x_s"), 200) / 1000):
        s.bar((-L / 2 + cover, -h + cover + dx / 2, z), (L / 2 - cover, -h + cover + dx / 2, z), rgb, dx, pieces=6)
    for x in _along(-L / 2 + cover, L / 2 - cover, _n(r.get("y_s"), 200) / 1000):
        s.bar((x, -h + cover + dx + dy / 2, -B / 2 + cover), (x, -h + cover + dx + dy / 2, B / 2 - cover), rgb, dy, pieces=6)
    if _n(der.get("NEd")) > 0:
        s.arrow((0, top + 1.0, 0), (0, top + 0.03, 0), LOAD, 0.035)
    p1, p2 = _n(der.get("uls_p1")), _n(der.get("uls_p2"))
    if p1 > 0:
        k = 0.8 / max(p1, p2, 1)
        for x in _along(-L / 2 + 0.15, L / 2 - 0.15, L / 6):
            depth = (min(p1, p2) + (x + L / 2) / L * abs(p1 - p2)) * k
            for z in (-B / 4, B / 4):
                s.arrow((x, -h - 0.05 - depth, z), (x, -h - 0.02, z), PRESSURE, 0.012)
    return -0.78, 0.36


BUILDERS = {"column": _column, "beam": _beam, "slab": _slab, "foundation": _foundation}


def iso_view(report, width, height):
    """The element in 3D as a reportlab Drawing, or None when its geometry is not in the report."""
    build = BUILDERS.get(report.get("element"))
    if not build:
        return None
    try:
        s = Scene()
        yaw, pitch = build(report, s, _status(report))
        return s.draw(width, height, yaw=yaw, pitch=pitch)
    except (KeyError, TypeError, ValueError):
        return None
