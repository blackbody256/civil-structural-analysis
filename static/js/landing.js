import { el, getJSON } from "./common.js";
import { drawBeamModel } from "./beam-canvas.js";
import { beamSectionFromInputs, drawBeamSection, drawElevation, drawSection, s, sectionFromInputs } from "./drawings.js";

// Card accents from Beam Pro palette
const CARD_ACCENTS = {
  beam: { light: "#6366F1", dark: "#818CF8" },
  column: { light: "#8B5CF6", dark: "#A78BFA" },
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
};

// ------------------------------------------------------------------ Hero Animation

function buildHeroAnimation(container) {
  const isReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const svg = s("svg", {
    viewBox: "0 0 1000 480",
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

  // Group for the beam model (drawBeamModel)
  const beamGroup = s("g", { class: "hero-beam-model" });
  drawBeamModel(beamGroup, clientModel);
  svg.append(beamGroup);

  // Group for reactions count-up display below the supports
  const reactionsGroup = s("g", { class: "hero-reactions" });
  // Node 1 at x = 0 (px 50)
  const rx1 = s("text", { x: 50, y: 228, fill: "var(--draw-react, #7C3AED)", "font-size": "13", "font-weight": "700", "text-anchor": "middle" }, "0.00 kN");
  const rx1M = s("text", { x: 50, y: 242, fill: "var(--draw-react, #7C3AED)", "font-size": "11.5", "font-weight": "600", "text-anchor": "middle" }, "281.19 kN·m");
  // Node 3 at x = 10 (px 500)
  const rx3 = s("text", { x: 500, y: 228, fill: "var(--draw-react, #7C3AED)", "font-size": "13", "font-weight": "700", "text-anchor": "middle" }, "0.00 kN");
  // Node 4 at x = 20 (px 950)
  const rx4 = s("text", { x: 950, y: 228, fill: "var(--draw-react, #7C3AED)", "font-size": "13", "font-weight": "700", "text-anchor": "middle" }, "0.00 kN");
  reactionsGroup.append(rx1, rx1M, rx3, rx4);
  svg.append(reactionsGroup);

  // ---------------- Diagrams (SFD & BMD)
  const diagramsGroup = s("g", { class: "hero-diagrams" });

  // 1. SFD baseline at Y = 300
  const sfdBaseY = 300;
  diagramsGroup.append(s("line", { x1: 50, y1: sfdBaseY, x2: 950, y2: sfdBaseY, stroke: "var(--line-strong, #CBD5E1)", "stroke-width": "1" }));
  diagramsGroup.append(s("text", { x: 50, y: 260, fill: "var(--draw-sfd, #2563EB)", "font-size": "12", "font-weight": "700" },
    "Shear force (kN) · positive above"));

  // Build exact points for SFD:
  // V(x) = 146.33 - 30*(x - x^2/12) for x in [0, 6]
  // Y = 300 - (V / 146.33) * 36 (positive drawn ABOVE)
  const sfdPoints = [];
  sfdPoints.push([50, sfdBaseY]);
  // x=0 to 6 (px 50 to 320)
  for (let i = 0; i <= 24; i++) {
    const x = (6 * i) / 24;
    const px = 50 + (x / 20) * 900;
    const v = 146.327 - 30 * (x - (x * x) / 12);
    const py = sfdBaseY - (v / 146.327) * 36;
    sfdPoints.push([px, py]);
  }
  // drop at x = 6 by 200 kN to -143.67
  const pyDrop = sfdBaseY - (-143.673 / 146.327) * 36;
  sfdPoints.push([320, pyDrop]);
  sfdPoints.push([500, pyDrop]);
  // jump at x = 10 by +243.46 to +99.79
  const pyJump = sfdBaseY - (99.792 / 146.327) * 36;
  sfdPoints.push([500, pyJump]);
  sfdPoints.push([725, pyJump]);
  // drop at x = 15 by 150 kN to -50.21
  const pyDrop2 = sfdBaseY - (-50.208 / 146.327) * 36;
  sfdPoints.push([725, pyDrop2]);
  sfdPoints.push([950, pyDrop2]);
  sfdPoints.push([950, sfdBaseY]);

  const sfdD = `M ${sfdPoints[0][0]} ${sfdPoints[0][1]} ` + sfdPoints.slice(1).map(([x, y]) => `L ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");

  const sfdFill = s("path", {
    d: sfdD + " Z",
    fill: "var(--draw-sfd, #2563EB)",
    "fill-opacity": isReducedMotion ? "0.22" : "0",
    stroke: "none",
    style: "transition: fill-opacity 0.6s ease-out;",
  });
  const sfdStroke = s("path", {
    d: sfdD,
    fill: "none",
    stroke: "var(--draw-sfd, #2563EB)",
    "stroke-width": "2.2",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
  });
  diagramsGroup.append(sfdFill, sfdStroke);

  // Peak labels on SFD
  diagramsGroup.append(
    s("text", { x: 50, y: 258, fill: "var(--draw-sfd, #2563EB)", "font-size": "11", "font-weight": "700" }, "+146.33"),
    s("text", { x: 310, y: 348, fill: "var(--draw-sfd, #2563EB)", "font-size": "11", "font-weight": "700", "text-anchor": "end" }, "−143.67"),
    s("text", { x: 505, y: 270, fill: "var(--draw-sfd, #2563EB)", "font-size": "11", "font-weight": "700" }, "+99.79"),
    s("text", { x: 945, y: 326, fill: "var(--draw-sfd, #2563EB)", "font-size": "11", "font-weight": "700", "text-anchor": "end" }, "−50.21")
  );

  // 2. BMD baseline at Y = 415
  const bmdBaseY = 415;
  diagramsGroup.append(s("line", { x1: 50, y1: bmdBaseY, x2: 950, y2: bmdBaseY, stroke: "var(--line-strong, #CBD5E1)", "stroke-width": "1" }));
  diagramsGroup.append(s("text", { x: 50, y: 362, fill: "var(--draw-bmd, #059669)", "font-size": "12", "font-weight": "700" },
    "Bending moment (kN·m) · sagging below"));

  // Build exact points for BMD:
  // M(x) = -281.187 + 146.327 x - 15 x^2 + 5/6 x^3 for x in [0, 6]
  // Y = 415 + (M / 337.92) * 46 (sagging is positive, drawn BELOW)
  const bmdPoints = [];
  bmdPoints.push([50, bmdBaseY]);
  for (let i = 0; i <= 24; i++) {
    const x = (6 * i) / 24;
    const px = 50 + (x / 20) * 900;
    const m = -281.187 + 146.327 * x - 15 * x * x + (5 / 6) * x * x * x;
    const py = bmdBaseY + (m / 337.918) * 46;
    bmdPoints.push([px, py]);
  }
  // straight line from x = 6 to x = 10: M goes from +236.79 to -337.92
  const pyHog = bmdBaseY + (-337.918 / 337.918) * 46;
  bmdPoints.push([500, pyHog]);
  // 90 kNm moment step at x = 10 to -247.92
  const pyStep = bmdBaseY + (-247.918 / 337.918) * 46;
  bmdPoints.push([500, pyStep]);
  // straight line to x = 15: sagging +251.04
  const pySag = bmdBaseY + (251.041 / 337.918) * 46;
  bmdPoints.push([725, pySag]);
  // straight line to x = 20: M = 0
  bmdPoints.push([950, bmdBaseY]);

  const bmdD = `M ${bmdPoints[0][0]} ${bmdPoints[0][1]} ` + bmdPoints.slice(1).map(([x, y]) => `L ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");

  const bmdFill = s("path", {
    d: bmdD + " Z",
    fill: "var(--draw-bmd, #059669)",
    "fill-opacity": isReducedMotion ? "0.22" : "0",
    stroke: "none",
    style: "transition: fill-opacity 0.6s ease-out;",
  });
  const bmdStroke = s("path", {
    d: bmdD,
    fill: "none",
    stroke: "var(--draw-bmd, #059669)",
    "stroke-width": "2.2",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
  });
  diagramsGroup.append(bmdFill, bmdStroke);

  // Peak labels on BMD
  diagramsGroup.append(
    s("text", { x: 50, y: 370, fill: "var(--draw-bmd, #059669)", "font-size": "11", "font-weight": "700" }, "−281.19"),
    s("text", { x: 320, y: 462, fill: "var(--draw-bmd, #059669)", "font-size": "11", "font-weight": "700", "text-anchor": "middle" }, "+236.79"),
    s("text", { x: 500, y: 360, fill: "var(--draw-bmd, #059669)", "font-size": "11", "font-weight": "700", "text-anchor": "middle" }, "−337.89"),
    s("text", { x: 725, y: 464, fill: "var(--draw-bmd, #059669)", "font-size": "11", "font-weight": "700", "text-anchor": "middle" }, "+251.04")
  );

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
  return el("section", { class: "planned-section" },
    el("h3", {}, "Coming next"),
    el("p", { class: "lede" }, "The other elements in the guide, planned in this order."),
    el("div", { class: "planned-grid" }, items.map((item) => {
      const tileColor = PLANNED_ACCENTS[item.id] || "#6366F1";
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
