import { el, getJSON, KEYS, postJSON, store } from "./common.js";
import { drawElevation, drawSection, endKinds, sectionFromInputs } from "./drawings.js";
import { anchorPopover } from "./theme.js";

export const EXAMPLES = {
  pass: {
    project: { name: "Campus teaching block", ref: "C2 ground floor", engineer: "", date: "" },
    materials: { concrete: "C32/40", fyk: 500, ductility: "B", dg: 20, gamma_c: 1.5, gamma_s: 1.15, alpha_cc: 0.85 },
    geometry: { b: 350, h: 350, l: 3.6 },
    reinforcement: { bar_dia: 20, n_b: 3, n_h: 3, link_dia: 8, cross_ties: false, cover: 30, delta_c_dev: 10 },
    restraint: { braced: true, y: { method: "k", k_top: 0.25, k_bottom: 0.1 }, z: { method: "k", k_top: 0.25, k_bottom: 0.1 } },
    actions: { NEd: 2100, bending: "biaxial", My_top: 45, My_bottom: 25, My_curvature: "single", Mz_top: 20,
      Mz_bottom: 10, Mz_curvature: "single", phi_ef: 1.7, lambda_lim_method: "simplified" },
    durability: { exposure: "XC1", cement_group: "All", fire_period: "R60", fire_exposure: "multi", mu_fi: 0.7, floor: "intermediate" },
  },
  fail: {
    project: { name: "Car park extension", ref: "C7 level 1", engineer: "", date: "" },
    materials: { concrete: "C25/30", fyk: 500, ductility: "B", dg: 20, gamma_c: 1.5, gamma_s: 1.15, alpha_cc: 0.85 },
    geometry: { b: 250, h: 400, l: 4.5 },
    reinforcement: { bar_dia: 25, n_b: 2, n_h: 3, link_dia: 6, cross_ties: false, cover: 25, delta_c_dev: 10 },
    restraint: { braced: true, y: { method: "k", k_top: 0.6, k_bottom: 0.4 }, z: { method: "factor", case: "c", F: 0.7 } },
    actions: { NEd: 1650, bending: "biaxial", My_top: 95, My_bottom: 60, My_curvature: "single", Mz_top: 30,
      Mz_bottom: 15, Mz_curvature: "single", phi_ef: 2.0, lambda_lim_method: "simplified" },
    durability: { exposure: "XC3/4-XF1", cement_group: "All except IVB", fire_period: "R90", fire_exposure: "multi", mu_fi: 0.7, floor: "intermediate" },
  },
};

const AXES = ["y", "z"];
// "End conditions" choices: beams = end stiffness k; a–e = Fig 5 cases; custom = F entered
const END_CHOICES = [
  ["beams", "Beams or slab at each end (enter k)"],
  ["a", "Pinned at both ends, F = 1.0"],
  ["c", "Fixed base, pinned top, F = 0.7"],
  ["d", "Fixed at both ends, F = 0.5"],
  ["b", "Cantilever, fixed base, F = 2.0"],
  ["e", "Fixed base, top free to sway, F = 1.0"],
  ["custom", "Enter F = l₀/l directly"],
];
const OPEN_KEY = "ec2.form.open";

const form = document.getElementById("column-form");
const $ = (id) => document.getElementById(id);
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

const option = (value, label) => el("option", { value }, label);

// ------------------------------------------------------------------ building the form

function populate() {
  for (const select of document.querySelectorAll("select[data-options]")) {
    const kind = select.dataset.options;
    let opts = [];
    if (kind === "concrete") opts = meta.concrete.map((c) => [c.name, c.name]);
    if (kind === "bars") opts = meta.bar_sizes.map((d) => [d, `H${d}`]);
    if (kind === "links") opts = meta.link_sizes.map((d) => [d, `H${d}`]);
    if (kind === "exposure") opts = meta.exposure.map((r) => [r.id, `${r.classes}: ${r.example}`]);
    if (kind === "fire") opts = meta.fire_periods.map((p) => [p, p === "none" ? "None required" : p]);
    if (kind === "psi") opts = meta.psi_categories.map((c) => [c.id, `${c.id}: ${c.label} (ψ0 ${c.psi[0]}, ψ2 ${c.psi[2]})`]);
    select.replaceChildren(...opts.map(([v, l]) => option(v, l)));
  }
}

