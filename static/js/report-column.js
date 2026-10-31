// Column report: drawings and the design path.
import { el, fmt, worst } from "./common.js";
import { drawElevation, drawInteraction, drawSection, endKinds } from "./drawings.js";
import { renderFigure } from "./figure-spec.js";
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

  const colFigures = el("div", { class: "figures" },
    figure("Cross-section", sectionBox, "To scale. Parts outlined in red failed a check; point at a row below to find its part."),
    figure("Elevation and design moments", elevationBox, "First-order moments dashed, with second-order effects solid.", switcher(drawElev)),
    figure("N–M interaction about y–y", nmY, "The design point must lie inside the capacity curve."),
    figure("N–M interaction about z–z", nmZ, null));

  if (!result.plots || !result.plots.frame) {
    return colFigures;
  }

  // Frame analysis figures
  const figs = result.plots.frame.figures || result.plots.figures || {};
  const modelBox = el("div", { class: "fig-frame-model" });
  const mBox = el("div", { class: "fig-frame-m" });
  const nBox = el("div", { class: "fig-frame-n" });

  queueMicrotask(() => {
    if (figs.model) renderFigure(modelBox, figs.model, "Analytical model");
    if (figs.M) renderFigure(mBox, figs.M, "Bending moment diagram");
    if (figs.N) renderFigure(nBox, figs.N, "Axial force diagram");
  });

  // Table of design actions from the frame analysis
  const actChk = result.checks.find((c) => c.id === "design_actions_frame");
  let tableEl = null;
  if (actChk && actChk.working && actChk.working.length) {
    const rows = actChk.working.map((line) => {
      const idx = line.indexOf(":");
      if (idx !== -1) {
        return el("tr", {},
          el("td", { style: "font-weight:600;padding:4px 8px;border-bottom:1px solid var(--border-color,#e5e7eb)" }, line.slice(0, idx).trim()),
          el("td", { style: "padding:4px 8px;border-bottom:1px solid var(--border-color,#e5e7eb);text-align:right" }, line.slice(idx + 1).trim())
        );
      }
      return el("tr", {}, el("td", { colspan: "2", style: "padding:4px 8px;color:var(--text-muted,#6b7280)" }, line));
    });
    tableEl = el("table", { class: "kv doc", style: "width:100%;border-collapse:collapse;margin-top:6px" }, el("tbody", {}, ...rows));
  }

  const frameFigures = el("div", { class: "figures", style: "margin-top:14px" },
    figure("Analytical model", modelBox, "Nodes are circled, elements boxed. Highlighted member is the column being designed."),
    figure("Bending moments M (kNm)", mBox, "Moments drawn on the tension side (sagging below baseline)."),
    figure("Axial forces N (kN)", nBox, "Axial force diagram along the members (compression negative)."),
    tableEl ? figure("Design actions from frame", tableEl, "Actions taken from the frame analysis for column design.") : null
  );

  return el("div", {},
    colFigures,
    el("h2", { style: "margin:24px 0 10px" }, "Frame analysis"),
    frameFigures
  );
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
