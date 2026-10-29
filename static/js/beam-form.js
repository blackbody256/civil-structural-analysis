import { el, getJSON, keysFor, postJSON, store } from "./common.js";
import { BeamCanvas, DEFAULT_LOAD } from "./beam-canvas.js";
import { CanvasEditor } from "./canvas-editor.js";
import { beamSectionFromInputs, drawBeamSection } from "./drawings.js";
import { renderFigure } from "./figure-spec.js";
import { formErrors, getPath, option, setPath, setupFilesMenu, setupSections } from "./form-kit.js";

const KEYS = keysFor("beam");
const PROJECT = { engineer: "", date: "" };
const MATERIALS = { fyk: 500, ductility: "B", dg: 20, gamma_c: 1.5, gamma_s: 1.15, alpha_cc: 0.85 };
const SLAB = { on: false, type: "one_way", gk: 5, qk: 2.5, trib: 3, lx: 4, ly: 6, sides: 1 };
const DIRECT = { M_sag: 150, M_hog: 0, VEd: 100 };
const OPTIONS = { partitions: false, kprime_limit: true };
const STIFF = { E_method: "concrete", E: 30, I_method: "section", segments: [] };

export const EXAMPLES = {
  // the client's example (the textbook beam his BeamViz Pro reproduces)
  analysis: {
    project: { name: "", ref: "", ...PROJECT },
    section: { shape: "rectangular", flange: "T", b: 400, h: 750, hf: 150, beff_method: "calculate", beff: 1500, b1: 1350, b2: 1350 },
    materials: { concrete: "C30/37", ...MATERIALS },
    span: { l: 20, preset: "custom", supports: [{ x: 0, type: "fixed" }, { x: 10, type: "roller" }, { x: 20, type: "roller" }] },
    reinforcement: { bottom_n: 4, bottom_dia: 20, bottom_layers: 1, top_n: 4, top_dia: 25, top_layers: 1, link_dia: 10, legs: 2,
      cover: 35, delta_c_dev: 10 },
    actions: {
      mode: "analysis", gk: 0, qk: 0, self_weight: false, category: "B", slab: { ...SLAB },
      loads: [
        { type: "linear", case: "Ed", w1: 30, w2: 0, x1: 0, x2: 6 },
        { type: "point", case: "Ed", W: 200, x: 6 },
        { type: "moment", case: "Ed", M: 90, x: 10 },
        { type: "point", case: "Ed", W: 150, x: 15 },
      ],
      ...DIRECT, ...OPTIONS,
    },
    stiffness: { E_method: "enter", E: 28, I_method: "enter",
      segments: [{ x1: 0, x2: 6, I: 8700 }, { x1: 6, x2: 20, I: 5800 }] },
    durability: { exposure: "XC1", cement_group: "All", fire_period: "R60" },
  },
  wrong: {
    project: { name: "", ref: "", ...PROJECT },
    section: { shape: "rectangular", flange: "T", b: 300, h: 500, hf: 150, beff_method: "calculate", beff: 1500, b1: 1350, b2: 1350 },
    materials: { concrete: "C25/30", ...MATERIALS },
    span: { l: 20, preset: "custom", supports: [{ x: 0, type: "fixed" }, { x: 10, type: "roller" }, { x: 20, type: "roller" }] },
    reinforcement: { bottom_n: 2, bottom_dia: 16, bottom_layers: 1, top_n: 2, top_dia: 16, top_layers: 1, link_dia: 6, legs: 2,
      cover: 25, delta_c_dev: 10 },
    actions: {
      mode: "analysis", gk: 0, qk: 0, self_weight: false, category: "B", slab: { ...SLAB },
      loads: [
        { type: "linear", case: "Ed", w1: 30, w2: 0, x1: 0, x2: 6 },
        { type: "point", case: "Ed", W: 200, x: 6 },
        { type: "moment", case: "Ed", M: 90, x: 10 },
        { type: "point", case: "Ed", W: 150, x: 15 },
      ],
      ...DIRECT, ...OPTIONS,
    },
    stiffness: { E_method: "enter", E: 28, I_method: "enter",
      segments: [{ x1: 0, x2: 6, I: 8700 }, { x1: 6, x2: 20, I: 5800 }] },
    durability: { exposure: "XC3/4-XF1", cement_group: "All except IVB", fire_period: "R90" },
  },
};