let stiffTarget = null;

function kControl(axis, end, label) {
  const name = `restraint.${axis}.${end}`;
  const preset = el("select", { "data-kfor": name, "aria-label": `${label}: type` },
    option("pinned", "Pinned"), option("0.1", "Fixed"), option("custom", "k ="));
  const input = el("input", { name, type: "number", step: "0.01", min: "0", max: "1000000", "aria-label": label });
  preset.addEventListener("change", () => {
    if (preset.value === "pinned") input.value = "";
    if (preset.value === "0.1") input.value = "0.1";
    input.disabled = preset.value !== "custom";
    if (preset.value === "custom") input.focus();
    refresh();
  });
  const fromBeams = el("button", { type: "button", class: "inline-link" }, "From beams…");
  fromBeams.addEventListener("click", () => {
    stiffTarget = { axis, end, button: fromBeams };
    $("pop-stiffness").showPopover();
  });
  return el("div", { class: "field k-only" }, el("label", {}, label), el("div", { class: "control" }, preset, input), fromBeams);
}

function axisBlock(axis) {
  const name = (k) => `restraint.${axis}.${k}`;
  const choice = el("select", { "data-endfor": axis, "aria-label": "End conditions" },
    ...END_CHOICES.map(([v, l]) => option(v, l)));
  const factor = el("input", { name: name("F"), type: "number", step: "0.01", min: "0.3", max: "5" });
  choice.addEventListener("change", () => {
    const c = meta.fig5_cases.find((x) => x.id === choice.value);
    if (c) factor.value = c.F;
    refresh();
  });
  return el("div", { class: "axis-block", "data-axis": axis },
    el("div", { class: "axis-name" }, axis === "y" ? "About y–y (bending across h)" : "About z–z (bending across b)"),
    el("div", { class: "fields" },
      el("div", { class: "field", style: "grid-column: 1 / -1" }, el("label", {}, "End conditions"),
        el("div", { class: "control" }, choice),
        el("span", { class: "help" }, "Guide, Ch 5 Fig 5 and Table 4")),
      kControl(axis, "k_top", "Top end, k₁"),
      kControl(axis, "k_bottom", "Bottom end, k₂"),
      el("div", { class: "field f-only" }, el("label", {}, "F = l₀/l"), el("div", { class: "control" }, factor))));
}

function buildRestraint() {
  $("restraint-axes").replaceChildren(...AXES.map(axisBlock));
}

function syncVisibility() {
  const same = $("same-axes").checked;
  for (const block of form.querySelectorAll(".axis-block")) {
    const axis = block.dataset.axis;
    block.hidden = same && axis === "z";
    const choice = block.querySelector("select[data-endfor]").value;
    block.querySelectorAll(".k-only").forEach((n) => { n.hidden = choice !== "beams"; });
    block.querySelectorAll(".f-only").forEach((n) => { n.hidden = choice !== "custom"; });
  }
  const yName = form.querySelector('.axis-block[data-axis="y"] .axis-name');
  if (yName) yName.textContent = same ? "Both axes" : "About y–y (bending across h)";

  const exp = meta.exposure.find((r) => r.id === form.elements["durability.exposure"].value);
  const cem = form.elements["durability.cement_group"];
  if (exp) {
    const current = cem.value;
    cem.replaceChildren(...exp.groups.map((g) => option(g, g)));
    if (exp.groups.includes(current)) cem.value = current;
    $("exposure-help").textContent = exp.note || "";
  }
  const conc = meta.concrete.find((c) => c.name === form.elements["materials.concrete"].value);
  if (conc) $("concrete-help").textContent = `fck ${conc.fck} MPa, fctm ${conc.fctm} MPa, Ecm ${conc.Ecm} GPa`;
  $("fire-more").hidden = form.elements["durability.fire_period"].value === "none";
  $("row-z").hidden = form.elements["actions.bending"].value !== "biaxial";
}

