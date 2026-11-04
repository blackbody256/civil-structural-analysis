// Slab form: Analysis, Design and Report tabs for solid one-way and two-way slabs and ribbed slabs.
import { downloadBlob, el, failureText, getJSON, keysFor, postJSON, statusDot, store } from "./common.js";
import { BeamCanvas, resizeModel } from "./beam-canvas.js";
import { CanvasEditor } from "./canvas-editor.js";
import { drawSlabSection, s } from "./drawings.js";
import { renderFigure } from "./figure-spec.js";
import { fitFrame, formErrors, getPath, option, setPath, setupFilesMenu, setupSections } from "./form-kit.js";
import { buildAnalysisView, designValues, num, spec, table } from "./beam-analysis-view.js";

const KEYS = keysFor("slab");
const PROJECT = { name: "", ref: "", engineer: "", date: "" };
const MATERIALS = { concrete: "C30/37", fyk: 500, ductility: "B", dg: 20, gamma_c: 1.5, gamma_s: 1.15, alpha_cc: 0.85 };
const STIFF = { E_method: "concrete", E: 33 };

export const EXAMPLES = {
  one_way: {
    project: { ...PROJECT },
    slab: { type: "one_way", h: 175 },
    materials: { ...MATERIALS },
    span: {
      l: 13.5, preset: "three_spans",
      supports: [
        { x: 0, type: "pin" },
        { x: 4.5, type: "roller" },
        { x: 9.0, type: "roller" },
        { x: 13.5, type: "roller" },
      ],
    },
    panel: {
      lx: 5.0, ly: 6.0,
      edges: { top: "continuous", bottom: "continuous", left: "continuous", right: "continuous" },
    },
    reinforcement: {
      bottom_x_dia: 12, bottom_x_s: 200,
      bottom_y_dia: 10, bottom_y_s: 300,
      top_x_dia: 12, top_x_s: 200,
      top_y_dia: "none", top_y_s: 200,
      cover: 25, delta_c_dev: 10,
    },
    actions: {
      mode: "analysis", gk: 1.5, qk: 2.5, self_weight: true, category: "B",
      loads: [], pattern: true, partitions: true,
      M_sag: 0, M_hog: 0, VEd: 0,
    },
    stiffness: { ...STIFF },
    durability: { exposure: "XC1", cement_group: "All", fire_period: "R60" },
  },
  one_way_wrong: {
    project: { ...PROJECT },
    slab: { type: "one_way", h: 125 },
    materials: { ...MATERIALS, concrete: "C25/30" },
    span: {
      l: 13.5, preset: "three_spans",
      supports: [
        { x: 0, type: "pin" },
        { x: 4.5, type: "roller" },
        { x: 9.0, type: "roller" },
        { x: 13.5, type: "roller" },
      ],
    },
    panel: {
      lx: 5.0, ly: 6.0,
      edges: { top: "continuous", bottom: "continuous", left: "continuous", right: "continuous" },
    },
    reinforcement: {
      bottom_x_dia: 8, bottom_x_s: 300,
      bottom_y_dia: 8, bottom_y_s: 300,
      top_x_dia: "none", top_x_s: 200,
      top_y_dia: "none", top_y_s: 200,
      cover: 15, delta_c_dev: 10,
    },
    actions: {
      mode: "analysis", gk: 1.5, qk: 2.5, self_weight: true, category: "B",
      loads: [], pattern: true, partitions: true,
      M_sag: 0, M_hog: 0, VEd: 0,
    },
    stiffness: { ...STIFF },
    durability: { exposure: "XC3/4", cement_group: "All except IVB", fire_period: "R90" },
  },
  two_way: {
    project: { ...PROJECT },
    slab: { type: "two_way", h: 200 },
    materials: { ...MATERIALS },
    span: {
      l: 5.0, preset: "simply_supported",
      supports: [{ x: 0, type: "pin" }, { x: 5.0, type: "roller" }],
    },
    panel: {
      lx: 5.0, ly: 6.0,
      edges: { top: "continuous", bottom: "continuous", left: "continuous", right: "continuous" },
    },
    reinforcement: {
      bottom_x_dia: 10, bottom_x_s: 200,
      bottom_y_dia: 10, bottom_y_s: 200,
      top_x_dia: 10, top_x_s: 200,
      top_y_dia: 10, top_y_s: 200,
      cover: 25, delta_c_dev: 10,
    },
    actions: {
      mode: "analysis", gk: 1.5, qk: 2.5, self_weight: true, category: "B",
      loads: [], pattern: true, partitions: true,
      M_sag: 0, M_hog: 0, VEd: 0,
    },
    stiffness: { ...STIFF },
    durability: { exposure: "XC1", cement_group: "All", fire_period: "R60" },
  },
  two_way_wrong: {
    project: { ...PROJECT },
    slab: { type: "two_way", h: 140 },
    materials: { ...MATERIALS },
    span: {
      l: 5.0, preset: "simply_supported",
      supports: [{ x: 0, type: "pin" }, { x: 5.0, type: "roller" }],
    },
    panel: {
      lx: 5.0, ly: 6.0,
      edges: { top: "discontinuous", bottom: "discontinuous", left: "discontinuous", right: "discontinuous" },
    },
    reinforcement: {
      bottom_x_dia: 8, bottom_x_s: 300,
      bottom_y_dia: 8, bottom_y_s: 300,
      top_x_dia: "none", top_x_s: 200,
      top_y_dia: "none", top_y_s: 200,
      cover: 25, delta_c_dev: 10,
    },
    actions: {
      mode: "analysis", gk: 1.5, qk: 2.5, self_weight: true, category: "B",
      loads: [], pattern: true, partitions: true,
      M_sag: 0, M_hog: 0, VEd: 0,
    },
    stiffness: { ...STIFF },
    durability: { exposure: "XC1", cement_group: "All", fire_period: "R60" },
  },
};

EXAMPLES.ribbed = {
  // worked example 3: 200 mm ribbed slab on 6" Maxpans, three 4.5 m spans on beams
  project: { ...PROJECT },
  slab: { type: "ribbed", maxpan: '6"', bw: 150, hf: 50 },
  materials: { ...MATERIALS, concrete: "C25/30" },
  span: {
    l: 13.5, preset: "three_spans",
    supports: [
      { x: 0, type: "pin" },
      { x: 4.5, type: "roller" },
      { x: 9.0, type: "roller" },
      { x: 13.5, type: "roller" },
    ],
  },
  reinforcement: {
    bottom_n: 2, bottom_dia: 10, top_n: 2, top_dia: 10, link_dia: "none", legs: 2,
    cover: 25, delta_c_dev: 10, mesh: "A98",
  },
  actions: {
    mode: "analysis", gk: 1.2, qk: 3.0, self_weight: true, category: "B",
    loads: [], pattern: true, partitions: false,
    M_sag: 0, M_hog: 0, VEd: 0,
  },
  stiffness: { ...STIFF },
  durability: { exposure: "XC1", cement_group: "All", fire_period: "none" },
};
EXAMPLES.ribbed_wrong = {
  ...structuredClone(EXAMPLES.ribbed),
  slab: { type: "ribbed", maxpan: '4"', bw: 100, hf: 50 },
  materials: { ...MATERIALS, concrete: "C20/25" },
  reinforcement: {
    bottom_n: 2, bottom_dia: 8, top_n: 2, top_dia: "none", link_dia: "none", legs: 2,
    cover: 15, delta_c_dev: 10, mesh: "none",
  },
};

