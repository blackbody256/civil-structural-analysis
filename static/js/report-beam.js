// Beam report: drawings and the design path.
import { el, fmt, worst } from "./common.js";
import { drawBeamElevation, drawBeamSection } from "./drawings.js";
import { arrow, block, branch, figure, node, question, targetStatus } from "./report-parts.js";

export function figures(state) {
  const { result } = state;
  const sectionBox = el("div", { id: "fig-section" });
  const elevationBox = el("div");
  const links = result.derived.links;
  queueMicrotask(() => {
    drawBeamSection(sectionBox, result.plots.section, {
      status: targetStatus(result.checks),
      linkLabel: links ? `H${links.dia} @ ${links.near}` : undefined,
    });
    drawBeamElevation(elevationBox, result.plots.elevation);
  });

  const figList = [
    figure("Cross-section", sectionBox, "To scale. Parts outlined in red failed a check; point at a row below to find its part."),
    figure("Loading, bending moment, shear and deflection", elevationBox,
      "Sagging moments and downward deflections are drawn below the axis. The dashed line marks the section checked.")
  ];

  if (result.derived.reactions && result.derived.reactions.length > 0) {
    const rxBox = el("div", { style: "padding: 4px 6px;" });
    const table = el("table", { class: "calc-sheet", style: "width: 100%; border-collapse: collapse; margin-top: 4px;" },
      el("thead", {},
        el("tr", {},
          el("th", { style: "text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line-strong);" }, "Support"),
          el("th", { style: "text-align: right; padding: 6px 8px; border-bottom: 1px solid var(--line-strong);" }, "x (m)"),
          el("th", { style: "text-align: right; padding: 6px 8px; border-bottom: 1px solid var(--line-strong);" }, "Reaction Ry (kN)"),
          el("th", { style: "text-align: right; padding: 6px 8px; border-bottom: 1px solid var(--line-strong);" }, "Reaction M (kNm)")
        )
      ),
      el("tbody", {},
        ...result.derived.reactions.map((r) => el("tr", {},
          el("td", { style: "padding: 6px 8px; font-weight: 500;" }, `Node ${r.node}`),
          el("td", { style: "text-align: right; padding: 6px 8px; font-family: var(--font-mono);" }, `${r.x.toFixed(2)}`),
          el("td", { style: "text-align: right; padding: 6px 8px; font-family: var(--font-mono); font-weight: 600;" }, `${Math.abs(r.Ry).toFixed(1)}`),
          el("td", { style: "text-align: right; padding: 6px 8px; font-family: var(--font-mono);" }, `${Math.abs(r.M).toFixed(1)}`)
        ))
      )
    );
    rxBox.appendChild(table);
    figList.push(figure("Support Reactions (Matrix Stiffness Analysis)", rxBox, "Computed from the global stiffness matrix Ku = F."));
  }

  return el("div", { class: "figures" }, ...figList);
}

export function designPath(result) {
  const d = result.derived;
  const by = Object.fromEntries(result.checks.map((c) => [c.id, c]));
  const needs = d.K > d.kp;
  const tension = by.tension;
  const shear = worst(["strut", "links", "leg_spacing", "long_shear"].filter((id) => by[id]).map((id) => by[id].status));
  const deflection = by.deflection;
  const detailing = worst(result.checks.filter((c) => c.group === "Detailing").map((c) => c.status));
  const flangedSpan = d.shape === "flanged" && d.location === "span";
  return block("Design path", { open: true }, el("div", { class: "flow" },
    node("Design actions", `M<sub>Ed</sub> = ${fmt(d.MEd)} kNm · V<sub>Ed</sub> = ${fmt(d.VEd)} kN${d.w ? ` · w = ${fmt(d.w)} kN/m` : ""}`),
    arrow(),
    node("Section", `d = ${fmt(d.d, 0)} mm${flangedSpan ? ` · b<sub>eff</sub> = ${fmt(d.beff, 0)} mm` : ""}`),
    arrow(),
    node("Bending", `K = ${fmt(d.K, 3)} · K′ = ${fmt(d.kp, 3)}`),
    arrow(),
    question(`Is K ≤ K′? ${needs ? "No" : "Yes"}`),
    arrow(),
    branch(needs,
      { tag: "Yes: tension steel only", node: node("Lever arm", needs ? "not used" : `z = ${fmt(d.z, 0)} mm`, needs ? "off" : "on") },
      { tag: "No: compression steel needed", node: node("Compression steel", needs && d.As2_req !== null
        ? `A<sub>s2,req</sub> = ${fmt(d.As2_req, 0)} mm²` : "not needed", needs ? "on" : "off") }),
    arrow(),
    node("Tension reinforcement", tension.markup.result, tension.status === "na" ? "on" : tension.status),
    arrow(),
    node("Shear", by.links && by.links.status !== "na" ? by.links.markup.result : by.strut.markup.result,
      shear === "fail" ? "fail" : "pass"),
    arrow(),
    node("Deflection", deflection.markup.result, deflection.status === "na" ? "on" : deflection.status),
    arrow(),
    node("Spacing and quantity of reinforcement", detailing === "fail" ? "Some detailing rules fail" : "All detailing rules pass",
      detailing === "fail" ? "fail" : "pass")));
}
