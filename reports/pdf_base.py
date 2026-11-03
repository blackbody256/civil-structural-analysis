"""Shared layout for the downloadable reports (Structural Analysis & Design).

Set out like an engineer's calculation pad, in DejaVu Sans (bundled, so every machine lays the pages out
the same). Every sheet carries a boxed title block: the tool, the project, the element, the sheet number,
who made it and when. The check sheets are ruled into Ref | Calculation | Output columns, as on a printed
calculation pad, and the foot of each sheet names the element and the code.

Order: A Design data (the input schedule beside a 3D view of the element), B Drawings and analysis,
C Design checks, D Conclusion (verdict stamp, governing check, utilisation of every check) and E Assumptions.
"""
import datetime as dt
import math
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Group, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, KeepTogether, NextPageTemplate, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

from ec2.notation import to_markup

from .iso3d import iso_view

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "static" / "fonts"
SYSTEM_DEJAVU = Path("/usr/share/fonts/truetype/dejavu")

SIZE = 10                 # body text
INK = colors.HexColor("#13202B")
MUTED = colors.HexColor("#55626C")
RULE = colors.HexColor("#C9D6E2")         # soft pad ruling
PAD = colors.HexColor("#9FB8CF")          # the pad's column rules
PAPER = colors.HexColor("#F4F8FB")
CONCRETE = colors.HexColor("#E1E6EA")
ACCENT = colors.HexColor("#0B3A5C")       # navy: title block, headings, lines of the drawings
MARGIN = colors.HexColor("#D95319")       # orange margin rule and group numbers
BLUE = colors.HexColor("#0072BD")
STATUS_HEX = {"pass": "#1F7A33", "fail": "#C62828", "warn": "#B84300", "info": "#1565C0", "na": "#6B7378"}
STATUS = {k: colors.HexColor(v) for k, v in STATUS_HEX.items()}
STATUS_TINT = {k: colors.HexColor(v) for k, v in
               {"pass": "#E6F2E8", "fail": "#FBE6E4", "warn": "#FCEEDF", "info": "#E3ECF8", "na": "#EEF0F1"}.items()}
STATUS_LABEL = {"pass": "Pass", "fail": "Fail", "warn": "Warning", "info": "Info", "na": "N/A"}
STAMP = {"pass": "PASS", "fail": "FAIL", "warn": "CHECK", "info": "INFO", "na": "N/A"}
SEVERITY = {"fail": 4, "warn": 3, "pass": 2, "info": 1, "na": 0}

PAGE_W, PAGE_H = A4
LEFT = RIGHT = 15 * mm
BODY_W = PAGE_W - LEFT - RIGHT
TB_H = 22 * mm                          # title block height
TB_TOP = PAGE_H - 10 * mm
REF_W, OUT_W = 30 * mm, 46 * mm         # the pad's Ref and Output columns
CALC_W = BODY_W - REF_W - OUT_W

_fonts = None


def fonts():
    """Register DejaVu Sans once; returns names for regular, bold, italic and condensed bold."""
    global _fonts
    if _fonts is not None:
        return _fonts
    italic = SYSTEM_DEJAVU / "DejaVuSans-Oblique.ttf"
    files = {"Sans": FONTS / "DejaVuSans.ttf", "Sans-Bold": FONTS / "DejaVuSans-Bold.ttf",
             "Sans-Italic": italic if italic.exists() else FONTS / "DejaVuSans.ttf",
             "Sans-Cond": FONTS / "DejaVuSansCondensed-Bold.ttf"}
    for name, path in files.items():
        pdfmetrics.registerFont(TTFont(name, str(path)))
    registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans-Italic", boldItalic="Sans-Bold")
    _fonts = {"regular": "Sans", "bold": "Sans-Bold", "italic": "Sans-Italic", "cond": "Sans-Cond", "face": "DejaVu Sans"}
    return _fonts


