// Report (Structural Analysis & Design): set out like an engineer's calculation pad. A title block, then
// A Design data (the inputs beside a 3D model whose failed parts glow red), B Drawings and analysis,
// C Design checks in Ref | Calculation | Output columns, D Conclusion (the verdict stamp, the governing check
// and the utilisations) and E Assumptions. Sections slide in as they scroll into view.
import {
  currentElement, downloadBlob, el, ELEMENT_TITLES, fmt, getJSON, guideHref, keysFor, store, STATUS_TEXT,
} from "./common.js";
import { plural, targetStatus } from "./report-parts.js";
import { anchorPopover } from "./theme.js";
import { gauge, governingCheck } from "./results-view.js";
import { createViewer } from "./viewer3d.js";
import { elementScene } from "./models3d.js";

const element = currentElement();
const TITLE = ELEMENT_TITLES[element];
const root = document.getElementById("report");
const RATED = new Set(["pass", "fail", "warn"]);
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const STAMP = { pass: "PASS", fail: "FAIL", warn: "CHECK", info: "INFO", na: "N/A" };

if (new URLSearchParams(location.search).get("embed") === "1") document.documentElement.classList.add("embed");

const today = () => new Date().toISOString().slice(0, 10);

function verdict(c) {
  if (c.fail) return { word: "Not adequate", status: "fail", line: `${plural(c.fail, "check")} fail` };
  if (c.warn) return { word: "Adequate", status: "warn", line: `with ${plural(c.warn, "warning")}` };
  return { word: "Adequate", status: "pass", line: `all ${c.pass} checks pass` };
}

// ------------------------------------------------------------------ title block

function titleBlock(state) {
  const { result } = state;
  const p = result.project;
  const v = verdict(result.summary.counts);
  const cell = (k, val, cls = "") => el("div", { class: `tb-cell ${cls}` }, el("span", { class: "tb-k" }, k), el("span", { class: "tb-v" }, val || "—"));
  const exportBtn = el("button", { type: "button", class: "btn", popovertarget: "export-menu" }, "Export ", el("span", { class: "caret" }));
  return el("header", { class: "title-block" },
    el("div", { class: "tb-brand" },
      el("span", { class: "tb-mark", "aria-hidden": "true" }),
      el("div", {}, el("strong", {}, "Structural Analysis & Design"), el("span", {}, "Calculation sheet · Eurocode 2"))),
    el("div", { class: "tb-grid" },
      cell("Project", p.name), cell("Element", `${TITLE}${p.ref ? ` · ${p.ref}` : ""}`),
      cell("Made by", p.engineer), cell("Date", p.date || today()),
      cell("Code", "BS EN 1992-1-1 + UK NA"), cell("Checks", `${result.checks.length} run, ${result.summary.counts.pass + result.summary.counts.fail + result.summary.counts.warn} with a limit`),
      cell("Result", `${v.word}: ${v.line}`, `tb-result ${v.status}`)),
    el("div", { class: "tb-actions" }, exportBtn, el("a", { class: "btn", href: `/${element}` }, "Edit inputs")));
}

function setupExport(state) {
  const menu = document.getElementById("export-menu");
  anchorPopover(menu, () => document.querySelector('[popovertarget="export-menu"]'), "end");
  const ref = (state.result.project.ref || element).replace(/[^A-Za-z0-9_-]+/g, "-");
  const pdfItem = document.getElementById("export-pdf");
  pdfItem.addEventListener("click", async () => {
    pdfItem.disabled = true;
    try {
      const res = await fetch(`/api/${element}/report.pdf`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state.input),
      });
      if (!res.ok) throw new Error(String(res.status));
      const name = /filename="?([^";]+)"?/.exec(res.headers.get("Content-Disposition") || "")?.[1] || `Structural_Analysis_and_Design-${element}-check.pdf`;
      downloadBlob(await res.blob(), name);
      menu.hidePopover();
    } catch {
      pdfItem.querySelector(".sub").textContent = "Could not create the PDF. Is the server running?";
    } finally {
      pdfItem.disabled = false;
    }
  });
  document.getElementById("export-print").addEventListener("click", () => { menu.hidePopover(); window.print(); });
  document.getElementById("export-json").addEventListener("click", () => {
    downloadBlob(new Blob([JSON.stringify(state.input, null, 2)], { type: "application/json" }), `Structural_Analysis_and_Design-${element}-${ref}.json`);
    menu.hidePopover();
  });
}

// ------------------------------------------------------------------ sections

function sheet(letter, title, lede, ...body) {
  return el("section", { class: "sheet-sec", id: `sec-${letter}` },
    el("div", { class: "sec-head" }, el("span", { class: "sec-letter" }, letter), el("h2", {}, title),
      lede ? el("p", { class: "sec-lede" }, lede) : null),
    ...body);
}

