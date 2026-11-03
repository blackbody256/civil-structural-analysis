import { el, getJSON } from "./common.js";
import { createViewer } from "./viewer3d.js";
import { beamScene, columnScene, foundationScene, slabScene } from "./models3d.js";
import { EXAMPLES as PAD_EXAMPLES } from "./foundation-examples.js";

// Each element's worked example (Elisha's), built in 3D by the same code as the input pages and turning slowly.
const MODELS = {
  column: () => columnScene({
    geometry: { b: 450, h: 300, l: 3.8 },
    reinforcement: { bar_dia: 25, n_b: 3, n_h: 2, link_dia: 8, cover: 35, cross_ties: false },
    actions: { NEd: 2600, My_top: 55, My_bottom: 30, bending: "uniaxial" },
  }),
  beam: () => beamScene({
    section: { shape: "rectangular", b: 350, h: 650 },
    span: { l: 15, supports: [{ x: 0, type: "pin" }, { x: 7.5, type: "roller" }, { x: 15, type: "roller" }] },
    reinforcement: { bottom_n: 3, bottom_dia: 25, bottom_layers: 1, top_n: 4, top_dia: 25, top_layers: 1, link_dia: 10, legs: 2, cover: 30 },
    materials: { dg: 20 },
    actions: { mode: "analysis", loads: [{ type: "udl", case: "G", w: 22, x1: 0, x2: 15 }, { type: "udl", case: "Q", w: 12, x1: 0, x2: 15 },
      { type: "point", case: "G", W: 60, x: 11.25 }] },
  }),
  slab: () => slabScene({
    slab: { type: "two_way", h: 190 },
    panel: { lx: 4.8, ly: 6, edges: { top: "continuous", bottom: "discontinuous", left: "continuous", right: "discontinuous" } },
    reinforcement: { bottom_x_dia: 10, bottom_x_s: 175, bottom_y_dia: 10, bottom_y_s: 200, top_x_dia: 10, top_x_s: 175, top_y_dia: 10, top_y_s: 200, cover: 25 },
  }),
  foundation: () => foundationScene(PAD_EXAMPLES.pass, { pressure: { pmax: 340, pmin: 300 } }),
};

/** The tile's model is built when the tile first comes into view, so its build-up animation is seen. */
function model(host, id) {
  const io = new IntersectionObserver((entries) => {
    if (!entries.some((e) => e.isIntersecting)) return;
    io.disconnect();
    const viewer = createViewer(host, { toolbar: false, labels: false, compact: true, spin: true });
    if (!viewer.ok) return;
    const scene = MODELS[id]();
    if (id !== "beam") scene.view = { ...scene.view, zoom: 0.84 };     // closer: the long beam needs all the room
    viewer.setScene(scene, { replay: true });
    host.closest(".tile")?.addEventListener("mouseenter", () => viewer.replay());
  }, { threshold: 0.3 });
  io.observe(host);
}

// ------------------------------------------------------------------ element tiles

// one titled panel per element: its worked example in 3D, what it checks, and Open
function tile(item) {
  const art = el("div", { class: "vp-host tile-model" });
  const node = el("article", { class: `tile tile-${item.id}` },
    el("div", { class: "tile-head" },
      el("h3", { class: "tile-title" }, el("a", { href: item.url }, item.title)),
      el("span", { class: "tile-ch" }, `Chapter ${item.chapter}`)),
    el("a", { class: "tile-art", href: item.url, tabindex: "-1", "aria-hidden": "true" }, art),
    el("div", { class: "tile-body" },
      el("p", { class: "tile-summary" }, item.summary),
      el("p", { class: "tile-checks" }, item.checks.join(", ")),
      el("div", { class: "tile-foot" },
        el("span", { class: "tile-count" }, `${item.checks.length} kinds of check`),
        el("a", { class: "btn primary tile-start", href: item.url }, `Open ${item.title.toLowerCase()}`))));
  if (MODELS[item.id]) queueMicrotask(() => model(art, item.id));
  return node;
}

function planned(items) {
  return el("section", { class: "planned" },
    el("h3", {}, "Planned"),
    el("ul", { class: "planned-list" }, items.map((item) => el("li", {},
      el("span", { class: "planned-name" }, item.title),
      el("span", { class: "planned-ch" }, `Chapter ${item.chapter}`),
      el("span", { class: "planned-checks" }, item.checks.join(", "))))));
}

async function main() {
  const box = document.getElementById("elements");
  try {
    const items = await getJSON("/api/elements");
    box.replaceChildren(
      el("div", { class: "tiles" }, ...items.filter((i) => i.status === "active").map(tile)),
      planned(items.filter((i) => i.status !== "active")));
  } catch {
    box.replaceChildren(el("p", { class: "empty" }, "Could not load the elements. Start the server and reload."));
  }
}

main();