def styles():
    f = fonts()
    base = dict(fontName=f["regular"], textColor=INK, fontSize=SIZE, leading=SIZE * 1.38)
    return {
        "title": ParagraphStyle("title", **{**base, "fontName": f["cond"], "fontSize": 18, "leading": 22, "textColor": ACCENT}),
        "subtitle": ParagraphStyle("subtitle", **{**base, "textColor": MUTED}),
        "h1": ParagraphStyle("h1", **{**base, "fontName": f["cond"], "fontSize": 12.5, "leading": 16, "spaceBefore": 8,
                                      "spaceAfter": 4, "textColor": ACCENT}),
        "h2": ParagraphStyle("h2", **{**base, "fontName": f["cond"], "fontSize": 10.5, "leading": 14, "spaceBefore": 8,
                                      "spaceAfter": 3, "textColor": ACCENT}),
        "body": ParagraphStyle("body", **base),
        "small": ParagraphStyle("small", **{**base, "fontSize": 8.5, "leading": 11}),
        "bold": ParagraphStyle("bold", **{**base, "fontName": f["bold"]}),
        "label": ParagraphStyle("label", **{**base, "fontName": f["cond"], "fontSize": 8, "leading": 10, "textColor": MUTED}),
        "muted": ParagraphStyle("muted", **{**base, "fontSize": 9, "leading": 12, "textColor": MUTED}),
        "ref": ParagraphStyle("ref", **{**base, "fontSize": 7.5, "leading": 9.5, "textColor": MUTED}),
        "refno": ParagraphStyle("refno", **{**base, "fontName": f["cond"], "fontSize": 10, "leading": 12, "textColor": ACCENT}),
        "group": ParagraphStyle("group", **{**base, "fontName": f["cond"], "fontSize": 11, "leading": 14, "textColor": ACCENT}),
        "verdict": ParagraphStyle("verdict", **{**base, "fontName": f["cond"], "fontSize": 16, "leading": 20}),
    }


class _NumberedCanvas(pdfcanvas.Canvas):
    """Canvas that knows the page count, for 'Sheet n of N'."""

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


def pdf_markup(markup):
    """Browser markup to reportlab markup: smaller, less lowered sub/superscripts."""
    return (markup.replace("<sub>", '<sub rise="22%" size="74%">')
                  .replace("<sup>", '<sup rise="38%" size="74%">'))


def para(text, style, markup=False):
    return Paragraph(pdf_markup(text if markup else to_markup(str(text))), style)


def status_text(status, style):
    return Paragraph(f'<font name="{fonts()["bold"]}" color="{STATUS_HEX[status]}">{STATUS_LABEL[status]}</font>', style)


def nice_ticks(vmax, count=5):
    if vmax <= 0:
        return [0.0, 1.0]
    raw = vmax / count
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    return [i * step for i in range(int(math.ceil(vmax / step)) + 1)]


def target_status(report):
    worst = {}
    for c in report["checks"]:
        t = c.get("target")
        if t and SEVERITY[c["status"]] > SEVERITY.get(worst.get(t, "na"), 0):
            worst[t] = c["status"]
    return worst


def _verdict(counts):
    if counts["fail"]:
        return "fail", "Not adequate", f"{counts['fail']} check{'s' if counts['fail'] > 1 else ''} fail"
    if counts["warn"]:
        return "warn", "Adequate", f"with {counts['warn']} warning{'s' if counts['warn'] > 1 else ''}"
    return "pass", "Adequate", f"all {counts['pass']} checks pass"


def _rated(report):
    return [c for c in report["checks"] if c["status"] in ("pass", "fail", "warn")
            and c["utilisation"] is not None and math.isfinite(c["utilisation"])]


# ---------------------------------------------------------------- small drawings

def stamp(status, width=17 * mm, height=6 * mm, size=7.5):
    """A rubber-stamp mark: PASS, FAIL, CHECK, INFO or N/A in a box, tilted a little."""
    f = fonts()
    d = Drawing(width, height)
    g = Group(Rect(1, 1, width - 2, height - 2, fillColor=None, strokeColor=STATUS[status], strokeWidth=1.2),
              String(width / 2, height / 2 - size * 0.36, STAMP[status], fontName=f["cond"], fontSize=size,
                     fillColor=STATUS[status], textAnchor="middle"))
    g.rotate(3)
    g.translate(0.6, -1.2)
    d.add(g)
    return d


