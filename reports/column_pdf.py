"""PDF report for a column check, built with reportlab.

Order: overall summary (title block, verdict, key results, checks at a glance and
drawings), then the detailed calculation sheet, the inputs and the assumptions.
"""
import datetime as dt
import math
from io import BytesIO
from html import escape
from pathlib import Path

from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, KeepTogether, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

from ec2.notation import to_markup

FONT_FILES = {
    "Sans": "DejaVuSans.ttf",
    "Sans-Bold": "DejaVuSans-Bold.ttf",
    "Cond-Bold": "DejaVuSansCondensed-Bold.ttf",
    "Mono": "DejaVuSansMono.ttf",
}
FONT_DIRS = (Path(__file__).resolve().parent.parent / "static" / "fonts",
             Path("/usr/share/fonts/truetype/dejavu"))

INK = colors.HexColor("#14213D")
MUTED = colors.HexColor("#5B6476")
RULE = colors.HexColor("#C9C3B3")
PAPER = colors.HexColor("#F4F1E8")
CONCRETE = colors.HexColor("#E6E1D3")
ACCENT = colors.HexColor("#1F4E8C")
STATUS_HEX = {"pass": "#1E7B47", "fail": "#B42318", "warn": "#B7791F", "info": "#2B6CB0", "na": "#8A8F98"}
STATUS = {k: colors.HexColor(v) for k, v in STATUS_HEX.items()}
STATUS_TINT = {k: colors.HexColor(v) for k, v in
               {"pass": "#E3F1E8", "fail": "#F8E1DE", "warn": "#F7EEDC", "info": "#E2ECF7", "na": "#ECEDEF"}.items()}
STATUS_LABEL = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "info": "INFO", "na": "N/A"}
SEVERITY = {"fail": 4, "warn": 3, "pass": 2, "info": 1, "na": 0}

_fonts = None


def _register_fonts():
    global _fonts
    if _fonts is not None:
        return _fonts
    found = {}
    for name, filename in FONT_FILES.items():
        for folder in FONT_DIRS:
            path = folder / filename
            if path.exists():
                pdfmetrics.registerFont(TTFont(name, str(path)))
                found[name] = name
                break
    if len(found) == len(FONT_FILES):
        registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans", boldItalic="Sans-Bold")
        _fonts = {"sans": "Sans", "bold": "Sans-Bold", "cond": "Cond-Bold", "mono": "Mono"}
    else:  # Greek symbols will not render, but the report still builds
        _fonts = {"sans": "Helvetica", "bold": "Helvetica-Bold", "cond": "Helvetica-Bold", "mono": "Courier"}
    return _fonts


def _styles(f):
    base = dict(fontName=f["sans"], textColor=INK, fontSize=8.5, leading=11)
    return {
        "title": ParagraphStyle("title", **{**base, "fontName": f["cond"], "fontSize": 20, "leading": 24}),
        "subtitle": ParagraphStyle("subtitle", **{**base, "textColor": MUTED, "fontSize": 9, "leading": 12}),
        "h1": ParagraphStyle("h1", **{**base, "fontName": f["cond"], "fontSize": 13, "leading": 16,
                                      "spaceBefore": 10, "spaceAfter": 5}),
        "h2": ParagraphStyle("h2", **{**base, "fontName": f["bold"], "fontSize": 9.5, "leading": 12,
                                      "spaceBefore": 8, "spaceAfter": 3, "textColor": ACCENT}),
        "body": ParagraphStyle("body", **base),
        "cell": ParagraphStyle("cell", **{**base, "fontSize": 8, "leading": 10.6}),
        "cellb": ParagraphStyle("cellb", **{**base, "fontName": f["bold"], "fontSize": 8, "leading": 10.6}),
        "label": ParagraphStyle("label", **{**base, "fontName": f["bold"], "fontSize": 6.5, "leading": 8,
                                            "textColor": MUTED}),
        "value": ParagraphStyle("value", **{**base, "fontName": f["bold"], "fontSize": 9.5, "leading": 12}),
        "work": ParagraphStyle("work", **{**base, "fontSize": 7.6, "leading": 10.6}),
        "small": ParagraphStyle("small", **{**base, "fontSize": 7.2, "leading": 9.2, "textColor": MUTED}),
        "verdict": ParagraphStyle("verdict", **{**base, "fontName": f["cond"], "fontSize": 16, "leading": 19,
                                                "textColor": colors.white}),
        "verdict_sub": ParagraphStyle("verdict_sub", **{**base, "fontSize": 8.5, "textColor": colors.white}),
    }