// ------------------------------------------------------------------ serialise / fill

export function serialize() {
  const data = {};
  for (const input of form.querySelectorAll("[name]")) {
    const path = input.name;
    if (input.type === "checkbox") setPath(data, path, input.checked);
    else if (input.type === "number") setPath(data, path, input.value === "" ? null : Number(input.value));
    else if (path === "restraint.braced") setPath(data, path, input.value === "true");
    else if (/^(reinforcement\.(bar_dia|link_dia|delta_c_dev)|durability\.mu_fi)$/.test(path)) setPath(data, path, Number(input.value));
    else setPath(data, path, input.value);
  }
  for (const axis of AXES) {
    const choice = form.querySelector(`select[data-endfor="${axis}"]`).value;
    const r = data.restraint[axis] ?? {};
    if (choice === "beams") {
      for (const end of ["k_top", "k_bottom"]) {
        const preset = form.querySelector(`select[data-kfor="restraint.${axis}.${end}"]`).value;
        if (preset === "pinned") r[end] = "pinned";
      }
      data.restraint[axis] = { method: "k", k_top: r.k_top, k_bottom: r.k_bottom };
    } else {
      data.restraint[axis] = { method: "factor", case: choice === "custom" ? "" : choice, F: r.F };
    }
  }
  if ($("same-axes").checked) data.restraint.z = structuredClone(data.restraint.y);
  return data;
}

export function fill(data) {
  if (data.actions && !data.actions.bending) {
    data.actions.bending = Number(data.actions.Mz_top) || Number(data.actions.Mz_bottom) ? "biaxial" : "uniaxial";
  }
  for (const input of form.querySelectorAll("[name]")) {
    const value = getPath(data, input.name);
    if (input.type === "checkbox") input.checked = Boolean(value);
    else if (value !== undefined) input.value = value === null ? "" : String(value);
  }
  for (const axis of AXES) {
    const r = getPath(data, `restraint.${axis}`) || {};
    const choice = form.querySelector(`select[data-endfor="${axis}"]`);
    choice.value = r.method === "factor" ? (r.case || "custom") : "beams";
    for (const end of ["k_top", "k_bottom"]) {
      const name = `restraint.${axis}.${end}`;
      const preset = form.querySelector(`select[data-kfor="${name}"]`);
      const input = form.elements[name];
      const value = r[end];
      if (value === "pinned" || value === null || value === undefined) {
        preset.value = "pinned"; input.value = ""; input.disabled = true;
      } else if (Number(value) === 0.1) {
        preset.value = "0.1"; input.value = "0.1"; input.disabled = true;
      } else {
        preset.value = "custom"; input.value = value; input.disabled = false;
      }
    }
  }
  const r = data.restraint || {};
  $("same-axes").checked = JSON.stringify(r.y) === JSON.stringify(r.z);
  syncVisibility();
  if (data.durability?.cement_group) form.elements["durability.cement_group"].value = data.durability.cement_group;
  refresh();
}

// ------------------------------------------------------------------ section summaries

