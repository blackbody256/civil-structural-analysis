// Beam report: cross-section, the structural analysis (as in the matrix stiffness method) and the design path.
import { el, fmt, worst } from "./common.js";
import { drawBeamSection } from "./drawings.js";
import { renderFigure } from "./figure-spec.js";
import { arrow, figure, node, block, targetStatus } from "./report-parts.js";

const num = (v, nd = 2) => (v === null || v === undefined ? "—" : Number(v).toFixed(nd).replace("-", "−"));

function table(head, rows, caption) {
  return el("div", { class: "data-wrap" },
    el("table", { class: "data" },
      el("thead", {}, el("tr", {}, head.map((h, i) => el("th", { class: i ? "num" : "" }, h)))),
      el("tbody", {}, rows.map((r) => el("tr", {}, r.map((c, i) => el("td", { class: i ? "num" : "" }, c)))))),
    caption ? el("p", { class: "data-note" }, caption) : null);
}

function spec(name, fig, label) {
  const box = el("div");
  queueMicrotask(() => renderFigure(box, fig, label));
  return box;
}

function designValues(result) {
  const d = result.derived;
  const a = result.plots.analysis;
  const rows = [
    ["Largest sagging moment M+Ed", d.MEd_sag ? `${num(d.MEd_sag)} kNm` : "none", d.x_sag !== null && d.MEd_sag ? `${num(d.x_sag)} m` : ""],
    ["Largest hogging moment M−Ed", d.MEd_hog ? `${num(d.MEd_hog)} kNm` : "none", d.x_hog !== null && d.MEd_hog ? `${num(d.x_hog)} m` : ""],
    ["Largest shear VEd", d.VEd ? `${num(d.VEd)} kN` : "none", d.x_v !== null && d.VEd ? `${num(d.x_v)} m` : ""],
  ];
  if (a) rows.push(["Elastic deflection δmax", `${num(Math.abs(a.envelope.deflection.d))} mm`, `${num(a.envelope.deflection.x)} m`]);
  const body = el("div", {},
    d.w !== null ? el("p", { class: "data-lede" }, `Design line load w = ${num(d.w)} kN/m`
      + (d.w_shear !== null && Math.abs(d.w_shear - d.w) > 1e-9 ? ` for bending, ${num(d.w_shear)} kN/m for shear` : "")
      + " (G = 1.35gk, Q = 1.5qk)") : el("p", { class: "data-lede" }, "Design actions entered directly"),
    table(["Design value", "Value", "At x"], rows),
    a ? table(["Support (node)", "x (m)", "Ry (kN)", "M (kNm)"],
      a.reactions.map((r) => [`${r.node} · ${r.type}`, num(r.x), num(r.Ry), r.M === null ? "—" : num(r.M)]),
      "Reactions upwards; moments anticlockwise.") : null);
  return figure("Design values from the analysis", body, "Every non-zero value is designed for; a zero moment or shear is skipped.");
}

