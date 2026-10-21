// Shared helpers for every page.

export const STATUS_LABEL = { pass: "PASS", fail: "FAIL", warn: "WARN", info: "INFO", na: "N/A" };
export const STATUS_ICON = { pass: "✓", fail: "✕", warn: "!", info: "i", na: "–" };
export const SEVERITY = { fail: 4, warn: 3, pass: 2, info: 1, na: 0 };
export const PDF_PAGE_OFFSET = 4;

export const KEYS = {
  input: "ec2.column.input",
  result: "ec2.column.result",
  errors: "ec2.column.errors",
};

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

export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
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

export function chip(status) {
  return el("span", { class: `chip ${status}` }, STATUS_LABEL[status]);
}

export function utilBar(u) {
  if (u === null || u === undefined || !Number.isFinite(u)) return el("span", { class: "muted" });
  const cls = u > 1 ? "fail" : u > 0.95 ? "warn" : "";
  const span = el("span", { class: cls });
  span.style.width = `${Math.min(u, 1) * 100}%`;
  return el("div", { class: "util" }, el("div", { class: "bar" }, span), el("span", { class: "val" }, fmt(u, 2)));
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
