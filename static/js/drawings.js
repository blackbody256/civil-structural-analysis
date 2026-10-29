// SVG drawings: column and beam cross-sections, column elevation, N–M interaction chart.

const NS = "http://www.w3.org/2000/svg";
// Colours come from the theme (see base.css); the fallbacks keep drawings readable elsewhere.
const INK = "var(--draw-ink, #192329)";
const MUTED = "var(--draw-muted, #6a747a)";
const ACCENT = "var(--draw-accent, #1e6479)";
const RULE = "var(--draw-rule, #e2ddd5)";
const PAPER = "var(--surface, #fffdfa)";
const STEEL = "var(--draw-steel, #192329)";
const LOAD = "var(--draw-load, #b33830)";
const CONCRETE = "var(--draw-concrete, #ece6db)";
const GRAIN = "var(--draw-grain, #c8bfae)";
const STUB = "var(--surface-3, #ebe6de)";
const COLORS = {
  pass: "var(--pass, #2b7440)", fail: "var(--fail, #b33830)", warn: "var(--warn, #8f5d0a)",
  info: "var(--info, #48658b)", na: "var(--na, #767d82)",
};
const PAINT = new Set(["fill", "stroke"]);
let uid = 0;

export function s(tag, attrs = {}, ...children) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    // var() is reliable in style declarations, not in presentation attributes
    if (PAINT.has(k) && String(v).startsWith("var(")) node.style.setProperty(k, v);
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

function text(x, y, str, attrs = {}) {
  return s("text", { x, y, "font-size": 12, fill: INK, ...attrs }, str);
}

// Text with subscripts written as base_sub, e.g. "M_Ed" or "l_0".
function symText(x, y, parts, attrs = {}) {
  const t = s("text", { x, y, "font-size": 12, fill: INK, ...attrs });
  for (const part of parts) {
    if (typeof part === "string") t.append(s("tspan", {}, part));
    else t.append(s("tspan", { "baseline-shift": "sub", "font-size": "75%" }, part.sub));
  }
  return t;
}

const sub = (str) => ({ sub: str });

function spread(lo, hi, n) {
  if (n === 1) return [(lo + hi) / 2];
  return Array.from({ length: n }, (_, i) => lo + ((hi - lo) * i) / (n - 1));
}

export function sectionFromInputs({ b, h, cover, link_dia, bar_dia, n_b, n_h }) {
  const a = cover + link_dia + bar_dia / 2;
  if (!(b > 0 && h > 0 && n_b >= 2 && n_h >= 2 && cover >= 0) || 2 * a >= Math.min(b, h)) return null;
  const xs = spread(-b / 2 + a, b / 2 - a, n_b);
  const ys = spread(-h / 2 + a, h / 2 - a, n_h);
  const bars = [];
  for (const y of [ys[ys.length - 1], ys[0]]) {
    xs.forEach((x, i) => bars.push({ x, y, dia: bar_dia, corner: i === 0 || i === xs.length - 1 }));
  }
  for (const x of [xs[0], xs[xs.length - 1]]) ys.slice(1, -1).forEach((y) => bars.push({ x, y, dia: bar_dia, corner: false }));
  return { b, h, cover, link_dia, bar_dia, n_b, n_h, a, bars };
}

function ticks(x, y, vertical) {
  // architectural tick at a dimension end
  return s("line", vertical
    ? { x1: x - 4, y1: y + 4, x2: x + 4, y2: y - 4, stroke: INK, "stroke-width": 1.3 }
    : { x1: x - 4, y1: y + 4, x2: x + 4, y2: y - 4, stroke: INK, "stroke-width": 1.3 });
}

function dimH(x1, x2, y, label, fromY) {
  const g = s("g", { class: "dim" });
  if (fromY !== undefined) {
    g.append(s("line", { x1, y1: fromY + 4, x2: x1, y2: y + 6, stroke: MUTED, "stroke-width": 0.7 }));
    g.append(s("line", { x1: x2, y1: fromY + 4, x2, y2: y + 6, stroke: MUTED, "stroke-width": 0.7 }));
  }
  g.append(s("line", { x1, y1: y, x2, y2: y, stroke: INK, "stroke-width": 0.9 }));
  g.append(ticks(x1, y), ticks(x2, y));
  g.append(text((x1 + x2) / 2, y + 17, label, { "text-anchor": "middle", class: "num" }));
  return g;
}

