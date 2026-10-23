// Building blocks shared by the report page and the element-specific report modules.
import { el, SEVERITY } from "./common.js";

export const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

export function targetStatus(checks) {
  const status = {};
  for (const c of checks) {
    if (c.target && (SEVERITY[c.status] ?? 0) > (SEVERITY[status[c.target]] ?? 0)) status[c.target] = c.status;
  }
  return status;
}

/** Two-way switch, e.g. between the y–y and z–z axes. */
export function switcher(onSelect, options = [["y", "y–y"], ["z", "z–z"]], label = "Axis") {
  const wrap = el("div", { class: "switch", role: "group", "aria-label": label });
  options.forEach(([value, text], i) => {
    const b = el("button", { type: "button", "aria-pressed": String(i === 0) }, text);
    b.addEventListener("click", () => {
      wrap.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      onSelect(value);
    });
    wrap.append(b);
  });
  return wrap;
}

export function figure(title, body, caption, extra) {
  return el("figure", { class: "panel figure" },
    el("div", { class: "panel-head" }, el("h3", {}, title), extra || null),
    el("div", { class: "panel-body" }, body),
    caption ? el("figcaption", {}, caption) : null);
}

export function block(title, { open = false, id = null, count = "", right = null } = {}, ...body) {
  return el("details", { class: "block", open: open || null, id },
    el("summary", {}, el("h3", {}, title), count ? el("span", { class: "count" }, count) : null,
      el("span", { class: "right" }, right, el("span", { class: "chev", "aria-hidden": "true" }))),
    el("div", { class: "block-body" }, ...body));
}

// design path flowchart
export const node = (label, value, cls = "on") =>
  el("div", { class: `flow-node ${cls}` }, el("div", { class: "fl" }, label), el("div", { class: "fv", html: value }));
export const arrow = (on = true) => el("div", { class: `flow-arrow${on ? " on" : ""}` });
export const question = (html) => el("div", { class: "flow-question", html });

export function branch(takeRight, left, right) {
  return el("div", { class: "flow-branch" },
    el("div", { class: `col ${takeRight ? "off" : "on"}` }, el("span", { class: "tag-line" }, left.tag), left.node),
    el("div", { class: `col ${takeRight ? "on" : "off"}` }, el("span", { class: "tag-line" }, right.tag), right.node));
}