class _NumberedCanvas(pdfcanvas.Canvas):
    """Canvas that knows the page count, for 'Page n of N' footers."""

    def __init__(self, *args, decorate=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []
        self._decorate = decorate

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._decorate(self, total)
            super().showPage()
        super().save()


def _status_chip(status, f, size=7.5):
    return Paragraph(f'<font name="{f["bold"]}" color="{STATUS_HEX[status]}">{STATUS_LABEL[status]}</font>',
                     ParagraphStyle("chip", fontName=f["bold"], fontSize=size, leading=size + 2))


def _pdf(markup):
    """Browser markup to reportlab markup: smaller, less lowered sub/superscripts."""
    return (markup.replace("<sub>", '<sub rise="22%" size="74%">')
                  .replace("<sup>", '<sup rise="38%" size="74%">'))


def _p(text, style, markup=False):
    return Paragraph(_pdf(text if markup else to_markup(str(text))), style)


def _nice_ticks(vmax, count=5):
    if vmax <= 0:
        return [0.0, 1.0]
    raw = vmax / count
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    return [i * step for i in range(int(math.ceil(vmax / step)) + 1)]


# ---------------------------------------------------------------- drawings

def _target_status(report):
    worst = {}
    for c in report["checks"]:
        t = c.get("target")
        if t and SEVERITY[c["status"]] > SEVERITY.get(worst.get(t, "na"), 0):
            worst[t] = c["status"]
    return worst


def _section_drawing(report, f, width=86 * mm, height=78 * mm):
    sec = report["plots"]["section"]
    status = _target_status(report)
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

    # axes
    dash = [4, 2, 1, 2]
    cx, cy = x0 + w / 2, y0 + hh / 2
    d.add(Line(x0 - 4, cy, x0 + w + 4, cy, strokeColor=MUTED, strokeWidth=0.4, strokeDashArray=dash))
    d.add(Line(cx, y0 - 4, cx, y0 + hh + 4, strokeColor=MUTED, strokeWidth=0.4, strokeDashArray=dash))
    d.add(String(x0 + w + 2, cy + 2, "y", fontName=f["bold"], fontSize=6.5, fillColor=MUTED))
    d.add(String(cx + 2, y0 + hh + 2, "z", fontName=f["bold"], fontSize=6.5, fillColor=MUTED))

    # dimensions
    def dim_h(xa, xb, y, text):
        d.add(Line(xa, y, xb, y, strokeColor=INK, strokeWidth=0.5))
        for x in (xa, xb):
            d.add(Line(x - 1.5, y - 1.5, x + 1.5, y + 1.5, strokeColor=INK, strokeWidth=0.7))
            d.add(Line(x, y - 3, x, y + 3, strokeColor=INK, strokeWidth=0.3))
        d.add(String((xa + xb) / 2, y - 7.5, text, fontName=f["sans"], fontSize=7, fillColor=INK,
                     textAnchor="middle"))

    def dim_v(ya, yb, x, text):
        d.add(Line(x, ya, x, yb, strokeColor=INK, strokeWidth=0.5))
        for y in (ya, yb):
            d.add(Line(x - 1.5, y - 1.5, x + 1.5, y + 1.5, strokeColor=INK, strokeWidth=0.7))
            d.add(Line(x - 3, y, x + 3, y, strokeColor=INK, strokeWidth=0.3))
        d.add(String(x - 3, (ya + yb) / 2, text, fontName=f["sans"], fontSize=7, fillColor=INK, textAnchor="end"))

    dim_h(x0, x0 + w, y0 - 6, f"b = {b:g}")
    dim_v(y0, y0 + hh, x0 - 6, f"h = {h:g}")
    cover_colour = STATUS["fail"] if fail("cover") else MUTED
    d.add(String(x0 + w, y0 + hh + 10, f"cnom = {sec['cover']:g} mm, a = {sec['a']:.0f} mm",
                 fontName=f["sans"], fontSize=6.5, fillColor=cover_colour, textAnchor="end"))
    return d


def _interaction_drawing(report, axis, f, width=86 * mm, height=72 * mm):
    data = report["plots"]["interaction"][axis]
    bending = next(c for c in report["checks"] if c["id"] == f"bending_{axis}")
    ok = bending["status"] == "pass"
    d = Drawing(width, height)
    pad_l, pad_b, pad_r, pad_t = 13 * mm, 10 * mm, 4 * mm, 7 * mm
    pw, ph = width - pad_l - pad_r, height - pad_b - pad_t
    m_max = max([p[0] for p in data["curve"]] + [data["MEd"]]) * 1.12
    n_max = max(data["Nmax"], data["NEd"]) * 1.08
    mt, nt = _nice_ticks(m_max), _nice_ticks(n_max)
    m_max, n_max = mt[-1], nt[-1]
    X = lambda m: pad_l + m / m_max * pw
    Y = lambda n: pad_b + n / n_max * ph

    for m in mt:
        d.add(Line(X(m), pad_b, X(m), pad_b + ph, strokeColor=RULE, strokeWidth=0.3))
        d.add(String(X(m), pad_b - 7, f"{m:g}", fontName=f["sans"], fontSize=6, fillColor=MUTED,
                     textAnchor="middle"))
    for n in nt:
        d.add(Line(pad_l, Y(n), pad_l + pw, Y(n), strokeColor=RULE, strokeWidth=0.3))
        d.add(String(pad_l - 2, Y(n) - 2, f"{n:g}", fontName=f["sans"], fontSize=6, fillColor=MUTED,
                     textAnchor="end"))
    d.add(Rect(pad_l, pad_b, pw, ph, fillColor=None, strokeColor=INK, strokeWidth=0.6))
    d.add(String(pad_l + pw / 2, 2, f"M{axis} [kNm]", fontName=f["sans"], fontSize=6.5, fillColor=INK,
                 textAnchor="middle"))
    d.add(String(pad_l, height - 9, f"N–M interaction about {axis}–{axis}  [N in kN]", fontName=f["bold"],
                 fontSize=7, fillColor=INK))

    pts = []
    for m, n in data["curve"]:
        pts += [X(m), Y(n)]
    d.add(PolyLine(pts, strokeColor=ACCENT, strokeWidth=1.3))
    colour = STATUS["pass"] if ok else STATUS["fail"]
    if data["MRd"] is not None:
        d.add(Line(X(0), Y(data["NEd"]), X(data["MRd"]), Y(data["NEd"]), strokeColor=MUTED, strokeWidth=0.5,
                   strokeDashArray=[2, 2]))
        d.add(Polygon([X(data["MRd"]), Y(data["NEd"]) + 2.5, X(data["MRd"]) + 2.5, Y(data["NEd"]),
                       X(data["MRd"]), Y(data["NEd"]) - 2.5, X(data["MRd"]) - 2.5, Y(data["NEd"])],
                      fillColor=ACCENT, strokeColor=None))
        d.add(String(X(data["MRd"]) + 4, Y(data["NEd"]) + 3, f"MRd {data['MRd']:.1f}", fontName=f["sans"],
                     fontSize=6.3, fillColor=ACCENT))
    d.add(Circle(X(data["M02"]), Y(data["NEd"]), 2, fillColor=colors.white, strokeColor=MUTED, strokeWidth=0.8))
    d.add(Circle(X(data["MEd"]), Y(data["NEd"]), 2.6, fillColor=colour, strokeColor=colors.white,
                 strokeWidth=0.6))
    d.add(String(X(data["MEd"]) + 4, Y(data["NEd"]) - 8, f"MEd {data['MEd']:.1f}", fontName=f["bold"],
                 fontSize=6.3, fillColor=colour))
    return d


def _elevation_drawing(report, axis, f, width=86 * mm, height=78 * mm):
    der = report["derived"]
    ax = der["axes"][axis]
    d = Drawing(width, height)
    top, bot = height - 12 * mm, 9 * mm
    col_x, col_w = 30 * mm, 7 * mm
    # column and end restraints
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
    # axial load
    d.add(Line(col_x + col_w / 2, top + 14, col_x + col_w / 2, top + 7, strokeColor=STATUS["fail"], strokeWidth=1))
    d.add(Polygon([col_x + col_w / 2 - 2.5, top + 8.5, col_x + col_w / 2 + 2.5, top + 8.5, col_x + col_w / 2,
                   top + 4], fillColor=STATUS["fail"], strokeColor=None))
    d.add(String(col_x + col_w / 2 + 4, top + 10, f"NEd = {der['NEd']:.0f} kN", fontName=f["sans"], fontSize=6.5,
                 fillColor=INK))
    # effective length bracket
    lx = col_x - 9 * mm
    span = (top - bot) * min(ax["l0"] / der["l"], 1.0)
    mid = (top + bot) / 2
    d.add(Line(lx, mid - span / 2, lx, mid + span / 2, strokeColor=ACCENT, strokeWidth=0.6))
    for y in (mid - span / 2, mid + span / 2):
        d.add(Line(lx - 2, y, lx + 2, y, strokeColor=ACCENT, strokeWidth=0.6))
    d.add(String(lx - 2, mid, f"l\u2080 = {ax['l0'] / 1000:.2f} m", fontName=f["sans"], fontSize=6.3,
                 fillColor=ACCENT, textAnchor="end"))
    # moment diagram (Fig 4): first order and design envelope
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
        y = bot + t * (top - bot)
        # quadratic through bottom, mid-height and top values
        m = bot_total * (1 - t) * (1 - 2 * t) + mid_total * 4 * t * (1 - t) + top_total * t * (2 * t - 1)
        curve += [base_x + m * scale, y]
    d.add(PolyLine(curve, strokeColor=ACCENT, strokeWidth=1.2))
    for value, y, label in ((top_total, top, "top"), (mid_total, mid, "mid"), (bot_total, bot, "bottom")):
        d.add(String(base_x + value * scale + (3 if value >= 0 else -3), y - 2, f"{value:.1f}",
                     fontName=f["sans"], fontSize=6.3, fillColor=ACCENT, textAnchor="start" if value >= 0 else "end"))
    d.add(String(4, height - 8, f"Elevation and moments about {axis}–{axis} [kNm]",
                 fontName=f["bold"], fontSize=7, fillColor=INK))
    d.add(String(base_x - 2, bot - 8, "first order (dashed) · design (solid)", fontName=f["sans"],
                 fontSize=5.8, fillColor=MUTED, textAnchor="middle"))
    tag = (f"λ = {ax['lam']:.1f} ≥ λlim = {ax['lam_lim']:.1f}: slender, e\u2082 = {ax['e2']:.1f} mm"
           if ax["slender"] else f"λ = {ax['lam']:.1f} < λlim = {ax['lam_lim']:.1f}: not slender")
    d.add(String(width / 2, 1, tag, fontName=f["sans"], fontSize=6.3, fillColor=MUTED, textAnchor="middle"))
    return d


# ---------------------------------------------------------------- document

def _title_block(report, st, f, generated):
    p = report["project"]
    cells = [("PROJECT", p.get("name") or "—"), ("ELEMENT REF", p.get("ref") or "—"),
             ("ENGINEER", p.get("engineer") or "—"), ("DATE", p.get("date") or generated[:10])]
    row1 = [Paragraph(k, st["label"]) for k, _ in cells]
    row2 = [Paragraph(escape(v), st["value"]) for _, v in cells]
    basis = Paragraph("CODE BASIS: BS EN 1992-1-1 with the UK National Annex values used in <i>How to Design "
                      "Concrete Structures using Eurocode 2</i> (The Concrete Centre, 2006), Chapter 5. "
                      f"Generated {generated}.", st["small"])
    t = Table([row1, row2, [basis, "", "", ""]], colWidths=[45 * mm] * 4)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.9, INK), ("INNERGRID", (0, 0), (-1, 1), 0.4, RULE),
        ("LINEABOVE", (0, 2), (-1, 2), 0.4, RULE), ("SPAN", (0, 2), (-1, 2)),
        ("BACKGROUND", (0, 0), (-1, -1), PAPER), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _verdict(report, st):
    s = report["summary"]
    c = s["counts"]
    if c["fail"]:
        head = f"{c['fail']} CHECK{'S' if c['fail'] > 1 else ''} FAILED"
    elif c["warn"]:
        head = f"PASSED WITH {c['warn']} WARNING{'S' if c['warn'] > 1 else ''}"
    else:
        head = "ALL CHECKS PASSED"
    sub = (f"{c['pass']} passed · {c['fail']} failed · {c['warn']} warnings · {c['info']} information · "
           f"{c['na']} not applicable ({s['total']} items)")
    t = Table([[Paragraph(head, st["verdict"])], [Paragraph(sub, st["verdict_sub"])]], colWidths=[180 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), STATUS[s["verdict"]]),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (0, 0), 7),
                           ("BOTTOMPADDING", (0, -1), (-1, -1), 7)]))
    return t