function dimV(y1, y2, x, label, fromX) {
  const g = s("g", { class: "dim" });
  if (fromX !== undefined) {
    g.append(s("line", { x1: fromX - 4, y1, x2: x - 6, y2: y1, stroke: MUTED, "stroke-width": 0.7 }));
    g.append(s("line", { x1: fromX - 4, y1: y2, x2: x - 6, y2, stroke: MUTED, "stroke-width": 0.7 }));
  }
  g.append(s("line", { x1: x, y1, x2: x, y2, stroke: INK, "stroke-width": 0.9 }));
  g.append(ticks(x, y1, true), ticks(x, y2, true));
  g.append(text(x - 9, (y1 + y2) / 2, label, {
    "text-anchor": "middle", transform: `rotate(-90 ${x - 9} ${(y1 + y2) / 2})`, class: "num",
  }));
  return g;
}

function concretePattern(id) {
  return s("pattern", { id, width: 16, height: 16, patternUnits: "userSpaceOnUse" },
    s("rect", { width: 16, height: 16, fill: CONCRETE }),
    s("circle", { cx: 3, cy: 4, r: 0.9, fill: GRAIN }),
    s("circle", { cx: 11, cy: 11, r: 0.7, fill: GRAIN }),
    s("circle", { cx: 13, cy: 3, r: 0.5, fill: GRAIN }),
    s("path", { d: "M6 9 l1.6 2.6 h-3.2z", fill: "none", stroke: GRAIN, "stroke-width": 0.6 }));
}

/**
 * Cross-section to scale.
 * opts.status: {section, links, bars, cover} -> status string, failed parts are drawn red.
 */
