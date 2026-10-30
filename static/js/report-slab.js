// Slab report: 1 m wide strip cross-section, structural analysis or panel moments, and design path.
import { el, fmt, worst } from "./common.js";
import { drawSlabSection } from "./drawings.js";
import { buildAnalysisView, num, spec, table } from "./beam-analysis-view.js";
import { arrow, block, figure, node, targetStatus } from "./report-parts.js";

function oneWayDesignValues(result) {
  const d = result.derived || {};
  const a = result.plots?.analysis;
  const rows = [
    ["Largest sagging moment M+Ed", d.MEd_sag ? `${num(d.MEd_sag)} kNm/m` : "none", d.x_sag !== null && d.MEd_sag ? `${num(d.x_sag)} m` : ""],
    ["Largest hogging moment M−Ed", d.MEd_hog ? `${num(d.MEd_hog)} kNm/m` : "none", d.x_hog !== null && d.MEd_hog ? `${num(d.x_hog)} m` : ""],
    ["Largest shear VEd", d.VEd ? `${num(d.VEd)} kN/m` : "none", d.x_v !== null && d.VEd ? `${num(d.x_v)} m` : ""],
  ];
  if (a && a.envelope?.deflection) {
    rows.push(["Elastic deflection δmax", `${num(Math.abs(a.envelope.deflection.d))} mm`, `${num(a.envelope.deflection.x)} m`]);
  }
  const body = el("div", {},
    a && a.w !== null ? el("p", { class: "data-lede" }, `Design strip load w = ${num(a.w)} kN/m (G = 1.35·gk, Q = 1.5·qk)`)
      : el("p", { class: "data-lede" }, "Design actions per metre width"),
    table(["Design value", "Value", "At x"], rows),
    a && a.reactions ? table(["Support (node)", "x (m)", "Ry (kN)", "M (kNm)"],
      a.reactions.map((r) => [`${r.node} · ${r.type}`, num(r.x), num(r.Ry), r.M === null ? "—" : num(r.M)]),
      "Reactions upwards per metre width.") : null);
  return figure("Design values from the analysis", body, "Every non-zero value is designed for; a zero moment or shear is skipped.");
}

function twoWayDesignValues(result) {
  const p = result.plots?.panel || {};
  const moms = p.moments || {};
  const coeffs = p.coefficients || {};
  const shears = p.shears || {};
  const ratio = p.lx ? p.ly / p.lx : 1.0;
  const rows = [
    ["Short span (lx) mid-span msx,mid", `${num(moms.msx_mid)} kNm/m`, `β = ${num(coeffs.bsx_mid, 4)}`],
    ["Short span continuous edge msx,sup", coeffs.bsx_sup !== null && coeffs.bsx_sup !== undefined ? `${num(moms.msx_sup)} kNm/m` : "discontinuous", coeffs.bsx_sup !== null && coeffs.bsx_sup !== undefined ? `β = ${num(coeffs.bsx_sup, 4)}` : "—"],
    ["Long span (ly) mid-span msy,mid", `${num(moms.msy_mid)} kNm/m`, `β = ${num(coeffs.bsy_mid, 4)}`],
    ["Long span continuous edge msy,sup", coeffs.bsy_sup !== null && coeffs.bsy_sup !== undefined ? `${num(moms.msy_sup)} kNm/m` : "discontinuous", coeffs.bsy_sup !== null && coeffs.bsy_sup !== undefined ? `β = ${num(coeffs.bsy_sup, 4)}` : "—"],
    ["Design shear force VEd", `${num(shears.VEd)} kN/m`, `${shears.basis || ""}`],
    ["Design shear stress vEd", `${num(shears.vEd, 3)} MPa`, `vRd,c = ${num(shears.vRd_c, 3)} MPa`],
  ];
  const body = el("div", {},
    el("p", { class: "data-lede" }, `Two-way slab panel (${num(p.lx)} m × ${num(p.ly)} m, ly/lx = ${num(ratio)}) — ${p.case?.label || ""}`),
    table(["Action / Location", "Value", "Notes / Coefficient"], rows)
  );
  return figure("Design moments and shears", body, "Moments and shears per metre width from Table 8 coefficients.");
}