/** A: the inputs as a schedule beside the 3D model. */
function designData(state, meta) {
  const { result } = state;
  const rows = result.inputs.map((i) => el("tr", {}, el("th", { scope: "row" }, i.label), el("td", {}, i.value)));
  const model = el("div", { class: "vp-host report-model" });
  const status = targetStatus(result.checks);
  const failed = Object.values(status).includes("fail");
  const legend = el("p", { class: "model-note" }, failed
    ? "Parts drawn red failed a check: turn the model to find them. X-ray shows the bars inside."
    : "Every part of the element passes its checks. X-ray shows the bars inside.");
  // the model is built when it first scrolls into view, so its build-up animation is seen
  const io = new IntersectionObserver((entries) => {
    if (!entries.some((e) => e.isIntersecting)) return;
    io.disconnect();
    const viewer = createViewer(model, { spin: "sway" });
    viewer.setScene(elementScene(element, state.input, state.result, { status, meta }), { replay: true });
  }, { threshold: 0.25 });
  queueMicrotask(() => io.observe(model));
  return el("div", { class: "data-grid" },
    el("div", { class: "schedule" }, el("h3", {}, "Input schedule"),
      el("table", { class: "schedule-table" }, el("tbody", {}, rows))),
    el("figure", { class: "model-fig" }, model, el("figcaption", {}, legend)));
}

/** C: every check as a row of the pad, grouped and numbered C1.1, C1.2 … */
function checks(result) {
  let g = 0;
  const out = [];
  const index = [];
  for (const group of result.groups) {
    const items = result.checks.filter((c) => c.group === group);
    if (!items.length) continue;
    g += 1;
    const fails = items.filter((c) => c.status === "fail").length;
    index.push(el("a", { href: `#grp-${g}`, class: fails ? "has-fail" : "" }, el("b", {}, `C${g}`), group,
      el("span", { class: "dots" }, items.map((c) => el("i", { class: c.status, title: `${c.title}: ${STATUS_TEXT[c.status]}` })))));
    const rows = items.map((c, i) => el("tr", { id: `check-${c.id}`, class: `row-${c.status}` },
      el("td", { class: "ref" }, el("span", { class: "no" }, `C${g}.${i + 1}`),
        ...(c.refs || []).map((r) => (r.page ? el("a", { href: guideHref(r.page), target: "_blank", rel: "noopener" }, r.label) : el("span", {}, r.label)))),
      el("td", { class: "calc" }, el("div", { class: "ct" }, c.title),
        ...c.markup.working.map((w) => el("div", { class: "wl", html: w })),
        c.note ? el("div", { class: "note", html: c.markup.note }) : null),
      el("td", { class: "out" }, el("div", { class: "res", html: c.markup.result }),
        el("span", { class: `stamp ${c.status}` }, STAMP[c.status]),
        c.utilisation !== null && Number.isFinite(c.utilisation) ? utilBar(c.utilisation, c.status) : null)));
    out.push(el("div", { class: "grp", id: `grp-${g}` },
      el("h3", {}, el("span", {}, `C${g}`), group, el("small", {}, [
        items.filter((c) => c.status === "pass").length && `${items.filter((c) => c.status === "pass").length} pass`,
        fails && `${fails} fail`, items.filter((c) => c.status === "warn").length && plural(items.filter((c) => c.status === "warn").length, "warning"),
      ].filter(Boolean).join(" · "))),
      el("table", { class: "pad" },
        el("thead", {}, el("tr", {}, el("th", { class: "ref" }, "Ref"), el("th", {}, "Calculation"), el("th", { class: "out" }, "Output"))),
        el("tbody", {}, rows))));
  }
  return [el("nav", { class: "grp-index", "aria-label": "Check groups" }, index), ...out];
}

function utilBar(u, status) {
  const fill = el("i", { class: u > 1 ? "fail" : status === "warn" ? "warn" : "" });
  fill.style.setProperty("--u", String(Math.min(u, 1)));
  return el("div", { class: "util" }, el("span", { class: "util-track" }, fill), el("span", { class: "util-val" }, `u = ${fmt(u, 2)}`));
}

