// Results (Structural Analysis & Design): the governing utilisation as a ring gauge, the verdict and counts, and the checks by group.
// Used by the Design step of the beam, slab and column pages and by the report summary.
import { el, fmt, statusDot } from "./common.js";

const RATED = new Set(["pass", "fail", "warn"]);
const SVG = "http://www.w3.org/2000/svg";
const svg = (tag, attrs = {}) => {
  const n = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
};

/** The rated check with the highest utilisation, or null. */
export function governingCheck(result) {
  return result.checks
    .filter((c) => RATED.has(c.status) && c.utilisation !== null && Number.isFinite(c.utilisation))
    .reduce((a, b) => (b.utilisation > (a?.utilisation ?? -1) ? b : a), null);
}

/** A ring filled to the utilisation (full and red above 1), the value in the middle. */
export function gauge(u, status, size = 132) {
  const r = 52, c = 2 * Math.PI * r;
  const shown = Math.max(0, Math.min(u, 1));
  const ring = svg("svg", { viewBox: "0 0 128 128", width: size, height: size, class: "gauge", role: "img",
    "aria-label": `Governing utilisation ${fmt(u, 2)}` });
  ring.append(
    svg("circle", { cx: 64, cy: 64, r, class: "gauge-track" }),
    svg("circle", { cx: 64, cy: 64, r, class: `gauge-arc ${status}`, "stroke-dasharray": `${c * shown} ${c}`,
      transform: "rotate(-90 64 64)" }),
  );
  const value = svg("text", { x: 64, y: 70, class: "gauge-value", "text-anchor": "middle" });
  value.textContent = fmt(u, 2);
  const label = svg("text", { x: 64, y: 90, class: "gauge-label", "text-anchor": "middle" });
  label.textContent = "utilisation";
  ring.append(value, label);
  return ring;
}

function verdictTitle(c) {
  return c.fail ? `Not adequate: ${c.fail} check${c.fail > 1 ? "s" : ""} fail`
    : c.warn ? `Adequate, with ${c.warn} warning${c.warn > 1 ? "s" : ""}`
      : `Adequate: all ${c.pass} checks pass`;
}

/** Counts as chips; a zero count is shown quietly. */
export function countChips(c) {
  const chip = (status, n, text) => el("span", { class: `chip-count ${status}${n ? "" : " zero"}` }, `${n} ${text}`);
  return el("div", { class: "chips-count" },
    chip("pass", c.pass, "pass"), chip("fail", c.fail, "fail"),
    chip("warn", c.warn, c.warn === 1 ? "warning" : "warnings"), chip("info", c.info, "for information"));
}

/** Gauge, verdict and counts: the head of the Design step's results and of the report summary. */
export function resultsHead(result) {
  const gov = governingCheck(result);
  const status = gov ? (gov.utilisation > 1 ? "fail" : gov.status) : "pass";
  return el("div", { class: `results-head ${result.summary.verdict}` },
    gov ? gauge(gov.utilisation, status) : null,
    el("div", { class: "results-verdict" },
      el("p", { class: `results-title ${result.summary.verdict}` }, verdictTitle(result.summary.counts)),
      gov ? el("p", { class: "results-gov" }, "Governed by ", el("strong", {}, gov.title), ` at ${fmt(gov.utilisation, 2)}`) : null,
      countChips(result.summary.counts)));
}

/** The Design step's results: head, then every check in a numbered grid by group, then the button to the report. */
export function designResults(result, { onContinue, continueLabel = "Continue to report" } = {}) {
  let no = 0;
  const rows = [];
  for (const group of result.groups || []) {
    const checks = result.checks.filter((c) => c.group === group);
    if (!checks.length) continue;
    rows.push(el("tr", { class: "group-row" }, el("td", { colspan: "4" }, group)));
    for (const c of checks) {
      rows.push(el("tr", { class: c.status === "fail" ? "is-fail" : "" },
        el("td", { class: "no" }, String(++no)),
        el("td", {}, c.title),
        el("td", { class: "res", html: c.markup?.result ?? c.result ?? "" }),
        el("td", { class: "st" }, statusDot(c.status))));
    }
  }
  const grid = el("div", { class: "data-wrap" }, el("table", { class: "data results-grid" },
    el("thead", {}, el("tr", {}, el("th", { class: "no" }, "No."), el("th", {}, "Check"), el("th", {}, "Result"),
      el("th", { class: "st" }, "Status"))),
    el("tbody", {}, ...rows)));
  return el("div", { class: "design-results-block" },
    resultsHead(result),
    grid,
    onContinue ? el("div", { class: "tab-continue" },
      el("button", { type: "button", class: "btn primary", onclick: onContinue }, continueLabel)) : null);
}
