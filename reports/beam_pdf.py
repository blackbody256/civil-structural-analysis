"""PDF report for a beam check: the beam drawings on top of the shared report layout."""
from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Polygon, Rect, String
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle

from .pdf_base import ACCENT, CONCRETE, INK, MUTED, RULE, STATUS, build_report, fonts, target_status


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
        colour = STATUS["fail"] if fail("bars") and bar["kind"] == "tension" else INK
        d.add(Circle(X(bar["x"]), Y(bar["y"]), max(bar["dia"] / 2 * s, 1.2), fillColor=colour, strokeColor=None))
    d.add(String(X(0), oy - 9, f"b{'w' if sec['shape'] == 'flanged' else ''} = {sec['b']:g}", fontName=f["regular"],
                 fontSize=8, fillColor=INK, textAnchor="middle"))
    d.add(String(X(x_min) - 3, Y(h / 2), f"h = {h:g}", fontName=f["regular"], fontSize=8, fillColor=INK,
                 textAnchor="end"))
    if sec["shape"] == "flanged":
        d.add(String(X((x_min + x_max) / 2), Y(h) + 4, f"beff = {sec['beff']:.0f}, hf = {sec['hf']:g}",
                     fontName=f["regular"], fontSize=8, fillColor=MUTED, textAnchor="middle"))
    face = "top" if sec["tension_face"] == "top" else "bottom"
    d.add(String(width - 2, 2, f"tension at the {face}", fontName=f["regular"], fontSize=7.5, fillColor=MUTED,
                 textAnchor="end"))
    return d


def _elevation_drawing(report, width=86 * mm, height=72 * mm):
    f = fonts()
    el = report["plots"]["elevation"]
    d = Drawing(width, height)
    left, right = 10 * mm, width - 6 * mm
    L = el["l"]
    X = lambda x: left + x / L * (right - left)
    beam_y = height - 16 * mm
    d.add(Rect(left, beam_y, right - left, 3 * mm, fillColor=CONCRETE, strokeColor=INK, strokeWidth=0.8))
    if el.get("supports"):
        for sp in el["supports"]:
            sx = X(sp["x"])
            if sp.get("fix_m") == 1:
                d.add(Line(sx, beam_y - 6, sx, beam_y + 14, strokeColor=INK, strokeWidth=1.6))
            else:
                d.add(Polygon([sx, beam_y, sx - 3, beam_y - 5, sx + 3, beam_y - 5], fillColor=None, strokeColor=INK,
                              strokeWidth=0.7))
    elif el["system"] == "cantilever":
        d.add(Line(left, beam_y - 6, left, beam_y + 14, strokeColor=INK, strokeWidth=1.6))
    else:
        for x in (left, right):
            d.add(Polygon([x, beam_y, x - 3, beam_y - 5, x + 3, beam_y - 5], fillColor=None, strokeColor=INK,
                          strokeWidth=0.7))
    if el["w"]:
        for i in range(9):
            x = left + i * (right - left) / 8
            d.add(Line(x, beam_y + 3 * mm + 7, x, beam_y + 3 * mm + 1, strokeColor=STATUS["fail"], strokeWidth=0.7))
        d.add(String((left + right) / 2, beam_y + 3 * mm + 9, f"w = {el['w']:.1f} kN/m", fontName=f["regular"],
                     fontSize=7.5, fillColor=INK, textAnchor="middle"))
    d.add(String(4, height - 7, f"Span {L:.2f} m: bending moment (kNm) and shear (kN)", fontName=f["bold"],
                 fontSize=8.5, fillColor=INK))
    if el.get("delta"):
        max_d = max(abs(v) for v in el["delta"])
        d.add(String(right, height - 7, f"δmax = {max_d:.2f} mm", fontName=f["bold"],
                     fontSize=8.0, fillColor=MUTED, textAnchor="end"))

    def diagram(values, base, depth, colour, label):
        peak = max(abs(v) for v in values) or 1
        pts = [left, base]
        for x, v in zip(el["x"], values):
            pts += [X(x), base - v / peak * depth]
        pts += [right, base]
        d.add(Line(left, base, right, base, strokeColor=MUTED, strokeWidth=0.5))
        d.add(PolyLine(pts, strokeColor=colour, strokeWidth=1.1))
        d.add(String(left - 2, base - 2, label, fontName=f["regular"], fontSize=7, fillColor=MUTED, textAnchor="end"))

    diagram(el["M"], beam_y - 15 * mm, 11 * mm, ACCENT, "M")
    diagram(el["V"], 13 * mm, 8 * mm, MUTED, "V")
    xd = X(el["x_design"])
    d.add(Line(xd, 4 * mm, xd, beam_y, strokeColor=STATUS["fail"], strokeWidth=0.5, strokeDashArray=[2, 2]))
    d.add(String(min(xd + 3, right - 40), beam_y - 4 * mm, f"MEd = {el['MEd']:.1f}", fontName=f["bold"],
                 fontSize=7.5, fillColor=ACCENT))
    d.add(String(min(xd + 3, right - 40), 4 * mm, f"VEd = {el['VEd']:.1f}", fontName=f["regular"], fontSize=7.5,
                 fillColor=INK))
    for r in el.get("reactions", []):
        xr = X(r["x"])
        d.add(String(xr, beam_y - 9 * mm, f"Ry={abs(r['Ry']):.1f}kN", fontName=f["regular"],
                     fontSize=6.5, fillColor=INK, textAnchor="middle"))
    return d


def build_beam_pdf(report):
    drawings = Table([[_section_drawing(report), _elevation_drawing(report)]], colWidths=[90 * mm, 90 * mm])
    drawings.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, RULE), ("INNERGRID", (0, 0), (-1, -1), 0.6, RULE),
                                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    caption = ("Cross-section to scale (a part drawn red failed a check) and the bending moment and shear along the "
               "span, with the section checked marked by the dashed line.")
    return build_report(report, "Beam", drawings, caption)