/** D: the verdict stamp, the governing check, every utilisation and what needs attention. */
function conclusion(result) {
  const c = result.summary.counts;
  const v = verdict(c);
  const gov = governingCheck(result);
  const rated = result.checks.filter((x) => RATED.has(x.status) && x.utilisation !== null && Number.isFinite(x.utilisation))
    .sort((a, b) => b.utilisation - a.utilisation);
  const attention = result.checks.filter((x) => x.status === "fail" || x.status === "warn");
  const count = (n, label, cls) => el("div", { class: `tally ${cls}` }, el("b", { "data-count": String(n) }, String(n)), el("span", {}, label));
  return el("div", { class: "concl" },
    el("div", { class: "concl-top" },
      el("div", { class: `verdict-stamp ${v.status}`, role: "img", "aria-label": `${v.word}: ${v.line}` },
        el("span", { class: "vs-word" }, v.word), el("span", { class: "vs-line" }, v.line)),
      gov ? el("div", { class: "gov" }, gauge(gov.utilisation, gov.utilisation > 1 ? "fail" : gov.status, 120),
        el("div", {}, el("span", { class: "k" }, "Governing check"), el("a", { href: `#check-${gov.id}` }, gov.title),
          el("span", { class: "gov-res", html: gov.markup.result }))) : null,
      el("div", { class: "tallies" }, count(c.pass, "pass", "pass"), count(c.fail, "fail", "fail"), count(c.warn, c.warn === 1 ? "warning" : "warnings", "warn"),
        count(c.info, "for information", "info"))),
    el("div", { class: "concl-cols" },
      el("div", { class: "bars" }, el("h3", {}, "Utilisation of every rated check"),
        rated.map((x) => el("a", { class: "bar-row", href: `#check-${x.id}` }, el("span", { class: "bt" }, x.title), utilBar(x.utilisation, x.status)))),
      el("div", { class: "attention" }, el("h3", {}, "Needs attention"),
        attention.length ? el("ul", {}, attention.map((x) => el("li", { class: x.status },
          el("a", { href: `#check-${x.id}` }, x.title), el("span", { html: x.markup.result }))))
          : el("p", { class: "none" }, "Nothing: every check passes."))));
}

// ------------------------------------------------------------------ motion

function animateIn() {
  const secs = [...root.querySelectorAll(".sheet-sec")];
  if (REDUCED || !("IntersectionObserver" in window)) { secs.forEach((s) => s.classList.add("is-in")); return; }
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      e.target.classList.add("is-in");
      io.unobserve(e.target);
      for (const b of e.target.querySelectorAll("[data-count]")) countUp(b);
    }
  }, { threshold: 0.08 });
  secs.forEach((s) => io.observe(s));
}

function countUp(node) {
  const to = Number(node.dataset.count);
  const t0 = performance.now();
  const tick = (now) => {
    const t = Math.min(1, (now - t0) / 900);
    node.textContent = String(Math.round(to * (1 - (1 - t) ** 3)));
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// ------------------------------------------------------------------ page

function render(state, parts, meta) {
  const { result } = state;
  document.title = `${TITLE} report · Structural Analysis & Design`;
  const crumb = document.getElementById("crumb-element");
  crumb.textContent = TITLE;
  crumb.href = `/${element}`;
  const drawings = parts.figures(state);
  root.replaceChildren(
    titleBlock(state),
    sheet("A", "Design data", "What was checked: the inputs as entered, and the element built from them.", designData(state, meta)),
    sheet("B", "Drawings and analysis", "The section and elevation to scale, and the structural analysis the design actions come from.",
      drawings, parts.designPath ? parts.designPath(result) : null),
    sheet("C", "Design checks", "Each check in the order of the design procedure: the guide reference, the working, and the output.",
      ...checks(result)),
    sheet("D", "Conclusion", null, conclusion(result)),
    sheet("E", "Assumptions", null,
      el("ol", { class: "assume" }, result.assumptions.map((a) => el("li", {}, a))),
      el("p", { class: "notice" }, "For learning and preliminary checking. A qualified structural engineer must verify the inputs and results.")),
    el("footer", { class: "sheet-foot" },
      el("span", {}, "Structural Analysis & Design"),
      el("span", {}, `${TITLE}${result.project.ref ? ` ${result.project.ref}` : ""} · ${result.project.date || today()}`),
      el("span", {}, "End of calculations")));
  setupExport(state);
  animateIn();
  for (const a of root.querySelectorAll('a[href^="#check-"], .grp-index a')) {
    a.addEventListener("click", (e) => {
      const target = document.querySelector(a.getAttribute("href"));
      if (!target) return;
      e.preventDefault();
      target.closest(".sheet-sec")?.classList.add("is-in");
      target.scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "center" });
      target.classList.add("target");
      setTimeout(() => target.classList.remove("target"), 2200);
    });
  }
}

async function main() {
  const state = store.getSession(keysFor(element).result);
  if (!state?.result) {
    root.replaceChildren(el("p", { class: "empty" }, "No results yet. ",
      el("a", { href: `/${element}` }, `Enter a ${TITLE.toLowerCase()} to check`)));
    return;
  }
  const [parts, meta] = await Promise.all([import(`./report-${element}.js`), getJSON("/api/meta").catch(() => null)]);
  render(state, parts, meta);
  if (location.hash.startsWith("#check-")) document.querySelector(location.hash)?.scrollIntoView({ block: "center" });
}

main();