def util_bar(u, status, width=OUT_W - 4 * mm, height=4.2 * mm):
    """Utilisation as a bar ruled in quarters, with its value."""
    f = fonts()
    d = Drawing(width, height)
    track = width - 15 * mm
    d.add(Rect(0, 1, track, 2.6, fillColor=colors.HexColor("#DCE6EF"), strokeColor=None))
    colour = STATUS["fail"] if u > 1 else STATUS["warn"] if status == "warn" else BLUE
    d.add(Rect(0, 1, track * min(max(u, 0), 1), 2.6, fillColor=colour, strokeColor=None))
    for q in (0.25, 0.5, 0.75):
        d.add(Line(track * q, 0.6, track * q, 4, strokeColor=colors.white, strokeWidth=0.6))
    d.add(String(width, 0.9, f"u = {u:.2f}", fontName=f["bold"], fontSize=7, fillColor=INK, textAnchor="end"))
    return d


def section_head(letter, title, lede=None, parts=False):
    st = styles()
    f = fonts()
    cells = [[Paragraph(f'<font color="white">{letter}</font>', ParagraphStyle("L", fontName=f["cond"], fontSize=13,
                                                                              leading=15, alignment=1)),
              Paragraph(escape(title.upper()), ParagraphStyle("T", fontName=f["cond"], fontSize=13, leading=15,
                                                              textColor=ACCENT))]]
    t = Table(cells, colWidths=[8 * mm, BODY_W - 8 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), ACCENT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LINEBELOW", (0, 0), (-1, 0), 1.4, ACCENT), ("LEFTPADDING", (1, 0), (1, 0), 6),
                           ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
    out = [Spacer(1, 2 * mm), t]
    if lede:
        out += [Spacer(1, 1.5 * mm), Paragraph(lede, st["muted"])]
    out.append(Spacer(1, 2.5 * mm))
    return out if parts else KeepTogether(out)


# ---------------------------------------------------------------- A: design data

def design_data(report, st):
    rows = [[para(i["label"], st["small"]), para(i["value"], ParagraphStyle("v", parent=st["small"], fontName=fonts()["bold"]))]
            for i in report["inputs"]]
    view = iso_view(report, 84 * mm, 96 * mm)
    sched_w = BODY_W - (88 * mm if view else 0)
    sched = Table(rows, colWidths=[sched_w * 0.44, sched_w * 0.56])
    sched.setStyle(TableStyle([("ROWBACKGROUNDS", (0, 0), (-1, -1), [PAPER, colors.white]),
                               ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                               ("LINEABOVE", (0, 0), (-1, 0), 1, ACCENT), ("LINEBELOW", (0, -1), (-1, -1), 1, ACCENT)]))
    if not view:
        return [Paragraph("Input schedule", st["h2"]), sched]
    failed = any(s == "fail" for s in target_status(report).values())
    right = [view, Spacer(1, 1 * mm), Paragraph(
        "3D view of the element. The concrete is drawn see-through to show the reinforcement"
        + ("; parts drawn red failed a check." if failed else "."), st["ref"])]
    t = Table([[[Paragraph("Input schedule", st["h2"]), sched], right]], colWidths=[sched_w + 4 * mm, 84 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (0, 0), 4 * mm), ("RIGHTPADDING", (1, 0), (1, 0), 0),
                           ("BOX", (1, 0), (1, 0), 0.6, PAD), ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F7FAFC"))]))
    return [t]


# ---------------------------------------------------------------- C: the calculation pad

def checks_pad(report, st):
    flow = []
    g = 0
    for group in report["groups"]:
        items = [c for c in report["checks"] if c["group"] == group]
        if not items:
            continue
        g += 1
        n = {s: sum(1 for c in items if c["status"] == s) for s in ("pass", "fail", "warn")}
        count = " · ".join(t for t in (n["pass"] and f"{n['pass']} pass", n["fail"] and f"{n['fail']} fail",
                                       n["warn"] and f"{n['warn']} warning{'s' if n['warn'] > 1 else ''}") if t)
        head = Table([[Paragraph(f'<font color="{MARGIN.hexval()}">C{g}</font>', st["group"]),
                       Paragraph(escape(group), st["group"]), Paragraph(count, st["ref"])]],
                     colWidths=[REF_W, CALC_W, OUT_W])
        head.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 1, ACCENT), ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                                  ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        rows, extra = [], []
        for i, c in enumerate(items):
            ref = [Paragraph(f"C{g}.{i + 1}", st["refno"])] + [para(r["label"] + (f", p. {r['page']}" if r.get("page") else ""), st["ref"])
                                                              for r in c.get("refs") or []]
            calc = [para(f"<b>{to_markup(c['title'])}</b>", st["body"], markup=True)]
            calc += [para(w, st["small"], markup=True) for w in c["markup"]["working"]]
            if c["note"]:
                calc.append(para(f'<i>{c["markup"]["note"]}</i>', st["ref"], markup=True))
            out = [para(c["markup"]["result"], ParagraphStyle("o", parent=st["small"], fontName=fonts()["bold"]), markup=True),
                   Spacer(1, 1.2 * mm), stamp(c["status"])]
            if c["utilisation"] is not None and math.isfinite(c["utilisation"]):
                out += [Spacer(1, 1 * mm), util_bar(c["utilisation"], c["status"])]
            rows.append([ref, calc, out])
            if c["status"] in ("fail", "warn"):
                extra.append(("BACKGROUND", (0, i), (-1, i), STATUS_TINT[c["status"]]))
        t = Table(rows, colWidths=[REF_W, CALC_W, OUT_W])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE),
                               ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                               ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)] + extra))
        flow += [CondPageBreak(35 * mm), head, t]
    return flow


