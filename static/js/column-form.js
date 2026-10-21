import { el, getJSON, KEYS, postJSON, store } from "./common.js";
import { drawElevation, drawSection, endKinds, sectionFromInputs } from "./drawings.js";

export const EXAMPLES = {
  pass: {
    project: { name: "Campus teaching block", ref: "C2 ground floor", engineer: "", date: "" },
    materials: { concrete: "C32/40", fyk: 500, ductility: "B", dg: 20, gamma_c: 1.5, gamma_s: 1.15, alpha_cc: 0.85 },
    geometry: { b: 350, h: 350, l: 3.6 },
    reinforcement: { bar_dia: 20, n_b: 3, n_h: 3, link_dia: 8, link_spacing: 200, link_spacing_mid: 300,
      cross_ties: false, cover: 30, delta_c_dev: 10 },
    restraint: { braced: true, y: { method: "k", k_top: 0.25, k_bottom: 0.1 }, z: { method: "k", k_top: 0.25, k_bottom: 0.1 } },
    actions: { NEd: 2100, My_top: 45, My_bottom: 25, My_curvature: "single", Mz_top: 20, Mz_bottom: 10,
      Mz_curvature: "single", phi_ef: 1.7, lambda_lim_method: "simplified" },
    durability: { exposure: "XC1", cement_group: "All", fire_period: "R60", fire_exposure: "multi", mu_fi: 0.7, floor: "intermediate" },
  },
  fail: {
    project: { name: "Car park extension", ref: "C7 level 1", engineer: "", date: "" },
    materials: { concrete: "C25/30", fyk: 500, ductility: "B", dg: 20, gamma_c: 1.5, gamma_s: 1.15, alpha_cc: 0.85 },
    geometry: { b: 250, h: 400, l: 4.5 },
    reinforcement: { bar_dia: 25, n_b: 2, n_h: 3, link_dia: 6, link_spacing: 250, link_spacing_mid: null,
      cross_ties: false, cover: 25, delta_c_dev: 10 },
    restraint: { braced: true, y: { method: "k", k_top: 0.6, k_bottom: 0.4 }, z: { method: "factor", case: "c", F: 0.7 } },
    actions: { NEd: 1650, My_top: 95, My_bottom: 60, My_curvature: "single", Mz_top: 30, Mz_bottom: 15,
      Mz_curvature: "single", phi_ef: 2.0, lambda_lim_method: "simplified" },
    durability: { exposure: "XC3/4-XF1", cement_group: "All except IVB", fire_period: "R90", fire_exposure: "multi", mu_fi: 0.7, floor: "intermediate" },
  },
};

const AXES = ["y", "z"];
const form = document.getElementById("column-form");
let meta = null;
let previewAxis = "y";

// ------------------------------------------------------------------ nested values

function setPath(obj, path, value) {
  const keys = path.split(".");
  let node = obj;
  keys.slice(0, -1).forEach((k) => { node = node[k] ??= {}; });
  node[keys[keys.length - 1]] = value;
}

function getPath(obj, path) {
  return path.split(".").reduce((node, k) => (node == null ? undefined : node[k]), obj);
}

// ------------------------------------------------------------------ building the form

function option(value, label, selected) {
  return el("option", { value, selected: selected ? true : null }, label);
}

function populate() {
  for (const select of form.querySelectorAll("select[data-options]")) {
    const kind = select.dataset.options;
    let opts = [];
    if (kind === "concrete") opts = meta.concrete.map((c) => [c.name, `${c.name}  (fck ${c.fck} MPa)`]);
    if (kind === "bars") opts = meta.bar_sizes.map((d) => [d, `H${d}`]);
    if (kind === "links") opts = meta.link_sizes.map((d) => [d, `H${d}`]);
    if (kind === "exposure") opts = meta.exposure.map((r) => [r.id, `${r.classes}: ${r.example}`]);
    if (kind === "fire") opts = meta.fire_periods.map((p) => [p, p === "none" ? "None required" : p]);
    if (kind === "psi") opts = meta.psi_categories.map((c) => [c.id, `${c.id}: ${c.label} (ψ0 ${c.psi[0]}, ψ2 ${c.psi[2]})`]);
    select.replaceChildren(...opts.map(([v, l]) => option(v, l)));
  }
}