export function drawSection(target, sec, opts = {}) {
  const W = opts.width || 420;
  const H = opts.height || 390;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": sec ? `Cross-section ${sec.b} × ${sec.h} mm` : "Cross-section" });
  if (!sec) {
    svg.append(text(W / 2, H / 2, "Section dimensions incomplete", { "text-anchor": "middle", fill: MUTED }));
    target.replaceChildren(svg);
    return svg;
  }
  const id = `conc${++uid}`;
  svg.append(s("defs", {}, concretePattern(id)));
  const padL = 70, padR = 96, padT = 44, padB = 62;
  const scale = Math.min((W - padL - padR) / sec.b, (H - padT - padB) / sec.h);
  const w = sec.b * scale, hh = sec.h * scale;
  const x0 = padL + (W - padL - padR - w) / 2;
  const y0 = padT + (H - padT - padB - hh) / 2;
  const X = (x) => x0 + (x + sec.b / 2) * scale;
  const Y = (y) => y0 + (sec.h / 2 - y) * scale;
  const status = opts.status || {};
  const cls = (part) => `part ${part}${status[part] === "fail" ? " is-fail" : ""}`;

  svg.append(s("rect", { x: x0, y: y0, width: w, height: hh, fill: `url(#${id})`, stroke: INK, "stroke-width": 1.8,
    class: cls("section"), "data-part": "section" }));

  const c = sec.cover + sec.link_dia / 2;
  const r = Math.max(2.5 * sec.link_dia * scale, 4);
  svg.append(s("rect", { x: x0 + c * scale, y: y0 + c * scale, width: (sec.b - 2 * c) * scale, height: (sec.h - 2 * c) * scale,
    rx: r, ry: r, fill: "none", stroke: ACCENT, "stroke-width": Math.max(sec.link_dia * scale, 1.6),
    class: cls("links"), "data-part": "links" }));

  const bars = s("g", { class: cls("bars"), "data-part": "bars" });
  for (const bar of sec.bars) {
    bars.append(s("circle", { cx: X(bar.x), cy: Y(bar.y), r: Math.max((bar.dia / 2) * scale, 2.4), fill: STEEL }));
  }
  svg.append(bars);

  // axes
  const cx = x0 + w / 2, cy = y0 + hh / 2;
  const axis = { stroke: MUTED, "stroke-width": 0.8, "stroke-dasharray": "10 3 2 3" };
  svg.append(s("line", { x1: x0 - 16, y1: cy, x2: x0 + w + 16, y2: cy, ...axis }));
  svg.append(s("line", { x1: cx, y1: y0 - 16, x2: cx, y2: y0 + hh + 16, ...axis }));
  svg.append(text(x0 + w + 20, cy + 4, "y", { fill: MUTED, "font-weight": 700 }));
  svg.append(text(x0 - 26, cy + 4, "y", { fill: MUTED, "font-weight": 700 }));
  svg.append(text(cx - 4, y0 - 20, "z", { fill: MUTED, "font-weight": 700 }));
  // axial load into the page
  svg.append(s("circle", { cx, cy, r: 7, fill: PAPER, stroke: INK, "stroke-width": 1.2 }));
  svg.append(s("path", { d: `M${cx - 4.5} ${cy - 4.5} L${cx + 4.5} ${cy + 4.5} M${cx + 4.5} ${cy - 4.5} L${cx - 4.5} ${cy + 4.5}`, stroke: INK, "stroke-width": 1.2 }));

  svg.append(dimH(x0, x0 + w, y0 + hh + 30, `b = ${sec.b}`, y0 + hh));
  svg.append(dimV(y0, y0 + hh, x0 - 34, `h = ${sec.h}`, x0));

  // cover callout (top right)
  const coverCls = status.cover === "fail" ? COLORS.fail : MUTED;
  const xc = x0 + w - Math.min(26, w * 0.12);
  const g = s("g", { class: cls("cover"), "data-part": "cover" });
  g.append(s("line", { x1: xc, y1: y0, x2: xc, y2: y0 + sec.cover * scale, stroke: coverCls, "stroke-width": 1.2 }));
  g.append(s("line", { x1: xc, y1: y0, x2: x0 + w + 12, y2: y0 - 18, stroke: coverCls, "stroke-width": 0.7 }));
  g.append(symText(x0 + w + 14, y0 - 20, ["c", sub("nom"), ` = ${sec.cover}`], { fill: coverCls, "font-size": 11.5 }));
  svg.append(g);

  // bar and link labels
  const tr = sec.bars[sec.n_b - 1];
  const nBars = sec.bars.length;
  svg.append(s("line", { x1: X(tr.x) + 3, y1: Y(tr.y) + 3, x2: x0 + w + 14, y2: y0 + hh * 0.3, stroke: MUTED, "stroke-width": 0.7 }));
  svg.append(text(x0 + w + 16, y0 + hh * 0.3 + 4, `${nBars}H${sec.bar_dia}`, { "font-weight": 700, class: "num" }));
  const linkX = x0 + w - c * scale;
  svg.append(s("line", { x1: linkX, y1: y0 + hh * 0.62, x2: x0 + w + 14, y2: y0 + hh * 0.62, stroke: MUTED, "stroke-width": 0.7 }));
  svg.append(text(x0 + w + 16, y0 + hh * 0.62 + 4, opts.linkLabel || `H${sec.link_dia} links`, { fill: ACCENT, "font-weight": 700, "font-size": 11.5 }));
  svg.append(symText(x0 + w + 16, y0 + hh * 0.62 + 20, ["a = ", `${sec.a.toFixed(0)}`], { fill: MUTED, "font-size": 11 }));

  target.replaceChildren(svg);
  return svg;
}

function hatch(x1, y, x2, dir) {
  const g = s("g", {});
  g.append(s("line", { x1, y1: y, x2, y2: y, stroke: INK, "stroke-width": 2 }));
  for (let x = x1 + 2; x < x2; x += 7) {
    g.append(s("line", { x1: x, y1: y, x2: x - 6, y2: y + dir * 7, stroke: INK, "stroke-width": 0.8 }));
  }
  return g;
}

function endSymbol(kind, cx, y, colW, dir, label) {
  // dir = -1 for the top end (symbol above), +1 for the bottom end (symbol below)
  const g = s("g", {});
  if (kind === "pinned") {
    const tip = y, base = y + dir * 16;
    g.append(s("path", { d: `M${cx} ${tip} L${cx - 11} ${base} L${cx + 11} ${base} Z`, fill: PAPER, stroke: INK, "stroke-width": 1.3 }));
    g.append(hatch(cx - 20, base, cx + 20, dir));
  } else if (kind === "fixed" || kind === "sway") {
    g.append(hatch(cx - colW / 2 - 16, y, cx + colW / 2 + 16, dir));
    if (kind === "sway") {
      g.append(s("circle", { cx: cx - 10, cy: y + dir * 11, r: 3.5, fill: PAPER, stroke: INK }));
      g.append(s("circle", { cx: cx + 10, cy: y + dir * 11, r: 3.5, fill: PAPER, stroke: INK }));
    }
  } else if (kind === "partial") {
    for (const side of [-1, 1]) {
      const x = side < 0 ? cx - colW / 2 - 54 : cx + colW / 2;
      g.append(s("rect", { x, y: y - (dir < 0 ? 0 : 14), width: 54, height: 14, fill: STUB, stroke: INK, "stroke-width": 1 }));
    }
    if (label) g.append(text(cx + colW / 2 + 58, y + (dir < 0 ? 11 : -3), label, { "font-size": 11, fill: MUTED, class: "num" }));
  }
  return g;
}

