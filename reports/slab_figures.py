"""Figures of the slab analysis and cross-section, drawn once for web report and PDF.

For one-way slabs: reuses loading_figure, model_figure, reactions_figure,
diagrams_figure, and deflection_figure from reports.beam_figures.
For two-way slabs: panel_figure draws the plan view of the panel to scale with
continuous edge hatching, dimensions, spanning direction arrows, and moments.
strip_figure draws the 1 m wide design strip cross-section.
"""
import math

from reports.beam_figures import (
    Fig,
    W,
    X0,
    X1,
    _diagram,
    _fmt,
    _key_xs,
    _len,
    _supports,
    deflection_figure,
    diagrams_figure,
    loading_figure,
    model_figure,
    reactions_figure,
)

__all__ = [
    "strip_figure",
    "ribbed_figure",
    "panel_figure",
    "slab_figures",
    "loading_figure",
    "model_figure",
    "reactions_figure",
    "diagrams_figure",
    "deflection_figure",
]


def strip_figure(section):
    """1 m strip cross-section: thickness h, bottom x bars as dots at their spacing,

    bottom y bars as a line just above them (two-way and one-way distribution bars),
    top bars as dots, cover dimension, labels 'H10 @ 200 (x, bottom)' etc.
    """
    h = float(section.get("h", 200))
    b = float(section.get("b", 1000))
    cover = float(section.get("cover", 25))
    slab_type = section.get("slab_type", "one_way")

    bx = section.get("bottom_x") or {}
    bx_dia = float(bx.get("dia") or 10)
    bx_s = float(bx.get("s") or 200)
    bx_As = bx.get("As", 0)

    by = section.get("bottom_y") or {}
    by_dia = float(by.get("dia") or 10)
    by_s = float(by.get("s") or 200)
    by_As = by.get("As", 0)

    tx = section.get("top_x") or {}
    tx_dia_raw = tx.get("dia")
    tx_dia = float(tx_dia_raw) if tx_dia_raw and str(tx_dia_raw).lower() != "none" else None
    tx_s = float(tx.get("s") or 200) if tx_dia else None
    tx_As = tx.get("As", 0) if tx_dia else 0

    ty = section.get("top_y") or {}
    ty_dia_raw = ty.get("dia")
    ty_dia = float(ty_dia_raw) if ty_dia_raw and str(ty_dia_raw).lower() != "none" else None
    ty_s = float(ty.get("s") or 200) if ty_dia else None
    ty_As = ty.get("As", 0) if ty_dia else 0

    x0 = 140
    x1 = 860
    w_px = x1 - x0
    scale_x = w_px / 1000.0  # 0.72 px/mm
    scale_y = scale_x

    d_px = max(h * scale_y, 60)
    y_top = 80
    y_bot = y_top + d_px
    h_fig = int(y_bot + 130)

    fig = Fig(h_fig)

    def X(x_mm):
        return x0 + x_mm * scale_x

    # Concrete slab polygon with break zigzags at left and right
    mid_y = (y_top + y_bot) / 2
    left_pts = [
        (x0, y_top),
        (x0, mid_y - 8),
        (x0 - 7, mid_y - 3),
        (x0 + 7, mid_y + 3),
        (x0, mid_y + 8),
        (x0, y_bot),
    ]
    right_pts = [
        (x1, y_bot),
        (x1, mid_y + 8),
        (x1 + 7, mid_y + 3),
        (x1 - 7, mid_y - 3),
        (x1, mid_y - 8),
        (x1, y_top),
    ]
    fig.poly(left_pts + right_pts, c="ink", f="concrete", closed=True, sw=1.5)

    # Bottom x bars (dots at their spacing)
    r_bx = max(bx_dia / 2.0 * scale_y, 3.5)
    y_bx = y_bot - (cover + bx_dia / 2.0) * scale_y
    n_bx = max(1, int(round(1000.0 / bx_s)))
    first_bx = (1000.0 - (n_bx - 1) * bx_s) / 2.0
    for i in range(n_bx):
        bx_pos = first_bx + i * bx_s
        fig.circle(X(bx_pos), y_bx, r_bx, c="ink", f="ink", sw=1.0)

    # Bottom y bars (line just above bottom x bars)
    y_by = y_bot - (cover + bx_dia + by_dia / 2.0) * scale_y
    sw_by = max(by_dia * scale_y, 2.2)
    fig.line(X(cover), y_by, X(1000.0 - cover), y_by, c="accent", sw=sw_by)

    # Top x bars (dots at their spacing if present)
    if tx_dia and tx_s:
        r_tx = max(tx_dia / 2.0 * scale_y, 3.5)
        y_tx = y_top + (cover + tx_dia / 2.0) * scale_y
        n_tx = max(1, int(round(1000.0 / tx_s)))
        first_tx = (1000.0 - (n_tx - 1) * tx_s) / 2.0
        for i in range(n_tx):
            tx_pos = first_tx + i * tx_s
            fig.circle(X(tx_pos), y_tx, r_tx, c="ink", f="ink", sw=1.0)

    # Top y bars (line just below top x bars if present)
    if ty_dia and ty_s:
        tx_effective_dia = tx_dia if tx_dia else 10.0
        y_ty = y_top + (cover + tx_effective_dia + ty_dia / 2.0) * scale_y
        sw_ty = max(ty_dia * scale_y, 2.2)
        fig.line(X(cover), y_ty, X(1000.0 - cover), y_ty, c="accent", sw=sw_ty)

    # Dimensions
    # Horizontal width b = 1000 mm
    y_dim_b = y_bot + 36
    fig.line(x0, y_bot + 10, x0, y_dim_b + 5, c="muted", sw=0.8)
    fig.line(x1, y_bot + 10, x1, y_dim_b + 5, c="muted", sw=0.8)
    fig.line(x0, y_dim_b, x1, y_dim_b, c="ink", sw=1.0)
    fig.line(x0 - 4, y_dim_b + 4, x0 + 4, y_dim_b - 4, c="ink", sw=1.3)
    fig.line(x1 - 4, y_dim_b + 4, x1 + 4, y_dim_b - 4, c="ink", sw=1.3)
    fig.text(500, y_dim_b + 18, "b = 1000 mm (1 m design strip)", c="ink", size=14, a="m")

    # Vertical thickness h
    x_dim_h = x0 - 42
    fig.line(x0 - 10, y_top, x_dim_h - 5, y_top, c="muted", sw=0.8)
    fig.line(x0 - 10, y_bot, x_dim_h - 5, y_bot, c="muted", sw=0.8)
    fig.line(x_dim_h, y_top, x_dim_h, y_bot, c="ink", sw=1.0)
    fig.line(x_dim_h - 4, y_top + 4, x_dim_h + 4, y_top - 4, c="ink", sw=1.3)
    fig.line(x_dim_h - 4, y_bot + 4, x_dim_h + 4, y_bot - 4, c="ink", sw=1.3)
    fig.text(x_dim_h - 10, (y_top + y_bot) / 2 + 5, f"h = {int(h)} mm", c="ink", size=14, a="e")

    # Cover dimension / callout
    fig.text(x1 + 18, y_bot - (cover / 2.0) * scale_y + 4, f"cnom = {int(cover)} mm", c="muted", size=13, a="s")
    fig.line(x1 + 6, y_bot, x1 + 15, y_bot, c="muted", sw=0.8)
    fig.line(x1 + 6, y_bot - cover * scale_y, x1 + 15, y_bot - cover * scale_y, c="muted", sw=0.8)
    fig.line(x1 + 11, y_bot, x1 + 11, y_bot - cover * scale_y, c="muted", sw=0.8)

    # Top reinforcement callout
    if tx_dia:
        tx_txt = f"H{int(tx_dia)} @ {int(tx_s)} (x, top)"
        if tx_As:
            tx_txt += f" — {int(tx_As)} mm²/m"
        fig.text(x0, y_top - 36, tx_txt, c="ink", size=14, a="s", b=True)
        if ty_dia:
            ty_txt = f"H{int(ty_dia)} @ {int(ty_s)} (y, top)"
            if ty_As:
                ty_txt += f" — {int(ty_As)} mm²/m"
            fig.text(x1, y_top - 36, ty_txt, c="accent", size=14, a="e", b=True)
        # Leader line
        fig.line(x0 + 80, y_top - 30, x0 + 120, y_top + (cover + tx_dia / 2.0) * scale_y - 4, c="muted", sw=0.8)
    else:
        fig.text(x0, y_top - 20, "No top reinforcement", c="muted", size=13, a="s")

    # Bottom reinforcement callout
    y_lbl = y_dim_b + 44
    bx_txt = f"H{int(bx_dia)} @ {int(bx_s)} (x, bottom)"
    if bx_As:
        bx_txt += f" — {int(bx_As)} mm²/m"
    by_kind = "distribution" if slab_type == "one_way" else "bottom y"
    by_txt = f"H{int(by_dia)} @ {int(by_s)} (y, {by_kind})"
    if by_As:
        by_txt += f" — {int(by_As)} mm²/m"
    fig.text(x0, y_lbl, bx_txt, c="ink", size=14, a="s", b=True)
    fig.text(x1, y_lbl, by_txt, c="accent", size=14, a="e", b=True)
    # Leader line
    fig.line(x0 + 80, y_lbl - 14, x0 + 100, y_bx + 4, c="muted", sw=0.8)

    return fig.spec()


