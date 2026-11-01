// Structural Analysis & Design shell: the module tabs under the title bar (HOME, COLUMN, BEAM, SLAB, PAD
// FOUNDATION), like the module tabs of Elisha's desktop app. The title bar is the page's <header class="topbar">.

const MODULES = [
  { id: "", title: "Home", url: "/" },
  { id: "column", title: "Column", url: "/column" },
  { id: "beam", title: "Beam", url: "/beam" },
  { id: "slab", title: "Slab", url: "/slab" },
  { id: "foundation", title: "Pad foundation", url: "/foundation" },
];

function mount() {
  const bar = document.querySelector(".topbar");
  if (!bar || bar.querySelector(".module-tabs")) return;
  const here = window.location.pathname.split("/")[1] || "";
  const nav = document.createElement("nav");
  nav.className = "module-tabs";
  nav.setAttribute("aria-label", "Modules");
  for (const m of MODULES) {
    const a = document.createElement("a");
    a.href = m.url;
    a.textContent = m.title;
    if (m.id === here) a.setAttribute("aria-current", "page");
    nav.append(a);
  }
  bar.append(nav);
}

mount();