/**
 * Elevation of the column. data: {l, depth, top, bottom, kTop, kBottom, axis, NEd, l0, moments}
 * top/bottom kinds: pinned | fixed | partial | free | sway
 */
export function drawElevation(target, data, opts = {}) {
  const W = opts.width || (data.moments ? 520 : 420);
  const H = opts.height || 390;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Column elevation" });
  const id = `conc${++uid}`;
  svg.append(s("defs", {}, concretePattern(id)));
  const top = 62, bot = H - 52;
  const cx = data.moments ? 128 : 170;
  const colW = Math.max(18, Math.min(44, (data.depth || 300) / 10));
  svg.append(s("rect", { x: cx - colW / 2, y: top, width: colW, height: bot - top, fill: `url(#${id})`, stroke: INK, "stroke-width": 1.6 }));
  svg.append(endSymbol(data.top, cx, top, colW, -1, data.kTop));
  svg.append(endSymbol(data.bottom, cx, bot, colW, 1, data.kBottom));

  // axial load
  svg.append(s("line", { x1: cx, y1: 10, x2: cx, y2: top - (data.top === "pinned" ? 22 : 8), stroke: LOAD, "stroke-width": 2 }));
  svg.append(s("path", { d: `M${cx - 6} ${top - (data.top === "pinned" ? 32 : 18)} L${cx + 6} ${top - (data.top === "pinned" ? 32 : 18)} L${cx} ${top - (data.top === "pinned" ? 20 : 6)} Z`, fill: LOAD }));
  svg.append(symText(cx + 10, 22, ["N", sub("Ed"), data.NEd ? ` = ${Math.round(data.NEd)} kN` : ""], { "font-weight": 700 }));

  // clear height
  const stubs = data.top === "partial" || data.bottom === "partial";
  const dx = cx + colW / 2 + (data.moments ? 18 : stubs ? 128 : 70);
  svg.append(dimV(top, bot, data.moments ? cx - colW / 2 - 24 : dx, `l = ${(data.l / 1000).toFixed(2)} m`));

  if (data.l0) {
    const span = Math.min(data.l0 / data.l, 1.6) * (bot - top);
    const mid = (top + bot) / 2;
    const xb = data.moments ? cx - colW / 2 - 58 : cx - colW / 2 - 40;
    const y1 = Math.max(mid - span / 2, 8), y2 = Math.min(mid + span / 2, H - 8);
    svg.append(s("line", { x1: xb, y1, x2: xb, y2, stroke: ACCENT, "stroke-width": 1.4 }));
    svg.append(s("line", { x1: xb - 5, y1, x2: xb + 5, y2: y1, stroke: ACCENT, "stroke-width": 1.4 }));
    svg.append(s("line", { x1: xb - 5, y1: y2, x2: xb + 5, y2, stroke: ACCENT, "stroke-width": 1.4 }));
    svg.append(symText(xb - 8, mid, ["l", sub("0"), ` = ${(data.l0 / 1000).toFixed(2)} m`], {
      fill: ACCENT, "font-weight": 700, "text-anchor": "middle", transform: `rotate(-90 ${xb - 8} ${mid})`,
    }));
  }

  if (data.moments) drawMomentDiagram(svg, data.moments, { x0: 310, top, bot, width: W - 370 });
  target.replaceChildren(svg);
  return svg;
}

