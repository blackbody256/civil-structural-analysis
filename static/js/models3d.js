// 3D models of the elements for the viewport (viewer3d.js), built from the same inputs the forms send to the
// server. Units are metres, y is up. Each part carries a tag (what it is, for focusing on one input) and the
// check targets it stands for (so a failed check can light it up red in the report).
import { Geo } from "./viewer3d.js";
import { beamSectionFromInputs, sectionFromInputs } from "./drawings.js";

const C = {
  concrete: "#c3c9cf", edge: "#e9eef3", context: "#7d8893", bars: "#e8642c", links: "#f2c12e", ties: "#f2c12e",
  member: "#c3c9cf", chosen: "#3aa0ec", support: "#7cc142", G: "#9b5fc0", Q: "#ef476f", Ed: "#e8642c", load: "#ef476f",
  pressure: "#4dbeee", soil: "#9b7a4f", blinding: "#6f7780", blocks: "#c8743e", grid: "#8796a5", wall: "#8a939c",
};
const FACTOR = { G: 1.35, Q: 1.5, Ed: 1 };

const n = (v, d = 0) => (Number.isFinite(Number(v)) && v !== "" && v !== null ? Number(v) : d);
const fmt = (v, dp = 0) => Number(v).toFixed(dp);
const spread = (lo, hi, count) => (count <= 1 ? [(lo + hi) / 2] : Array.from({ length: count }, (_, i) => lo + ((hi - lo) * i) / (count - 1)));
const along = (lo, hi, step, max = 400) => {
  const out = [];
  if (!(step > 0) || hi <= lo) return out;
  const count = Math.min(max, Math.floor((hi - lo) / step) + 1);
  const start = lo + (hi - lo - (count - 1) * step) / 2;
  for (let i = 0; i < count; i++) out.push(start + i * step);
  return out;
};

function part(geo, o) { return { geo, ...o }; }

function grid(cx, cz, y, half, step) {
  const g = new Geo();
  const k = Math.ceil(half / step);
  for (let i = -k; i <= k; i++) {
    g.line([cx + i * step, y, cz - k * step], [cx + i * step, y, cz + k * step]);
    g.line([cx - k * step, y, cz + i * step], [cx + k * step, y, cz + i * step]);
  }
  return part(g, { tag: "grid", edge: C.grid, edgeAlpha: 0.22, anim: { type: "fade", delay: 0, dur: 0.6 } });
}