function summaries(d) {
  const f = (x, unit = "") => (x === null || x === undefined || x === "" ? "?" : `${x}${unit}`);
  const sameAxes = $("same-axes").checked;
  const end = (r) => {
    if (!r) return "?";
    if (r.method === "factor") {
      const c = meta.fig5_cases.find((x) => x.id === r.case);
      return c ? `${c.label.split(":")[0]} (F ${c.F})` : `F = ${f(r.F)}`;
    }
    const k = (v) => (v === "pinned" ? "pinned" : f(v));
    return `k₁ ${k(r.k_top)}, k₂ ${k(r.k_bottom)}`;
  };
  const re = d.reinforcement, a = d.actions, du = d.durability;
  const nBars = re.n_b && re.n_h ? 2 * re.n_b + 2 * (re.n_h - 2) : "?";
  return {
    project: [d.project.name, d.project.ref].filter(Boolean).join(" · ") || "Optional",
    materials: `${d.materials.concrete} · fyk ${f(d.materials.fyk)} MPa · class ${d.materials.ductility} · dg ${f(d.materials.dg)} mm`,
    geometry: `${f(d.geometry.b)} × ${f(d.geometry.h)} mm · l = ${f(d.geometry.l)} m`,
    reinforcement: `${nBars}H${re.bar_dia} · H${re.link_dia} @ ${linkSpacing(d.geometry.b, d.geometry.h, re.bar_dia).near ?? "?"} · cover ${f(re.cover)} mm`,
    restraint: `${d.restraint.braced ? "Braced" : "Unbraced"} · ${sameAxes ? end(d.restraint.y)
      : `y: ${end(d.restraint.y)}; z: ${end(d.restraint.z)}`}`,
    actions: a.bending === "biaxial"
      ? `NEd ${f(a.NEd)} kN · biaxial · My ${f(a.My_top ?? 0)}/${f(a.My_bottom ?? 0)} · Mz ${f(a.Mz_top ?? 0)}/${f(a.Mz_bottom ?? 0)} kNm`
      : `NEd ${f(a.NEd)} kN · uniaxial · My ${f(a.My_top ?? 0)}/${f(a.My_bottom ?? 0)} kNm`,
    durability: `${(meta.exposure.find((r) => r.id === du.exposure) || {}).classes || du.exposure} · `
      + `${du.fire_period === "none" ? "no fire period" : `fire ${du.fire_period}`}`,
  };
}

// ------------------------------------------------------------------ preview

/** Same rule as the server: s ≤ min(12φ, 0.6·bmin, 240), rounded down to 25 mm; ×1.67 elsewhere. */
function linkSpacing(b, h, phi) {
  if (!(b > 0 && h > 0 && phi > 0)) return { near: null, far: null };
  const sMax = Math.min(12 * phi, 0.6 * Math.min(b, h), 240);
  return { near: Math.floor(sMax / 25) * 25, far: Math.floor((1.67 * sMax) / 25) * 25 };
}

function values() {
  const v = (n) => Number(form.elements[n]?.value);
  return {
    b: v("geometry.b"), h: v("geometry.h"), l: v("geometry.l") * 1000, cover: v("reinforcement.cover"),
    link_dia: v("reinforcement.link_dia"), bar_dia: v("reinforcement.bar_dia"),
    n_b: Math.round(v("reinforcement.n_b")), n_h: Math.round(v("reinforcement.n_h")),
    NEd: v("actions.NEd"),
  };
}

function refresh() {
  if (!meta) return;
  syncVisibility();
  let data = null;
  try { data = serialize(); } catch { /* half-filled form */ }
  if (data) {
    const text = summaries(data);
    for (const node of document.querySelectorAll("[data-sum]")) node.textContent = text[node.dataset.sum] ?? "";
  }
  const v = values();
  const sec = sectionFromInputs(v);
  const sp = linkSpacing(v.b, v.h, v.bar_dia);
  $("link-calc").textContent = sp.near ? `H${v.link_dia} @ ${sp.near} mm, ${sp.far} mm elsewhere` : "—";
  drawSection($("preview-section"), sec, { linkLabel: `H${v.link_dia} @ ${sp.near ?? "?"}` });
  if (sec) {
    const as = sec.bars.length * Math.PI * sec.bar_dia ** 2 / 4;
    const gapB = (sec.b - 2 * sec.a) / (sec.n_b - 1) - sec.bar_dia;
    const gapH = (sec.h - 2 * sec.a) / (sec.n_h - 1) - sec.bar_dia;
    $("st-as").textContent = `${as.toFixed(0)} mm²`;
    $("st-rho").textContent = `${(100 * as / (sec.b * sec.h)).toFixed(2)} %`;
    $("st-gap").textContent = `${Math.min(gapB, gapH).toFixed(0)} mm`;
  } else {
    ["st-as", "st-rho", "st-gap"].forEach((id) => { $(id).textContent = "—"; });
  }
  drawElevation($("preview-elevation"), {
    l: v.l || 3000, depth: previewAxis === "y" ? v.h : v.b, NEd: v.NEd, ...endKinds(data?.restraint?.[previewAxis]),
  });
}

