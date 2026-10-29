"""Shared layout for the downloadable element reports (reportlab).

Reports are set in Times New Roman at 12 pt. When Times New Roman is not installed the
bundled Liberation Serif is used: it has the same letter widths, so pages lay out the same.

Order: overall summary (title block, verdict, checks at a glance, drawings), then the
calculation sheet (calculation and result), the inputs and the assumptions.
"""
import datetime as dt
import math
from html import escape
from io import BytesIO
from pathlib import Path

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

ROOT = Path(__file__).resolve().parent.parent
BUNDLED = ROOT / "static" / "fonts" / "liberation"
# (regular, bold, italic, bold italic) for Times New Roman on Linux, Windows and macOS
TIMES_CANDIDATES = [
    [Path("/usr/share/fonts/truetype/msttcorefonts") / f for f in
     ("Times_New_Roman.ttf", "Times_New_Roman_Bold.ttf", "Times_New_Roman_Italic.ttf", "Times_New_Roman_Bold_Italic.ttf")],
    [Path("C:/Windows/Fonts") / f for f in ("times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf")],
    [Path("/System/Library/Fonts/Supplemental") / f for f in
     ("Times New Roman.ttf", "Times New Roman Bold.ttf", "Times New Roman Italic.ttf", "Times New Roman Bold Italic.ttf")],
]
LIBERATION = [BUNDLED / f for f in ("LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf",
                                    "LiberationSerif-Italic.ttf", "LiberationSerif-BoldItalic.ttf")]

SIZE = 12                 # body text, as required for the reports
INK = colors.HexColor("#192329")
MUTED = colors.HexColor("#5A656B")
RULE = colors.HexColor("#DCD9D2")
PAPER = colors.HexColor("#F3EFE9")
CONCRETE = colors.HexColor("#ECE6DB")
ACCENT = colors.HexColor("#1E6479")
STATUS_HEX = {"pass": "#2B7440", "fail": "#B33830", "warn": "#8F5D0A", "info": "#48658B", "na": "#767D82"}
STATUS = {k: colors.HexColor(v) for k, v in STATUS_HEX.items()}
STATUS_TINT = {k: colors.HexColor(v) for k, v in
               {"pass": "#E4EFE6", "fail": "#F8E5E2", "warn": "#F6ECD9", "info": "#E6ECF3", "na": "#ECE9E4"}.items()}
STATUS_LABEL = {"pass": "Pass", "fail": "Fail", "warn": "Warning", "info": "Info", "na": "N/A"}
SEVERITY = {"fail": 4, "warn": 3, "pass": 2, "info": 1, "na": 0}

_fonts = None


def fonts():
    """Register the serif family once; returns names for regular, bold and italic."""
    global _fonts
    if _fonts is not None:
        return _fonts
    files = next((c for c in TIMES_CANDIDATES if all(p.exists() for p in c)), LIBERATION)
    names = ("Serif", "Serif-Bold", "Serif-Italic", "Serif-BoldItalic")
    for name, path in zip(names, files):
        pdfmetrics.registerFont(TTFont(name, str(path)))
    registerFontFamily("Serif", normal="Serif", bold="Serif-Bold", italic="Serif-Italic", boldItalic="Serif-BoldItalic")
    _fonts = {"regular": "Serif", "bold": "Serif-Bold", "italic": "Serif-Italic",
              "face": "Times New Roman" if files is not LIBERATION else "Liberation Serif"}
    return _fonts


