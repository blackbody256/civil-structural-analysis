import { el, getJSON } from "./common.js";

const stroke = 'stroke="#14213d" stroke-width="2" fill="none"';
const ICONS = {
  column: `<svg viewBox="0 0 150 112" aria-hidden="true">
      <rect x="52" y="8" width="24" height="88" fill="#e8e3d5" ${stroke}/>
      <path d="M40 96 h48" stroke="#14213d" stroke-width="2.5"/>
      ${[0, 1, 2, 3, 4, 5].map((i) => `<path d="M${42 + i * 8} 96 l-6 8" stroke="#14213d" stroke-width="1"/>`).join("")}
      <path d="M64 0 v8" stroke="#b42318" stroke-width="2.5"/><path d="M59 2 l5 7 l5 -7" fill="#b42318"/>
      <rect x="98" y="30" width="40" height="40" fill="#e8e3d5" ${stroke}/>
      <rect x="103" y="35" width="30" height="30" rx="4" fill="none" stroke="#1f4e8c" stroke-width="2"/>
      ${[[107, 39], [118, 39], [129, 39], [107, 50], [129, 50], [107, 61], [118, 61], [129, 61]]
        .map(([x, y]) => `<circle cx="${x}" cy="${y}" r="2.6" fill="#14213d"/>`).join("")}
      <path d="M76 50 h22" stroke="#6b7385" stroke-dasharray="3 2"/>
    </svg>`,
  wall: `<svg viewBox="0 0 150 112" aria-hidden="true">
      <rect x="35" y="10" width="80" height="84" fill="#e8e3d5" ${stroke}/>
      ${[0, 1, 2, 3, 4].map((i) => `<path d="M${47 + i * 14} 16 v72" stroke="#1f4e8c" stroke-width="1.6"/>`).join("")}
      ${[0, 1, 2, 3].map((i) => `<path d="M41 ${26 + i * 18} h68" stroke="#1f4e8c" stroke-width="1" stroke-dasharray="4 2"/>`).join("")}
      <path d="M25 94 h100" stroke="#14213d" stroke-width="2.5"/>
    </svg>`,
  beam: `<svg viewBox="0 0 150 112" aria-hidden="true">
      <rect x="14" y="46" width="122" height="20" fill="#e8e3d5" ${stroke}/>
      <path d="M24 66 l-8 12 h16 z M126 66 l-8 12 h16 z" fill="#fff" ${stroke}/>
      ${[0, 1, 2, 3, 4, 5, 6].map((i) => `<path d="M${26 + i * 16} 24 v18" stroke="#b42318" stroke-width="1.6"/><path d="M${22 + i * 16} 36 l4 6 l4 -6" fill="#b42318"/>`).join("")}
      <path d="M22 24 h108" stroke="#b42318" stroke-width="1.6"/>
      <path d="M24 60 h102" stroke="#1f4e8c" stroke-width="2"/>
    </svg>`,
  slab: `<svg viewBox="0 0 150 112" aria-hidden="true">
      <path d="M20 62 L64 36 L132 46 L88 74 Z" fill="#e8e3d5" ${stroke}/>
      <path d="M20 62 v8 L88 82 v-8 M88 82 L132 54 v-8" ${stroke}/>
      ${[0, 1, 2, 3].map((i) => `<path d="M${33 + i * 14} ${54 - i * 1} L${101 + i * 7} ${66 - i * 5}" stroke="#1f4e8c" stroke-width="1"/>`).join("")}
      <path d="M20 70 v20 M88 82 v18 M132 54 v24" stroke="#14213d" stroke-width="3"/>
    </svg>`,
  "flat-slab": `<svg viewBox="0 0 150 112" aria-hidden="true">
      <path d="M14 44 L60 26 L136 36 L90 56 Z" fill="#e8e3d5" ${stroke}/>
      <path d="M14 44 v7 L90 63 v-7 M90 63 L136 43 v-7" ${stroke}/>
      <rect x="40" y="52" width="8" height="40" fill="#e8e3d5" ${stroke}/>
      <rect x="96" y="58" width="8" height="40" fill="#e8e3d5" ${stroke}/>
      <ellipse cx="44" cy="49" rx="16" ry="6" fill="none" stroke="#b42318" stroke-dasharray="4 2" stroke-width="1.5"/>
    </svg>`,
  foundation: `<svg viewBox="0 0 150 112" aria-hidden="true">
      <rect x="64" y="8" width="22" height="52" fill="#e8e3d5" ${stroke}/>
      <rect x="28" y="60" width="94" height="22" fill="#e8e3d5" ${stroke}/>
      <path d="M10 82 h130" stroke="#14213d" stroke-width="1.5"/>
      ${[0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => `<path d="M${30 + i * 11} 86 l4 6" stroke="#6b7385" stroke-width="1"/>`).join("")}
      ${[0, 1, 2, 3, 4, 5, 6].map((i) => `<path d="M${36 + i * 13} 98 v-8" stroke="#1f4e8c" stroke-width="1.4"/>`).join("")}
      <path d="M36 98 h78" stroke="#1f4e8c" stroke-width="1.4"/>
    </svg>`,
  "retaining-wall": `<svg viewBox="0 0 150 112" aria-hidden="true">
      <path d="M58 10 h14 v66 h44 v14 H34 v-14 h24 Z" fill="#e8e3d5" ${stroke}/>
      <path d="M72 18 L136 18 L136 76 L72 76" fill="rgba(168,107,12,.12)" stroke="#a86b0c" stroke-dasharray="4 3"/>
      ${[0, 1, 2, 3].map((i) => `<path d="M${52 - i * 6} ${30 + i * 12} h-14" stroke="#b42318" stroke-width="1.5"/><path d="M${40 - i * 6} ${26 + i * 12} l-5 4 l5 4" fill="#b42318"/>`).join("")}
    </svg>`,
};

function card(item) {
  const active = item.status === "active";
  const body = [
    el("div", { class: "art", html: ICONS[item.id] || "" }),
    el("div", { class: "body" },
      el("div", { class: "meta" }, el("span", {}, `Chapter ${item.chapter}`), el("span", {}, `p.${item.page}`)),
      el("h3", {}, item.title),
      el("div", { class: "sub" }, item.subtitle),
      el("p", {}, item.summary),
      el("ul", {}, item.checks.map((c) => el("li", {}, c)))),
    el("div", { class: "foot" },
      el("span", { class: `badge ${active ? "active" : "planned"}` }, active ? "Available" : "Planned"),
      active ? el("span", { class: "go" }, "Start check →") : el("span", { class: "muted" }, "Next modules")),
  ];
  return active
    ? el("a", { class: "element-card active", href: item.url }, ...body)
    : el("div", { class: "element-card planned", "aria-disabled": "true" }, ...body);
}

async function main() {
  const grid = document.getElementById("elements");
  try {
    const items = await getJSON("/api/elements");
    grid.replaceChildren(...items.map(card));
  } catch (err) {
    grid.replaceChildren(el("div", { class: "empty" }, "Could not load the element list. Is the server running?"));
  }
}

main();
