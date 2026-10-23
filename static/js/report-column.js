// Column report: drawings and the design path.
import { el, fmt, worst } from "./common.js";
import { drawElevation, drawInteraction, drawSection, endKinds } from "./drawings.js";
import { arrow, block, branch, figure, node, question, switcher, targetStatus } from "./report-parts.js";

export function figures(state) {
  const { result, input } = state;
  const by = Object.fromEntries(result.checks.map((c) => [c.id, c]));
  const sectionBox = el("div", { id: "fig-section" });
  const elevationBox = el("div");
  const nmY = el("div"), nmZ = el("div");
  const drawElev = (axis) => {
    const ax = result.derived.axes[axis];
    drawElevation(elevationBox, {
      l: result.derived.l, depth: ax.depth, NEd: result.derived.NEd, l0: ax.l0,
      ...endKinds(input.restraint[axis]), moments: { ...ax, axis },
    });
  };
  queueMicrotask(() => {
    drawSection(sectionBox, result.plots.section, {
      status: targetStatus(result.checks), linkLabel: `H${result.derived.links.dia} @ ${result.derived.links.near}`,
    });
    drawElev("y");
    drawInteraction(nmY, result.plots.interaction.y, { axis: "y", status: by.bending_y.status });
    drawInteraction(nmZ, result.plots.interaction.z, { axis: "z", status: by.bending_z.status });
  });
  return el("div", { class: "figures" },
    figure("Cross-section", sectionBox, "To scale. Parts outlined in red failed a check; point at a row below to find its part."),
    figure("Elevation and design moments", elevationBox, "First-order moments dashed, with second-order effects solid.", switcher(drawElev)),
    figure("N–M interaction about y–y", nmY, "The design point must lie inside the capacity curve."),
    figure("N–M interaction about z–z", nmZ, null));
}

function flow(result, axis) {
  const ax = result.derived.axes[axis];
  const by = Object.fromEntries(result.checks.map((c) => [c.id, c]));
  const bend = by[`bending_${axis}`];
  const detailing = worst(result.checks.filter((c) => c.group === "Detailing").map((c) => c.status));
  const slender = ax.slender;
  return el("div", { class: "flow" },
    node("Actions on the column", `N<sub>Ed</sub> = ${fmt(result.derived.NEd, 0)} kN · M<sub>top</sub> = ${fmt(ax.M_top)} · M<sub>bottom</sub> = ${fmt(ax.M_bottom)} kNm`),
    arrow(),
    node("Effective length", `l<sub>0</sub> = ${fmt(ax.F, 3)} × ${fmt(result.derived.l / 1000, 2)} m = ${fmt(ax.l0 / 1000, 2)} m`),
    arrow(),
    node("First-order moments", `e<sub>i</sub> = ${fmt(ax.e_i)} mm · M<sub>01</sub> = ${fmt(ax.M01)} · M<sub>02</sub> = ${fmt(ax.M02)} kNm`),
    arrow(),
    node("Slenderness", `λ = ${fmt(ax.lam)} · λ<sub>lim</sub> = ${fmt(ax.lam_lim)}`),
    arrow(),
    question(`Is λ ≥ λ<sub>lim</sub>? ${slender ? "Yes" : "No"}`),
    arrow(),
    branch(slender,
      { tag: "No: not slender", node: node("Design moment", `M<sub>Ed</sub> = M<sub>02</sub> = ${fmt(ax.M02)} kNm`, slender ? "off" : "on") },
      { tag: "Yes: nominal curvature method", node: node("Second-order moment", slender
        ? `K<sub>r</sub> = ${fmt(ax.Kr, 3)}, K<sub>φ</sub> = ${fmt(ax.Kphi, 3)}<br>e<sub>2</sub> = ${fmt(ax.e2)} mm, M<sub>2</sub> = ${fmt(ax.M2)} kNm<br>M<sub>Ed</sub> = ${fmt(ax.MEd)} kNm`
        : "not needed", slender ? "on" : "off") }),
    arrow(),
    node("Resistance", `${bend.markup.result}<br>A<sub>s,req</sub> = ${ax.As_req === null ? "not achievable" : `${fmt(ax.As_req, 0)} mm²`} · A<sub>s,prov</sub> = ${fmt(result.derived.As, 0)} mm²`, bend.status),
    arrow(),
    node("Spacing and quantity of reinforcement", detailing === "fail" ? "Some detailing rules fail" : "All detailing rules pass", detailing === "fail" ? "fail" : "pass"));
}

export function designPath(result) {
  const box = el("div");
  const draw = (axis) => box.replaceChildren(flow(result, axis));
  draw("y");
  return block("Design path", { open: true }, el("div", { style: "display:flex;margin-bottom:10px" }, switcher(draw)), box);
}