# ---------------------------------------------------------------- D: conclusion

def big_stamp(status, word, line, width=70 * mm, height=26 * mm):
    f = fonts()
    d = Drawing(width, height)
    g = Group(Rect(3, 4, width - 6, height - 8, fillColor=None, strokeColor=STATUS[status], strokeWidth=2.2),
              Rect(5.5, 6.5, width - 11, height - 13, fillColor=None, strokeColor=STATUS[status], strokeWidth=0.8),
              String(width / 2, height / 2 - 1, word.upper(), fontName=f["cond"], fontSize=17, fillColor=STATUS[status],
                     textAnchor="middle"),
              String(width / 2, height / 2 - 8.5, line.upper(), fontName=f["cond"], fontSize=7.5, fillColor=STATUS[status],
                     textAnchor="middle"))
    g.rotate(4)
    g.translate(2, -4)
    d.add(g)
    return d


def utilisation_chart(report, width=BODY_W):
    f = fonts()
    rated = sorted(_rated(report), key=lambda c: -c["utilisation"])
    row = 5.2 * mm
    d = Drawing(width, row * len(rated) + 7 * mm)
    top = d.height - 6 * mm
    label_w, value_w = 68 * mm, 16 * mm
    track = width - label_w - value_w - 4 * mm
    for q in (0, 0.25, 0.5, 0.75, 1):
        x = label_w + track * q
        d.add(Line(x, 1, x, top + 3, strokeColor=RULE if q not in (0, 1) else PAD, strokeWidth=0.4,
                   strokeDashArray=None if q in (0, 1) else [1.5, 1.5]))
        d.add(String(x, top + 4.2, f"{q:g}", fontName=f["regular"], fontSize=6.5, fillColor=MUTED, textAnchor="middle"))
    for i, c in enumerate(rated):
        y = top - (i + 1) * row + 1.2
        u = c["utilisation"]
        colour = STATUS["fail"] if u > 1 else STATUS["warn"] if c["status"] == "warn" else BLUE
        title = c["title"] if len(c["title"]) <= 44 else c["title"][:42] + "…"
        d.add(String(0, y + 0.9, title, fontName=f["regular"], fontSize=7.5, fillColor=INK))
        d.add(Rect(label_w, y, track * min(u, 1), row * 0.55, fillColor=colour, strokeColor=None))
        d.add(String(width, y + 0.9, f"{u:.2f}", fontName=f["bold"], fontSize=7.5, fillColor=colour, textAnchor="end"))
    return d


