// Colour theme (system / light / dark) and positioning for menus and pop-overs.
// Every page also has a tiny inline script in <head> that applies the theme before
// first paint, so there is no flash of the wrong theme.

const KEY = "ec2.theme";
const media = window.matchMedia("(prefers-color-scheme: dark)");

const ICONS = {
  system: '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><rect x="2.5" y="3.5" width="15" height="10" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M7 16.5h6M10 13.5v3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
  light: '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><circle cx="10" cy="10" r="3.5" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M10 1.8v2.4M10 15.8v2.4M1.8 10h2.4M15.8 10h2.4M4.2 4.2l1.7 1.7M14.1 14.1l1.7 1.7M4.2 15.8l1.7-1.7M14.1 5.9l1.7-1.7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
  dark: '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M15.5 12.6A6.5 6.5 0 0 1 7.4 4.5a6.5 6.5 0 1 0 8.1 8.1Z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>',
};
const LABELS = { system: "Match system", light: "Light", dark: "Dark" };

export function themePreference() {
  try {
    const p = localStorage.getItem(KEY);
    return p === "light" || p === "dark" ? p : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(pref = themePreference()) {
  try {
    if (pref === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, pref);
  } catch { /* storage blocked: the choice lasts for this page only */ }
  const dark = pref === "dark" || (pref === "system" && media.matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.dispatchEvent(new CustomEvent("themechange", { detail: { pref, dark } }));
  renderButton(pref);
}

media.addEventListener("change", () => {
  if (themePreference() === "system") applyTheme("system");
});

/** Keep a [popover] attached under its invoker; align "start" or "end". */
export function anchorPopover(pop, invoker, align = "end") {
  const place = () => {
    const r = invoker.getBoundingClientRect();
    const w = pop.offsetWidth, h = pop.offsetHeight;
    let left = align === "end" ? r.right - w : r.left;
    left = Math.max(8, Math.min(left, window.innerWidth - w - 8));
    let top = r.bottom + 6;
    if (top + h > window.innerHeight - 8 && r.top - h - 6 > 8) top = r.top - h - 6;
    pop.style.left = `${left}px`;
    pop.style.top = `${Math.max(8, top)}px`;
  };
  pop.addEventListener("toggle", (e) => {
    if (e.newState === "open") {
      place();
      window.addEventListener("scroll", place, { passive: true });
      window.addEventListener("resize", place);
    } else {
      window.removeEventListener("scroll", place);
      window.removeEventListener("resize", place);
    }
  });
}

let button = null;

function renderButton(pref) {
  if (!button) return;
  button.innerHTML = `${ICONS[pref]}<span class="theme-label">${LABELS[pref]}</span><span class="caret"></span>`;
  document.querySelectorAll("#theme-menu [data-pref]").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.pref === pref)));
}

function mountMenu() {
  const slot = document.getElementById("theme-slot");
  if (!slot) return;
  button = document.createElement("button");
  button.type = "button";
  button.className = "btn quiet small theme-button";
  button.setAttribute("popovertarget", "theme-menu");
  button.setAttribute("aria-label", "Colour theme");
  const menu = document.createElement("div");
  menu.id = "theme-menu";
  menu.className = "menu";
  menu.setAttribute("popover", "");
  menu.setAttribute("role", "menu");
  for (const pref of ["system", "light", "dark"]) {
    const item = document.createElement("button");
    item.type = "button";
    item.setAttribute("role", "menuitemradio");
    item.dataset.pref = pref;
    item.innerHTML = `${ICONS[pref]}<span>${LABELS[pref]}</span>`;
    item.addEventListener("click", () => { applyTheme(pref); menu.hidePopover(); });
    menu.append(item);
  }
  slot.replaceWith(button, menu);
  anchorPopover(menu, button, "end");
  renderButton(themePreference());
}

mountMenu();
applyTheme(themePreference());