/** A curved arrow round `axis` (a moment), radius r, from angle a0 through `sweep`. */
function arcArrow(g, centre, axis, r, a0, sweep, tube) {
  const ref = Math.abs(axis[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0];
  const cr = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const nz = (a) => { const l = Math.hypot(...a); return a.map((x) => x / l); };
  const u = nz(cr(axis, ref)), w = cr(axis, u);
  const at = (t) => centre.map((c, i) => c + r * (Math.cos(t) * u[i] + Math.sin(t) * w[i]));
  const segs = 22;
  let prev = at(a0);
  for (let i = 1; i <= segs; i++) {
    const p = at(a0 + (sweep * i) / segs);
    if (i < segs) g.cylinder(prev, p, tube, 8, false);
    else {
      const tip = at(a0 + sweep * 1.08);
      g.cone(prev, tip, tube * 2.6, 12);
    }
    prev = p;
  }
}

function failOf(status, targets) { return Boolean(status && targets?.some((t) => status[t] === "fail")); }

// ------------------------------------------------------------------ column

function linkSpacing(b, h, phi) {
  const sMax = Math.min(12 * phi, 0.6 * Math.min(b, h), 240);
  return { near: Math.floor(sMax / 25) * 25, far: Math.floor((1.67 * sMax) / 25) * 25 };
}

export function columnScene(d, { status = null } = {}) {
  const g = d.geometry || {}, r = d.reinforcement || {}, a = d.actions || {};
  const b = n(g.b, 300), h = n(g.h, 300), L = Math.max(n(g.l, 3), 0.5);
  const B = b / 1000, H = h / 1000;
  const t = 0.2, hx = Math.max(B, H) * 1.15 + 0.25;
  const parts = [], labels = [];
  parts.push(grid(0, 0, -t - 0.001, hx + 0.6, 0.25));

  parts.push(part(new Geo().box(-hx, -t, -hx, hx, 0, hx), { tag: "context", color: C.context, alpha: 1, xray: 0.4, edge: C.edge,
    edgeAlpha: 0.45, anim: { type: "fade", delay: 0.05, dur: 0.5 } }));
  parts.push(part(new Geo().box(-B / 2, 0, -H / 2, B / 2, L, H / 2), { tag: "concrete", targets: ["section", "elevation", "cover"],
    color: C.concrete, alpha: 1, xray: 0.26, edge: C.edge, edgeAlpha: 0.85, shine: 0.08,
    anim: { type: "grow", axis: 1, anchor: [0, 0, 0], delay: 0.25, dur: 1.1 } }));
  parts.push(part(new Geo().box(-hx, L, -hx, hx, L + t, hx), { tag: "context", color: C.context, alpha: 1, xray: 0.36, edge: C.edge,
    edgeAlpha: 0.45, anim: { type: "drop", dist: 0.8, delay: 1.15, dur: 0.6 } }));

  const sec = sectionFromInputs({ b, h, cover: n(r.cover), link_dia: n(r.link_dia, 8), bar_dia: n(r.bar_dia, 16),
    n_b: Math.round(n(r.n_b, 2)), n_h: Math.round(n(r.n_h, 2)) });
  const barFail = failOf(status, ["bars"]), linkFail = failOf(status, ["links"]);
  if (sec) {
    sec.bars.forEach((bar, i) => {
      const x = bar.x / 1000, z = bar.y / 1000;
      parts.push(part(new Geo().cylinder([x, -t * 0.8, z], [x, L + t + 0.32, z], bar.dia / 2000, 12), {
        tag: "bars", targets: ["bars"], fail: barFail, color: C.bars, shine: 0.55, edgeAlpha: 0,
        anim: { type: "drop", dist: L * 0.7, delay: 1.35 + i * 0.06, dur: 0.6 },
      }));
    });
    const sp = linkSpacing(b, h, sec.bar_dia);
    const zone = Math.max(B, H);
    const c = (sec.cover + sec.link_dia / 2) / 1000, rl = sec.link_dia / 2000;
    const ys = [];
    for (let y = 0.05; y <= L - 0.04 && ys.length < 90;) {
      ys.push(y);
      y += (y < zone || y > L - zone ? sp.near : sp.far) / 1000;
    }
    const ring = [[-B / 2 + c, 0, -H / 2 + c], [B / 2 - c, 0, -H / 2 + c], [B / 2 - c, 0, H / 2 - c], [-B / 2 + c, 0, H / 2 - c]];
    const inner = sec.bars.filter((x) => !x.corner);
    ys.forEach((y, i) => {
      const gl = new Geo().loop(ring.map((p) => [p[0], y, p[2]]), rl, 6);
      if (r.cross_ties) {
        for (const bar of inner) {
          const x = bar.x / 1000, z = bar.y / 1000;
          if (Math.abs(Math.abs(z) - (H / 2 - c)) < 1e-6) gl.cylinder([x, y, -H / 2 + c], [x, y, H / 2 - c], rl, 6, false);
          else gl.cylinder([-B / 2 + c, y, z], [B / 2 - c, y, z], rl, 6, false);
        }
      }
      parts.push(part(gl, { tag: "links", targets: ["links"], fail: linkFail, color: C.links, shine: 0.4, edgeAlpha: 0,
        anim: { type: "pop", anchor: [0, y, 0], delay: 1.9 + i * 0.03, dur: 0.45 } }));
    });
    labels.push({ at: [B / 2, L * 0.62, H / 2], text: `${sec.bars.length}H${sec.bar_dia}`, tag: "bars", cls: "bars", delay: 2.2 });
    labels.push({ at: [-B / 2, L * 0.32, H / 2], text: `H${sec.link_dia} links @ ${sp.near}/${sp.far}`, tag: "links", cls: "links", delay: 2.6 });
  }

  const NEd = n(a.NEd, 0);
  const top = L + t;
  if (NEd > 0) {
    parts.push(part(new Geo().arrow([0, top + 1.15, 0], [0, top + 0.42, 0], 0.028), { tag: "loads", color: C.load, shine: 0.3,
      anim: { type: "drop", dist: 0.7, delay: 2.5, dur: 0.6 } }));
    labels.push({ at: [0, top + 1.22, 0], text: `NEd ${fmt(NEd)} kN`, tag: "loads", cls: "load", delay: 2.9 });
  }
  const moment = (key) => Math.max(Math.abs(n(a[`${key}_top`])), Math.abs(n(a[`${key}_bottom`])));
  const R = Math.max(B, H) * 0.75 + 0.12;
  if (moment("My") > 0) {
    const gm = new Geo();
    arcArrow(gm, [0, L * 0.88, 0], [1, 0, 0], R, -0.6, 2.2, 0.016);
    parts.push(part(gm, { tag: "loads", color: C.load, shine: 0.3, anim: { type: "pop", anchor: [0, L * 0.88, 0], delay: 2.75, dur: 0.5 } }));
    labels.push({ at: [0, L * 0.88 + R, R * 0.5], text: `My ${fmt(n(a.My_top))} / ${fmt(n(a.My_bottom))} kNm`, tag: "loads", cls: "load", delay: 3 });
  }
  if (a.bending === "biaxial" && moment("Mz") > 0) {
    const gm = new Geo();
    arcArrow(gm, [0, L * 0.72, 0], [0, 0, 1], R, 2.4, 2.2, 0.016);
    parts.push(part(gm, { tag: "loads", color: C.Q, shine: 0.3, anim: { type: "pop", anchor: [0, L * 0.72, 0], delay: 2.9, dur: 0.5 } }));
    labels.push({ at: [-R, L * 0.72, 0], text: `Mz ${fmt(n(a.Mz_top))} / ${fmt(n(a.Mz_bottom))} kNm`, tag: "loads", cls: "load", delay: 3.1 });
  }
  labels.unshift({ at: [B / 2, 0.02, H / 2], text: `${fmt(b)} × ${fmt(h)}`, tag: "concrete", delay: 1.4 },
    { at: [-B / 2, L / 2, -H / 2], text: `l ${fmt(L, 2)} m`, tag: "concrete", delay: 1.4 });
  return { parts, labels, view: { yaw: -0.72, pitch: 0.34 } };
}

// ------------------------------------------------------------------ plane frame (column page, analysis)

export function frameScene(frame, chosen) {
  const nodes = Object.fromEntries((frame?.nodes || []).map((p) => [p.id, [n(p.x), n(p.y), 0]]));
  const members = (frame?.members || []).filter((m) => nodes[m.node1] && nodes[m.node2]);
  const parts = [], labels = [];
  if (!members.length) return { parts, labels };
  const xs = Object.values(nodes).map((p) => p[0]), ys = Object.values(nodes).map((p) => p[1]);
  const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 1);
  const k = span / 12;
  const y0 = Math.min(...ys);
  parts.push(grid((Math.max(...xs) + Math.min(...xs)) / 2, 0, y0 - 0.3 * k - 0.001, span * 0.65, span > 20 ? 2 : 1));

  const vertical = (m) => Math.abs(nodes[m.node1][0] - nodes[m.node2][0]) < 1e-6;
  const sorted = [...members].sort((p, q) => (vertical(q) - vertical(p)) || (nodes[p.node1][0] - nodes[q.node1][0]));
  sorted.forEach((m, i) => {
    let p0 = nodes[m.node1], p1 = nodes[m.node2];
    if (vertical(m) && p0[1] > p1[1]) [p0, p1] = [p1, p0];
    const isChosen = m.id === chosen;
    const geo = new Geo().member(p0, p1, n(m.b, 300) / 1000, n(m.h, 300) / 1000);
    const axis = vertical(m) ? 1 : 0;
    parts.push(part(geo, {
      tag: isChosen ? "chosen" : "members", color: isChosen ? C.chosen : C.member, alpha: 1, xray: isChosen ? 1 : 0.85,
      edge: C.edge, edgeAlpha: 0.5, shine: isChosen ? 0.3 : 0.08,
      anim: { type: "grow", axis, anchor: axis === 1 ? p0 : (p0[0] < p1[0] ? p0 : p1), delay: 0.3 + i * 0.18, dur: 0.7 },
    }));
    const mid = p0.map((c, j) => (c + p1[j]) / 2);
    labels.push({ at: vertical(m) ? [mid[0] + 0.25, mid[1], 0.2] : [mid[0], mid[1] - n(m.h, 300) / 2000 - 0.2, 0.2],
      text: isChosen ? `${m.id} · designed` : m.id, cls: isChosen ? "chosen" : "", delay: 0.8 + i * 0.18 });
  });
  const tMembers = 0.3 + sorted.length * 0.18 + 0.4;

  (frame.supports || []).forEach((s, i) => {
    const p = nodes[s.node];
    if (!p) return;
    const g = new Geo();
    const z = 0.45 * k + 0.2;
    if (s.type === "fixed") g.box(p[0] - 0.45 * k - 0.15, p[1] - 0.3 * k, -z, p[0] + 0.45 * k + 0.15, p[1], z);
    else if (s.type === "roller") {
      g.cylinder([p[0], p[1] - 0.11 * k, -z], [p[0], p[1] - 0.11 * k, z], 0.11 * k, 14);
      g.box(p[0] - 0.35 * k, p[1] - 0.3 * k, -z, p[0] + 0.35 * k, p[1] - 0.22 * k, z);
    } else g.cone([p[0], p[1] - 0.3 * k, 0], [p[0], p[1], 0], 0.32 * k, 4);
    parts.push(part(g, { tag: "supports", color: C.support, shine: 0.2, edge: "#24400f", edgeAlpha: 0.6,
      anim: { type: "pop", anchor: p, delay: 0.1 + i * 0.08, dur: 0.5 } }));
  });

  // loads: factored, drawn to one scale
  const loads = frame.loads || [];
  const wOf = (ld) => n(ld.w) * (FACTOR[ld.case] ?? 1);
  const wMax = Math.max(1e-9, ...loads.filter((l) => l.type === "udl").map(wOf));
  const perMember = {};
  loads.forEach((ld, i) => {
    const delay = tMembers + i * 0.15;
    const colour = C[ld.case] || C.load;
    if (ld.type === "udl") {
      const m = members.find((x) => x.id === ld.member);
      if (!m || vertical(m)) return;
      const [p0, p1] = [nodes[m.node1], nodes[m.node2]].sort((a, b) => a[0] - b[0]);
      const base = Math.max(p0[1], p1[1]) + n(m.h, 300) / 2000 + 0.45 * k + (perMember[m.id] || 0);
      const hh = (0.25 + 0.9 * (wOf(ld) / wMax)) * k;
      perMember[m.id] = (perMember[m.id] || 0) + hh + 0.05 * k;
      const z = n(m.b, 300) / 2000 + 0.05;
      const g = new Geo().box(p0[0], base, -z, p1[0], base + hh, z);
      parts.push(part(g, { tag: "loads", color: colour, alpha: 0.42, edge: colour, edgeAlpha: 0.9,
        anim: { type: "drop", dist: 1.2 * k, delay, dur: 0.55 } }));
      labels.push({ at: [(p0[0] + p1[0]) / 2, base + hh + 0.12 * k, 0], text: `${ld.case} ${fmt(n(ld.w), 1)} kN/m`, tag: "loads", cls: `load case-${ld.case}`, delay: delay + 0.4 });
      if (!perMember[`${m.id}-arrows`]) {
        perMember[`${m.id}-arrows`] = true;
        const ga = new Geo();
        const top = Math.max(p0[1], p1[1]) + n(m.h, 300) / 2000;
        for (const x of along(p0[0] + 0.25, p1[0] - 0.25, Math.max((p1[0] - p0[0]) / 9, 0.3))) ga.arrow([x, top + 0.42 * k, 0], [x, top + 0.02, 0], 0.012 * k + 0.004, 3);
        parts.push(part(ga, { tag: "loads", color: colour, shine: 0.2, anim: { type: "drop", dist: 0.8 * k, delay, dur: 0.5 } }));
      }
    } else if (ld.type === "point") {
      const m = members.find((x) => x.id === ld.member);
      if (!m) return;
      const p0 = nodes[m.node1], p1 = nodes[m.node2];
      const len = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]) || 1;
      const t = Math.max(0, Math.min(1, n(ld.a) / len));
      const p = [p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t + n(m.h, 300) / 2000, 0];
      parts.push(part(new Geo().arrow([p[0], p[1] + 1.6 * k, 0], [p[0], p[1] + 0.02, 0], 0.03 * k, 3), { tag: "loads", color: colour,
        anim: { type: "drop", dist: k, delay, dur: 0.5 } }));
      labels.push({ at: [p[0], p[1] + 1.7 * k, 0], text: `${ld.case} ${fmt(n(ld.P), 1)} kN`, tag: "loads", cls: `load case-${ld.case}`, delay: delay + 0.4 });
    } else if (ld.type === "node") {
      const p = nodes[ld.node];
      if (!p) return;
      const g = new Geo();
      const fx = n(ld.fx), fy = n(ld.fy), mz = n(ld.mz);
      if (fx) g.arrow([p[0] - Math.sign(fx) * 1.6 * k, p[1], 0], [p[0] - Math.sign(fx) * 0.25 * k, p[1], 0], 0.03 * k, 3);
      if (fy) g.arrow([p[0], p[1] + Math.sign(fy) * 1.6 * k, 0], [p[0], p[1] + Math.sign(fy) * 0.3 * k, 0], 0.03 * k, 3);
      if (mz) arcArrow(g, p, [0, 0, 1], 0.7 * k, 0.4, Math.sign(mz) * 2.4, 0.02 * k);
      parts.push(part(g, { tag: "loads", color: colour, anim: { type: "drop", dir: [fx ? -Math.sign(fx) : 0, fx ? 0 : 1, 0], dist: k, delay, dur: 0.5 } }));
      const text = [fx && `fx ${fmt(fx, 1)}`, fy && `fy ${fmt(fy, 1)}`, mz && `mz ${fmt(mz, 1)}`].filter(Boolean).join(", ");
      if (text) labels.push({ at: [p[0] - (fx ? Math.sign(fx) * 1.7 * k : 0), p[1] + (fx ? 0.2 * k : 1.7 * k), 0], text: `${ld.case} ${text}`, tag: "loads", cls: `load case-${ld.case}`, delay: delay + 0.4 });
    }
  });
  return { parts, labels, view: { yaw: -0.38, pitch: 0.22, refit: true } };
}