def conclusion(report, st):
    c = report["summary"]["counts"]
    status, word, line = _verdict(c)
    rated = _rated(report)
    gov = max(rated, key=lambda x: x["utilisation"]) if rated else None
    gov_cell = [Paragraph("GOVERNING CHECK", st["label"])]
    if gov:
        colour = STATUS_HEX["fail" if gov["utilisation"] > 1 else gov["status"]]
        gov_cell += [Paragraph(f'<b>{escape(gov["title"])}</b>', ParagraphStyle("g", parent=st["body"], fontSize=11.5, leading=15)),
                     para(gov["markup"]["result"], st["small"], markup=True),
                     Paragraph(f'Utilisation <font name="{fonts()["cond"]}" size="15" color="{colour}">{gov["utilisation"]:.2f}</font>',
                               ParagraphStyle("u", parent=st["body"], leading=18))]
    else:
        gov_cell.append(Paragraph("No check has a limit to compare with.", st["body"]))
    big = ParagraphStyle("n", parent=st["body"], fontName=fonts()["cond"], fontSize=16, leading=18, alignment=2)
    tally = Table([[Paragraph(f'<font color="{STATUS_HEX[k]}">{c[k]}</font>', big), Paragraph(label, st["muted"])]
                   for k, label in (("pass", "pass"), ("fail", "fail"), ("warn", "warnings"), ("info", "for information"))],
                  colWidths=[13 * mm, 27 * mm])
    tally.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5)]))
    top = Table([[big_stamp(status, word, line), gov_cell, tally]], colWidths=[74 * mm, 66 * mm, 40 * mm])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 0.6, PAD),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    flow = [top, Spacer(1, 3 * mm)]
    if rated:
        flow += [Paragraph("Utilisation of every check with a limit, highest first", st["h2"]), utilisation_chart(report)]
    attention = [x for x in report["checks"] if x["status"] in ("fail", "warn")]
    flow.append(Paragraph("Needs attention", st["h2"]))
    if attention:
        rows = [[stamp(x["status"]), para(f"<b>{to_markup(x['title'])}</b>", st["small"], markup=True),
                 para(x["markup"]["result"], st["small"], markup=True)] for x in attention]
        t = Table(rows, colWidths=[20 * mm, 70 * mm, 90 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE)]))
        flow.append(t)
    else:
        flow.append(Paragraph(f'<font color="{STATUS_HEX["pass"]}"><b>Nothing: every check passes.</b></font>', st["body"]))
    return flow


# ---------------------------------------------------------------- the document

