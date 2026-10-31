"""PDF report for a column check: the column drawings on top of the shared report layout."""
from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, KeepTogether, Paragraph, Spacer, Table, TableStyle

from .beam_pdf import _table, render_figure
from .frame_figures import frame_figures
from .pdf_base import (ACCENT, CONCRETE, INK, MUTED, RULE, STATUS, build_report, fonts, nice_ticks,
                       para, styles, target_status)


def _section_drawing(report, width=86 * mm, height=78 * mm):
    f = fonts()
    sec = report["plots"]["section"]
    status = target_status(report)
    d = Drawing(width, height)
    b, h = sec["b"], sec["h"]
    pad_l, pad_b, pad_r, pad_t = 16 * mm, 13 * mm, 6 * mm, 8 * mm
    s = min((width - pad_l - pad_r) / b, (height - pad_b - pad_t) / h)
    w, hh = b * s, h * s
    x0 = pad_l + (width - pad_l - pad_r - w) / 2
    y0 = pad_b + (height - pad_b - pad_t - hh) / 2
    fail = lambda target: status.get(target) == "fail"

    d.add(Rect(x0, y0, w, hh, fillColor=CONCRETE, strokeColor=STATUS["fail"] if fail("section") else INK,
               strokeWidth=1.2))
    c = sec["cover"] + sec["link_dia"] / 2
    r_link = max(sec["link_dia"] * 2 * s, 1.5)
    d.add(Rect(x0 + c * s, y0 + c * s, (b - 2 * c) * s, (h - 2 * c) * s, rx=r_link, ry=r_link,
               fillColor=None, strokeColor=STATUS["fail"] if fail("links") else ACCENT,
               strokeWidth=max(sec["link_dia"] * s, 0.7)))
    bar_colour = STATUS["fail"] if fail("bars") else INK
    for bar in sec["bars"]:
        d.add(Circle(x0 + (bar["x"] + b / 2) * s, y0 + (bar["y"] + h / 2) * s, max(bar["dia"] / 2 * s, 1.2),
                     fillColor=bar_colour, strokeColor=None))

    dash = [4, 2, 1, 2]
    cx, cy = x0 + w / 2, y0 + hh / 2
    d.add(Line(x0 - 4, cy, x0 + w + 4, cy, strokeColor=MUTED, strokeWidth=0.4, strokeDashArray=dash))
    d.add(Line(cx, y0 - 4, cx, y0 + hh + 4, strokeColor=MUTED, strokeWidth=0.4, strokeDashArray=dash))
    d.add(String(x0 + w + 2, cy + 2, "y", fontName=f["bold"], fontSize=7, fillColor=MUTED))
    d.add(String(cx + 2, y0 + hh + 2, "z", fontName=f["bold"], fontSize=7, fillColor=MUTED))

    def dim_h(xa, xb, y, text):
        d.add(Line(xa, y, xb, y, strokeColor=INK, strokeWidth=0.5))
        for x in (xa, xb):
            d.add(Line(x - 1.5, y - 1.5, x + 1.5, y + 1.5, strokeColor=INK, strokeWidth=0.7))
            d.add(Line(x, y - 3, x, y + 3, strokeColor=INK, strokeWidth=0.3))
        d.add(String((xa + xb) / 2, y - 8, text, fontName=f["regular"], fontSize=8, fillColor=INK,
                     textAnchor="middle"))

    def dim_v(ya, yb, x, text):
        d.add(Line(x, ya, x, yb, strokeColor=INK, strokeWidth=0.5))
        for y in (ya, yb):
            d.add(Line(x - 1.5, y - 1.5, x + 1.5, y + 1.5, strokeColor=INK, strokeWidth=0.7))
            d.add(Line(x - 3, y, x + 3, y, strokeColor=INK, strokeWidth=0.3))
        d.add(String(x - 3, (ya + yb) / 2, text, fontName=f["regular"], fontSize=8, fillColor=INK, textAnchor="end"))

    dim_h(x0, x0 + w, y0 - 6, f"b = {b:g}")
    dim_v(y0, y0 + hh, x0 - 6, f"h = {h:g}")
    d.add(String(x0 + w, y0 + hh + 10, f"cnom = {sec['cover']:g} mm, a = {sec['a']:.0f} mm",
                 fontName=f["regular"], fontSize=7.5, fillColor=STATUS["fail"] if fail("cover") else MUTED,
                 textAnchor="end"))
    return d