const PRESETS = {
  simple: (L) => [[0, "pin"], [L, "roller"]],
  cantilever: () => [[0, "fixed"]],
  propped: (L) => [[0, "fixed"], [L, "roller"]],
  fixed: (L) => [[0, "fixed"], [L, "fixed"]],
  two: (L) => [[0, "pin"], [L / 2, "roller"], [L, "roller"]],
  three: (L) => [[0, "pin"], [L / 3, "roller"], [(2 * L) / 3, "roller"], [L, "roller"]],
};
const SUPPORT_LABEL = { pin: "Pinned", roller: "Roller", fixed: "Fixed" };
const LOAD_LABEL = { point: "Point load", udl: "Uniform", linear: "Varying", moment: "Moment" };
const VALUE_KEY = { point: "W", udl: "w", linear: "w1", moment: "M" };
const UNIT = { point: "kN", udl: "kN/m", linear: "kN/m", moment: "kNm" };
const CASES = [["Ed", "Design"], ["G", "gk × 1.35"], ["Q", "qk × 1.5"]];
const NUMERIC = /^reinforcement\.(bottom_dia|top_dia|link_dia|legs|bottom_layers|top_layers|delta_c_dev)$|^actions\.slab\.sides$/;
const L0_FACTOR = { simple: 1.0, two: 0.85, three: 0.85, propped: 0.85, fixed: 0.7, cantilever: 1.0, custom: 0.85 };

const form = document.getElementById("beam-form");
const $ = (id) => document.getElementById(id);
const errors = formErrors(form, $("form-message"));
let meta = null;
let canvas = null;
let model = { supports: [], loads: [], segments: [] };
let selected = null;
let lastAnalysis = null;

const shape = () => form.querySelector('input[name="section.shape"]:checked')?.value || "rectangular";
const valueOf = (name) => form.elements[name]?.value;
const length = () => Number(valueOf("span.l")) || 0;
const r3 = (x) => Number(Number(x).toFixed(3));

function populate() {
  for (const select of form.querySelectorAll("select[data-options]")) {
    const kind = select.dataset.options;
    let opts = [];
    if (kind === "concrete") opts = meta.concrete.map((c) => [c.name, c.name]);
    if (kind === "bars") opts = meta.bar_sizes.map((d) => [d, `H${d}`]);
    if (kind === "links") opts = meta.link_sizes.map((d) => [d, `H${d}`]);
    if (kind === "exposure") opts = meta.exposure_all.map((r) => [r.id, `${r.classes}: ${r.example}`]);
    if (kind === "fire") opts = meta.fire_periods.map((p) => [p, p === "none" ? "None required" : p]);
    if (kind === "psi") opts = meta.psi_categories.map((c) => [c.id, `${c.id}: ${c.label} (ψ2 ${c.psi[2]})`]);
    select.replaceChildren(...opts.map(([v, l]) => option(v, l)));
  }
}

function show(selector, on) {
  form.querySelectorAll(selector).forEach((n) => { n.hidden = !on; });
}

