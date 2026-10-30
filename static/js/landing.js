import { el, getJSON } from "./common.js";
import { drawBeamModel } from "./beam-canvas.js";
import { beamSectionFromInputs, drawBeamSection, drawElevation, drawSection, drawSlabSection, s, sectionFromInputs } from "./drawings.js";

// Card accents from Beam Pro palette
const CARD_ACCENTS = {
  beam: { light: "#6366F1", dark: "#818CF8" },
  column: { light: "#8B5CF6", dark: "#A78BFA" },
  slab: { light: "#10B981", dark: "#34D399" },
};

const PLANNED_ACCENTS = {
  wall: "#06B6D4",
  slab: "#10B981",
  "flat-slab": "#F59E0B",
  foundation: "#EC4899",
  "retaining-wall": "#8B5CF6",
};

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

// ------------------------------------------------------------------ Hero Animation

function buildHeroAnimation(container) {
  const isReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const svg = s("svg", {
    viewBox: "0 0 1000 560",
    role: "img",
    "aria-label": "Beam analysis animation: loads, reactions, shear force and bending moment diagrams",
  });

  // Client's beam model: 20 m beam, fixed at 0, roller at 10, roller at 20
  const clientModel = {
    length: 20,
    supports: [
      { x: 0, type: "fixed" },
      { x: 10, type: "roller" },
      { x: 20, type: "roller" },
    ],
    loads: [
      { type: "linear", w1: 30, w2: 0, x1: 0, x2: 6 },
      { type: "point", W: 200, x: 6 },
      { type: "moment", M: 90, x: 10 },
      { type: "point", W: 150, x: 15 },
    ],
  };

  // the beam model, drawn by the canvas code (x from 70 to 930 in drawing units); its ruler is
  // dropped here so the reaction values can sit under the supports
  const beamGroup = s("g", { class: "hero-beam-model" });
  drawBeamModel(beamGroup, clientModel);
  beamGroup.querySelector(".ruler")?.remove();
  svg.append(beamGroup);
  const X = (x) => 70 + (x / 20) * 860;
  const label = (x, y, text, colour, anchor = "middle", size = 12) => s("text", { x, y, fill: colour,
    "font-size": size, "font-weight": "700", "text-anchor": anchor, class: "hero-num" }, text);

  // reactions from the app's own analysis of this beam, counted up by the animation
  const REACT = "var(--draw-react, #7C3AED)";
  const rx1 = label(X(0), 198, "0.00 kN", REACT, "start", 13);
  const rx1M = label(X(0), 214, "281.19 kN·m", REACT, "start", 12);
  const rx3 = label(X(10), 198, "0.00 kN", REACT, "middle", 13);
  const rx4 = label(X(20), 198, "0.00 kN", REACT, "end", 13);
  svg.append(s("g", { class: "hero-reactions" }, rx1, rx1M, rx3, rx4));

  const diagramsGroup = s("g", { class: "hero-diagrams" });
  const SFD = "var(--draw-sfd, #2563EB)", BMD = "var(--draw-bmd, #059669)";
  const axis = (y) => s("line", { x1: X(0), y1: y, x2: X(20), y2: y, stroke: "var(--line-strong, #CBD5E1)", "stroke-width": 1 });
  for (const x of [0, 6, 10, 15, 20]) {
    diagramsGroup.append(s("line", { x1: X(x), y1: 268, x2: X(x), y2: 530, stroke: "var(--draw-rule, #e2ddd5)",
      "stroke-width": 1, "stroke-dasharray": "4 4" }));
    diagramsGroup.append(label(X(x), 550, x ? `${x} m` : "0", "var(--draw-muted, #6a747a)", "middle", 12));
  }
  const path = (pts) => `M ${pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(" L ")}`;

  // shear force, positive above the axis
  const sfdBase = 330, vScale = 40 / 146.327;
  const V = (v) => sfdBase - v * vScale;
  const sfdPts = [[X(0), sfdBase]];
  for (let i = 0; i <= 24; i++) {
    const x = (6 * i) / 24;
    sfdPts.push([X(x), V(146.327 - 30 * (x - (x * x) / 12))]);
  }
  sfdPts.push([X(6), V(-143.673)], [X(10), V(-143.673)], [X(10), V(99.792)], [X(15), V(99.792)],
    [X(15), V(-50.208)], [X(20), V(-50.208)], [X(20), sfdBase]);
  diagramsGroup.append(axis(sfdBase), label(X(0), 262, "Shear force (kN) · positive above", SFD, "start", 13));
  const sfdFill = s("path", { d: `${path(sfdPts)} Z`, fill: SFD, "fill-opacity": isReducedMotion ? "0.22" : "0",
    stroke: "none", class: "hero-fill" });
  const sfdStroke = s("path", { d: path(sfdPts), fill: "none", stroke: SFD, "stroke-width": "2.2",
    "stroke-linecap": "round", "stroke-linejoin": "round" });
  diagramsGroup.append(sfdFill, sfdStroke,
    label(X(0) + 4, V(146.327) - 7, "146.33", SFD, "start", 11.5),
    label(X(6) - 4, V(56.327) - 7, "56.33", SFD, "end", 11.5),
    label(X(6) + 4, V(-143.673) + 15, "−143.67", SFD, "start", 11.5),
    label(X(10) + 4, V(99.792) - 7, "99.79", SFD, "start", 11.5),
    label(X(15) + 4, V(-50.208) + 15, "−50.21", SFD, "start", 11.5));

  // bending moment, sagging (positive) below the axis
  const bmdBase = 478, mScale = 46 / 337.918;
  const M = (m) => bmdBase + m * mScale;
  const bmdPts = [[X(0), bmdBase]];
  for (let i = 0; i <= 24; i++) {
    const x = (6 * i) / 24;
    bmdPts.push([X(x), M(-281.187 + 146.327 * x - 15 * x * x + (5 / 6) * x * x * x)]);
  }
  bmdPts.push([X(10), M(-337.918)], [X(10), M(-247.918)], [X(15), M(251.041)], [X(20), bmdBase]);
  diagramsGroup.append(axis(bmdBase), label(X(0), 404, "Bending moment (kN·m) · sagging below", BMD, "start", 13));
  const bmdFill = s("path", { d: `${path(bmdPts)} Z`, fill: BMD, "fill-opacity": isReducedMotion ? "0.22" : "0",
    stroke: "none", class: "hero-fill" });
  const bmdStroke = s("path", { d: path(bmdPts), fill: "none", stroke: BMD, "stroke-width": "2.2",
    "stroke-linecap": "round", "stroke-linejoin": "round" });
  diagramsGroup.append(bmdFill, bmdStroke,
    label(X(0) + 4, M(-281.187) - 7, "−281.19", BMD, "start", 11.5),
    label(X(6), M(236.775) + 16, "236.77", BMD, "middle", 11.5),
    label(X(10) - 4, M(-337.918) - 7, "−337.92", BMD, "end", 11.5),
    label(X(10) + 6, M(-247.918) + 4, "−247.92", BMD, "start", 11.5),
    label(X(15), M(251.041) + 16, "251.04", BMD, "middle", 11.5));
  for (const z of [2.455, 7.648, 12.484]) {
    diagramsGroup.append(s("circle", { cx: X(z), cy: bmdBase, r: 4, fill: BMD }));
  }

  svg.append(diagramsGroup);
  container.replaceChildren(svg);

  // ---------------- Animation Logic
  if (isReducedMotion) {
    rx1.textContent = "146.33 kN";
    rx3.textContent = "243.46 kN";
    rx4.textContent = "50.21 kN";
    return;
  }

  const sfdLen = sfdStroke.getTotalLength();
  const bmdLen = bmdStroke.getTotalLength();
  const loadElements = [...beamGroup.querySelectorAll('g[data-kind="load"]')];

  let animTimer = null;
  let isRunning = false;

  function countUp(node, target, suffix = " kN", duration = 800) {
    const start = performance.now();
    function tick(now) {
      const p = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - p, 2);
      node.textContent = `${(ease * target).toFixed(2)}${suffix}`;
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  function runCycle() {
    if (isRunning) return;
    isRunning = true;

    // Reset loads
    loadElements.forEach((el) => {
      el.style.opacity = "0";
      el.style.transform = "translateY(-36px)";
      el.style.transition = "none";
    });

    // Reset reactions
    rx1.textContent = "0.00 kN";
    rx3.textContent = "0.00 kN";
    rx4.textContent = "0.00 kN";
    rx1M.style.opacity = "0";
    rx1M.style.transition = "opacity 0.4s ease-out";

    // Reset diagram strokes
    sfdStroke.style.transition = "none";
    sfdStroke.style.strokeDasharray = `${sfdLen} ${sfdLen}`;
    sfdStroke.style.strokeDashoffset = `${sfdLen}`;
    sfdFill.style.fillOpacity = "0";

    bmdStroke.style.transition = "none";
    bmdStroke.style.strokeDasharray = `${bmdLen} ${bmdLen}`;
    bmdStroke.style.strokeDashoffset = `${bmdLen}`;
    bmdFill.style.fillOpacity = "0";

    // Drop in loads one by one
    loadElements.forEach((el, idx) => {
      setTimeout(() => {
        el.style.transition = "opacity 0.4s ease-out, transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)";
        el.style.opacity = "1";
        el.style.transform = "translateY(0)";
      }, 300 + idx * 300);
    });

    // Count up reactions at ~1500ms
    setTimeout(() => {
      countUp(rx1, 146.33);
      countUp(rx3, 243.46);
      countUp(rx4, 50.21);
      rx1M.style.opacity = "1";
    }, 1500);

    // Draw SFD stroke at ~1800ms
    setTimeout(() => {
      sfdStroke.style.transition = "stroke-dashoffset 1.4s cubic-bezier(0.25, 0.1, 0.25, 1)";
      sfdStroke.style.strokeDashoffset = "0";
      setTimeout(() => { sfdFill.style.fillOpacity = "0.22"; }, 1300);
    }, 1800);

    // Draw BMD stroke at ~2400ms
    setTimeout(() => {
      bmdStroke.style.transition = "stroke-dashoffset 1.5s cubic-bezier(0.25, 0.1, 0.25, 1)";
      bmdStroke.style.strokeDashoffset = "0";
      setTimeout(() => { bmdFill.style.fillOpacity = "0.22"; }, 1400);
    }, 2400);

    // End cycle and schedule next loop
    setTimeout(() => {
      isRunning = false;
      animTimer = setTimeout(runCycle, 6000);
    }, 4500);
  }

  // Start initial animation
  setTimeout(runCycle, 200);

  // Replay on container hover/click
  container.addEventListener("mouseenter", () => {
    if (!isRunning) {
      clearTimeout(animTimer);
      runCycle();
    }
  });
}

// ------------------------------------------------------------------ Elements List

function feature(item) {
  const accent = CARD_ACCENTS[item.id] || { light: "#6366F1", dark: "#818CF8" };
  const sectionBox = el("div");
  const elevationBox = el("div");

  const card = el("section", { class: "card-element", style: `--card-accent: ${accent.light};` },
    el("div", { class: "card-copy" },
      el("div", { class: "card-header-line" },
        el("span", { class: "card-kicker" }, `Chapter ${item.chapter} · Available Now`)),
      el("h2", { class: "card-title" }, item.title),
      el("p", { class: "card-summary" },
        `${item.summary} The checks run in the exact order of the Eurocode 2 guide's design procedure, with full working and a printable PDF.`),
      el("div", { class: "chips-list" }, item.checks.map((c) => el("span", { class: "chip" }, c))),
      el("div", { class: "card-action" },
        el("a", { class: "btn primary", href: item.url }, `Check a ${item.title.toLowerCase()}`),
        el("span", { class: "note" }, "Worked example included"))),
    el("div", { class: `card-art art-${item.id}`, "aria-hidden": "true" }, sectionBox, elevationBox));

  queueMicrotask(() => ART[item.id]?.(sectionBox, elevationBox));
  return card;
}

function planned(items) {
  const allPlanned = [
    ...items,
    {
      id: "ribbed-slab",
      title: "Ribbed slab",
      chapter: 3,
      checks: ["Ribbed slab: data being gathered"],
    },
  ];
  return el("section", { class: "planned-section" },
    el("h3", {}, "Coming next"),
    el("p", { class: "lede" }, "The other elements in the guide, planned in this order."),
    el("div", { class: "planned-grid" }, allPlanned.map((item) => {
      const tileColor = PLANNED_ACCENTS[item.id] || "#10B981";
      return el("div", { class: "tile-planned", style: `--tile-color: ${tileColor};` },
        el("div", { class: "tile-top" },
          el("span", { class: "tile-name" }, item.title),
          el("span", { class: "tile-badge" }, "Planned")),
        el("span", { class: "tile-chapter" }, `Chapter ${item.chapter}`),
        el("p", { class: "tile-desc" }, item.checks.join(", ")));
    })));
}

async function main() {
  const heroSlot = document.getElementById("hero-animation");
  if (heroSlot) buildHeroAnimation(heroSlot);

  const box = document.getElementById("elements");
  try {
    const items = await getJSON("/api/elements");
    const active = items.filter((i) => i.status === "active");
    const next = items.filter((i) => i.status !== "active");
    box.replaceChildren(
      el("div", { class: "element-cards-grid" }, ...active.map(feature)),
      planned(next)
    );
  } catch {
    box.replaceChildren(el("p", { class: "empty" }, "Could not load the elements. Is the server running?"));
  }
}

main();
