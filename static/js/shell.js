// RC Studio shell: the element list in the sidebar (a drawer behind a Menu button on phones).
// The sidebar itself is the page's <header class="topbar">, laid out by base.css; this only adds the list.

const ACTIVE = [
  { id: "column", title: "Column", chapter: 5, url: "/column" },
  { id: "beam", title: "Beam", chapter: 4, url: "/beam" },
  { id: "slab", title: "Slab", chapter: 3, url: "/slab" },
  { id: "foundation", title: "Pad foundation", chapter: 6, url: "/foundation" },
];
const PLANNED = [
  { title: "Wall", chapter: 5 },
  { title: "Flat slab", chapter: 7 },
  { title: "Retaining wall", chapter: 9 },
];

function node(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  n.append(...children);
  return n;
}

function mount() {
  const bar = document.querySelector(".topbar");
  if (!bar || bar.querySelector(".side-nav")) return;
  const here = window.location.pathname.split("/")[1] || "";

  const nav = node("nav", { class: "side-nav", id: "side-nav", "aria-label": "Elements" },
    node("a", { class: "nav-item", href: "/", ...(here === "" ? { "aria-current": "page" } : {}) },
      node("span", { class: "nav-name" }, "Overview")),
    node("p", { class: "nav-group" }, "Elements"),
    ...ACTIVE.map((e) => node("a", { class: "nav-item", href: e.url, ...(here === e.id ? { "aria-current": "page" } : {}) },
      node("span", { class: "nav-name" }, e.title), node("span", { class: "nav-ch", title: `Guide chapter ${e.chapter}` }, `Ch ${e.chapter}`))),
    node("p", { class: "nav-group" }, "Planned"),
    ...PLANNED.map((e) => node("span", { class: "nav-item is-planned", "aria-disabled": "true" },
      node("span", { class: "nav-name" }, e.title), node("span", { class: "nav-ch" }, `Ch ${e.chapter}`))));

  const toggle = node("button", { type: "button", class: "nav-toggle", "aria-expanded": "false", "aria-controls": "side-nav" },
    node("span", { class: "nav-toggle-icon", "aria-hidden": "true" }), "Menu");
  const close = () => { document.documentElement.classList.remove("nav-open"); toggle.setAttribute("aria-expanded", "false"); };
  toggle.addEventListener("click", () => {
    const open = document.documentElement.classList.toggle("nav-open");
    toggle.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  nav.addEventListener("click", (e) => { if (e.target.closest("a")) close(); });

  const brand = bar.querySelector(".brand");
  (brand || bar.firstChild).after(toggle, nav);
}

mount();
