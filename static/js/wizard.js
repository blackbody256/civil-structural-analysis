// Guided input (Structural Analysis & Design): the element's inputs one step at a time, with a rail of steps
// down the side, Back and Next, a review of everything entered before the checks run, and the results and
// report as the last steps. The inputs stay in the one form, so saving, filling, examples, the server's field
// errors and the page's own Analysis / Design / Report logic all work as before: a step is a
// <section class="wz-step"> inside a tab panel, and moving to a step in another panel presses that panel's tab.

// hidden by a mode (frame or direct, one-way or two-way); a tab panel the page hid because another one is showing
// does not count, its steps are still steps
const hiddenWithin = (node, root) => {
  for (let n = node; n && n !== root; n = n.parentElement) if (n.hidden && n.getAttribute("role") !== "tabpanel") return true;
  return false;
};
const waitFor = (test, ms = 20000) => new Promise((resolve) => {
  const t0 = performance.now();
  const tick = () => {
    const v = test();
    if (v || performance.now() - t0 > ms) resolve(v);
    else setTimeout(tick, 80);
  };
  tick();
});

function text(node) { return (node?.textContent || "").replace(/\s+/g, " ").trim(); }

/**
 * What is wrong with a value, or "" when it can be sent. The step attribute only sets how far the arrows move:
 * any value between min and max is accepted (NEd 693 kN with step 10 is fine), so a step mismatch is ignored.
 * The server checks every value again and its messages show on the field.
 */
function problem(c) {
  const v = c.validity;
  if (!v || v.valid || (v.stepMismatch && !v.valueMissing && !v.rangeUnderflow && !v.rangeOverflow && !v.badInput)) return "";
  const unit = text(c.closest(".control")?.querySelector(".unit"));
  const u = unit ? ` ${unit}` : "";
  const range = c.min !== "" && c.max !== "" ? `between ${c.min} and ${c.max}${u}`
    : c.min !== "" ? `${c.min}${u} or more` : `${c.max}${u} or less`;
  if (v.badInput) return "Enter a number, using digits and a decimal point (for example 4.5).";
  if (v.valueMissing) return "This value is needed: enter a number here.";
  if (v.rangeUnderflow) return `${c.value}${u} is too small: enter a value ${range}.`;
  if (v.rangeOverflow) return `${c.value}${u} is too large: enter a value ${range}.`;
  if (v.stepMismatch) return "";
  return c.validationMessage || "Check this value.";
}

/** The value of a control as shown to the user: the option text, the number with its unit, or a tick. */
function shown(ctl) {
  if (!ctl) return "";
  if (ctl.matches(".computed")) return text(ctl);
  if (ctl.tagName === "SELECT") return text(ctl.selectedOptions[0]) || "—";
  if (ctl.type === "checkbox") return ctl.checked ? "Yes" : "No";
  const unit = text(ctl.closest(".control")?.querySelector(".unit"));
  if (ctl.value === "") return ctl.disabled ? "—" : "not entered";
  return unit ? `${ctl.value} ${unit}` : ctl.value;
}