function kControl(axis, end, label) {
  const name = `restraint.${axis}.${end}`;
  const preset = el("select", { "data-kfor": name, "aria-label": `${label} preset` },
    option("pinned", "Pinned"), option("0.1", "Fixed (0.1)"), option("custom", "Custom"));
  const input = el("input", { name, type: "number", step: "0.01", min: "0", max: "1000000", "aria-label": label });
  preset.addEventListener("change", () => {
    if (preset.value === "pinned") input.value = "";
    if (preset.value === "0.1") input.value = "0.1";
    input.disabled = preset.value !== "custom";
    if (preset.value === "custom") input.focus();
    refresh();
  });
  return el("div", { class: "field k-only" }, el("label", {}, label), el("div", { class: "control" }, preset, input));
}

function axisBlock(axis) {
  const name = (k) => `restraint.${axis}.${k}`;
  const caseSelect = el("select", { name: name("case"), "aria-label": "Figure 5 case" },
    ...meta.fig5_cases.map((c) => option(c.id, `${c.id}) ${c.label}: F = ${c.F}`)), option("", "Custom F"));
  const factor = el("input", { name: name("F"), type: "number", step: "0.01", min: "0.3", max: "5" });
  caseSelect.addEventListener("change", () => {
    const c = meta.fig5_cases.find((x) => x.id === caseSelect.value);
    if (c) factor.value = c.F;
    refresh();
  });
  const radios = ["k", "factor"].map((m) => el("label", {},
    el("input", { type: "radio", name: name("method"), value: m, checked: m === "k" ? true : null }),
    m === "k" ? " End stiffness k (Table 4)" : " Factor F (Fig 5)"));
  return el("div", { class: "axis-block", "data-axis": axis },
    el("div", { class: "axis-name" }, axis === "y" ? "About y–y (bending across h)" : "About z–z (bending across b)"),
    el("div", { class: "fields" },
      el("div", { class: "field" }, el("span", { class: "label" }, "Method"), el("div", { class: "segmented" }, ...radios)),
      kControl(axis, "k_top", "Top end k₁"),
      kControl(axis, "k_bottom", "Bottom end k₂"),
      el("div", { class: "field f-only" }, el("label", {}, "Fig 5 case"), el("div", { class: "control" }, caseSelect)),
      el("div", { class: "field f-only" }, el("label", {}, "F = l₀/l"), el("div", { class: "control" }, factor))));
}

function buildRestraint() {
  document.getElementById("restraint-axes").replaceChildren(...AXES.map(axisBlock));
}

function syncVisibility() {
  const same = document.getElementById("same-axes").checked;
  for (const block of form.querySelectorAll(".axis-block")) {
    const axis = block.dataset.axis;
    block.hidden = same && axis === "z";
    const method = form.querySelector(`input[name="restraint.${axis}.method"]:checked`)?.value || "k";
    block.querySelectorAll(".k-only").forEach((n) => { n.hidden = method !== "k"; });
    block.querySelectorAll(".f-only").forEach((n) => { n.hidden = method !== "factor"; });
  }
  const yAxisName = form.querySelector('.axis-block[data-axis="y"] .axis-name');
  if (yAxisName) yAxisName.textContent = same ? "Both axes" : "About y–y (bending across h)";
  const exp = meta.exposure.find((r) => r.id === form.elements["durability.exposure"].value);
  const cem = form.elements["durability.cement_group"];
  if (exp) {
    const current = cem.value;
    cem.replaceChildren(...exp.groups.map((g) => option(g, g)));
    if (exp.groups.includes(current)) cem.value = current;
    document.getElementById("exposure-help").textContent = exp.note || "";
  }
  const conc = meta.concrete.find((c) => c.name === form.elements["materials.concrete"].value);
  if (conc) document.getElementById("concrete-help").textContent =
    `fck,cube ${conc.fck_cube} MPa · fctm ${conc.fctm} MPa · Ecm ${conc.Ecm} GPa`;
  const fire = form.elements["durability.fire_period"].value !== "none";
  ["durability.fire_exposure", "durability.mu_fi", "durability.floor"].forEach((n) => { form.elements[n].disabled = !fire; });
}