function drawMomentDiagram(svg, m, { x0, top, bot, width }) {
  const topIsMax = Math.abs(m.M_top) >= Math.abs(m.M_bottom);
  const firstTop = topIsMax ? m.M02 : m.M01;
  const firstBot = topIsMax ? m.M01 : m.M02;
  let midT, topT, botT;
  if (m.slender) {
    const endT = m.M01 + 0.5 * m.M2;
    midT = m.M0e + m.M2;
    [topT, botT] = topIsMax ? [m.M02, endT] : [endT, m.M02];
  } else {
    [topT, botT, midT] = [firstTop, firstBot, (firstTop + firstBot) / 2];
  }
  const peak = Math.max(Math.abs(firstTop), Math.abs(firstBot), Math.abs(midT), Math.abs(topT), Math.abs(botT), 1e-6);
  const neg = Math.min(firstTop, firstBot, topT, botT, midT) < 0;
  const base = neg ? x0 + width * 0.35 : x0;
  const scale = (neg ? width * 0.55 : width * 0.78) / peak;
  const Xm = (v) => base + v * scale;
  const mid = (top + bot) / 2;
  svg.append(s("line", { x1: base, y1: top - 6, x2: base, y2: bot + 6, stroke: INK, "stroke-width": 1 }));
  svg.append(s("path", { d: `M${base} ${bot} L${Xm(firstBot)} ${bot} L${Xm(firstTop)} ${top} L${base} ${top}`,
    fill: MUTED, "fill-opacity": 0.08, stroke: MUTED, "stroke-width": 1.1, "stroke-dasharray": "5 3" }));
  let d = `M${base} ${bot}`;
  const pts = [];
  for (let i = 0; i <= 24; i++) {
    const t = i / 24;
    const v = botT * (1 - t) * (1 - 2 * t) + midT * 4 * t * (1 - t) + topT * t * (2 * t - 1);
    pts.push([Xm(v), bot - t * (bot - top)]);
  }
  d += pts.map(([x, y]) => ` L${x} ${y}`).join("") + ` L${base} ${top} Z`;
  svg.append(s("path", { d, fill: ACCENT, "fill-opacity": 0.1, stroke: ACCENT, "stroke-width": 2 }));
  const label = (v, y, extra = {}) => text(Xm(v) + (v >= 0 ? 6 : -6), y, v.toFixed(1), {
    "text-anchor": v >= 0 ? "start" : "end", "font-size": 11.5, fill: ACCENT, "font-weight": 700, class: "num", ...extra });
  svg.append(label(topT, top + 4), label(midT, mid + 4), label(botT, bot + 4));
  svg.append(symText(base, top - 18, ["M", sub(m.axis === "z" ? "z" : "y"), " [kNm]"], { "font-size": 11.5, fill: MUTED, "text-anchor": "middle" }));
  svg.append(text(base, bot + 28, m.slender ? "dashed 1st order · solid design" : "1st order = design", {
    "font-size": 10.5, fill: MUTED, "text-anchor": "middle" }));
}

function niceTicks(max, count = 5) {
  if (!(max > 0)) return [0, 1];
  const raw = max / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((v) => v >= raw);
  const n = Math.ceil(max / step);
  return Array.from({ length: n + 1 }, (_, i) => +(i * step).toFixed(6));
}

