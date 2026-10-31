"""Figures for the column page's 2D frame analysis: the frame with its loads, and the N, V and M diagrams.

Same figure format as reports/beam_figures.py (a 1000-unit-wide spec): the page draws it with
static/js/figure-spec.js renderFigure and the PDF with reports/beam_pdf.py render_figure.

Every figure places the frame identically, so the model and the diagrams line up. Diagrams are drawn
perpendicular to each member: bending moments on the tension side (sagging below a beam, hogging above),
N and V with positive values on the left of node 1 → node 2 (above a left-to-right beam).
Colours: "ink" members, "accent" the column being designed, "load" loads, "bmd" M, "sfd" V, "react" N.
"""
import math

from reports.beam_figures import Fig, _fmt

W = 1000
TEXT = 20          # ids and load labels
SMALL = 18         # values on the diagrams and dimensions
TOP = 110          # room above the frame for loads
BOTTOM = 105       # room below for supports and the dimension line
SIDE = 150         # room either side for node loads and the height dimensions
NODE_R = 15


def _layout(nodes):
    """Scale and placement shared by all the figures of one frame: returns X(x), Y(y), the figure height and the
    frame's extent on the figure."""
    xs = [float(n["x"]) for n in nodes]
    ys = [float(n["y"]) for n in nodes]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    dx, dy = max(xmax - xmin, 1e-6), max(ymax - ymin, 1e-6)
    scale = min((W - 2 * SIDE) / dx if xmax > xmin else math.inf, 380.0 / dy if ymax > ymin else math.inf)
    if math.isinf(scale):
        scale = 100.0
    frame_w, frame_h = (xmax - xmin) * scale, (ymax - ymin) * scale
    H = int(TOP + frame_h + BOTTOM)
    x0 = (W - frame_w) / 2.0

    def X(x):
        return x0 + (float(x) - xmin) * scale

    def Y(y):
        return TOP + frame_h - (float(y) - ymin) * scale

    return X, Y, H, (X(xmin), X(xmax), Y(ymax), Y(ymin))


def _members(result):
    """(definition, result, (x1, y1), (x2, y2)) for every member, in figure units."""
    nodes = {str(n["id"]): n for n in result.get("nodes", [])}
    res = {str(m["id"]): m for m in result.get("members", [])}
    out = []
    for m in result.get("elements", []):
        n1, n2 = nodes.get(str(m["node1"])), nodes.get(str(m["node2"]))
        if n1 and n2:
            out.append((m, res.get(str(m["id"])), n1, n2))
    return out


def _value(v):
    return _fmt(v, 1)


def _is_vertical(p1, p2):
    return abs(p2[0] - p1[0]) < 0.05 * math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def _supports(fig, result, X, Y):
    nodes = {str(n["id"]): n for n in result.get("nodes", [])}
    for sup in result.get("supports", []):
        n = nodes.get(str(sup["node"]))
        if not n:
            continue
        sx, sy = X(n["x"]), Y(n["y"]) + NODE_R
        kind = sup.get("type", "pin")
        if kind == "fixed":
            fig.line(sx - 26, sy, sx + 26, sy, c="ink", sw=2.6)
            for hx in range(-24, 25, 8):
                fig.line(sx + hx, sy, sx + hx - 8, sy + 10, c="muted", sw=1.1)
            continue
        fig.poly([(sx, sy - 4), (sx - 15, sy + 20), (sx + 15, sy + 20)], c="ink", f="paper", closed=True, sw=1.4)
        base = sy + 20
        if kind == "roller":
            for cx in (sx - 8, sx + 8):
                fig.circle(cx, base + 5, 4.5, c="ink", f="paper", sw=1.1)
            base += 10
        fig.line(sx - 24, base, sx + 24, base, c="ink", sw=1.6)
        for hx in range(-22, 23, 8):
            fig.line(sx + hx, base, sx + hx - 8, base + 9, c="muted", sw=1.1)


def _dimensions(fig, result, X, Y, extent):
    """Bay widths under the frame and storey heights on its right."""
    left, right, top, bottom = extent
    xs = sorted({round(float(n["x"]), 6) for n in result.get("nodes", [])})
    ys = sorted({round(float(n["y"]), 6) for n in result.get("nodes", [])})
    y_dim = bottom + 70
    for a, b in zip(xs, xs[1:]):
        fig.line(X(a), y_dim, X(b), y_dim, c="muted", sw=1.1)
        fig.text((X(a) + X(b)) / 2, y_dim - 8, f"{b - a:.2f} m", c="muted", size=SMALL)
    for x in xs if len(xs) > 1 else []:
        fig.line(X(x) - 6, y_dim + 6, X(x) + 6, y_dim - 6, c="muted", sw=1.4)
    x_dim = right + 92
    for a, b in zip(ys, ys[1:]):
        fig.line(x_dim, Y(a), x_dim, Y(b), c="muted", sw=1.1)
        fig.text(x_dim + 10, (Y(a) + Y(b)) / 2 + 6, f"{b - a:.2f} m", c="muted", size=SMALL, a="s")
    for y in ys if len(ys) > 1 else []:
        fig.line(x_dim - 6, Y(y) + 6, x_dim + 6, Y(y) - 6, c="muted", sw=1.4)


