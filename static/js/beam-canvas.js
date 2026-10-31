// Beam drawing canvas: the beam with its supports and loads, drawn to scale. With a tool picked,
// a click on the beam places a support or a load; in select mode items are picked and dragged,
// and the ends of distributed loads can be dragged to change their extent.
import { s } from "./drawings.js";

const W = 1000, H = 250;
const X0 = 70, X1 = 930;
const BEAM_Y = 140, THICK = 12;
const INK = "var(--draw-ink, #192329)";
const MUTED = "var(--draw-muted, #6a747a)";
const LOAD = "var(--draw-load, #b33830)";
const ACCENT = "var(--draw-accent, #1e6479)";
const CONCRETE = "var(--draw-concrete, #ece6db)";
const PAPER = "var(--surface, #fffdfa)";
const RULE = "var(--draw-rule, #e2ddd5)";
const fmt = (v) => `${Number(v.toFixed(2))}`;

export const DEFAULT_LOAD = {
  point: { W: 50 }, udl: { w: 10 }, linear: { w1: 10, w2: 0 }, moment: { M: 50 },
};

function niceStep(length) {
  const raw = length / 10;
  const mag = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 2.5, 5, 10].map((m) => m * mag).find((v) => v >= raw);
}

function arrowDown(g, x, y1, y2, colour, width = 1.4, head = 7) {
  g.append(s("line", { x1: x, y1, x2: x, y2: y2 - head + 1, stroke: colour, "stroke-width": width }));
  g.append(s("path", { d: `M${x - head * 0.55} ${y2 - head} L${x + head * 0.55} ${y2 - head} L${x} ${y2} Z`, fill: colour }));
}

function supportShape(g, type, x, length, colour, beamLength = length) {
  const yb = BEAM_Y + THICK / 2;
  if (type === "fixed") {
    const atLeft = x < beamLength * 1e-6, atRight = x > beamLength * (1 - 1e-6);
    g.append(s("line", { x1: X(x, length), y1: BEAM_Y - 30, x2: X(x, length), y2: BEAM_Y + 30, stroke: colour, "stroke-width": 3 }));
    for (const side of atLeft ? [-1] : atRight ? [1] : [-1, 1]) {
      for (let y = BEAM_Y - 27; y < BEAM_Y + 30; y += 7) {
        g.append(s("line", { x1: X(x, length), y1: y, x2: X(x, length) + side * 9, y2: y + 7, stroke: colour, "stroke-width": 1 }));
      }
    }
    return;
  }
  const sx = X(x, length);
  if (type === "pin") {
    g.append(s("path", { d: `M${sx} ${yb} L${sx - 13} ${yb + 22} L${sx + 13} ${yb + 22} Z`, fill: PAPER, stroke: colour, "stroke-width": 1.5 }));
  } else {
    g.append(s("circle", { cx: sx, cy: yb + 10, r: 10, fill: PAPER, stroke: colour, "stroke-width": 1.5 }));
  }
  const yg = yb + (type === "pin" ? 22 : 20);
  g.append(s("line", { x1: sx - 19, y1: yg, x2: sx + 19, y2: yg, stroke: colour, "stroke-width": 1.4 }));
  for (let hx = sx - 17; hx < sx + 19; hx += 7) {
    g.append(s("line", { x1: hx, y1: yg, x2: hx - 6, y2: yg + 7, stroke: colour, "stroke-width": 0.9 }));
  }
}

function X(x, length) {
  return X0 + (x / length) * (X1 - X0);
}

const intensity = (ld, x) => (ld.type === "udl" ? ld.w : ld.w1 + (ld.w2 - ld.w1) * ((x - ld.x1) / (ld.x2 - ld.x1 || 1)));