// ------------------------------------------------------------------ serialise / fill

const NUMERIC = new Set(["number"]);

export function serialize() {
  const data = {};
  for (const input of form.querySelectorAll("[name]")) {
    if (input.disabled && !input.name.includes(".k_")) continue;
    const path = input.name;
    if (input.type === "radio") {
      if (!input.checked) continue;
      setPath(data, path, input.value === "true" ? true : input.value === "false" ? false : input.value);
    } else if (input.type === "checkbox") {
      setPath(data, path, input.checked);
    } else if (NUMERIC.has(input.type)) {
      setPath(data, path, input.value === "" ? null : Number(input.value));
    } else if (input.tagName === "SELECT" && /^(reinforcement\.(bar_dia|link_dia|delta_c_dev)|durability\.mu_fi)$/.test(path)) {
      setPath(data, path, Number(input.value));
    } else {
      setPath(data, path, input.value);
    }
  }
  for (const preset of form.querySelectorAll("select[data-kfor]")) {
    if (preset.value === "pinned") setPath(data, preset.dataset.kfor, "pinned");
  }
  if (document.getElementById("same-axes").checked) data.restraint.z = structuredClone(data.restraint.y);
  for (const axis of AXES) {
    const r = data.restraint[axis];
    if (r.method === "factor") { delete r.k_top; delete r.k_bottom; } else { delete r.case; delete r.F; }
  }
  return data;
}

export function fill(data) {
  for (const input of form.querySelectorAll("[name]")) {
    const value = getPath(data, input.name);
    if (input.type === "radio") input.checked = String(value) === input.value;
    else if (input.type === "checkbox") input.checked = Boolean(value);
    else if (value !== undefined) input.value = value ?? "";
  }
  for (const preset of form.querySelectorAll("select[data-kfor]")) {
    const value = getPath(data, preset.dataset.kfor);
    const input = form.elements[preset.dataset.kfor];
    if (value === "pinned" || value === null || value === undefined) {
      preset.value = "pinned"; input.value = ""; input.disabled = true;
    } else if (Number(value) === 0.1) {
      preset.value = "0.1"; input.value = "0.1"; input.disabled = true;
    } else {
      preset.value = "custom"; input.disabled = false;
    }
  }
  const r = data.restraint || {};
  document.getElementById("same-axes").checked = JSON.stringify(r.y) === JSON.stringify(r.z);
  syncVisibility();
  if (data.durability?.cement_group) form.elements["durability.cement_group"].value = data.durability.cement_group;
  refresh();
}

// ------------------------------------------------------------------ preview

function values() {
  const v = (n) => Number(form.elements[n]?.value);
  return {
    b: v("geometry.b"), h: v("geometry.h"), l: v("geometry.l") * 1000, cover: v("reinforcement.cover"),
    link_dia: v("reinforcement.link_dia"), bar_dia: v("reinforcement.bar_dia"),
    n_b: Math.round(v("reinforcement.n_b")), n_h: Math.round(v("reinforcement.n_h")),
    spacing: v("reinforcement.link_spacing"), NEd: v("actions.NEd"),
  };
}