def _interaction_drawing(report, axis, width=86 * mm, height=72 * mm):
    f = fonts()
    data = report["plots"]["interaction"][axis]
    bending = next(c for c in report["checks"] if c["id"] == f"bending_{axis}")
    d = Drawing(width, height)
    pad_l, pad_b, pad_r, pad_t = 13 * mm, 10 * mm, 4 * mm, 7 * mm
    pw, ph = width - pad_l - pad_r, height - pad_b - pad_t
    mt = nice_ticks(max([p[0] for p in data["curve"]] + [data["MEd"]]) * 1.12)
    nt = nice_ticks(max(data["Nmax"], data["NEd"]) * 1.08)
    m_max, n_max = mt[-1], nt[-1]
    X = lambda m: pad_l + m / m_max * pw
    Y = lambda n: pad_b + n / n_max * ph

    for m in mt:
        d.add(Line(X(m), pad_b, X(m), pad_b + ph, strokeColor=RULE, strokeWidth=0.3))
        d.add(String(X(m), pad_b - 8, f"{m:g}", fontName=f["regular"], fontSize=7, fillColor=MUTED,
                     textAnchor="middle"))
    for n in nt:
        d.add(Line(pad_l, Y(n), pad_l + pw, Y(n), strokeColor=RULE, strokeWidth=0.3))
        d.add(String(pad_l - 2, Y(n) - 2, f"{n:g}", fontName=f["regular"], fontSize=7, fillColor=MUTED,
                     textAnchor="end"))
    d.add(Rect(pad_l, pad_b, pw, ph, fillColor=None, strokeColor=INK, strokeWidth=0.6))
    d.add(String(pad_l + pw / 2, 1, f"M{axis} (kNm)", fontName=f["regular"], fontSize=8, fillColor=INK,
                 textAnchor="middle"))
    d.add(String(pad_l, height - 9, f"N–M interaction about {axis}–{axis}, N in kN", fontName=f["bold"],
                 fontSize=8.5, fillColor=INK))

    pts = []
    for m, n in data["curve"]:
        pts += [X(m), Y(n)]
    d.add(PolyLine(pts, strokeColor=ACCENT, strokeWidth=1.3))
    colour = STATUS["pass"] if bending["status"] == "pass" else STATUS["fail"]
    if data["MRd"] is not None:
        d.add(Line(X(0), Y(data["NEd"]), X(data["MRd"]), Y(data["NEd"]), strokeColor=MUTED, strokeWidth=0.5,
                   strokeDashArray=[2, 2]))
        d.add(Polygon([X(data["MRd"]), Y(data["NEd"]) + 2.5, X(data["MRd"]) + 2.5, Y(data["NEd"]),
                       X(data["MRd"]), Y(data["NEd"]) - 2.5, X(data["MRd"]) - 2.5, Y(data["NEd"])],
                      fillColor=ACCENT, strokeColor=None))
        d.add(String(X(data["MRd"]) + 4, Y(data["NEd"]) + 3, f"MRd {data['MRd']:.1f}", fontName=f["regular"],
                     fontSize=7.5, fillColor=ACCENT))
    d.add(Circle(X(data["M02"]), Y(data["NEd"]), 2, fillColor=colors.white, strokeColor=MUTED, strokeWidth=0.8))
    d.add(Circle(X(data["MEd"]), Y(data["NEd"]), 2.6, fillColor=colour, strokeColor=colors.white, strokeWidth=0.6))
    d.add(String(X(data["MEd"]) + 4, Y(data["NEd"]) - 9, f"MEd {data['MEd']:.1f}", fontName=f["bold"],
                 fontSize=7.5, fillColor=colour))
    return d