function rowsOf(step) {
  const rows = [];
  const seen = new Set();
  for (const f of step.querySelectorAll(".field, label.check, td > .control > input[aria-label], td > .control > select[aria-label]")) {
    if (hiddenWithin(f, step) || f.closest(".wz-review, .grid-table, #analysis-results-area, #design-results-area, .wz-skip")) continue;
    if (f.matches("label.check")) {
      const i = f.querySelector("input[type=checkbox]");
      if (i && !seen.has(i)) { seen.add(i); rows.push([text(f), i.checked ? "Yes" : "No"]); }
      continue;
    }
    if (f.matches("input, select")) {
      if (!seen.has(f)) { seen.add(f); rows.push([f.getAttribute("aria-label"), shown(f)]); }
      continue;
    }
    const ctl = f.querySelector("input:not([type=hidden]):not([type=checkbox]), select, .computed");
    if (!ctl || seen.has(ctl) || hiddenWithin(ctl, step)) continue;
    seen.add(ctl);
    const label = text(f.querySelector(":scope > label, :scope > .label")) || ctl.getAttribute("aria-label");
    // a preset and its value in one control ("k =" and 0.145): both
    const pair = ctl.tagName === "SELECT" ? ctl.closest(".control")?.querySelector("input:not([type=hidden])") : null;
    if (pair) seen.add(pair);
    const value = pair && pair.value !== "" && !pair.disabled ? `${shown(ctl).replace(/\s*=$/, "")} = ${pair.value}` : shown(ctl);
    if (label) rows.push([label, value]);
  }
  // tables (nodes, members, loads, supports): their one-line summary
  if (step.querySelector(".grid-table")) {
    const sum = text(step.querySelector("[data-sum]"));
    if (sum) rows.unshift(["Entered", sum]);
  }
  return rows;
}