// ------------------------------------------------------------------ sections open/closed

function sections() {
  return [...form.querySelectorAll("details.section")];
}

function rememberOpen() {
  try {
    localStorage.setItem(OPEN_KEY, JSON.stringify(sections().filter((s) => s.open).map((s) => s.dataset.section)));
  } catch { /* not essential */ }
}

function restoreOpen() {
  let open = null;
  try { open = JSON.parse(localStorage.getItem(OPEN_KEY)); } catch { /* default below */ }
  if (Array.isArray(open)) sections().forEach((s) => { s.open = open.includes(s.dataset.section); });
}

// ------------------------------------------------------------------ errors

function clearErrors() {
  form.querySelectorAll(".control.invalid").forEach((c) => c.classList.remove("invalid"));
  form.querySelectorAll(".field .error").forEach((e) => e.remove());
  $("form-message").textContent = "";
}

function showErrors(errors) {
  clearErrors();
  let first = null;
  for (const [path, message] of Object.entries(errors || {})) {
    const input = form.querySelector(`[name="${CSS.escape(path)}"]`);
    if (!input) continue;
    const section = input.closest("details.section");
    if (section) section.open = true;
    const more = input.closest("details.more");
    if (more) more.open = true;
    input.closest(".control")?.classList.add("invalid");
    (input.closest(".field") || input.closest("td"))?.append(el("span", { class: "error" }, message));
    first ??= input;
  }
  const n = Object.keys(errors || {}).length;
  $("form-message").textContent = n ? `${n} input${n > 1 ? "s" : ""} to fix` : "";
  first?.scrollIntoView({ behavior: "smooth", block: "center" });
}

// ------------------------------------------------------------------ helpers (pop-overs)

function setupHelpers() {
  const out = (id, text) => { $(id).textContent = text; };
  let combo = null, creep = null, kValue = null;
  anchorPopover($("pop-combination"), document.querySelector('[popovertarget="pop-combination"]'), "start");
  anchorPopover($("pop-creep"), document.querySelector('[popovertarget="pop-creep"]'), "start");
  anchorPopover($("pop-stiffness"), () => stiffTarget?.button, "start");

  $("c-run").addEventListener("click", async () => {
    const res = await postJSON("/api/helpers/combination", {
      gk: Number($("c-gk").value || 0), qk: Number($("c-qk").value || 0),
      category: $("c-cat").value, expression: $("c-exp").value,
    });
    if (!res.ok) { out("c-out", res.data?.error || "Could not calculate."); return; }
    combo = res.data;
    out("c-out", combo.working.join("\n"));
    $("c-use").disabled = false;
  });
  $("c-use").addEventListener("click", () => {
    if (!combo) return;
    form.elements["actions.NEd"].value = combo.value.toFixed(1);
    $("cr-ratio").value = combo.qp_ratio.toFixed(2);
    $("pop-combination").hidePopover();
    refresh();
  });

  $("cr-run").addEventListener("click", async () => {
    const v = values();
    const res = await postJSON("/api/helpers/creep", {
      concrete: form.elements["materials.concrete"].value, b: v.b, h: v.h,
      rh: Number($("cr-rh").value), t0: Number($("cr-t0").value),
      cement: $("cr-cem").value, moment_ratio: Number($("cr-ratio").value),
    });
    if (!res.ok) { out("cr-out", res.data?.error || "Could not estimate."); return; }
    creep = res.data;
    out("cr-out", `h0 = 2Ac/u = ${creep.h0.toFixed(0)} mm\nφ(∞,t0) = ${creep.phi_inf.toFixed(2)}\n`
      + `φef = ${creep.phi_inf.toFixed(2)} × ${$("cr-ratio").value} = ${creep.phi_ef.toFixed(2)}`);
    $("cr-use").disabled = false;
  });
  $("cr-use").addEventListener("click", () => {
    if (creep) form.elements["actions.phi_ef"].value = creep.phi_ef.toFixed(2);
    $("pop-creep").hidePopover();
    refresh();
  });

  $("kh-run").addEventListener("click", async () => {
    if (!stiffTarget) return;
    const v = values();
    const beams = [1, 2].map((i) => ({
      b: Number($(`kh-b${i}`).value || 0), h: Number($(`kh-h${i}`).value || 0),
      span: Number($(`kh-l${i}`).value || 0) * 1000,
    }));
    const y = stiffTarget.axis === "y";
    const res = await postJSON("/api/helpers/stiffness", {
      col_width: y ? v.b : v.h, col_depth: y ? v.h : v.b, col_length: v.l, beams,
    });
    if (!res.ok) { out("kh-out", res.data?.error || "Could not calculate."); return; }
    kValue = res.data.pinned ? "pinned" : res.data.k;
    out("kh-out", res.data.pinned ? "No beams entered: this end is unrestrained (pinned)." : `k = ${res.data.k.toFixed(3)}`);
    $("kh-use").disabled = false;
  });
  $("kh-use").addEventListener("click", () => {
    if (kValue === null || !stiffTarget) return;
    const { axis, end } = stiffTarget;
    const name = `restraint.${axis}.${end}`;
    const preset = form.querySelector(`select[data-kfor="${name}"]`);
    if (kValue === "pinned") { preset.value = "pinned"; form.elements[name].value = ""; form.elements[name].disabled = true; }
    else { preset.value = "custom"; form.elements[name].disabled = false; form.elements[name].value = kValue.toFixed(3); }
    $("pop-stiffness").hidePopover();
    refresh();
  });
}

