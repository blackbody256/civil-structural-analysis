// Inspector tabs: a run of input sections (<details class="section">) next to each other becomes a tab strip that
// shows one section at a time, like the data-table tabs of Elisha's desktop app (Nodes, Members, Supports, Loads).
// A section standing on its own is shown as an always-open titled panel. The <details> stay in the page, so
// serialising, filling, error handling (which opens the section with the error) and saved open sections all work
// as before: opening a section, by code or by a tab, selects its tab.

const isSection = (n) => n.matches?.("details.section");
// a wrapper that only shows or hides one or more sections (".one-way-only", ".two-way-only") counts as part of a run
const isWrapper = (n) => n.tagName === "DIV" && n.children.length > 0 && [...n.children].every(isSection);
const sectionsOf = (n) => (isSection(n) ? [n] : [...n.children]);
// a title's text without the parts its page hides for the current mode ("(1 m strip)" or "(one rib)")
const titleOf = (s) => {
  const t = s.querySelector(":scope > summary .s-title");
  if (!t) return s.dataset.section;
  const parts = [];
  const walk = (n) => n.childNodes.forEach((c) => {
    if (c.nodeType === Node.TEXT_NODE) parts.push(c.textContent);
    else if (!c.hidden) walk(c);
  });
  walk(t);
  return parts.join("").replace(/\s+/g, " ").trim();
};
const hiddenWithin = (node, root) => {
  for (let n = node; n && n !== root; n = n.parentElement) if (n.hidden) return true;
  return false;
};

function runs(form) {
  const parents = new Set();
  for (const d of form.querySelectorAll("details.section")) {
    const p = d.parentElement;
    parents.add(isWrapper(p) ? p.parentElement : p);
  }
  const out = [];
  for (const parent of parents) {
    let run = [];
    for (const child of [...parent.children, null]) {
      if (child && (isSection(child) || isWrapper(child))) { run.push(child); continue; }
      if (run.length) out.push({ parent, items: run });
      run = [];
    }
  }
  return out;
}

function single(section) {
  section.classList.add("is-fixed");
  section.open = true;
  section.querySelector(":scope > summary").addEventListener("click", (e) => e.preventDefault());
  section.addEventListener("toggle", () => { if (!section.open) section.open = true; });
}

function group(parent, items) {
  const sections = items.flatMap(sectionsOf);
  const strip = document.createElement("div");
  strip.className = "inspector-tabs";
  strip.setAttribute("role", "tablist");
  strip.setAttribute("aria-label", "Input sections");
  const buttons = sections.map((s) => {
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("role", "tab");
    b.textContent = titleOf(s);
    b.addEventListener("click", () => select(s, true));
    strip.append(b);
    s.classList.add("in-tabs");
    return b;
  });
  parent.insertBefore(strip, items[0]);

  let current = null;
  function visible(s) { return !hiddenWithin(s, parent); }
  function select(s, focus = false) {
    current = s;
    sections.forEach((x, i) => {
      if (x !== s && x.open) x.open = false;
      buttons[i].setAttribute("aria-selected", String(x === s));
      buttons[i].tabIndex = x === s ? 0 : -1;
    });
    if (!s.open) s.open = true;
    if (focus) buttons[sections.indexOf(s)].focus();
  }
  function refresh() {
    sections.forEach((s, i) => { buttons[i].hidden = !visible(s); buttons[i].textContent = titleOf(s); });
    if (!current || !visible(current)) {
      const next = sections.find(visible);
      if (next) select(next);
    }
  }
  // opening a section in any way (an error in it, a saved state) selects its tab
  sections.forEach((s) => s.addEventListener("toggle", () => { if (s.open && s !== current) select(s); }));
  strip.addEventListener("keydown", (e) => {
    const shown = sections.filter(visible);
    const i = shown.indexOf(current);
    const to = { ArrowRight: shown[(i + 1) % shown.length], ArrowLeft: shown[(i - 1 + shown.length) % shown.length],
      Home: shown[0], End: shown[shown.length - 1] }[e.key];
    if (to) { e.preventDefault(); select(to, true); }
  });
  const start = sections.find((s) => s.open && visible(s)) || sections.find(visible) || sections[0];
  select(start);
  refresh();
  return refresh;
}

export function inspectorTabs(form) {
  const refreshers = [];
  for (const { parent, items } of runs(form)) {
    const sections = items.flatMap(sectionsOf);
    if (sections.length === 1) single(sections[0]);
    else refreshers.push(group(parent, items));
  }
  // modes show and hide sections (frame or direct actions, one-way or two-way, flanged beams)
  let queued = false;
  const update = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; refreshers.forEach((r) => r()); });
  };
  new MutationObserver(update).observe(form, { attributes: true, attributeFilter: ["hidden"], subtree: true });
  form.addEventListener("change", update);
}
