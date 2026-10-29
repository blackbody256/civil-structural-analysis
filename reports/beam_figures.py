"""Figures of the beam analysis, drawn once as simple shapes for both the web report and the PDF.

Each figure is {"w": 1000, "h": height, "items": [...]} in drawing units, y downwards. An item is
a line, a polyline or polygon ("poly"), a circle or a text, with a colour name (ink, muted,
accent, load, rule, concrete, paper, sfd, bmd, defl, react) that each renderer maps to its own
palette: static/js/figure-spec.js for the page and reports/beam_pdf.py for the PDF.

Figures follow the textbook presentation of the matrix stiffness method: the beam with its
loads and dimensions, the analytical model with numbered nodes, elements and degrees of
freedom, the support reactions, and the shear force and bending moment diagrams. Positive
shear and hogging moments are drawn above the x-axis; negative shear and sagging moments below it.
"""
import math

W = 1000
X0, X1 = 90, 920


def _fmt(v, nd=2):
    return f"{v:.{nd}f}".replace("-", "−")


def _len(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


class Fig:
    def __init__(self, h):
        self.h = h
        self.items = []

    def line(self, x1, y1, x2, y2, c="ink", sw=1.4, dash=None):
        self.items.append({"k": "line", "p": [x1, y1, x2, y2], "c": c, "sw": sw, **({"dash": dash} if dash else {})})

    def poly(self, pts, c="ink", f=None, fo=1.0, sw=1.4, closed=False):
        flat = [round(v, 2) for p in pts for v in p]
        self.items.append({"k": "poly", "p": flat, "c": c, "f": f, "fo": fo, "sw": sw, "closed": closed})

    def circle(self, x, y, r, c="ink", f=None, sw=1.2):
        self.items.append({"k": "circle", "x": x, "y": y, "r": r, "c": c, "f": f, "sw": sw})

    def text(self, x, y, t, c="ink", size=17, a="m", b=False):
        self.items.append({"k": "text", "x": round(x, 2), "y": round(y, 2), "t": t, "c": c, "size": size, "a": a, "b": b})

    def arrow(self, x1, y1, x2, y2, c="ink", sw=1.5, head=9):
        """Arrow from (x1, y1) to the tip (x2, y2)."""
        self.line(x1, y1, x2, y2, c, sw)
        ang = math.atan2(y2 - y1, x2 - x1)
        left = (x2 - head * math.cos(ang - 0.4), y2 - head * math.sin(ang - 0.4))
        right = (x2 - head * math.cos(ang + 0.4), y2 - head * math.sin(ang + 0.4))
        self.poly([(x2, y2), left, right], c=c, f=c, closed=True, sw=0.8)

    def arc_arrow(self, cx, cy, r, a0, a1, c="ink", sw=1.5, head=9):
        """Arc from angle a0 to a1 (degrees, anticlockwise on screen = increasing), arrowhead at a1."""
        n = 24
        pts = [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                cy - r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        self.poly(pts, c=c, sw=sw)
        (xa, ya), (xb, yb) = pts[-2], pts[-1]
        ang = math.atan2(yb - ya, xb - xa)
        self.poly([(xb, yb), (xb - head * math.cos(ang - 0.45), yb - head * math.sin(ang - 0.45)),
                   (xb - head * math.cos(ang + 0.45), yb - head * math.sin(ang + 0.45))], c=c, f=c, closed=True, sw=0.8)
        return pts

    def spec(self):
        return {"w": W, "h": self.h, "items": self.items}


def _scale(length, x0=X0, x1=X1):
    return lambda x: x0 + x / length * (x1 - x0)


def _hatch(fig, x1, x2, y, c="muted", below=True):
    fig.line(x1, y, x2, y, c, 1.3)
    step = 7
    x = x1 + 2
    while x < x2:
        fig.line(x, y, x - 6, y + 7 if below else y - 7, c, 0.9)
        x += step


def _supports(fig, supports, X, y_bottom, length, c="ink", beam_half=8):
    for sp in supports:
        sx = X(sp["x"])
        if sp["type"] == "fixed":
            at_left = sp["x"] < 1e-6
            at_right = sp["x"] > length - 1e-6
            top, bot = y_bottom - 2 * beam_half - 26, y_bottom + 26
            fig.line(sx, top, sx, bot, c, 2.6)
            for side in ([-1] if at_left else [1] if at_right else [-1, 1]):
                y = top + 3
                while y < bot:
                    fig.line(sx, y, sx + side * 8, y + 7, c, 0.9)
                    y += 7
        elif sp["type"] == "pin":
            fig.poly([(sx, y_bottom), (sx - 12, y_bottom + 20), (sx + 12, y_bottom + 20)], c=c, f="paper",
                     closed=True, sw=1.4)
            _hatch(fig, sx - 17, sx + 17, y_bottom + 20, c)
        else:
            fig.circle(sx, y_bottom + 9, 9, c=c, f="paper", sw=1.4)
            _hatch(fig, sx - 17, sx + 17, y_bottom + 18, c)


def _intensity(ld, x):
    if ld["type"] == "udl":
        return ld["w"]
    t = (x - ld["x1"]) / (ld["x2"] - ld["x1"])
    return ld["w1"] + (ld["w2"] - ld["w1"]) * t


def _loads(fig, loads, X, y_top, colour="load", text="ink"):
    """Loads above a beam whose top face is at y_top."""
    dist = [ld for ld in loads if ld["type"] in ("udl", "linear")]
    wmax = max([abs(_intensity(ld, x)) for ld in dist for x in (ld["x1"], ld["x2"])] or [1.0]) or 1.0
    for ld in dist:
        x1, x2 = ld["x1"], ld["x2"]
        n = max(2, round((X(x2) - X(x1)) / 34))
        pts = []
        for i in range(n + 1):
            x = x1 + (x2 - x1) * i / n
            w = _intensity(ld, x)
            hgt = 16 + 54 * abs(w) / wmax
            sx = X(x)
            pts.append((sx, y_top - hgt))
            if abs(w) > 1e-9:
                fig.arrow(sx, y_top - hgt, sx, y_top - 1, colour, 1.1, 7)
        fig.poly(pts, c=colour, sw=1.4)
        if ld.get("line"):
            fig.text((X(x1) + X(x2)) / 2, y_top - 78, f"w = {_fmt(ld['w'])} kN/m", text, 16, "m", True)
        elif ld["type"] == "udl":
            fig.text((X(x1) + X(x2)) / 2, y_top - 26 - 54 * abs(ld["w"]) / wmax, f"{ld['w']:g} kN/m", text, 15)
        else:
            end = x1 if abs(ld["w1"]) >= abs(ld["w2"]) else x2
            peak = max(abs(ld["w1"]), abs(ld["w2"]))
            fig.text(X(end) + (8 if end == x1 else -8), y_top - 24 - 54 * peak / wmax, f"{peak:g} kN/m", text, 15,
                     "s" if end == x1 else "e")
    for ld in loads:
        if ld["type"] == "point":
            sx = X(ld["x"])
            if ld["W"] >= 0:
                fig.arrow(sx, y_top - 86, sx, y_top - 1, colour, 2.0, 11)
                fig.text(sx, y_top - 93, f"{ld['W']:g} kN", text, 16, "m", True)
            else:
                fig.arrow(sx, y_top - 1, sx, y_top - 86, colour, 2.0, 11)
                fig.text(sx, y_top - 93, f"{-ld['W']:g} kN (up)", text, 16, "m", True)
        elif ld["type"] == "moment":
            sx = X(ld["x"])
            clockwise = ld["M"] >= 0
            fig.arc_arrow(sx, y_top - 8, 24, 200 if clockwise else -20, -20 if clockwise else 200, colour, 1.8)
            fig.text(sx, y_top - 42, f"{abs(ld['M']):g} kN·m", text, 16, "m", True)


def _beam(fig, data, X, y, thick):
    segs = data["segments"]
    imin = min(s["I"] for s in segs)
    imax = max(s["I"] for s in segs)
    for s in segs:
        t = thick if imax - imin < 1e-9 else thick + 8 * (s["I"] - imin) / (imax - imin)
        fig.poly([(X(s["x1"]), y - t / 2), (X(s["x2"]), y - t / 2), (X(s["x2"]), y + t / 2), (X(s["x1"]), y + t / 2)],
                 c="ink", f="concrete", closed=True, sw=1.3)
    return thick + (8 if imax - imin > 1e-9 else 0)


def _key_xs(data):
    xs = {0.0, data["length"], *(s["x"] for s in data["supports"]), *(n["x"] for n in data["nodes"])}
    for ld in data["loads"]:
        if ld.get("line"):
            continue
        for k in ("x", "x1", "x2"):
            if k in ld:
                xs.add(ld[k])
    return sorted(round(x, 6) for x in xs)


def _chain(fig, xs, X, y, labels=None):
    fig.line(X(xs[0]), y, X(xs[-1]), y, "ink", 1.0)
    for x in xs:
        fig.line(X(x) - 5, y + 5, X(x) + 5, y - 5, "ink", 1.3)
        fig.line(X(x), y - 9, X(x), y + 9, "muted", 0.7)
    for i, (a, b) in enumerate(zip(xs, xs[1:])):
        if X(b) - X(a) > 34:
            fig.text((X(a) + X(b)) / 2, y - 7, labels[i] if labels else f"{_len(b - a)} m", "ink", 16)


def loading_figure(data):
    """The beam, its supports and loads, with the dimensions and the stiffness of each part."""
    fig = Fig(360)
    X = _scale(data["length"])
    y = 150
    thick = _beam(fig, data, X, y, 12)
    _supports(fig, data["supports"], X, y + thick / 2, data["length"], beam_half=thick / 2)
    _loads(fig, data["loads"], X, y - thick / 2)
    xs = _key_xs(data)
    _chain(fig, xs, X, 232)
    segs = data["segments"]
    imin = min(s["I"] for s in segs)
    if len({round(s["I"], 6) for s in segs}) > 1:
        bounds = sorted({0.0, data["length"], *(s["x1"] for s in segs), *(s["x2"] for s in segs)})
        labels = []
        for a, b in zip(bounds, bounds[1:]):
            mid = (a + b) / 2
            seg = next(s for s in segs if s["x1"] - 1e-9 <= mid <= s["x2"] + 1e-9)
            ratio = seg["I"] / imin
            labels.append("I" if abs(ratio - 1) < 1e-6 else f"{ratio:g} I")
        _chain(fig, bounds, X, 276, labels)
        fig.text(X0, 330, f"E = {data['E']:g} GPa, I = {imin:g} × 10⁶ mm⁴", "muted", 16, "s")
    else:
        fig.text(X0, 300, f"E = {data['E']:g} GPa, I = {imin:g} × 10⁶ mm⁴ (EI constant)", "muted", 16, "s")
        fig.h = 320
    return fig.spec()


def model_figure(data):
    """Analytical model: nodes (circled), elements (boxed) and degrees of freedom, free ones first."""
    fig = Fig(300)
    X = _scale(data["length"])
    y = 130
    fig.line(X0, y, X1, y, "ink", 2.0)
    _supports(fig, data["supports"], X, y + 1, data["length"], c="muted", beam_half=1)
    for el in data["elements"]:
        a, b = X(el["x1"]), X(el["x2"])
        mid = (a + b) / 2
        tip = a + 0.62 * (b - a)
        fig.poly([(tip, y), (tip - 12, y - 6), (tip - 12, y + 6)], c="ink", f="ink", closed=True, sw=0.6)
        fig.poly([(mid - 17, y - 50), (mid + 17, y - 50), (mid + 17, y - 26), (mid - 17, y - 26)], c="ink",
                 f="paper", closed=True, sw=1.2)
        fig.text(mid, y - 32, str(el["e"]), "ink", 16)
    for nd in data["nodes"]:
        sx = X(nd["x"])
        offset = 36 if nd["x"] < data["length"] - 1e-6 else -36
        fig.circle(sx + offset, y + 18, 12, c="ink", f="paper", sw=1.2)
        fig.text(sx + offset, y + 24, str(nd["n"]), "ink", 15)
        v, r = nd["dofs"]
        if nd["fix"][0]:
            fig.arrow(sx, y + 104, sx, y + 62, "react", 1.6)
            fig.line(sx - 7, y + 90, sx + 7, y + 80, "react", 1.6)
            fig.text(sx, y + 126, str(v), "react", 16, "m", True)
        else:
            fig.arrow(sx, y - 4, sx, y - 62, "accent", 1.6)
            fig.text(sx + 10, y - 62, str(v), "accent", 16, "s", True)
        if nd["fix"][1]:
            side = -1 if nd["x"] < 1e-6 else 1
            cx = sx + side * 22
            pts = fig.arc_arrow(cx, y, 22, 120 if side < 0 else 60, 240 if side < 0 else -60, "react", 1.5)
            mid = pts[len(pts) // 2]
            fig.line(mid[0] - 7, mid[1] - 5, mid[0] + 7, mid[1] + 5, "react", 1.5)
            fig.text(cx + side * 34, y + 6, str(r), "react", 16, "m", True)
        else:
            fig.arc_arrow(sx, y, 24, -35, 215, "accent", 1.4, 8)
            fig.text(sx - 30, y - 22, str(r), "accent", 16, "e", True)
    fig.text(X0, 288, f"{len(data['nodes'])} nodes, {len(data['elements'])} element"
             f"{'s' if len(data['elements']) > 1 else ''}; degrees of freedom 1–{data['free_dofs']} free, "
             f"{data['free_dofs'] + 1}–{2 * len(data['nodes'])} restrained", "muted", 15, "s")
    return fig.spec()


def reactions_figure(data):
    """Loads and the support reactions found by the analysis."""
    fig = Fig(330)
    fixed = {r["x"] for r in data["reactions"] if r["M"] is not None and abs(r["M"]) > 1e-6}
    # room beside a fixed end for its moment and label
    X = _scale(data["length"], 190 if 0.0 in fixed else X0, 800 if data["length"] in fixed else X1)
    y = 150
    thick = _beam(fig, data, X, y, 10)
    _supports(fig, data["supports"], X, y + thick / 2, data["length"], beam_half=thick / 2)
    _loads(fig, data["loads"], X, y - thick / 2, colour="muted", text="muted")
    for r in data["reactions"]:
        sx = X(r["x"])
        base = y + thick / 2 + 34
        if r["Ry"] >= 0:
            fig.arrow(sx, base + 70, sx, base + 4, "react", 2.2, 11)
        else:
            fig.arrow(sx, base + 4, sx, base + 70, "react", 2.2, 11)
        fig.line(sx - 7, base + 48, sx + 7, base + 38, "react", 1.6)
        fig.text(sx, base + 96, f"{abs(r['Ry']):.2f} kN", "react", 17, "m", True)
        if r["M"] is not None and abs(r["M"]) > 1e-6:
            side = -1 if r["x"] < 1e-6 else 1
            cx = sx + side * 34
            if (r["M"] > 0) == (side < 0):
                fig.arc_arrow(cx, y, 30, 70 if side < 0 else 110, 290 if side < 0 else -110, "react", 1.8)
            else:
                fig.arc_arrow(cx, y, 30, 290 if side < 0 else -110, 70 if side < 0 else 110, "react", 1.8)
            fig.text(cx + side * 38, y + 6, f"{abs(r['M']):.2f} kN·m", "react", 17, "e" if side < 0 else "s", True)
    return fig.spec()


def _diagram(fig, xs, values, X, base, depth, colour, events, unit_title, top, zeros=None, design=(),
             positive_down=True):
    vmax = max((abs(v) for v in values), default=0.0) or 1.0
    if positive_down:
        Y = lambda v: base + v / vmax * depth
    else:
        Y = lambda v: base - v / vmax * depth
    pts = [(X(xs[0]), base)] + [(X(x), Y(v)) for x, v in zip(xs, values)] + [(X(xs[-1]), base)]
    fig.poly(pts, c=colour, f=colour, fo=0.16, sw=0.1, closed=True)
    fig.poly(pts[1:-1], c=colour, sw=2.0)
    fig.line(X0, base, X1, base, "ink", 1.0)
    fig.text(X0 - 8, top, unit_title, "ink", 17, "s", True)
    placed = []

    def place(x, v, anchor):
        below = Y(v) >= base
        y = Y(v) + (19 if below else -8)
        tx = X(x) + {"s": 5, "e": -5, "m": 0}[anchor]
        label = _fmt(v)
        width = 9 * len(label)
        x_lo = tx - (width if anchor == "e" else width / 2 if anchor == "m" else 0)
        for _ in range(4):
            if not any(abs(y - py) < 17 and x_lo < px2 and x_lo + width > px1 for px1, px2, py in placed):
                break
            y += 17 if below else -17
        placed.append((x_lo, x_lo + width, y))
        bold = any(abs(abs(v) - d) < 0.006 for d in design if d)
        fig.text(tx, y, label, colour if not bold else "ink", 15, anchor, bold)

    last = None
    for ev in sorted(events, key=lambda e: e["x"]):
        x, left, right = ev["x"], ev["left"], ev["right"]
        jump = abs(left - right) > 1e-3 * vmax
        if x > 1e-9 and jump and abs(left) > 5e-3 * vmax and (last is None or abs(left - last) > 1e-3 * vmax):
            place(x, left, "e")
        if x < xs[-1] - 1e-9 or not jump:
            v = right
            if abs(v) > 5e-3 * vmax and (last is None or abs(v - last) > 1e-3 * vmax or ev.get("peak")):
                place(x, v, "s" if jump else "m")
        last = right
    for z in zeros or []:
        fig.circle(X(z), base, 4.5, c=colour, f=colour, sw=1)


def diagrams_figure(data):
    """Shear force and bending moment diagrams. Positive shear and hogging moments are drawn above the x-axis; negative shear and sagging moments below it."""
    fig = Fig(600)
    X = _scale(data["length"])
    xs = _key_xs(data)
    for x in xs:
        fig.line(X(x), 46, X(x), 560, "rule", 1.0, [5, 5])
    design = data.get("design") or {}
    _diagram(fig, data["x"], data["V"], X, 150, 82, "sfd", data["events"]["V"], "Shear force (kN)", 28,
             design=(design.get("V"),), positive_down=False)
    _diagram(fig, data["x"], data["M"], X, 420, 96, "bmd", data["events"]["M"], "Bending moment (kN·m)", 300,
             zeros=data["events"]["zeros"], design=(design.get("sag"), design.get("hog")), positive_down=True)
    last = -1e9
    for x in xs:
        if X(x) - last > 30:
            fig.text(X(x), 586, "0" if x < 1e-9 else f"{_len(x)} m", "muted", 15)
            last = X(x)
    return fig.spec()


def deflection_figure(data):
    """Elastic deflected shape under the design loads, exaggerated; downward below the axis."""
    fig = Fig(205)
    X = _scale(data["length"])
    base, depth = 56, 70
    dmax = max((abs(v) for v in data["delta"]), default=0.0) or 1.0
    fig.line(X0, base, X1, base, "muted", 1.0, [6, 5])
    for sp in data["supports"]:
        sx = X(sp["x"])
        fig.poly([(sx, base), (sx - 8, base + 13), (sx + 8, base + 13)], c="muted", f="paper", closed=True, sw=1.1)
    fig.poly([(X(x), base + d / dmax * depth) for x, d in zip(data["x"], data["delta"])], c="defl", sw=2.4)
    e = data["envelope"]["deflection"]
    fig.circle(X(e["x"]), base + e["d"] / dmax * depth, 4.5, c="defl", f="defl")
    right = X(e["x"]) < (X0 + X1) / 2
    fig.text(X(e["x"]) + (12 if right else -12), base + e["d"] / dmax * depth + (-12 if e["d"] >= 0 else 22),
             f"δmax = {abs(e['d']):.2f} mm at {_len(e['x'])} m", "defl", 16, "s" if right else "e", True)
    fig.text(X0, 196, "Elastic deflection under the design loads (gross section, short-term E), drawn exaggerated",
             "muted", 14, "s")
    return fig.spec()


def beam_figures(report):
    """All figures for a beam report, or {} when the design actions were entered directly."""
    data = report["plots"].get("analysis")
    if not data:
        return {}
    return {"loading": loading_figure(data), "model": model_figure(data), "reactions": reactions_figure(data),
            "diagrams": diagrams_figure(data), "deflection": deflection_figure(data)}