def _key_results(report, st):
    der, checks = report["derived"], {c["id"]: c for c in report["checks"]}
    tiles = []
    for axis in ("y", "z"):
        c, ax = checks[f"bending_{axis}"], der["axes"][axis]
        util = "—" if c["utilisation"] is None else f"{c['utilisation']:.2f}"
        tiles.append((f"BENDING {axis}–{axis}", f"utilisation {util}", c["markup"]["result"], c["status"]))
    axial = checks["axial"]
    tiles.append(("AXIAL", f"utilisation {axial['utilisation']:.2f}", axial["markup"]["result"], axial["status"]))
    for axis in ("y", "z"):
        ax = der["axes"][axis]
        tiles.append((f"SLENDERNESS {axis}–{axis}", "slender" if ax["slender"] else "not slender",
                      to_markup(f"λ = {ax['lam']:.1f}, λlim = {ax['lam_lim']:.1f}"), "info"))
    req = [der["axes"][a]["As_req"] for a in ("y", "z") if der["axes"][a]["As_req"] is not None]
    req_text = f"As,req = {max(req):.0f} mm²" if req else "As,req: not achievable"
    tiles.append(("REINFORCEMENT", f"ρ = {100 * der['rho']:.2f} %",
                  to_markup(f"As,prov = {der['As']:.0f} mm², {req_text}"), checks["as_min"]["status"]))
    cells = []
    for label, sub, value, status in tiles:
        cells.append([Paragraph(f'{label} <font color="{STATUS_HEX[status]}">● {STATUS_LABEL[status]}</font>',
                                st["label"]),
                      _p(value, st["cellb"], markup=True), Paragraph(sub, st["small"])])
    rows = [cells[i:i + 3] for i in range(0, len(cells), 3)]
    t = Table(rows, colWidths=[60 * mm] * 3)
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, RULE), ("INNERGRID", (0, 0), (-1, -1), 0.6, RULE),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def _checks_table(report, st, f):
    rows = [[Paragraph(h, st["label"]) for h in ("#", "GROUP", "CHECK", "RESULT", "UTIL.", "STATUS")]]
    styles = []
    for i, c in enumerate(report["checks"], start=1):
        util = "" if c["utilisation"] is None else f"{c['utilisation']:.2f}"
        rows.append([Paragraph(str(i), st["cell"]), _p(c["group"], st["cell"]), _p(c["title"], st["cell"]),
                     _p(c["markup"]["result"], st["cell"], markup=True), Paragraph(util, st["cell"]),
                     _status_chip(c["status"], f)])
        styles.append(("BACKGROUND", (5, i), (5, i), STATUS_TINT[c["status"]]))
    t = Table(rows, colWidths=[8 * mm, 30 * mm, 49 * mm, 62 * mm, 13 * mm, 18 * mm], repeatRows=1)
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.8, INK), ("LINEBELOW", (0, 1), (-1, -1), 0.3, RULE),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.2),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2)] + styles))
    return t


