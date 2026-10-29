// Draws a figure described by reports/beam_figures.py (lines, polygons, circles and text in
// drawing units) as SVG, with the colour names mapped to the theme.
import { s } from "./drawings.js";

const COLOURS = {
  ink: "var(--draw-ink, #192329)", muted: "var(--draw-muted, #6a747a)", accent: "var(--draw-accent, #1e6479)",
  load: "var(--draw-load, #b33830)", rule: "var(--draw-rule, #e2ddd5)", concrete: "var(--draw-concrete, #ece6db)",
  paper: "var(--surface, #fffdfa)", sfd: "var(--draw-sfd, #2f5d8a)", bmd: "var(--draw-bmd, #a4452c)",
  defl: "var(--draw-defl, #8f5d0a)", react: "var(--draw-react, #2b7440)",
};
const ANCHOR = { s: "start", m: "middle", e: "end" };
const paint = (name) => (name ? COLOURS[name] || name : "none");

export function renderFigure(target, spec, label = "Figure") {
  const svg = s("svg", { viewBox: `0 0 ${spec.w} ${spec.h}`, role: "img", "aria-label": label, class: "fig-spec" });
  for (const it of spec.items) {
    if (it.k === "line") {
      const [x1, y1, x2, y2] = it.p;
      svg.append(s("line", { x1, y1, x2, y2, stroke: paint(it.c), "stroke-width": it.sw,
        "stroke-dasharray": it.dash ? it.dash.join(" ") : null, "stroke-linecap": "round" }));
    } else if (it.k === "poly") {
      const pts = [];
      for (let i = 0; i < it.p.length; i += 2) pts.push(`${it.p[i]},${it.p[i + 1]}`);
      svg.append(s(it.closed ? "polygon" : "polyline", { points: pts.join(" "), fill: it.f ? paint(it.f) : "none",
        "fill-opacity": it.f && it.fo < 1 ? it.fo : null, stroke: it.sw > 0.2 ? paint(it.c) : "none",
        "stroke-width": it.sw, "stroke-linejoin": "round" }));
    } else if (it.k === "circle") {
      svg.append(s("circle", { cx: it.x, cy: it.y, r: it.r, fill: paint(it.f), stroke: paint(it.c), "stroke-width": it.sw }));
    } else if (it.k === "text") {
      svg.append(s("text", { x: it.x, y: it.y, fill: paint(it.c), "font-size": it.size, "text-anchor": ANCHOR[it.a],
        "font-weight": it.b ? 700 : 400, class: "fig-text" }, it.t));
    }
  }
  target.replaceChildren(svg);
  return svg;
}