// ------------------------------------------------------------------ beam

function supportsAlong(parts, supports, y, zHalf, k, length) {
  (supports || []).forEach((s, i) => {
    const x = n(s.x);
    const g = new Geo();
    if (s.type === "fixed") {
      const side = x <= length / 2 ? -1 : 1;
      g.box(Math.min(x, x + side * 0.35 * k), y - 0.9 * k, -zHalf - 0.25 * k, Math.max(x, x + side * 0.35 * k), y + 1.6 * k, zHalf + 0.25 * k);
    } else if (s.type === "roller") {
      g.cylinder([x, y - 0.1 * k, -zHalf], [x, y - 0.1 * k, zHalf], 0.1 * k, 16);
      g.box(x - 0.24 * k, y - 0.3 * k, -zHalf, x + 0.24 * k, y - 0.2 * k, zHalf);
    } else {
      g.wedge(x, y, 0.2 * k, 0.3 * k, -zHalf, zHalf);
    }
    parts.push(part(g, { tag: "supports", color: s.type === "fixed" ? C.wall : C.support, shine: 0.2, edge: "#1f3010", edgeAlpha: 0.6,
      anim: { type: "pop", anchor: [x, y, 0], delay: 0.1 + i * 0.08, dur: 0.5 } }));
  });
}