def ribbed_figure(section):
    """Cross-section of a ribbed slab across two ribs: Maxpans between the ribs, the topping with its
    fabric, the bars in each rib, and the dimensions bw, s, hf and h."""
    bw, hf, ph, h = (float(section[k]) for k in ("bw", "hf", "ph", "h"))
    s_mm = float(section["spacing"])
    cover = float(section.get("cover", 25))
    link = float(section.get("link_dia") or 0)
    bot, top = section.get("bottom") or {}, section.get("top") or {}
    width = 2 * s_mm                        # two rib spacings, a rib in the middle of each
    x0, x1 = 120, 880
    k = (x1 - x0) / width
    y_top = 70
    y_bot = y_top + h * k
    fig = Fig(int(y_bot + 150))
    X = lambda mm: x0 + mm * k
    Y = lambda mm: y_bot - mm * k          # mm from the soffit
    ribs = [s_mm / 2, 3 * s_mm / 2]
    # topping and ribs as one outline
    pts = [(X(0), Y(h)), (X(width), Y(h)), (X(width), Y(ph))]
    for c in reversed(ribs):
        pts += [(X(c + bw / 2), Y(ph)), (X(c + bw / 2), Y(0)), (X(c - bw / 2), Y(0)), (X(c - bw / 2), Y(ph))]
    pts += [(X(0), Y(ph))]
    fig.poly(pts, c="ink", f="concrete", closed=True, sw=1.5)
    # Maxpans: crossed boxes between the ribs (half pans at the edges)
    pan_edges = [(0, ribs[0] - bw / 2), (ribs[0] + bw / 2, ribs[1] - bw / 2), (ribs[1] + bw / 2, width)]
    for a, b in pan_edges:
        box = [(X(a), Y(ph)), (X(b), Y(ph)), (X(b), Y(0)), (X(a), Y(0))]
        fig.poly(box, c="muted", f="paper", closed=True, sw=1.0)
        fig.line(X(a), Y(ph), X(b), Y(0), c="muted", sw=0.8)
        fig.line(X(a), Y(0), X(b), Y(ph), c="muted", sw=0.8)
    # fabric in the topping
    if section.get("mesh"):
        fig.line(X(0), Y(h - hf / 2), X(width), Y(h - hf / 2), c="accent", sw=1.4, dash=[6, 4])
    # bars and links in each rib
    for c in ribs:
        if link:
            fig.poly([(X(c - bw / 2 + cover), Y(h - cover)), (X(c + bw / 2 - cover), Y(h - cover)),
                      (X(c + bw / 2 - cover), Y(cover)), (X(c - bw / 2 + cover), Y(cover))], c="accent", closed=True,
                     sw=max(link * k, 1.2))
        for face, data, at in (("bottom", bot, cover + link + (bot.get("dia") or 10) / 2),
                               ("top", top, h - cover - link - (top.get("dia") or 10) / 2)):
            n, dia = int(data.get("n") or 0), data.get("dia")
            if not dia or not n:
                continue
            lo = c - bw / 2 + cover + link + dia / 2
            hi = c + bw / 2 - cover - link - dia / 2
            xs = [(lo + hi) / 2] if n == 1 else [lo + (hi - lo) * i / (n - 1) for i in range(n)]
            for xb in xs:
                fig.circle(X(xb), Y(at), max(dia / 2 * k, 3.0), c="ink", f="ink", sw=0.8)
    # dimensions: rib width, rib centres, topping and overall depth
    yd = y_bot + 30
    c0 = ribs[0]
    fig.line(X(c0 - bw / 2), yd, X(c0 + bw / 2), yd, c="ink", sw=1.0)
    fig.text(X(c0), yd + 18, f"bw = {bw:g}", c="ink", size=14, a="m")
    yd2 = y_bot + 66
    fig.line(X(ribs[0]), yd2, X(ribs[1]), yd2, c="ink", sw=1.0)
    for xx in (ribs[0], ribs[1]):
        fig.line(X(xx), y_bot + 4, X(xx), yd2 + 6, c="muted", sw=0.7, dash=[3, 3])
    fig.text((X(ribs[0]) + X(ribs[1])) / 2, yd2 + 18, f"ribs at s = {s_mm:g} mm", c="ink", size=14, a="m")
    fig.line(X(width) + 22, Y(h), X(width) + 22, Y(0), c="ink", sw=1.0)
    fig.text(X(width) + 30, (Y(h) + Y(0)) / 2 + 5, f"h = {h:g}", c="ink", size=14, a="s")
    fig.text(X(width) + 30, Y(h - hf / 2) + 5, f"hf = {hf:g}", c="muted", size=13, a="s")
    # callouts
    label = lambda n, d: f"{n}H{d:g}" if d and n else "none"
    fig.text(x0, y_top - 30, f"Top bars per rib: {label(int(top.get('n') or 0), top.get('dia'))}"
             + (f"; fabric {section['mesh']} in the topping" if section.get("mesh") else "; no fabric"), c="ink", size=14, a="s", b=True)
    fig.text(x0, y_top - 10, f"Maxpan {section.get('maxpan', '')}: {ph:g} mm deep", c="muted", size=13, a="s")
    fig.text(x0, y_bot + 118, f"Bottom bars per rib: {label(int(bot.get('n') or 0), bot.get('dia'))}"
             + (f"; links H{link:g}" if link else "; no links") + f"; cnom = {cover:g} mm", c="ink", size=14, a="s", b=True)
    return fig.spec()


