import { getJSON, keysFor, store } from "./common.js";
import { beamSectionFromInputs, drawBeamElevation, drawBeamSection } from "./drawings.js";
import { formErrors, getPath, option, setPath, setupFilesMenu, setupSections } from "./form-kit.js";

const KEYS = keysFor("beam");
const PROJECT = { engineer: "", date: "" };
const MATERIALS = { fyk: 500, ductility: "B", dg: 20, gamma_c: 1.5, gamma_s: 1.15, alpha_cc: 0.85 };
const OPTIONS = { self_weight: true, category: "B", combination: "6.10ab", partitions: false, kprime_limit: true };

export const EXAMPLES = {
  pass: {
    project: { name: "Campus teaching block", ref: "B1 first floor", ...PROJECT },
    section: { shape: "rectangular", flange: "T", b: 300, h: 500, hf: 150, beff_method: "calculate", beff: 1500, b1: 1350, b2: 1350 },
    materials: { concrete: "C30/37", ...MATERIALS },
    span: { l: 6.0, system: "simple", location: "span" },
    reinforcement: { tension_n: 4, tension_dia: 20, layers: 1, compression_n: 2, compression_dia: 12, link_dia: 8, legs: 2,
      cover: 30, delta_c_dev: 10 },
    actions: { mode: "loads", gk: 15, qk: 10, MEd: 150, VEd: 100, ...OPTIONS },
    durability: { exposure: "XC1", cement_group: "All", fire_period: "R60" },
  },
  flanged: {
    project: { name: "Campus teaching block", ref: "B4 roof, end bay", ...PROJECT },
    section: { shape: "flanged", flange: "T", b: 300, h: 550, hf: 150, beff_method: "calculate", beff: 2000, b1: 1350, b2: 1350 },
    materials: { concrete: "C30/37", ...MATERIALS },
    span: { l: 7.0, system: "end", location: "span" },
    reinforcement: { tension_n: 4, tension_dia: 25, layers: 1, compression_n: 2, compression_dia: 16, link_dia: 8, legs: 2,
      cover: 30, delta_c_dev: 10 },
    actions: { mode: "loads", gk: 25, qk: 15, MEd: 250, VEd: 150, ...OPTIONS },
    durability: { exposure: "XC1", cement_group: "All", fire_period: "R60" },
  },
  fail: {
    project: { name: "Car park extension", ref: "B9 balcony cantilever", ...PROJECT },
    section: { shape: "rectangular", flange: "T", b: 250, h: 450, hf: 150, beff_method: "calculate", beff: 1200, b1: 1000, b2: 1000 },
    materials: { concrete: "C25/30", ...MATERIALS },
    span: { l: 3.0, system: "cantilever", location: "support" },
    reinforcement: { tension_n: 3, tension_dia: 20, layers: 1, compression_n: 2, compression_dia: 12, link_dia: 6, legs: 2,
      cover: 25, delta_c_dev: 10 },
    actions: { mode: "loads", gk: 20, qk: 15, MEd: 150, VEd: 100, ...OPTIONS, category: "C" },
    durability: { exposure: "XC3/4-XF1", cement_group: "All except IVB", fire_period: "R90" },
  },
  analysis: {
    project: { name: "Matrix analysis example", ref: "20m continuous beam with linear load", ...PROJECT },
    section: { shape: "rectangular", flange: "T", b: 400, h: 750, hf: 150, beff_method: "calculate", beff: 1500, b1: 1350, b2: 1350 },
    materials: { concrete: "C30/37", ...MATERIALS },
    span: { l: 20.0, system: "end", location: "span" },
    reinforcement: { tension_n: 4, tension_dia: 25, layers: 1, compression_n: 2, compression_dia: 16, link_dia: 10, legs: 2,
      cover: 35, delta_c_dev: 10 },
    actions: {
      mode: "analysis",
      loads: [
        { type: "linear", w1: 30, w2: 0, l1: 0.0, l2: 6.0 },
        { type: "point", W: 200, x: 6.0 },
        { type: "moment", M0: 90, x: 10.0 },
        { type: "point", W: 150, x: 15.0 }
      ],
      supports: [
        { x: 0.0, fix_v: 1, fix_m: 1 },
        { x: 10.0, fix_v: 1, fix_m: 0 },
        { x: 20.0, fix_v: 1, fix_m: 0 }
      ],
      inertia: [
        { x1: 0.0, x2: 6.0, I: 0.0087 },
        { x1: 6.0, x2: 20.0, I: 0.0058 }
      ],
      self_weight: false,
      has_slab: false,
      MEd: 251.1, VEd: 146.3, ...OPTIONS
    },
    durability: { exposure: "XC1", cement_group: "All", fire_period: "R60" },
  },
  slab: {
    project: { name: "Campus science block", ref: "B1 with two-way slab on Ly", ...PROJECT },
    section: { shape: "flanged", flange: "T", b: 300, h: 550, hf: 150, beff_method: "calculate", beff: 1500, b1: 1350, b2: 1350 },
    materials: { concrete: "C30/37", ...MATERIALS },
    span: { l: 6.0, system: "simple", location: "span" },
    reinforcement: { tension_n: 4, tension_dia: 20, layers: 1, compression_n: 2, compression_dia: 12, link_dia: 8, legs: 2,
      cover: 30, delta_c_dev: 10 },
    actions: {
      mode: "loads", gk: 5, qk: 2.5,
      has_slab: true, slab_type: "two_way_long",
      slab_gk: 4.0, slab_qk: 3.0, slab_lx: 4.0, slab_ly: 6.0, slab_trib: 3.0,
      self_weight: true, ...OPTIONS
    },
    durability: { exposure: "XC1", cement_group: "All", fire_period: "R60" },
  },
};