function loadStack(parts, labels, loads, length, top, zHalf, k, t0) {
  const udl = (loads || []).filter((l) => l.type === "udl");
  const wOf = (ld) => n(ld.w) * (FACTOR[ld.case] ?? 1);
  const wMax = Math.max(1e-9, ...udl.map(wOf));
  const gap = 0.45 * k;
  let stack = top + gap;
  udl.forEach((ld, i) => {
    const x1 = Math.max(0, n(ld.x1)), x2 = Math.min(length, n(ld.x2, length));
    if (x2 <= x1) return;
    const hh = (0.18 + 0.55 * (wOf(ld) / wMax)) * k;
    const colour = C[ld.case] || C.load;
    parts.push(part(new Geo().box(x1, stack, -zHalf, x2, stack + hh, zHalf), { tag: "loads", color: colour, alpha: 0.42, edge: colour,
      edgeAlpha: 0.9, anim: { type: "drop", dist: 1.5 * k, delay: t0 + i * 0.18, dur: 0.55 } }));
    labels.push({ at: [(x1 + x2) / 2, stack + hh + 0.06 * k, zHalf], text: `${ld.case} ${fmt(n(ld.w), 1)} kN/m`, tag: "loads", cls: `load case-${ld.case}`, delay: t0 + 0.5 + i * 0.18 });
    stack += hh + 0.06 * k;
  });
  if (udl.length) {
    const ga = new Geo();
    const x1 = Math.min(...udl.map((l) => Math.max(0, n(l.x1)))), x2 = Math.max(...udl.map((l) => Math.min(length, n(l.x2, length))));
    for (const x of along(x1 + 0.1, x2 - 0.1, Math.max((x2 - x1) / 24, 0.25))) ga.arrow([x, top + gap - 0.01, 0], [x, top + 0.01, 0], 0.012 * k, 3);
    parts.push(part(ga, { tag: "loads", color: C.load, shine: 0.2, anim: { type: "drop", dist: 0.8 * k, delay: t0, dur: 0.5 } }));
  }
  (loads || []).filter((l) => l.type === "point").forEach((ld, i) => {
    const x = Math.max(0, Math.min(length, n(ld.x)));
    const colour = C[ld.case] || C.load;
    parts.push(part(new Geo().arrow([x, stack + 0.9 * k, 0], [x, top + 0.01, 0], 0.035 * k, 3), { tag: "loads", color: colour, shine: 0.3,
      anim: { type: "drop", dist: 1.2 * k, delay: t0 + 0.4 + i * 0.15, dur: 0.55 } }));
    labels.push({ at: [x, stack + 1.0 * k, 0], text: `${ld.case} ${fmt(n(ld.W), 1)} kN`, tag: "loads", cls: `load case-${ld.case}`, delay: t0 + 0.9 });
  });
}

export function beamScene(d, { status = null, beff = null, links = null } = {}) {
  const s = d.section || {}, r = d.reinforcement || {}, sp = d.span || {}, a = d.actions || {};
  const L = Math.max(n(sp.l, 6), 0.5);
  const sec = beamSectionFromInputs({ ...s, ...r, b: n(s.b), h: n(s.h), hf: n(s.hf), cover: n(r.cover), link_dia: n(r.link_dia, 8),
    legs: n(r.legs, 2), bottom_n: n(r.bottom_n), bottom_dia: n(r.bottom_dia), bottom_layers: n(r.bottom_layers, 1),
    top_n: n(r.top_n), top_dia: n(r.top_dia), top_layers: n(r.top_layers, 1), beff: n(beff ?? s.beff, n(s.b)), dg: n(d.materials?.dg, 20) });
  const parts = [], labels = [];
  if (!sec) return { parts, labels };
  const b = sec.b / 1000, h = sec.h / 1000, hf = n(sec.hf) / 1000, bf = sec.beff / 1000;
  const k = Math.max(h, 0.35) / 0.6;
  parts.push(grid(L / 2, 0, -0.32 * k - 0.001, L * 0.6, L > 12 ? 1 : 0.5));
  const conc = { tag: "concrete", targets: ["section", "cover"], color: C.concrete, alpha: 1, xray: 0.26, edge: C.edge, edgeAlpha: 0.7, shine: 0.08 };
  const flanged = sec.shape === "flanged";
  parts.push(part(new Geo().box(0, 0, -b / 2, L, flanged ? h - hf : h, b / 2), { ...conc, anim: { type: "grow", axis: 0, anchor: [0, 0, 0], delay: 0.3, dur: 1.1 } }));
  let zHalf = b / 2;
  if (flanged) {
    const z0 = sec.flange === "T" ? -bf / 2 : -b / 2, z1 = sec.flange === "T" ? bf / 2 : bf - b / 2;
    zHalf = Math.max(Math.abs(z0), Math.abs(z1));
    parts.push(part(new Geo().box(0, h - hf, z0, L, h, z1), { ...conc, tag: "flange", anim: { type: "grow", axis: 0, anchor: [0, 0, 0], delay: 0.55, dur: 1.1 } }));
  }
  supportsAlong(parts, sp.supports, 0, zHalf + 0.05, k, L);

  const barFail = failOf(status, ["bars"]), linkFail = failOf(status, ["links"]);
  sec.bars.forEach((bar, i) => {
    const y = bar.y / 1000, z = bar.x / 1000;
    parts.push(part(new Geo().cylinder([0.03, y, z], [L - 0.03, y, z], bar.dia / 2000, 12), { tag: "bars", targets: ["bars"], fail: barFail,
      color: C.bars, shine: 0.55, edgeAlpha: 0, anim: { type: "drop", dir: [-1, 0, 0], dist: L * 0.6, delay: 1.3 + i * 0.07, dur: 0.7 } }));
  });
  const c = (sec.cover + sec.link_dia / 2) / 1000, rl = sec.link_dia / 2000;
  const dEff = sec.stats.bottom.d;
  const step = (links?.near ?? Math.max(75, Math.floor(Math.min(0.75 * dEff, 600) / 25) * 25)) / 1000;
  const legs = Math.max(2, Math.round(n(sec.legs, 2)));
  const zs = spread(-b / 2 + c, b / 2 - c, legs);
  along(0.05, L - 0.05, step, 160).forEach((x, i) => {
    const g = new Geo().loop([[x, c, -b / 2 + c], [x, c, b / 2 - c], [x, h - c, b / 2 - c], [x, h - c, -b / 2 + c]], rl, 6);
    for (const z of zs.slice(1, -1)) g.cylinder([x, c, z], [x, h - c, z], rl, 6, false);
    parts.push(part(g, { tag: "links", targets: ["links"], fail: linkFail, color: C.links, shine: 0.4, edgeAlpha: 0,
      anim: { type: "pop", anchor: [x, h / 2, 0], delay: 2 + i * 0.022, dur: 0.4 } }));
  });
  if (a.mode !== "direct") loadStack(parts, labels, a.loads, L, h, zHalf, k, 2.6);

  const xsS = (sp.supports || []).map((x) => n(x.x)).sort((p, q) => p - q);
  xsS.slice(1).forEach((x, i) => labels.push({ at: [(x + xsS[i]) / 2, -0.38 * k, zHalf], text: `${fmt(x - xsS[i], 2)} m`, tag: "supports", delay: 1.2 }));
  const bottom = sec.bars.filter((x) => x.kind === "bottom"), topBars = sec.bars.filter((x) => x.kind === "top");
  if (bottom.length) labels.push({ at: [L * 0.3, bottom[0].y / 1000, b / 2], text: `${bottom.length}H${bottom[0].dia} bottom`, tag: "bars", cls: "bars", delay: 2.1 });
  if (topBars.length) labels.push({ at: [L * 0.7, topBars[0].y / 1000, b / 2], text: `${topBars.length}H${topBars[0].dia} top`, tag: "bars", cls: "bars", delay: 2.2 });
  labels.push({ at: [0, h / 2, zHalf], text: `${fmt(sec.b)} × ${fmt(sec.h)}${flanged ? `, beff ${fmt(sec.beff)}` : ""}`, tag: "concrete", delay: 1.4 });
  return { parts, labels, view: { yaw: -1.0, pitch: 0.26 } };
}