def _calc_sheet(report, st, f):
    flow = []
    for group in report["groups"]:
        items = [c for c in report["checks"] if c["group"] == group]
        if not items:
            continue
        rows = [[Paragraph(h, st["label"]) for h in ("REF", "CALCULATION", "OUTPUT")]]
        for c in items:
            refs = "<br/>".join(
                to_markup(r["label"]) + (f' <font color="#5B6476">p.{r["page"]}</font>' if r["page"] else "")
                for r in c["refs"])
            calc = [_p(f"<b>{to_markup(c['title'])}</b>", st["cell"], markup=True)]
            calc += [_p(line, st["work"], markup=True) for line in c["markup"]["working"]]
            if c["note"]:
                calc.append(_p(f'<font color="#5B6476">Note: {c["markup"]["note"]}</font>', st["work"], markup=True))
            out = [_p(c["markup"]["result"], st["cellb"], markup=True), Spacer(1, 2), _status_chip(c["status"], f, 8.5)]
            if c["utilisation"] is not None:
                out.append(Paragraph(f"utilisation {c['utilisation']:.2f}", st["small"]))
            rows.append([_p(refs, st["small"], markup=True), calc, out])
        t = Table(rows, colWidths=[38 * mm, 104 * mm, 38 * mm], repeatRows=1)
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
                               ("LINEBELOW", (0, 1), (-1, -1), 0.3, RULE),
                               ("LINEAFTER", (0, 0), (1, -1), 0.3, RULE),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        flow += [CondPageBreak(30 * mm), Paragraph(group, st["h2"]), t]
    return flow