function syncVisibility() {
  const flanged = shape() === "flanged";
  const method = valueOf("section.beff_method");
  show(".flanged-only", flanged);
  if (flanged) {
    show(".beff-enter", method === "enter");
    show(".beff-calc", method === "calculate");
    if (method === "calculate") show(".t-only", valueOf("section.flange") === "T");
  }
  $("g-b-label").textContent = flanged ? "Web width bw" : "Width b";
  const direct = valueOf("actions.mode") === "direct";
  show(".analysis-only", !direct);
  show(".direct-only", direct);
  const slabOn = form.elements["actions.slab.on"].checked;
  show(".slab-only", slabOn && !direct);
  const oneWay = valueOf("actions.slab.type") === "one_way";
  show(".one-way", oneWay);
  show(".two-way", !oneWay);
  show(".e-enter", valueOf("stiffness.E_method") === "enter");
  show(".i-enter", valueOf("stiffness.I_method") === "enter" && !direct);

  const exp = meta.exposure_all.find((r) => r.id === valueOf("durability.exposure"));
  const cem = form.elements["durability.cement_group"];
  if (exp) {
    const current = cem.value;
    cem.replaceChildren(...exp.groups.map((g) => option(g, g)));
    if (exp.groups.includes(current)) cem.value = current;
    $("exposure-help").textContent = exp.note || "";
  }
  const conc = meta.concrete.find((c) => c.name === valueOf("materials.concrete"));
  if (conc) {
    $("concrete-help").textContent = `fck ${conc.fck} MPa, fctm ${conc.fctm} MPa, Ecm ${conc.Ecm} GPa`;
    $("e-help").textContent = valueOf("stiffness.E_method") === "enter" ? "" : `Ecm = ${conc.Ecm} GPa`;
  }
  const b = Number(valueOf("section.b")), h = Number(valueOf("section.h"));
  $("i-help").textContent = valueOf("stiffness.I_method") === "section" && b > 0 && h > 0
    ? `Rectangle b·h³/12 = ${((b * h ** 3) / 12 / 1e6).toFixed(0)}×10⁶ mm⁴${shape() === "flanged" ? " (T-section with beff in the analysis)" : ""}` : "";
}

// ------------------------------------------------------------------ the tables

function cellInput(path, value, attrs = {}) {
  return el("div", { class: "control" }, el("input", { type: "number", step: "any", value: value ?? "", "data-path": path,
    "aria-label": attrs.label || path, ...attrs.extra }), attrs.unit ? el("span", { class: "unit" }, attrs.unit) : null);
}

function cellSelect(path, value, options, label) {
  const sel = el("select", { "data-path": path, "aria-label": label }, ...options.map(([v, l]) => option(v, l)));
  sel.value = value;
  return el("div", { class: "control" }, sel);
}

function removeButton(onClick, label) {
  const b = el("button", { type: "button", class: "btn-icon", "aria-label": label, title: label }, "×");
  b.addEventListener("click", onClick);
  return b;
}

function renderSupports() {
  const tbody = $("supports-table").tBodies[0];
  tbody.replaceChildren(...model.supports.map((sp, i) => {
    const row = el("tr", { class: selected?.kind === "support" && selected.index === i ? "is-selected" : "" },
      el("td", { class: "idx" }, String(i + 1)),
      el("td", {}, cellInput(`span.supports.${i}.x`, sp.x, { label: `Support ${i + 1} position`, unit: "m" })),
      el("td", {}, cellSelect(`span.supports.${i}.type`, sp.type, Object.entries(SUPPORT_LABEL), `Support ${i + 1} type`)),
      el("td", {}, removeButton(() => { model.supports.splice(i, 1); markCustom(); structural(); }, `Remove support ${i + 1}`)));
    row.addEventListener("click", (e) => { if (!e.target.closest("button")) pick({ kind: "support", index: i }, false); });
    return row;
  }));
}

function renderLoads() {
  const tbody = $("loads-table").tBodies[0];
  tbody.replaceChildren(...model.loads.map((ld, i) => {
    const p = `actions.loads.${i}`;
    const span = ld.type === "udl" || ld.type === "linear";
    const row = el("tr", { class: selected?.kind === "load" && selected.index === i ? "is-selected" : "" },
      el("td", {}, cellSelect(`${p}.type`, ld.type, Object.entries(LOAD_LABEL), `Load ${i + 1} type`)),
      el("td", {}, cellInput(`${p}.${VALUE_KEY[ld.type]}`, ld[VALUE_KEY[ld.type]], { label: `Load ${i + 1} value`, unit: UNIT[ld.type] })),
      el("td", {}, cellSelect(`${p}.case`, ld.case || "Ed", CASES, `Load ${i + 1} case`)),
      el("td", {}, cellInput(span ? `${p}.x1` : `${p}.x`, span ? ld.x1 : ld.x, { label: `Load ${i + 1} position` })),
      el("td", {}, span ? cellInput(`${p}.x2`, ld.x2, { label: `Load ${i + 1} end` }) : el("span", { class: "dash" }, "—")),
      el("td", {}, ld.type === "linear" ? cellInput(`${p}.w2`, ld.w2, { label: `Load ${i + 1} end value`, unit: "kN/m" })
        : el("span", { class: "dash" }, "—")),
      el("td", {}, removeButton(() => { model.loads.splice(i, 1); selected = null; structural(); }, `Remove load ${i + 1}`)));
    row.addEventListener("click", (e) => { if (!e.target.closest("button, select")) pick({ kind: "load", index: i }, false); });
    return row;
  }));
}