def _case(ld):
    return f" ({ld['case']})" if ld.get("case", "Ed") != "Ed" else ""


def _loads(fig, result, X, Y):
    nodes = {str(n["id"]): n for n in result.get("nodes", [])}
    members = {str(m["id"]): (n1, n2) for m, _, n1, n2 in _members(result)}
    loads = result.get("loads", [])

    # uniform loads: one row of arrows per member, the cases on one label
    udl = {}
    for ld in loads:
        if ld.get("type") == "udl" and str(ld.get("member")) in members and abs(float(ld.get("w") or 0)) > 1e-9:
            udl.setdefault(str(ld["member"]), []).append(ld)
    for mid, items in udl.items():
        n1, n2 = members[mid]
        x1, y1, x2, y2 = X(n1["x"]), Y(n1["y"]), X(n2["x"]), Y(n2["y"])
        lift = 34
        count = max(3, min(9, int(abs(x2 - x1) / 55) + 1))
        for k in range(count):
            t = (k + 0.5) / count
            bx, by = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
            fig.arrow(bx, by - lift, bx, by - 3, c="load", sw=1.3, head=7)
        fig.line(x1, y1 - lift, x2, y2 - lift, c="load", sw=1.3)
        label = " + ".join(f"{float(ld['w']):g}{_case(ld)}" for ld in items) + " kN/m"
        fig.text((x1 + x2) / 2, min(y1, y2) - lift - 9, label, c="load", size=TEXT)

    for ld in loads:
        kind = ld.get("type")
        if kind == "point" and str(ld.get("member")) in members:
            n1, n2 = members[str(ld["member"])]
            length = math.hypot(float(n2["x"]) - float(n1["x"]), float(n2["y"]) - float(n1["y"]))
            a = float(ld["a"]) if ld.get("a") is not None else length / 2
            t = a / length if length else 0.5
            bx = X(n1["x"]) + t * (X(n2["x"]) - X(n1["x"]))
            by = Y(n1["y"]) + t * (Y(n2["y"]) - Y(n1["y"]))
            fig.arrow(bx, by - 58, bx, by - 3, c="load", sw=2.0, head=10)
            fig.text(bx + 8, by - 62, f"{float(ld['P']):g} kN{_case(ld)}", c="load", size=TEXT, a="s")
        elif kind == "node" and str(ld.get("node")) in nodes:
            n = nodes[str(ld["node"])]
            nx, ny = X(n["x"]), Y(n["y"])
            fx, fy = float(ld.get("fx") or 0), float(ld.get("fy") or 0)
            if abs(fx) > 1e-9:
                s = 1.0 if fx > 0 else -1.0          # arrow pointing the way the force acts
                tail = nx - s * (NODE_R + 62)
                fig.arrow(tail, ny, nx - s * (NODE_R + 2), ny, c="load", sw=2.0, head=10)
                fig.text(tail - s * 6, ny + 7, f"{abs(fx):g} kN{_case(ld)}", c="load", size=TEXT,
                         a="e" if s > 0 else "s")
            if abs(fy) > 1e-9:
                s = 1.0 if fy > 0 else -1.0          # fy is positive downwards
                tail = ny - s * (NODE_R + 62)
                fig.arrow(nx, tail, nx, ny - s * (NODE_R + 2), c="load", sw=2.0, head=10)
                fig.text(nx + 10, tail + (4 if s > 0 else 14), f"{abs(fy):g} kN{_case(ld)}", c="load", size=TEXT, a="s")
            mz = float(ld.get("mz") or 0)
            if abs(mz) > 1e-9:
                a0, a1 = (-20, 200) if mz > 0 else (200, -20)      # anticlockwise positive
                fig.arc_arrow(nx, ny, NODE_R + 16, a0, a1, c="load", sw=1.8, head=9)
                fig.text(nx + NODE_R + 22, ny - NODE_R - 14, f"{abs(mz):g} kNm{_case(ld)}", c="load", size=TEXT, a="s")


def _id_box(fig, x, y, text, accent=False):
    w = len(text) * 11 + 16
    c = "accent" if accent else "muted"
    fig.poly([(x - w / 2, y - 14), (x + w / 2, y - 14), (x + w / 2, y + 14), (x - w / 2, y + 14)],
             c=c, f="paper", closed=True, sw=1.6 if accent else 1.1)
    fig.text(x, y + 7, text, c="accent" if accent else "ink", size=TEXT, b=accent)


def _nodes(fig, result, X, Y):
    for n in result.get("nodes", []):
        nx, ny = X(n["x"]), Y(n["y"])
        fig.circle(nx, ny, NODE_R, c="ink", f="paper", sw=1.4)
        fig.text(nx, ny + 6, str(n["id"]), c="ink", size=SMALL - 2, b=True)