const PRESETS = {
  simply_supported: (L) => [{ x: 0, type: "pin" }, { x: L, type: "roller" }],
  two_spans: (L) => [{ x: 0, type: "pin" }, { x: Number((L / 2).toFixed(3)), type: "roller" }, { x: L, type: "roller" }],
  three_spans: (L) => [
    { x: 0, type: "pin" },
    { x: Number((L / 3).toFixed(3)), type: "roller" },
    { x: Number(((2 * L) / 3).toFixed(3)), type: "roller" },
    { x: L, type: "roller" },
  ],
  cantilever: () => [{ x: 0, type: "fixed" }],
};

const SUPPORT_LABEL = { pin: "Pinned", roller: "Roller", fixed: "Fixed" };
const LOAD_LABEL = { point: "Point load", udl: "Uniform", linear: "Varying", moment: "Moment" };
const VALUE_KEY = { point: "W", udl: "w", linear: "w1", moment: "M" };
const UNIT = { point: "kN", udl: "kN/m", linear: "kN/m", moment: "kNm" };
const DEFAULT_LOAD = {
  point: { W: 10 },
  udl: { w: 10 },
  linear: { w1: 10, w2: 0 },
  moment: { M: 10 },
};
const CASES = [["Ed", "Design"], ["G", "gk × 1.35"], ["Q", "qk × 1.5"]];
const NUMERIC = /^reinforcement\.(bottom_x_dia|bottom_x_s|bottom_y_dia|bottom_y_s|top_x_s|top_y_s|bottom_dia|legs|cover|delta_c_dev|bottom_n|top_n)$|^slab\.(h|bw|hf)$/;
const OPTIONAL_DIA = /^reinforcement\.(top_x_dia|top_y_dia|top_dia|link_dia)$/;

const form = document.getElementById("slab-form");
const $ = (id) => document.getElementById(id);
const errors = formErrors(form, $("form-message"));
let meta = null;
let canvas = null;
let editor = null;
let model = { supports: [], loads: [] };
let selected = null;
let lastAnalysis = null;
let analysisRequest = 0;

const TAB_NAMES = ["analysis", "design", "report"];
let currentTab = "analysis";
let analysisDone = false;
let designDone = false;
let analysisDirty = false;

const slabType = () => form.querySelector('input[name="slab.type"]:checked')?.value || "one_way";
// one-way slabs and ribbed slabs are both analysed as a beam along the span (a 1 m strip or one rib)
const isStrip = (type = slabType()) => type === "one_way" || type === "ribbed";
const valueOf = (name) => form.elements[name]?.value;
const length = () => Number(valueOf("span.l")) || 0;
const r3 = (x) => Number(Number(x).toFixed(3));

function updateTabStates() {
  const tDesign = $("tab-design");
  const tReport = $("tab-report");
  const canDesign = analysisDone && !analysisDirty;
  tDesign.setAttribute("aria-disabled", String(!canDesign));
  tReport.setAttribute("aria-disabled", String(!designDone));
  if (analysisDirty && $("analysis-note")) {
    $("analysis-note").textContent = "Inputs changed since last analysis: click Analyse to refresh";
  }
}

function markAnalysisDirty() {
  analysisDirty = true;
  updateTabStates();
}

function switchTab(name) {
  if (name === currentTab) return;
  const button = $(`tab-${name}`);
  if (button?.getAttribute("aria-disabled") === "true") return;

  for (const t of TAB_NAMES) {
    const active = t === name;
    $(`tab-${t}`)?.setAttribute("aria-selected", String(active));
    const panel = $(`panel-${t}`);
    if (panel) {
      panel.classList.toggle("is-active", active);
      panel.hidden = !active;
    }
  }
  currentTab = name;
  form.classList.toggle("report-active", name === "report");

  if (history.replaceState) {
    history.replaceState(null, "", `#${name}`);
  } else {
    location.hash = name;
  }

  if (name === "report") {
    const frame = $("report-frame");
    if (!frame.src || !frame.src.includes("/slab/report?embed=1")) {
      frame.src = "/slab/report?embed=1";
    }
  }
}

function setupTabs() {
  for (const t of TAB_NAMES) {
    $(`tab-${t}`)?.addEventListener("click", () => switchTab(t));
  }
  window.addEventListener("hashchange", () => {
    const hash = location.hash.replace("#", "");
    if (TAB_NAMES.includes(hash)) switchTab(hash);
  });
}

function show(selector, on) {
  form.querySelectorAll(selector).forEach((n) => { n.hidden = !on; });
}

function syncVisibility() {
  const type = slabType();
  show(".one-way-only", isStrip(type));
  show(".two-way-only", type === "two_way");
  show(".solid-only", type !== "ribbed");
  show(".ribbed-only", type === "ribbed");
  // per metre width for a solid slab, per rib for a ribbed slab
  for (const node of form.querySelectorAll("[data-unit]")) {
    node.textContent = (node.dataset.unit === "moment" ? "kNm" : "kN") + (type === "ribbed" ? "" : "/m");
  }

  show(".e-enter", valueOf("stiffness.E_method") === "enter");

  if (meta) {
    const exp = meta.exposure_all.find((r) => r.id === valueOf("durability.exposure"));
    const cem = form.elements["durability.cement_group"];
    if (exp && cem) {
      const current = cem.value;
      cem.replaceChildren(...exp.groups.map((g) => option(g, g)));
      if (exp.groups.includes(current)) cem.value = current;
      $("exposure-help").textContent = exp.note || "";
    }
    const conc = meta.concrete.find((c) => c.name === valueOf("materials.concrete"));
    if (conc) {
      $("concrete-help").textContent = `fck ${conc.fck} MPa, fctm ${conc.fctm} MPa, Ecm ${conc.Ecm} GPa`;
      if ($("e-help")) $("e-help").textContent = valueOf("stiffness.E_method") === "enter" ? "" : `Ecm = ${conc.Ecm} GPa (${conc.name}, set on the Design tab)`;
    }
  }
}

// ------------------------------------------------------------------ Tables

function cellInput(path, value, attrs = {}) {
  return el("div", { class: "control" }, el("input", {
    type: "number",
    step: attrs.step || "any",
    value: value ?? "",
    "data-path": path,
    "aria-label": attrs.label || path,
    ...(attrs.min !== undefined ? { min: attrs.min } : {}),
    ...(attrs.max !== undefined ? { max: attrs.max } : {}),
    ...attrs.extra,
  }), attrs.unit ? el("span", { class: "unit" }, attrs.unit) : null);
}

function cellSelect(path, value, options, label) {
  const sel = el("select", { "data-path": path, "aria-label": label }, ...options.map(([v, l]) => option(v, l)));
  sel.value = value;
  return el("div", { class: "control" }, sel);
}

function removeButton(onClick, label) {
  const b = el("button", {
    type: "button",
    class: "btn-icon",
    "aria-label": label,
    title: label,
  }, "×");
  b.addEventListener("click", (e) => {
    e.stopPropagation();
    onClick();
  });
  return b;
}

