// Pad foundation form: inputs, live plan and section from the server, then the run and report pages.
import { getJSON, keysFor, postJSON, store } from "./common.js";
import { renderFigure } from "./figure-spec.js";
import { formErrors, getPath, option, setPath, setupFilesMenu, setupSections } from "./form-kit.js";
import { EXAMPLES } from "./foundation-examples.js";

const KEYS = keysFor("foundation");
const OPEN_KEY = "ec2.foundation.sections";
const NUMERIC = /^(reinforcement\.(x_dia|y_dia|delta_c_dev))$/;

const form = document.getElementById("foundation-form");
const $ = (id) => document.getElementById(id);
const errors = formErrors(form, $("form-message"));
let meta = null;
let liveRequest = 0;
let liveTimer = null;

function populate() {
  for (const select of form.querySelectorAll("select[data-options]")) {
    const kind = select.dataset.options;
    let opts = [];
    if (kind === "concrete") opts = meta.concrete.map((c) => [c.name, c.name]);
    if (kind === "bars") opts = meta.bar_sizes.map((d) => [d, `H${d}`]);
    if (kind === "exposure") opts = meta.exposure_all.map((r) => [r.id, `${r.classes}: ${r.example}`]);
    if (kind === "psi") opts = meta.psi_categories.map((c) => [c.id, `${c.id}: ${c.label} (ψ2 ${c.psi[2]})`]);
    if (kind === "soils") {
      opts = [...meta.presumed_bearing.map((s) => [s.id, `${s.soil} (${s.range}${s.value === null ? "" : " kPa"})`]),
        ["custom", "From the site investigation (enter the value)"]];
    }
    select.replaceChildren(...opts.map(([v, l]) => option(v, l)));
  }
}

// ------------------------------------------------------------------ inputs

export function serialize() {
  const data = {};
  for (const input of form.querySelectorAll("[name]")) {
    const path = input.name;
    if (input.type === "number") setPath(data, path, input.value === "" ? null : Number(input.value));
    else if (NUMERIC.test(path)) setPath(data, path, Number(input.value));
    else setPath(data, path, input.value);
  }
  return data;
}

export function fill(data) {
  for (const input of form.querySelectorAll("[name]")) {
    const value = getPath(data, input.name);
    if (value !== undefined) input.value = value === null ? "" : String(value);
  }
  refresh();
}

function syncVisibility() {
  const exp = meta.exposure_all.find((r) => r.id === form.elements["durability.exposure"].value);
  const cem = form.elements["durability.cement_group"];
  if (exp) {
    const current = cem.value;
    cem.replaceChildren(...exp.groups.map((g) => option(g, g)));
    if (exp.groups.includes(current)) cem.value = current;
    $("exposure-help").textContent = exp.note || "";
  }
  const conc = meta.concrete.find((c) => c.name === form.elements["materials.concrete"].value);
  if (conc) $("concrete-help").textContent = `fck ${conc.fck} MPa, fctm ${conc.fctm} MPa`;
  const soil = meta.presumed_bearing.find((s) => s.id === form.elements["soil.type"].value);
  $("soil-help").textContent = soil
    ? (soil.value === null ? "No presumed value: needs a geotechnical design"
      : `${soil.group} soil; presumed allowable bearing value ${soil.range} kPa (BS 8004), for preliminary design`)
    : "Enter the allowable bearing pressure from the site investigation";
}

function summaries(d) {
  const f = (x, unit = "") => (x === null || x === undefined || x === "" ? "?" : `${x}${unit}`);
  const soil = meta.presumed_bearing.find((s) => s.id === d.soil.type);
  const exp = meta.exposure_all.find((r) => r.id === d.durability.exposure);
  return {
    project: [d.project.name, d.project.ref].filter(Boolean).join(" · ") || "Optional",
    geometry: `column ${f(d.column.cx)} × ${f(d.column.cy)} mm · base ${f(d.base.L)} × ${f(d.base.B)} m × ${f(d.base.h)} mm`,
    ground: `${soil ? soil.soil : "Site investigation"} · ${f(d.soil.q_allow, " kPa")}`,
    actions: `Gk ${f(d.actions.Gk)} · Qk ${f(d.actions.Qk ?? 0)} kN · M ${f(d.actions.MGk ?? 0)} + ${f(d.actions.MQk ?? 0)} kNm`,
    materials: `${d.materials.concrete} · fyk ${f(d.materials.fyk)} MPa · class ${d.materials.ductility}`,
    reinforcement: `H${d.reinforcement.x_dia} @ ${f(d.reinforcement.x_s)} along L · H${d.reinforcement.y_dia} @ ${f(d.reinforcement.y_s)} along B · cover ${f(d.reinforcement.cover)} mm`,
    durability: exp ? `${exp.classes} · ${d.durability.cement_group}` : "",
  };
}

