"""Figures of a pad foundation, drawn once as simple shapes for the page, the report and the PDF
(see reports/beam_figures.py for the format).

section: the base cut along L with the column, the soil over the base, the bars, the bending faces
and the beam-shear sections at d, then the ground pressure under it: characteristic (bearing, with
the allowable value) and design (STR). plan: the base with its bars both ways, the column, the
beam-shear lines at d and the punching control perimeters. Parts whose checks fail are drawn red.

The figures are shown narrow on the input page, so the text is larger than in the beam figures.
"""
import math

from reports.beam_figures import Fig

TEXT = 24          # labels
SMALL = 21         # values and keys


def _status(checks):
    worst = {}
    order = {"na": 0, "info": 0, "pass": 1, "warn": 2, "fail": 3}
    for c in checks or []:
        t = c.get("target")
        if t and order.get(c["status"], 0) > order.get(worst.get(t), 0):
            worst[t] = c["status"]
    return worst


def _dim_h(fig, xa, xb, y, label, c="ink"):
    fig.line(xa, y, xb, y, c=c, sw=1.2)
    for x in (xa, xb):
        fig.line(x - 6, y + 6, x + 6, y - 6, c=c, sw=1.5)
    fig.text((xa + xb) / 2, y - 9, label, c=c, size=SMALL)


def _dim_v(fig, x, ya, yb, label, c="ink"):
    fig.line(x, ya, x, yb, c=c, sw=1.2)
    for y in (ya, yb):
        fig.line(x - 6, y + 6, x + 6, y - 6, c=c, sw=1.5)
    fig.text(x + 12, (ya + yb) / 2 + 7, label, c=c, size=SMALL, a="s")


def _pressure_block(fig, sec, which, X, y0, depth, title, status, limit=None):
    """Pressure diagram under the base, the heavily loaded edge on the right. Returns its lowest y."""
    p = sec[which]
    L = sec["L"]
    fig.text(X(0), y0 - 12, title, c="ink", size=SMALL, a="s", b=True)
    if p["p1"] is None:
        fig.text(X(L / 2), y0 + 34, "The base overturns: no pressure diagram", c="load", size=SMALL)
        return y0 + 50
    top = max(p["p1"], limit or 0)
    k = depth / top if top else 0
    colour = "load" if status == "fail" else "sfd"
    if p["shape"] == "triangular":
        pts = [(X(L - p["contact"]), y0), (X(L), y0), (X(L), y0 + p["p1"] * k)]
    else:
        pts = [(X(0), y0), (X(L), y0), (X(L), y0 + p["p1"] * k), (X(0), y0 + p["p2"] * k)]
    fig.poly(pts, c=colour, f=colour, fo=0.18, sw=1.6, closed=True)
    fig.text(X(L) + 10, y0 + p["p1"] * k + 8, f"{p['p1']:.1f}", c=colour, size=SMALL, a="s", b=True)
    if p["shape"] == "triangular":
        fig.text(X(L - p["contact"]) - 8, y0 + 22, "0", c=colour, size=SMALL, a="e")
    else:
        fig.text(X(0) - 10, y0 + p["p2"] * k + 8, f"{p['p2']:.1f}", c=colour, size=SMALL, a="e")
    if limit:
        fig.line(X(0), y0 + limit * k, X(L), y0 + limit * k, c="muted", sw=1.2, dash=[8, 5])
        fig.text(X(L / 2), y0 + limit * k + 26, f"allowable {limit:g} kPa", c="muted", size=SMALL)
    return y0 + top * k + (34 if limit else 8)