def panel_figure(panel):
    """Plan view of a two-way slab panel to scale: ly across, lx up, so that the top and bottom
    edges are the long edges as on the input page:

    continuous edges thick line with hatching outside, discontinuous thin line;
    dimension lines lx, ly; direction arrows;
    moment values at mid-span and continuous edges (sagging in 'bmd', hogging in 'accent');
    panel title with the case.
    """
    lx = float(panel.get("lx", 5.0))
    ly = float(panel.get("ly", 6.0))
    edges = panel.get("edges") or {}
    case = panel.get("case") or {}
    case_label = case.get("label", "Two-way slab panel")
    moms = panel.get("moments") or {}
    coeffs = panel.get("coefficients") or {}

    fig = Fig(640)

    # Scale to fit inside available area
    scale = min(560.0 / ly, 330.0 / lx)
    w_px = ly * scale
    h_px = lx * scale
    x_mid, y_mid = 500.0, 335.0

    x0 = x_mid - w_px / 2.0
    x1 = x_mid + w_px / 2.0
    y0 = y_mid - h_px / 2.0  # top edge
    y1 = y_mid + h_px / 2.0  # bottom edge

    # Title
    fig.text(500, 32, f"Two-way slab panel — {case_label}", c="ink", size=17, a="m", b=True)
    fig.text(500, 54, f"lx = {lx:.2f} m (short span), ly = {ly:.2f} m (long span), ly/lx = {ly / lx:.2f}", c="muted", size=13, a="m")

    # Panel concrete fill
    fig.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], c="ink", f="concrete", fo=0.45, closed=True, sw=0.5)

    # Top edge
    top_cont = edges.get("top") == "continuous"
    fig.line(x0, y0, x1, y0, c="ink", sw=3.5 if top_cont else 1.4)
    if top_cont:
        x = x0 + 4
        while x < x1:
            fig.line(x, y0, x + 7, y0 - 10, c="muted", sw=1.0)
            x += 9

    # Bottom edge
    bot_cont = edges.get("bottom") == "continuous"
    fig.line(x0, y1, x1, y1, c="ink", sw=3.5 if bot_cont else 1.4)
    if bot_cont:
        x = x0 + 4
        while x < x1:
            fig.line(x, y1, x - 7, y1 + 10, c="muted", sw=1.0)
            x += 9

    # Left edge
    left_cont = edges.get("left") == "continuous"
    fig.line(x0, y0, x0, y1, c="ink", sw=3.5 if left_cont else 1.4)
    if left_cont:
        y = y0 + 4
        while y < y1:
            fig.line(x0, y, x0 - 10, y + 7, c="muted", sw=1.0)
            y += 9

    # Right edge
    right_cont = edges.get("right") == "continuous"
    fig.line(x1, y0, x1, y1, c="ink", sw=3.5 if right_cont else 1.4)
    if right_cont:
        y = y0 + 4
        while y < y1:
            fig.line(x1, y, x1 + 10, y - 7, c="muted", sw=1.0)
            y += 9

    # Dimension lines: lx across
    y_dim_x = y1 + 38
    fig.line(x0, y1 + 14, x0, y_dim_x + 6, c="muted", sw=0.8)
    fig.line(x1, y1 + 14, x1, y_dim_x + 6, c="muted", sw=0.8)
    fig.line(x0, y_dim_x, x1, y_dim_x, c="ink", sw=1.0)
    fig.line(x0 - 4, y_dim_x + 4, x0 + 4, y_dim_x - 4, c="ink", sw=1.3)
    fig.line(x1 - 4, y_dim_x + 4, x1 + 4, y_dim_x - 4, c="ink", sw=1.3)
    fig.text(x_mid, y_dim_x + 18, f"ly = {ly:.2f} m (long edges)", c="ink", size=14, a="m", b=True)

    # Dimension lines: ly up
    x_dim_y = x0 - 45
    fig.line(x0 - 14, y0, x_dim_y - 6, y0, c="muted", sw=0.8)
    fig.line(x0 - 14, y1, x_dim_y - 6, y1, c="muted", sw=0.8)
    fig.line(x_dim_y, y0, x_dim_y, y1, c="ink", sw=1.0)
    fig.line(x_dim_y - 4, y0 + 4, x_dim_y + 4, y0 - 4, c="ink", sw=1.3)
    fig.line(x_dim_y - 4, y1 + 4, x_dim_y + 4, y1 - 4, c="ink", sw=1.3)
    fig.text(x_dim_y - 10, y_mid + 5, f"lx = {lx:.2f} m", c="ink", size=14, a="e", b=True)

    # Direction arrows
    fig.arrow(x_mid - w_px * 0.35, y_mid, x_mid + w_px * 0.35, y_mid, c="muted", sw=1.0, head=7)
    fig.arrow(x_mid + w_px * 0.35, y_mid, x_mid - w_px * 0.35, y_mid, c="muted", sw=1.0, head=7)
    fig.arrow(x_mid, y_mid + h_px * 0.35, x_mid, y_mid - h_px * 0.35, c="muted", sw=1.0, head=7)
    fig.arrow(x_mid, y_mid - h_px * 0.35, x_mid, y_mid + h_px * 0.35, c="muted", sw=1.0, head=7)

    # Moments
    msx_mid = moms.get("msx_mid", 0)
    msy_mid = moms.get("msy_mid", 0)
    msx_sup = moms.get("msx_sup", 0)
    msy_sup = moms.get("msy_sup", 0)

    # Mid-span sagging moments (bmd)
    fig.text(x_mid, y_mid - 16, f"msx,mid = +{msx_mid:.2f} kNm/m (bottom x)", c="bmd", size=14, a="m", b=True)
    fig.text(x_mid, y_mid + 18, f"msy,mid = +{msy_mid:.2f} kNm/m (bottom y)", c="bmd", size=14, a="m", b=True)

    # Hogging moments (accent) at continuous edges
    if top_cont:
        fig.text(x_mid, y0 + 18, f"Top cont. edge: msx,sup = −{msx_sup:.2f} kNm/m (top x)", c="accent", size=13, a="m", b=True)
    else:
        fig.text(x_mid, y0 + 18, "Discontinuous", c="muted", size=12, a="m")

    if bot_cont:
        fig.text(x_mid, y1 - 10, f"Bottom cont. edge: msx,sup = −{msx_sup:.2f} kNm/m (top x)", c="accent", size=13, a="m", b=True)
    else:
        fig.text(x_mid, y1 - 10, "Discontinuous", c="muted", size=12, a="m")

    # short edges: the left label above the middle, the right one below it, so they never overlap
    if left_cont:
        fig.text(x0 + 10, y_mid - 52, f"msy,sup = −{msy_sup:.2f}", c="accent", size=13, a="s", b=True)
    else:
        fig.text(x0 + 10, y_mid - 52, "Discontinuous", c="muted", size=12, a="s")

    if right_cont:
        fig.text(x1 - 10, y_mid + 62, f"msy,sup = −{msy_sup:.2f}", c="accent", size=13, a="e", b=True)
    else:
        fig.text(x1 - 10, y_mid + 62, "Discontinuous", c="muted", size=12, a="e")

    # Shear summary note
    shears = panel.get("shears") or {}
    VEd = shears.get("VEd", 0)
    vEd = shears.get("vEd", 0)
    vRd_c = shears.get("vRd_c", 0)
    fig.text(500, 618, f"Design shear: VEd = {VEd:.2f} kN/m, vEd = {vEd:.3f} MPa ≤ vRd,c = {vRd_c:.3f} MPa", c="muted", size=13, a="m")

    return fig.spec()


def slab_figures(report):
    """All figures for a slab report or analysis result."""
    plots = report.get("plots") or {}
    figures = {}

    if "section" in plots and plots["section"]:
        sec = plots["section"]
        figures["strip"] = ribbed_figure(sec) if sec.get("slab_type") == "ribbed" else strip_figure(sec)

    analysis = plots.get("analysis")
    if analysis:
        figures.update({
            "loading": loading_figure(analysis),
            "model": model_figure(analysis),
            "reactions": reactions_figure(analysis),
            "diagrams": diagrams_figure(analysis),
            "deflection": deflection_figure(analysis),
        })

    panel = plots.get("panel")
    if panel:
        figures["panel"] = panel_figure(panel)

    return figures
