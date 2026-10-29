// Analysis results view: envelope values, figures, and analysis tables.
// Shared between the live beam form and the final report.
import { el } from "./common.js";
import { renderFigure } from "./figure-spec.js";
import { figure } from "./report-parts.js";

export const num = (v, nd = 2) =>
  v === null || v === undefined ? "—" : Number(v).toFixed(nd).replace("-", "−");

export function table(head, rows, caption) {
  return el(
    "div",
    { class: "data-wrap" },
    el(
      "table",
      { class: "data" },
      el("thead", {}, el("tr", {}, head.map((h, i) => el("th", { class: i ? "num" : "" }, h)))),
      el("tbody", {}, rows.map((r) => el("tr", {}, r.map((c, i) => el("td", { class: i ? "num" : "" }, c)))))
    ),
    caption ? el("p", { class: "data-note" }, caption) : null
  );
}

export function spec(name, fig, label) {
  const box = el("div");
  queueMicrotask(() => renderFigure(box, fig, label));
  return box;
}

export function buildAnalysisView(data, { onContinue, showContinue = false } = {}) {
  const a = data.analysis;
  const figs = data.figures || {};
  if (!a) return el("div", {});

  const wide = (title, body, caption) => {
    const f = figure(title, body, caption);
    f.classList.add("wide");
    return f;
  };

  const env = a.envelope || {};
  const sag = env.sagging || { M: 0, x: 0 };
  const hog = env.hogging || { M: 0, x: 0 };
  const vEnv = env.shear || env.V || { V: 0, x: 0 };
  const defl = env.deflection || { d: 0, x: 0 };
  const wVal = data.loads?.w ?? a.w;

  const statItem = (label, val, at) =>
    el("div", { class: "analysis-env-item" },
      el("div", { class: "k" }, label),
      el("div", { class: "v" }, val),
      at ? el("div", { class: "sub" }, `at ${at}`) : null
    );

  const envStrip = el("div", { class: "analysis-env-grid" },
    statItem("Largest sagging M⁺", `${num(sag.M)} kN·m`, `${num(sag.x)} m`),
    statItem("Largest hogging M⁻", `${num(hog.M)} kN·m`, `${num(hog.x)} m`),
    statItem("Largest |V|", `${num(Math.abs(vEnv.V))} kN`, `${num(vEnv.x)} m`),
    statItem("δmax", `${num(Math.abs(defl.d))} mm`, `${num(defl.x)} m`),
    statItem("Design line load w", wVal !== null && wVal !== undefined ? `${num(wVal)} kN/m` : "direct", null)
  );

  const figList = [];
  if (figs.loading) {
    figList.push(wide("Beam, loads and stiffness", spec("loading", figs.loading, "Beam and loads"),
      "Design loads, the dimensions between supports and loads, and the second moment of area of each part."));
  }
  if (figs.model) {
    figList.push(wide("Analytical model", spec("model", figs.model, "Analytical model"),
      "Nodes circled, elements boxed. Free degrees of freedom (indigo) are numbered first, restrained ones (violet, crossed) after them."));
  }
  if (figs.reactions) {
    figList.push(wide("Support reactions", spec("reactions", figs.reactions, "Support reactions"), null));
  }
  if (figs.diagrams) {
    figList.push(wide("Shear force and bending moment diagrams", spec("diagrams", figs.diagrams, "Shear force and bending moment"),
      "Positive shear and hogging moments are drawn above the x-axis; negative shear and sagging moments below it."));
  }
  if (figs.deflection) {
    figList.push(wide("Deflected shape", spec("deflection", figs.deflection, "Deflected shape"), null));
  }

  const rxRows = (a.reactions || []).map((r) => [
    `${r.node} · ${r.type}`,
    num(r.x),
    num(r.Ry),
    r.M === null ? "—" : num(r.M),
  ]);
  const rxTable = figure(
    "Support reactions",
    table(["Support (node)", "x (m)", "Ry (kN)", "M (kNm)"], rxRows, "Reactions upwards; moments anticlockwise."),
    null
  );

  const meRows = (a.elements || []).map((e) => [
    String(e.e),
    `${e.start}–${e.end}`,
    ...e.Q.map((v) => num(v)),
  ]);
  const meTable = figure(
    "Member end forces",
    table(["Element", "Nodes", "V1 (kN)", "M1 (kNm)", "V2 (kN)", "M2 (kNm)"], meRows, "Shears upwards and moments anticlockwise on the element ends."),
    null
  );

  const jdRows = (a.nodes || []).map((n) => [
    String(n.n),
    num(n.x),
    n.dofs.join(", "),
    n.fix[0] ? "0" : num(n.v_mm, 4),
    n.fix[1] ? "0" : num(n.theta, 6),
  ]);
  const jdTable = figure(
    "Joint displacements",
    table(["Node", "x (m)", "DOFs", "v (mm)", "θ (rad)"], jdRows, "Translations upwards and rotations anticlockwise."),
    null
  );

  const continueBlock = showContinue && onContinue ? el("div", { class: "tab-continue" },
    el("button", { type: "button", class: "btn primary", onclick: onContinue }, "Continue to design →")
  ) : null;

  return el("div", { class: "analysis-results-block" },
    el("h3", {}, "Analysis results"),
    el("p", { class: "lede", style: "font-size:14px;margin:4px 0 12px" },
      "Positive shear and hogging moments are drawn above the x-axis; negative shear and sagging moments below it."),
    envStrip,
    el("div", { class: "figures", style: "margin-top:16px" },
      ...figList,
      rxTable,
      meTable,
      jdTable
    ),
    continueBlock
  );
}