const SYSTEMS = { simple: "simply supported", end: "end span", interior: "interior span", cantilever: "cantilever" };
// distance between points of zero moment as a share of the span, for the effective flange width (as the server)
const L0_FACTOR = { simple: 1.0, end: 0.85, interior: 0.7, cantilever: 1.0 };
const NUMERIC = /^(reinforcement\.(tension_dia|compression_dia|link_dia|legs|layers|delta_c_dev))$/;

const form = document.getElementById("beam-form");
const $ = (id) => document.getElementById(id);
const errors = formErrors(form, $("form-message"));
let meta = null;

const shape = () => form.querySelector('input[name="section.shape"]:checked')?.value || "rectangular";
const valueOf = (name) => form.elements[name]?.value;

function populate() {
  for (const select of form.querySelectorAll("select[data-options]")) {
    const kind = select.dataset.options;
    let opts = [];
    if (kind === "concrete") opts = meta.concrete.map((c) => [c.name, c.name]);
    if (kind === "bars") opts = meta.bar_sizes.map((d) => [d, `H${d}`]);
    if (kind === "links") opts = meta.link_sizes.map((d) => [d, `H${d}`]);
    if (kind === "exposure") opts = meta.exposure_all.map((r) => [r.id, `${r.classes}: ${r.example}`]);
    if (kind === "fire") opts = meta.fire_periods.map((p) => [p, p === "none" ? "None required" : p]);
    if (kind === "psi") opts = meta.psi_categories.map((c) => [c.id, `${c.id}: ${c.label} (ψ0 ${c.psi[0]}, ψ2 ${c.psi[2]})`]);
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

  const mode = valueOf("actions.mode") || "loads";
  show(".loads-only", mode === "loads");
  show(".direct-only", mode === "direct");
  show(".analysis-only", mode === "analysis");
  show(".not-direct", mode !== "direct");

  // a simply supported span has no support moment; a cantilever is checked at its root
  const system = valueOf("span.system");
  const loc = form.elements["span.location"];
  loc.querySelector('[value="support"]').disabled = system === "simple";
  loc.querySelector('[value="span"]').disabled = system === "cantilever";
  if (system === "simple") loc.value = "span";
  if (system === "cantilever") loc.value = "support";
  $("loc-help").textContent = {
    simple: "Only mid-span applies to a simply supported beam",
    cantilever: "A cantilever is checked at its support",
  }[system] || "Check each critical section in turn";
  const top = loc.value === "support";
  $("r-tn-label").textContent = `Tension bars (${top ? "top" : "bottom"})`;
  $("r-cn-label").textContent = `Compression bars (${top ? "bottom" : "top"})`;

  const exp = meta.exposure_all.find((r) => r.id === valueOf("durability.exposure"));
  const cem = form.elements["durability.cement_group"];
  if (exp) {
    const current = cem.value;
    cem.replaceChildren(...exp.groups.map((g) => option(g, g)));
    if (exp.groups.includes(current)) cem.value = current;
    $("exposure-help").textContent = exp.note || "";
  }
  const conc = meta.concrete.find((c) => c.name === valueOf("materials.concrete"));
  if (conc) $("concrete-help").textContent = `fck ${conc.fck} MPa, fctm ${conc.fctm} MPa, Ecm ${conc.Ecm} GPa`;

  const hasSlab = form.elements["actions.has_slab"]?.checked || false;
  const slabOpts = $("slab-options");
  if (slabOpts) {
    slabOpts.style.display = hasSlab ? "grid" : "none";
    const slabType = valueOf("actions.slab_type") || "one_way";
    form.querySelectorAll(".slab-oneway-only").forEach((el) => { el.style.display = slabType === "one_way" ? "block" : "none"; });
    form.querySelectorAll(".slab-twoway-only").forEach((el) => { el.style.display = slabType.startsWith("two_way") ? "block" : "none"; });

    const sgk = parseFloat(valueOf("actions.slab_gk")) || 0;
    const sqk = parseFloat(valueOf("actions.slab_qk")) || 0;
    const wSlab = 1.35 * sgk + 1.5 * sqk;
    const lx = parseFloat(valueOf("actions.slab_lx")) || (parseFloat(valueOf("span.l")) || 4.0);
    const ly = parseFloat(valueOf("actions.slab_ly")) || (parseFloat(valueOf("span.l")) || 6.0);
    const trib = parseFloat(valueOf("actions.slab_trib")) || (lx / 2.0);

    let weqM = 0, weqV = 0, formulaStr = "";
    if (slabType === "one_way") {
      weqM = wSlab * trib;
      weqV = wSlab * trib;
      formulaStr = `w_slab = 1.35·${sgk.toFixed(1)} + 1.5·${sqk.toFixed(1)} = ${wSlab.toFixed(2)} kN/m² | w = w_slab × b_trib (${trib.toFixed(2)} m)`;
    } else if (slabType === "two_way_long") {
      const r = Math.min(1.0, Math.max(0.01, lx / ly));
      weqM = wSlab * (lx / 6.0) * (3.0 - r * r);
      weqV = wSlab * (lx / 4.0) * (2.0 - r);
      formulaStr = `w_eq,M = w_slab × (Lx/6)·[3 - (Lx/Ly)²] | w_eq,V = w_slab × (Lx/4)·[2 - Lx/Ly]`;
    } else {
      weqM = wSlab * (lx / 3.0);
      weqV = wSlab * (lx / 4.0);
      formulaStr = `w_eq,M = w_slab × (Lx/3) | w_eq,V = w_slab × (Lx/4)`;
    }
    const fEl = $("slab-calc-formula");
    if (fEl) fEl.textContent = formulaStr;
    const rEl = $("slab-calc-results");
    if (rEl) rEl.textContent = `w_slab = ${wSlab.toFixed(2)} kN/m² → Equivalent UDL: Moment weq = ${weqM.toFixed(2)} kN/m, Shear weq = ${weqV.toFixed(2)} kN/m`;
  }
}

// ------------------------------------------------------------------ loads table

let analysisLoads = [
  { type: "point", W: 50, x: 3.0 },
  { type: "udl", w: 12, l1: 0.0, l2: 6.0 }
];
let analysisSupports = null;
let analysisInertia = null;

function renderLoadsTable() {
  const tbody = $("loads-body");
  if (!tbody) return;
  tbody.replaceChildren();

  analysisLoads.forEach((ld, idx) => {
    const tr = document.createElement("tr");

    // Type select
    const tdType = document.createElement("td");
    const cType = document.createElement("div");
    cType.className = "control";
    const sType = document.createElement("select");
    sType.innerHTML = `
      <option value="point">Point load (kN)</option>
      <option value="udl">Partial UDL (kN/m)</option>
      <option value="moment">Moment (kNm)</option>
      <option value="linear">Varying (kN/m)</option>
    `;
    sType.value = ld.type || "point";
    sType.addEventListener("change", () => {
      ld.type = sType.value;
      renderLoadsTable();
      refresh();
    });
    cType.appendChild(sType);
    tdType.appendChild(cType);

    // Magnitude
    const tdMag = document.createElement("td");
    const cMag = document.createElement("div");
    cMag.className = "control";
    const iMag = document.createElement("input");
    iMag.type = "number";
    iMag.step = "0.5";
    iMag.placeholder = ld.type === "linear" ? "Start w₁" : (ld.type === "moment" ? "M₀" : "Load");
    iMag.value = ld.type === "linear" ? (ld.w1 ?? 0) : (ld.type === "udl" ? (ld.w ?? 0) : (ld.type === "moment" ? (ld.M0 ?? 0) : (ld.W ?? 0)));
    iMag.addEventListener("input", () => {
      const val = parseFloat(iMag.value) || 0;
      if (ld.type === "linear") ld.w1 = val;
      else if (ld.type === "udl") ld.w = val;
      else if (ld.type === "moment") ld.M0 = val;
      else ld.W = val;
      refresh();
    });
    cMag.appendChild(iMag);
    tdMag.appendChild(cMag);

    // Position x1
    const tdX1 = document.createElement("td");
    const cX1 = document.createElement("div");
    cX1.className = "control";
    const iX1 = document.createElement("input");
    iX1.type = "number";
    iX1.step = "0.1";
    iX1.placeholder = (ld.type === "udl" || ld.type === "linear") ? "Start x₁" : "Position x";
    iX1.value = (ld.type === "udl" || ld.type === "linear") ? (ld.l1 ?? 0) : (ld.x ?? 0);
    iX1.addEventListener("input", () => {
      const val = parseFloat(iX1.value) || 0;
      if (ld.type === "udl" || ld.type === "linear") ld.l1 = val;
      else ld.x = val;
      refresh();
    });
    cX1.appendChild(iX1);
    tdX1.appendChild(cX1);

    // End x2 or w2
    const tdX2 = document.createElement("td");
    const cX2 = document.createElement("div");
    cX2.className = "control";
    const iX2 = document.createElement("input");
    iX2.type = "number";
    iX2.step = "0.1";
    if (ld.type === "linear") {
      iX2.placeholder = "End w₂";
      iX2.value = ld.w2 ?? 0;
      iX2.addEventListener("input", () => {
        ld.w2 = parseFloat(iX2.value) || 0;
        refresh();
      });
    } else if (ld.type === "udl") {
      iX2.placeholder = "End x₂";
      iX2.value = ld.l2 ?? (parseFloat(valueOf("span.l")) || 6.0);
      iX2.addEventListener("input", () => {
        ld.l2 = parseFloat(iX2.value) || 0;
        refresh();
      });
    } else {
      iX2.disabled = true;
      iX2.placeholder = "—";
      iX2.value = "";
    }
    cX2.appendChild(iX2);
    tdX2.appendChild(cX2);

    // Remove button
    const tdDel = document.createElement("td");
    const bDel = document.createElement("button");
    bDel.type = "button";
    bDel.className = "btn-icon";
    bDel.textContent = "×";
    bDel.title = "Delete load";
    bDel.addEventListener("click", () => {
      analysisLoads.splice(idx, 1);
      renderLoadsTable();
      refresh();
    });
    tdDel.appendChild(bDel);

    tr.append(tdType, tdMag, tdX1, tdX2, tdDel);
    tbody.appendChild(tr);
  });
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
  if (data.actions && data.actions.mode === "analysis") {
    data.actions.loads = analysisLoads.map((ld) => ({ ...ld }));
    if (analysisSupports) data.actions.supports = analysisSupports.map((sp) => ({ ...sp }));
    if (analysisInertia) data.actions.inertia = analysisInertia.map((it) => ({ ...it }));
  }
  return data;
}

export function fill(data) {
  for (const input of form.querySelectorAll("[name]")) {
    const value = getPath(data, input.name);
    if (input.type === "radio") input.checked = input.value === (value ?? "rectangular");
    else if (input.type === "checkbox") { if (value !== undefined) input.checked = Boolean(value); }
    else if (value !== undefined) input.value = value === null ? "" : String(value);
  }
  if (data.actions?.loads && Array.isArray(data.actions.loads)) {
    analysisLoads = data.actions.loads.map((ld) => ({ ...ld }));
  }
  analysisSupports = data.actions?.supports ? data.actions.supports.map((sp) => ({ ...sp })) : null;
  analysisInertia = data.actions?.inertia ? data.actions.inertia.map((it) => ({ ...it })) : null;
  renderLoadsTable();
  syncVisibility();
  if (data.durability?.cement_group) form.elements["durability.cement_group"].value = data.durability.cement_group;
  refresh();
}

// ------------------------------------------------------------------ section summaries

function summaries(d) {
  const f = (x, unit = "") => (x === null || x === undefined || x === "" ? "?" : `${x}${unit}`);
  const s = d.section, sp = d.span, re = d.reinforcement, a = d.actions, du = d.durability;
  const top = sp.location === "support";
  const size = s.shape === "flanged"
    ? `${s.flange} beam, web ${f(s.b)} × ${f(s.h)} mm, hf ${f(s.hf)} mm`
    : `${f(s.b)} × ${f(s.h)} mm`;
  const actText = a.mode === "direct"
    ? `MEd ${f(a.MEd, " kNm")} · VEd ${f(a.VEd, " kN")}`
    : (a.mode === "analysis"
      ? `FEA analysis: ${analysisLoads.length} load${analysisLoads.length === 1 ? "" : "s"}${a.self_weight ? " + sw" : ""}`
      : `gk ${f(a.gk)}${a.self_weight ? " + self-weight" : ""} · qk ${f(a.qk)} kN/m · category ${a.category}`);
  return {
    project: [d.project.name, d.project.ref].filter(Boolean).join(" · ") || "Optional",
    materials: `${d.materials.concrete} · fyk ${f(d.materials.fyk)} MPa · class ${d.materials.ductility} · dg ${f(d.materials.dg)} mm`,
    geometry: `${size} · ${f(sp.l)} m ${SYSTEMS[sp.system]} · ${top ? "at the support" : "mid-span"}`,
    reinforcement: `${f(re.tension_n)}H${re.tension_dia} ${top ? "top" : "bottom"} · ${f(re.compression_n)}H${re.compression_dia} `
      + `${top ? "bottom" : "top"} · H${re.link_dia} links, ${re.legs} legs · cover ${f(re.cover)} mm`,
    actions: actText,
    durability: `${(meta.exposure_all.find((r) => r.id === du.exposure) || {}).classes || du.exposure} · `
      + `${du.fire_period === "none" ? "no fire period" : `fire ${du.fire_period}`}`,
  };
}

// ------------------------------------------------------------------ preview

/** Effective flange width from the beam spacing, as the server works it out. */
function effectiveWidth(d) {
  const s = d.section;
  if (s.shape !== "flanged") return s.b;
  if (s.beff_method === "enter") return s.beff;
  const l0 = L0_FACTOR[d.span.system] * (d.span.l || 0) * 1000;
  return (s.flange === "T" ? [s.b1, s.b2] : [s.b1])
    .reduce((sum, bi) => sum + Math.min(0.2 * (bi || 0) + 0.1 * l0, 0.2 * l0, bi || 0), s.b);
}

/** Design load w for the drawing, strictly G = 1.35 gk and Q = 1.5 qk without 0.925. */
function designLoad(d) {
  const a = d.actions, s = d.section;
  if (a.mode === "direct") return null;
  const web = s.shape === "flanged" ? s.b * (s.h - (s.hf || 0)) : s.b * s.h;
  const sw = a.self_weight && web > 0 ? (25 * web) / 1e6 : 0;
  const gk = (a.gk || 0) + sw;
  let w = 1.35 * gk + 1.5 * (a.qk || 0);
  if (a.has_slab) {
    const wSlab = 1.35 * (a.slab_gk || 0) + 1.5 * (a.slab_qk || 0);
    const lx = a.slab_lx || d.span.l || 4.0;
    const ly = a.slab_ly || d.span.l || 6.0;
    if (a.slab_type === "one_way") {
      const trib = a.slab_trib || (lx / 2.0);
      w += wSlab * trib;
    } else if (a.slab_type === "two_way_long") {
      const r = Math.min(1.0, Math.max(0.01, lx / ly));
      w += wSlab * (lx / 6.0) * (3.0 - r * r);
    } else {
      w += wSlab * (lx / 3.0);
    }
  }
  return w > 0 ? w : null;
}

function refresh() {
  if (!meta) return;
  syncVisibility();
  const d = serialize();
  const text = summaries(d);
  for (const node of document.querySelectorAll("[data-sum]")) node.textContent = text[node.dataset.sum] ?? "";

  const sec = beamSectionFromInputs({
    ...d.section, ...d.reinforcement, beff: effectiveWidth(d), dg: d.materials.dg, location: d.span.location,
  });
  drawBeamSection($("preview-section"), sec);
  $("st-as").textContent = sec ? `${sec.As.toFixed(0)} mm²` : "—";
  $("st-d").textContent = sec ? `${sec.d.toFixed(0)} mm` : "—";
  $("st-gap").textContent = sec ? `${sec.clear.toFixed(0)} mm` : "—";

  const w = designLoad(d);
  drawBeamElevation($("preview-elevation"), {
    l: d.span.l > 0 ? d.span.l : 6,
    system: d.span.system,
    w,
    loads: d.actions?.mode === "analysis" ? analysisLoads : null,
    supports: d.actions?.mode === "analysis" ? analysisSupports : null
  });
  $("elev-hint").textContent = d.actions?.mode === "analysis"
    ? "Matrix FEA applied loads"
    : (w ? "ULS design load" : "actions from your analysis");
}

// ------------------------------------------------------------------ init

async function init() {
  meta = await getJSON("/api/meta");
  populate();
  setupSections(form, "ec2.beam.form.open");
  $("add-load-btn")?.addEventListener("click", () => {
    const span = parseFloat(valueOf("span.l")) || 6.0;
    analysisLoads.push({ type: "point", W: 40, x: +(span / 2).toFixed(2) });
    renderLoadsTable();
    refresh();
  });
  fill(store.get(KEYS.input) || structuredClone(EXAMPLES.pass));
  const serverErrors = store.getSession(KEYS.errors);
  if (serverErrors) { errors.show(serverErrors); store.setSession(KEYS.errors, null); }

  let timer = null;
  form.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(refresh, 90); });
  form.addEventListener("change", refresh);
  document.addEventListener("themechange", refresh);
  setupFilesMenu({
    examples: EXAMPLES, fill, errors, inputKey: KEYS.input, message: $("form-message"), looksValid: (x) => Boolean(x.section && x.span),
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