/** Draws the beam model into an SVG element; returns the SVG. */
export function drawBeamModel(svg, model, { selected = null, interactive = false, scaleLength = null } = {}) {
  const L = model.length > 0 ? model.length : 1;
  // the drawing scale: normally the beam fills the width; while its end is dragged the scale can stay put
  const S = scaleLength || L;
  svg.replaceChildren();
  // ruler
  const step = niceStep(L);
  const ruler = s("g", { class: "ruler" });
  ruler.append(s("line", { x1: X0, y1: 222, x2: X(L, S), y2: 222, stroke: RULE, "stroke-width": 1 }));
  for (let x = 0; x <= L + 1e-9; x += step) {
    ruler.append(s("line", { x1: X(x, S), y1: 218, x2: X(x, S), y2: 226, stroke: MUTED, "stroke-width": 1 }));
    ruler.append(s("text", { x: X(x, S), y: 243, "text-anchor": "middle", "font-size": 13, fill: MUTED, class: "num" }, fmt(x)));
  }
  ruler.append(s("text", { x: X(L, S) + 8, y: 243, "font-size": 13, fill: MUTED }, "m"));
  svg.append(ruler);

  // the beam (also the click target for placing items)
  svg.append(s("rect", { x: X0, y: BEAM_Y - THICK / 2, width: X(L, S) - X0, height: THICK, fill: CONCRETE, stroke: INK,
    "stroke-width": 1.5, class: interactive ? "beam-hit" : null }));
  if (interactive) {
    svg.append(s("rect", { x: X0 - 10, y: 20, width: X(L, S) - X0 + 20, height: 180, fill: "transparent", class: "beam-zone" }));
  }

  const isSel = (kind, i) => selected && selected.kind === kind && selected.index === i;
  // uniform line load from gk and qk
  if (model.w > 0) {
    const g = s("g", { class: "line-load" });
    const top = BEAM_Y - THICK / 2 - 74;
    g.append(s("line", { x1: X0, y1: top, x2: X(L, S), y2: top, stroke: MUTED, "stroke-width": 1.2, "stroke-dasharray": "4 3" }));
    for (let i = 0; i <= 20; i++) {
      const x = X0 + ((X(L, S) - X0) * i) / 20;
      arrowDown(g, x, top, BEAM_Y - THICK / 2 - 1, MUTED, 0.8, 5);
    }
    g.append(s("text", { x: X(L, S), y: top - 7, "text-anchor": "end", "font-size": 14, fill: MUTED, "font-weight": 600 },
      `w = ${model.w.toFixed(2)} kN/m (gk, qk${model.slab ? ", slab" : ""})`));
    svg.append(g);
  }

  const dist = (model.loads || []).filter((ld) => ld.type === "udl" || ld.type === "linear");
  const wmax = Math.max(1e-9, ...dist.flatMap((ld) => [Math.abs(intensity(ld, ld.x1)), Math.abs(intensity(ld, ld.x2))]));
  (model.loads || []).forEach((ld, i) => {
    const colour = isSel("load", i) ? ACCENT : LOAD;
    const g = s("g", { class: `item${isSel("load", i) ? " selected" : ""}`, "data-kind": "load", "data-index": i });
    const yTop = BEAM_Y - THICK / 2;
    if (ld.type === "point") {
      const sx = X(ld.x, S);
      const up = ld.W < 0;
      if (up) {
        g.append(s("line", { x1: sx, y1: yTop - 4, x2: sx, y2: yTop - 70, stroke: colour, "stroke-width": 2.2 }));
        g.append(s("path", { d: `M${sx - 6} ${yTop - 62} L${sx + 6} ${yTop - 62} L${sx} ${yTop - 74} Z`, fill: colour }));
      } else {
        arrowDown(g, sx, yTop - 74, yTop - 1, colour, 2.2, 11);
      }
      g.append(s("text", { x: sx, y: yTop - 80, "text-anchor": "middle", "font-size": 14, "font-weight": 700, fill: INK, class: "load-label-text" }, `${fmt(Math.abs(ld.W))} kN`));
      g.append(s("rect", { x: sx - 12, y: yTop - 96, width: 24, height: 96, fill: "transparent", class: "grab" }));
    } else if (ld.type === "moment") {
      const sx = X(ld.x, S);
      const cw = ld.M >= 0;
      const r = 20, cy = yTop - 12;
      const a0 = cw ? 200 : -20, a1 = cw ? -20 : 200;
      const pts = Array.from({ length: 21 }, (_, k) => {
        const a = ((a0 + ((a1 - a0) * k) / 20) * Math.PI) / 180;
        return [sx + r * Math.cos(a), cy - r * Math.sin(a)];
      });
      g.append(s("polyline", { points: pts.map((p) => p.join(",")).join(" "), fill: "none", stroke: colour, "stroke-width": 2 }));
      const [xa, ya] = pts[19], [xb, yb] = pts[20];
      const ang = Math.atan2(yb - ya, xb - xa);
      g.append(s("path", { d: `M${xb} ${yb} L${xb - 9 * Math.cos(ang - 0.45)} ${yb - 9 * Math.sin(ang - 0.45)} L${xb - 9 * Math.cos(ang + 0.45)} ${yb - 9 * Math.sin(ang + 0.45)} Z`, fill: colour }));
      g.append(s("text", { x: sx, y: cy - r - 8, "text-anchor": "middle", "font-size": 14, "font-weight": 700, fill: INK, class: "load-label-text" }, `${fmt(Math.abs(ld.M))} kN·m`));
      g.append(s("rect", { x: sx - 26, y: cy - r - 24, width: 52, height: r * 2 + 30, fill: "transparent", class: "grab" }));
    } else {
      const n = Math.max(2, Math.round((X(ld.x2, S) - X(ld.x1, S)) / 30));
      const pts = [];
      for (let k = 0; k <= n; k++) {
        const x = ld.x1 + ((ld.x2 - ld.x1) * k) / n;
        const w = intensity(ld, x);
        const hgt = 14 + (48 * Math.abs(w)) / wmax;
        pts.push([X(x, S), yTop - hgt]);
        if (Math.abs(w) > 1e-9) arrowDown(g, X(x, S), yTop - hgt, yTop - 1, colour, 1.1, 6);
      }
      g.append(s("polyline", { points: pts.map((p) => p.join(",")).join(" "), fill: "none", stroke: colour, "stroke-width": 1.6 }));
      const label = ld.type === "udl" ? `${fmt(ld.w)} kN/m` : `${fmt(ld.w1)} → ${fmt(ld.w2)} kN/m`;
      const top = Math.min(...pts.map((p) => p[1]));
      g.append(s("text", { x: (X(ld.x1, S) + X(ld.x2, S)) / 2, y: top - 8, "text-anchor": "middle", "font-size": 14, "font-weight": 700, fill: INK, class: "load-label-text" }, label));
      g.append(s("rect", { x: X(ld.x1, S), y: top - 22, width: Math.max(4, X(ld.x2, S) - X(ld.x1, S)), height: yTop - top + 22, fill: "transparent", class: "grab" }));
      if (interactive && isSel("load", i)) {
        for (const end of ["x1", "x2"]) {
          g.append(s("rect", { x: X(ld[end], S) - 5, y: yTop - 40, width: 10, height: 34, rx: 3, fill: PAPER, stroke: ACCENT,
            "stroke-width": 1.5, class: "handle", "data-handle": end }));
        }
      }
    }
    svg.append(g);
  });

  (model.supports || []).forEach((sp, i) => {
    const g = s("g", { class: `item${isSel("support", i) ? " selected" : ""}`, "data-kind": "support", "data-index": i });
    supportShape(g, sp.type, sp.x, S, isSel("support", i) ? ACCENT : INK, L);
    const sx = X(sp.x, S);
    g.append(s("rect", { x: sx - 20, y: BEAM_Y - 32, width: 40, height: 70, fill: "transparent", class: "grab" }));
    svg.append(g);
  });

  if (interactive) {
    // green grip at the free end of the beam: drag it to change the length
    const ex = X(L, S), GREEN = "var(--pass, #2b7440)";
    const g = s("g", { class: "end-handle", "data-kind": "end", "data-index": 0 });
    g.append(s("text", { x: ex + 66, y: BEAM_Y - 22, "text-anchor": "end", "font-size": 13, "font-weight": 700,
      fill: GREEN, class: "num" }, `L = ${fmt(L)} m`));
    g.append(s("rect", { x: ex + 22, y: BEAM_Y - 12, width: 44, height: 24, rx: 12, fill: PAPER, stroke: GREEN, "stroke-width": 1.8 }));
    g.append(s("line", { x1: ex + 32, y1: BEAM_Y, x2: ex + 56, y2: BEAM_Y, stroke: GREEN, "stroke-width": 2 }));
    g.append(s("path", { d: `M${ex + 27} ${BEAM_Y} l8 -6 v12 z M${ex + 61} ${BEAM_Y} l-8 -6 v12 z`, fill: GREEN }));
    g.append(s("rect", { x: ex + 18, y: BEAM_Y - 40, width: 54, height: 56, fill: "transparent", class: "grab-end" }));
    g.append(s("title", {}, "Drag to change the length of the beam"));
    svg.append(g);
  }
  return svg;
}

