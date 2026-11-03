// Structural Analysis & Design: the 3D viewport. A small WebGL renderer written for this app (no library, so it
// works offline). A scene is a list of parts (concrete, bars, links, supports, loads) that assemble with an
// animation, a camera that orbits, zooms and spins, labels that follow the model, and an x-ray mode that shows
// the reinforcement cage through the concrete. Parts can be dimmed to focus on one input, or glow red when a
// check on them fails.

const VS = `
attribute vec3 aPos;
attribute vec3 aNor;
uniform mat4 uVP;
uniform mat4 uM;
varying vec3 vN;
varying vec3 vW;
void main() {
  vec4 w = uM * vec4(aPos, 1.0);
  vW = w.xyz;
  vN = (uM * vec4(aNor, 0.0)).xyz;
  gl_Position = uVP * w;
}`;

const FS = `
precision mediump float;
varying vec3 vN;
varying vec3 vW;
uniform vec4 uColor;
uniform vec3 uEye;
uniform vec3 uGlow;
uniform float uShine;
void main() {
  vec3 n = normalize(vN);
  vec3 v = normalize(uEye - vW);
  if (dot(n, v) < 0.0) n = -n;
  vec3 l1 = normalize(vec3(0.45, 0.85, 0.35));
  vec3 l2 = normalize(vec3(-0.6, 0.25, -0.55));
  float d1 = max(dot(n, l1), 0.0);
  float d2 = max(dot(n, l2), 0.0);
  float hemi = 0.5 + 0.5 * n.y;
  float spec = pow(max(dot(n, normalize(l1 + v)), 0.0), 36.0) * uShine;
  float rim = pow(1.0 - max(dot(n, v), 0.0), 2.5);
  vec3 col = uColor.rgb * (0.30 + 0.20 * hemi + 0.58 * d1 + 0.16 * d2) + vec3(spec);
  col += uGlow * (0.55 + 1.3 * rim);
  gl_FragColor = vec4(col, uColor.a);
}`;

const LVS = `
attribute vec3 aPos;
uniform mat4 uVP;
uniform mat4 uM;
void main() { gl_Position = uVP * uM * vec4(aPos, 1.0); }`;

const LFS = `
precision mediump float;
uniform vec4 uColor;
void main() { gl_FragColor = uColor; }`;

// ------------------------------------------------------------------ small matrix helpers (column-major)

const ident = () => new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);

function mul(a, b) {
  const o = new Float32Array(16);
  for (let c = 0; c < 4; c++) {
    for (let r = 0; r < 4; r++) {
      let s = 0;
      for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k];
      o[c * 4 + r] = s;
    }
  }
  return o;
}

function perspective(fovy, aspect, near, far) {
  const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far);
  return new Float32Array([f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) * nf, -1, 0, 0, 2 * far * near * nf, 0]);
}