function renderSupports() {
  const tbody = $("supports-table")?.tBodies[0];
  if (!tbody) return;
  tbody.replaceChildren(...model.supports.map((sp, i) => {
    const row = el("tr", { class: selected?.kind === "support" && selected.index === i ? "is-selected" : "" },
      el("td", { class: "idx" }, String(i + 1)),
      el("td", {}, cellInput(`span.supports.${i}.x`, sp.x, { label: `Support ${i + 1} position`, unit: "m" })),
      el("td", {}, cellSelect(`span.supports.${i}.type`, sp.type, Object.entries(SUPPORT_LABEL), `Support ${i + 1} type`)),
      el("td", { class: "row-actions" }, removeButton(() => {
        model.supports.splice(i, 1);
        if (selected?.kind === "support") {
          if (selected.index === i) selected = null;
          else if (selected.index > i) selected = { kind: "support", index: selected.index - 1 };
        }
        markCustom();
        structural();
      }, `Remove support ${i + 1}`)));
    row.addEventListener("click", (e) => {
      if (!e.target.closest("button, input, select")) pick({ kind: "support", index: i }, true);
    });
    return row;
  }));
}

function changeLoadType(item, type) {
  const L = length();
  const at = item.x ?? item.x1 ?? 0;
  const value = item[VALUE_KEY[item.type]] ?? DEFAULT_LOAD[type][VALUE_KEY[type]];
  for (const k of ["W", "w", "w1", "w2", "M", "x", "x1", "x2"]) delete item[k];
  item.type = type;
  item[VALUE_KEY[type]] = value;
  if (type === "point" || type === "moment") {
    item.x = at;
  } else {
    item.x1 = Math.min(at, L * 0.8);
    item.x2 = r3(Math.min(L, item.x1 + L / 5));
    if (type === "linear") item.w2 = 0;
  }
}

function renderLoads() {
  const tbody = $("loads-table")?.tBodies[0];
  if (!tbody) return;
  tbody.replaceChildren(...model.loads.map((ld, i) => {
    const p = `actions.loads.${i}`;
    const span = ld.type === "udl" || ld.type === "linear";
    const row = el("tr", { class: selected?.kind === "load" && selected.index === i ? "is-selected" : "" },
      el("td", {}, cellSelect(`${p}.type`, ld.type, Object.entries(LOAD_LABEL), `Load ${i + 1} type`)),
      el("td", {}, cellInput(`${p}.${VALUE_KEY[ld.type]}`, ld[VALUE_KEY[ld.type]], { label: `Load ${i + 1} value`, unit: UNIT[ld.type] })),
      el("td", {}, cellSelect(`${p}.case`, ld.case || "Ed", CASES, `Load ${i + 1} case`)),
      el("td", {}, cellInput(span ? `${p}.x1` : `${p}.x`, span ? ld.x1 : ld.x, { label: `Load ${i + 1} position` })),
      el("td", {}, span ? cellInput(`${p}.x2`, ld.x2, { label: `Load ${i + 1} end` }) : el("span", { class: "dash" }, "—")),
      el("td", {}, ld.type === "linear" ? cellInput(`${p}.w2`, ld.w2, { label: `Load ${i + 1} end value`, unit: "kN/m" }) : el("span", { class: "dash" }, "—")),
      el("td", { class: "row-actions" }, removeButton(() => {
        model.loads.splice(i, 1);
        if (selected?.kind === "load") {
          if (selected.index === i) selected = null;
          else if (selected.index > i) selected = { kind: "load", index: selected.index - 1 };
        }
        structural();
      }, `Remove load ${i + 1}`)));
    row.addEventListener("click", (e) => {
      if (!e.target.closest("button, select, input")) pick({ kind: "load", index: i }, true);
    });
    return row;
  }));
}

function renderTables() {
  renderSupports();
  renderLoads();
}

/** A value typed or selected in a table cell. */
function onTableInput(event) {
  const path = event.target.dataset.path;
  if (!path) return;
  const parts = path.split(".");
  const index = Number(parts[parts.length - 2]);
  const key = parts[parts.length - 1];
  const list = path.startsWith("span.supports") ? model.supports : model.loads;
  const item = list[index];
  if (!item) return;
  if (event.target.tagName === "SELECT") {
    if (key === "type" && list === model.loads) changeLoadType(item, event.target.value);
    else item[key] = event.target.value;
    if (list === model.supports) markCustom();
    structural();
    return;
  }
  item[key] = event.target.value === "" ? null : Number(event.target.value);
  if (list === model.supports) markCustom();
  refresh();
}

function markCustom() {
  if (form.elements["span.preset"]) form.elements["span.preset"].value = "custom";
}

function applyPreset() {
  const name = valueOf("span.preset");
  if (!name || name === "custom" || !PRESETS[name]) return;
  model.supports = PRESETS[name](length()).map((sp) => ({ ...sp }));
}

function structural() {
  renderTables();
  refresh();
  markAnalysisDirty();
}

function pick(sel, syncCanvas = true) {
  selected = sel;
  $("canvas-delete").disabled = !sel;
  renderTables();
  if (syncCanvas && canvas) canvas.select(sel);
}

function editItem(sel, screenPoint) {
  pick(sel, false);
  if (!editor || !sel) return;
  const item = sel.kind === "support" ? model.supports[sel.index] : model.loads[sel.index];
  if (!item) return;
  editor.open({
    selection: sel,
    item,
    length: length(),
    screenPoint: screenPoint || canvas.getItemScreenPoint(sel),
    onApply: (selection, updated) => {
      const l = selection.kind === "load" ? model.loads : model.supports;
      l[selection.index] = updated;
      if (selection.kind === "support") {
        model.supports.sort((a, b) => a.x - b.x);
        markCustom();
        selected = { kind: "support", index: model.supports.indexOf(updated) };
      }
      canvas.render();
      renderTables();
      refresh();
    },
    onDelete: (selection) => {
      canvas.select(selection);
      canvas.remove();
    },
  });
}

// ------------------------------------------------------------------ Two-Way Interactive Plan

function toggleEdge(edgeName) {
  const sel = form.elements[`panel.edges.${edgeName}`];
  if (!sel) return;
  sel.value = sel.value === "continuous" ? "discontinuous" : "continuous";
  drawPanelPlan();
  markAnalysisDirty();
  runLiveAnalysis();
}

