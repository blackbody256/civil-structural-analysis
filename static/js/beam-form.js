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

  const direct = valueOf("actions.mode") === "direct";
  show(".loads-only", !direct);
  show(".direct-only", direct);

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
  return data;
}

export function fill(data) {
  for (const input of form.querySelectorAll("[name]")) {
    const value = getPath(data, input.name);
    if (input.type === "radio") input.checked = input.value === (value ?? "rectangular");
    else if (input.type === "checkbox") { if (value !== undefined) input.checked = Boolean(value); }
    else if (value !== undefined) input.value = value === null ? "" : String(value);
  }
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
  return {
    project: [d.project.name, d.project.ref].filter(Boolean).join(" · ") || "Optional",
    materials: `${d.materials.concrete} · fyk ${f(d.materials.fyk)} MPa · class ${d.materials.ductility} · dg ${f(d.materials.dg)} mm`,
    geometry: `${size} · ${f(sp.l)} m ${SYSTEMS[sp.system]} · ${top ? "at the support" : "mid-span"}`,
    reinforcement: `${f(re.tension_n)}H${re.tension_dia} ${top ? "top" : "bottom"} · ${f(re.compression_n)}H${re.compression_dia} `
      + `${top ? "bottom" : "top"} · H${re.link_dia} links, ${re.legs} legs · cover ${f(re.cover)} mm`,
    actions: a.mode === "direct"
      ? `MEd ${f(a.MEd)} kNm · VEd ${f(a.VEd)} kN`
      : `gk ${f(a.gk)}${a.self_weight ? " + self-weight" : ""} · qk ${f(a.qk)} kN/m · category ${a.category}`,
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

/** Design load w for the drawing, by the same combination as the server. */
function designLoad(d) {
  const a = d.actions, s = d.section;
  if (a.mode === "direct" || !(a.gk >= 0) || !(a.qk >= 0)) return null;
  const web = s.shape === "flanged" ? s.b * (s.h - (s.hf || 0)) : s.b * s.h;
  const gk = a.gk + (a.self_weight && web > 0 ? (25 * web) / 1e6 : 0);
  if (a.combination === "6.10") return 1.35 * gk + 1.5 * a.qk;
  const psi0 = meta.psi_categories.find((c) => c.id === a.category)?.psi[0] ?? 0.7;
  return Math.max(1.35 * gk + 1.5 * psi0 * a.qk, 0.925 * 1.35 * gk + 1.5 * a.qk);
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
  drawBeamElevation($("preview-elevation"), { l: d.span.l > 0 ? d.span.l : 6, system: d.span.system, w });
  $("elev-hint").textContent = w ? "ULS design load" : "actions from your analysis";
}

// ------------------------------------------------------------------ init

async function init() {
  meta = await getJSON("/api/meta");
  populate();
  setupSections(form, "ec2.beam.form.open");
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
