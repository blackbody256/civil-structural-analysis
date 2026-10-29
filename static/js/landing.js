import { el, getJSON } from "./common.js";
import { drawBeamModel } from "./beam-canvas.js";
import { beamSectionFromInputs, drawBeamSection, drawElevation, drawSection, s, sectionFromInputs } from "./drawings.js";

// Each element's worked example, drawn with the app's own drawing code.
const ART = {
  column(section, elevation) {
    const sample = { b: 350, h: 350, cover: 30, link_dia: 8, bar_dia: 20, n_b: 3, n_h: 3 };
    drawSection(section, sectionFromInputs(sample), { linkLabel: "H8 @ 200" });
    drawElevation(elevation, { l: 3600, depth: 350, NEd: 2100, top: "partial", bottom: "fixed", kTop: "k = 0.25" });
  },
  beam(section, elevation) {
    const sample = { shape: "rectangular", b: 400, h: 750, cover: 35, link_dia: 10, legs: 2,
      bottom_n: 4, bottom_dia: 20, top_n: 4, top_dia: 25 };
    drawBeamSection(section, beamSectionFromInputs(sample), { linkLabel: "H10 links" });
    const svg = s("svg", { viewBox: "0 0 1000 250", role: "img", "aria-label": "Beam model" });
    drawBeamModel(svg, { length: 20, supports: [{ x: 0, type: "fixed" }, { x: 10, type: "roller" }, { x: 20, type: "roller" }],
      loads: [{ type: "linear", w1: 30, w2: 0, x1: 0, x2: 6 }, { type: "point", W: 200, x: 6 }, { type: "moment", M: 90, x: 10 },
        { type: "point", W: 150, x: 15 }] });
    elevation.replaceChildren(svg);
  },
};

function feature(item) {
  const sectionBox = el("div");
  const elevationBox = el("div");
  const card = el("section", { class: "feature" },
    el("div", { class: "copy" },
      el("span", { class: "kicker" }, `Chapter ${item.chapter} · available now`),
      el("h2", {}, item.title),
      el("p", {}, `${item.summary} The checks run in the order of the guide's design procedure, `
        + "and you get a summary first, then the full calculation sheet as a PDF."),
      el("ul", {}, item.checks.map((c) => el("li", {}, c))),
      el("div", { class: "go" },
        el("a", { class: "btn primary", href: item.url }, `Check a ${item.title.toLowerCase()}`),
        el("span", { class: "note" }, "Opens with a worked example you can edit"))),
    el("div", { class: `art art-${item.id}`, "aria-hidden": "true" }, sectionBox, elevationBox));
  queueMicrotask(() => ART[item.id]?.(sectionBox, elevationBox));
  return card;
}

function planned(items) {
  return el("section", { class: "next" },
    el("h2", {}, "Coming next"),
    el("p", { class: "lede" }, "The other elements in the guide, planned in this order."),
    el("ul", { class: "next-list" }, items.map((item) => el("li", {},
      el("span", { class: "name" }, item.title),
      el("span", { class: "ch" }, `Ch ${item.chapter}`),
      el("span", { class: "what" }, item.checks.join(", "))))));
}

async function main() {
  const box = document.getElementById("elements");
  try {
    const items = await getJSON("/api/elements");
    box.replaceChildren(...items.filter((i) => i.status === "active").map(feature),
      planned(items.filter((i) => i.status !== "active")));
  } catch {
    box.replaceChildren(el("p", { class: "empty" }, "Could not load the elements. Is the server running?"));
  }
}

main();