function refresh() {
  if (!meta) return;
  syncVisibility();
  const v = values();
  const sec = sectionFromInputs(v);
  drawSection(document.getElementById("preview-section"), sec,
    { linkLabel: `H${v.link_dia} @ ${Number.isFinite(v.spacing) ? v.spacing : "?"}` });
  if (sec) {
    const as = sec.bars.length * Math.PI * sec.bar_dia ** 2 / 4;
    const gapB = (sec.b - 2 * sec.a) / (sec.n_b - 1) - sec.bar_dia;
    const gapH = (sec.h - 2 * sec.a) / (sec.n_h - 1) - sec.bar_dia;
    document.getElementById("st-as").textContent = `${as.toFixed(0)} mm²`;
    document.getElementById("st-rho").textContent = `${(100 * as / (sec.b * sec.h)).toFixed(2)} %`;
    document.getElementById("st-gap").textContent = `${Math.min(gapB, gapH).toFixed(0)} mm`;
  } else {
    ["st-as", "st-rho", "st-gap"].forEach((id) => { document.getElementById(id).textContent = "—"; });
  }
  let r;
  try { r = serialize().restraint?.[previewAxis]; } catch { r = null; }
  drawElevation(document.getElementById("preview-elevation"), {
    l: v.l || 3000, depth: previewAxis === "y" ? v.h : v.b, NEd: v.NEd, ...endKinds(r),
  });
}

// ------------------------------------------------------------------ errors

function clearErrors() {
  form.querySelectorAll(".control.invalid").forEach((c) => c.classList.remove("invalid"));
  form.querySelectorAll(".field .error").forEach((e) => e.remove());
  document.getElementById("form-message").textContent = "";
}

function showErrors(errors) {
  clearErrors();
  let first = null;
  for (const [path, message] of Object.entries(errors || {})) {
    const input = form.elements[path] || form.querySelector(`[name="${CSS.escape(path)}"]`);
    if (!input || !input.closest) continue;
    const control = input.closest(".control");
    control?.classList.add("invalid");
    const field = input.closest(".field") || input.closest("td");
    field?.append(el("span", { class: "error" }, message));
    first ??= input;
  }
  const n = Object.keys(errors || {}).length;
  document.getElementById("form-message").textContent = n ? `${n} input${n > 1 ? "s" : ""} need attention.` : "";
  first?.scrollIntoView({ behavior: "smooth", block: "center" });
}

// ------------------------------------------------------------------ helpers

