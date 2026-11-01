import { el, getJSON, postJSON } from "./common.js";
import { drawBeamModel } from "./beam-canvas.js";
import { beamSectionFromInputs, drawBeamSection, drawElevation, drawSection, drawSlabSection, s, sectionFromInputs } from "./drawings.js";
import { renderFigure } from "./figure-spec.js";
import { EXAMPLES as PAD_EXAMPLES } from "./foundation-examples.js";

// Each element's worked example, drawn with the app's own drawing code.
const ART = {
  async foundation(section, elevation) {
    // the pad's drawings come from the server, for its worked example
    const res = await postJSON("/api/foundation/check", PAD_EXAMPLES.pass);
    if (!res.ok) return;
    renderFigure(section, res.data.plots.figures.plan_plain, "Pad foundation plan");
    renderFigure(elevation, res.data.plots.figures.section, "Pad foundation section and ground pressure");
  },
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
    drawBeamModel(svg, {
      length: 20,
      supports: [{ x: 0, type: "fixed" }, { x: 10, type: "roller" }, { x: 20, type: "roller" }],
      loads: [
        { type: "linear", w1: 30, w2: 0, x1: 0, x2: 6 },
        { type: "point", W: 200, x: 6 },
        { type: "moment", M: 90, x: 10 },
        { type: "point", W: 150, x: 15 },
      ],
    });
    elevation.replaceChildren(svg);
  },
  slab(section, elevation) {
    const sample = {
      slab_type: "one_way",
      b: 1000,
      h: 175,
      cover: 25,
      bottom_x: { dia: 12, s: 200, As: 565 },
      bottom_y: { dia: 10, s: 300, As: 262 },
      top_x: { dia: 12, s: 200, As: 565 },
      top_y: { dia: null, s: 200, As: 0 },
    };
    drawSlabSection(section, sample, { width: 380, height: 210 });

    const svg = s("svg", { viewBox: "0 0 280 200", role: "img", "aria-label": "Two-way slab panel plan" });
    const pw = 150, ph = 120, x0 = 65, y0 = 35, x1 = x0 + pw, y1 = y0 + ph;
    svg.append(s("polygon", {
      points: `${x0},${y0} ${x1},${y0} ${x1},${y1} ${x0},${y1}`,
      fill: "var(--draw-concrete, #ece6db)",
      stroke: "var(--draw-rule, #e2ddd5)",
      "stroke-width": 1,
    }));
    // Continuous edges with hatching
    // Top
    svg.append(s("line", { x1: x0, y1: y0, x2: x1, y2: y0, stroke: "var(--draw-ink, #192329)", "stroke-width": 3 }));
    for (let x = x0 + 4; x < x1; x += 8) svg.append(s("line", { x1: x, y1: y0, x2: x + 6, y2: y0 - 7, stroke: "var(--draw-muted, #6a747a)", "stroke-width": 1 }));
    // Bottom
    svg.append(s("line", { x1: x0, y1: y1, x2: x1, y2: y1, stroke: "var(--draw-ink, #192329)", "stroke-width": 3 }));
    for (let x = x0 + 4; x < x1; x += 8) svg.append(s("line", { x1: x, y1: y1, x2: x - 6, y2: y1 + 7, stroke: "var(--draw-muted, #6a747a)", "stroke-width": 1 }));
    // Left
    svg.append(s("line", { x1: x0, y1: y0, x2: x0, y2: y1, stroke: "var(--draw-ink, #192329)", "stroke-width": 3 }));
    for (let y = y0 + 4; y < y1; y += 8) svg.append(s("line", { x1: x0, y1: y, x2: x0 - 7, y2: y + 6, stroke: "var(--draw-muted, #6a747a)", "stroke-width": 1 }));
    // Right
    svg.append(s("line", { x1: x1, y1: y0, x2: x1, y2: y1, stroke: "var(--draw-ink, #192329)", "stroke-width": 1.4 }));

    // Direction arrows & moments
    svg.append(s("line", { x1: x0 + 15, y1: (y0 + y1) / 2, x2: x1 - 15, y2: (y0 + y1) / 2, stroke: "var(--draw-muted, #6a747a)", "stroke-width": 1 }));
    svg.append(s("line", { x1: (x0 + x1) / 2, y1: y0 + 15, x2: (x0 + x1) / 2, y2: y1 - 15, stroke: "var(--draw-muted, #6a747a)", "stroke-width": 1 }));
    svg.append(s("text", { x: (x0 + x1) / 2, y: (y0 + y1) / 2 - 5, "text-anchor": "middle", "font-size": 11, "font-weight": "700", fill: "var(--draw-bmd, #059669)" }, "msx,mid"));
    svg.append(s("text", { x: (x0 + x1) / 2, y: (y0 + y1) / 2 + 13, "text-anchor": "middle", "font-size": 11, "font-weight": "700", fill: "var(--draw-bmd, #059669)" }, "msy,mid"));
    svg.append(s("text", { x: (x0 + x1) / 2, y: y1 + 20, "text-anchor": "middle", "font-size": 11, fill: "var(--draw-ink, #192329)" }, "lx = 5.0 m × ly = 6.0 m"));

    elevation.replaceChildren(svg);
  },
};

// ------------------------------------------------------------------ element tiles

// one tile per element: its worked example drawn by the app's own code, then what it checks and a start link
function tile(item) {
  const first = el("div"), second = el("div");
  const node = el("article", { class: `tile tile-${item.id}` },
    el("a", { class: "tile-art", href: item.url, tabindex: "-1", "aria-hidden": "true" }, first, second),
    el("div", { class: "tile-body" },
      el("h3", { class: "tile-title" }, el("a", { href: item.url }, item.title)),
      el("p", { class: "tile-meta" },
        el("span", {}, `Guide chapter ${item.chapter}`), el("span", {}, `${item.checks.length} kinds of check`)),
      el("p", { class: "tile-summary" }, item.summary),
      el("p", { class: "tile-checks" }, item.checks.join(", ")),
      el("a", { class: "btn tile-start", href: item.url }, `Start a ${item.title.toLowerCase()}`)));
  queueMicrotask(() => ART[item.id]?.(first, second));
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