def model_figure(result, member=None):
    """The frame: members (the column being designed in colour), node and member ids, supports, the loads as
    entered with their cases, and the bay and storey dimensions."""
    if not result.get("nodes"):
        fig = Fig(200)
        fig.text(W / 2, 100, "No frame to draw", c="muted", size=TEXT)
        return fig
    X, Y, H, extent = _layout(result["nodes"])
    fig = Fig(H)
    for m, _, n1, n2 in _members(result):
        target = member is not None and str(m["id"]) == str(member)
        fig.line(X(n1["x"]), Y(n1["y"]), X(n2["x"]), Y(n2["y"]), c="accent" if target else "ink", sw=4.0 if target else 2.2)
    _supports(fig, result, X, Y)
    _dimensions(fig, result, X, Y, extent)
    _loads(fig, result, X, Y)
    for m, _, n1, n2 in _members(result):
        p1, p2 = (X(n1["x"]), Y(n1["y"])), (X(n2["x"]), Y(n2["y"]))
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        if _is_vertical(p1, p2):
            mx -= 34                                  # columns: id to the left
        else:
            my += 30                                  # beams: id below, clear of the load arrows
        _id_box(fig, mx, my, str(m["id"]), accent=member is not None and str(m["id"]) == str(member))
    _nodes(fig, result, X, Y)
    return fig


def _labels(values):
    """Indices of the values worth a label: both ends, and an interior extreme that is larger than both ends.
    A member with an (almost) constant value gets one label at mid-length."""
    v0, v1 = values[0], values[-1]
    vmax = max(abs(v) for v in values)
    if vmax < 1e-9:
        return []
    if max(values) - min(values) < 0.02 * vmax:
        return [len(values) // 2]
    out = [0, len(values) - 1]
    inner = max(range(1, len(values) - 1), key=lambda i: abs(values[i]), default=None)
    if inner is not None and abs(values[inner]) > max(abs(v0), abs(v1)) + 0.03 * vmax:
        out.append(inner)
    return out


def diagram_figure(result, kind):
    """The N, V or M diagram over the whole frame, with values at the member ends and at the peaks."""
    title = {"N": "axial force", "V": "shear force", "M": "bending moment"}[kind]
    if not result.get("nodes") or not result.get("members"):
        fig = Fig(200)
        fig.text(W / 2, 100, f"No {title} diagram", c="muted", size=TEXT)
        return fig
    X, Y, H, _ = _layout(result["nodes"])
    fig = Fig(H)
    colour = {"N": "react", "V": "sfd", "M": "bmd"}[kind]
    parts = [(m, r, (X(n1["x"]), Y(n1["y"])), (X(n2["x"]), Y(n2["y"])))
             for m, r, n1, n2 in _members(result) if r]
    peak = max((abs(v) for _, r, _, _ in parts for v in r[kind]), default=0.0)
    shortest = min((math.hypot(p2[0] - p1[0], p2[1] - p1[1]) for _, _, p1, p2 in parts), default=100.0)
    depth = min(80.0, 0.3 * shortest)
    k = depth / peak if peak > 1e-9 else 0.0
    # M on the tension side: sagging (+) is drawn on the right of node 1 → node 2 (below a left-to-right beam)
    side = -1.0 if kind == "M" else 1.0

    for m, r, p1, p2 in parts:
        fig.line(*p1, *p2, c="ink", sw=1.6)
        length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        if length < 1 or k == 0:
            continue
        ux, uy = (p2[0] - p1[0]) / length, (p2[1] - p1[1]) / length
        nx, ny = uy, -ux                              # left of node 1 → node 2 on the figure (y down)
        L = r["L"]
        pts = []
        for x, v in zip(r["x"], r[kind]):
            bx, by = p1[0] + ux * length * x / L, p1[1] + uy * length * x / L
            off = side * v * k
            pts.append((bx + nx * off, by + ny * off))
        fig.poly([p1] + pts + [p2], c=colour, f=colour, fo=0.16, sw=1.6, closed=True)

        values = r[kind]
        for i in _labels(values):
            v = values[i]
            if abs(v) < 0.04 * peak:
                continue
            t = r["x"][i] / L
            # keep end labels a little inside the member so the labels of members meeting at a joint stay apart
            t = min(max(t, min(0.12, 40 / length)), 1 - min(0.12, 40 / length))
            bx, by = p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t
            off = side * v * k
            out = 1.0 if off >= 0 else -1.0
            lx, ly = bx + nx * (off + out * 16), by + ny * (off + out * 16)
            anchor = "m"
            if abs(nx) > 0.7:                         # vertical member: text beside the diagram
                anchor = "s" if nx * out > 0 else "e"
                ly += 6
            else:
                ly += 14 if ny * out > 0 else -4
            fig.text(lx, ly, _value(v), c=colour, size=SMALL, a=anchor, b=True)

    for n in result["nodes"]:
        fig.circle(X(n["x"]), Y(n["y"]), 4.5, c="ink", f="paper", sw=1.2)
    return fig


def frame_figures(result, member=None):
    """{"model", "N", "V", "M"} figure specs for a frame result from ec2.frame.analyse_frame."""
    return {
        "model": model_figure(result, member=member).spec(),
        "N": diagram_figure(result, "N").spec(),
        "V": diagram_figure(result, "V").spec(),
        "M": diagram_figure(result, "M").spec(),
    }
