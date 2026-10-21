import { downloadBlob, el, fmt, guideHref, KEYS, meter, SEVERITY, statusDot, store, worst } from "./common.js";
import { drawElevation, drawInteraction, drawSection, endKinds } from "./drawings.js";
import { anchorPopover } from "./theme.js";

const root = document.getElementById("report");
const RATED = new Set(["pass", "fail", "warn"]);

function targetStatus(checks) {
  const status = {};
  for (const c of checks) {
    if (c.target && (SEVERITY[c.status] ?? 0) > (SEVERITY[status[c.target]] ?? 0)) status[c.target] = c.status;
  }
  return status;
}

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** Open the collapsed group holding a check, scroll to it and mark it briefly. */
function reveal(id) {
  const row = document.getElementById(id);
  if (!row) return;
  const block = row.closest("details");
  if (block) block.open = true;
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
    el("p", { class: "context" }, ["Column", p.ref, p.name].filter(Boolean).join(" · ")),
    el("div", {}, title,
      el("p", { class: "meta" }, [p.engineer, p.date || new Date().toISOString().slice(0, 10),
        "BS EN 1992-1-1 with the UK National Annex"].filter(Boolean).join(" · "))),
    el("div", { class: "actions" }, exportBtn, el("a", { class: "btn", href: "/column" }, "Edit inputs")));
}

function setupExport(state) {
  const menu = document.getElementById("export-menu");
  anchorPopover(menu, () => document.querySelector('[popovertarget="export-menu"]'), "end");
  const ref = (state.result.project.ref || "column").replace(/[^A-Za-z0-9_-]+/g, "-");
  const pdfItem = document.getElementById("export-pdf");
  pdfItem.addEventListener("click", async () => {
    pdfItem.disabled = true;
    try {
      const res = await fetch("/api/column/report.pdf", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state.input),
      });
      if (!res.ok) throw new Error(String(res.status));
      const name = /filename="?([^";]+)"?/.exec(res.headers.get("Content-Disposition") || "")?.[1] || "EC2-column-check.pdf";
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
    downloadBlob(new Blob([JSON.stringify(state.input, null, 2)], { type: "application/json" }), `EC2-column-${ref}.json`);
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
        const block = document.getElementById(`group-${i}`);
        block.open = true;
        block.scrollIntoView({ behavior: "smooth", block: "start" });
      },
    }, g, el("span", { class: "dots" }, items.map((c) => el("i", { class: c.status, title: `${c.title}` }))));
  }));
}

// ------------------------------------------------------------------ drawings

function switcher(onSelect) {
  const wrap = el("div", { class: "switch", role: "group", "aria-label": "Axis" });
  for (const axis of ["y", "z"]) {
    const b = el("button", { type: "button", "aria-pressed": String(axis === "y") }, `${axis}–${axis}`);
    b.addEventListener("click", () => {
      wrap.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      onSelect(axis);
    });
    wrap.append(b);
  }
  return wrap;
}

function figure(title, body, caption, extra) {
  return el("figure", { class: "panel figure" },
    el("div", { class: "panel-head" }, el("h3", {}, title), extra || null),
    el("div", { class: "panel-body" }, body),
    caption ? el("figcaption", {}, caption) : null);
}

function figures(state) {
  const { result, input } = state;
  const by = Object.fromEntries(result.checks.map((c) => [c.id, c]));
  const sectionBox = el("div", { id: "fig-section" });
  const elevationBox = el("div");
  const nmY = el("div"), nmZ = el("div");
  const drawElev = (axis) => {
    const ax = result.derived.axes[axis];
    drawElevation(elevationBox, {
      l: result.derived.l, depth: ax.depth, NEd: result.derived.NEd, l0: ax.l0,
      ...endKinds(input.restraint[axis]), moments: { ...ax, axis },
    });
  };
  queueMicrotask(() => {
    drawSection(sectionBox, result.plots.section, {
      status: targetStatus(result.checks), linkLabel: `H${input.reinforcement.link_dia} @ ${input.reinforcement.link_spacing}`,
    });
    drawElev("y");
    drawInteraction(nmY, result.plots.interaction.y, { axis: "y", status: by.bending_y.status });
    drawInteraction(nmZ, result.plots.interaction.z, { axis: "z", status: by.bending_z.status });
  });
  return el("div", { class: "figures" },
    figure("Cross-section", sectionBox, "To scale. Parts outlined in red failed a check; point at a row below to find its part."),
    figure("Elevation and design moments", elevationBox, "Ch 5, Fig 4: first-order moments dashed, with second-order effects solid.", switcher(drawElev)),
    figure("N–M interaction about y–y", nmY, "The design point must lie inside the capacity curve (Figs 7–9)."),
    figure("N–M interaction about z–z", nmZ, null));
}

// ------------------------------------------------------------------ design path (Fig 2 / Fig 3)

const node = (label, value, cls = "on") =>
  el("div", { class: `flow-node ${cls}` }, el("div", { class: "fl" }, label), el("div", { class: "fv", html: value }));
const arrow = (on = true) => el("div", { class: `flow-arrow${on ? " on" : ""}` });