function drawPanelPlan() {
  const host = $("panel-plan-interactive");
  if (!host) return;

  const lx = Number(valueOf("panel.lx")) || 5.0;
  const ly = Number(valueOf("panel.ly")) || 6.0;
  const edges = {
    top: valueOf("panel.edges.top") || "continuous",
    bottom: valueOf("panel.edges.bottom") || "continuous",
    left: valueOf("panel.edges.left") || "continuous",
    right: valueOf("panel.edges.right") || "continuous",
  };

  const W = 280, H = 200;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Interactive panel plan" });

  // ly across and lx up: the top and bottom edges are the long edges, as the labels say
  const maxW = 180, maxH = 130;
  const scale = Math.min(maxW / ly, maxH / lx);
  const pw = Math.max(ly * scale, 70);
  const ph = Math.max(lx * scale, 70);
  const cx = W / 2, cy = H / 2;
  const x0 = cx - pw / 2;
  const x1 = cx + pw / 2;
  const y0 = cy - ph / 2;
  const y1 = cy + ph / 2;

  // Concrete fill
  svg.append(s("polygon", {
    points: `${x0},${y0} ${x1},${y0} ${x1},${y1} ${x0},${y1}`,
    fill: "var(--draw-concrete, #ece6db)",
    stroke: "var(--draw-rule, #e2ddd5)",
    "stroke-width": 1,
  }));

  // Top edge
  const topCont = edges.top === "continuous";
  svg.append(s("line", { x1: x0, y1: y0, x2: x1, y2: y0, stroke: "var(--draw-ink, #192329)", "stroke-width": topCont ? 3.5 : 1.4 }));
  if (topCont) {
    for (let x = x0 + 4; x < x1; x += 8) {
      svg.append(s("line", { x1: x, y1: y0, x2: x + 6, y2: y0 - 8, stroke: "var(--draw-muted, #6a747a)", "stroke-width": 1 }));
    }
  }
  const hitTop = s("line", { x1: x0, y1: y0, x2: x1, y2: y0, stroke: "transparent", "stroke-width": 26, style: "cursor: pointer" });
  hitTop.addEventListener("click", () => toggleEdge("top"));
  svg.append(hitTop);

  // Bottom edge
  const botCont = edges.bottom === "continuous";
  svg.append(s("line", { x1: x0, y1: y1, x2: x1, y2: y1, stroke: "var(--draw-ink, #192329)", "stroke-width": botCont ? 3.5 : 1.4 }));
  if (botCont) {
    for (let x = x0 + 4; x < x1; x += 8) {
      svg.append(s("line", { x1: x, y1: y1, x2: x - 6, y2: y1 + 8, stroke: "var(--draw-muted, #6a747a)", "stroke-width": 1 }));
    }
  }
  const hitBot = s("line", { x1: x0, y1: y1, x2: x1, y2: y1, stroke: "transparent", "stroke-width": 26, style: "cursor: pointer" });
  hitBot.addEventListener("click", () => toggleEdge("bottom"));
  svg.append(hitBot);

  // Left edge
  const leftCont = edges.left === "continuous";
  svg.append(s("line", { x1: x0, y1: y0, x2: x0, y2: y1, stroke: "var(--draw-ink, #192329)", "stroke-width": leftCont ? 3.5 : 1.4 }));
  if (leftCont) {
    for (let y = y0 + 4; y < y1; y += 8) {
      svg.append(s("line", { x1: x0, y1: y, x2: x0 - 8, y2: y + 6, stroke: "var(--draw-muted, #6a747a)", "stroke-width": 1 }));
    }
  }
  const hitLeft = s("line", { x1: x0, y1: y0, x2: x0, y2: y1, stroke: "transparent", "stroke-width": 26, style: "cursor: pointer" });
  hitLeft.addEventListener("click", () => toggleEdge("left"));
  svg.append(hitLeft);

  // Right edge
  const rightCont = edges.right === "continuous";
  svg.append(s("line", { x1: x1, y1: y0, x2: x1, y2: y1, stroke: "var(--draw-ink, #192329)", "stroke-width": rightCont ? 3.5 : 1.4 }));
  if (rightCont) {
    for (let y = y0 + 4; y < y1; y += 8) {
      svg.append(s("line", { x1: x1, y1: y, x2: x1 + 8, y2: y - 6, stroke: "var(--draw-muted, #6a747a)", "stroke-width": 1 }));
    }
  }
  const hitRight = s("line", { x1: x1, y1: y0, x2: x1, y2: y1, stroke: "transparent", "stroke-width": 26, style: "cursor: pointer" });
  hitRight.addEventListener("click", () => toggleEdge("right"));
  svg.append(hitRight);

  // Labels in center
  svg.append(s("text", {
    x: cx, y: cy - 8, "text-anchor": "middle", "font-size": 12, "font-weight": 600,
    fill: "var(--draw-ink, #192329)",
  }, `ly ${ly.toFixed(1)} m × lx ${lx.toFixed(1)} m`));
  svg.append(s("text", {
    x: cx, y: cy + 10, "text-anchor": "middle", "font-size": 10.5,
    fill: "var(--draw-muted, #6a747a)",
  }, `(ly/lx = ${(ly / lx).toFixed(2)})`));

  host.replaceChildren(svg);
}

// ------------------------------------------------------------------ Live Preview & Side Panel

const barArea = (dia) => (Math.PI * dia * dia) / 4;

function setStats(rows) {
  rows.forEach(([label, value], i) => {
    $(`st-k${i + 1}`).innerHTML = label;
    $(`st-${["asbx", "asby", "astx", "asty"][i]}`).textContent = value;
  });
}

function updateRibbedPreview() {
  const pan = meta?.maxpans.find((p) => p.id === valueOf("slab.maxpan")) || { id: '6"', height: 150, mass: 8.5, width: 300, length: 300 };
  const bw = Number(valueOf("slab.bw")) || 0;
  const hf = Number(valueOf("slab.hf")) || 0;
  const h = pan.height + hf;
  const spacing = bw + pan.width;
  const cover = Number(valueOf("reinforcement.cover")) || 25;
  const link = valueOf("reinforcement.link_dia");
  const linkDia = link && link !== "none" ? Number(link) : null;

  const nb = Number(valueOf("reinforcement.bottom_n")) || 0;
  const db = Number(valueOf("reinforcement.bottom_dia")) || 10;
  const top = valueOf("reinforcement.top_dia");
  const dt = top && top !== "none" ? Number(top) : null;
  const nt = dt ? Number(valueOf("reinforcement.top_n")) || 0 : 0;
  const mesh = valueOf("reinforcement.mesh");
  const asb = nb * barArea(db);
  const ast = dt ? nt * barArea(dt) : 0;

  // own weight of one rib per metre run: concrete of the rib and the topping, plus one row of Maxpans
  const swC = (25 * (bw * pan.height + spacing * hf)) / 1e6;
  const swPan = (pan.mass * 9.81e-3) / (pan.length / 1000);
  $("rb-geometry").textContent = bw && hf
    ? `h = ${pan.height} + ${hf} = ${h} mm; ribs at ${spacing} mm centres (${bw} + ${pan.width}); `
      + `own weight per rib ${(swC + swPan).toFixed(3)} kN/m (concrete ${swC.toFixed(3)}, Maxpans ${swPan.toFixed(3)})`
    : "—";
  $("rb-pan-help").textContent = `Clay blocks ${pan.length} × ${pan.width} × ${pan.height} mm, ${pan.mass.toFixed(2)} kg, ${meta?.maxpans_per_m2 ?? 8} per m²`;
  $("rb-bot-help").textContent = `As = ${Math.round(asb)} mm² per rib (sagging)`;
  $("rb-top-help").textContent = dt ? `As = ${Math.round(ast)} mm² per rib over the supports` : "none: needed over continuous supports";

  setStats([
    ["A<sub>s</sub> bottom per rib", `${Math.round(asb)} mm²`],
    ["A<sub>s</sub> top per rib", dt ? `${Math.round(ast)} mm²` : "none"],
    ["Depth h / centres", `${h} / ${spacing} mm`],
    ["Fabric", mesh && mesh !== "none" ? mesh : "none"],
  ]);

  const sec = {
    slab_type: "ribbed", h, hf, ph: pan.height, bw, spacing, cover, link_dia: linkDia, maxpan: pan.id,
    bottom: { n: nb, dia: db, As: asb }, top: { n: nt, dia: dt, As: ast },
    mesh: mesh && mesh !== "none" ? mesh : null,
  };
  const previewBox = $("preview-section");
  if (previewBox && bw && hf) drawSlabSection(previewBox, sec, { width: 380, height: 230 });
}

