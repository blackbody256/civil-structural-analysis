import { el, getJSON } from "./common.js";
import { drawElevation, drawSection, sectionFromInputs } from "./drawings.js";

// The passing example from the column form, drawn with the app's own drawing code.
const SAMPLE = { b: 350, h: 350, cover: 30, link_dia: 8, bar_dia: 20, n_b: 3, n_h: 3 };

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
    el("div", { class: "art", "aria-hidden": "true" }, sectionBox, elevationBox));
  queueMicrotask(() => {
    drawSection(sectionBox, sectionFromInputs(SAMPLE), { linkLabel: "H8 @ 200" });
    drawElevation(elevationBox, { l: 3600, depth: 350, NEd: 2100, top: "partial", bottom: "fixed", kTop: "k = 0.25" });
  });
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