// ------------------------------------------------------------------ slabs

const MESH = { A142: [6, 200], A193: [7, 200], A252: [8, 200], A393: [10, 200] };

function barsPart(geo, targets, status, delay, dir) {
  return part(geo, { tag: "bars", targets, fail: failOf(status, targets), color: C.bars, shine: 0.5, edgeAlpha: 0,
    anim: { type: "drop", dir, dist: 1.4, delay, dur: 0.75 } });
}

function wallsUnder(parts, supports, z0, z1, k) {
  (supports || []).forEach((s, i) => {
    const x = n(s.x);
    parts.push(part(new Geo().box(x - 0.1, -1.6 * k, z0, x + 0.1, 0, z1), { tag: "supports", color: C.wall, alpha: 1, xray: 0.55,
      edge: C.edge, edgeAlpha: 0.35, anim: { type: "grow", axis: 1, anchor: [x, 0, 0], delay: 0.05 + i * 0.1, dur: 0.6 } }));
  });
}

function oneWayScene(d, status) {
  const sl = d.slab || {}, r = d.reinforcement || {}, sp = d.span || {};
  const L = Math.max(n(sp.l, 5), 0.5), h = n(sl.h, 200) / 1000, W = Math.min(4, Math.max(2.4, L * 0.32));
  const parts = [], labels = [];
  parts.push(grid(L / 2, 0, -1.6 - 0.001, L * 0.62, 0.5));
  wallsUnder(parts, sp.supports, -W / 2, W / 2, 1);
  parts.push(part(new Geo().box(0, 0, -W / 2, L, h, W / 2), { tag: "concrete", targets: ["h", "slab.h", "cover", "section"], color: C.concrete,
    alpha: 1, xray: 0.24, edge: C.edge, edgeAlpha: 0.7, anim: { type: "grow", axis: 0, anchor: [0, 0, 0], delay: 0.4, dur: 1 } }));
  const cover = n(r.cover, 25) / 1000;
  const bx = n(r.bottom_x_dia, 10) / 1000, by = r.bottom_y_dia === "none" ? 0 : n(r.bottom_y_dia, 8) / 1000;
  const gb = new Geo();
  for (const z of along(-W / 2 + 0.05, W / 2 - 0.05, n(r.bottom_x_s, 200) / 1000)) gb.cylinder([0.03, cover + bx / 2, z], [L - 0.03, cover + bx / 2, z], bx / 2, 8);
  parts.push(barsPart(gb, ["reinforcement.bottom_x_dia", "reinforcement.bottom_x_s"], status, 1.3, [-1, 0, 0]));
  if (by) {
    const gd = new Geo();
    for (const x of along(0.05, L - 0.05, n(r.bottom_y_s, 250) / 1000)) gd.cylinder([x, cover + bx + by / 2, -W / 2 + 0.03], [x, cover + bx + by / 2, W / 2 - 0.03], by / 2, 8);
    parts.push(barsPart(gd, ["reinforcement.bottom_y_s", "reinforcement.bottom_y_dia"], status, 1.7, [0, 0, 1]));
  }
  const tx = r.top_x_dia === "none" ? 0 : n(r.top_x_dia) / 1000;
  if (tx) {
    const xs = (sp.supports || []).map((s) => n(s.x)).sort((p, q) => p - q);
    const inner = xs.slice(1, -1);
    const spanLen = xs.length > 1 ? (xs[xs.length - 1] - xs[0]) / (xs.length - 1) : L;
    const runs = inner.length ? inner.map((x) => [Math.max(0, x - 0.3 * spanLen), Math.min(L, x + 0.3 * spanLen)]) : [[0.03, L - 0.03]];
    const gt = new Geo();
    for (const [x1, x2] of runs) for (const z of along(-W / 2 + 0.05, W / 2 - 0.05, n(r.top_x_s, 200) / 1000)) gt.cylinder([x1, h - cover - tx / 2, z], [x2, h - cover - tx / 2, z], tx / 2, 8);
    parts.push(barsPart(gt, ["reinforcement.top_x_s", "reinforcement.top_x_dia"], status, 2.1, [0, 1, 0]));
    labels.push({ at: [runs[0][0], h, W / 2], text: `H${fmt(tx * 1000)} @ ${fmt(n(r.top_x_s))} top`, tag: "bars", cls: "bars", delay: 2.5 });
  }
  labels.push({ at: [L * 0.25, cover, W / 2], text: `H${fmt(bx * 1000)} @ ${fmt(n(r.bottom_x_s))} bottom`, tag: "bars", cls: "bars", delay: 2.2 });
  labels.push({ at: [0, h, -W / 2], text: `h ${fmt(h * 1000)}`, tag: "concrete", delay: 1.4 });
  const xs = (sp.supports || []).map((s) => n(s.x)).sort((p, q) => p - q);
  xs.slice(1).forEach((x, i) => labels.push({ at: [(x + xs[i]) / 2, -0.05, W / 2], text: `${fmt(x - xs[i], 2)} m`, tag: "supports", delay: 1.1 }));
  return { parts, labels, view: { yaw: -0.9, pitch: 0.4 } };
}