function renderSegments() {
  const tbody = $("segments-table").tBodies[0];
  tbody.replaceChildren(...model.segments.map((sg, i) => el("tr", {},
    el("td", {}, cellInput(`stiffness.segments.${i}.x1`, sg.x1, { label: `Part ${i + 1} from`, unit: "m" })),
    el("td", {}, cellInput(`stiffness.segments.${i}.x2`, sg.x2, { label: `Part ${i + 1} to`, unit: "m" })),
    el("td", {}, cellInput(`stiffness.segments.${i}.I`, sg.I, { label: `Part ${i + 1} I` })),
    el("td", {}, removeButton(() => { model.segments.splice(i, 1); structural(); }, `Remove part ${i + 1}`)))));
}

function renderTables() {
  renderSupports();
  renderLoads();
  renderSegments();
}

/** A value typed into a table cell. */
function onTableInput(event) {
  const path = event.target.dataset.path;
  if (!path) return;
  const parts = path.split(".");
  const index = Number(parts[parts.length - 2]);
  const key = parts[parts.length - 1];
  const list = path.startsWith("span.supports") ? model.supports : path.startsWith("actions.loads") ? model.loads : model.segments;
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

function changeLoadType(item, type) {
  const L = length();
  const at = item.x ?? item.x1 ?? 0;
  const value = item[VALUE_KEY[item.type]] ?? DEFAULT_LOAD[type][VALUE_KEY[type]];
  for (const k of ["W", "w", "w1", "w2", "M", "x", "x1", "x2"]) delete item[k];
  item.type = type;
  item[VALUE_KEY[type]] = value;
  if (type === "point" || type === "moment") item.x = at;
  else {
    item.x1 = Math.min(at, L * 0.8);
    item.x2 = r3(Math.min(L, item.x1 + L / 5));
    if (type === "linear") item.w2 = 0;
  }
}

function markCustom() {
  form.elements["span.preset"].value = "custom";
}

function applyPreset() {
  const preset = valueOf("span.preset");
  const L = length();
  if (!PRESETS[preset] || !(L > 0)) return;
  model.supports = PRESETS[preset](L).map(([x, type]) => ({ x: r3(x), type }));
}

/** Supports or loads were added, removed or retyped: redraw the tables too. */
function structural() {
  renderTables();
  refresh();
}

function pick(sel, fromCanvas = true) {
  selected = sel;
  $("canvas-delete").disabled = !sel;
  if (!fromCanvas && canvas) { canvas.selected = sel; canvas.render(); }
  for (const tr of form.querySelectorAll("#supports-table tbody tr, #loads-table tbody tr")) tr.classList.remove("is-selected");
  if (sel) {
    const table = sel.kind === "support" ? "supports-table" : "loads-table";
    $(table).tBodies[0].rows[sel.index]?.classList.add("is-selected");
  }
}

function focusItem(sel) {
  const section = form.querySelector(`details[data-section="${sel.kind === "support" ? "span" : "actions"}"]`);
  section.open = true;
  const table = sel.kind === "support" ? "supports-table" : "loads-table";
  const row = $(table).tBodies[0].rows[sel.index];
  const input = row?.querySelector(sel.kind === "support" ? "input" : "td:nth-child(2) input");
  if (input) { input.focus(); input.select(); row.scrollIntoView({ behavior: "smooth", block: "center" }); }
}

// ------------------------------------------------------------------ serialise / fill

export function serialize() {
  const data = {};
  for (const input of form.querySelectorAll("[name]")) {
    const path = input.name;
    if (input.type === "radio") { if (input.checked) setPath(data, path, input.value); }
    else if (input.type === "checkbox") setPath(data, path, input.checked);
    else if (input.type === "number") setPath(data, path, input.value === "" ? null : Number(input.value));
    else if (NUMERIC.test(path)) setPath(data, path, Number(input.value));
    else setPath(data, path, input.value);
  }
  data.span.supports = model.supports.map((sp) => ({ ...sp }));
  data.actions.loads = model.loads.map((ld) => ({ ...ld }));
  data.stiffness.segments = model.segments.map((sg) => ({ ...sg }));
  return data;
}

export function fill(data) {
  if (!data.span?.supports) data = structuredClone(EXAMPLES.analysis);
  for (const input of form.querySelectorAll("[name]")) {
    const value = getPath(data, input.name);
    if (input.type === "radio") input.checked = input.value === (value ?? "rectangular");
    else if (input.type === "checkbox") { if (value !== undefined) input.checked = Boolean(value); }
    else if (value !== undefined && value !== null) input.value = String(value);
    else if (value === null) input.value = "";
  }
  model = {
    supports: (data.span.supports || []).map((sp) => ({ ...sp })),
    loads: (data.actions?.loads || []).map((ld) => ({ ...ld })),
    segments: (data.stiffness?.segments || []).map((sg) => ({ ...sg })),
  };
  if (!data.span.preset) markCustom();
  if (data.stiffness?.E_method === "enter" || data.stiffness?.I_method === "enter") $("stiffness-more").open = true;
  selected = null;
  syncVisibility();
  if (data.durability?.cement_group) form.elements["durability.cement_group"].value = data.durability.cement_group;
  renderTables();
  refresh();
}

// ------------------------------------------------------------------ summaries and previews

function summaries(d) {
  const f = (x, unit = "") => (x === null || x === undefined || x === "" ? "?" : `${x}${unit}`);
  const s = d.section, re = d.reinforcement, a = d.actions, du = d.durability;
  const size = s.shape === "flanged" ? `${s.flange} beam, web ${f(s.b)} × ${f(s.h)} mm, hf ${f(s.hf)} mm` : `${f(s.b)} × ${f(s.h)} mm`;
  const sup = d.span.supports.map((sp) => `${sp.type[0].toUpperCase()}${sp.type.slice(1)} ${f(sp.x)}`).join(", ");
  const loads = a.mode === "direct" ? `M+Ed ${f(a.M_sag)} · M−Ed ${f(a.M_hog)} kNm · VEd ${f(a.VEd)} kN`
    : [`gk ${f(a.gk)}${a.self_weight ? " + self-weight" : ""}`, `qk ${f(a.qk)} kN/m`, a.slab.on ? "slab" : "",
      a.loads.length ? `${a.loads.length} further load${a.loads.length > 1 ? "s" : ""}` : ""].filter(Boolean).join(" · ");
  return {
    project: [d.project.name, d.project.ref].filter(Boolean).join(" · ") || "Optional",
    materials: `${d.materials.concrete} · fyk ${f(d.materials.fyk)} MPa · class ${d.materials.ductility} · dg ${f(d.materials.dg)} mm`,
    geometry: size,
    span: `L = ${f(d.span.l)} m · ${sup || "no supports"}`,
    reinforcement: `${f(re.bottom_n)}H${re.bottom_dia} bottom · ${f(re.top_n)}H${re.top_dia} top · H${re.link_dia} links, `
      + `${re.legs} legs · cover ${f(re.cover)} mm`,
    actions: loads,
    durability: `${(meta.exposure_all.find((r) => r.id === du.exposure) || {}).classes || du.exposure} · `
      + `${du.fire_period === "none" ? "no fire period" : `fire ${du.fire_period}`}`,
  };
}

function estimatedBeff(d) {
  const s = d.section;
  if (s.shape !== "flanged") return s.b;
  if (s.beff_method === "enter") return s.beff;
  const xs = d.span.supports.map((sp) => sp.x).sort((a, b) => a - b);
  const span = xs.length > 1 ? Math.max(...xs.slice(1).map((x, i) => x - xs[i])) : d.span.l;
  const l0 = (L0_FACTOR[d.span.preset] ?? 0.85) * span * 1000;
  return (s.flange === "T" ? [s.b1, s.b2] : [s.b1]).reduce((sum, bi) => sum + Math.min(0.2 * (bi || 0) + 0.1 * l0, 0.2 * l0, bi || 0), s.b);
}

function drawSectionPreview(d, serverSection) {
  const sec = beamSectionFromInputs({ ...d.section, ...d.reinforcement, beff: estimatedBeff(d), dg: d.materials.dg });
  drawBeamSection($("preview-section"), serverSection && sec ? { ...sec, beff: serverSection.beff } : sec);
  $("st-asb").textContent = sec ? `${sec.stats.bottom.As.toFixed(0)} mm²` : "—";
  $("st-ast").textContent = sec ? `${sec.stats.top.As.toFixed(0)} mm²` : "—";
  $("st-d").textContent = sec ? `${sec.stats.bottom.d.toFixed(0)} mm` : "—";
}

function refresh() {
  if (!meta) return;
  syncVisibility();
  const d = serialize();
  const text = summaries(d);
  for (const node of document.querySelectorAll("[data-sum]")) node.textContent = text[node.dataset.sum] ?? "";
  drawSectionPreview(d, lastAnalysis?.section);
  canvas.selected = selected;
  canvas.setModel({ length: Number(d.span.l) || 0, supports: model.supports, loads: d.actions.mode === "direct" ? [] : model.loads,
    w: d.actions.mode === "direct" ? 0 : lastAnalysis?.loads?.w || 0, slab: d.actions.slab?.on });
  scheduleAnalysis();
}

let analysisTimer = null;
let analysisRequest = 0;

function scheduleAnalysis() {
  clearTimeout(analysisTimer);
  analysisTimer = setTimeout(runAnalysis, 260);
}

async function runAnalysis() {
  const id = ++analysisRequest;
  const data = serialize();
  if (data.actions.mode === "direct") {
    lastAnalysis = null;
    $("preview-analysis").replaceChildren(el("p", { class: "empty-note" }, "Design actions are entered directly: nothing to analyse."));
    for (const k of ["st-w", "st-m", "st-v"]) $(k).textContent = "—";
    $("analysis-reactions").replaceChildren();
    $("slab-formula").textContent = "";
    return;
  }
  let res;
  try {
    res = await postJSON("/api/beam/analysis", data);
  } catch {
    return;
  }
  if (id !== analysisRequest) return;
  if (!res.ok) {
    const n = Object.keys(res.data?.errors || {}).length;
    $("analysis-hint").textContent = n ? `${n} input${n > 1 ? "s" : ""} to fix` : "not available";
    $("preview-analysis").replaceChildren(el("p", { class: "empty-note" },
      res.data?.errors?.["span.supports"] || "Complete the inputs to see the analysis."));
    return;
  }
  lastAnalysis = res.data;
  const a = res.data.analysis;
  $("analysis-hint").textContent = "live";
  renderFigure($("preview-analysis"), res.data.figures.diagrams, "Shear force and bending moment");
  const env = a.envelope, ld = res.data.loads;
  $("st-w").textContent = `${ld.w.toFixed(2)} kN/m`;
  $("st-m").textContent = `${env.sagging.M.toFixed(1)} / ${(-env.hogging.M).toFixed(1)}`;
  $("st-v").textContent = `${env.shear.V.toFixed(1)} kN`;
  $("analysis-reactions").replaceChildren(el("table", { class: "mini" },
    el("thead", {}, el("tr", {}, el("th", {}, "Support"), el("th", {}, "Ry (kN)"), el("th", {}, "M (kNm)"))),
    el("tbody", {}, a.reactions.map((r) => el("tr", {}, el("td", {}, `Node ${r.node} · ${r.x} m`),
      el("td", {}, r.Ry.toFixed(2)), el("td", {}, r.M === null ? "—" : r.M.toFixed(2)))))));
  const slab = ld.slab;
  $("slab-formula").textContent = slab
    ? `wslab = 1.35 gk + 1.5 qk = ${slab.w_area.toFixed(2)} kN/m²; on the beam ${(slab.w_area * slab.fm).toFixed(2)} kN/m for bending`
      + (Math.abs(slab.fm - slab.fv) > 1e-9 ? `, ${(slab.w_area * slab.fv).toFixed(2)} kN/m for shear` : "")
    : "";
  canvas.setModel({ ...canvas.model, w: ld.w });
  drawSectionPreview(data, res.data.section);
}

// ------------------------------------------------------------------ init

let canvasEditor = null;

function editItem(sel, screenPoint) {
  if (!sel || !canvasEditor) return;
  const list = sel.kind === "load" ? model.loads : model.supports;
  const item = list[sel.index];
  if (!item) return;
  const L = length() || 20;
  canvasEditor.open({
    selection: sel,
    item,
    length: L,
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

function setupCanvas() {
  canvasEditor = new CanvasEditor($("beam-canvas"));
  canvas = new BeamCanvas($("beam-canvas"), {
    onChange: ({ structural: big } = {}) => {
      if (big) {
        if (canvas.selected?.kind === "support" || canvas.drag?.kind === "support") markCustom();
        selected = canvas.selected;
        renderTables();
        refresh();
      } else {
        if (canvas.drag?.kind === "support") markCustom();
        refresh();
      }
    },
    onSelect: (sel) => pick(sel),
    onEdit: (sel, screenPoint) => editItem(sel, screenPoint),
  });
  for (const button of document.querySelectorAll(".canvas-tools [data-tool]")) {
    button.addEventListener("click", () => {
      document.querySelectorAll(".canvas-tools [data-tool]").forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
      canvas.setTool(button.dataset.tool);
      $("canvas-hint").textContent = button.dataset.tool === "select"
        ? "Click the beam to place; type the value in the box; drag to move; double-click to edit"
        : `Click on the beam to place: ${button.textContent.toLowerCase()}`;
    });
  }
  $("canvas-delete").addEventListener("click", () => canvas.remove());
}

async function init() {
  meta = await getJSON("/api/meta");
  populate();
  setupCanvas();
  setupSections(form, "ec2.beam.form.open.v2");
  fill(store.get(KEYS.input) || structuredClone(EXAMPLES.analysis));
  const serverErrors = store.getSession(KEYS.errors);
  if (serverErrors) { errors.show(serverErrors); store.setSession(KEYS.errors, null); }

  let timer = null;
  form.addEventListener("input", (e) => {
    if (e.target.dataset.path) { onTableInput(e); return; }
    clearTimeout(timer);
    timer = setTimeout(refresh, 90);
  });
  form.addEventListener("change", (e) => {
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
  $("add-support").addEventListener("click", () => {
    const L = length();
    const xs = model.supports.map((sp) => sp.x);
    const x = xs.includes(L) ? r3(L / 2) : L;
    model.supports.push({ x, type: "roller" });
    model.supports.sort((a, b) => a.x - b.x);
    markCustom();
    structural();
  });
  $("add-load").addEventListener("click", () => {
    model.loads.push({ type: "point", case: "Ed", W: 50, x: r3(length() / 2) });
    selected = { kind: "load", index: model.loads.length - 1 };
    structural();
    focusItem(selected);
  });
  $("add-segment").addEventListener("click", () => {
    const last = model.segments[model.segments.length - 1];
    const b = Number(valueOf("section.b")), h = Number(valueOf("section.h"));
    model.segments.push({ x1: last ? last.x2 : 0, x2: length(), I: last ? last.I : Math.round((b * h ** 3) / 12 / 1e6) });
    structural();
  });
  document.addEventListener("themechange", refresh);
  setupFilesMenu({
    examples: EXAMPLES, fill, errors, inputKey: KEYS.input, message: $("form-message"), resetTo: "analysis",
    looksValid: (x) => Boolean(x.section && x.span),
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    errors.clear();
    store.set(KEYS.input, serialize());
    store.setSession(KEYS.result, null);
    window.location.href = "/beam/run";
  });
}

init().catch((err) => {
  $("form-message").textContent = "Could not reach the server. Start it with: .venv/bin/python app.py";
  console.error(err);
});
