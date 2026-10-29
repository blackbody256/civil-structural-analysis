// Report page for any element: summary first, then the full calculations.
import {
  currentElement, downloadBlob, el, ELEMENT_TITLES, fmt, keysFor, meter, statusDot, store, worst,
} from "./common.js";
import { block, plural } from "./report-parts.js";
import { anchorPopover } from "./theme.js";

const element = currentElement();
const TITLE = ELEMENT_TITLES[element];
const root = document.getElementById("report");
const RATED = new Set(["pass", "fail", "warn"]);

/** Open the collapsed group holding a check, scroll to it and mark it briefly. */
function reveal(id) {
  const row = document.getElementById(id);
  if (!row) return;
  const details = row.closest("details");
  if (details) details.open = true;
  row.scrollIntoView({ behavior: "smooth", block: "center" });
  row.classList.add("target");
  setTimeout(() => row.classList.remove("target"), 2200);
}

function checkLink(c, ...children) {
  return el("a", { href: `#check-${c.id}`, onclick: (e) => { e.preventDefault(); reveal(`check-${c.id}`); } }, ...children);
}

// ------------------------------------------------------------------ header

function header(state) {
  const { result } = state;
  const p = result.project;
  const c = result.summary.counts;
  const title = el("h1");
  if (c.fail) {
    title.append(el("span", { class: "verdict-word" }, "Not adequate"), `: ${plural(c.fail, "check")} fail`);
  } else if (c.warn) {
    title.append(el("span", { class: "verdict-word warn" }, "Adequate"), `, with ${plural(c.warn, "warning")}`);
  } else {
    title.append(el("span", { class: "verdict-word pass" }, "Adequate"), `: all ${c.pass} checks pass`);
  }
  const exportBtn = el("button", { type: "button", class: "btn", popovertarget: "export-menu" }, "Export ", el("span", { class: "caret" }));
  return el("div", { class: "report-head" },
    el("p", { class: "context" }, TITLE),
    el("div", {}, title,
      el("p", { class: "meta" }, [p.engineer, p.date || new Date().toISOString().slice(0, 10),
        "BS EN 1992-1-1 with the UK National Annex"].filter(Boolean).join(" · "))),
    el("div", { class: "actions" }, exportBtn, el("a", { class: "btn", href: `/${element}` }, "Edit inputs")));
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
      const name = /filename="?([^";]+)"?/.exec(res.headers.get("Content-Disposition") || "")?.[1] || `EC2-${element}-check.pdf`;
      downloadBlob(await res.blob(), name);
      menu.hidePopover();
    } catch {
      pdfItem.querySelector(".sub").textContent = "Could not create the PDF. Is the server running?";
    } finally {
      pdfItem.disabled = false;
    }
  });
  document.getElementById("export-print").addEventListener("click", () => {
    menu.hidePopover();
    const closed = [...document.querySelectorAll("details:not([open])")];
    closed.forEach((d) => { d.open = true; });
    window.print();
    closed.forEach((d) => { d.open = false; });
  });
  document.getElementById("export-json").addEventListener("click", () => {
    downloadBlob(new Blob([JSON.stringify(state.input, null, 2)], { type: "application/json" }), `EC2-${element}-${ref}.json`);
    menu.hidePopover();
  });
}

// ------------------------------------------------------------------ summary

function governing(result) {
  const rated = result.checks.filter((c) => RATED.has(c.status) && c.utilisation !== null && Number.isFinite(c.utilisation));
  const gov = rated.reduce((a, b) => (b.utilisation > (a?.utilisation ?? -1) ? b : a), null);
  const c = result.summary.counts;
  const attention = result.checks.filter((x) => x.status === "fail" || x.status === "warn");
  const status = gov ? (gov.utilisation > 1 ? "fail" : gov.status) : "pass";
  return el("section", { class: "panel governing" },
    el("span", { class: "label" }, "Governing check"),
    gov ? el("div", { class: "big" },
      el("span", { class: `u ${status}` }, fmt(gov.utilisation, 2)),
      el("span", { class: "what" }, gov.title)) : el("div", {}, "No rated checks"),
    gov ? meter(gov.utilisation) : null,
    el("div", { class: "counts" },
      statusDot("pass", `${c.pass} pass`), statusDot("fail", `${c.fail} fail`),
      statusDot("warn", plural(c.warn, "warning")), statusDot("info", `${c.info} for information`)),
    el("div", { class: "attention" },
      el("h3", {}, "Needs attention"),
      attention.length
        ? el("ul", {}, attention.map((x) => el("li", {}, checkLink(x,
          el("span", {}, x.title), el("span", { class: `res ${x.status}`, html: x.markup.result })))))
        : el("p", { class: "none" }, "Nothing to fix: every check passes.")));
}

