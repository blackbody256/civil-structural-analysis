import { el, getJSON } from "./common.js";
import {
  beamSectionFromInputs, drawBeamElevation, drawBeamSection, drawElevation, drawSection, sectionFromInputs,
} from "./drawings.js";

// Each element's worked example, drawn with the app's own drawing code.
const ART = {
  column(section, elevation) {
    const sample = { b: 350, h: 350, cover: 30, link_dia: 8, bar_dia: 20, n_b: 3, n_h: 3 };
    drawSection(section, sectionFromInputs(sample), { linkLabel: "H8 @ 200" });
    drawElevation(elevation, { l: 3600, depth: 350, NEd: 2100, top: "partial", bottom: "fixed", kTop: "k = 0.25" });
  },
  beam(section, elevation) {
    const sample = { shape: "flanged", flange: "T", b: 300, h: 550, hf: 150, beff: 2030, cover: 30, link_dia: 8, legs: 2,
      tension_n: 4, tension_dia: 25, compression_n: 2, compression_dia: 16 };
    drawBeamSection(section, beamSectionFromInputs(sample), { linkLabel: "H8 @ 175" });
    drawBeamElevation(elevation, { l: 7, system: "end", w: 57.5 });
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