// ------------------------------------------------------------------ live drawings

const barArea = (dia) => (Math.PI * dia * dia) / 4;

function refresh() {
  if (!meta) return;
  syncVisibility();
  const d = serialize();
  const text = summaries(d);
  for (const node of document.querySelectorAll("[data-sum]")) node.textContent = text[node.dataset.sum] ?? "";
  const gk = Number(d.actions.Gk) || 0, qk = Number(d.actions.Qk) || 0;
  const mg = Number(d.actions.MGk) || 0, mq = Number(d.actions.MQk) || 0;
  $("design-load").textContent = `NEd = 1.35 × ${gk} + 1.5 × ${qk} = ${(1.35 * gk + 1.5 * qk).toFixed(1)} kN; `
    + `MEd = ${(1.35 * mg + 1.5 * mq).toFixed(1)} kNm`;
  for (const [axis, len] of [["x", d.base.B], ["y", d.base.L]]) {
    const dia = Number(d.reinforcement[`${axis}_dia`]), s = Number(d.reinforcement[`${axis}_s`]);
    const perM = s ? (barArea(dia) * 1000) / s : 0;
    $(`${axis}-help`).textContent = perM ? `${perM.toFixed(0)} mm²/m; ${(perM * (Number(len) || 0)).toFixed(0)} mm² in all` : "";
  }
  clearTimeout(liveTimer);
  liveTimer = setTimeout(live, 150);
}

async function live() {
  const id = ++liveRequest;
  let res;
  try {
    res = await postJSON("/api/foundation/check", serialize());
  } catch {
    return;
  }
  if (id !== liveRequest) return;
  if (!res.ok) {
    const n = Object.keys(res.data?.errors || {}).length;
    $("live-hint").textContent = n ? `${n} input${n > 1 ? "s" : ""} to fix` : "incomplete";
    return;
  }
  $("live-hint").textContent = "to scale";
  const r = res.data;
  const fig = r.plots.figures;
  renderFigure($("preview-plan"), fig.plan, "Pad foundation plan");
  renderFigure($("preview-section"), fig.section, "Pad foundation section and ground pressure");
  const dv = r.derived;
  $("st-p").textContent = dv.sls_p1 === null ? "overturns" : `${dv.sls_p1.toFixed(1)} kPa`;
  $("st-q").textContent = dv.q_allow ? `${dv.q_allow} kPa` : "—";
  $("st-n").textContent = `${dv.NEd.toFixed(0)} kN / ${dv.MEd.toFixed(1)} kNm`;
  $("st-asx").textContent = dv.As_req_x ? `${dv.As_x.toFixed(0)} / ${dv.As_req_x.toFixed(0)} mm²` : "—";
  $("st-asy").textContent = dv.As_req_y ? `${dv.As_y.toFixed(0)} / ${dv.As_req_y.toFixed(0)} mm²` : "—";
  const c = r.summary.counts;
  $("st-verdict").textContent = c.fail ? `${c.fail} fail` : `all ${c.pass} pass`;
}

// ------------------------------------------------------------------ init

async function init() {
  meta = await getJSON("/api/meta");
  populate();
  setupSections(form, OPEN_KEY);
  fill(store.get(KEYS.input) || structuredClone(EXAMPLES.pass));
  const serverErrors = store.getSession(KEYS.errors);
  if (serverErrors) { errors.show(serverErrors); store.setSession(KEYS.errors, null); }

  // choosing a soil type suggests its presumed bearing value
  form.elements["soil.type"].addEventListener("change", () => {
    const soil = meta.presumed_bearing.find((s) => s.id === form.elements["soil.type"].value);
    if (soil && soil.value !== null) form.elements["soil.q_allow"].value = soil.value;
  });
  form.addEventListener("input", refresh);
  form.addEventListener("change", refresh);
  document.addEventListener("themechange", refresh);
  setupFilesMenu({
    examples: EXAMPLES, fill, errors, inputKey: KEYS.input, message: $("form-message"),
    looksValid: (d) => Boolean(d.base && d.column),
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    errors.clear();
    store.set(KEYS.input, serialize());
    store.setSession(KEYS.result, null);
    window.location.href = "/foundation/run";
  });
}

init().catch((err) => {
  $("form-message").textContent = "Could not reach the server. Start it with: .venv/bin/python app.py";
  console.error(err);
});