const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const scale = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a) => { const l = Math.hypot(...a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };

function lookAt(eye, target, up) {
  const z = norm(sub(eye, target));
  const x = norm(cross(up, z));
  const y = cross(z, x);
  return new Float32Array([x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0,
    -dot(x, eye), -dot(y, eye), -dot(z, eye), 1]);
}

function transformOf({ t = [0, 0, 0], s = [1, 1, 1], anchor = [0, 0, 0] }) {
  // translate(t) · translate(anchor) · scale(s) · translate(-anchor)
  const m = ident();
  m[0] = s[0]; m[5] = s[1]; m[10] = s[2];
  m[12] = t[0] + anchor[0] - s[0] * anchor[0];
  m[13] = t[1] + anchor[1] - s[1] * anchor[1];
  m[14] = t[2] + anchor[2] - s[2] * anchor[2];
  return m;
}

function project(vp, p) {
  const x = vp[0] * p[0] + vp[4] * p[1] + vp[8] * p[2] + vp[12];
  const y = vp[1] * p[0] + vp[5] * p[1] + vp[9] * p[2] + vp[13];
  const w = vp[3] * p[0] + vp[7] * p[1] + vp[11] * p[2] + vp[15];
  return w <= 0 ? null : [x / w, y / w];
}

// ------------------------------------------------------------------ geometry

/** Triangles (position + normal) and line segments for one part. */
export class Geo {
  constructor() { this.v = []; this.l = []; this.min = [Infinity, Infinity, Infinity]; this.max = [-Infinity, -Infinity, -Infinity]; }

  grow(p) { for (let i = 0; i < 3; i++) { this.min[i] = Math.min(this.min[i], p[i]); this.max[i] = Math.max(this.max[i], p[i]); } }

  tri(a, b, c, n) {
    n ??= norm(cross(sub(b, a), sub(c, a)));
    for (const p of [a, b, c]) { this.v.push(p[0], p[1], p[2], n[0], n[1], n[2]); this.grow(p); }
    return this;
  }

  quad(a, b, c, d, n) { this.tri(a, b, c, n); this.tri(a, c, d, n); return this; }

  line(a, b) { this.l.push(...a, ...b); this.grow(a); this.grow(b); return this; }

  /** Axis-aligned box; `edges` adds its outline. */
  box(x0, y0, z0, x1, y1, z1, edges = true) {
    const p = (x, y, z) => [x, y, z];
    const [a, b, c, d] = [p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1), p(x0, y1, z1)];
    const [e, f, g, h] = [p(x0, y0, z0), p(x1, y0, z0), p(x1, y1, z0), p(x0, y1, z0)];
    this.quad(a, b, c, d, [0, 0, 1]).quad(f, e, h, g, [0, 0, -1]).quad(b, f, g, c, [1, 0, 0])
      .quad(e, a, d, h, [-1, 0, 0]).quad(d, c, g, h, [0, 1, 0]).quad(e, f, b, a, [0, -1, 0]);
    if (edges) {
      for (const [u, w] of [[a, b], [b, c], [c, d], [d, a], [e, f], [f, g], [g, h], [h, e], [a, e], [b, f], [c, g], [d, h]]) this.line(u, w);
    }
    return this;
  }

  /** A face wound to face away from `inside`, so see-through parts draw their far side first. */
  face(pts, inside) {
    const n = norm(cross(sub(pts[1], pts[0]), sub(pts[2], pts[0])));
    const c = scale(pts.reduce((s, p) => add(s, p), [0, 0, 0]), 1 / pts.length);
    const q = dot(n, sub(c, inside)) < 0 ? [...pts].reverse() : pts;
    for (let i = 1; i < q.length - 1; i++) this.tri(q[0], q[i], q[i + 1]);
    return this;
  }

  /** Box from p0 to p1 along any direction: `depth` in the plane normal to `up`, `width` along `up`. */
  member(p0, p1, depth, width, up = [0, 0, 1], edges = true) {
    const u = norm(sub(p1, p0));
    let w = cross(u, up);
    w = Math.hypot(...w) < 1e-6 ? [1, 0, 0] : norm(w);
    const v = norm(cross(w, u));
    const corner = (p, sv, sw) => add(p, add(scale(v, (sv * depth) / 2), scale(w, (sw * width) / 2)));
    const order = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
    const A = order.map(([a, b]) => corner(p0, a, b));
    const B = order.map(([a, b]) => corner(p1, a, b));
    const mid = scale(add(p0, p1), 0.5);
    for (let i = 0; i < 4; i++) {
      const j = (i + 1) % 4;
      this.face([A[i], A[j], B[j], B[i]], mid);
    }
    this.face([...A], mid).face([...B], mid);
    if (edges) for (let i = 0; i < 4; i++) { const j = (i + 1) % 4; this.line(A[i], A[j]).line(B[i], B[j]).line(A[i], B[i]); }
    return this;
  }

  /** Cylinder (a bar) from p0 to p1. */
  cylinder(p0, p1, r, seg = 10, caps = true) {
    const ax = norm(sub(p1, p0));
    const ref = Math.abs(ax[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0];
    const u = norm(cross(ax, ref)), w = cross(ax, u);
    const ring = (i) => { const t = (i / seg) * Math.PI * 2; return add(scale(u, Math.cos(t)), scale(w, Math.sin(t))); };
    for (let i = 0; i < seg; i++) {
      const n0 = ring(i), n1 = ring(i + 1);
      const a = add(p0, scale(n0, r)), b = add(p0, scale(n1, r)), c = add(p1, scale(n1, r)), d = add(p1, scale(n0, r));
      for (const [p, n] of [[a, n0], [b, n1], [c, n1], [a, n0], [c, n1], [d, n0]]) {
        this.v.push(p[0], p[1], p[2], n[0], n[1], n[2]); this.grow(p);
      }
      if (caps) {
        this.tri(p1, d, c, ax);
        this.tri(p0, b, a, scale(ax, -1));
      }
    }
    return this;
  }

  /** Cone with its base centred at `base` and its tip at `tip` (an arrow head; seg = 4 gives a pyramid). */
  cone(base, tip, r, seg = 14) {
    const ax = norm(sub(tip, base));
    const ref = Math.abs(ax[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0];
    const u = norm(cross(ax, ref)), w = cross(ax, u);
    const ring = (i) => { const t = (i / seg) * Math.PI * 2 + (seg === 4 ? Math.PI / 4 : 0); return add(scale(u, Math.cos(t)), scale(w, Math.sin(t))); };
    for (let i = 0; i < seg; i++) {
      const a = add(base, scale(ring(i), r)), b = add(base, scale(ring(i + 1), r));
      this.tri(a, b, tip);
      this.tri(base, b, a, scale(ax, -1));
    }
    return this;
  }

  /** A closed loop of bars through the points (a link or stirrup). */
  loop(points, r, seg = 6) {
    for (let i = 0; i < points.length; i++) this.cylinder(points[i], points[(i + 1) % points.length], r, seg, false);
    return this;
  }

  /** An arrow from `from` to `to`, its head a cone. */
  arrow(from, to, r, head = 3.2) {
    const len = Math.hypot(...sub(to, from));
    const hl = Math.min(len * 0.45, r * head * 2.2);
    const neck = add(to, scale(norm(sub(from, to)), hl));
    this.cylinder(from, neck, r, 10);
    this.cone(neck, to, r * head * 0.8, 14);
    return this;
  }

  /** A triangular prism standing on its base, its ridge along z: a pinned support. */
  wedge(cx, y, half, height, z0, z1) {
    const a = [cx - half, y - height, z1], b = [cx + half, y - height, z1], c = [cx, y, z1];
    const d = [cx - half, y - height, z0], e = [cx + half, y - height, z0], f = [cx, y, z0];
    this.tri(a, b, c).tri(e, d, f).quad(b, e, f, c).quad(d, a, c, f).quad(d, e, b, a);
    for (const [u, w] of [[a, b], [b, c], [c, a], [d, e], [e, f], [f, d], [a, d], [b, e], [c, f]]) this.line(u, w);
    return this;
  }
}

// ------------------------------------------------------------------ easing

const clamp01 = (x) => Math.max(0, Math.min(1, x));
const easeOut = (t) => 1 - (1 - t) ** 3;
const easeBack = (t) => { const c = 1.6; return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2; };

const hex = (h) => {
  const n = parseInt(h.replace("#", ""), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
};

// ------------------------------------------------------------------ the viewer

const REDUCED = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Mount a 3D viewport in `host`. Options: toolbar (true), labels (true), spin (true), compact (false).
 * Returns { setScene(scene, { replay }), setFocus(tags), replay(), dispose(), ok }.
 */
export function createViewer(host, opts = {}) {
  const o = { toolbar: true, labels: true, spin: true, compact: false, ...opts };
  host.classList.add("vp");
  if (o.compact) host.classList.add("vp-compact");
  const canvas = document.createElement("canvas");
  canvas.className = "vp-canvas";
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", "3D model of the element");
  const overlay = document.createElement("div");
  overlay.className = "vp-labels";
  overlay.setAttribute("aria-hidden", "true");
  const triad = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  triad.setAttribute("class", "vp-triad");
  triad.setAttribute("viewBox", "-30 -30 60 60");
  triad.setAttribute("aria-hidden", "true");
  host.replaceChildren(canvas, overlay);
  if (!o.compact) host.append(triad);

  const gl = canvas.getContext("webgl", { antialias: true, alpha: true, premultipliedAlpha: false, preserveDrawingBuffer: false })
    || canvas.getContext("experimental-webgl");
  if (!gl) {
    host.classList.add("vp-none");
    const p = document.createElement("p");
    p.className = "vp-fallback";
    p.textContent = "The 3D view needs WebGL, which this browser has turned off. The 2D drawings show the same element.";
    host.replaceChildren(p);
    return { ok: false, setScene() {}, setFocus() {}, replay() {}, dispose() {} };
  }

  const program = (vs, fs) => {
    const p = gl.createProgram();
    for (const [type, src] of [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fs]]) {
      const s = gl.createShader(type);
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      gl.attachShader(p, s);
    }
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    const loc = (n) => gl.getUniformLocation(p, n);
    return { p, aPos: gl.getAttribLocation(p, "aPos"), aNor: gl.getAttribLocation(p, "aNor"),
      uVP: loc("uVP"), uM: loc("uM"), uColor: loc("uColor"), uEye: loc("uEye"), uGlow: loc("uGlow"), uShine: loc("uShine") };
  };
  const solid = program(VS, FS);
  const lines = program(LVS, LFS);

  const state = {
    parts: [], labels: [], start: 0, center: [0, 0, 0], radius: 1, fit: 1,
    yaw: -0.65, pitch: 0.42, zoom: 1, baseYaw: -0.65, basePitch: 0.42,
    spin: o.spin && !REDUCED, xray: true, focus: null, drag: null, raf: 0, last: 0, visible: true, disposed: false,
    intro: 0,
  };

  // ---------------------------------------------------------------- toolbar
  const buttons = {};
  if (o.toolbar) {
    const bar = document.createElement("div");
    bar.className = "vp-tools";
    const mk = (key, label, title, pressed) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "vp-btn";
      b.dataset.key = key;
      b.textContent = label;
      b.title = title;
      if (pressed !== undefined) b.setAttribute("aria-pressed", String(pressed));
      bar.append(b);
      buttons[key] = b;
      return b;
    };
    mk("xray", "X-ray", "See the reinforcement through the concrete", true).addEventListener("click", () => {
      state.xray = !state.xray; buttons.xray.setAttribute("aria-pressed", String(state.xray)); kick();
    });
    mk("spin", "Spin", "Turn the model slowly", state.spin).addEventListener("click", () => {
      state.spin = !state.spin; buttons.spin.setAttribute("aria-pressed", String(state.spin)); kick();
    });
    mk("replay", "Build", "Play the build-up animation again").addEventListener("click", () => replay());
    mk("home", "Reset view", "Back to the starting view").addEventListener("click", () => {
      state.yaw = state.baseYaw; state.pitch = state.basePitch; state.zoom = 1; kick();
    });
    host.append(bar);
  }
  const hint = document.createElement("p");
  hint.className = "vp-hint";
  hint.textContent = "Drag to turn · scroll or pinch to zoom · double-click to rebuild";
  if (!o.compact) host.append(hint);

  // ---------------------------------------------------------------- interaction
  const pointers = new Map();
  canvas.addEventListener("pointerdown", (e) => {
    pointers.set(e.pointerId, [e.clientX, e.clientY]);
    canvas.setPointerCapture?.(e.pointerId);
    state.drag = { x: e.clientX, y: e.clientY, pinch: null };
    if (state.spin && !o.compact) { state.spin = false; buttons.spin?.setAttribute("aria-pressed", "false"); }
    host.classList.add("vp-dragging");
    kick();
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!pointers.has(e.pointerId) || !state.drag) return;
    pointers.set(e.pointerId, [e.clientX, e.clientY]);
    if (pointers.size >= 2) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (state.drag.pinch) state.zoom = Math.max(0.25, Math.min(4, state.zoom * (state.drag.pinch / d)));
      state.drag.pinch = d;
    } else {
      state.yaw -= (e.clientX - state.drag.x) * 0.008;
      state.pitch = Math.max(-0.7, Math.min(1.45, state.pitch + (e.clientY - state.drag.y) * 0.006));
      state.drag.x = e.clientX; state.drag.y = e.clientY;
    }
    kick();
  });
  const end = (e) => {
    pointers.delete(e.pointerId);
    if (!pointers.size) { state.drag = null; host.classList.remove("vp-dragging"); }
  };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
  canvas.addEventListener("wheel", (e) => {
    if (o.compact) return;
    e.preventDefault();
    state.zoom = Math.max(0.25, Math.min(4, state.zoom * Math.exp(e.deltaY * 0.0012)));
    kick();
  }, { passive: false });
  canvas.addEventListener("dblclick", () => replay());
  canvas.addEventListener("webglcontextlost", (e) => { e.preventDefault(); state.disposed = true; });

  const ro = new ResizeObserver(() => kick());
  ro.observe(host);
  const io = new IntersectionObserver((entries) => {
    state.visible = entries.some((x) => x.isIntersecting);
    if (state.visible) kick();
  });
  io.observe(host);

  // ---------------------------------------------------------------- scene

  function upload(part) {
    const g = part.geo;
    if (g.v.length) {
      part.buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, part.buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(g.v), gl.STATIC_DRAW);
      part.count = g.v.length / 6;
    }
    if (g.l.length) {
      part.lbuf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, part.lbuf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(g.l), gl.STATIC_DRAW);
      part.lcount = g.l.length / 3;
    }
    part.rgb = hex(part.color || "#9aa3ab");
    part.lrgb = hex(part.edge || "#1f2a33");
    part.mid = [(g.min[0] + g.max[0]) / 2, (g.min[1] + g.max[1]) / 2, (g.min[2] + g.max[2]) / 2];
  }

  function free(parts) {
    for (const p of parts) { if (p.buf) gl.deleteBuffer(p.buf); if (p.lbuf) gl.deleteBuffer(p.lbuf); }
  }

  /** scene = { parts: [{ geo, color, alpha, shine, tag, edge, edgeAlpha, xray, anim, fail }], labels, view } */
  function setScene(scene, { replay: animate = false, keepTime = false } = {}) {
    if (state.disposed) return;
    free(state.parts);
    state.parts = (scene?.parts || []).filter((p) => p.geo && (p.geo.v.length || p.geo.l.length));
    state.parts.forEach(upload);
    state.labels = o.labels ? (scene?.labels || []) : [];
    overlay.replaceChildren(...state.labels.map((l) => {
      const s = document.createElement("span");
      s.className = `vp-label ${l.cls || ""}`;
      s.textContent = l.text;
      l.node = s;
      return s;
    }));
    // fit the camera to everything except the ground grid
    const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    for (const p of state.parts) {
      if (p.tag === "grid") continue;
      for (let i = 0; i < 3; i++) { min[i] = Math.min(min[i], p.geo.min[i]); max[i] = Math.max(max[i], p.geo.max[i]); }
    }
    if (Number.isFinite(min[0])) {
      const c = [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2];
      const r = Math.max(Math.hypot(max[0] - min[0], max[1] - min[1], max[2] - min[2]) / 2, 0.05);
      const first = !state.fitted || scene?.view?.refit;
      state.center = c;
      state.radius = r;
      state.box = [min, max];
      if (first) {
        state.fitted = true;
        if (scene?.view?.yaw !== undefined) state.yaw = state.baseYaw = scene.view.yaw;
        if (scene?.view?.pitch !== undefined) state.pitch = state.basePitch = scene.view.pitch;
        state.zoom = scene?.view?.zoom ?? 1;
      }
    }
    if (animate || !state.played) { state.played = true; state.start = performance.now(); state.intro = REDUCED ? 0 : 1; }
    else if (!keepTime) state.start = -1e9;     // a live update: show the parts as they are
    kick();
  }

  function replay() {
    state.start = performance.now();
    state.intro = REDUCED ? 0 : 1;
    kick();
  }

  function setFocus(tags) { state.focus = tags && tags.length ? new Set(tags) : null; kick(); }

  // ---------------------------------------------------------------- drawing

  function progress(part, now) {
    const a = part.anim;
    if (!a || REDUCED) return 1;
    return clamp01((now - state.start - (a.delay || 0) * 1000) / ((a.dur || 0.7) * 1000));
  }

  function partMatrix(part, p) {
    const a = part.anim;
    if (!a || p >= 1) return null;
    const e = a.type === "pop" ? easeBack(p) : easeOut(p);
    const anchor = a.anchor || part.mid;
    if (a.type === "grow") {
      const s = [1, 1, 1];
      s[a.axis ?? 1] = Math.max(e, 0.001);
      return transformOf({ s, anchor });
    }
    if (a.type === "drop") {
      const d = a.dir || [0, 1, 0];
      return transformOf({ t: scale(d, (1 - e) * (a.dist ?? 1)) });
    }
    if (a.type === "pop") {
      const k = Math.max(0.001, e);
      return transformOf({ s: [k, k, k], anchor });
    }
    return null;
  }

  /** Distance at which the box fits the view from every side the model turns to (spinning stays in frame). */
  function fitDistance(fov, aspect, pitch, yaw0) {
    if (!state.box) return state.radius / Math.sin(fov / 2);
    const [min, max] = state.box, c = state.center;
    const tv = Math.tan(fov / 2), th = tv * aspect;
    let need = 0;
    // a model that sways is seen from its starting view, give or take the sway; one that turns from every side
    const yaws = o.spin === "sway" ? [-0.55, -0.28, 0, 0.28, 0.55] : [0, 1, 2, 3, 4, 5, 6, 7].map((k) => (k * Math.PI) / 4);
    for (const dy of yaws) {
      const yaw = yaw0 + dy;
      const fwd = [-Math.cos(pitch) * Math.sin(yaw), -Math.sin(pitch), -Math.cos(pitch) * Math.cos(yaw)];
      const right = norm(cross(fwd, [0, 1, 0]));
      const up = cross(right, fwd);
      for (let i = 0; i < 8; i++) {
        const p = [i & 1 ? max[0] : min[0], i & 2 ? max[1] : min[1], i & 4 ? max[2] : min[2]].map((v, j) => v - c[j]);
        const z = dot(p, fwd);
        need = Math.max(need, Math.abs(dot(p, right)) / th - z, Math.abs(dot(p, up)) / tv - z);
      }
    }
    return need;
  }

  function camera(now) {
    const w = canvas.clientWidth || 1, h = canvas.clientHeight || 1;
    const fov = 0.62;
    const aspect = w / h;
    const key = `${aspect.toFixed(3)}:${state.basePitch}:${state.radius}`;
    if (state.fitKey !== key) { state.fitKey = key; state.fit = fitDistance(fov, aspect, state.basePitch, state.baseYaw); }
    let dist = state.fit * 1.06 * state.zoom;
    let yaw = state.yaw, pitch = state.pitch;
    if (state.intro) {
      const t = clamp01((now - state.start) / 1900);
      const e = easeOut(t);
      dist *= 1 + 0.75 * (1 - e);
      yaw += 1.1 * (1 - e);
      pitch += 0.25 * (1 - e);
      if (t >= 1) state.intro = 0;
    }
    const c = state.center;
    const eye = [c[0] + dist * Math.cos(pitch) * Math.sin(yaw), c[1] + dist * Math.sin(pitch), c[2] + dist * Math.cos(pitch) * Math.cos(yaw)];
    const P = perspective(fov, aspect, Math.max(dist / 200, 0.005), dist * 20);
    const V = lookAt(eye, c, [0, 1, 0]);
    return { VP: mul(P, V), V, eye, w, h };
  }

  function draw(now) {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.round(canvas.clientWidth * dpr), h = Math.round(canvas.clientHeight * dpr);
    if (!w || !h) return false;
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    gl.viewport(0, 0, w, h);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LEQUAL);
    const cam = camera(now);
    let busy = Boolean(state.intro);
    const pulse = REDUCED ? 0.8 : 0.55 + 0.45 * Math.sin(now / 260);
    const focusGlow = REDUCED ? 0.5 : 0.35 + 0.25 * Math.sin(now / 420);

    const items = [];
    for (const part of state.parts) {
      const p = progress(part, now);
      if (p < 1) busy = true;
      if (p <= 0) continue;
      let alpha = part.alpha ?? 1;
      if (state.xray && part.xray !== undefined) alpha = part.xray;
      if (part.anim && part.anim.type !== "grow" && part.anim.type !== "pop") alpha *= easeOut(p);
      const dim = state.focus && part.tag !== "grid" && !state.focus.has(part.tag);
      if (dim) alpha *= 0.4;
      else if (state.focus && state.xray && part.xray !== undefined) alpha = Math.max(alpha, 0.5);
      let glow = [0, 0, 0];
      if (part.fail) { glow = [0.95 * pulse, 0.1 * pulse, 0.08 * pulse]; busy = true; }
      else if (state.focus && state.focus.has(part.tag)) { glow = [0.05 * focusGlow, 0.3 * focusGlow, 0.62 * focusGlow]; busy = true; }
      const M = partMatrix(part, p) || ident();
      const d = dot(sub(part.mid, cam.eye), sub(part.mid, cam.eye));
      items.push({ part, alpha, glow, M, d });
    }

    const drawSolid = (it) => {
      if (!it.part.buf) return;
      gl.useProgram(solid.p);
      gl.uniformMatrix4fv(solid.uVP, false, cam.VP);
      gl.uniformMatrix4fv(solid.uM, false, it.M);
      gl.uniform3fv(solid.uEye, cam.eye);
      gl.uniform4f(solid.uColor, ...(it.part.fail ? [0.86, 0.2, 0.18] : it.part.rgb), it.alpha);
      gl.uniform3fv(solid.uGlow, it.glow);
      gl.uniform1f(solid.uShine, it.part.shine ?? 0.12);
      gl.bindBuffer(gl.ARRAY_BUFFER, it.part.buf);
      gl.enableVertexAttribArray(solid.aPos);
      gl.vertexAttribPointer(solid.aPos, 3, gl.FLOAT, false, 24, 0);
      gl.enableVertexAttribArray(solid.aNor);
      gl.vertexAttribPointer(solid.aNor, 3, gl.FLOAT, false, 24, 12);
      gl.drawArrays(gl.TRIANGLES, 0, it.part.count);
      gl.disableVertexAttribArray(solid.aNor);
    };

    // opaque first, then the see-through parts from the back, their far faces before their near ones
    gl.disable(gl.BLEND);
    gl.depthMask(true);
    gl.disable(gl.CULL_FACE);
    gl.enable(gl.POLYGON_OFFSET_FILL);
    gl.polygonOffset(1, 1);
    for (const it of items) if (it.alpha >= 0.995) drawSolid(it);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.depthMask(false);
    gl.enable(gl.CULL_FACE);
    const clear = items.filter((it) => it.alpha < 0.995).sort((a, b) => b.d - a.d);
    for (const it of clear) {
      gl.cullFace(gl.FRONT); drawSolid(it);
      gl.cullFace(gl.BACK); drawSolid(it);
    }
    gl.disable(gl.CULL_FACE);
    gl.disable(gl.POLYGON_OFFSET_FILL);

    // outlines
    gl.useProgram(lines.p);
    gl.uniformMatrix4fv(lines.uVP, false, cam.VP);
    for (const it of items) {
      if (!it.part.lbuf) continue;
      const ea = (it.part.edgeAlpha ?? 0.55) * Math.min(1, it.alpha * 2.2);
      if (ea <= 0.01) continue;
      gl.uniformMatrix4fv(lines.uM, false, it.M);
      gl.uniform4f(lines.uColor, ...(it.part.fail ? [1, 0.3, 0.25] : it.part.lrgb), ea);
      gl.bindBuffer(gl.ARRAY_BUFFER, it.part.lbuf);
      gl.enableVertexAttribArray(lines.aPos);
      gl.vertexAttribPointer(lines.aPos, 3, gl.FLOAT, false, 12, 0);
      gl.drawArrays(gl.LINES, 0, it.part.lcount);
    }
    gl.depthMask(true);

    // labels, nudged down when they would cover one placed before them
    const placed = [];
    for (const l of state.labels) {
      const q = project(cam.VP, l.at);
      const shown = q && (REDUCED || now - state.start > (l.delay ?? 1.6) * 1000) && (!state.focus || !l.tag || state.focus.has(l.tag));
      if (!q || !shown) { l.node.style.opacity = "0"; continue; }
      l.w ??= l.node.offsetWidth || 80;
      l.h ??= l.node.offsetHeight || 20;
      let x = ((q[0] + 1) / 2) * cam.w + 6, y = ((1 - q[1]) / 2) * cam.h - 11;
      x = Math.max(4, Math.min(cam.w - l.w - 4, x));
      y = Math.max(o.toolbar ? 42 : 4, Math.min(cam.h - l.h - 26, y));
      for (let k = 0; k < 6; k++) {
        const hit = placed.find((r) => x < r.x + r.w + 3 && x + l.w + 3 > r.x && y < r.y + r.h + 2 && y + l.h + 2 > r.y);
        if (!hit) break;
        y = hit.y + hit.h + 3;
      }
      placed.push({ x, y, w: l.w, h: l.h });
      l.node.style.opacity = "1";
      l.node.style.transform = `translate(${x}px, ${y}px)`;
    }

    // orientation triad
    if (!o.compact) {
      const V = cam.V;
      const axes = [["x", [1, 0, 0], "#d95319"], ["y", [0, 1, 0], "#77ac30"], ["z", [0, 0, 1], "#4dbeee"]];
      triad.replaceChildren(...axes.flatMap(([n, a, c]) => {
        const x = V[0] * a[0] + V[4] * a[1] + V[8] * a[2], y = V[1] * a[0] + V[5] * a[1] + V[9] * a[2];
        const ln = document.createElementNS("http://www.w3.org/2000/svg", "line");
        ln.setAttribute("x1", "0"); ln.setAttribute("y1", "0");
        ln.setAttribute("x2", String(x * 20)); ln.setAttribute("y2", String(-y * 20));
        ln.setAttribute("stroke", c); ln.setAttribute("stroke-width", "2.4"); ln.setAttribute("stroke-linecap", "round");
        const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
        t.setAttribute("x", String(x * 26)); t.setAttribute("y", String(-y * 26 + 3.5));
        t.setAttribute("fill", c); t.setAttribute("text-anchor", "middle");
        t.textContent = n;
        return [ln, t];
      }));
    }
    return busy;
  }

  function frame(now) {
    state.raf = 0;
    if (state.disposed) return;
    const dt = state.last ? Math.min(0.05, (now - state.last) / 1000) : 0;
    state.last = now;
    if (state.spin && !state.drag) {
      // a full turn on the home page; elsewhere the model sways about its starting view so its labels stay readable
      if (o.spin === "sway") { state.swayT = (state.swayT || 0) + dt; state.yaw = state.baseYaw + 0.5 * Math.sin(state.swayT * 0.42); }
      else state.yaw += dt * 0.28;
    }
    const busy = draw(now);
    if (state.visible && !document.hidden && (busy || state.spin || state.drag)) state.raf = requestAnimationFrame(frame);
    else state.last = 0;
  }

  function kick() {
    if (!state.raf && !state.disposed) state.raf = requestAnimationFrame(frame);
  }
  document.addEventListener("visibilitychange", kick);

  return {
    ok: true,
    setScene,
    setFocus,
    replay,
    dispose() {
      state.disposed = true;
      cancelAnimationFrame(state.raf);
      ro.disconnect(); io.disconnect();
      free(state.parts);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    },
  };
}
