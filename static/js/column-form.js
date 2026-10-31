import { downloadBlob, el, getJSON, keysFor, postJSON, statusDot, store } from "./common.js";
import { drawElevation, drawSection, endKinds, sectionFromInputs } from "./drawings.js";
import { renderFigure } from "./figure-spec.js";
import { fitFrame, formErrors, getPath, option, setPath, setupFilesMenu, setupSections } from "./form-kit.js";
import { anchorPopover } from "./theme.js";

const KEYS = keysFor("column");

export const EXAMPLES = {
  frame_pass: {
    project: { name: "Two-storey office frame", ref: "Col C1", engineer: "", date: "" },
    materials: { concrete: "C32/40", fyk: 500, ductility: "B", dg: 20, gamma_c: 1.5, gamma_s: 1.15, alpha_cc: 0.85 },
    geometry: { b: 350, h: 350, l: 3.5 },
    reinforcement: { bar_dia: 20, n_b: 3, n_h: 3, link_dia: 8, cross_ties: false, cover: 30, delta_c_dev: 10 },
    restraint: { braced: true, y: { method: "k", k_top: 0.343, k_bottom: 0.1 }, z: { method: "k", k_top: 0.343, k_bottom: 0.1 } },
    actions: {
      mode: "frame", member: "C1", bending: "uniaxial",
      phi_ef: 1.7, lambda_lim_method: "simplified",
    },
    durability: { exposure: "XC1", cement_group: "All", fire_period: "none", fire_exposure: "multi", mu_fi: 0.7, floor: "intermediate" },
    frame: {
      nodes: [
        { id: "N1", x: 0.0, y: 0.0 },
        { id: "N2", x: 0.0, y: 3.5 },
        { id: "N3", x: 0.0, y: 7.0 },
        { id: "N4", x: 6.0, y: 0.0 },
        { id: "N5", x: 6.0, y: 3.5 },
        { id: "N6", x: 6.0, y: 7.0 },
      ],
      members: [
        { id: "C1", node1: "N1", node2: "N2", b: 350, h: 350 },
        { id: "C2", node1: "N2", node2: "N3", b: 350, h: 350 },
        { id: "C3", node1: "N4", node2: "N5", b: 350, h: 350 },
        { id: "C4", node1: "N5", node2: "N6", b: 350, h: 350 },
        { id: "B1", node1: "N2", node2: "N5", b: 300, h: 500 },
        { id: "B2", node1: "N3", node2: "N6", b: 300, h: 500 },
      ],
      supports: [
        { node: "N1", type: "fixed" },
        { node: "N4", type: "fixed" },
      ],
      loads: [
        { type: "udl", member: "B1", w: 25.0, case: "G" },
        { type: "udl", member: "B2", w: 20.0, case: "G" },
        { type: "udl", member: "B1", w: 15.0, case: "Q" },
        { type: "udl", member: "B2", w: 12.0, case: "Q" },
        { type: "node", node: "N3", fx: 15.0, fy: 0.0, mz: 0.0, case: "Q" },
        { type: "node", node: "N2", fx: 10.0, fy: 0.0, mz: 0.0, case: "Q" },
      ],
      self_weight: true,
      E_method: "concrete",
    },
  },
  frame_fail: {
    project: { name: "Portal frame with errors", ref: "Col C1", engineer: "", date: "" },
    materials: { concrete: "C20/25", fyk: 500, ductility: "B", dg: 20, gamma_c: 1.5, gamma_s: 1.15, alpha_cc: 0.85 },
    geometry: { b: 200, h: 250, l: 4.0 },
    reinforcement: { bar_dia: 25, n_b: 2, n_h: 2, link_dia: 6, cross_ties: false, cover: 15, delta_c_dev: 10 },
    restraint: { braced: false, y: { method: "k", k_top: "pinned", k_bottom: 0.1 }, z: { method: "k", k_top: "pinned", k_bottom: 0.1 } },
    actions: {
      mode: "frame", member: "C1", bending: "uniaxial",
      phi_ef: 2.0, lambda_lim_method: "simplified",
    },
    durability: { exposure: "XC3/4-XF1", cement_group: "All except IVB", fire_period: "R60", fire_exposure: "multi", mu_fi: 0.7, floor: "intermediate" },
    frame: {
      nodes: [
        { id: "N1", x: 0.0, y: 0.0 },
        { id: "N2", x: 0.0, y: 4.0 },
        { id: "N3", x: 7.0, y: 0.0 },
        { id: "N4", x: 7.0, y: 4.0 },
      ],
      members: [
        { id: "C1", node1: "N1", node2: "N2", b: 200, h: 250 },
        { id: "C2", node1: "N3", node2: "N4", b: 200, h: 250 },
        { id: "B1", node1: "N2", node2: "N4", b: 250, h: 400 },
      ],
      supports: [
        { node: "N1", type: "fixed" },
        { node: "N3", type: "pin" },
      ],
      loads: [
        { type: "udl", member: "B1", w: 35.0, case: "G" },
        { type: "udl", member: "B1", w: 25.0, case: "Q" },
        { type: "node", node: "N2", fx: 25.0, fy: 0.0, mz: 0.0, case: "Q" },
      ],
      self_weight: true,
      E_method: "concrete",
    },
  },
  pass: {
    project: { name: "Campus teaching block", ref: "C2 ground floor", engineer: "", date: "" },
    materials: { concrete: "C32/40", fyk: 500, ductility: "B", dg: 20, gamma_c: 1.5, gamma_s: 1.15, alpha_cc: 0.85 },
    geometry: { b: 350, h: 350, l: 3.6 },
    reinforcement: { bar_dia: 20, n_b: 3, n_h: 3, link_dia: 8, cross_ties: false, cover: 30, delta_c_dev: 10 },
    restraint: { braced: true, y: { method: "k", k_top: 0.25, k_bottom: 0.1 }, z: { method: "k", k_top: 0.25, k_bottom: 0.1 } },
    actions: {
      mode: "direct", NEd: 2100, bending: "biaxial", My_top: 45, My_bottom: 25, My_curvature: "single", Mz_top: 20,
      Mz_bottom: 10, Mz_curvature: "single", phi_ef: 1.7, lambda_lim_method: "simplified",
    },
    durability: { exposure: "XC1", cement_group: "All", fire_period: "R60", fire_exposure: "multi", mu_fi: 0.7, floor: "intermediate" },
  },
  fail: {
    project: { name: "Car park extension", ref: "C7 level 1", engineer: "", date: "" },
    materials: { concrete: "C25/30", fyk: 500, ductility: "B", dg: 20, gamma_c: 1.5, gamma_s: 1.15, alpha_cc: 0.85 },
    geometry: { b: 250, h: 400, l: 4.5 },
    reinforcement: { bar_dia: 25, n_b: 2, n_h: 3, link_dia: 6, cross_ties: false, cover: 25, delta_c_dev: 10 },
    restraint: { braced: true, y: { method: "k", k_top: 0.6, k_bottom: 0.4 }, z: { method: "factor", case: "c", F: 0.7 } },
    actions: {
      mode: "direct", NEd: 1650, bending: "biaxial", My_top: 95, My_bottom: 60, My_curvature: "single", Mz_top: 30,
      Mz_bottom: 15, Mz_curvature: "single", phi_ef: 2.0, lambda_lim_method: "simplified",
    },
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
const OPEN_KEY = "ec2.column.form.open.v2";

const form = document.getElementById("column-form");
const $ = (id) => document.getElementById(id);
const errors = formErrors(form, $("form-message"));
let meta = null;
let previewAxis = "y";

let frameModel = {
  nodes: [],
  members: [],
  supports: [],
  loads: [],
};
let selectedMemberId = "C1";
let lastAnalysis = null;
let lastColumnActions = null;
let lastColumnActionsError = null;   // why the chosen member cannot be designed as a column

const TAB_NAMES = ["analysis", "design", "report"];
let currentTab = "analysis";
let analysisDone = false;
let designDone = false;
let analysisDirty = false;

const valueOf = (name) => form.elements[name]?.value;

function updateTabStates() {
  const direct = valueOf("actions.mode") === "direct";
  const canDesign = analysisDone || direct;
  $("tab-design").setAttribute("aria-disabled", String(!canDesign));
  $("tab-report").setAttribute("aria-disabled", String(!designDone));
}

function switchTab(name) {
  if (!TAB_NAMES.includes(name)) return;
  const tabBtn = $(`tab-${name}`);
  if (tabBtn.getAttribute("aria-disabled") === "true") return;

  currentTab = name;
  for (const t of TAB_NAMES) {
    $(`tab-${t}`).setAttribute("aria-selected", String(t === name));
    $(`panel-${t}`).classList.toggle("is-active", t === name);
  }
  form.classList.toggle("report-active", name === "report");
  if (history.replaceState) {
    history.replaceState(null, "", `#${name}`);
  } else {
    location.hash = name;
  }
  if (name === "report") {
    const frame = $("report-frame");
    if (!frame.src || !frame.src.includes("/column/report?embed=1")) {
      frame.src = "/column/report?embed=1";
    }
  }
}

function setupTabs() {
  for (const t of TAB_NAMES) {
    $(`tab-${t}`).addEventListener("click", () => switchTab(t));
    $(`tab-${t}`).addEventListener("keydown", (e) => {
      let target = null;
      const enabledTabs = TAB_NAMES.filter((name) => $(`tab-${name}`).getAttribute("aria-disabled") !== "true");
      const idx = enabledTabs.indexOf(t);
      if (e.key === "ArrowRight" || e.key === "ArrowDown") {
        target = enabledTabs[(idx + 1) % enabledTabs.length];
      } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        target = enabledTabs[(idx - 1 + enabledTabs.length) % enabledTabs.length];
      } else if (e.key === "Home") {
        target = enabledTabs[0];
      } else if (e.key === "End") {
        target = enabledTabs[enabledTabs.length - 1];
      }
      if (target && target !== t) {
        e.preventDefault();
        $(`tab-${target}`).focus();
        switchTab(target);
      }
    });
  }
  window.addEventListener("hashchange", () => {
    const hash = location.hash.replace("#", "");
    if (TAB_NAMES.includes(hash)) switchTab(hash);
  });
}

function handleErrors(errs) {
  errors.show(errs);
  const keys = Object.keys(errs || {});
  if (keys.length > 0) {
    const k = keys[0];
    const input = form.querySelector(`[name="${k}"]`) || form.querySelector(`[data-path^="${k}"]`);
    if (input) {
      const panel = input.closest('[role="tabpanel"]');
      if (panel) {
        const tabName = panel.id.replace("panel-", "");
        switchTab(tabName);
      }
      input.focus();
    }
  }
}

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

function show(selector, on) {
  form.querySelectorAll(selector).forEach((n) => { n.hidden = !on; });
}

function checkGeometryHWarn() {
  const mem = frameModel.members.find((m) => m.id === selectedMemberId);
  const warnEl = $("geom-h-warn");
  if (valueOf("actions.mode") === "frame" && mem && mem.h) {
    const curH = Number(form.elements["geometry.h"]?.value);
    if (curH && curH !== mem.h) {
      warnEl.textContent = `Depth h (${curH} mm) differs from member ${mem.id} depth (${mem.h} mm) in the frame.`;
      warnEl.hidden = false;
      return;
    }
  }
  warnEl.hidden = true;
  warnEl.textContent = "";
}

function syncVisibility() {
  const isFrame = valueOf("actions.mode") === "frame";
  show(".frame-only", isFrame);
  show(".direct-only", !isFrame);

  show(".fr-e-enter", valueOf("frame.E_method") === "entered");

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
  if (conc) {
    $("concrete-help").textContent = `fck ${conc.fck} MPa, fctm ${conc.fctm} MPa, Ecm ${conc.Ecm} GPa`;
    $("fr-e-help").textContent = valueOf("frame.E_method") === "entered" ? "" : `Ecm = ${conc.Ecm} GPa (${conc.name})`;
  }
  $("fire-more").hidden = form.elements["durability.fire_period"].value === "none";
  $("row-z").hidden = form.elements["actions.bending"].value !== "biaxial";
  checkGeometryHWarn();
}

// ------------------------------------------------------------------ tables

function cellInput(path, value, attrs = {}) {
  return el("div", { class: "control" }, el("input", {
    type: "number", step: attrs.step || "any", value: value ?? "", "data-path": path,
    "aria-label": attrs.label || path, ...(attrs.extra || {}),
  }), attrs.unit ? el("span", { class: "unit" }, attrs.unit) : null);
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

function renderNodes() {
  const tbody = $("nodes-table").tBodies[0];
  tbody.replaceChildren(...frameModel.nodes.map((nd, i) => {
    const p = `frame.nodes.${i}`;
    return el("tr", {},
      el("td", { class: "idx" }, String(i + 1)),
      el("td", {}, el("div", { class: "control" }, el("input", {
        type: "text", value: nd.id || "", "data-path": `${p}.id`, "aria-label": `${p.includes("nodes") ? "Node" : "Member"} ${i + 1} id`,
      }))),
      el("td", {}, cellInput(`${p}.x`, nd.x, { label: `Node ${i + 1} x (m)` })),
      el("td", {}, cellInput(`${p}.y`, nd.y, { label: `Node ${i + 1} y (m)` })),
      el("td", {}, removeButton(() => {
        frameModel.nodes.splice(i, 1);
        renderTables();
        refresh();
      }, `Remove node ${i + 1}`))
    );
  }));
}

function renderMembers() {
  const tbody = $("members-table").tBodies[0];
  const nodeOpts = frameModel.nodes.map((n) => [n.id, n.id]);
  tbody.replaceChildren(...frameModel.members.map((m, i) => {
    const p = `frame.members.${i}`;
    return el("tr", {},
      el("td", { class: "idx" }, String(i + 1)),
      el("td", {}, el("div", { class: "control" }, el("input", {
        type: "text", value: m.id || "", "data-path": `${p}.id`, "aria-label": `${p.includes("nodes") ? "Node" : "Member"} ${i + 1} id`,
      }))),
      el("td", {}, cellSelect(`${p}.node1`, m.node1, nodeOpts, `Member ${i + 1} node 1`)),
      el("td", {}, cellSelect(`${p}.node2`, m.node2, nodeOpts, `Member ${i + 1} node 2`)),
      el("td", {}, cellInput(`${p}.b`, m.b, { label: `Member ${i + 1} b (mm)`, step: "5" })),
      el("td", {}, cellInput(`${p}.h`, m.h, { label: `Member ${i + 1} h (mm)`, step: "5" })),
      el("td", {}, removeButton(() => {
        frameModel.members.splice(i, 1);
        renderTables();
        refresh();
      }, `Remove member ${i + 1}`))
    );
  }));
}

function renderSupports() {
  const tbody = $("supports-table").tBodies[0];
  const nodeOpts = frameModel.nodes.map((n) => [n.id, n.id]);
  const typeOpts = [["fixed", "Fixed"], ["pin", "Pinned"], ["roller", "Roller"]];
  tbody.replaceChildren(...frameModel.supports.map((sp, i) => {
    const p = `frame.supports.${i}`;
    return el("tr", {},
      el("td", { class: "idx" }, String(i + 1)),
      el("td", {}, cellSelect(`${p}.node`, sp.node, nodeOpts, `Support ${i + 1} node`)),
      el("td", {}, cellSelect(`${p}.type`, sp.type, typeOpts, `Support ${i + 1} type`)),
      el("td", {}, removeButton(() => {
        frameModel.supports.splice(i, 1);
        renderSupports();
        refresh();
      }, `Remove support ${i + 1}`))
    );
  }));
}

function renderLoads() {
  const tbody = $("loads-table").tBodies[0];
  const nodeOpts = frameModel.nodes.map((n) => [n.id, n.id]);
  const memOpts = frameModel.members.map((m) => [m.id, m.id]);
  const loadTypes = [["udl", "Uniform load"], ["point", "Point load"], ["node", "Node load"]];
  const cases = [["G", "G"], ["Q", "Q"], ["Ed", "Ed"]];

  tbody.replaceChildren(...frameModel.loads.map((ld, i) => {
    const p = `frame.loads.${i}`;
    const isNode = ld.type === "node";
    const isUdl = ld.type === "udl";

    const typeCell = cellSelect(`${p}.type`, ld.type, loadTypes, `Load ${i + 1} type`);
    const targetCell = isNode
      ? cellSelect(`${p}.node`, ld.node, nodeOpts, `Load ${i + 1} node`)
      : cellSelect(`${p}.member`, ld.member, memOpts, `Load ${i + 1} member`);

    let val1Cell, val2Cell, val3Cell;
    if (isNode) {
      val1Cell = cellInput(`${p}.fx`, ld.fx, { label: "fx", unit: "kN" });
      val2Cell = cellInput(`${p}.fy`, ld.fy, { label: "fy", unit: "kN" });
      val3Cell = cellInput(`${p}.mz`, ld.mz, { label: "mz", unit: "kNm" });
    } else if (isUdl) {
      val1Cell = cellInput(`${p}.w`, ld.w, { label: "w", unit: "kN/m" });
      val2Cell = el("span", { class: "dash" }, "—");
      val3Cell = el("span", { class: "dash" }, "—");
    } else { // point
      val1Cell = cellInput(`${p}.P`, ld.P, { label: "P", unit: "kN" });
      val2Cell = cellInput(`${p}.a`, ld.a, { label: "a", unit: "m" });
      val3Cell = el("span", { class: "dash" }, "—");
    }

    const caseCell = cellSelect(`${p}.case`, ld.case || "Ed", cases, `Load ${i + 1} case`);
    const removeCell = removeButton(() => {
      frameModel.loads.splice(i, 1);
      renderLoads();
      refresh();
    }, `Remove load ${i + 1}`);

    return el("tr", {},
      el("td", {}, typeCell),
      el("td", {}, targetCell),
      el("td", {}, val1Cell),
      el("td", {}, val2Cell),
      el("td", {}, val3Cell),
      el("td", {}, caseCell),
      el("td", {}, removeCell)
    );
  }));
}

function renderTables() {
  renderNodes();
  renderMembers();
  renderSupports();
  renderLoads();
}

function onTableInput(event) {
  const path = event.target.dataset.path;
  if (!path) return;
  const parts = path.split(".");
  const tableKey = parts[1];
  const index = Number(parts[2]);
  const prop = parts[3];
  const list = frameModel[tableKey];
  if (!list || !list[index]) return;

  if (tableKey === "loads" && prop === "type") {
    const newType = event.target.value;
    const item = list[index];
    item.type = newType;
    if (newType === "node") {
      delete item.member; delete item.w; delete item.P; delete item.a;
      item.node = frameModel.nodes[0]?.id || "N1";
      item.fx = 0; item.fy = 0; item.mz = 0;
    } else if (newType === "udl") {
      delete item.node; delete item.fx; delete item.fy; delete item.mz; delete item.P; delete item.a;
      item.member = frameModel.members[0]?.id || "C1";
      item.w = 20;
    } else if (newType === "point") {
      delete item.node; delete item.fx; delete item.fy; delete item.mz; delete item.w;
      item.member = frameModel.members[0]?.id || "C1";
      item.P = 50; item.a = 1.5;
    }
    renderLoads();
    refresh();
    return;
  }

  if (prop === "id") {
    if (event.type === "change") renameId(tableKey, index, event.target);
    return;
  }
  if (event.target.tagName === "SELECT") {
    list[index][prop] = event.target.value;
  } else {
    list[index][prop] = event.target.value === "" ? null : Number(event.target.value);
  }
  refresh();
}

// A node or member id is committed when the field is left: an empty or repeated id is refused, and the new id
// replaces the old one in the members, supports, loads and the column choice that refer to it.
function renameId(tableKey, index, input) {
  const list = frameModel[tableKey];
  const old = list[index].id;
  const id = input.value.trim();
  if (id === old) return;
  const kind = tableKey === "nodes" ? "Node" : "Member";
  if (!id || list.some((item, i) => i !== index && item.id === id)) {
    input.value = old;
    $("analysis-note").textContent = id ? `${kind} ${id} already exists` : `A ${kind.toLowerCase()} needs an id`;
    return;
  }
  list[index].id = id;
  if (tableKey === "nodes") {
    for (const m of frameModel.members) {
      if (m.node1 === old) m.node1 = id;
      if (m.node2 === old) m.node2 = id;
    }
    for (const sp of frameModel.supports) if (sp.node === old) sp.node = id;
    for (const ld of frameModel.loads) if (ld.type === "node" && ld.node === old) ld.node = id;
  } else {
    for (const ld of frameModel.loads) if (ld.type !== "node" && ld.member === old) ld.member = id;
    if (selectedMemberId === old) {
      selectedMemberId = id;
      form.elements["actions.member"].value = id;
    }
  }
  renderTables();
  refresh();
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
    const r = data.restraint?.[axis] ?? {};
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

  // the frame is kept in the inputs in both modes, so switching to direct values (or adjusting them) loses nothing
  data.frame = {
    nodes: frameModel.nodes.map((n) => ({ ...n })),
    members: frameModel.members.map((m) => ({ ...m })),
    supports: frameModel.supports.map((s) => ({ ...s })),
    loads: frameModel.loads.map((l) => ({ ...l })),
    self_weight: form.elements["frame.self_weight"].checked,
    E_method: form.elements["frame.E_method"].value,
    E: data.frame?.E ?? null,
  };
  data.actions.member = selectedMemberId || form.elements["actions.member"].value;
  if (data.actions?.mode === "frame") {
    if ($("adjust-design-values").checked) {
      data.actions.mode = "direct";
      data.actions.NEd = Number($("dv-ned").value);
      data.actions.My_top = Number($("dv-myt").value);
      data.actions.My_bottom = Number($("dv-myb").value);
      data.actions.My_curvature = $("dv-mycurv").value;
    }
  }

  return data;
}

export function fill(data) {
  // inputs saved before the frame analysis existed have no mode: they were entered directly (as the server reads them)
  if (data.actions && !data.actions.mode) data.actions.mode = "direct";
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

  // Frame data (inputs entered directly on main have none: start from the example frame)
  const fr = data.frame?.nodes ? data.frame : EXAMPLES.frame_pass.frame;
  frameModel = {
    nodes: (fr.nodes || []).map((n) => ({ ...n })),
    members: (fr.members || []).map((m) => ({ ...m })),
    supports: (fr.supports || []).map((s) => ({ ...s })),
    loads: (fr.loads || []).map((l) => ({ ...l })),
  };
  selectedMemberId = data.actions?.member || (frameModel.members[0]?.id || "C1");
  $("a-member").value = selectedMemberId;

  if (fr.self_weight !== undefined && form.elements["frame.self_weight"]) {
    form.elements["frame.self_weight"].checked = Boolean(fr.self_weight);
  }
  if (fr.E_method && form.elements["frame.E_method"]) {
    form.elements["frame.E_method"].value = fr.E_method;
  }
  if (fr.E && form.elements["frame.E"]) {
    form.elements["frame.E"].value = fr.E;
  }

  // Reset tab states & results
  analysisDone = false;
  designDone = false;
  analysisDirty = false;
  $("analysis-note").textContent = "";
  $("analysis-results-area").replaceChildren();
  $("design-results-area").replaceChildren();
  $("adjust-design-values").checked = false;
  $("dv-ned").readOnly = true;
  $("dv-myt").readOnly = true;
  $("dv-myb").readOnly = true;
  $("dv-mycurv").disabled = true;
  $("dv-ned").value = data.actions?.NEd ?? "";
  $("dv-myt").value = data.actions?.My_top ?? "";
  $("dv-myb").value = data.actions?.My_bottom ?? "";
  $("dv-mycurv").value = data.actions?.My_curvature ?? "single";
  $("dv-warn").hidden = true;

  updateTabStates();
  syncVisibility();
  if (data.durability?.cement_group) form.elements["durability.cement_group"].value = data.durability.cement_group;
  renderTables();
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
  const numNodes = frameModel.nodes.length;
  const numMembers = frameModel.members.length;
  const numLoads = frameModel.loads.length;

  return {
    "frame-nodes": `${numNodes} node${numNodes === 1 ? "" : "s"}`,
    "frame-members": `${numMembers} member${numMembers === 1 ? "" : "s"}`,
    "frame-supports": `${frameModel.supports.length} support${frameModel.supports.length === 1 ? "" : "s"}`,
    "frame-loads": `${numLoads} load${numLoads === 1 ? "" : "s"}`,
    project: [d.project.name, d.project.ref].filter(Boolean).join(" · ") || "Optional",
    materials: `${d.materials.concrete} · fyk ${f(d.materials.fyk)} MPa · class ${d.materials.ductility} · dg ${f(d.materials.dg)} mm`,
    geometry: `${f(d.geometry.b)} × ${f(d.geometry.h)} mm · l = ${f(d.geometry.l)} m`,
    reinforcement: `${nBars}H${re.bar_dia} · H${re.link_dia} @ ${linkSpacing(d.geometry.b, d.geometry.h, re.bar_dia).near ?? "?"} · cover ${f(re.cover)} mm`,
    restraint: `${d.restraint.braced ? "Braced" : "Unbraced"} · ${sameAxes ? end(d.restraint.y)
      : `y: ${end(d.restraint.y)}; z: ${end(d.restraint.z)}`}`,
    actions: a.mode === "frame"
      ? `Frame analysis · Column ${a.member || selectedMemberId} · NEd ${f(a.NEd)} kN`
      : (a.bending === "biaxial"
        ? `NEd ${f(a.NEd)} kN · biaxial · My ${f(a.My_top ?? 0)}/${f(a.My_bottom ?? 0)} · Mz ${f(a.Mz_top ?? 0)}/${f(a.Mz_bottom ?? 0)} kNm`
        : `NEd ${f(a.NEd)} kN · uniaxial · My ${f(a.My_top ?? 0)}/${f(a.My_bottom ?? 0)} kNm`),
    bending: `${a.bending === "biaxial" ? `biaxial · Mz ${f(a.Mz_top ?? 0)}/${f(a.Mz_bottom ?? 0)} kNm` : "uniaxial"}`
      + ` · φef ${f(a.phi_ef)}`,
    durability: `${(meta.exposure.find((r) => r.id === du.exposure) || {}).classes || du.exposure} · `
      + `${du.fire_period === "none" ? "no fire period" : `fire ${du.fire_period}`}`,
  };
}

// ------------------------------------------------------------------ preview

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

let liveFrameTimer = null;
let liveFrameSeq = 0;

function scheduleLiveFrame() {
  clearTimeout(liveFrameTimer);
  liveFrameTimer = setTimeout(runLiveFrame, 260);
}

async function runLiveFrame() {
  if (valueOf("actions.mode") !== "frame") {
    $("preview-frame").replaceChildren();
    return;
  }
  const seq = ++liveFrameSeq;
  try {
    const data = serialize();
    const res = await postJSON("/api/column/analysis", data);
    if (seq !== liveFrameSeq) return;
    if (res.ok && res.data.figures?.model) {
      $("frame-hint").textContent = "live";
      renderFigure($("preview-frame"), res.data.figures.model, "Analytical model");
    } else {
      $("frame-hint").textContent = "incomplete";
    }
  } catch {
    if (seq === liveFrameSeq) $("frame-hint").textContent = "unavailable";
  }
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

  scheduleLiveFrame();
}

// ------------------------------------------------------------------ Analysis & Design Actions

function applyColumnActionsToDesign(colAct) {
  if (!colAct) return;
  $("dv-ned").value = colAct.NEd != null ? colAct.NEd.toFixed(1) : "";
  $("dv-myt").value = colAct.M_top != null ? colAct.M_top.toFixed(1) : "";
  $("dv-myb").value = colAct.M_bottom != null ? colAct.M_bottom.toFixed(1) : "";
  $("dv-mycurv").value = colAct.curvature || "single";

  form.elements["actions.NEd"].value = $("dv-ned").value;
  form.elements["actions.My_top"].value = $("dv-myt").value;
  form.elements["actions.My_bottom"].value = $("dv-myb").value;
  form.elements["actions.My_curvature"].value = $("dv-mycurv").value;

  const mem = frameModel.members.find((m) => m.id === colAct.member);
  if (mem) {
    if (mem.b) form.elements["geometry.b"].value = String(mem.b);
    if (mem.h) form.elements["geometry.h"].value = String(mem.h);
  }
  if (colAct.l) form.elements["geometry.l"].value = colAct.l.toFixed(2);

  checkGeometryHWarn();
  refresh();
}

function renderAnalysisView(resData) {
  const container = $("analysis-results-area");
  const figs = resData.figures || {};
  let currentDiag = "M";

  const diagButtons = [
    ["M", "Bending moment M"],
    ["N", "Axial force N"],
    ["V", "Shear force V"],
    ["model", "Analytical model"],
  ];
  const btnGroup = el("div", { class: "canvas-tools", style: "margin-bottom: 8px;" },
    ...diagButtons.map(([k, label]) => {
      const b = el("button", {
        type: "button",
        "aria-pressed": String(k === currentDiag),
        onclick: () => {
          currentDiag = k;
          btnGroup.querySelectorAll("button").forEach((btn) => {
            btn.setAttribute("aria-pressed", String(btn === b));
          });
          drawCurrentDiag();
        },
      }, label);
      return b;
    })
  );

  const diagHost = el("div", { class: "live-diagrams", id: "analysis-diagram-host" });
  function drawCurrentDiag() {
    if (figs[currentDiag]) {
      renderFigure(diagHost, figs[currentDiag], diagButtons.find((b) => b[0] === currentDiag)[1]);
    }
  }
  drawCurrentDiag();

  const rxTable = el("div", { class: "table-scroll", style: "margin-top: 14px;" },
    el("div", { class: "group-title", style: "margin-bottom: 6px;" }, "Support reactions"),
    el("table", { class: "mini", style: "width: 100%;" },
      el("thead", {}, el("tr", {}, el("th", {}, "Node"), el("th", {}, "Rx (kN)"), el("th", {}, "Ry (kN)"), el("th", {}, "Mz (kNm)"))),
      el("tbody", {}, ...Object.entries(resData.frame.reactions || {}).map(([nodeId, rx]) => el("tr", {},
        el("td", {}, String(nodeId)),
        el("td", {}, rx.Rx != null ? Number(rx.Rx).toFixed(2) : "—"),
        el("td", {}, rx.Ry != null ? Number(rx.Ry).toFixed(2) : "—"),
        el("td", {}, rx.Mz != null ? Number(rx.Mz).toFixed(2) : "—")
      )))
    ),
    el("p", { class: "help-line" }, "Rx to the right, Ry upwards, Mz anticlockwise.")
  );

  const forcesTable = el("div", { class: "table-scroll", style: "margin-top: 14px;" },
    el("div", { class: "group-title", style: "margin-bottom: 6px;" }, "Member end forces"),
    el("table", { class: "mini", style: "width: 100%; font-size: 12.5px;" },
      el("thead", {}, el("tr", {},
        el("th", {}, "Member"),
        el("th", {}, "End 1"), el("th", {}, "N (kN)"), el("th", {}, "V (kN)"), el("th", {}, "M (kNm)"),
        el("th", {}, "End 2"), el("th", {}, "N (kN)"), el("th", {}, "V (kN)"), el("th", {}, "M (kNm)")
      )),
      el("tbody", {}, ...(resData.frame.members || []).map((elem) => el("tr", {},
        el("td", { style: "font-weight: 600;" }, String(elem.id)),
        el("td", {}, String(elem.node1)),
        el("td", {}, elem.axial_start != null ? Number(elem.axial_start).toFixed(1) : "—"),
        el("td", {}, elem.shear_start != null ? Number(elem.shear_start).toFixed(1) : "—"),
        el("td", {}, elem.moment_start != null ? Number(elem.moment_start).toFixed(1) : "—"),
        el("td", {}, String(elem.node2)),
        el("td", {}, elem.axial_end != null ? Number(elem.axial_end).toFixed(1) : "—"),
        el("td", {}, elem.shear_end != null ? Number(elem.shear_end).toFixed(1) : "—"),
        el("td", {}, elem.moment_end != null ? Number(elem.moment_end).toFixed(1) : "—")
      )))
    ),
    el("p", { class: "help-line" }, "N: tension positive. V and M along the member from end 1 to end 2, sagging "
      + "moments positive.")
  );

  const vertMembers = resData.vertical_members || [];
  const colPicker = el("select", { id: "sel-column-member", style: "min-width: 120px;" },
    ...vertMembers.map((mId) => option(mId, `Column ${mId}`))
  );
  colPicker.value = selectedMemberId;

  const cardContent = el("div", { id: "col-summary-content", style: "margin-top: 10px; font-size: 13.5px;" });

  function updateCard(colAct) {
    if (!colAct) {
      const why = lastColumnActionsError
        || (vertMembers.length ? "Choose the column to design." : "The frame has no vertical member to design as a column.");
      cardContent.replaceChildren(el("p", { class: "error-line" }, why));
      return;
    }
    const topK = colAct.k_top === "pinned" ? "pinned" : Number(colAct.k_top).toFixed(3);
    const botK = colAct.k_bottom === "pinned" ? "pinned" : Number(colAct.k_bottom).toFixed(3);
    cardContent.replaceChildren(
      el("div", { style: "display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin-bottom: 12px;" },
        el("div", {}, el("div", { class: "group-title" }, "Axial load NEd"), el("div", { style: "font-size: 16px; font-weight: 600;" }, `${colAct.NEd.toFixed(1)} kN`)),
        el("div", {}, el("div", { class: "group-title" }, "Moments (y–y)"), el("div", { style: "font-size: 16px; font-weight: 600;" }, `${colAct.M_top.toFixed(1)} / ${colAct.M_bottom.toFixed(1)} kNm`)),
        el("div", {}, el("div", { class: "group-title" }, "Curvature"), el("div", { style: "font-size: 16px; font-weight: 600; text-transform: capitalize;" }, colAct.curvature)),
        el("div", {}, el("div", { class: "group-title" }, "Clear height l"), el("div", { style: "font-size: 16px; font-weight: 600;" }, `${colAct.l.toFixed(2)} m`)),
        el("div", {}, el("div", { class: "group-title" }, "Suggested restraint"), el("div", { style: "font-size: 14px; font-family: var(--font-mono);" }, `top ${topK}, bottom ${botK}`))
      )
    );
  }
  updateCard(lastColumnActions);

  colPicker.addEventListener("change", async () => {
    selectedMemberId = colPicker.value;
    form.elements["actions.member"].value = selectedMemberId;
    const data = serialize();
    data.actions.member = selectedMemberId;
    const res = await postJSON("/api/column/analysis", data);
    if (res.ok) {
      lastAnalysis = res.data;
      lastColumnActions = res.data.column_actions;
      lastColumnActionsError = res.data.column_actions_error;
      figs.model = res.data.figures.model;
      figs.M = res.data.figures.M;
      figs.N = res.data.figures.N;
      figs.V = res.data.figures.V;
      drawCurrentDiag();
      updateCard(lastColumnActions);
      applyColumnActionsToDesign(lastColumnActions);
    }
  });

  const continueBtn = el("div", { class: "tab-continue" },
    el("button", {
      type: "button",
      class: "btn primary",
      id: "btn-analysis-continue",
      onclick: () => switchTab("design"),
    }, "Continue to design →")
  );

  const columnCard = el("section", { class: "panel", style: "margin-top: 18px; padding: 16px;" },
    el("div", { style: "display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;" },
      el("h3", { style: "margin: 0; font-size: 15px;" }, "Column to design"),
      el("div", { class: "control" }, colPicker)
    ),
    cardContent,
    continueBtn
  );

  const block = el("div", { class: "analysis-results-block" },
    el("h3", { style: "margin: 0 0 10px;" }, "Frame analysis results"),
    btnGroup,
    diagHost,
    rxTable,
    forcesTable,
    columnCard
  );

  container.replaceChildren(block);
}

async function performAnalysis() {
  errors.clear();
  const btn = $("btn-analyse-frame");
  btn.disabled = true;
  $("analysis-note").textContent = "Analysing…";
  try {
    const data = serialize();
    const res = await postJSON("/api/column/analysis", data);
    if (!res.ok) {
      if (res.status === 400 && res.data?.errors) {
        handleErrors(res.data.errors);
      } else {
        $("form-message").textContent = `Analysis error (${res.status}): ${res.data?.error || "Check inputs"}`;
      }
      $("analysis-note").textContent = "";
      return;
    }
    lastAnalysis = res.data;
    analysisDone = true;
    analysisDirty = false;
    $("analysis-note").textContent = "";
    updateTabStates();

    const vertMembers = res.data.vertical_members || [];
    let curMem = data.actions?.member;
    if (!curMem || !vertMembers.includes(curMem)) {
      curMem = vertMembers[0] || "";
    }
    selectedMemberId = curMem;

    let colAct = res.data.column_actions;
    lastColumnActionsError = res.data.column_actions_error;
    if (selectedMemberId && (!colAct || colAct.member !== selectedMemberId)) {
      const reData = { ...data, actions: { ...data.actions, member: selectedMemberId } };
      const reRes = await postJSON("/api/column/analysis", reData);
      if (reRes.ok) {
        lastAnalysis = reRes.data;
        colAct = reRes.data.column_actions;
        lastColumnActionsError = reRes.data.column_actions_error;
      }
    }
    lastColumnActions = colAct;
    form.elements["actions.member"].value = selectedMemberId;

    applyColumnActionsToDesign(colAct);
    renderAnalysisView(lastAnalysis);
  } catch (err) {
    $("form-message").textContent = "Could not reach the analysis server.";
    console.error(err);
  } finally {
    btn.disabled = false;
  }
}

function setupAdjustDesignValues() {
  $("adjust-design-values").addEventListener("change", (e) => {
    const adjust = e.target.checked;
    $("dv-ned").readOnly = !adjust;
    $("dv-myt").readOnly = !adjust;
    $("dv-myb").readOnly = !adjust;
    $("dv-mycurv").disabled = !adjust;

    form.elements["actions.mode"].value = adjust ? "direct" : "frame";
    if (adjust) {
      form.elements["actions.NEd"].value = $("dv-ned").value;
      form.elements["actions.My_top"].value = $("dv-myt").value;
      form.elements["actions.My_bottom"].value = $("dv-myb").value;
      form.elements["actions.My_curvature"].value = $("dv-mycurv").value;
      $("dv-warn").hidden = false;
    } else {
      $("dv-warn").hidden = true;
      if (lastColumnActions) {
        applyColumnActionsToDesign(lastColumnActions);
      }
    }
    updateTabStates();
    refresh();
  });

  for (const id of ["dv-ned", "dv-myt", "dv-myb"]) {
    $(id).addEventListener("input", () => {
      if ($("adjust-design-values").checked) {
        form.elements["actions.NEd"].value = $("dv-ned").value;
        form.elements["actions.My_top"].value = $("dv-myt").value;
        form.elements["actions.My_bottom"].value = $("dv-myb").value;
        refresh();
      }
    });
  }
  $("dv-mycurv").addEventListener("change", () => {
    if ($("adjust-design-values").checked) {
      form.elements["actions.My_curvature"].value = $("dv-mycurv").value;
      refresh();
    }
  });
}

function applyKToEnd(axis, end, val) {
  const name = `restraint.${axis}.${end}`;
  const preset = form.querySelector(`select[data-kfor="${name}"]`);
  const input = form.elements[name];
  if (!preset || !input) return;
  if (val === "pinned" || val === null || val === undefined) {
    preset.value = "pinned";
    input.value = "";
    input.disabled = true;
  } else if (Number(val) === 0.1) {
    preset.value = "0.1";
    input.value = "0.1";
    input.disabled = true;
  } else {
    preset.value = "custom";
    input.value = Number(val).toFixed(3);
    input.disabled = false;
  }
}

function setupUseFrameK() {
  $("btn-use-frame-k").addEventListener("click", () => {
    if (!lastColumnActions) {
      $("use-k-note").textContent = "Analyse the frame first to get k.";
      return;
    }
    const { k_top, k_bottom } = lastColumnActions;
    const choiceY = form.querySelector('select[data-endfor="y"]');
    if (choiceY) choiceY.value = "beams";

    applyKToEnd("y", "k_top", k_top);
    applyKToEnd("y", "k_bottom", k_bottom);

    if ($("same-axes").checked) {
      const choiceZ = form.querySelector('select[data-endfor="z"]');
      if (choiceZ) choiceZ.value = "beams";
      applyKToEnd("z", "k_top", k_top);
      applyKToEnd("z", "k_bottom", k_bottom);
    }
    const topStr = k_top === "pinned" ? "pinned" : Number(k_top).toFixed(3);
    const botStr = k_bottom === "pinned" ? "pinned" : Number(k_bottom).toFixed(3);
    $("use-k-note").textContent = `Applied from frame: top k = ${topStr}, bottom k = ${botStr}`;
    refresh();
  });
}

async function performDesignChecks() {
  errors.clear();
  const btn = $("btn-run-design");
  btn.disabled = true;
  try {
    const data = serialize();
    const res = await postJSON("/api/column/check", data);
    if (!res.ok) {
      if (res.status === 400 && res.data?.errors) {
        handleErrors(res.data.errors);
      } else {
        $("form-message").textContent = `Server error (${res.status}): ${res.data?.error || "Check inputs"}`;
      }
      return;
    }
    store.set(KEYS.input, data);
    store.setSession(KEYS.result, { input: data, result: res.data });
    designDone = true;
    updateTabStates();
    renderDesignResults(res.data);
    $("report-frame").src = "/column/report?embed=1";
  } catch (err) {
    $("form-message").textContent = "Could not reach the server.";
    console.error(err);
  } finally {
    btn.disabled = false;
  }
}

function renderDesignResults(result) {
  const c = result.summary.counts;
  const verdict = result.summary.verdict;
  const titleText = c.fail ? `Not adequate: ${c.fail} check${c.fail > 1 ? "s" : ""} fail`
    : c.warn ? `Adequate, with ${c.warn} warning${c.warn > 1 ? "s" : ""}`
      : `Adequate: all ${c.pass} checks pass`;

  const counts = el("div", { class: "design-counts" },
    `${result.summary.counts.pass} passed · ${result.summary.counts.fail} failed`
    + (result.summary.counts.warn ? ` · ${result.summary.counts.warn} warning${result.summary.counts.warn > 1 ? "s" : ""}` : "")
  );

  let rowIndex = 0;
  const groupNodes = [];
  (result.groups || []).forEach((grp) => {
    const checks = result.checks.filter((chk) => chk.group === grp);
    if (!checks.length) return;
    const rows = checks.map((chk) => {
      const idx = rowIndex++;
      const row = el("div", { class: `design-check-row check-row-animated ${chk.status === "fail" ? "is-fail" : ""}` },
        statusDot(chk.status),
        el("span", { class: "check-title" }, chk.title),
        el("span", { class: "check-res" }, chk.result || "")
      );
      row.style.animationDelay = `${idx * 25}ms`;
      return row;
    });
    groupNodes.push(el("div", { class: "design-checks-group" },
      el("div", { class: "design-group-title" }, grp),
      ...rows
    ));
  });

  const continueBtn = el("div", { class: "tab-continue" },
    el("button", { type: "button", class: "btn primary", onclick: () => switchTab("report") }, "Continue to report →")
  );

  const block = el("div", { class: "design-results-block" },
    el("div", { class: `design-verdict-head ${verdict}` }, titleText),
    counts,
    ...groupNodes,
    continueBtn
  );
  $("design-results-area").replaceChildren(block);
}

function setupReportTab() {
  $("btn-pdf").addEventListener("click", async () => {
    const btn = $("btn-pdf");
    btn.disabled = true;
    try {
      const res = await fetch("/api/column/report.pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(serialize()),
      });
      if (!res.ok) throw new Error(String(res.status));
      const name = /filename="?([^";]+)"?/.exec(res.headers.get("Content-Disposition") || "")?.[1] || "EC2-column-check.pdf";
      downloadBlob(await res.blob(), name);
    } catch (e) {
      console.error(e);
    } finally {
      btn.disabled = false;
    }
  });

  $("btn-print").addEventListener("click", () => {
    const frame = $("report-frame");
    if (frame?.contentWindow) frame.contentWindow.print();
  });

  fitFrame($("report-frame"));
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