def _elevation_drawing(report, axis, width=86 * mm, height=78 * mm):
    f = fonts()
    der = report["derived"]
    ax = der["axes"][axis]
    d = Drawing(width, height)
    top, bot = height - 12 * mm, 9 * mm
    col_x, col_w = 30 * mm, 7 * mm
    d.add(Rect(col_x, bot, col_w, top - bot, fillColor=CONCRETE, strokeColor=INK, strokeWidth=0.9))
    for y, k in ((top, ax["restraint"]["k_top"]), (bot, ax["restraint"]["k_bottom"])):
        sign = 1 if y == top else -1
        if ax["restraint"]["method"] == "k" and k is None:
            tri = [col_x + col_w / 2, y, col_x + col_w / 2 - 4, y + sign * 6, col_x + col_w / 2 + 4, y + sign * 6]
            d.add(Polygon(tri, fillColor=None, strokeColor=INK, strokeWidth=0.7))
        else:
            d.add(Line(col_x - 7, y, col_x + col_w + 7, y, strokeColor=INK, strokeWidth=1.2))
            for i in range(6):
                xs = col_x - 7 + i * (col_w + 14) / 5
                d.add(Line(xs, y, xs - 3, y + sign * 3.5, strokeColor=INK, strokeWidth=0.5))
    d.add(Line(col_x + col_w / 2, top + 14, col_x + col_w / 2, top + 7, strokeColor=STATUS["fail"], strokeWidth=1))
    d.add(Polygon([col_x + col_w / 2 - 2.5, top + 8.5, col_x + col_w / 2 + 2.5, top + 8.5, col_x + col_w / 2,
                   top + 4], fillColor=STATUS["fail"], strokeColor=None))
    d.add(String(col_x + col_w / 2 + 4, top + 10, f"NEd = {der['NEd']:.0f} kN", fontName=f["regular"], fontSize=7.5,
                 fillColor=INK))
    lx = col_x - 9 * mm
    span = (top - bot) * min(ax["l0"] / der["l"], 1.0)
    mid = (top + bot) / 2
    d.add(Line(lx, mid - span / 2, lx, mid + span / 2, strokeColor=ACCENT, strokeWidth=0.6))
    for y in (mid - span / 2, mid + span / 2):
        d.add(Line(lx - 2, y, lx + 2, y, strokeColor=ACCENT, strokeWidth=0.6))
    d.add(String(lx - 2, mid, f"l₀ = {ax['l0'] / 1000:.2f} m", fontName=f["regular"], fontSize=7.5,
                 fillColor=ACCENT, textAnchor="end"))
    m_top_is_max = abs(ax["M_top"]) >= abs(ax["M_bottom"])
    m_top = ax["M02"] if m_top_is_max else ax["M01"]
    m_bot = ax["M01"] if m_top_is_max else ax["M02"]
    if ax["slender"]:
        mid_total = ax["M0e"] + ax["M2"]
        end_total = ax["M01"] + 0.5 * ax["M2"]
        top_total, bot_total = (ax["M02"], end_total) if m_top_is_max else (end_total, ax["M02"])
    else:
        mid_total, top_total, bot_total = (m_top + m_bot) / 2, m_top, m_bot
    peak = max(abs(m_top), abs(m_bot), abs(mid_total), abs(top_total), abs(bot_total), 1e-9)
    base_x, scale = col_x + col_w + 14 * mm, 21 * mm / peak
    d.add(Line(base_x, bot, base_x, top, strokeColor=INK, strokeWidth=0.6))
    d.add(PolyLine([base_x + m_bot * scale, bot, base_x + m_top * scale, top], strokeColor=MUTED,
                   strokeWidth=0.8, strokeDashArray=[3, 2]))
    curve = []
    for i in range(21):
        t = i / 20
        m = bot_total * (1 - t) * (1 - 2 * t) + mid_total * 4 * t * (1 - t) + top_total * t * (2 * t - 1)
        curve += [base_x + m * scale, bot + t * (top - bot)]
    d.add(PolyLine(curve, strokeColor=ACCENT, strokeWidth=1.2))
    for value, y in ((top_total, top), (mid_total, mid), (bot_total, bot)):
        d.add(String(base_x + value * scale + (3 if value >= 0 else -3), y - 2, f"{value:.1f}",
                     fontName=f["regular"], fontSize=7.5, fillColor=ACCENT, textAnchor="start" if value >= 0 else "end"))
    d.add(String(4, height - 8, f"Elevation and moments about {axis}–{axis} (kNm)",
                 fontName=f["bold"], fontSize=8.5, fillColor=INK))
    d.add(String(base_x - 2, bot - 9, "first order dashed, design solid", fontName=f["regular"],
                 fontSize=7, fillColor=MUTED, textAnchor="middle"))
    tag = (f"λ = {ax['lam']:.1f} ≥ λlim = {ax['lam_lim']:.1f}: slender, e₂ = {ax['e2']:.1f} mm"
           if ax["slender"] else f"λ = {ax['lam']:.1f} < λlim = {ax['lam_lim']:.1f}: not slender")
    d.add(String(width / 2, 0, tag, fontName=f["regular"], fontSize=7.5, fillColor=MUTED, textAnchor="middle"))
    return d