export function figures(state) {
  const { result } = state;
  const sectionBox = el("div", { id: "fig-section" });
  const links = result.derived.links;
  queueMicrotask(() => drawBeamSection(sectionBox, result.plots.section, {
    status: targetStatus(result.checks), linkLabel: links ? `H${links.dia} @ ${links.near}` : undefined,
  }));
  const top = el("div", { class: "figures" },
    figure("Cross-section", sectionBox, "To scale. Parts outlined in red failed a check; point at a row below to find its part."),
    designValues(result));
  const figs = result.plots.figures || {};
  const a = result.plots.analysis;
  if (!a || !figs.diagrams) return top;
  const wide = (title, body, caption) => {
    const f = figure(title, body, caption);
    f.classList.add("wide");
    return f;
  };
  return el("div", {}, top,
    el("h2", {}, "Structural analysis"),
    el("p", { class: "lede", style: "font-size:14px;margin:6px 0 12px" },
      "Matrix stiffness analysis of the beam under the design loads. Positive shears and sagging moments are drawn below the axis, negative ones above."),
    el("div", { class: "figures" },
      wide("Beam, loads and stiffness", spec("loading", figs.loading, "Beam and loads"),
        "Design loads, the dimensions between supports and loads, and the second moment of area of each part."),
      wide("Analytical model", spec("model", figs.model, "Analytical model"),
        "Nodes circled, elements boxed. Free degrees of freedom (blue) are numbered first, restrained ones (green, crossed) after them."),
      wide("Support reactions", spec("reactions", figs.reactions, "Support reactions"), null),
      wide("Shear force and bending moment diagrams", spec("diagrams", figs.diagrams, "Shear force and bending moment"),
        "Values either side of each node and load, and at the peaks; dots mark zero moment. Bold values are designed for."),
      wide("Deflected shape", spec("deflection", figs.deflection, "Deflected shape"), null),
      figure("Member end forces", table(["Element", "Nodes", "V1 (kN)", "M1 (kNm)", "V2 (kN)", "M2 (kNm)"],
        a.elements.map((e) => [String(e.e), `${e.start}–${e.end}`, ...e.Q.map((v) => num(v))]),
        "Shears upwards and moments anticlockwise on the element ends."), null),
      figure("Joint displacements", table(["Node", "x (m)", "DOFs", "v (mm)", "θ (rad)"],
        a.nodes.map((n) => [String(n.n), num(n.x), n.dofs.join(", "), n.fix[0] ? "0" : num(n.v_mm, 4),
          n.fix[1] ? "0" : num(n.theta, 6)]),
        "Translations upwards and rotations anticlockwise."), null)));
}

function faceNode(title, s, check) {
  if (!s) return node(title, "No moment of this sign: not designed for", "off");
  const status = check ? check.status : "na";
  return node(title, `M = ${fmt(s.M)} kNm · d = ${fmt(s.d, 0)} mm<br>K = ${fmt(s.K, 3)} ${s.K <= s.kp ? "≤" : ">"} K′ = ${fmt(s.kp, 3)}`
    + (check ? `<br>${check.markup.result}` : ""), status === "na" ? "on" : status);
}

export function designPath(result) {
  const d = result.derived;
  const by = Object.fromEntries(result.checks.map((c) => [c.id, c]));
  const shear = worst(["strut", "links", "leg_spacing", "long_shear"].filter((id) => by[id]).map((id) => by[id].status));
  const detailing = worst(result.checks.filter((c) => c.group === "Detailing").map((c) => c.status));
  const a = result.plots.analysis;
  const flow = [
    node("Loading", d.w !== null ? `w = 1.35·g<sub>k</sub> + 1.5·q<sub>k</sub> = ${fmt(d.w)} kN/m` : "Design actions entered"),
    arrow(),
  ];
  if (a) {
    flow.push(node("Matrix stiffness analysis", `${a.nodes.length} nodes · ${a.elements.length} element${a.elements.length > 1 ? "s" : ""}`
      + ` · reactions ${a.reactions.map((r) => fmt(r.Ry)).join(", ")} kN`), arrow());
  }
  flow.push(
    node("Design values", `M<sup>+</sup><sub>Ed</sub> = ${fmt(d.MEd_sag)} · M<sup>−</sup><sub>Ed</sub> = ${fmt(d.MEd_hog)} kNm · V<sub>Ed</sub> = ${fmt(d.VEd)} kN`),
    arrow(),
    el("div", { class: "flow-branch" },
      el("div", { class: `col ${d.sag ? "on" : "off"}` }, el("span", { class: "tag-line" }, "Sagging: bottom bars"),
        faceNode("Bottom reinforcement", d.sag, by.tension_sag)),
      el("div", { class: `col ${d.hog ? "on" : "off"}` }, el("span", { class: "tag-line" }, "Hogging: top bars"),
        faceNode("Top reinforcement", d.hog, by.tension_hog))),
    arrow(),
    node("Shear", by.links && by.links.status !== "na" ? by.links.markup.result : by.strut.markup.result,
      shear === "fail" ? "fail" : by.strut.status === "na" ? "on" : "pass"),
    arrow(),
    node("Deflection", by.deflection.markup.result, by.deflection.status === "na" ? "on" : by.deflection.status),
    arrow(),
    node("Spacing and quantity of reinforcement", detailing === "fail" ? "Some detailing rules fail" : "All detailing rules pass",
      detailing === "fail" ? "fail" : "pass"));
  return block("Design path", { open: true }, el("div", { class: "flow" }, ...flow));
}