/** N–M interaction chart. d: {curve: [[M, N]], NEd, MEd, M02, MRd, Nmax}; opts.axis, opts.status */
export function drawInteraction(target, d, opts = {}) {
  const W = opts.width || 470;
  const H = opts.height || 360;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `N–M interaction about ${opts.axis}–${opts.axis}` });
  const pl = 62, pr = 20, pt = 22, pb = 48;
  const pw = W - pl - pr, ph = H - pt - pb;
  const mt = niceTicks(Math.max(...d.curve.map((p) => p[0]), d.MEd) * 1.12);
  const nt = niceTicks(Math.max(d.Nmax, d.NEd) * 1.08);
  const mMax = mt[mt.length - 1], nMax = nt[nt.length - 1];
  const X = (m) => pl + (m / mMax) * pw;
  const Y = (n) => pt + ph - (n / nMax) * ph;

  for (const m of mt) {
    svg.append(s("line", { x1: X(m), y1: pt, x2: X(m), y2: pt + ph, stroke: RULE, "stroke-width": 0.8 }));
    svg.append(text(X(m), pt + ph + 16, m, { "text-anchor": "middle", "font-size": 11, fill: MUTED, class: "num" }));
  }
  for (const n of nt) {
    svg.append(s("line", { x1: pl, y1: Y(n), x2: pl + pw, y2: Y(n), stroke: RULE, "stroke-width": 0.8 }));
    svg.append(text(pl - 6, Y(n) + 4, n, { "text-anchor": "end", "font-size": 11, fill: MUTED, class: "num" }));
  }
  svg.append(s("rect", { x: pl, y: pt, width: pw, height: ph, fill: "none", stroke: INK, "stroke-width": 1 }));
  svg.append(symText(pl + pw / 2, H - 10, ["M", sub(opts.axis || "y"), " [kNm]"], { "text-anchor": "middle", "font-size": 12 }));
  svg.append(symText(16, pt + ph / 2, ["N [kN]"], { "text-anchor": "middle", "font-size": 12, transform: `rotate(-90 16 ${pt + ph / 2})` }));

  const pts = d.curve.map(([m, n]) => `${X(m)},${Y(n)}`);
  svg.append(s("polygon", { points: [`${X(0)},${Y(d.curve[0][1])}`, ...pts, `${X(0)},${Y(d.Nmax)}`].join(" "), fill: ACCENT, "fill-opacity": 0.08, stroke: "none" }));
  svg.append(s("polyline", { points: pts.join(" "), fill: "none", stroke: ACCENT, "stroke-width": 2.2, "stroke-linejoin": "round" }));

  const colour = COLORS[opts.status === "pass" ? "pass" : "fail"];
  const yN = Y(d.NEd);
  if (d.MRd !== null && d.MRd !== undefined) {
    svg.append(s("line", { x1: X(0), y1: yN, x2: X(d.MRd), y2: yN, stroke: MUTED, "stroke-width": 1, "stroke-dasharray": "4 3" }));
    svg.append(s("path", { d: `M${X(d.MRd)} ${yN - 6} l6 6 l-6 6 l-6 -6 Z`, fill: ACCENT }));
    svg.append(symText(X(d.MRd) + 9, yN - 8, ["M", sub("Rd"), ` = ${d.MRd.toFixed(1)}`], { "font-size": 11.5, fill: ACCENT, "font-weight": 700 }));
  }
  svg.append(s("circle", { cx: X(d.M02), cy: yN, r: 4.5, fill: PAPER, stroke: MUTED, "stroke-width": 1.5 }));
  svg.append(s("circle", { cx: X(d.MEd), cy: yN, r: 6.5, fill: colour, stroke: PAPER, "stroke-width": 2 }));
  svg.append(symText(X(d.MEd) + 9, yN + 18, ["M", sub("Ed"), ` = ${d.MEd.toFixed(1)}`], { "font-size": 11.5, fill: colour, "font-weight": 700 }));

  const lg = s("g", { transform: `translate(${pl + pw - 170}, ${pt + 10})` });
  lg.append(s("rect", { x: -8, y: -12, width: 172, height: 58, rx: 6, fill: PAPER, "fill-opacity": 0.94, stroke: RULE }));
  lg.append(s("line", { x1: 0, y1: 0, x2: 18, y2: 0, stroke: ACCENT, "stroke-width": 2.2 }));
  lg.append(text(24, 4, "Capacity, As,prov", { "font-size": 11 }));
  lg.append(s("circle", { cx: 9, cy: 17, r: 5, fill: colour, stroke: PAPER, "stroke-width": 1.5 }));
  lg.append(text(24, 21, "Design point (MEd, NEd)", { "font-size": 11 }));
  lg.append(s("circle", { cx: 9, cy: 34, r: 4, fill: PAPER, stroke: MUTED, "stroke-width": 1.5 }));
  lg.append(text(24, 38, "First order (M02, NEd)", { "font-size": 11 }));
  svg.append(lg);
  target.replaceChildren(svg);
  return svg;
}

/** Kind of end restraint for drawing, from the form's restraint description. */
export function endKinds(r) {
  if (!r) return { top: "partial", bottom: "partial" };
  if (r.method === "factor") {
    const map = { a: ["pinned", "pinned"], b: ["free", "fixed"], c: ["pinned", "fixed"], d: ["fixed", "fixed"], e: ["sway", "fixed"] };
    const [top, bottom] = map[r.case] || ["partial", "partial"];
    return { top, bottom };
  }
  const kind = (k) => (k === "pinned" || k === null ? "pinned" : Number(k) <= 0.1 ? "fixed" : "partial");
  const lab = (k) => (k === "pinned" || k === null ? null : Number(k) <= 0.1 ? null : `k = ${Number(k).toFixed(2)}`);
  return { top: kind(r.k_top), bottom: kind(r.k_bottom), kTop: lab(r.k_top), kBottom: lab(r.k_bottom) };
}

// ------------------------------------------------------------------ beams