def section_figure(sec, checks=None):
    st = _status(checks)
    L, h, cx, hs = sec["L"], sec["h"], sec["cx"], sec.get("hs") or 0
    x0, x1 = 130, 830
    k = (x1 - x0) / L
    X = lambda mm: x0 + mm * k
    y_col = 120                        # top of the column stub
    y_ground = y_col + 60
    y_top = y_ground + hs * k
    y_bot = y_top + h * k
    fig = Fig(0)
    fail = lambda part: "load" if st.get(part) == "fail" else None

    # loads on the column
    mid = X(L / 2)
    fig.arrow(mid, y_col - 62, mid, y_col - 4, c="load", sw=2.6, head=13)
    load = f"NEd = {sec['NEd']:.0f} kN" + (f"   MEd = {sec['MEd']:.1f} kNm" if sec.get("MEd") else "")
    fig.text(mid + 20, y_col - 40, load, c="load", size=TEXT, a="s", b=True)
    # ground and soil over the base
    fig.line(20, y_ground, 980, y_ground, c="muted", sw=1.4)
    for i in range(20):
        xh = 30 + i * 49
        fig.line(xh, y_ground, xh - 12, y_ground + 12, c="muted", sw=1.0)
    if hs:
        fig.text(X(L) + 14, (y_ground + y_top) / 2 + 8, f"soil {hs / 1000:g} m", c="muted", size=SMALL, a="s")
    # column stub and base
    c_left, c_right = X((L - cx) / 2), X((L + cx) / 2)
    fig.poly([(c_left, y_col), (c_right, y_col), (c_right, y_top), (c_left, y_top)], c="ink", f="concrete", sw=1.8,
             closed=True)
    fig.poly([(X(0), y_top), (X(L), y_top), (X(L), y_bot), (X(0), y_bot)], c=fail("section") or "ink", f="concrete",
             sw=2.4, closed=True)
    if sec.get("MEd"):
        fig.arc_arrow(mid, y_col + 4, 44, 165, 15, c="load", sw=2.2, head=12)

    # bars: along L in the bottom layer (bent up at the ends), along B as dots above them
    cover = sec["cover"]
    bars = fail("bars") or "accent"
    xd, yd = sec["x"]["dia"], sec["y"]["dia"]
    y_x = y_bot - (cover + xd / 2) * k
    fig.poly([(X(cover), y_x - 0.4 * h * k), (X(cover), y_x), (X(L - cover), y_x), (X(L - cover), y_x - 0.4 * h * k)],
             c=bars, sw=max(xd * k, 2.5))
    y_y = y_bot - (cover + xd + yd / 2) * k
    n = max(2, int((L - 2 * cover) // sec["y"]["s"]) + 1)
    pitch = (L - 2 * cover - yd) / (n - 1)
    for i in range(n):
        fig.circle(X(cover + yd / 2 + i * pitch), y_y, max(yd / 2 * k, 2.8), c=bars, f=bars, sw=0.6)

    # bending face and beam-shear section at d, on the heavily loaded side (right)
    face = (L + cx) / 2
    d = sec["dx"]
    fig.line(X(face), y_top - 10, X(face), y_bot + 10, c="bmd", sw=1.5, dash=[7, 5])
    fig.text(X(face) - 6, y_bot + 32, "M", c="bmd", size=SMALL, a="e", b=True)
    if face + d < L:
        fig.line(X(face + d), y_top - 10, X(face + d), y_bot + 10, c="sfd", sw=1.5, dash=[7, 5])
        fig.text(X(face + d) + 6, y_bot + 32, "V at d", c="sfd", size=SMALL, a="s", b=True)
    _dim_v(fig, X(L) + 34, y_top, y_bot, f"h {h:g}")
    _dim_h(fig, X(face), X(L), y_top - 22, f"a = {(L - cx) / 2:.0f}")
    fig.text(X(0), y_bot + 62, f"H{xd} @ {sec['x']['s']:g} along L, H{yd} @ {sec['y']['s']:g} along B; "
                               f"cover {cover:g}", c=fail("bars") or "ink", size=SMALL, a="s")

    # pressures under the base
    y = _pressure_block(fig, sec, "sls", X, y_bot + 130, 80, "Bearing pressure, kPa", st.get("section"),
                        sec.get("q_allow"))
    y = _pressure_block(fig, sec, "uls", X, y + 60, 80, "Design ground pressure (STR), kPa", None)
    _dim_h(fig, X(0), X(L), y + 46, f"L = {L / 1000:g} m")
    fig.h = int(y + 66)
    return fig.spec()


def _rounded(cx, cy, a, n=10):
    """Control perimeter at a from a cx × cy column, rounded corners: points in mm about the centre."""
    pts = []
    for qx, qy, start in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        for i in range(n + 1):
            ang = math.radians(start + 90 * i / n)
            pts.append((qx * cx / 2 + a * math.cos(ang), qy * cy / 2 + a * math.sin(ang)))
    return pts


def plan_figure(sec, checks=None):
    st = _status(checks)
    L, B, cx, cy = sec["L"], sec["B"], sec["cx"], sec["cy"]
    k = min(680 / L, 560 / B)
    w, hgt = L * k, B * k
    left = 470 - w / 2
    top = 50
    X = lambda mm: left + (mm + L / 2) * k          # mm from the base centre
    Y = lambda mm: top + (B / 2 - mm) * k
    fig = Fig(int(top + hgt + 150))
    fig.poly([(X(-L / 2), Y(B / 2)), (X(L / 2), Y(B / 2)), (X(L / 2), Y(-B / 2)), (X(-L / 2), Y(-B / 2))],
             c="load" if st.get("section") == "fail" else "ink", f="concrete", sw=2.4, closed=True)
    # bars both ways, lightly
    bars = "load" if st.get("bars") == "fail" else "accent"
    cover = sec["cover"]
    for along, s_mm, across in (("L", sec["x"]["s"], B), ("B", sec["y"]["s"], L)):
        n = max(2, int((across - 2 * cover) // s_mm) + 1)
        pitch = (across - 2 * cover) / (n - 1)
        for i in range(n):
            t = -across / 2 + cover + i * pitch
            if along == "L":
                fig.line(X(-L / 2 + cover), Y(t), X(L / 2 - cover), Y(t), c=bars, sw=0.8)
            else:
                fig.line(X(t), Y(B / 2 - cover), X(t), Y(-B / 2 + cover), c=bars, sw=0.8)
    # beam-shear lines at d from the faces
    d = sec["d"]
    for x in (cx / 2 + sec["dx"], -cx / 2 - sec["dx"]):
        if abs(x) < L / 2:
            fig.line(X(x), Y(B / 2), X(x), Y(-B / 2), c="sfd", sw=1.6, dash=[8, 5])
    for y in (cy / 2 + sec["dy"], -cy / 2 - sec["dy"]):
        if abs(y) < B / 2:
            fig.line(X(-L / 2), Y(y), X(L / 2), Y(y), c="sfd", sw=1.6, dash=[8, 5])
    # punching perimeters: basic at 2d and the critical one
    per = sec.get("perimeter") or {}
    if per.get("a_2d"):
        fig.poly([(X(px), Y(py)) for px, py in _rounded(cx, cy, per["a_2d"])], c="muted", sw=1.5, closed=True)
    crit = per.get("a")
    punch = "load" if st.get("perimeter") == "fail" else "bmd"
    if crit:
        fig.poly([(X(px), Y(py)) for px, py in _rounded(cx, cy, crit)], c=punch, sw=3.0, closed=True)
    # column
    fig.poly([(X(-cx / 2), Y(cy / 2)), (X(cx / 2), Y(cy / 2)), (X(cx / 2), Y(-cy / 2)), (X(-cx / 2), Y(-cy / 2))],
             c="ink", f="ink", fo=0.8, sw=1.6, closed=True)
    # dimensions and key
    _dim_h(fig, X(-L / 2), X(L / 2), top - 16, f"L = {L / 1000:g} m")
    _dim_v(fig, X(L / 2) + 28, Y(B / 2), Y(-B / 2), f"B = {B / 1000:g} m")
    y = top + hgt + 42
    xk = X(-L / 2)
    fig.line(xk, y - 7, xk + 40, y - 7, c="sfd", sw=1.6, dash=[8, 5])
    fig.text(xk + 52, y, "beam shear at d from the faces", c="ink", size=SMALL, a="s")
    if crit:
        fig.line(xk, y + 30, xk + 40, y + 30, c=punch, sw=3.0)
        fig.text(xk + 52, y + 37, f"critical punching perimeter at {crit:.0f} mm ({crit / d:.2f}d)", c="ink",
                 size=SMALL, a="s")
    fig.line(xk, y + 67, xk + 40, y + 67, c="muted", sw=1.5)
    fig.text(xk + 52, y + 74, f"basic control perimeter at 2d = {2 * d:.0f} mm", c="ink", size=SMALL, a="s")
    return fig.spec()


def foundation_figures(report):
    sec = report["plots"]["section"]
    checks = report.get("checks")
    # plan_plain: without the failed parts in red, for the run page while the tests are still running
    return {"section": section_figure(sec, checks), "plan": plan_figure(sec, checks), "plan_plain": plan_figure(sec)}


__all__ = ["foundation_figures", "section_figure", "plan_figure"]