def build_report(report, element_title, drawings, caption, extra=None):
    """Assemble the PDF. `drawings` is a flowable (or None) for section B; `extra` is a list of flowables
    (the element's analysis) placed after it."""
    f = fonts()
    st = styles()
    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    project = report["project"]
    status, word, line = _verdict(report["summary"]["counts"])
    element_line = f"{element_title}{' · ' + project['ref'] if project.get('ref') else ''}"

    def title_block(canv, page, total):
        x0, y1 = LEFT, TB_TOP
        y0 = y1 - TB_H
        brand_w, mid_w = 56 * mm, 84 * mm
        right_w = BODY_W - brand_w - mid_w
        canv.setFillColor(ACCENT)
        canv.rect(x0, y0, brand_w, TB_H, stroke=0, fill=1)
        # the mark: a frame on a ground line
        canv.setStrokeColor(colors.white)
        canv.setLineWidth(1.6)
        canv.rect(x0 + 4 * mm, y0 + 7 * mm, 8 * mm, 8 * mm, stroke=1, fill=0)
        canv.setStrokeColor(MARGIN)
        canv.setLineWidth(1.4)
        canv.lines([(x0 + 5.6 * mm, y0 + 8.4 * mm, x0 + 5.6 * mm, y0 + 12.8 * mm), (x0 + 5.6 * mm, y0 + 12.8 * mm, x0 + 10.4 * mm, y0 + 12.8 * mm),
                    (x0 + 10.4 * mm, y0 + 12.8 * mm, x0 + 10.4 * mm, y0 + 8.4 * mm)])
        canv.setFillColor(colors.white)
        canv.setFont(f["cond"], 9.5)
        canv.drawString(x0 + 15 * mm, y0 + 13.2 * mm, "STRUCTURAL ANALYSIS")
        canv.drawString(x0 + 15 * mm, y0 + 9.4 * mm, "& DESIGN")
        canv.setFont(f["regular"], 6.5)
        canv.drawString(x0 + 4 * mm, y0 + 3 * mm, "Calculation sheet · BS EN 1992-1-1 + UK NA")
        # the grid
        canv.setStrokeColor(ACCENT)
        canv.setLineWidth(1.2)
        canv.rect(x0, y0, BODY_W, TB_H, stroke=1, fill=0)
        canv.setLineWidth(0.5)
        canv.line(x0 + brand_w, y0 + TB_H / 2, x0 + BODY_W, y0 + TB_H / 2)
        canv.line(x0 + brand_w + mid_w, y0, x0 + brand_w + mid_w, y1)

        def cell(x, y, w, label, value, colour=INK, size=9):
            canv.setFillColor(MUTED)
            canv.setFont(f["cond"], 6)
            canv.drawString(x + 2.2 * mm, y + TB_H / 2 - 3.4 * mm, label)
            canv.setFillColor(colour)
            canv.setFont(f["bold"], size)
            text = value
            while pdfmetrics.stringWidth(text, f["bold"], size) > w - 4.4 * mm and len(text) > 4:
                text = text[:-2]
            if text != value:
                text = text[:-1] + "…"
            canv.drawString(x + 2.2 * mm, y + 2 * mm, text)

        mx, rx = x0 + brand_w, x0 + brand_w + mid_w
        cell(mx, y0 + TB_H / 2, mid_w, "PROJECT", project.get("name") or "—")
        cell(mx, y0, mid_w, "ELEMENT · CALCULATION", f"{element_line} · check to Eurocode 2")
        cell(rx, y0 + TB_H / 2, right_w, "SHEET", f"{page} of {total}")
        cell(rx, y0, right_w, "MADE BY · DATE", f"{project.get('engineer') or '—'} · {project.get('date') or generated[:10]}", size=8)

    def foot(canv):
        canv.setStrokeColor(ACCENT)
        canv.setLineWidth(0.8)
        canv.line(LEFT, 12 * mm, PAGE_W - RIGHT, 12 * mm)
        canv.setFillColor(MUTED)
        canv.setFont(f["cond"], 7)
        canv.drawString(LEFT, 8.2 * mm, f"SAD · {element_line.upper()}")
        canv.drawCentredString(PAGE_W / 2, 8.2 * mm, f"RESULT: {word.upper()}, {line.upper()}")
        canv.drawRightString(PAGE_W - RIGHT, 8.2 * mm, f"PRINTED {generated}")

    def pad_rules(canv):
        top = TB_TOP - TB_H - 3 * mm
        bottom = 15 * mm
        canv.setFillColor(PAPER)
        canv.rect(LEFT, top - 5 * mm, BODY_W, 5 * mm, stroke=0, fill=1)
        canv.setFillColor(ACCENT)
        canv.setFont(f["cond"], 7.5)
        canv.drawString(LEFT + 2 * mm, top - 3.6 * mm, "REF")
        canv.drawString(LEFT + REF_W + 2 * mm, top - 3.6 * mm, "CALCULATION")
        canv.drawString(PAGE_W - RIGHT - OUT_W + 2 * mm, top - 3.6 * mm, "OUTPUT")
        canv.setStrokeColor(ACCENT)
        canv.setLineWidth(0.8)
        canv.line(LEFT, top - 5 * mm, PAGE_W - RIGHT, top - 5 * mm)
        canv.setStrokeColor(MARGIN)
        canv.setLineWidth(0.7)
        canv.line(LEFT + REF_W, top, LEFT + REF_W, bottom)
        canv.setStrokeColor(PAD)
        canv.setLineWidth(0.6)
        canv.line(PAGE_W - RIGHT - OUT_W, top, PAGE_W - RIGHT - OUT_W, bottom)

    def decorate(canv, total):
        canv.saveState()
        title_block(canv, canv.getPageNumber(), total)
        foot(canv)
        if getattr(canv, "_pad", False):
            pad_rules(canv)
        canv.restoreState()

    def mark_pad(on):
        def hook(canv, doc):
            canv._pad = on
        return hook

    buf = BytesIO()
    top_margin = PAGE_H - (TB_TOP - TB_H) + 4 * mm
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=LEFT, rightMargin=RIGHT, topMargin=top_margin,
                          bottomMargin=16 * mm, title=f"{element_title} check {project.get('ref', '')}".strip(),
                          author=project.get("engineer") or "Structural Analysis & Design",
                          subject=f"{element_title} check to Eurocode 2 (calculation sheet)")
    sheet = Frame(LEFT, doc.bottomMargin, BODY_W, PAGE_H - top_margin - doc.bottomMargin, id="sheet",
                  leftPadding=0, rightPadding=0)
    pad = Frame(LEFT, doc.bottomMargin, BODY_W, PAGE_H - top_margin - doc.bottomMargin - 6 * mm, id="pad",
                leftPadding=0, rightPadding=0, topPadding=0)
    doc.addPageTemplates([PageTemplate(id="sheet", frames=[sheet], onPage=mark_pad(False)),
                          PageTemplate(id="pad", frames=[pad], onPage=mark_pad(True))])

    story = [
        Paragraph(f"{escape(element_title)} check to Eurocode 2", st["title"]),
        Paragraph(f"Calculation sheet for {escape(element_line)}: design to BS EN 1992-1-1 with the UK National Annex, "
                  f"following <i>How to design concrete structures using Eurocode 2</i>.", st["subtitle"]),
        section_head("A", "Design data", "The inputs as entered, and the element they describe."),
        *design_data(report, st),
    ]
    if drawings is not None or extra:
        head = section_head("B", "Drawings and analysis", "The element to scale, and the analysis the design actions come from.",
                            parts=True)
        if drawings is not None:
            # the heading goes with the drawings, never alone at the foot of a sheet
            story += [KeepTogether([*head, drawings, Spacer(1, 1.5 * mm), Paragraph(caption, st["muted"])])]
        else:
            story += [CondPageBreak(90 * mm), *head]
        if extra:
            story += extra
    story += [NextPageTemplate("pad"), PageBreak(),
              section_head("C", "Design checks", "Each check in the order of the design procedure: the reference in "
                           "the guide, the working, and the output.")]
    story += checks_pad(report, st)
    story += [NextPageTemplate("sheet"), PageBreak(), section_head("D", "Conclusion")]
    story += conclusion(report, st)
    story += [CondPageBreak(50 * mm), section_head("E", "Assumptions")]
    story += [Paragraph(f"{i}. {to_markup(a)}", st["body"]) for i, a in enumerate(report["assumptions"], start=1)]
    story += [Spacer(1, 4 * mm), Paragraph(
        "Prepared with a checking tool for education and preliminary design. It does not replace the judgement of a "
        "qualified structural engineer, who should verify the input data and the results.", st["muted"])]
    doc.build(story, canvasmaker=lambda *a, **k: _NumberedCanvas(*a, decorate=decorate, **k))
    return buf.getvalue()