/** Outline of a beam section in mm (origin at the bottom of the web centre line, y up). */
function beamOutline(sec, flangeHalf) {
  const { b, h } = sec;
  if (sec.shape !== "flanged") return [[-b / 2, 0], [b / 2, 0], [b / 2, h], [-b / 2, h]];
  const hf = sec.hf;
  if (sec.flange === "T") {
    return [[-b / 2, 0], [b / 2, 0], [b / 2, h - hf], [flangeHalf, h - hf], [flangeHalf, h], [-flangeHalf, h],
      [-flangeHalf, h - hf], [-b / 2, h - hf]];
  }
  return [[-b / 2, 0], [b / 2, 0], [b / 2, h - hf], [b / 2 + 2 * flangeHalf - b, h - hf],
    [b / 2 + 2 * flangeHalf - b, h], [-b / 2, h]];
}

/**
 * A beam section laid out as the server does it: bottom and top bars, each in one or two
 * layers. Also returns the steel area, effective depth and clear bar gap of each face.
 */
export function beamSectionFromInputs({ shape, flange, b, h, hf, beff, cover, link_dia, legs, bottom_n, bottom_dia,
  bottom_layers = 1, top_n, top_dia, top_layers = 1, dg = 20 }) {
  const ok = (x) => Number.isFinite(x) && x > 0;
  if (!ok(b) || !ok(h) || !(cover >= 0) || !(bottom_n >= 1) || !(top_n >= 1)) return null;
  const flanged = shape === "flanged" && ok(hf) && hf < h;
  const face = cover + link_dia;
  const width = b - 2 * face;
  const bars = [];
  const stats = {};
  for (const [name, n, dia, layers, at] of [["bottom", bottom_n, bottom_dia, bottom_layers, (d) => d],
    ["top", top_n, top_dia, top_layers, (d) => h - d]]) {
    const count = Math.round(n);
    const perLayer = Math.ceil(count / layers);
    const second = count - perLayer;
    const a1 = face + dia / 2;
    const a2 = a1 + dia + Math.max(dia, dg + 5, 20);
    const lo = -b / 2 + face + dia / 2;
    bars.push(...spread(lo, -lo, perLayer).map((x) => ({ x, y: at(a1), dia, kind: name })));
    if (second) bars.push(...spread(lo, -lo, second).map((x) => ({ x, y: at(a2), dia, kind: name })));
    stats[name] = {
      As: (count * Math.PI * dia ** 2) / 4,
      d: h - (perLayer * a1 + second * a2) / count,
      clear: perLayer > 1 ? (width - dia) / (perLayer - 1) - dia : width - dia,
    };
  }
  return {
    shape: flanged ? "flanged" : "rectangular", flange, b, h, hf, beff: flanged ? Math.max(beff || b, b) : b, cover,
    link_dia, legs, bars, stats,
  };
}

/**
 * Beam cross-section to scale. Wide flanges are drawn cut short with break marks;
 * the dimension still gives the full effective width.
 */