function updateStatsAndPreview() {
  if (slabType() === "ribbed") {
    updateRibbedPreview();
    return;
  }
  const h = Number(valueOf("slab.h")) || 200;
  const cover = Number(valueOf("reinforcement.cover")) || 25;
  const type = slabType();

  const bx_dia = Number(valueOf("reinforcement.bottom_x_dia")) || 10;
  const bx_s = Number(valueOf("reinforcement.bottom_x_s")) || 200;
  const asbx = Math.round((Math.PI * bx_dia * bx_dia / 4.0) * 1000.0 / bx_s);

  const by_dia = Number(valueOf("reinforcement.bottom_y_dia")) || 10;
  const by_s = Number(valueOf("reinforcement.bottom_y_s")) || 200;
  const asby = Math.round((Math.PI * by_dia * by_dia / 4.0) * 1000.0 / by_s);

  const tx_val = valueOf("reinforcement.top_x_dia");
  const has_tx = tx_val && tx_val !== "none" && Number(tx_val) > 0;
  const tx_dia = has_tx ? Number(tx_val) : null;
  const tx_s = Number(valueOf("reinforcement.top_x_s")) || 200;
  const astx = has_tx ? Math.round((Math.PI * tx_dia * tx_dia / 4.0) * 1000.0 / tx_s) : 0;

  const ty_val = valueOf("reinforcement.top_y_dia");
  const has_ty = ty_val && ty_val !== "none" && Number(ty_val) > 0;
  const ty_dia = has_ty ? Number(ty_val) : null;
  const ty_s = Number(valueOf("reinforcement.top_y_s")) || 200;
  const asty = has_ty ? Math.round((Math.PI * ty_dia * ty_dia / 4.0) * 1000.0 / ty_s) : 0;

  setStats([
    ["A<sub>s</sub> bottom x", `${asbx} mm²/m`],
    ["A<sub>s</sub> bottom y", `${asby} mm²/m`],
    ["A<sub>s</sub> top x", astx ? `${astx} mm²/m` : "none"],
    ["A<sub>s</sub> top y", asty ? `${asty} mm²/m` : "none"],
  ]);

  if ($("bx-as-help")) $("bx-as-help").textContent = `As = ${asbx} mm²/m`;
  if ($("by-as-help")) $("by-as-help").textContent = `As = ${asby} mm²/m`;
  if ($("tx-as-help")) $("tx-as-help").textContent = astx ? `As = ${astx} mm²/m` : "none";
  if ($("ty-as-help")) $("ty-as-help").textContent = asty ? `As = ${asty} mm²/m` : "none";

  const sec = {
    slab_type: type,
    b: 1000,
    h,
    cover,
    bottom_x: { dia: bx_dia, s: bx_s, As: asbx },
    bottom_y: { dia: by_dia, s: by_s, As: asby },
    top_x: { dia: tx_dia, s: tx_s, As: astx },
    top_y: { dia: ty_dia, s: ty_s, As: asty },
  };

  const previewBox = $("preview-section");
  if (previewBox) {
    drawSlabSection(previewBox, sec, { width: 380, height: 230 });
  }
}

function summaries(d) {
  const f = (n, dp = 2) => (typeof n === "number" && !Number.isNaN(n) ? (Number.isInteger(n) ? String(n) : n.toFixed(dp).replace(/\.?0+$/, "")) : "—");
  const type = d.slab?.type || "one_way";
  let geom = "—";
  if (type === "ribbed") {
    const pan = meta?.maxpans.find((p) => p.id === d.slab?.maxpan) || { height: 150 };
    geom = `Maxpan ${d.slab?.maxpan || '6"'} · bw ${f(d.slab?.bw, 0)} mm · hf ${f(d.slab?.hf, 0)} mm (h = ${pan.height + (Number(d.slab?.hf) || 0)} mm)`;
  } else {
    geom = `Solid slab · h = ${f(d.slab?.h, 0)} mm`;
  }

  const sup = (d.span?.supports || []).map((sp) => `${sp.type[0].toUpperCase()}${sp.type.slice(1)} ${f(sp.x)}`).join(", ");
  const spanSummary = `L = ${f(d.span?.l)} m · ${sup || "no supports"}`;
  const panelSummary = `${f(d.panel?.lx)} × ${f(d.panel?.ly)} m · edges: ${d.panel?.edges?.top || "continuous"}`;

  const a = d.actions || {};
  const loadsSummary = a.mode === "direct"
    ? `M+Ed ${f(a.M_sag)} · M−Ed ${f(a.M_hog)} kNm · VEd ${f(a.VEd)} kN`
    : `gk ${f(a.gk)}${a.self_weight ? " + sw" : ""} · qk ${f(a.qk)} kN/m²${(a.loads || []).length ? ` · ${a.loads.length} further load${a.loads.length > 1 ? "s" : ""}` : ""}`;

  const mat = d.materials || {};
  const matSummary = `${mat.concrete || "C30/37"} · fyk ${f(mat.fyk, 0)} MPa`;

  const re = d.reinforcement || {};
  let reSummary = "—";
  if (type === "ribbed") {
    reSummary = `${re.bottom_n || 2}H${re.bottom_dia || 10} bot · ${re.top_dia && re.top_dia !== "none" ? `${re.top_n || 2}H${re.top_dia} top` : "no top bars"} · cover ${f(re.cover, 0)} mm`;
  } else {
    reSummary = `H${re.bottom_x_dia || 10}@${re.bottom_x_s || 200} bot x · H${re.bottom_y_dia || 10}@${re.bottom_y_s || 200} bot y · cover ${f(re.cover, 0)} mm`;
  }

  const du = d.durability || {};
  const duSummary = `${du.exposure || "XC1"} · ${du.fire_period === "none" ? "no fire period" : `fire ${du.fire_period}`}`;

  const pr = d.project || {};
  const projSummary = [pr.name, pr.ref].filter(Boolean).join(" · ") || "Optional";

  return {
    geometry: geom,
    span: spanSummary,
    panel: panelSummary,
    actions: loadsSummary,
    materials: matSummary,
    reinforcement: reSummary,
    durability: duSummary,
    project: projSummary,
  };
}

function updateSummaries() {
  const d = serialize();
  const text = summaries(d);
  for (const node of document.querySelectorAll("[data-sum]")) {
    node.textContent = text[node.dataset.sum] ?? "";
  }
}

let analysisTimer = null;

function scheduleAnalysis() {
  clearTimeout(analysisTimer);
  analysisTimer = setTimeout(runLiveAnalysis, 260);
}

function refresh() {
  syncVisibility();
  drawPanelPlan();
  updateStatsAndPreview();
  updateSummaries();
  if (canvas && isStrip()) {
    canvas.selected = selected;
    canvas.setModel({ length: length(), supports: model.supports, loads: model.loads, w: lastAnalysis?.analysis?.w || 0 });
  }
  scheduleAnalysis();
}

// ------------------------------------------------------------------ Serialization