// ------------------------------------------------------------------ init

async function init() {
  meta = await getJSON("/api/meta");
  populate();
  buildRestraint();
  setupTabs();
  setupAdjustDesignValues();
  setupUseFrameK();
  setupReportTab();
  setupSections(form, OPEN_KEY);

  fill(store.get(KEYS.input) || structuredClone(EXAMPLES.frame_pass));
  const serverErrors = store.getSession(KEYS.errors);
  if (serverErrors) { handleErrors(serverErrors); store.setSession(KEYS.errors, null); }

  let timer = null;
  form.addEventListener("input", (e) => {
    if (e.target.closest("#panel-analysis") && analysisDone) {
      analysisDirty = true;
      $("analysis-note").textContent = "Inputs changed: analyse again";
    }
    if (e.target.dataset.path) { onTableInput(e); return; }
    clearTimeout(timer);
    timer = setTimeout(refresh, 90);
  });

  form.addEventListener("change", (e) => {
    if (e.target.closest("#panel-analysis") && analysisDone) {
      analysisDirty = true;
      $("analysis-note").textContent = "Inputs changed: analyse again";
    }
    if (e.target.dataset.path) {
      if (e.target.tagName === "SELECT" || e.target.dataset.path.endsWith(".id")) onTableInput(e);
      return;
    }
    if (e.target.name === "actions.mode") {
      updateTabStates();
      syncVisibility();
    }
    refresh();
  });

  $("same-axes").addEventListener("change", refresh);
  for (const button of document.querySelectorAll(".switch [data-axis]")) {
    button.addEventListener("click", () => {
      previewAxis = button.dataset.axis;
      document.querySelectorAll(".switch [data-axis]").forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
      refresh();
    });
  }

  $("btn-analyse-frame").addEventListener("click", performAnalysis);
  $("btn-continue-direct").addEventListener("click", () => switchTab("design"));
  $("btn-run-design").addEventListener("click", performDesignChecks);

  $("add-node").addEventListener("click", () => {
    const nextIdx = frameModel.nodes.length + 1;
    frameModel.nodes.push({ id: `N${nextIdx}`, x: 0, y: 0 });
    renderTables();
    refresh();
  });
  $("add-member").addEventListener("click", () => {
    const nextIdx = frameModel.members.length + 1;
    const n1 = frameModel.nodes[0]?.id || "N1";
    const n2 = frameModel.nodes[1]?.id || n1;
    frameModel.members.push({ id: `M${nextIdx}`, node1: n1, node2: n2, b: 300, h: 300 });
    renderTables();
    refresh();
  });
  $("add-support").addEventListener("click", () => {
    const n1 = frameModel.nodes[0]?.id || "N1";
    frameModel.supports.push({ node: n1, type: "fixed" });
    renderSupports();
    refresh();
  });
  $("add-load").addEventListener("click", () => {
    const m1 = frameModel.members[0]?.id || "C1";
    frameModel.loads.push({ type: "udl", member: m1, w: 20, case: "G" });
    renderLoads();
    refresh();
  });

  document.addEventListener("themechange", refresh);
  setupHelpers();
  setupFilesMenu({
    examples: EXAMPLES, fill, errors, inputKey: KEYS.input, message: $("form-message"), resetTo: "frame_pass",
    looksValid: (d) => Boolean(d.geometry || d.frame),
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (valueOf("actions.mode") !== "direct" && (!analysisDone || analysisDirty)) {
      await performAnalysis();
    }
    if ($("tab-design").getAttribute("aria-disabled") === "true") return;
    switchTab("design");
    await performDesignChecks();
    $("design-results-area").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  const initialHash = location.hash.replace("#", "");
  if (TAB_NAMES.includes(initialHash)) {
    switchTab(initialHash);
  }
}

init().catch((err) => {
  $("form-message").textContent = "Could not reach the server. Start it with: .venv/bin/python app.py";
  console.error(err);
});