export function drawBeamSection(target, sec, opts = {}) {
  const W = opts.width || 420;
  const H = opts.height || 360;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Beam cross-section" });
  if (!sec || !(sec.b > 0 && sec.h > 0)) {
    svg.append(text(W / 2, H / 2, "Section dimensions incomplete", { "text-anchor": "middle", fill: MUTED }));
    target.replaceChildren(svg);
    return svg;
  }
  const id = `conc${++uid}`;
  svg.append(s("defs", {}, concretePattern(id)));
  const flanged = sec.shape === "flanged" && sec.hf > 0 && sec.beff > sec.b;
  const fullHalf = flanged ? (sec.flange === "T" ? sec.beff / 2 : (sec.beff + sec.b) / 4) : sec.b / 2;
  const half = flanged ? Math.min(fullHalf, sec.b * 1.6) : sec.b / 2;
  const cut = flanged && half < fullHalf;
  const pts = beamOutline(sec, half);
  const xs = pts.map((p) => p[0]);
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const padL = 64, padR = 84, padT = flanged ? 54 : 40, padB = 58;
  const scale = Math.min((W - padL - padR) / (xMax - xMin), (H - padT - padB) / sec.h);
  const x0 = padL + (W - padL - padR - (xMax - xMin) * scale) / 2 - xMin * scale;
  const yBase = H - padB;
  const X = (x) => x0 + x * scale;
  const Y = (y) => yBase - y * scale;
  const status = opts.status || {};
  const cls = (part) => `part ${part}${status[part] === "fail" ? " is-fail" : ""}`;

  svg.append(s("polygon", { points: pts.map(([x, y]) => `${X(x)},${Y(y)}`).join(" "), fill: `url(#${id})`,
    stroke: INK, "stroke-width": 1.8, "stroke-linejoin": "round", class: cls("section"), "data-part": "section" }));
  if (cut) {
    for (const side of sec.flange === "T" ? [-1, 1] : [1]) {
      const xe = side < 0 ? X(xMin) : X(xMax);
      const yt = Y(sec.h), yb = Y(sec.h - sec.hf);
      const m = (yt + yb) / 2;
      svg.append(s("path", { d: `M${xe} ${yt - 6} L${xe} ${m - 4} L${xe - 5 * side} ${m} L${xe + 5 * side} ${m + 3} L${xe} ${m + 7} L${xe} ${yb + 6}`,
        fill: "none", stroke: PAPER, "stroke-width": 5 }));
      svg.append(s("path", { d: `M${xe} ${yt - 6} L${xe} ${m - 4} L${xe - 5 * side} ${m} L${xe + 5 * side} ${m + 3} L${xe} ${m + 7} L${xe} ${yb + 6}`,
        fill: "none", stroke: INK, "stroke-width": 1 }));
    }
  }

  const c = sec.cover + sec.link_dia / 2;
  const r = Math.max(2.5 * sec.link_dia * scale, 4);
  svg.append(s("rect", { x: X(-sec.b / 2 + c), y: Y(sec.h - c), width: (sec.b - 2 * c) * scale, height: (sec.h - 2 * c) * scale,
    rx: r, ry: r, fill: "none", stroke: ACCENT, "stroke-width": Math.max(sec.link_dia * scale, 1.6),
    class: cls("links"), "data-part": "links" }));
  const legs = Number(sec.legs) || 2;
  const inner = s("g", { class: cls("links"), "data-part": "links" });
  for (let i = 1; i < legs - 1; i++) {
    const x = -sec.b / 2 + c + ((sec.b - 2 * c) * i) / (legs - 1);
    inner.append(s("line", { x1: X(x), y1: Y(sec.h - c), x2: X(x), y2: Y(c), stroke: ACCENT, "stroke-width": Math.max(sec.link_dia * scale, 1.4) }));
  }
  svg.append(inner);
  const bars = s("g", { class: cls("bars"), "data-part": "bars" });
  for (const bar of sec.bars || []) {
    bars.append(s("circle", { cx: X(bar.x), cy: Y(bar.y), r: Math.max((bar.dia / 2) * scale, 2.4), fill: STEEL }));
  }
  svg.append(bars);

  svg.append(dimH(X(-sec.b / 2), X(sec.b / 2), yBase + 30, `${flanged ? "bw" : "b"} = ${sec.b}`, yBase));
  svg.append(dimV(Y(sec.h), yBase, X(xMin) - 30, `h = ${sec.h}`, X(xMin)));
  if (flanged) {
    svg.append(dimH(X(xMin), X(xMax), Y(sec.h) - 24, `beff = ${Math.round(sec.beff)}${cut ? " (cut)" : ""}`, Y(sec.h)));
    svg.append(text(X(xMax) + 6, Y(sec.h - sec.hf / 2) + 4, `hf = ${sec.hf}`, { "font-size": 11, fill: MUTED }));
  }
  const label = (list, y, extra) => {
    if (!list.length) return;
    const xr = X(sec.b / 2) + 14;
    svg.append(s("line", { x1: X(list[list.length - 1].x) + 3, y1: Y(list[list.length - 1].y), x2: xr, y2: y, stroke: MUTED, "stroke-width": 0.7 }));
    svg.append(text(xr + 2, y + 4, `${list.length}H${list[0].dia}${extra}`, { "font-weight": 700, class: "num", "font-size": 11.5 }));
  };
  label((sec.bars || []).filter((b) => b.kind === "bottom"), yBase - 18, " bottom");
  label((sec.bars || []).filter((b) => b.kind === "top"), Y(sec.h) + 26, " top");
  svg.append(text(X(sec.b / 2) + 16, Y(sec.h / 2) + 4, opts.linkLabel || `H${sec.link_dia} links`, { fill: ACCENT, "font-weight": 700, "font-size": 11.5 }));
  const coverColour = status.cover === "fail" ? COLORS.fail : MUTED;
  svg.append(symText(X(sec.b / 2) + 16, yBase + 16, ["c", sub("nom"), ` = ${sec.cover} mm`], { fill: coverColour, "font-size": 11 }));
  target.replaceChildren(svg);
  return svg;
}