function serialize() {
  const data = {};
  for (const input of form.querySelectorAll("[name]")) {
    const path = input.name;
    if (input.type === "radio") {
      if (input.checked) setPath(data, path, input.value);
    } else if (input.type === "checkbox") {
      setPath(data, path, input.checked);
    } else if (input.type === "number") {
      setPath(data, path, input.value === "" ? null : Number(input.value));
    } else if (OPTIONAL_DIA.test(path)) {
      setPath(data, path, input.value === "none" ? "none" : Number(input.value));
    } else if (NUMERIC.test(path)) {
      setPath(data, path, input.value === "" ? null : Number(input.value));
    } else {
      setPath(data, path, input.value);
    }
  }

  if (!data.span) data.span = {};
  data.span.supports = model.supports.map((sp) => ({ ...sp }));
  if (!data.actions) data.actions = {};
  data.actions.loads = model.loads.map((ld) => ({ ...ld }));

  const adjust = $("adjust-design-values")?.checked;
  if (adjust) {
    data.actions.mode = "direct";
    if (isStrip(data.slab?.type)) {
      data.actions.M_sag = Number($("dv-ms")?.value) || 0;
      data.actions.M_hog = Number($("dv-mh")?.value) || 0;
      data.actions.VEd = Number($("dv-ved")?.value) || 0;
    } else {
      data.actions.M_sag = Number($("dv-msx-mid")?.value) || 0;
      data.actions.VEd = Number($("dv-tw-ved")?.value) || 0;
    }
  } else {
    data.actions.mode = "analysis";
  }

  return data;
}

export function fill(data) {
  if (!data.slab?.type) data = structuredClone(EXAMPLES.one_way);
  for (const input of form.querySelectorAll("[name]")) {
    const value = getPath(data, input.name);
    if (input.type === "radio") {
      input.checked = input.value === (value ?? "one_way");
    } else if (input.type === "checkbox") {
      if (value !== undefined) input.checked = Boolean(value);
    } else if (value !== undefined && value !== null) {
      input.value = String(value);
    }
  }
  if (data.span?.supports) {
    model.supports = data.span.supports.map((sp) => ({ ...sp }));
  } else if (isStrip(data.slab?.type)) {
    model.supports = PRESETS.three_spans(data.span?.l || 13.5);
  } else {
    model.supports = [];
  }
  model.loads = (data.actions?.loads || []).map((ld) => ({ ...ld }));

  renderTables();
  refresh();
  markAnalysisDirty();
  runLiveAnalysis();
}

// ------------------------------------------------------------------ Live Analysis

async function runLiveAnalysis() {
  const id = ++analysisRequest;
  const data = serialize();
  let res;
  try {
    res = await postJSON("/api/slab/analysis", data);
  } catch {
    return;
  }
  if (id !== analysisRequest) return;
  if (!res.ok) {
    const n = Object.keys(res.data?.errors || {}).length;
    $("analysis-hint").textContent = n ? `${n} to fix` : "incomplete";
    return;
  }

  lastAnalysis = res.data;
  $("analysis-hint").textContent = "live";
  if (canvas && isStrip(data.slab?.type)) canvas.setModel({ ...canvas.model, w: res.data.analysis?.w || 0 });

  if (isStrip(data.slab?.type)) {
    const ribbed = data.slab.type === "ribbed";
    if (res.data.figures?.diagrams) {
      renderFigure($("preview-analysis"), res.data.figures.diagrams, "Shear force and bending moment");
    }
    if (res.data.analysis?.envelope) {
      const { sag, hog, V: shr } = designValues(res.data.analysis);
      $("st-w").textContent = `${(res.data.analysis.w || 0).toFixed(2)} kN/m${ribbed ? " per rib" : ""}`;
      $("st-m").textContent = `${sag.toFixed(1)} / ${hog.toFixed(1)} kNm`;
      $("st-v").textContent = `${shr.toFixed(1)} kN`;

      if (!$("adjust-design-values")?.checked) {
        $("dv-ms").value = sag.toFixed(1);
        $("dv-mh").value = hog.toFixed(1);
        $("dv-ved").value = shr.toFixed(1);
      }
    }
    const rxBox = $("analysis-reactions");
    if (rxBox && res.data.analysis?.reactions) {
      rxBox.textContent = `Reactions: ${res.data.analysis.reactions.map((r) => `${r.Ry.toFixed(1)} kN`).join(", ")}`;
    }
  } else {
    const p = res.data.panel;
    if (p) {
      const moms = p.moments || {};
      const shears = p.shears || {};
      const sw = (25.0 * (data.slab.h / 1000.0));
      const n = 1.35 * (data.actions.gk + sw) + 1.5 * data.actions.qk;
      $("st-w").textContent = `${n.toFixed(2)} kN/m²`;
      $("st-m").textContent = `${moms.msx_mid.toFixed(1)} / ${moms.msy_mid.toFixed(1)} kNm`;
      $("st-v").textContent = `${shears.VEd.toFixed(1)} kN/m`;

      if (!$("adjust-design-values")?.checked) {
        $("dv-msx-mid").value = moms.msx_mid.toFixed(1);
        $("dv-msx-sup").value = moms.msx_sup.toFixed(1);
        $("dv-msy-mid").value = moms.msy_mid.toFixed(1);
        $("dv-msy-sup").value = moms.msy_sup.toFixed(1);
        $("dv-tw-ved").value = shears.VEd.toFixed(1);
      }
      const rxBox = $("analysis-reactions");
      if (rxBox) {
        rxBox.textContent = `${p.case?.label || ""}: βsx=${p.coefficients?.bsx_mid} (mid), βsy=${p.coefficients?.bsy_mid} (mid)`;
      }
    }
  }
}

// ------------------------------------------------------------------ Perform Analysis (Button)

function buildTwoWayAnalysisView(data, { onContinue }) {
  const p = data.panel;
  const figs = data.figures || {};
  const coeffs = p.coefficients || {};
  const moms = p.moments || {};
  const shears = p.shears || {};
  const ratio = p.lx ? p.ly / p.lx : 1.0;

  const statItem = (label, val, sub) =>
    el("div", { class: "analysis-env-item" },
      el("div", { class: "k" }, label),
      el("div", { class: "v" }, val),
      sub ? el("div", { class: "sub" }, sub) : null
    );

  const envStrip = el("div", { class: "analysis-env-grid" },
    statItem("Aspect ratio ly/lx", num(ratio), p.case?.label),
    statItem("Short span msx,mid", `${num(moms.msx_mid)} kNm/m`, `β = ${num(coeffs.bsx_mid, 4)}`),
    statItem("Long span msy,mid", `${num(moms.msy_mid)} kNm/m`, `β = ${num(coeffs.bsy_mid, 4)}`),
    statItem("Short span continuous", coeffs.bsx_sup !== null ? `${num(moms.msx_sup)} kNm/m` : "discontinuous", coeffs.bsx_sup !== null ? `β = ${num(coeffs.bsx_sup, 4)}` : null),
    statItem("Design shear VEd", `${num(shears.VEd)} kN/m`, `vEd = ${num(shears.vEd, 3)} MPa`)
  );

  const panelFigureEl = figs.panel ? el("figure", { class: "panel figure wide" },
    el("div", { class: "panel-head" }, el("h3", {}, "Panel plan & moments")),
    el("div", { class: "panel-body" }, spec("panel", figs.panel, "Two-way panel plan")),
    el("figcaption", {}, "Plan view to scale with continuous edges hatched and moments per metre width.")
  ) : null;

  const rowsCoeffs = [
    ["Short span (lx) mid-span", "Sagging (bottom x)", num(coeffs.bsx_mid, 4), `${num(moms.msx_mid)} kNm/m`],
    ["Short span continuous edge", "Hogging (top x)", coeffs.bsx_sup !== null ? num(coeffs.bsx_sup, 4) : "—", coeffs.bsx_sup !== null ? `${num(moms.msx_sup)} kNm/m` : "discontinuous"],
    ["Long span (ly) mid-span", "Sagging (bottom y)", num(coeffs.bsy_mid, 4), `${num(moms.msy_mid)} kNm/m`],
    ["Long span continuous edge", "Hogging (top y)", coeffs.bsy_sup !== null ? num(coeffs.bsy_sup, 4) : "—", coeffs.bsy_sup !== null ? `${num(moms.msy_sup)} kNm/m` : "discontinuous"],
  ];
  const coeffTable = el("figure", { class: "panel figure" },
    el("div", { class: "panel-head" }, el("h3", {}, "Moment coefficients")),
    el("div", { class: "panel-body" }, table(["Location", "Action", "Coeff. β", "Moment m = β·n·lx²"], rowsCoeffs)),
    el("figcaption", {}, "Bending moment coefficients for two-way slabs with restrained corners.")
  );

  const rowsShears = [
    ["Design shear force VEd", `${num(shears.VEd)} kN/m`, shears.basis || ""],
    ["Design shear stress vEd", `${num(shears.vEd, 3)} MPa`, "vEd = VEd / (b·d)"],
    ["Concrete shear resistance vRd,c", `${num(shears.vRd_c, 3)} MPa`, "without shear links"],
  ];
  const shearTable = el("figure", { class: "panel figure" },
    el("div", { class: "panel-head" }, el("h3", {}, "Shear evaluation")),
    el("div", { class: "panel-body" }, table(["Item", "Value", "Basis"], rowsShears)),
    el("figcaption", {}, "Shear capacity verified without shear reinforcement.")
  );

  const continueBlock = el("div", { class: "tab-continue" },
    el("button", { type: "button", class: "btn primary", onclick: onContinue }, "Continue to design →")
  );

  return el("div", { class: "analysis-results-block" },
    el("h3", {}, `Two-way slab analysis: ${p.case?.label || ""}`),
    envStrip,
    el("div", { class: "figures", style: "margin-top: 16px;" }, panelFigureEl, coeffTable, shearTable),
    continueBlock
  );
}