/** Change the length of a beam model: supports at the old end move with it, anything past a
 *  shorter end is trimmed or dropped, and a stiffness part that reached the old end reaches the new one. */
export function resizeModel(model, oldL, newL) {
  const atEnd = (x) => Math.abs(x - oldL) < 1e-6;
  model.supports = (model.supports || []).map((sp) => (atEnd(sp.x) ? { ...sp, x: newL } : sp))
    .filter((sp) => sp.x <= newL + 1e-9);
  model.loads = (model.loads || []).filter((ld) => (ld.x ?? ld.x1) < newL - 1e-9 || (ld.x !== undefined && ld.x <= newL + 1e-9))
    .map((ld) => (ld.x2 !== undefined && ld.x2 > newL ? { ...ld, x2: newL } : ld));
  if (model.segments) {
    model.segments = model.segments.filter((sg) => sg.x1 < newL - 1e-9)
      .map((sg) => (atEnd(sg.x2) || sg.x2 > newL ? { ...sg, x2: newL } : sg));
  }
  return model;
}

export class BeamCanvas {
  constructor(host, { onChange, onSelect, onEdit, onLength }) {
    this.host = host;
    this.onChange = onChange;
    this.onLength = onLength || (() => {});
    this.onSelect = onSelect || (() => {});
    this.onEdit = onEdit || (() => {});
    this.tool = "select";
    this.selected = null;
    this.model = { length: 6, supports: [], loads: [], w: 0 };
    this.svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "beam-canvas", role: "application" });
    host.replaceChildren(this.svg);
    this.drag = null;
    this.svg.addEventListener("pointerdown", (e) => this.down(e));
    this.svg.addEventListener("pointermove", (e) => this.move(e));
    this.svg.addEventListener("pointerup", (e) => this.up(e));
    this.svg.addEventListener("pointercancel", () => { this.drag = null; });
    this.svg.addEventListener("dblclick", (e) => {
      const hit = this.hit(e.target);
      if (hit) {
        this.select({ kind: hit.kind, index: hit.index });
        const pt = { x: e.clientX, y: e.clientY };
        this.onEdit(this.selected, pt);
      }
    });
    host.addEventListener("keydown", (e) => {
      if ((e.key === "Delete" || e.key === "Backspace") && this.selected) {
        e.preventDefault();
        this.remove();
      } else if (e.key === "Escape") {
        this.select(null);
      }
    });
  }

  setModel(model) {
    this.model = model;
    if (this.selected) {
      const list = this.selected.kind === "load" ? model.loads : model.supports;
      if (this.selected.index >= list.length) this.selected = null;
    }
    this.render();
  }

  setTool(tool) {
    this.tool = tool;
    this.svg.classList.toggle("placing", tool !== "select");
  }

  render() {
    if (this.drag?.kind === "end") {
      // while the end is dragged: the beam grows or shrinks under the pointer, the scale only grows to keep it in view
      const preview = { ...this.model, length: this.drag.length };
      drawBeamModel(this.svg, preview, { selected: null, interactive: true, scaleLength: Math.max(this.drag.L0, this.drag.length) });
      return;
    }
    drawBeamModel(this.svg, this.model, { selected: this.selected, interactive: true });
  }

  svgX(event) {
    const pt = this.svg.createSVGPoint();
    pt.x = event.clientX;
    pt.y = event.clientY;
    return pt.matrixTransform(this.svg.getScreenCTM().inverse()).x;
  }

  select(sel) {
    this.selected = sel;
    this.onSelect(sel);
    this.render();
  }

  remove() {
    if (!this.selected) return;
    const list = this.selected.kind === "load" ? this.model.loads : this.model.supports;
    list.splice(this.selected.index, 1);
    this.selected = null;
    this.onSelect(null);
    this.onChange({ structural: true });
  }

  toBeam(event) {
    const pt = this.svg.createSVGPoint();
    pt.x = event.clientX;
    pt.y = event.clientY;
    const p = pt.matrixTransform(this.svg.getScreenCTM().inverse());
    const L = this.model.length;
    let x = ((p.x - X0) / (X1 - X0)) * L;
    x = Math.min(Math.max(x, 0), L);
    const snap = niceStep(L) / 10;
    x = Math.round(x / snap) * snap;
    for (const target of [0, L, ...this.model.supports.map((sp) => sp.x)]) {
      if (Math.abs(x - target) < L * 0.012) x = target;
    }
    return Number(x.toFixed(3));
  }

  getItemScreenPoint(sel) {
    if (!sel) return null;
    const L = this.model.length || 1;
    let sx = X0, sy = BEAM_Y;
    if (sel.kind === "load") {
      const item = (this.model.loads || [])[sel.index];
      if (!item) return null;
      if (item.type === "point" || item.type === "moment") {
        sx = X(item.x, L);
        sy = BEAM_Y - 40;
      } else {
        sx = (X(item.x1, L) + X(item.x2, L)) / 2;
        sy = BEAM_Y - 50;
      }
    } else if (sel.kind === "support") {
      const item = (this.model.supports || [])[sel.index];
      if (!item) return null;
      sx = X(item.x, L);
      sy = BEAM_Y + 20;
    }
    const pt = this.svg.createSVGPoint();
    pt.x = sx;
    pt.y = sy;
    const ctm = this.svg.getScreenCTM();
    return ctm ? pt.matrixTransform(ctm) : null;
  }

  hit(node) {
    const g = node.closest("[data-kind]");
    return g ? { kind: g.dataset.kind, index: Number(g.dataset.index), handle: node.dataset.handle || null } : null;
  }

  down(event) {
    const L = this.model.length;
    if (!(L > 0)) return;
    const x = this.toBeam(event);
    const hit = this.hit(event.target);
    if (hit?.kind === "end") {
      this.drag = { kind: "end", L0: L, length: L, startX: this.svgX(event) };
      this.svg.setPointerCapture(event.pointerId);
      this.render();
      return;
    }
    const isTextClick = event.target.tagName === "text" || event.target.classList.contains("load-label-text");
    if (isTextClick && hit) {
      this.select({ kind: hit.kind, index: hit.index });
      const pt = { x: event.clientX, y: event.clientY };
      this.onEdit(this.selected, pt);
      return;
    }
    if (this.tool === "select") {
      if (!hit) { this.select(null); return; }
      this.select({ kind: hit.kind, index: hit.index });
      const item = (hit.kind === "load" ? this.model.loads : this.model.supports)[hit.index];
      this.drag = { ...hit, start: x, orig: { ...item } };
      this.svg.setPointerCapture(event.pointerId);
      return;
    }
    if (["pin", "roller", "fixed"].includes(this.tool)) {
      const existing = this.model.supports.findIndex((sp) => Math.abs(sp.x - x) < 1e-6);
      if (existing >= 0) this.model.supports[existing].type = this.tool;
      else this.model.supports.push({ x, type: this.tool });
      this.model.supports.sort((a, b) => a.x - b.x);
      const index = this.model.supports.findIndex((sp) => Math.abs(sp.x - x) < 1e-6);
      this.selected = { kind: "support", index };
    } else {
      const item = { type: this.tool, case: "Ed", ...DEFAULT_LOAD[this.tool] };
      if (this.tool === "point" || this.tool === "moment") item.x = x;
      else {
        const span = Math.max(L / 5, niceStep(L));
        item.x1 = Math.min(x, L - span / 4);
        item.x2 = Math.min(L, Number((item.x1 + span).toFixed(3)));
      }
      this.model.loads.push(item);
      this.selected = { kind: "load", index: this.model.loads.length - 1 };
    }
    this.onSelect(this.selected);
    this.onChange({ structural: true });
    this.onEdit(this.selected, this.getItemScreenPoint(this.selected));
  }

  move(event) {
    if (!this.drag) return;
    if (this.drag.kind === "end") {
      const { L0, startX } = this.drag;
      const raw = L0 + ((this.svgX(event) - startX) / (X1 - X0)) * L0;   // pointer travel, at the scale the drag started with
      const step = L0 > 30 ? 0.25 : 0.1;
      this.drag.length = Math.min(Math.max(Math.round(raw / step) * step, 0.5), 60);
      this.drag.length = Number(this.drag.length.toFixed(2));
      if (!this.frame) this.frame = requestAnimationFrame(() => { this.frame = null; this.render(); });
      return;
    }
    const x = this.toBeam(event);
    const L = this.model.length;
    const { kind, index, handle, start, orig } = this.drag;
    const item = (kind === "load" ? this.model.loads : this.model.supports)[index];
    if (kind === "support" || item.type === "point" || item.type === "moment") {
      item.x = x;
    } else if (handle === "x1") {
      item.x1 = Math.min(x, item.x2 - L / 100);
    } else if (handle === "x2") {
      item.x2 = Math.max(x, item.x1 + L / 100);
    } else {
      const len = orig.x2 - orig.x1;
      const x1 = Math.min(Math.max(orig.x1 + (x - start), 0), L - len);
      item.x1 = Number(x1.toFixed(3));
      item.x2 = Number((x1 + len).toFixed(3));
    }
    this.drag.moved = true;
    if (!this.frame) {
      this.frame = requestAnimationFrame(() => {
        this.frame = null;
        this.render();
        this.onChange({ structural: false });
      });
    }
  }

  up() {
    if (!this.drag) return;
    if (this.drag.kind === "end") {
      const { L0, length } = this.drag;
      this.drag = null;
      if (Math.abs(length - L0) > 1e-9) this.onLength(length, L0);
      else this.render();
      return;
    }
    const { kind, moved } = this.drag;
    this.drag = null;
    if (kind === "support") {
      const item = this.model.supports[this.selected.index];
      this.model.supports.sort((a, b) => a.x - b.x);
      this.selected = { kind, index: this.model.supports.indexOf(item) };
    }
    if (moved) this.onChange({ structural: true });
  }
}