function twoWayScene(d, status) {
  const sl = d.slab || {}, r = d.reinforcement || {}, p = d.panel || {};
  const lx = Math.max(n(p.lx, 4), 0.5), ly = Math.max(n(p.ly, 5), 0.5), h = n(sl.h, 200) / 1000;
  const edges = p.edges || {};
  const parts = [], labels = [];
  parts.push(grid(0, 0, -2.6 - 0.001, Math.max(lx, ly) * 0.85, 0.5));
  const X = ly / 2, Z = lx / 2;
  parts.push(part(new Geo().box(-X, 0, -Z, X, h, Z), { tag: "concrete", targets: ["h", "slab.h", "cover", "section"], color: C.concrete,
    alpha: 1, xray: 0.24, edge: C.edge, edgeAlpha: 0.7, anim: { type: "pop", anchor: [0, 0, 0], delay: 0.5, dur: 0.8 } }));
  const beam = 0.3, dn = 0.45;
  const edgeBox = {
    top: [-X - beam / 2, -Z - beam / 2, X + beam / 2, -Z + beam / 2], bottom: [-X - beam / 2, Z - beam / 2, X + beam / 2, Z + beam / 2],
    left: [-X - beam / 2, -Z - beam / 2, -X + beam / 2, Z + beam / 2], right: [X - beam / 2, -Z - beam / 2, X + beam / 2, Z + beam / 2],
  };
  const stub = 1.2;
  const stubBox = {
    top: [-X, -Z - stub, X, -Z], bottom: [-X, Z, X, Z + stub], left: [-X - stub, -Z, -X, Z], right: [X, -Z, X + stub, Z],
  };
  Object.entries(edgeBox).forEach(([name, [x0, z0, x1, z1]], i) => {
    parts.push(part(new Geo().box(x0, -dn, z0, x1, 0, z1), { tag: "supports", color: C.wall, alpha: 1, xray: 0.55, edge: C.edge, edgeAlpha: 0.35,
      anim: { type: "grow", axis: name === "left" || name === "right" ? 2 : 0, delay: 0.1 + i * 0.08, dur: 0.6 } }));
    if (edges[name] === "continuous") {
      const [a0, b0, a1, b1] = stubBox[name];
      parts.push(part(new Geo().box(a0, 0, b0, a1, h, b1), { tag: "context", color: C.context, alpha: 0.5, xray: 0.22, edge: C.edge, edgeAlpha: 0.3,
        anim: { type: "fade", delay: 1.1 + i * 0.1, dur: 0.5 } }));
    }
    const mid = { top: [0, h, -Z], bottom: [0, h, Z], left: [-X, h, 0], right: [X, h, 0] }[name];
    labels.push({ at: mid, text: edges[name] === "continuous" ? "continuous" : "discontinuous", tag: "supports", cls: edges[name] === "continuous" ? "" : "muted", delay: 1.5 });
  });
  for (const [x, z] of [[-X, -Z], [X, -Z], [X, Z], [-X, Z]]) {
    parts.push(part(new Geo().box(x - 0.15, -2.6, z - 0.15, x + 0.15, -dn, z + 0.15), { tag: "context", color: C.wall, alpha: 1, xray: 0.5,
      edge: C.edge, edgeAlpha: 0.3, anim: { type: "grow", axis: 1, anchor: [x, -dn, z], delay: 0, dur: 0.5 } }));
  }
  const cover = n(r.cover, 25) / 1000;
  const bx = n(r.bottom_x_dia, 10) / 1000, by = n(r.bottom_y_dia, 10) / 1000;
  const g1 = new Geo();
  for (const x of along(-X + 0.05, X - 0.05, n(r.bottom_x_s, 200) / 1000)) g1.cylinder([x, cover + bx / 2, -Z + 0.03], [x, cover + bx / 2, Z - 0.03], bx / 2, 8);
  parts.push(barsPart(g1, ["reinforcement.bottom_x_dia", "reinforcement.bottom_x_s"], status, 1.4, [0, 0, -1]));
  const g2 = new Geo();
  for (const z of along(-Z + 0.05, Z - 0.05, n(r.bottom_y_s, 200) / 1000)) g2.cylinder([-X + 0.03, cover + bx + by / 2, z], [X - 0.03, cover + bx + by / 2, z], by / 2, 8);
  parts.push(barsPart(g2, ["reinforcement.bottom_y_dia", "reinforcement.bottom_y_s"], status, 1.8, [1, 0, 0]));
  const tx = r.top_x_dia === "none" ? 0 : n(r.top_x_dia) / 1000, ty = r.top_y_dia === "none" ? 0 : n(r.top_y_dia) / 1000;
  const gt = new Geo();
  const reach = 0.25 * lx;
  if (tx) {
    for (const name of ["top", "bottom"]) {
      if (edges[name] !== "continuous") continue;
      const z = name === "top" ? -Z : Z, dir = name === "top" ? 1 : -1;
      for (const x of along(-X + 0.05, X - 0.05, n(r.top_x_s, 200) / 1000)) gt.cylinder([x, h - cover - tx / 2, z - dir * reach * 0.6], [x, h - cover - tx / 2, z + dir * reach], tx / 2, 8);
    }
  }
  if (ty) {
    for (const name of ["left", "right"]) {
      if (edges[name] !== "continuous") continue;
      const x = name === "left" ? -X : X, dir = name === "left" ? 1 : -1;
      for (const z of along(-Z + 0.05, Z - 0.05, n(r.top_y_s, 200) / 1000)) gt.cylinder([x - dir * reach * 0.6, h - cover - tx - ty / 2, z], [x + dir * reach, h - cover - tx - ty / 2, z], ty / 2, 8);
    }
  }
  if (gt.v.length) parts.push(barsPart(gt, ["reinforcement.top_x_s", "reinforcement.top_x_dia", "reinforcement.top_y_s"], status, 2.2, [0, 1, 0]));
  labels.push({ at: [0, 0, Z], text: `ly ${fmt(ly, 2)} m`, tag: "concrete", delay: 1.3 });
  labels.push({ at: [X, 0, 0], text: `lx ${fmt(lx, 2)} m`, tag: "concrete", delay: 1.3 });
  labels.push({ at: [-X * 0.4, cover, Z * 0.6], text: `H${fmt(bx * 1000)} @ ${fmt(n(r.bottom_x_s))} · H${fmt(by * 1000)} @ ${fmt(n(r.bottom_y_s))}`, tag: "bars", cls: "bars", delay: 2.4 });
  return { parts, labels, view: { yaw: -0.6, pitch: 0.55 } };
}

