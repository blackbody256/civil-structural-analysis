// The model side of an element page: the 3D viewport on top, the 2D drawings under it as tabs. The model
// rebuilds as the inputs change, plays its build-up animation when the kind of model changes (the frame, then
// the column), and lights up the parts the current wizard step is about.
import { createViewer } from "./viewer3d.js";

/**
 * host: the viewport element. build(step) returns { kind, scene, caption: [title, sub] } for the current inputs;
 * kind tells one model from another (a change replays the build-up).
 */
export function modelView(host, form, build) {
  if (!host) return { update() {}, viewer: null };
  const viewer = createViewer(host, { spin: "sway" });
  const caption = document.createElement("p");
  caption.className = "vp-caption";
  caption.innerHTML = "<b></b><span></span>";
  host.append(caption);
  let step = null, kind = null, timer = null;

  function update() {
    let out = null;
    try { out = build(step); } catch (e) { console.error(e); return; }
    if (!out?.scene) return;
    const changed = out.kind !== kind;
    kind = out.kind;
    viewer.setScene(out.scene, { replay: changed });
    viewer.setFocus(step?.focus || []);
    caption.querySelector("b").textContent = out.caption?.[0] || "";
    caption.querySelector("span").textContent = out.caption?.[1] || "";
  }
  const soon = () => { clearTimeout(timer); timer = setTimeout(update, 140); };

  form.addEventListener("wizard:step", (e) => {
    step = e.detail;
    viewer.setFocus(step.focus);
    soon();
  });
  form.addEventListener("input", soon);
  form.addEventListener("change", soon);
  return { update: soon, now: update, viewer };
}

/** The 2D drawings under the model: one at a time, chosen by a row of tabs (a panel the page hides drops out). */
export function drawingTabs(aside) {
  const panels = [...aside.querySelectorAll(":scope > section.panel:not(.vp-panel)")];
  if (panels.length < 2) return;
  const bar = document.createElement("div");
  bar.className = "draw-tabs";
  bar.setAttribute("role", "tablist");
  bar.setAttribute("aria-label", "Drawings");
  // the heading's text without the parts the page hides for the current mode ("1 m strip" or "one rib")
  const title = (p) => {
    const h = p.querySelector(".panel-head h3");
    if (!h) return "Drawing";
    const parts = [];
    const walk = (n) => n.childNodes.forEach((c) => {
      if (c.nodeType === Node.TEXT_NODE) parts.push(c.textContent);
      else if (!c.hidden) walk(c);
    });
    walk(h);
    return parts.join("").replace(/\s+/g, " ").trim() || "Drawing";
  };
  const buttons = panels.map((p, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("role", "tab");
    b.textContent = title(p);
    b.addEventListener("click", () => select(i));
    bar.append(b);
    p.classList.add("draw-panel");
    return b;
  });
  panels[0].before(bar);
  let at = 0;
  function select(i) {
    at = i;
    panels.forEach((p, k) => {
      p.classList.toggle("is-shown", k === i);
      buttons[k].setAttribute("aria-selected", String(k === i));
      buttons[k].tabIndex = k === i ? 0 : -1;
    });
  }
  function sync() {
    panels.forEach((p, k) => { buttons[k].hidden = p.hidden; const t = title(p); if (buttons[k].textContent !== t) buttons[k].textContent = t; });
    if (panels[at].hidden) {
      const i = panels.findIndex((p) => !p.hidden);
      if (i >= 0) select(i);
    }
  }
  bar.addEventListener("keydown", (e) => {
    const shown = panels.map((p, k) => k).filter((k) => !panels[k].hidden);
    const j = shown.indexOf(at);
    const to = { ArrowRight: shown[(j + 1) % shown.length], ArrowLeft: shown[(j - 1 + shown.length) % shown.length] }[e.key];
    if (to !== undefined) { e.preventDefault(); select(to); buttons[to].focus(); }
  });
  new MutationObserver(sync).observe(aside, { attributes: true, attributeFilter: ["hidden"], subtree: true });
  select(panels.findIndex((p) => !p.hidden) >= 0 ? panels.findIndex((p) => !p.hidden) : 0);
  sync();
}
