"""PDF report for a slab check: the 1 m wide strip section, structural analysis or panel moments, and shared report layout."""
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, KeepTogether, Paragraph, Spacer, Table, TableStyle

from reports.beam_pdf import WIDTH, _table, render_figure
from reports.pdf_base import RULE, build_report, styles
from reports.slab_figures import slab_figures, strip_figure


def one_way_analysis_section(report):
    """Section 2 of the PDF for a one-way slab: matrix stiffness analysis."""
    data = report["plots"].get("analysis")
    if not data:
        return None
    st = styles()
    figs = slab_figures(report)

    def block(title, spec, caption):
        return KeepTogether([
            Paragraph(title, st["h2"]),
            render_figure(spec),
            Spacer(1, 1.5 * mm),
            Paragraph(caption, st["muted"]),
        ])

    flow = [
        CondPageBreak(120 * mm),
        Paragraph("2. Structural analysis", st["h1"]),
        Paragraph("Matrix stiffness analysis of the 1 m wide slab strip under the design loads. Positive shear and "
                  "hogging moments are drawn above the x-axis; negative shear and sagging moments below it.", st["body"]),
        block("Strip, loads and stiffness", figs["loading"], "Design loads on the 1 m wide strip, with the dimensions "
              "between supports and loads, and the second moment of area of each part."),
        block("Analytical model", figs["model"], "Nodes are circled and elements boxed. Degrees of freedom: "
              "free ones (blue) numbered first, restrained ones (green, crossed) after them."),
        block("Support reactions", figs["reactions"], "Reactions from the analysis: forces upwards, moments "
              "with the sense drawn."),
        block("Shear force and bending moment diagrams", figs["diagrams"], "Values at the nodes and loads, "
              "and at the peaks; dots mark zero moment. Bold values are the ones designed for."),
        block("Deflected shape", figs["deflection"], "Elastic deflection, for information."),
    ]

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

    flow += [
        KeepTogether([Paragraph("Support reactions", st["h2"]),
                      _table(rx, [36 * mm, 24 * mm, 30 * mm, 30 * mm, 30 * mm], st)]),
        KeepTogether([Paragraph("Member end forces", st["h2"]),
                      _table(me, [22 * mm, 22 * mm, 30 * mm, 32 * mm, 30 * mm, 32 * mm], st),
                      Paragraph("Shears upwards and moments anticlockwise on the element ends.", st["muted"])]),
        KeepTogether([Paragraph("Joint displacements", st["h2"]),
                      _table(jd, [22 * mm, 26 * mm, 26 * mm, 40 * mm, 40 * mm], st),
                      Paragraph("Translations upwards and rotations anticlockwise, in the directions of the "
                                "degrees of freedom.", st["muted"])]),
    ]
    return flow


def two_way_analysis_section(report):
    """Section 2 of the PDF for a two-way slab: panel plan and moment coefficients."""
    panel = report["plots"].get("panel")
    if not panel:
        return None
    st = styles()
    figs = slab_figures(report)

    flow = [
        CondPageBreak(120 * mm),
        Paragraph("2. Panel analysis and moments", st["h1"]),
        Paragraph("Two-way spanning rectangular slab supported on four edges with restrained corners. "
                  "Bending moments and shears calculated using tabulated elastic bending coefficients with corner restraint.", st["body"]),
    ]
    if "panel" in figs:
        lx_val = panel.get("lx", 0)
        ly_val = panel.get("ly", 0)
        ratio = ly_val / lx_val if lx_val else 1.0
        label = panel.get("case", {}).get("label", "")
        flow.append(KeepTogether([
            Paragraph("Panel plan and moment envelope", st["h2"]),
            render_figure(figs["panel"], width=170 * mm),
            Spacer(1, 1.5 * mm),
            Paragraph(f"Plan view of panel ({lx_val:.2f} m × {ly_val:.2f} m, ly/lx = {ratio:.2f}) — {label}. "
                      "Continuous edges hatched, moments per metre width.", st["muted"]),
        ]))

    coeffs = panel.get("coefficients") or {}
    moms = panel.get("moments") or {}

    rows = [
        ["Span direction", "Location", "Boundary condition", "Coeff. β", "MEd (kNm/m)"],
        ["Short span (lx)", "Mid-span (bottom x)", "Sagging span moment",
         f"{coeffs.get('bsx_mid', 0):.4f}", f"{moms.get('msx_mid', 0):.2f}"],
        ["Short span (lx)", "Continuous edge (top x)",
         "Top/bottom long edges: " + ("Continuous" if coeffs.get("bsx_sup") is not None else "Discontinuous"),
         f"{coeffs.get('bsx_sup', 0):.4f}" if coeffs.get("bsx_sup") is not None else "—",
         f"{moms.get('msx_sup', 0):.2f}" if coeffs.get("bsx_sup") is not None else "—"],
        ["Long span (ly)", "Mid-span (bottom y)", "Sagging span moment",
         f"{coeffs.get('bsy_mid', 0):.4f}", f"{moms.get('msy_mid', 0):.2f}"],
        ["Long span (ly)", "Continuous edge (top y)",
         "Left/right short edges: " + ("Continuous" if coeffs.get("bsy_sup") is not None else "Discontinuous"),
         f"{coeffs.get('bsy_sup', 0):.4f}" if coeffs.get("bsy_sup") is not None else "—",
         f"{moms.get('msy_sup', 0):.2f}" if coeffs.get("bsy_sup") is not None else "—"],
    ]
    flow.append(KeepTogether([
        Paragraph("Bending moment coefficients and design moments", st["h2"]),
        _table(rows, [35 * mm, 45 * mm, 50 * mm, 25 * mm, 25 * mm], st),
        Paragraph("Design moments m = β · n · lx² per metre width.", st["muted"]),
    ]))

    shears = panel.get("shears") or {}
    sh_rows = [
        ["Action", "Symbol", "Value", "Unit"],
        ["Design shear force", "VEd", f"{shears.get('VEd', 0):.2f}", "kN/m"],
        ["Design shear stress", "vEd", f"{shears.get('vEd', 0):.3f}", "MPa"],
        ["Concrete shear resistance", "vRd,c", f"{shears.get('vRd_c', 0):.3f}", "MPa"],
    ]
    flow.append(KeepTogether([
        Paragraph("Shear actions and resistance", st["h2"]),
        _table(sh_rows, [60 * mm, 30 * mm, 45 * mm, 25 * mm], st),
        Paragraph(f"Shear basis: {shears.get('basis', '')}.", st["muted"]),
    ]))
    return flow


def build_slab_pdf(report):
    """Build the complete PDF report for a slab check."""
    sec_data = report["plots"].get("section")
    if sec_data:
        strip_fig = strip_figure(sec_data)
        dwg = render_figure(strip_fig, width=170 * mm)
        sec = Table([[dwg]], colWidths=[175 * mm])
        sec.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, RULE), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        caption = "1 m wide design strip cross-section to scale."
    else:
        sec = None
        caption = ""

    is_one_way = report.get("derived", {}).get("slab_type") == "one_way" or bool(report.get("plots", {}).get("analysis"))
    extra = one_way_analysis_section(report) if is_one_way else two_way_analysis_section(report)
    return build_report(report, "Slab", sec, caption, extra=extra)