def styles():
    f = fonts()
    base = dict(fontName=f["regular"], textColor=INK, fontSize=SIZE, leading=SIZE * 1.3)
    return {
        "title": ParagraphStyle("title", **{**base, "fontName": f["bold"], "fontSize": 18, "leading": 22}),
        "subtitle": ParagraphStyle("subtitle", **{**base, "textColor": MUTED}),
        "h1": ParagraphStyle("h1", **{**base, "fontName": f["bold"], "fontSize": 14, "leading": 18,
                                      "spaceBefore": 12, "spaceAfter": 6}),
        "h2": ParagraphStyle("h2", **{**base, "fontName": f["bold"], "spaceBefore": 10, "spaceAfter": 4,
                                      "textColor": ACCENT}),
        "body": ParagraphStyle("body", **base),
        "bold": ParagraphStyle("bold", **{**base, "fontName": f["bold"]}),
        "label": ParagraphStyle("label", **{**base, "fontName": f["bold"], "fontSize": 10, "leading": 12,
                                            "textColor": MUTED}),
        "muted": ParagraphStyle("muted", **{**base, "textColor": MUTED}),
        "verdict": ParagraphStyle("verdict", **{**base, "fontName": f["bold"], "fontSize": 16, "leading": 20,
                                                "textColor": colors.white}),
        "verdict_sub": ParagraphStyle("verdict_sub", **{**base, "textColor": colors.white}),
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


def pdf_markup(markup):
    """Browser markup to reportlab markup: smaller, less lowered sub/superscripts."""
    return (markup.replace("<sub>", '<sub rise="22%" size="74%">')
                  .replace("<sup>", '<sup rise="38%" size="74%">'))


def para(text, style, markup=False):
    return Paragraph(pdf_markup(text if markup else to_markup(str(text))), style)


def status_text(status, style):
    return Paragraph(f'<font name="{fonts()["bold"]}" color="{STATUS_HEX[status]}">{STATUS_LABEL[status]}</font>',
                     style)


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


# ---------------------------------------------------------------- building blocks

def title_block(report, st, generated):
    p = report["project"]
    cells = [("Project", p.get("name") or "—"), ("Element reference", p.get("ref") or "—"),
             ("Engineer", p.get("engineer") or "—"), ("Date", p.get("date") or generated[:10])]
    t = Table([[Paragraph(k, st["label"]) for k, _ in cells],
               [Paragraph(escape(v), st["bold"]) for _, v in cells],
               [Paragraph(f"Code basis: BS EN 1992-1-1 with the UK National Annex. Generated {generated}.",
                          st["muted"]), "", "", ""]],
              colWidths=[45 * mm] * 4)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.9, INK), ("INNERGRID", (0, 0), (-1, 1), 0.4, RULE),
        ("LINEABOVE", (0, 2), (-1, 2), 0.4, RULE), ("SPAN", (0, 2), (-1, 2)),
        ("BACKGROUND", (0, 0), (-1, -1), PAPER), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def verdict(report, st):
    s = report["summary"]
    c = s["counts"]
    if c["fail"]:
        head = f"Not adequate: {c['fail']} check{'s' if c['fail'] > 1 else ''} fail"
    elif c["warn"]:
        head = f"Adequate, with {c['warn']} warning{'s' if c['warn'] > 1 else ''}"
    else:
        head = f"Adequate: all {c['pass']} checks pass"
    sub = (f"{c['pass']} pass · {c['fail']} fail · {c['warn']} warnings · {c['info']} for information · "
           f"{c['na']} not applicable")
    t = Table([[Paragraph(head, st["verdict"])], [Paragraph(sub, st["verdict_sub"])]], colWidths=[180 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), STATUS[s["verdict"]]),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (0, 0), 8),
                           ("BOTTOMPADDING", (0, -1), (-1, -1), 8)]))
    return t


def governing(report, st):
    rated = [c for c in report["checks"] if c["status"] in ("pass", "fail", "warn")
             and c["utilisation"] is not None and math.isfinite(c["utilisation"])]
    if not rated:
        return Spacer(1, 1)
    gov = max(rated, key=lambda c: c["utilisation"])
    colour = STATUS_HEX["fail" if gov["utilisation"] > 1 else gov["status"]]
    return Paragraph(f'Governing check: <b>{escape(gov["title"])}</b>, utilisation '
                     f'<font color="{colour}"><b>{gov["utilisation"]:.2f}</b></font>', st["body"])


def checks_table(report, st):
    head = [Paragraph(h, st["label"]) for h in ("No.", "Check", "Result", "Utilisation", "Status")]
    rows, extra = [head], []
    for i, c in enumerate(report["checks"], start=1):
        util = "" if c["utilisation"] is None else f"{c['utilisation']:.2f}"
        rows.append([Paragraph(str(i), st["body"]), para(c["title"], st["body"]),
                     para(c["markup"]["result"], st["body"], markup=True), Paragraph(util, st["body"]),
                     status_text(c["status"], st["body"])])
        if c["status"] in ("fail", "warn"):
            extra.append(("BACKGROUND", (0, i), (-1, i), STATUS_TINT[c["status"]]))
    t = Table(rows, colWidths=[11 * mm, 58 * mm, 66 * mm, 23 * mm, 22 * mm], repeatRows=1)
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.8, INK), ("LINEBELOW", (0, 1), (-1, -1), 0.3, RULE),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)] + extra))
    return t