function setupHelpers() {
  const out = (id, html) => { document.getElementById(id).innerHTML = html; };
  let combo = null, creep = null, kValue = null;

  document.getElementById("c-run").addEventListener("click", async () => {
    const res = await postJSON("/api/helpers/combination", {
      gk: Number(document.getElementById("c-gk").value || 0), qk: Number(document.getElementById("c-qk").value || 0),
      category: document.getElementById("c-cat").value, expression: document.getElementById("c-exp").value,
    });
    if (!res.ok) { out("c-out", res.data?.error || "Could not calculate."); return; }
    combo = res.data;
    out("c-out", combo.working.join("\n"));
    document.getElementById("c-use").disabled = false;
  });
  document.getElementById("c-use").addEventListener("click", () => {
    if (!combo) return;
    form.elements["actions.NEd"].value = combo.value.toFixed(1);
    document.getElementById("cr-ratio").value = combo.qp_ratio.toFixed(2);
    refresh();
  });

  document.getElementById("cr-run").addEventListener("click", async () => {
    const v = values();
    const res = await postJSON("/api/helpers/creep", {
      concrete: form.elements["materials.concrete"].value, b: v.b, h: v.h,
      rh: Number(document.getElementById("cr-rh").value), t0: Number(document.getElementById("cr-t0").value),
      cement: document.getElementById("cr-cem").value, moment_ratio: Number(document.getElementById("cr-ratio").value),
    });
    if (!res.ok) { out("cr-out", res.data?.error || "Could not estimate."); return; }
    creep = res.data;
    out("cr-out", `h0 = 2Ac/u = ${creep.h0.toFixed(0)} mm\nφ(∞,t0) = ${creep.phi_inf.toFixed(2)}\nφef = ${creep.phi_inf.toFixed(2)} × ${document.getElementById("cr-ratio").value} = ${creep.phi_ef.toFixed(2)}`);
    document.getElementById("cr-use").disabled = false;
  });
  document.getElementById("cr-use").addEventListener("click", () => {
    if (creep) form.elements["actions.phi_ef"].value = creep.phi_ef.toFixed(2);
  });

  document.getElementById("kh-run").addEventListener("click", async () => {
    const v = values();
    const axis = document.getElementById("kh-axis").value;
    const beams = [1, 2].map((i) => ({
      b: Number(document.getElementById(`kh-b${i}`).value || 0), h: Number(document.getElementById(`kh-h${i}`).value || 0),
      span: Number(document.getElementById(`kh-l${i}`).value || 0) * 1000,
    }));
    const res = await postJSON("/api/helpers/stiffness", {
      col_width: axis === "y" ? v.b : v.h, col_depth: axis === "y" ? v.h : v.b, col_length: v.l, beams,
    });
    if (!res.ok) { out("kh-out", res.data?.error || "Could not calculate."); return; }
    kValue = res.data.pinned ? "pinned" : res.data.k;
    out("kh-out", res.data.pinned ? "No beams given: the end is unrestrained (pinned)." : `k = ${res.data.k.toFixed(3)} (≥ 0.1)`);
    document.getElementById("kh-use").disabled = false;
  });
  document.getElementById("kh-use").addEventListener("click", () => {
    if (kValue === null) return;
    const axis = document.getElementById("kh-axis").value;
    const end = document.getElementById("kh-end").value;
    if (axis === "z") document.getElementById("same-axes").checked = false;
    const name = `restraint.${axis}.${end}`;
    const preset = form.querySelector(`select[data-kfor="${name}"]`);
    form.querySelector(`input[name="restraint.${axis}.method"][value="k"]`).checked = true;
    if (kValue === "pinned") { preset.value = "pinned"; form.elements[name].value = ""; form.elements[name].disabled = true; }
    else { preset.value = "custom"; form.elements[name].disabled = false; form.elements[name].value = kValue.toFixed(3); }
    refresh();
  });
}

// ------------------------------------------------------------------ init

async function init() {
  meta = await getJSON("/api/meta");
  populate();
  buildRestraint();
  const saved = store.get(KEYS.input);
  fill(saved || EXAMPLES.pass);
  const errors = store.getSession(KEYS.errors);
  if (errors) { showErrors(errors); store.setSession(KEYS.errors, null); }

  let timer = null;
  form.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(refresh, 90); });
  form.addEventListener("change", refresh);
  document.getElementById("same-axes").addEventListener("change", refresh);
  document.getElementById("ex-pass").addEventListener("click", () => { clearErrors(); fill(EXAMPLES.pass); });
  document.getElementById("ex-fail").addEventListener("click", () => { clearErrors(); fill(EXAMPLES.fail); });
  document.getElementById("reset").addEventListener("click", () => { clearErrors(); fill(EXAMPLES.pass); store.set(KEYS.input, null); });
  const fileInput = document.getElementById("import-file");
  document.getElementById("import").addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      if (!data || typeof data !== "object" || !data.geometry) throw new Error("not an inputs file");
      clearErrors();
      fill(data);
    } catch {
      document.getElementById("form-message").textContent = "That file is not an exported inputs JSON.";
    }
    fileInput.value = "";
  });
  for (const tab of document.querySelectorAll(".tabs [data-axis]")) {
    tab.addEventListener("click", () => {
      previewAxis = tab.dataset.axis;
      document.querySelectorAll(".tabs [data-axis]").forEach((t) => t.setAttribute("aria-selected", t === tab));
      refresh();
    });
  }
  setupHelpers();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearErrors();
    const data = serialize();
    store.set(KEYS.input, data);
    store.setSession(KEYS.result, null);
    window.location.href = "/column/run";
  });
}

init().catch((err) => {
  document.getElementById("form-message").textContent = "Could not reach the server. Start it with: .venv/bin/python app.py";
  console.error(err);
});