function flow(result, axis) {
  const ax = result.derived.axes[axis];
  const by = Object.fromEntries(result.checks.map((c) => [c.id, c]));
  const bend = by[`bending_${axis}`];
  const detailing = worst(result.checks.filter((c) => c.group === "Detailing").map((c) => c.status));
  const slender = ax.slender;
  return el("div", { class: "flow" },
    node("Actions on the column", `N<sub>Ed</sub> = ${fmt(result.derived.NEd, 0)} kN · M<sub>top</sub> = ${fmt(ax.M_top)} · M<sub>bottom</sub> = ${fmt(ax.M_bottom)} kNm`),
    arrow(),
    node("Effective length (Fig 5, Table 4)", `l<sub>0</sub> = ${fmt(ax.F, 3)} × ${fmt(result.derived.l / 1000, 2)} m = ${fmt(ax.l0 / 1000, 2)} m`),
    arrow(),
    node("First-order moments", `e<sub>i</sub> = ${fmt(ax.e_i)} mm · M<sub>01</sub> = ${fmt(ax.M01)} · M<sub>02</sub> = ${fmt(ax.M02)} kNm`),
    arrow(),
    node("Slenderness", `λ = ${fmt(ax.lam)} · λ<sub>lim</sub> = ${fmt(ax.lam_lim)}`),
    arrow(),
    el("div", { class: "flow-question", html: `Is λ ≥ λ<sub>lim</sub>? ${slender ? "Yes" : "No"}` }),
    arrow(),
    el("div", { class: "flow-branch" },
      el("div", { class: `col ${slender ? "off" : "on"}` }, el("span", { class: "tag-line" }, "No: not slender"),
        node("Design moment", `M<sub>Ed</sub> = M<sub>02</sub> = ${fmt(ax.M02)} kNm`, slender ? "off" : "on")),
      el("div", { class: `col ${slender ? "on" : "off"}` }, el("span", { class: "tag-line" }, "Yes: nominal curvature, Fig 3"),
        node("Second-order moment", slender
          ? `K<sub>r</sub> = ${fmt(ax.Kr, 3)}, K<sub>φ</sub> = ${fmt(ax.Kphi, 3)}<br>e<sub>2</sub> = ${fmt(ax.e2)} mm, M<sub>2</sub> = ${fmt(ax.M2)} kNm<br>M<sub>Ed</sub> = ${fmt(ax.MEd)} kNm`
          : "not needed", slender ? "on" : "off"))),
    arrow(),
    node("Resistance (Figs 7–9)", `${bend.markup.result}<br>A<sub>s,req</sub> = ${ax.As_req === null ? "not achievable" : `${fmt(ax.As_req, 0)} mm²`} · A<sub>s,prov</sub> = ${fmt(result.derived.As, 0)} mm²`, bend.status),
    arrow(),
    node("Spacing and quantity of reinforcement", detailing === "fail" ? "Some detailing rules fail" : "All detailing rules pass", detailing === "fail" ? "fail" : "pass"));
}

function block(title, { open = false, id = null, count = "", right = null } = {}, ...body) {
  return el("details", { class: "block", open: open || null, id },
    el("summary", {}, el("h3", {}, title), count ? el("span", { class: "count" }, count) : null,
      el("span", { class: "right" }, right, el("span", { class: "chev", "aria-hidden": "true" }))),
    el("div", { class: "block-body" }, ...body));
}

function designPath(result) {
  const box = el("div");
  const draw = (axis) => box.replaceChildren(flow(result, axis));
  draw("y");
  return block("Design path through Figures 2 and 3", { open: true },
    el("div", { style: "display:flex;margin-bottom:10px" }, switcher(draw)), box);
}

// ------------------------------------------------------------------ full calculations

function highlight(target, on) {
  if (!target) return;
  document.querySelectorAll(`#fig-section [data-part="${target}"]`).forEach((n) => n.classList.toggle("is-hl", on));
}

function refCell(refs) {
  return el("td", { class: "ref" }, refs.map((r) => r.page
    ? el("a", { href: guideHref(r.page), target: "_blank", rel: "noopener" }, r.label, " ", el("span", { class: "pg" }, `p.${r.page}`))
    : el("div", { class: "pg" }, r.label)));
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
        refCell(c.refs),
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
          el("thead", {}, el("tr", {}, el("th", {}, "Reference"), el("th", {}, "Calculation"), el("th", {}, "Result"))),
          el("tbody", {}, rows))));
  }).filter(Boolean);
}

function render(state) {
  const { result } = state;
  document.title = `${["Column", result.project.ref].filter(Boolean).join(" ")} · EC2 Checker`;
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
    figures(state),
    designPath(result),
    el("div", { class: "section-tools" }, el("h2", {}, "Full calculations"), expand, collapse),
    el("p", { class: "lede", style: "font-size:14px;margin:6px 0 4px" },
      "Every test with its working and result. Groups that need attention are open; references open the guide at that page."),
    ...groups,
    el("h2", {}, "Inputs and assumptions"),
    block("Inputs", {}, el("table", { class: "kv" }, el("tbody", {},
      result.inputs.map((i) => el("tr", {}, el("td", {}, i.label), el("td", { class: "num" }, i.value)))))),
    block("Assumptions", {}, el("ul", { class: "assumptions" }, result.assumptions.map((a) => el("li", {}, a)))),
    el("p", { class: "notice" }, "For learning and preliminary checking. A qualified structural engineer must verify the inputs and results."));
  setupExport(state);
}

const state = store.getSession(KEYS.result);
if (!state?.result) {
  root.replaceChildren(el("p", { class: "empty" }, "No results yet. ", el("a", { href: "/column" }, "Enter a column to check")));
} else {
  render(state);
  if (location.hash.startsWith("#check-")) reveal(location.hash.slice(1));
}