function utilisation(result) {
  const rows = result.checks
    .filter((c) => RATED.has(c.status) && c.utilisation !== null && Number.isFinite(c.utilisation))
    .sort((a, b) => b.utilisation - a.utilisation);
  return el("section", { class: "panel utilisation" },
    el("h3", {}, "Utilisation, highest first"),
    rows.map((c) => el("div", { class: "util-row" }, checkLink(c, c.title), meter(c.utilisation))));
}

function strip(result) {
  return el("nav", { class: "strip", "aria-label": "Check groups" }, result.groups.map((g, i) => {
    const items = result.checks.filter((c) => c.group === g);
    return el("a", {
      href: `#group-${i}`,
      onclick: (e) => {
        e.preventDefault();
        const details = document.getElementById(`group-${i}`);
        details.open = true;
        details.scrollIntoView({ behavior: "smooth", block: "start" });
      },
    }, g, el("span", { class: "dots" }, items.map((c) => el("i", { class: c.status, title: `${c.title}` }))));
  }));
}

// ------------------------------------------------------------------ full calculations

function highlight(target, on) {
  if (!target) return;
  document.querySelectorAll(`#fig-section [data-part="${target}"]`).forEach((n) => n.classList.toggle("is-hl", on));
}

function calcGroups(result) {
  return result.groups.map((group, gi) => {
    const items = result.checks.filter((c) => c.group === group);
    if (!items.length) return null;
    const status = worst(items.map((c) => c.status));
    const n = (s) => items.filter((c) => c.status === s).length;
    const count = [n("pass") && `${n("pass")} pass`, n("fail") && `${n("fail")} fail`,
      n("warn") && plural(n("warn"), "warning"), n("info") && `${n("info")} for information`,
      n("na") && `${n("na")} not applicable`].filter(Boolean).join(" · ");
    const rows = items.map((c) => {
      const row = el("tr", { id: `check-${c.id}` },
        el("td", {}, el("div", { class: "ct" }, c.title),
          ...c.markup.working.map((w) => el("div", { class: "wl", html: w })),
          c.note ? el("div", { class: "note", html: c.markup.note }) : null),
        el("td", { class: "out" }, el("div", { class: "res", html: c.markup.result }), statusDot(c.status),
          c.utilisation !== null ? meter(c.utilisation) : null));
      row.addEventListener("mouseenter", () => highlight(c.target, true));
      row.addEventListener("mouseleave", () => highlight(c.target, false));
      return row;
    });
    return block(group, { open: status === "fail" || status === "warn", id: `group-${gi}`, count, right: statusDot(status) },
      el("div", { class: "calc-wrap", style: "margin:-16px -18px" },
        el("table", { class: "calc" },
          el("thead", {}, el("tr", {}, el("th", {}, "Calculation"), el("th", {}, "Result"))),
          el("tbody", {}, rows))));
  }).filter(Boolean);
}

function render(state, parts) {
  const { result } = state;
  document.title = `${TITLE} report · EC2 Checker`;
  const crumb = document.getElementById("crumb-element");
  crumb.textContent = TITLE;
  crumb.href = `/${element}`;
  const expand = el("button", { type: "button", class: "btn quiet small" }, "Expand all");
  const collapse = el("button", { type: "button", class: "btn quiet small" }, "Collapse all");
  const groups = calcGroups(result);
  expand.addEventListener("click", () => groups.forEach((g) => { g.open = true; }));
  collapse.addEventListener("click", () => groups.forEach((g) => { g.open = false; }));
  root.replaceChildren(
    header(state),
    el("div", { class: "summary" }, governing(result), utilisation(result)),
    strip(result),
    el("h2", {}, "Drawings"),
    parts.figures(state),
    parts.designPath ? parts.designPath(result) : null,
    el("div", { class: "section-tools" }, el("h2", {}, "Full calculations"), expand, collapse),
    el("p", { class: "lede", style: "font-size:14px;margin:6px 0 4px" },
      "Every test with its working and result. Groups that need attention are open."),
    ...groups,
    el("h2", {}, "Inputs and assumptions"),
    block("Inputs", {}, el("table", { class: "kv doc" }, el("tbody", {},
      result.inputs.map((i) => el("tr", {}, el("td", {}, i.label), el("td", { class: "num" }, i.value)))))),
    block("Assumptions", {}, el("ul", { class: "assumptions doc" }, result.assumptions.map((a) => el("li", {}, a)))),
    el("p", { class: "notice" }, "For learning and preliminary checking. A qualified structural engineer must verify the inputs and results."));
  setupExport(state);
}

async function main() {
  const state = store.getSession(keysFor(element).result);
  if (!state?.result) {
    root.replaceChildren(el("p", { class: "empty" }, "No results yet. ",
      el("a", { href: `/${element}` }, `Enter a ${TITLE.toLowerCase()} to check`)));
    return;
  }
  const parts = await import(`./report-${element}.js`);
  render(state, parts);
  if (location.hash.startsWith("#check-")) reveal(location.hash.slice(1));
}

main();
