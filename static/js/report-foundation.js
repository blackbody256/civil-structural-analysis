// Pad foundation report: plan and section from the server's figures, design values and design path.
import { el, worst } from "./common.js";
import { renderFigure } from "./figure-spec.js";
import { num, table } from "./beam-analysis-view.js";
import { arrow, block, figure, node } from "./report-parts.js";

function drawn(spec, label) {
  const box = el("div");
  if (spec) queueMicrotask(() => renderFigure(box, spec, label));
  return box;
}

const num1 = (v) => num(v, 1);

function designValues(result) {
  const d = result.derived;
  const rows = [
    ["Characteristic load on the ground P", `${num1(d.P)} kN`, "with the base and the soil over it"],
    ["Largest bearing pressure", d.sls_p1 === null ? "overturns" : `${num1(d.sls_p1)} kPa`, d.q_allow ? `allowable ${d.q_allow} kPa` : ""],
    ["Design column load NEd", `${num1(d.NEd)} kN`, "1.35·Gk + 1.5·Qk"],
    ["Design moment MEd", `${num1(d.MEd)} kNm`, "1.35·MGk + 1.5·MQk"],
    ["Net design ground pressure", d.uls_p1 === null ? "overturns" : `${num1(d.uls_p1)} / ${num1(d.uls_p2)} kPa`, "max / min"],
  ];
  if (d.Mx !== undefined) {
    rows.push(
      ["Moment at the column face", `${num1(d.Mx)} / ${num1(d.My)} kNm`, "bars along L / along B"],
      ["Beam shear at d from the face", `${num1(d.Vx)} / ${num1(d.Vy)} kN`, "along L / along B"]);
  }
  return figure("Design values", table(["Design value", "Value", "Notes"], rows), "Every value used by the checks below.");
}

export function figures(state) {
  const { result } = state;
  const figs = result.plots.figures || {};
  const plan = figure("Plan", drawn(figs.plan, "Pad foundation plan"),
    "To scale: bars both ways, beam-shear lines at d from the column faces and the punching perimeters. Failed parts are red.");
  const section = figure("Section and ground pressure", drawn(figs.section, "Pad foundation section"),
    "Section along L with the bearing pressure (characteristic) and the design ground pressure (STR).");
  const values = designValues(result);
  values.classList.add("wide");
  return el("div", { class: "figures" }, plan, section, values);
}

export function designPath(result) {
  const by = Object.fromEntries(result.checks.map((c) => [c.id, c]));
  const d = result.derived;
  const status = (id) => by[id]?.status ?? "na";
  const value = (id, fallback = "") => by[id]?.markup?.result || by[id]?.result || fallback;
  const pair = (a, b) => worst([status(a), status(b)]);
  const detailing = worst(result.checks.filter((c) => c.group === "Detailing").map((c) => c.status));
  const flow = [
    node("Characteristic loads", `P = ${num1(d.P)} kN, M = ${num1(d.M)} kNm`),
    arrow(),
    node("Bearing pressure", value("bearing"), status("bearing")),
    arrow(),
    node("Overturning (EQU)", value("overturning", "No moment"), status("overturning") === "na" ? "off" : status("overturning")),
    arrow(),
    node("Design loads (STR)", `NEd = ${num1(d.NEd)} kN, MEd = ${num1(d.MEd)} kNm`),
    arrow(),
    el("div", { class: "flow-branch" },
      el("div", { class: "col on" }, el("span", { class: "tag-line" }, "Bars along L"), node("Bending at the face", value("bending_x"), status("bending_x"))),
      el("div", { class: "col on" }, el("span", { class: "tag-line" }, "Bars along B"), node("Bending at the face", value("bending_y"), status("bending_y")))),
    arrow(),
    node("Beam shear at d", `${value("shear_x", "—")} · ${value("shear_y", "—")}`, pair("shear_x", "shear_y")),
    arrow(),
    node("Punching shear", `${value("punching_face", "—")} at the face<br>${value("punching", "—")}`, pair("punching_face", "punching")),
    arrow(),
    node("Detailing", detailing === "fail" ? "Some detailing checks failed" : "All detailing checks pass", detailing === "fail" ? "fail" : "pass"),
  ];
  return block("Design path", { open: true }, el("div", { class: "flow" }, ...flow));
}