def calc_sheet(report, st):
    """Calculation sheet: one table per group with the working and the result."""
    flow = []
    for group in report["groups"]:
        items = [c for c in report["checks"] if c["group"] == group]
        if not items:
            continue
        rows = [[Paragraph("Calculation", st["label"]), Paragraph("Result", st["label"])]]
        for c in items:
            calc = [para(f"<b>{to_markup(c['title'])}</b>", st["body"], markup=True)]
            calc += [para(line, st["body"], markup=True) for line in c["markup"]["working"]]
            if c["note"]:
                calc.append(para(f'<i>Note: {c["markup"]["note"]}</i>', st["muted"], markup=True))
            out = [para(c["markup"]["result"], st["bold"], markup=True), Spacer(1, 3), status_text(c["status"], st["body"])]
            if c["utilisation"] is not None:
                out.append(Paragraph(f"Utilisation {c['utilisation']:.2f}", st["muted"]))
            rows.append([calc, out])
        t = Table(rows, colWidths=[128 * mm, 52 * mm], repeatRows=1)
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
                               ("LINEBELOW", (0, 1), (-1, -1), 0.3, RULE),
                               ("LINEAFTER", (0, 0), (0, -1), 0.3, RULE),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        flow += [CondPageBreak(40 * mm), Paragraph(escape(group), st["h2"]), t]
    return flow


def build_report(report, element_title, drawings, caption, extra=None):
    """Assemble the PDF. `drawings` is a flowable (or None) shown after the summary; `extra` is a
    list of flowables (an analysis section, say) placed before the calculations."""
    f = fonts()
    st = styles()
    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    project = report["project"]
    header_right = f"{element_title} check to Eurocode 2"

    def decorate(canv, total):
        w, h = A4
        canv.saveState()
        canv.setFillColor(INK)
        canv.rect(0, h - 9 * mm, w, 9 * mm, stroke=0, fill=1)
        canv.setFillColor(colors.white)
        canv.setFont(f["bold"], 10)
        canv.drawString(15 * mm, h - 6.2 * mm, f"EC2 Checker · {element_title}")
        canv.setFont(f["regular"], 10)
        canv.drawRightString(w - 15 * mm, h - 6.2 * mm, header_right[:80])
        canv.setStrokeColor(RULE)
        canv.line(15 * mm, 12 * mm, w - 15 * mm, 12 * mm)
        canv.setFillColor(MUTED)
        canv.setFont(f["regular"], 9)
        canv.drawString(15 * mm, 8 * mm, "Results to be verified by a qualified structural engineer.")
        canv.drawRightString(w - 15 * mm, 8 * mm, f"Page {canv.getPageNumber()} of {total}")
        canv.restoreState()

    buf = BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                          bottomMargin=17 * mm,
                          title=f"{element_title} check {project.get('ref', '')}".strip(),
                          author=project.get("engineer") or "EC2 Checker",
                          subject=f"{element_title} check to Eurocode 2")
    doc.addPageTemplates([PageTemplate(id="page", frames=[
        Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")])])

    story = [
        Paragraph(f"{element_title} check to Eurocode 2", st["title"]),
        Paragraph("Design check to BS EN 1992-1-1 with the UK National Annex", st["subtitle"]),
        Spacer(1, 5 * mm), title_block(report, st, generated), Spacer(1, 4 * mm),
        Paragraph("1. Overall summary", st["h1"]), verdict(report, st), Spacer(1, 3 * mm),
        governing(report, st), Spacer(1, 3 * mm),
        Paragraph("Checks at a glance", st["h2"]), checks_table(report, st),
    ]
    if drawings is not None:
        story += [CondPageBreak(175 * mm), Paragraph("Drawings", st["h2"]),
                  KeepTogether([drawings, Spacer(1, 2 * mm), Paragraph(caption, st["muted"])])]
    if extra:
        story += extra
    story += [CondPageBreak(60 * mm), Paragraph(f"{3 if extra else 2}. Calculations", st["h1"])]
    story += calc_sheet(report, st)
    inputs = Table([[para(i["label"], st["bold"]), para(i["value"], st["body"])] for i in report["inputs"]],
                   colWidths=[60 * mm, 120 * mm])
    inputs.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE), ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    n = 4 if extra else 3
    story += [CondPageBreak(60 * mm), Paragraph(f"{n}. Inputs", st["h1"]), inputs,
              Paragraph(f"{n + 1}. Assumptions", st["h1"])]
    story += [Paragraph(f"• {to_markup(a)}", st["body"]) for a in report["assumptions"]]
    story += [Spacer(1, 4 * mm), Paragraph(
        "This report is produced by a checking tool for education and preliminary design. It does not replace "
        "the judgement of a qualified structural engineer, who should verify the input data and results.",
        st["muted"])]
    doc.build(story, canvasmaker=lambda *a, **k: _NumberedCanvas(*a, decorate=decorate, **k))
    return buf.getvalue()