export function figures(state) {
  const { result } = state;
  const isTwoWay = result.derived?.slab_type === "two_way" || !!result.plots?.panel;

  const sectionBox = el("div", { id: "fig-section" });
  queueMicrotask(() => drawSlabSection(sectionBox, result.plots?.section, {
    status: targetStatus(result.checks),
  }));

  const top = el("div", { class: "figures" },
    figure("1 m strip cross-section", sectionBox, "Cross-section to scale. Bar callouts show size and spacing."),
    isTwoWay ? twoWayDesignValues(result) : oneWayDesignValues(result)
  );

  const figs = result.plots?.figures || {};
  if (isTwoWay) {
    if (!figs.panel) return top;
    const panelWrap = figure(
      "Two-way panel plan",
      spec("panel", figs.panel, "Two-way slab panel plan"),
      "Plan view to scale with continuous edges hatched, direction arrows, and moments."
    );
    panelWrap.classList.add("wide");
    return el("div", {}, top, el("h2", {}, "Panel moments"), el("div", { class: "figures" }, panelWrap));
  } else {
    const a = result.plots?.analysis;
    if (!a || !figs.diagrams) return top;
    return el("div", {}, top,
      el("h2", {}, "Structural analysis"),
      buildAnalysisView({ analysis: a, figures: figs, loads: result.plots.loads }, { showContinue: false })
    );
  }
}

export function designPath(result) {
  const isTwoWay = result.derived?.slab_type === "two_way" || !!result.plots?.panel;
  const by = Object.fromEntries(result.checks.map((c) => [c.id, c]));
  const detailing = worst(result.checks.filter((c) => c.group === "Detailing").map((c) => c.status));
  const shear = by.shear ? by.shear.status : "na";
  const defl = result.checks.find((c) => c.group === "Deflection");
  const deflStatus = defl ? defl.status : "na";

  const flow = [];
  if (isTwoWay) {
    const p = result.plots?.panel || {};
    const ratio = p.lx ? p.ly / p.lx : 1.0;
    flow.push(
      node("Loading", "gk + sw, qk (area load)"),
      arrow(),
      node("Table 8 coefficients", `${p.case?.label || "Two-way panel"}<br>ly/lx = ${num(ratio)}`),
      arrow(),
      node("Design values", `msx,mid = ${num(p.moments?.msx_mid)} · msy,mid = ${num(p.moments?.msy_mid)}<br>VEd = ${num(p.shears?.VEd)} kN/m`),
      arrow()
    );
  } else {
    const a = result.plots?.analysis;
    const d = result.derived || {};
    flow.push(
      node("Loading", "1 m strip load: 1.35·gk + 1.5·qk"),
      arrow()
    );
    if (a) {
      flow.push(node("Strip analysis (pattern loading)", `${a.nodes.length} nodes · envelope over load cases`), arrow());
    }
    flow.push(
      node("Design values", `M<sup>+</sup><sub>Ed</sub> = ${num(d.MEd_sag)} · M<sup>−</sup><sub>Ed</sub> = ${num(d.MEd_hog)} kNm/m<br>V<sub>Ed</sub> = ${num(d.VEd)} kN/m`),
      arrow()
    );
  }

  const cBx = by.bending_bottom_x;
  const cTx = by.bending_top_x;
  const cBy = by.bending_bottom_y;
  const cTy = by.bending_top_y;

  const barNode = (title, c) => {
    if (!c || c.status === "na") return node(title, "Not applicable (no moment)", "off");
    return node(title, c.markup?.result || c.result || "", c.status);
  };

  flow.push(
    el("div", { class: "flow-branch" },
      el("div", { class: "col on" }, el("span", { class: "tag-line" }, "Bottom x (main)"), barNode("Bottom x", cBx)),
      el("div", { class: `col ${cTx && cTx.status !== "na" ? "on" : "off"}` }, el("span", { class: "tag-line" }, "Top x (hogging)"), barNode("Top x", cTx))
    ),
    arrow(),
    el("div", { class: "flow-branch" },
      el("div", { class: "col on" }, el("span", { class: "tag-line" }, isTwoWay ? "Bottom y (span)" : "Bottom y (distribution)"), barNode("Bottom y", cBy)),
      el("div", { class: `col ${cTy && cTy.status !== "na" ? "on" : "off"}` }, el("span", { class: "tag-line" }, "Top y (hogging)"), barNode("Top y", cTy))
    ),
    arrow(),
    node("Shear", by.shear ? by.shear.markup?.result || by.shear.result : "Shear check", shear),
    arrow(),
    node("Deflection", defl ? defl.markup?.result || defl.result : "Span/depth check", deflStatus),
    arrow(),
    node("Detailing", detailing === "fail" ? "Some detailing checks failed" : "All detailing checks pass", detailing === "fail" ? "fail" : "pass")
  );

  return block("Design path", { open: true }, el("div", { class: "flow" }, ...flow));
}