function ribbedScene(d, status, pan) {
  const sl = d.slab || {}, r = d.reinforcement || {}, sp = d.span || {};
  const L = Math.max(n(sp.l, 5), 0.5);
  const P = pan || { height: 150, width: 300, length: 300 };
  const ph = P.height / 1000, pw = P.width / 1000, plen = P.length / 1000;
  const bw = n(sl.bw, 125) / 1000, hf = n(sl.hf, 75) / 1000, pitch = bw + pw;
  const ribs = 4, W = (ribs - 1) * pitch + bw;
  const zr = (i) => -W / 2 + bw / 2 + i * pitch;
  const parts = [], labels = [];
  parts.push(grid(L / 2, 0, -1.6 - 0.001, L * 0.62, 0.5));
  wallsUnder(parts, sp.supports, -W / 2 - 0.1, W / 2 + 0.1, 1);
  const conc = { tag: "concrete", targets: ["section", "cover", "h"], color: C.concrete, alpha: 1, xray: 0.26, edge: C.edge, edgeAlpha: 0.6 };
  const gr = new Geo();
  for (let i = 0; i < ribs; i++) gr.box(0, 0, zr(i) - bw / 2, L, ph, zr(i) + bw / 2);
  parts.push(part(gr, { ...conc, anim: { type: "grow", axis: 0, anchor: [0, 0, 0], delay: 0.3, dur: 1 } }));
  const gp = new Geo();
  for (let i = 0; i < ribs - 1; i++) {
    const z = zr(i) + pitch / 2;
    for (const x of along(0.02, L - 0.02 - plen, plen + 0.004, 200)) gp.box(x, 0.0, z - pw / 2 + 0.002, x + plen, ph, z + pw / 2 - 0.002, false);
  }
  parts.push(part(gp, { tag: "blocks", color: C.blocks, alpha: 1, xray: 0.32, shine: 0.05, anim: { type: "drop", dist: 0.9, delay: 0.9, dur: 0.6 } }));
  parts.push(part(new Geo().box(0, ph, -W / 2, L, ph + hf, W / 2), { ...conc, tag: "topping", anim: { type: "drop", dist: 1.2, delay: 1.5, dur: 0.6 } }));
  const cover = n(r.cover, 25) / 1000, link = r.link_dia && r.link_dia !== "none" ? n(r.link_dia) / 1000 : 0;
  const db = n(r.bottom_dia, 12) / 1000, nb = Math.max(1, Math.round(n(r.bottom_n, 2)));
  const gb = new Geo();
  for (let i = 0; i < ribs; i++) {
    const half = bw / 2 - cover - link - db / 2;
    for (const z of spread(zr(i) - half, zr(i) + half, nb)) gb.cylinder([0.03, cover + link + db / 2, z], [L - 0.03, cover + link + db / 2, z], db / 2, 10);
  }
  parts.push(barsPart(gb, ["bars", "reinforcement.bottom_dia"], status, 2, [-1, 0, 0]));
  const dt = r.top_dia && r.top_dia !== "none" ? n(r.top_dia) / 1000 : 0, nt = Math.max(1, Math.round(n(r.top_n, 2)));
  if (dt) {
    const xs = (sp.supports || []).map((s) => n(s.x)).sort((p, q) => p - q);
    const inner = xs.slice(1, -1);
    const spanLen = xs.length > 1 ? (xs[xs.length - 1] - xs[0]) / (xs.length - 1) : L;
    const gt = new Geo();
    for (const x of inner.length ? inner : [L / 2]) {
      for (let i = 0; i < ribs; i++) {
        const half = bw / 2 - cover - link - dt / 2;
        for (const z of spread(zr(i) - half, zr(i) + half, nt)) gt.cylinder([Math.max(0, x - 0.3 * spanLen), ph + hf - cover - dt / 2, z], [Math.min(L, x + 0.3 * spanLen), ph + hf - cover - dt / 2, z], dt / 2, 10);
      }
    }
    parts.push(barsPart(gt, ["bars", "reinforcement.top_dia"], status, 2.3, [0, 1, 0]));
  }
  const mesh = MESH[r.mesh];
  if (mesh) {
    const [md, ms] = [mesh[0] / 1000, mesh[1] / 1000];
    const gm = new Geo();
    const y = ph + hf / 2;
    for (const z of along(-W / 2 + 0.04, W / 2 - 0.04, ms)) gm.cylinder([0.03, y, z], [L - 0.03, y, z], md / 2, 6, false);
    for (const x of along(0.04, L - 0.04, ms)) gm.cylinder([x, y + md, -W / 2 + 0.03], [x, y + md, W / 2 - 0.03], md / 2, 6, false);
    parts.push(part(gm, { tag: "links", color: C.links, shine: 0.4, edgeAlpha: 0, anim: { type: "drop", dist: 1, delay: 2.6, dur: 0.6 } }));
    labels.push({ at: [L * 0.75, ph + hf, W / 2], text: `${r.mesh} fabric`, tag: "links", cls: "links", delay: 3 });
  }
  labels.push({ at: [L * 0.3, cover, W / 2], text: `${nb}H${fmt(db * 1000)} per rib`, tag: "bars", cls: "bars", delay: 2.5 });
  labels.push({ at: [0, ph, -W / 2], text: `${P.height} + ${fmt(hf * 1000)} deep, ribs ${fmt(bw * 1000)} at ${fmt(pitch * 1000)}`, tag: "concrete", delay: 1.6 });
  return { parts, labels, view: { yaw: -1.0, pitch: -0.15 } };
}

export function slabScene(d, { status = null, pan = null } = {}) {
  const type = d.slab?.type;
  if (type === "ribbed") return ribbedScene(d, status, pan);
  if (type === "two_way") return twoWayScene(d, status);
  return oneWayScene(d, status);
}

// ------------------------------------------------------------------ pad foundation