export function wizard(form) {
  const steps = [...form.querySelectorAll(".wz-step")];
  if (!steps.length) return null;
  const main = form.querySelector(".form-main");
  const phaseOf = (s) => s.closest('[role="tabpanel"]')?.id.replace("panel-", "") || "inputs";
  const tabOf = (phase) => document.getElementById(`tab-${phase}`);
  const panelActive = (phase) => {
    const panel = document.getElementById(`panel-${phase}`);
    return !panel || panel.classList.contains("is-active");
  };
  const reachable = (s) => { const t = tabOf(phaseOf(s)); return !t || t.getAttribute("aria-disabled") !== "true"; };
  const visible = (s) => !hiddenWithin(s, form) && [...s.children].some((c) => !c.hidden && !c.matches(".wz-review"));
  const shownSteps = () => steps.filter(visible);
  const store = `ec2.wizard.${location.pathname}`;

  // ---------------------------------------------------------------- chrome: rail, step head and foot
  const rail = document.createElement("nav");
  rail.className = "wz-rail";
  rail.setAttribute("aria-label", "Steps");
  const meter = document.createElement("div");
  meter.className = "wz-meter";
  meter.innerHTML = '<span class="wz-meter-text"></span><span class="wz-meter-bar"><i></i></span>';
  const list = document.createElement("ol");
  list.className = "wz-list";
  rail.append(meter, list);
  form.prepend(rail);

  const head = document.createElement("header");
  head.className = "wz-head";
  head.innerHTML = '<p class="wz-kicker"></p><h2 class="wz-title" tabindex="-1"></h2><p class="wz-prompt"></p>';
  const foot = document.createElement("footer");
  foot.className = "wz-foot";
  foot.innerHTML = '<button type="button" class="btn wz-back">← Back</button><span class="wz-note" role="status"></span>'
    + '<button type="button" class="btn primary wz-next">Next →</button>';
  const panels = [...main.querySelectorAll('[role="tabpanel"]')];
  const firstBlock = panels[0] || steps[0];
  firstBlock.before(head);
  (panels[panels.length - 1] || steps[steps.length - 1]).after(foot);
  const back = foot.querySelector(".wz-back"), next = foot.querySelector(".wz-next"), note = foot.querySelector(".wz-note");

  const items = new Map();
  let lastPhase = null;
  for (const s of steps) {
    const phase = phaseOf(s);
    if (phase !== lastPhase) {
      lastPhase = phase;
      const t = tabOf(phase);
      const h = document.createElement("li");
      h.className = "wz-phase";
      h.textContent = t ? text(t).replace(/^\d+\s*/, "") : "Inputs";
      list.append(h);
    }
    const li = document.createElement("li");
    li.className = "wz-item";
    const b = document.createElement("button");
    b.type = "button";
    b.innerHTML = '<span class="wz-num"></span><span class="wz-name"></span><span class="wz-sum"></span>';
    b.querySelector(".wz-name").textContent = s.dataset.title;
    b.addEventListener("click", () => go(s, { focus: true }));
    li.append(b);
    list.append(li);
    items.set(s, { li, b, sum: b.querySelector(".wz-sum"), num: b.querySelector(".wz-num") });
  }

  // ---------------------------------------------------------------- state
  let current = null;
  let landOnRun = false;

  function refreshRail() {
    const vis = shownSteps();
    const at = vis.indexOf(current);
    let n = 0;
    for (const s of steps) {
      const it = items.get(s);
      const on = vis.includes(s);
      if (it.li.hidden !== !on) it.li.hidden = !on;
      if (!on) continue;
      n += 1;
      if (it.num.textContent !== String(n)) it.num.textContent = String(n);
      const i = vis.indexOf(s);
      it.li.classList.toggle("is-current", s === current);
      it.li.classList.toggle("is-done", i < at);
      it.li.classList.toggle("is-locked", !reachable(s));
      it.li.classList.toggle("has-error", Boolean(s.querySelector(".control.invalid, .error")));
      it.b.setAttribute("aria-current", s === current ? "step" : "false");
      const sum = text(s.querySelector("[data-sum]"));
      if (it.sum.textContent !== sum) it.sum.textContent = sum;
    }
    // phase headings with no shown step disappear too
    for (const h of list.querySelectorAll(".wz-phase")) {
      let x = h.nextElementSibling, any = false;
      while (x && !x.matches(".wz-phase")) { if (!x.hidden) any = true; x = x.nextElementSibling; }
      if (h.hidden !== !any) h.hidden = !any;
    }
    meter.querySelector(".wz-meter-text").textContent = at >= 0 ? `Step ${at + 1} of ${vis.length}` : "";
    if (current) {
      const t = tabOf(phaseOf(current));
      const kicker = `Step ${at + 1} of ${vis.length}${t ? ` · ${text(t).replace(/^\d+\s*/, "")}` : ""}`;
      const k = head.querySelector(".wz-kicker");
      if (k.textContent !== kicker) k.textContent = kicker;
    }
    meter.querySelector("i").style.width = `${vis.length ? ((at + 1) / vis.length) * 100 : 0}%`;
    updateFoot();
  }

  function nextOf(s) { const vis = shownSteps(); return vis[vis.indexOf(s) + 1] || null; }
  function prevOf(s) { const vis = shownSteps(); return vis[vis.indexOf(s) - 1] || null; }

  function actionButton(s) {
    const sel = s.dataset.next;
    if (!sel || sel === "submit") return null;
    return document.querySelector(sel);
  }

  function updateFoot() {
    if (!current) return;
    const after = nextOf(current);
    back.disabled = !prevOf(current);
    const act = current.dataset.next;
    const waiting = act && (!after || !reachable(after) || current.hasAttribute("data-always"));
    if (act === "submit") next.textContent = current.dataset.nextLabel || "Run →";
    else if (waiting) next.textContent = `${current.dataset.nextLabel || "Run"} →`;
    else if (after) next.textContent = `Next: ${after.dataset.title} →`;
    else next.textContent = "Done";
    next.disabled = !after && !act;
    next.classList.toggle("is-action", Boolean(waiting || act === "submit"));
  }

  function go(s, { focus = false, dir = 0 } = {}) {
    if (!s || !visible(s)) return false;
    const phase = phaseOf(s);
    if (!panelActive(phase)) {
      const t = tabOf(phase);
      if (!t || t.getAttribute("aria-disabled") === "true") {
        note.textContent = s.dataset.locked || (phase === "report" ? "The report opens once the design checks have run."
          : "These steps open once the analysis has run: press Analyse on the last analysis step.");
        return false;
      }
      t.click();
      if (!panelActive(phase)) return false;
    }
    const was = current;
    current = s;
    for (const x of steps) x.classList.toggle("is-current", x === s);
    if (was !== s) {
      const vis = shownSteps();
      const d = dir || (was ? Math.sign(vis.indexOf(s) - vis.indexOf(was)) : 0);
      s.classList.remove("wz-in-fwd", "wz-in-back");
      void s.offsetWidth;
      if (d) s.classList.add(d > 0 ? "wz-in-fwd" : "wz-in-back");
    }
    head.querySelector(".wz-title").textContent = s.dataset.title;
    head.querySelector(".wz-prompt").textContent = s.dataset.prompt || "";
    note.textContent = "";
    if (s.hasAttribute("data-review")) buildReview(s);
    refreshRail();
    try { sessionStorage.setItem(store, s.dataset.step); } catch { /* not essential */ }
    form.dispatchEvent(new CustomEvent("wizard:step", { detail: { key: s.dataset.step, phase, focus: (s.dataset.focus || "").split(/\s+/).filter(Boolean) } }));
    if (focus) {
      head.querySelector(".wz-title").focus({ preventScroll: true });
      const top = head.getBoundingClientRect().top;
      if (top < 70 || top > window.innerHeight * 0.6) head.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    return true;
  }

  function invalidIn(s) {
    const bad = [];
    for (const c of s.querySelectorAll("input, select")) {
      if (c.disabled || c.type === "hidden" || hiddenWithin(c, s) || c.closest(".wz-review")) continue;
      if (problem(c)) bad.push(c);
    }
    return bad;
  }

  function markInvalid(bad) {
    for (const c of bad) {
      const ctl = c.closest(".control");
      ctl?.classList.add("invalid");
      const host = c.closest(".field") || c.closest("td");
      if (host && !host.querySelector(".error")) {
        const e = document.createElement("span");
        e.className = "error";
        e.textContent = problem(c);
        host.append(e);
      }
    }
    bad[0]?.focus();
  }

  async function onNext() {
    if (!current) return;
    const bad = invalidIn(current);
    if (bad.length) {
      markInvalid(bad);
      note.textContent = bad.length === 1 ? "1 input on this step needs changing: it is marked in red, with what to do."
        : `${bad.length} inputs on this step need changing: each is marked in red, with what to do.`;
      refreshRail();
      return;
    }
    const after = nextOf(current);
    const act = current.dataset.next;
    if (act === "submit") { form.requestSubmit(); return; }
    if (act && (!after || !reachable(after) || current.hasAttribute("data-always"))) {
      const btn = actionButton(current);
      if (!btn) return;
      const before = after && reachable(after);
      next.disabled = true;
      note.textContent = "Working…";
      btn.click();
      const ok = await waitFor(() => (after && reachable(after) && !before) || form.querySelector(".control.invalid")
        || current.querySelector(".error, .is-error"), 20000);
      next.disabled = false;
      note.textContent = ok && after && reachable(after) ? "" : note.textContent === "Working…" ? "" : note.textContent;
      if (current.hasAttribute("data-always")) current.removeAttribute("data-always");
      refreshRail();
      return;
    }
    if (after) go(after, { focus: true, dir: 1 });
  }

  // ---------------------------------------------------------------- review step
  function buildReview(s) {
    let box = s.querySelector(".wz-review");
    if (!box) {
      box = document.createElement("div");
      box.className = "wz-review";
      s.prepend(box);
    }
    const cards = [];
    for (const x of shownSteps()) {
      if (x === s) break;
      if (x.hasAttribute("data-no-review")) continue;
      const rows = rowsOf(x);
      if (!rows.length) continue;
      const card = document.createElement("section");
      card.className = "wz-card";
      const h = document.createElement("div");
      h.className = "wz-card-head";
      const t = document.createElement("h4");
      t.textContent = x.dataset.title;
      const edit = document.createElement("button");
      edit.type = "button";
      edit.className = "inline-link";
      edit.textContent = "Edit";
      edit.addEventListener("click", () => go(x, { focus: true, dir: -1 }));
      h.append(t, edit);
      const dl = document.createElement("dl");
      for (const [k, v] of rows) {
        const dt = document.createElement("dt"); dt.textContent = k;
        const dd = document.createElement("dd"); dd.textContent = v;
        if (v === "not entered") dd.className = "missing";
        dl.append(dt, dd);
      }
      card.append(h, dl);
      cards.push(card);
    }
    box.replaceChildren(...cards);
  }

  // ---------------------------------------------------------------- wiring
  back.addEventListener("click", () => { const p = prevOf(current); if (p) go(p, { focus: true, dir: -1 }); });
  next.addEventListener("click", onNext);

  // Enter moves on instead of running every check (a table cell just commits its value)
  form.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || e.shiftKey || e.isComposing) return;
    const t = e.target;
    if (!(t instanceof HTMLInputElement) || ["checkbox", "radio", "button", "submit", "file"].includes(t.type)) return;
    e.preventDefault();
    if (t.closest("td")) { t.dispatchEvent(new Event("change", { bubbles: true })); return; }
    t.dispatchEvent(new Event("change", { bubbles: true }));
    onNext();
  });

  // the page moved to another panel itself (a Continue button, the toolbar's Run, a link with #design)
  const tabs = [...document.querySelectorAll('[role="tab"][id^="tab-"]')];
  const mo = new MutationObserver(() => {
    if (current && !panelActive(phaseOf(current))) {
      const active = shownSteps().filter((s) => panelActive(phaseOf(s)));
      const target = (landOnRun && active.find((s) => s.hasAttribute("data-run"))) || active[0];
      landOnRun = false;
      if (target) go(target, { dir: 1 });
    } else refreshRail();
  });
  tabs.forEach((t) => mo.observe(t, { attributes: true, attributeFilter: ["aria-selected", "aria-disabled"] }));
  form.addEventListener("submit", () => {
    landOnRun = true;
    const run = shownSteps().find((s) => s.hasAttribute("data-run"));
    // the run step is in the panel already showing: go there straight away
    setTimeout(() => { if (run && panelActive(phaseOf(run))) { landOnRun = false; go(run, { dir: 1 }); } }, 0);
  }, true);

  // inputs shown or hidden by a mode, and summaries rewritten by the page
  let queued = false;
  const later = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      if (current && !visible(current)) {
        const vis = shownSteps();
        const fallback = vis.find((s) => phaseOf(s) === phaseOf(current)) || vis[0];
        if (fallback) go(fallback);
      } else refreshRail();
    });
  };
  const ours = (n) => rail.contains(n) || head.contains(n) || foot.contains(n);
  new MutationObserver((records) => { if (records.some((r) => !ours(r.target))) later(); }).observe(form, { attributes: true, attributeFilter: ["hidden", "class"], subtree: true, childList: true, characterData: true });

  // server field errors: show the step with the first one
  form.addEventListener("reveal", (e) => {
    const s = e.detail?.closest?.(".wz-step");
    if (s) go(s, { dir: -1 });
  });
  form.addEventListener("input", (e) => {
    const f = e.target.closest(".field, td");
    if (f?.querySelector(".error") && e.target.validity && !problem(e.target)) {
      f.querySelectorAll(".error").forEach((x) => x.remove());
      e.target.closest(".control")?.classList.remove("invalid");
    }
  });

  // start where the visitor left off, or at the first step of the panel showing
  let start = null;
  try { start = steps.find((s) => s.dataset.step === sessionStorage.getItem(store)); } catch { /* none */ }
  const activeFirst = shownSteps().find((s) => panelActive(phaseOf(s)));
  if (!start || !visible(start) || !panelActive(phaseOf(start))) start = activeFirst || shownSteps()[0];
  go(start);

  return {
    go: (key) => go(steps.find((s) => s.dataset.step === key), { focus: true }),
    current: () => current,
    refresh: refreshRail,
  };
}
