"""PDF report for a pad foundation: the section with the ground pressures, the plan with the shear
perimeters, then the shared report layout."""
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, KeepTogether, Paragraph, Spacer, Table, TableStyle

from reports.beam_pdf import _table, render_figure
from reports.foundation_figures import foundation_figures
from reports.pdf_base import RULE, build_report, styles


def _boxed(spec, width=170 * mm):
    box = Table([[render_figure(spec, width=width)]], colWidths=[175 * mm])
    box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, RULE), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    return box


def design_values_section(report):
    """Section 2: the plan with the shear perimeters and the design values at the faces."""
    st = styles()
    figs = foundation_figures(report)
    d = report["derived"]
    rows = [["Design value", "Value"],
            ["Characteristic load on the ground P (with base and soil)", f"{d['P']:.1f} kN"],
            ["Largest bearing pressure", "—" if d["sls_p1"] is None else f"{d['sls_p1']:.1f} kPa"],
            ["Design column load NEd, moment MEd", f"{d['NEd']:.1f} kN, {d['MEd']:.1f} kNm"],
            ["Net design ground pressure (max, min)",
             "—" if d["uls_p1"] is None else f"{d['uls_p1']:.1f}, {d['uls_p2']:.1f} kPa"]]
    if "Mx" in d:
        rows += [["Moment at the column face, bars along L / along B", f"{d['Mx']:.1f} / {d['My']:.1f} kNm"],
                 ["Beam shear at d from the face, along L / along B", f"{d['Vx']:.1f} / {d['Vy']:.1f} kN"]]
    return [
        CondPageBreak(120 * mm),
        Paragraph("2. Plan and design values", st["h1"]),
        KeepTogether([_boxed(figs["plan"], width=150 * mm), Spacer(1, 1.5 * mm),
                      Paragraph("Plan to scale: bars both ways, beam-shear lines at d from the column faces, the "
                                "basic control perimeter at 2d and the critical punching perimeter.", st["muted"])]),
        Spacer(1, 3 * mm),
        Paragraph("Design values", st["h2"]),
        _table(rows, [120 * mm, 60 * mm], st),
    ]


def build_foundation_pdf(report):
    figs = foundation_figures(report)
    return build_report(report, "Pad foundation", _boxed(figs["section"], width=140 * mm),
                        "Section along L to scale, with the bearing pressure (characteristic) and the design ground "
                        "pressure (STR) under the base.", extra=design_values_section(report))