async function performAnalysis() {
  errors.clear();
  const btn = $("btn-analyse");
  btn.disabled = true;
  try {
    const data = serialize();
    const res = await postJSON("/api/slab/analysis", data);
    if (!res.ok) {
      if (res.status === 400 && res.data?.errors) {
        errors.show(res.data.errors);
      } else {
        $("form-message").textContent = `Server error (${res.status})`;
      }
      return;
    }
    lastAnalysis = res.data;
    analysisDone = true;
    analysisDirty = false;
    $("analysis-note").textContent = "";
    updateTabStates();

    if (isStrip(data.slab.type)) {
      const view = buildAnalysisView(res.data, {
        showContinue: true,
        onContinue: () => switchTab("design"),
      });
      $("analysis-results-area").replaceChildren(view);
    } else {
      const view = buildTwoWayAnalysisView(res.data, {
        onContinue: () => switchTab("design"),
      });
      $("analysis-results-area").replaceChildren(view);
    }
  } catch (err) {
    $("form-message").textContent = failureText(err, "the analysis");
  } finally {
    btn.disabled = false;
  }
}

// ------------------------------------------------------------------ Perform Design Checks

async function performDesignChecks(e) {
  if (e) e.preventDefault();
  errors.clear();
  const btn = $("btn-run-design");
  if (btn) btn.disabled = true;
  try {
    const data = serialize();
    const res = await postJSON("/api/slab/check", data);
    if (!res.ok) {
      if (res.status === 400 && res.data?.errors) {
        errors.show(res.data.errors);
        $("form-message").textContent = "Please fix the highlighted errors.";
      } else {
        $("form-message").textContent = `Server error (${res.status})`;
      }
      return;
    }

    designDone = true;
    updateTabStates();
    // the report page reads { input, result } from this tab's session, as the run page stores it
    store.setSession(KEYS.result, { input: data, result: res.data });
    store.set(KEYS.input, data);

    const c = res.data.summary.counts;
    const verdict = res.data.summary.verdict;
    const isPass = verdict === "pass";

    const badge = el("div", { class: `verdict-badge ${verdict}` },
      statusDot(verdict),
      el("strong", {}, isPass ? "Adequate" : "Not adequate"),
      el("span", {}, `: ${isPass ? `all ${c.pass} checks pass` : `${c.fail} check${c.fail > 1 ? "s" : ""} fail`}`)
    );

    const checksList = el("ul", { class: "checks-summary-list", style: "margin: 12px 0; list-style: none; padding: 0;" },
      ...res.data.checks.map((chk) =>
        el("li", { style: "display: flex; gap: 8px; align-items: baseline; margin: 4px 0; font-size: 13.5px;" },
          statusDot(chk.status),
          el("span", { style: "font-weight: 500;" }, chk.title),
          el("span", { class: "muted", style: "margin-left: auto;" }, chk.result || "")
        )
      )
    );

    const continueBtn = el("div", { class: "tab-continue" },
      el("button", { type: "button", class: "btn primary", onclick: () => switchTab("report") }, "View full calculation report →")
    );

    const area = $("design-results-area");
    area.replaceChildren(badge, checksList, continueBtn);
    area.scrollIntoView({ behavior: "smooth", block: "nearest" });

    // Update report frame
    const frame = $("report-frame");
    if (frame) {
      frame.src = "/slab/report?embed=1";
    }
  } catch (err) {
    console.error(err);
    $("form-message").textContent = failureText(err, "the design checks");
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ------------------------------------------------------------------ Setup & Init

function setupAdjustDesignValues() {
  const chk = $("adjust-design-values");
  if (!chk) return;
  chk.addEventListener("change", (e) => {
    const adjust = e.target.checked;
    $("dv-ms").readOnly = !adjust;
    $("dv-mh").readOnly = !adjust;
    $("dv-ved").readOnly = !adjust;
    $("dv-msx-mid").readOnly = !adjust;
    $("dv-msx-sup").readOnly = !adjust;
    $("dv-msy-mid").readOnly = !adjust;
    $("dv-msy-sup").readOnly = !adjust;
    $("dv-tw-ved").readOnly = !adjust;
  });
}

function setupReportActions() {
  $("btn-pdf")?.addEventListener("click", async () => {
    const btn = $("btn-pdf");
    btn.disabled = true;
    try {
      const data = serialize();
      const res = await postJSON("/api/slab/report.pdf", data, { blob: true });
      if (res.ok) {
        const ref = (data.project?.ref || "slab").replace(/[^A-Za-z0-9_-]+/g, "-");
        downloadBlob(res.data, `EC2-slab-check-${ref}.pdf`);
      } else {
        alert("Failed to generate PDF. Make sure all checks are complete.");
      }
    } finally {
      btn.disabled = false;
    }
  });

  $("btn-print")?.addEventListener("click", () => {
    const frame = $("report-frame");
    if (frame?.contentWindow) frame.contentWindow.print();
  });
}

function initCanvas() {
  const host = $("slab-canvas");
  if (!host) return;

  editor = new CanvasEditor(host);
  canvas = new BeamCanvas(host, {
    onChange: ({ structural: big } = {}) => {
      if (big) {
        if (canvas.selected?.kind === "support" || canvas.drag?.kind === "support") markCustom();
        selected = canvas.selected;
        renderTables();
        refresh();
        markAnalysisDirty();
      } else {
        if (canvas.drag?.kind === "support") markCustom();
        refresh();
      }
    },
    onSelect: (sel) => pick(sel, false),
    onEdit: (sel, screenPoint) => editItem(sel, screenPoint),
    onLength: (L, oldL) => {
      // the green grip at the end of the beam was dragged: new length, supports at the end follow it
      resizeModel(model, oldL, L);
      const input = form.elements["span.l"];
      input.value = String(L);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    },
  });

  for (const button of document.querySelectorAll(".canvas-tools [data-tool]")) {
    button.addEventListener("click", () => {
      document.querySelectorAll(".canvas-tools [data-tool]").forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
      canvas.setTool(button.dataset.tool);
      $("canvas-delete").disabled = true;
      selected = null;
    });
  }

  $("canvas-delete")?.addEventListener("click", () => {
    if (!selected) return;
    if (selected.kind === "support") markCustom();
    canvas.select(selected);
    canvas.remove();
  });
}

function populateSelects() {
  for (const select of form.querySelectorAll("select[data-options]")) {
    const kind = select.dataset.options;
    let opts = [];
    if (kind === "concrete") opts = meta.concrete.map((c) => [c.name, c.name]);
    if (kind === "bars") opts = meta.bar_sizes.map((d) => [d, `H${d}`]);
    if (kind === "bars-or-none") opts = [["none", "None"], ...meta.bar_sizes.map((d) => [d, `H${d}`])];
    if (kind === "links-or-none") opts = [["none", "None"], ...meta.link_sizes.map((d) => [d, `H${d}`])];
    if (kind === "maxpans") opts = meta.maxpans.map((p) => [p.id, `${p.id} (${p.height} mm, ${p.mass.toFixed(2)} kg)`]);
    if (kind === "meshes-or-none") opts = [["none", "None"], ...meta.meshes.map((m) => [m.id, `${m.id} (${m.As} mm²/m)`])];
    if (kind === "exposure") opts = meta.exposure_all.map((r) => [r.id, `${r.classes}: ${r.example}`]);
    if (kind === "fire") opts = meta.fire_periods.map((p) => [p, p === "none" ? "None required" : p]);
    if (kind === "psi") opts = meta.psi_categories.map((c) => [c.id, `${c.id}: ${c.label} (ψ2 ${c.psi[2]})`]);
    select.replaceChildren(...opts.map(([v, l]) => option(v, l)));
  }
}

async function init() {
  meta = await getJSON("/api/meta");
  populateSelects();
  setupSections(form, "ec2.slab.sections");
  setupTabs();
  initCanvas();
  setupAdjustDesignValues();
  setupReportActions();

  // Edge dropdown events
  ["top", "bottom", "left", "right"].forEach((side) => {
    $(`edge-${side}`)?.addEventListener("change", () => {
      drawPanelPlan();
      markAnalysisDirty();
      scheduleAnalysis();
    });
  });

  // Slab type radio switch
  form.querySelectorAll('input[name="slab.type"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      if (radio.checked && radio.value === "ribbed") {
        if (!form.elements["slab.bw"].value) form.elements["slab.bw"].value = "150";
        if (!form.elements["slab.hf"].value) form.elements["slab.hf"].value = "50";
        if (!form.elements["reinforcement.bottom_n"].value) form.elements["reinforcement.bottom_n"].value = "2";
        if (!form.elements["reinforcement.bottom_dia"].value) form.elements["reinforcement.bottom_dia"].value = "10";
        if (!form.elements["reinforcement.top_n"].value) form.elements["reinforcement.top_n"].value = "2";
        if (!form.elements["reinforcement.top_dia"].value) form.elements["reinforcement.top_dia"].value = "10";
        if (!form.elements["reinforcement.link_dia"].value) form.elements["reinforcement.link_dia"].value = "none";
        if (!form.elements["reinforcement.mesh"].value) form.elements["reinforcement.mesh"].value = "A98";
      } else if (radio.checked && (radio.value === "one_way" || radio.value === "two_way")) {
        if (!form.elements["slab.h"].value) form.elements["slab.h"].value = radio.value === "two_way" ? "200" : "175";
      }
      syncVisibility();
      drawPanelPlan();
      updateStatsAndPreview();
      markAnalysisDirty();
      refresh();
    });
  });

  // Global keydown for Delete / Backspace when a canvas item or table row is selected
  document.addEventListener("keydown", (e) => {
    if ((e.key === "Delete" || e.key === "Backspace") && selected) {
      if (e.target?.closest?.("input, select, textarea")) return;
      e.preventDefault();
      if (selected.kind === "support") markCustom();
      if (canvas) {
        canvas.select(selected);
        canvas.remove();
      }
    }
  });

  let inputTimer = null;
  form.addEventListener("input", (e) => {
    updateStatsAndPreview();
    if (e.target.closest("#panel-analysis") && analysisDone) {
      analysisDirty = true;
      if ($("analysis-note")) $("analysis-note").textContent = "Inputs changed since last analysis: click Analyse to refresh";
    }
    if (e.target.dataset.path) {
      onTableInput(e);
      return;
    }
    clearTimeout(inputTimer);
    inputTimer = setTimeout(refresh, 90);
  });

  form.addEventListener("change", (e) => {
    if (e.target.closest("#panel-analysis") && analysisDone) {
      analysisDirty = true;
      if ($("analysis-note")) $("analysis-note").textContent = "Inputs changed since last analysis: click Analyse to refresh";
    }
    if (e.target.dataset.path) {
      if (e.target.tagName === "SELECT") onTableInput(e);
      return;
    }
    if (e.target.name === "span.preset" || e.target.name === "span.l") {
      if (valueOf("span.preset") !== "custom") applyPreset();
      else {
        const L = length();
        model.supports = model.supports.filter((sp) => sp.x <= L + 1e-9);
      }
      renderTables();
    }
    refresh();
  });

  $("btn-analyse")?.addEventListener("click", performAnalysis);
  $("btn-run-design")?.addEventListener("click", performDesignChecks);
  // the bar under the tabs: analyse first if needed, then run the checks and show them on the Design tab
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!analysisDone || analysisDirty) await performAnalysis();
    if ($("tab-design").getAttribute("aria-disabled") === "true") return;      // the analysis needs fixing first
    switchTab("design");
    await performDesignChecks();
  });
  fitFrame($("report-frame"));

  $("add-support")?.addEventListener("click", () => {
    const L = length();
    const xs = model.supports.map((sp) => sp.x);
    const x = xs.includes(L) ? r3(L / 2) : L;
    model.supports.push({ x, type: "roller" });
    model.supports.sort((a, b) => a.x - b.x);
    markCustom();
    structural();
  });

  $("add-load")?.addEventListener("click", () => {
    model.loads.push({ type: "point", case: "Ed", W: 10, x: r3(length() / 2) });
    selected = { kind: "load", index: model.loads.length - 1 };
    structural();
  });

  setupFilesMenu({
    examples: EXAMPLES,
    fill,
    errors,
    inputKey: KEYS.input,
    message: $("form-message"),
    resetTo: "one_way",
    looksValid: (x) => Boolean(x.slab && (x.span || x.panel)),
  });

  // Load stored input or initial example
  const stored = store.get(KEYS.input);
  fill(stored || structuredClone(EXAMPLES.one_way));

  // Handle URL hash on load
  const hash = location.hash.replace("#", "");
  if (TAB_NAMES.includes(hash)) {
    switchTab(hash);
  }
}

document.addEventListener("DOMContentLoaded", () => init().catch((err) => {
  $("form-message").textContent = failureText(err, "the page");
  console.error(err);
}));
