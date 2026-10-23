import { currentElement, el, ELEMENT_TITLES, keysFor, postJSON, SEVERITY, STATUS_SVG, store, verdictText } from "./common.js";
import { drawBeamSection, drawSection } from "./drawings.js";

const element = currentElement();
const KEYS = keysFor(element);
const draw = { column: drawSection, beam: drawBeamSection }[element];

const list = document.getElementById("run-list");
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let skip = false;

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, skip || reduceMotion ? 0 : ms));

function sectionStatus(checks) {
  const status = {};
  for (const c of checks) {
    if (!c.target) continue;
    if ((SEVERITY[c.status] ?? 0) > (SEVERITY[status[c.target]] ?? 0)) status[c.target] = c.status;
  }
  return status;
}

function buildList(result) {
  const rows = [];
  const items = [];
  result.groups.forEach((group) => {
    const checks = result.checks.filter((c) => c.group === group);
    if (!checks.length) return;
    rows.push(el("li", { class: "run-group" }, group));
    for (const c of checks) {
      const icon = el("span", { class: "icon", "aria-hidden": "true" });
      const res = el("span", { class: "r" });
      const row = el("li", { class: "run-item" }, icon, el("span", { class: "t" }, c.title), res);
      rows.push(row);
      items.push({ check: c, row, icon, res });
    }
  });
  list.replaceChildren(...rows);
  return items;
}

async function animate(result) {
  const items = buildList(result);
  const counts = { pass: 0, fail: 0, warn: 0, info: 0, na: 0 };
  const done = [];
  document.getElementById("n-total").textContent = items.length;
  draw(document.getElementById("run-section"), result.plots.section, {});
  for (const [i, item] of items.entries()) {
    item.row.classList.add("active");
    if (!skip && !reduceMotion) item.row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    await wait(150);
    const status = item.check.status;
    item.row.classList.remove("active");
    item.row.classList.add("done", status);
    item.icon.innerHTML = STATUS_SVG[status];
    item.res.innerHTML = item.check.markup.result;
    counts[status] += 1;
    done.push(item.check);
    for (const k of ["pass", "fail", "warn", "info"]) document.getElementById(`n-${k}`).textContent = counts[k];
    document.getElementById("n-done").textContent = i + 1;
    document.getElementById("run-bar").style.width = `${((i + 1) / items.length) * 100}%`;
    document.getElementById("run-hint").textContent = item.check.group;
    if (item.check.target) {
      draw(document.getElementById("run-section"), result.plots.section, { status: sectionStatus(done) });
    }
    await wait(40);
  }
  const verdict = result.summary.verdict;
  const stamp = document.getElementById("stamp");
  stamp.className = `stamp ${verdict}`;
  stamp.textContent = verdict === "fail" ? "Not adequate" : verdict === "warn" ? "Adequate, with warnings" : "Adequate";
  requestAnimationFrame(() => stamp.classList.add("show"));
  document.getElementById("run-title").textContent = verdictText(result.summary);
  document.getElementById("run-lede").textContent = "All tests have run. The report opens next: the summary first, then the full calculations.";
  document.getElementById("skip").hidden = true;
  document.getElementById("open").hidden = false;
  await new Promise((resolve) => setTimeout(resolve, reduceMotion ? 600 : 1800));
  window.location.href = `/${element}/report`;
}

async function main() {
  document.getElementById("skip").addEventListener("click", () => { skip = true; });
  const crumb = document.getElementById("crumb-element");
  crumb.textContent = ELEMENT_TITLES[element];
  crumb.href = `/${element}`;
  document.getElementById("open").href = `/${element}/report`;
  document.title = `Running Checks · ${ELEMENT_TITLES[element]} · EC2 Checker`;
  const input = store.get(KEYS.input);
  if (!input) { window.location.replace(`/${element}`); return; }
  let res;
  try {
    res = await postJSON(`/api/${element}/check`, input);
  } catch {
    list.replaceChildren(el("li", { class: "empty" }, "Could not reach the calculation server. Is app.py running?"));
    return;
  }
  if (res.status === 400 && res.data?.errors) {
    store.setSession(KEYS.errors, res.data.errors);
    window.location.replace(`/${element}`);
    return;
  }
  if (!res.ok || !res.data?.checks) {
    list.replaceChildren(el("li", { class: "empty" }, `The server could not run the checks (${res.status}).`));
    return;
  }
  store.setSession(KEYS.result, { input, result: res.data });
  await animate(res.data);
}

main();