def build_column_pdf(report):
    f = _register_fonts()
    st = _styles(f)
    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    project = report["project"]
    header_right = " · ".join(x for x in (project.get("name"), project.get("ref")) if x) or "Column check"

    def decorate(canv, total):
        w, h = A4
        canv.saveState()
        canv.setFillColor(INK)
        canv.rect(0, h - 9 * mm, w, 9 * mm, stroke=0, fill=1)
        canv.setFillColor(colors.white)
        canv.setFont(f["cond"], 9)
        canv.drawString(15 * mm, h - 6 * mm, "EC2 ELEMENT CHECKER · COLUMN")
        canv.setFont(f["sans"], 8)
        canv.drawRightString(w - 15 * mm, h - 6 * mm, header_right[:90])
        canv.setStrokeColor(RULE)
        canv.line(15 * mm, 12 * mm, w - 15 * mm, 12 * mm)
        canv.setFillColor(MUTED)
        canv.setFont(f["sans"], 6.8)
        canv.drawString(15 * mm, 8 * mm, "Based on 'How to Design Concrete Structures using Eurocode 2' "
                                         "(The Concrete Centre, 2006). Verify with a qualified engineer.")
        canv.drawRightString(w - 15 * mm, 8 * mm, f"Page {canv.getPageNumber()} of {total}")
        canv.restoreState()

    buf = BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                          bottomMargin=17 * mm, title=f"EC2 column check {project.get('ref', '')}".strip(),
                          author=project.get("engineer") or "EC2 Element Checker",
                          subject="Column check to Eurocode 2")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame])])

    story = [
        Paragraph("Column check to Eurocode 2", st["title"]),
        Paragraph("Chapter 5 procedure (Table 1, Figures 2 and 3) of <i>How to Design Concrete Structures "
                  "using Eurocode 2</i>", st["subtitle"]),
        Spacer(1, 5 * mm), _title_block(report, st, f, generated), Spacer(1, 4 * mm),
        Paragraph("1. Overall summary", st["h1"]), _verdict(report, st), Spacer(1, 3 * mm),
        _key_results(report, st), Spacer(1, 3 * mm),
        Paragraph("Checks at a glance", st["h2"]), _checks_table(report, st, f),
    ]
    drawings = Table([[_section_drawing(report, f), _elevation_drawing(report, "y", f)],
                      [_interaction_drawing(report, "y", f), _interaction_drawing(report, "z", f)]],
                     colWidths=[90 * mm, 90 * mm])
    drawings.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, RULE), ("INNERGRID", (0, 0), (-1, -1), 0.6, RULE),
                                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story += [CondPageBreak(170 * mm), Paragraph("Drawings", st["h2"]),
              KeepTogether([drawings, Spacer(1, 2 * mm), Paragraph(
                  "Cross-section to scale (red marks a failed check on that part), design moment diagram after "
                  "Fig 4, and N–M interaction curves for the reinforcement provided with the design point "
                  "(MEd, NEd) in green when inside the curve.", st["small"])])]

    story += [CondPageBreak(60 * mm), Paragraph("2. Detailed calculations", st["h1"]),
              Paragraph("Each check follows the guide's procedure; references give the printed page of the guide "
                        "and, where useful, the clause of BS EN 1992-1-1.", st["small"])]
    story += _calc_sheet(report, st, f)

    inputs = Table([[_p(i["label"], st["cellb"]), _p(i["value"], st["cell"])] for i in report["inputs"]],
                   colWidths=[50 * mm, 130 * mm])
    inputs.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE), ("TOPPADDING", (0, 0), (-1, -1), 2),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story += [CondPageBreak(60 * mm), Paragraph("3. Inputs", st["h1"]), inputs,
              Paragraph("4. Assumptions", st["h1"])]
    story += [Paragraph(f"• {to_markup(a)}", st["body"]) for a in report["assumptions"]]
    story += [Spacer(1, 4 * mm), Paragraph(
        "This report is produced by a checking tool for education and preliminary design. It does not replace "
        "the judgement of a qualified structural engineer, who should verify the input data and results.",
        st["small"])]

    doc.build(story, canvasmaker=lambda *a, **k: _NumberedCanvas(*a, decorate=decorate, **k))
    return buf.getvalue()
