"""PDF report for a beam check: the section, the structural analysis and the shared report layout."""
from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, KeepTogether, Paragraph, Spacer, Table, TableStyle

from .beam_figures import beam_figures
from .pdf_base import ACCENT, CONCRETE, INK, MUTED, RULE, STATUS, build_report, fonts, styles, target_status

FIGURE_COLOURS = {
    "ink": INK, "muted": MUTED, "accent": ACCENT, "load": colors.HexColor("#DC2626"), "rule": RULE, "concrete": CONCRETE,
    "paper": colors.white, "sfd": colors.HexColor("#2563EB"), "bmd": colors.HexColor("#059669"),
    "defl": colors.HexColor("#D97706"), "react": colors.HexColor("#7C3AED"),
    "node": colors.HexColor("#EA580C"), "elem": colors.HexColor("#0D9488"), "dof": colors.HexColor("#4F46E5"),
}
WIDTH = 180 * mm


def _outline(sec):
    """Section outline in mm, origin at the bottom of the web centre line."""
    b, h = sec["b"], sec["h"]
    if sec["shape"] == "rectangular":
        return [(-b / 2, 0), (b / 2, 0), (b / 2, h), (-b / 2, h)]
    hf, beff = sec["hf"], sec["beff"]
    if sec["flange"] == "T":
        half = beff / 2
        return [(-b / 2, 0), (b / 2, 0), (b / 2, h - hf), (half, h - hf), (half, h), (-half, h), (-half, h - hf),
                (-b / 2, h - hf)]
    return [(-b / 2, 0), (b / 2, 0), (b / 2, h - hf), (beff - b / 2, h - hf), (beff - b / 2, h), (-b / 2, h)]


def _section_drawing(report, width=86 * mm, height=72 * mm):
    f = fonts()
    sec = report["plots"]["section"]
    status = target_status(report)
    fail = lambda t: status.get(t) == "fail"
    pts = _outline(sec)
    xs = [p[0] for p in pts]
    x_min, x_max, h = min(xs), max(xs), sec["h"]
    pad = 12 * mm
    s = min((width - 2 * pad) / (x_max - x_min), (height - 2 * pad) / h)
    ox = pad + (width - 2 * pad - (x_max - x_min) * s) / 2 - x_min * s
    oy = pad
    X = lambda x: ox + x * s
    Y = lambda y: oy + y * s
    d = Drawing(width, height)
    flat = []
    for x, y in pts:
        flat += [X(x), Y(y)]
    d.add(Polygon(flat, fillColor=CONCRETE, strokeColor=STATUS["fail"] if fail("section") else INK, strokeWidth=1.1))
    c = sec["cover"] + sec["link_dia"] / 2
    d.add(Rect(X(-sec["b"] / 2 + c), Y(c), (sec["b"] - 2 * c) * s, (h - 2 * c) * s, rx=3, ry=3, fillColor=None,
               strokeColor=STATUS["fail"] if fail("links") else ACCENT, strokeWidth=max(sec["link_dia"] * s, 0.7)))
    for bar in sec["bars"]:
        colour = STATUS["fail"] if fail("bars") else INK
        d.add(Circle(X(bar["x"]), Y(bar["y"]), max(bar["dia"] / 2 * s, 1.2), fillColor=colour, strokeColor=None))
    d.add(String(X(0), oy - 9, f"b{'w' if sec['shape'] == 'flanged' else ''} = {sec['b']:g}", fontName=f["regular"],
                 fontSize=8, fillColor=INK, textAnchor="middle"))
    d.add(String(X(x_min) - 3, Y(h / 2), f"h = {h:g}", fontName=f["regular"], fontSize=8, fillColor=INK,
                 textAnchor="end"))
    if sec["shape"] == "flanged":
        d.add(String(X((x_min + x_max) / 2), Y(h) + 4, f"beff = {sec['beff']:.0f}, hf = {sec['hf']:g}",
                     fontName=f["regular"], fontSize=8, fillColor=MUTED, textAnchor="middle"))
    for kind, y in (("bottom", 2), ("top", height - 9)):
        bars = [b for b in sec["bars"] if b["kind"] == kind]
        if bars:
            d.add(String(width - 2, y, f"{kind}: {len(bars)}H{bars[0]['dia']}", fontName=f["regular"], fontSize=7.5,
                         fillColor=MUTED, textAnchor="end"))
    return d