def frame_actions_rows(act):
    """The design actions taken from the frame for the chosen column, as (label, value) rows (web and PDF)."""
    k = lambda v: "pinned" if v == "pinned" else f"{v:.2f}"
    return [
        ("Column", f"{act['member']}, {act['bottom_node']} to {act['top_node']}, l = {act['l']:.2f} m"),
        ("Axial force NEd", f"{act['NEd']:.1f} kN (compression)"),
        ("Moment at the top Mtop", f"{act['M_top']:.1f} kNm ({act['top_node']})"),
        ("Moment at the bottom Mbottom", f"{act['M_bottom']:.1f} kNm ({act['bottom_node']})"),
        ("Curvature", f"{act['curvature']} (end moments {'of the same' if act['curvature'] == 'single' else 'of opposite'} sense)"),
        ("End stiffness k, top / bottom", f"{k(act['k_top'])} / {k(act['k_bottom'])}"),
    ]


def frame_analysis_section(report):
    """Section 2 of the PDF when the column's actions come from a 2D frame analysis."""
    frame = report["plots"].get("frame")
    if not frame:
        return None
    st = styles()
    figs = report["plots"].get("figures") or frame_figures(frame, member=frame["member"])

    def block(title, spec, caption):
        return KeepTogether([Paragraph(title, st["h2"]), render_figure(spec), Spacer(1, 1.5 * mm),
                             Paragraph(caption, st["muted"])])

    cell = ParagraphStyle("cell", parent=st["body"], fontSize=11, leading=14)
    rows = [["Design action", "Value"]] + [[para(label, cell), para(value, cell)]
                                           for label, value in frame_actions_rows(frame["actions"])]
    return [
        CondPageBreak(120 * mm), Paragraph("2. Frame analysis", st["h1"]),
        Paragraph("Linear elastic matrix stiffness analysis of the plane frame under the design loads "
                  "(G × 1.35, Q × 1.5, self-weight as G). Bending moments are drawn on the tension side of each "
                  "member: sagging below a beam, hogging above it.", st["body"]),
        block("Frame and design loads", figs["model"], "Nodes are circled and members boxed; the column being "
              "designed is drawn in colour."),
        block("Bending moments (kNm)", figs["M"], "Values at the member ends and at the peaks."),
        KeepTogether([Paragraph("Design actions for the column", st["h2"]),
                      _table(rows, [70 * mm, 104 * mm], st),
                      Paragraph("Bending is in the plane of the frame, about y–y of the column.", st["muted"])]),
    ]


def build_column_pdf(report):
    drawings = Table([[_section_drawing(report), _elevation_drawing(report, "y")],
                      [_interaction_drawing(report, "y"), _interaction_drawing(report, "z")]],
                     colWidths=[90 * mm, 90 * mm])
    drawings.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, RULE), ("INNERGRID", (0, 0), (-1, -1), 0.6, RULE),
                                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    caption = ("Cross-section to scale (a part drawn red failed a check), moments along the column, and N–M "
               "interaction curves for the reinforcement provided with the design point (MEd, NEd), green when "
               "it lies inside the curve.")
    extra = frame_analysis_section(report) if report.get("plots", {}).get("frame") else None
    return build_report(report, "Column", drawings, caption, extra=extra)