function setupFilesMenu() {
  const menu = $("files-menu");
  anchorPopover(menu, $("files-button"), "start");
  for (const item of menu.querySelectorAll("[data-example]")) {
    item.addEventListener("click", () => { clearErrors(); fill(EXAMPLES[item.dataset.example]); menu.hidePopover(); });
  }
  $("reset").addEventListener("click", () => {
    clearErrors(); fill(EXAMPLES.pass); store.set(KEYS.input, null); menu.hidePopover();
  });
  const fileInput = $("import-file");
  $("import").addEventListener("click", () => { menu.hidePopover(); fileInput.click(); });
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      if (!data || typeof data !== "object" || !data.geometry) throw new Error("not an inputs file");
      clearErrors();
      fill(data);
    } catch {
      $("form-message").textContent = "That file is not an exported inputs file.";
    }
    fileInput.value = "";
  });
}

// ------------------------------------------------------------------ init

async function init() {
  meta = await getJSON("/api/meta");
  populate();
  buildRestraint();
  restoreOpen();
  fill(store.get(KEYS.input) || EXAMPLES.pass);
  const errors = store.getSession(KEYS.errors);
  if (errors) { showErrors(errors); store.setSession(KEYS.errors, null); }

  let timer = null;
  form.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(refresh, 90); });
  form.addEventListener("change", refresh);
  $("same-axes").addEventListener("change", refresh);
  sections().forEach((s) => s.addEventListener("toggle", rememberOpen));
  $("expand-all").addEventListener("click", () => { sections().forEach((s) => { s.open = true; }); });
  $("collapse-all").addEventListener("click", () => { sections().forEach((s) => { s.open = false; }); });
  for (const button of document.querySelectorAll(".switch [data-axis]")) {
    button.addEventListener("click", () => {
      previewAxis = button.dataset.axis;
      document.querySelectorAll(".switch [data-axis]").forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
      refresh();
    });
  }
  document.addEventListener("themechange", refresh);
  setupHelpers();
  setupFilesMenu();

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    clearErrors();
    store.set(KEYS.input, serialize());
    store.setSession(KEYS.result, null);
    window.location.href = "/column/run";
  });
}

init().catch((err) => {
  $("form-message").textContent = "Could not reach the server. Start it with: .venv/bin/python app.py";
  console.error(err);
});