def render_figure(spec, width=WIDTH):
    """Draw a figure from reports.beam_figures at the given width."""
    f = fonts()
    k = width / spec["w"]
    H = spec["h"] * k
    d = Drawing(width, H)
    colour = lambda name: FIGURE_COLOURS.get(name) if name else None
    for it in spec["items"]:
        kind = it["k"]
        if kind == "line":
            x1, y1, x2, y2 = it["p"]
            d.add(Line(x1 * k, H - y1 * k, x2 * k, H - y2 * k, strokeColor=colour(it["c"]),
                       strokeWidth=it["sw"] * k * 1.25,
                       strokeDashArray=[v * k for v in it["dash"]] if it.get("dash") else None))
        elif kind == "poly":
            pts = []
            for i in range(0, len(it["p"]), 2):
                pts += [it["p"][i] * k, H - it["p"][i + 1] * k]
            fill = colour(it.get("f"))
            if fill is not None and it.get("fo", 1) < 1:
                fill = colors.Color(fill.red, fill.green, fill.blue, alpha=it["fo"])
            if it.get("closed") or fill is not None:
                d.add(Polygon(pts, fillColor=fill, strokeColor=colour(it["c"]) if it["sw"] > 0.2 else None,
                              strokeWidth=it["sw"] * k * 1.25))
            else:
                d.add(PolyLine(pts, strokeColor=colour(it["c"]), strokeWidth=it["sw"] * k * 1.25))
        elif kind == "circle":
            d.add(Circle(it["x"] * k, H - it["y"] * k, it["r"] * k, fillColor=colour(it.get("f")),
                         strokeColor=colour(it["c"]), strokeWidth=it["sw"] * k * 1.25))
        elif kind == "text":
            d.add(String(it["x"] * k, H - it["y"] * k, it["t"], fontName=f["bold"] if it.get("b") else f["regular"],
                         fontSize=it["size"] * k * 1.05, fillColor=colour(it["c"]),
                         textAnchor={"s": "start", "m": "middle", "e": "end"}[it["a"]]))
    return d


def _table(rows, widths, st, head_rows=1):
    t = Table(rows, colWidths=widths, repeatRows=head_rows)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), fonts()["regular"], 11), ("FONT", (0, 0), (-1, head_rows - 1), fonts()["bold"], 11),
        ("TEXTCOLOR", (0, 0), (-1, head_rows - 1), MUTED), ("LINEBELOW", (0, head_rows - 1), (-1, head_rows - 1), 0.8, INK),
        ("LINEBELOW", (0, head_rows), (-1, -1), 0.3, RULE), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def analysis_section(report):
    """Section 2 of the PDF: the structural analysis behind the design actions."""
    data = report["plots"].get("analysis")
    if not data:
        return None
    st = styles()
    figs = beam_figures(report)

    def block(title, spec, caption):
        return KeepTogether([Paragraph(title, st["h2"]), render_figure(spec), Spacer(1, 1.5 * mm),
                             Paragraph(caption, st["muted"])])

    flow = [CondPageBreak(120 * mm), Paragraph("2. Structural analysis", st["h1"]),
            Paragraph("Matrix stiffness analysis of the beam under the design loads. Positive shear and "
                      "hogging moments are drawn above the x-axis; negative shear and sagging moments below it.", st["body"]),
            block("Beam, loads and stiffness", figs["loading"], "Design loads on the beam, with the dimensions "
                  "between supports and loads, and the second moment of area of each part."),
            block("Analytical model", figs["model"], "Nodes are circled and elements boxed. Degrees of freedom: "
                  "free ones (blue) numbered first, restrained ones (green, crossed) after them."),
            block("Support reactions", figs["reactions"], "Reactions from the analysis: forces upwards, moments "
                  "with the sense drawn."),
            block("Shear force and bending moment diagrams", figs["diagrams"], "Values at the nodes and loads, "
                  "and at the peaks; dots mark zero moment. Bold values are the ones designed for."),
            block("Deflected shape", figs["deflection"], "Elastic deflection, for information.")]
    rx = [["Support (node)", "x (m)", "Type", "Ry (kN)", "M (kNm)"]]
    for r in data["reactions"]:
        rx.append([str(r["node"]), f"{r['x']:.2f}", r["type"], f"{r['Ry']:.2f}",
                   f"{r['M']:.2f}" if r["M"] is not None else "—"])
    me = [["Element", "Nodes", "V1 (kN)", "M1 (kNm)", "V2 (kN)", "M2 (kNm)"]]
    for e in data["elements"]:
        me.append([str(e["e"]), f"{e['start']}–{e['end']}"] + [f"{v:.2f}" for v in e["Q"]])
    jd = [["Node", "x (m)", "DOFs", "v (mm)", "θ (rad)"]]
    for n in data["nodes"]:
        jd.append([str(n["n"]), f"{n['x']:.2f}", f"{n['dofs'][0]}, {n['dofs'][1]}",
                   "0" if n["fix"][0] else f"{n['v_mm']:.4f}", "0" if n["fix"][1] else f"{n['theta']:.6f}"])
    flow += [KeepTogether([Paragraph("Support reactions", st["h2"]),
                           _table(rx, [36 * mm, 24 * mm, 30 * mm, 30 * mm, 30 * mm], st)]),
             KeepTogether([Paragraph("Member end forces", st["h2"]),
                           _table(me, [22 * mm, 22 * mm, 30 * mm, 32 * mm, 30 * mm, 32 * mm], st),
                           Paragraph("Shears upwards and moments anticlockwise on the element ends.", st["muted"])]),
             KeepTogether([Paragraph("Joint displacements", st["h2"]),
                           _table(jd, [22 * mm, 26 * mm, 26 * mm, 40 * mm, 40 * mm], st),
                           Paragraph("Translations upwards and rotations anticlockwise, in the directions of the "
                                     "degrees of freedom.", st["muted"])])]
    return flow


def build_beam_pdf(report):
    sec = Table([[_section_drawing(report, width=100 * mm)]], colWidths=[110 * mm])
    sec.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, RULE), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    caption = "Cross-section to scale; a part drawn red failed a check."
    return build_report(report, "Beam", sec, caption, extra=analysis_section(report))
