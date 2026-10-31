// Pieces shared by the element input pages: nested values, collapsible sections,
// server errors and the "Examples and files" menu.
import { el, store } from "./common.js";
import { anchorPopover } from "./theme.js";

export function setPath(obj, path, value) {
  const keys = path.split(".");
  let node = obj;
  keys.slice(0, -1).forEach((k) => { node = node[k] ??= {}; });
  node[keys[keys.length - 1]] = value;
}

export function getPath(obj, path) {
  return path.split(".").reduce((node, k) => (node == null ? undefined : node[k]), obj);
}

export const option = (value, label) => el("option", { value }, label);

/** Collapsible sections: remember which are open and wire the expand / collapse buttons. */
export function setupSections(form, storageKey) {
  const sections = () => [...form.querySelectorAll("details.section")];
  let open = null;
  try { open = JSON.parse(localStorage.getItem(storageKey)); } catch { /* keep the page default */ }
  if (Array.isArray(open)) sections().forEach((s) => { s.open = open.includes(s.dataset.section); });
  const remember = () => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(sections().filter((s) => s.open).map((s) => s.dataset.section)));
    } catch { /* not essential */ }
  };
  sections().forEach((s) => s.addEventListener("toggle", remember));
  document.getElementById("expand-all").addEventListener("click", () => { sections().forEach((s) => { s.open = true; }); });
  document.getElementById("collapse-all").addEventListener("click", () => { sections().forEach((s) => { s.open = false; }); });
}

/** Field errors returned by the server, keyed by input name. */
export function formErrors(form, message) {
  function clear() {
    form.querySelectorAll(".control.invalid").forEach((c) => c.classList.remove("invalid"));
    form.querySelectorAll(".field .error, td .error").forEach((e) => e.remove());
    message.textContent = "";
  }
  function show(errors) {
    clear();
    let first = null;
    for (const [path, text] of Object.entries(errors || {})) {
      const input = form.querySelector(`[name="${CSS.escape(path)}"], [data-path="${CSS.escape(path)}"]`);
      if (!input) continue;
      const section = input.closest("details.section");
      if (section) section.open = true;
      const more = input.closest("details.more");
      if (more) more.open = true;
      input.closest(".control")?.classList.add("invalid");
      (input.closest(".field") || input.closest("td"))?.append(el("span", { class: "error" }, text));
      first ??= input;
    }
    const n = Object.keys(errors || {}).length;
    message.textContent = n ? `${n} input${n > 1 ? "s" : ""} to fix` : "";
    first?.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  return { clear, show };
}

/**
 * The "Examples and files" menu: load an example, open an exported inputs file, or reset.
 * `looksValid(data)` tells an inputs file for this element from any other JSON.
 */
export function setupFilesMenu({ examples, fill, errors, inputKey, looksValid, message, resetTo = "pass" }) {
  const menu = document.getElementById("files-menu");
  anchorPopover(menu, document.getElementById("files-button"), "start");
  for (const item of menu.querySelectorAll("[data-example]")) {
    item.addEventListener("click", () => { errors.clear(); fill(structuredClone(examples[item.dataset.example])); menu.hidePopover(); });
  }
  document.getElementById("reset").addEventListener("click", () => {
    errors.clear(); fill(structuredClone(examples[resetTo])); store.set(inputKey, null); menu.hidePopover();
  });
  const fileInput = document.getElementById("import-file");
  document.getElementById("import").addEventListener("click", () => { menu.hidePopover(); fileInput.click(); });
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      if (!data || typeof data !== "object" || !looksValid(data)) throw new Error("not an inputs file");
      errors.clear();
      fill(data);
    } catch {
      message.textContent = "That file is not an exported inputs file.";
    }
    fileInput.value = "";
  });
}

/**
 * Keeps an embedded report as tall as its content, so the page scrolls and the frame never does.
 * Only the content's own size is watched: the frame's resize must not set off another one, or the
 * page keeps changing height and the browser keeps pulling the scroll position back.
 */
export function fitFrame(frame) {
  const fit = () => {
    try {
      const body = frame.contentDocument?.body;
      if (!body) return;
      const height = Math.ceil(body.getBoundingClientRect().height) + 24;
      if (Math.abs(frame.clientHeight - height) > 1) frame.style.height = `${height}px`;
    } catch { /* not readable: the frame keeps its own height */ }
  };
  frame.addEventListener("load", () => {
    fit();
    try {
      new frame.contentWindow.ResizeObserver(fit).observe(frame.contentDocument.body);
    } catch { /* sized once on load */ }
  });
  return fit;
}
