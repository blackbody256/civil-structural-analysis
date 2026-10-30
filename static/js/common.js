// Shared helpers for every page.
import "./theme.js";

export const STATUS_TEXT = { pass: "Pass", fail: "Fail", warn: "Warning", info: "Info", na: "Not applicable" };
const svgIcon = (body) => `<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
export const STATUS_SVG = {
  pass: svgIcon('<path d="M2.6 6.3 5 8.6l4.5-5"/>'),
  fail: svgIcon('<path d="M3.4 3.4l5.2 5.2M8.6 3.4 3.4 8.6"/>'),
  warn: svgIcon('<path d="M6 2.4v4.3"/><circle cx="6" cy="9.2" r=".6" fill="currentColor"/>'),
  info: svgIcon('<circle cx="6" cy="3" r=".6" fill="currentColor"/><path d="M6 5.4v4.2"/>'),
  na: svgIcon('<path d="M3.4 6h5.2"/>'),
};
export const SEVERITY = { fail: 4, warn: 3, pass: 2, info: 1, na: 0 };
export const PDF_PAGE_OFFSET = 4;

export const ELEMENT_TITLES = { column: "Column", beam: "Beam", slab: "Slab" };

/** The element a page belongs to, from its path: /beam, /beam/run, /beam/report. */
export function currentElement() {
  const first = window.location.pathname.split("/")[1];
  return first in ELEMENT_TITLES ? first : "column";
}

/** Storage keys for one element's inputs, last result and validation errors. */
export function keysFor(element) {
  return { input: `ec2.${element}.input`, result: `ec2.${element}.result`, errors: `ec2.${element}.errors` };
}

export const KEYS = keysFor("column");

function safeStorage(kind) {
  try {
    const s = window[kind];
    const probe = "__ec2__";
    s.setItem(probe, "1");
    s.removeItem(probe);
    return s;
  } catch {
    return null;
  }
}

const session = safeStorage("sessionStorage");
const local = safeStorage("localStorage");

function read(storage, key, fallback) {
  if (!storage) return fallback;
  try {
    const raw = storage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function write(storage, key, value) {
  if (!storage) return;
  try {
    if (value === undefined || value === null) storage.removeItem(key);
    else storage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage full or blocked: the app still works for this page view */
  }
}

export const store = {
  get: (key, fallback = null) => read(session, key, fallback) ?? read(local, key, fallback),
  set: (key, value) => { write(session, key, value); write(local, key, value); },
  getSession: (key, fallback = null) => read(session, key, fallback),
  setSession: (key, value) => write(session, key, value),
};

export async function getJSON(url) {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return res.json();
}

export async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON error page */ }
  return { ok: res.ok, status: res.status, data };
}

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (k === "dataset") Object.assign(node.dataset, v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function fmt(x, nd = 1) {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return Number(x).toFixed(nd);
}

export function guideHref(page) {
  return `/reference/guide.pdf#page=${page + PDF_PAGE_OFFSET}`;
}

export function worst(statuses) {
  return statuses.reduce((w, s) => (SEVERITY[s] > SEVERITY[w] ? s : w), "na");
}

/** Status with a coloured dot, e.g. "● Fail". */
export function statusDot(status, text = STATUS_TEXT[status]) {
  return el("span", { class: `status ${status}` }, text);
}

/** Utilisation meter: a track filled up to min(u, 1) and the value. */
export function meter(u) {
  if (u === null || u === undefined || !Number.isFinite(u)) return el("span");
  const fill = el("span", { class: u > 1 ? "fail" : u > 0.95 ? "warn" : "" });
  fill.style.width = `${Math.min(u, 1) * 100}%`;
  return el("div", { class: "meter" }, el("div", { class: "track" }, fill), el("span", { class: "val" }, fmt(u, 2)));
}

export function verdictText(summary) {
  const c = summary.counts;
  if (c.fail) return `${c.fail} check${c.fail > 1 ? "s" : ""} failed`;
  if (c.warn) return `Passed with ${c.warn} warning${c.warn > 1 ? "s" : ""}`;
  return "All checks passed";
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = el("a", { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