export function foundationScene(d, { status = null, pressure = null } = {}) {
  const col = d.column || {}, base = d.base || {}, r = d.reinforcement || {}, a = d.actions || {};
  const L = Math.max(n(base.L, 2), 0.3), B = Math.max(n(base.B, 2), 0.3), h = Math.max(n(base.h, 500), 100) / 1000;
  const cx = n(col.cx, 400) / 1000, cy = n(col.cy, 400) / 1000, ds = Math.max(n(base.soil_depth, 0.5), 0);
  const parts = [], labels = [];
  const top = ds + 0.9;
  parts.push(grid(0, 0, ds + 0.001, Math.max(L, B) * 0.9 + 0.6, 0.25));
  if (r.cast === "blinding") {
    parts.push(part(new Geo().box(-L / 2 - 0.1, -h - 0.075, -B / 2 - 0.1, L / 2 + 0.1, -h, B / 2 + 0.1), { tag: "context", color: C.blinding,
      alpha: 1, xray: 0.5, edge: C.edge, edgeAlpha: 0.3, anim: { type: "fade", delay: 0, dur: 0.5 } }));
  }
  parts.push(part(new Geo().box(-L / 2, -h, -B / 2, L / 2, 0, B / 2), { tag: "concrete", targets: ["section", "cover", "base"], color: C.concrete,
    alpha: 1, xray: 0.26, edge: C.edge, edgeAlpha: 0.7, anim: { type: "grow", axis: 1, anchor: [0, -h, 0], delay: 0.2, dur: 0.9 } }));
  parts.push(part(new Geo().box(-cx / 2, 0, -cy / 2, cx / 2, top, cy / 2), { tag: "column", targets: ["column"], color: C.concrete, alpha: 1,
    xray: 0.3, edge: C.edge, edgeAlpha: 0.7, anim: { type: "grow", axis: 1, anchor: [0, 0, 0], delay: 1.7, dur: 0.7 } }));
  const cover = n(r.cover, 50) / 1000, dx = n(r.x_dia, 16) / 1000, dy = n(r.y_dia, 16) / 1000;
  const gx = new Geo();
  for (const z of along(-B / 2 + cover, B / 2 - cover, n(r.x_s, 200) / 1000)) gx.cylinder([-L / 2 + cover, -h + cover + dx / 2, z], [L / 2 - cover, -h + cover + dx / 2, z], dx / 2, 10);
  parts.push(barsPart(gx, ["bars", "reinforcement.x_dia", "reinforcement.x_s", "x"], status, 0.9, [-1, 0, 0]));
  const gy = new Geo();
  for (const x of along(-L / 2 + cover, L / 2 - cover, n(r.y_s, 200) / 1000)) gy.cylinder([x, -h + cover + dx + dy / 2, -B / 2 + cover], [x, -h + cover + dx + dy / 2, B / 2 - cover], dy / 2, 10);
  parts.push(barsPart(gy, ["bars", "reinforcement.y_dia", "reinforcement.y_s", "y"], status, 1.25, [0, 0, 1]));
  parts.push(part(new Geo().box(-L / 2 - 0.5, -h - 0.35, -B / 2 - 0.5, L / 2 + 0.5, ds, B / 2 + 0.5, false), { tag: "soil", color: C.soil,
    alpha: 0.2, xray: 0.1, edgeAlpha: 0, anim: { type: "fade", delay: 2.1, dur: 0.8 } }));

  const NEd = 1.35 * n(a.Gk) + 1.5 * n(a.Qk), MEd = 1.35 * n(a.MGk) + 1.5 * n(a.MQk);
  if (NEd > 0) {
    parts.push(part(new Geo().arrow([0, top + 1.1, 0], [0, top + 0.03, 0], 0.035), { tag: "loads", color: C.load, shine: 0.3,
      anim: { type: "drop", dist: 0.9, delay: 2.4, dur: 0.6 } }));
    labels.push({ at: [0, top + 1.18, 0], text: `NEd ${fmt(NEd)} kN`, tag: "loads", cls: "load", delay: 2.9 });
  }
  if (MEd > 0) {
    const gm = new Geo();
    arcArrow(gm, [0, top - 0.25, 0], [0, 0, 1], Math.max(cx, cy) * 0.9 + 0.15, 0.5, 2.3, 0.018);
    parts.push(part(gm, { tag: "loads", color: C.Q, anim: { type: "pop", anchor: [0, top - 0.25, 0], delay: 2.7, dur: 0.5 } }));
    labels.push({ at: [Math.max(cx, cy) + 0.25, top - 0.1, 0], text: `MEd ${fmt(MEd, 1)} kNm`, tag: "loads", cls: "load", delay: 3 });
  }
  // ground bearing pressure: a prism under the base, larger towards the side the moment pushes down
  const pmax = n(pressure?.pmax, 0), pmin = Math.max(0, n(pressure?.pmin, pmax));
  if (pmax > 0) {
    const yb = -h - (r.cast === "blinding" ? 0.075 : 0) - 0.02;
    const k = 0.9 / Math.max(pmax, 1);
    const g = new Geo();
    const P0 = [-L / 2, yb - pmin * k], P1 = [L / 2, yb - pmax * k];
    const quadPts = (z) => [[-L / 2, yb, z], [L / 2, yb, z], [L / 2, P1[1], z], [-L / 2, P0[1], z]];
    const f = quadPts(B / 2), bk = quadPts(-B / 2), inside = [0, yb - pmax * k / 2, 0];
    g.face(f, inside).face(bk, inside);
    for (let i = 0; i < 4; i++) { const j = (i + 1) % 4; g.face([f[i], f[j], bk[j], bk[i]], inside); g.line(f[i], f[j]).line(bk[i], bk[j]).line(f[i], bk[i]); }
    parts.push(part(g, { tag: "pressure", color: C.pressure, alpha: 0.3, edge: C.pressure, edgeAlpha: 0.9,
      anim: { type: "drop", dir: [0, -1, 0], dist: 0.8, delay: 2.9, dur: 0.6 } }));
    const ga = new Geo();
    for (const x of along(-L / 2 + 0.15, L / 2 - 0.15, L / 7)) {
      const depth = (pmin + ((x + L / 2) / L) * (pmax - pmin)) * k;
      for (const z of [-B / 4, B / 4]) ga.arrow([x, yb - depth, z], [x, yb - 0.01, z], 0.016, 3);
    }
    parts.push(part(ga, { tag: "pressure", color: C.pressure, shine: 0.3, anim: { type: "drop", dir: [0, -1, 0], dist: 0.8, delay: 3, dur: 0.6 } }));
    labels.push({ at: [L / 2, P1[1], B / 2], text: `${fmt(pmax, 0)} kPa ULS`, tag: "pressure", cls: "pressure", delay: 3.4 });
    if (Math.abs(pmax - pmin) > 0.5) labels.push({ at: [-L / 2, P0[1], B / 2], text: `${fmt(pmin, 0)} kPa ULS`, tag: "pressure", cls: "pressure", delay: 3.4 });
  }
  labels.push({ at: [0, -h, B / 2], text: `L ${fmt(L, 2)} m`, tag: "concrete", delay: 1.2 });
  labels.push({ at: [L / 2, -h, 0], text: `B ${fmt(B, 2)} m`, tag: "concrete", delay: 1.2 });
  labels.push({ at: [-L / 2, -h / 2, B / 2], text: `h ${fmt(h * 1000)}`, tag: "concrete", delay: 1.2 });
  labels.push({ at: [-L / 2 + cover, -h + cover, B / 2], text: `H${fmt(dx * 1000)} @ ${fmt(n(r.x_s))} · H${fmt(dy * 1000)} @ ${fmt(n(r.y_s))}`, tag: "bars", cls: "bars", delay: 2 });
  labels.push({ at: [-L / 2 - 0.5, ds, -B / 2 - 0.5], text: "ground level", tag: "soil", cls: "muted", delay: 2.6 });
  return { parts, labels, view: { yaw: -0.78, pitch: 0.36 } };
}

// ------------------------------------------------------------------ an element from its saved inputs and results

/** The model of a checked element (report and run pages): its inputs, with the failed parts from `status`. */
export function elementScene(element, input, result, { status = null, meta = null } = {}) {
  const d = result?.derived || {};
  if (element === "column") return columnScene({ ...input, actions: { ...input.actions, NEd: d.NEd ?? input.actions?.NEd } }, { status });
  if (element === "beam") return beamScene(input, { status, beff: result?.plots?.section?.beff, links: d.links });
  if (element === "slab") return slabScene(input, { status, pan: meta?.maxpans?.find((p) => p.id === input.slab?.maxpan) || null });
  const p1 = d.uls_p1, p2 = d.uls_p2 ?? d.uls_p1;
  return foundationScene(input, { status, pressure: p1 ? { pmax: Math.max(p1, p2), pmin: Math.min(p1, p2) } : null });
}
