// Inline floating editor for loads and supports placed on the beam canvas.
import { el } from "./common.js";

const CASES = [
  ["Ed", "Design"],
  ["G", "gk × 1.35"],
  ["Q", "qk × 1.5"],
];

const SUPPORT_TYPES = [
  ["pin", "Pinned"],
  ["roller", "Roller"],
  ["fixed", "Fixed"],
];

const DIRECTIONS = [
  ["cw", "Clockwise"],
  ["ccw", "Anticlockwise"],
];

export class CanvasEditor {
  constructor(host) {
    this.host = host;
    this.current = null;
    this.panel = null;
    this._outsideHandler = (e) => {
      if (this.panel && !this.panel.contains(e.target)) {
        this.close();
      }
    };
  }

  isOpen() {
    return Boolean(this.panel);
  }

  close() {
    if (this.panel) {
      document.removeEventListener("pointerdown", this._outsideHandler, true);
      this.panel.remove();
      this.panel = null;
      this.current = null;
    }
  }

  open({ selection, item, length, screenPoint, onApply, onDelete }) {
    this.close();
    if (!item) return;

    this.current = { selection, item };
    const kind = selection.kind;
    const isLoad = kind === "load";
    const type = isLoad ? item.type : "support";

    const titleText = isLoad
      ? { point: "Point load", udl: "Uniform load", linear: "Varying load", moment: "Applied moment" }[type] || "Load"
      : "Support";

    const closeBtn = el("button", { type: "button", class: "canvas-editor-close", "aria-label": "Close" }, "×");
    closeBtn.addEventListener("click", () => this.close());

    const head = el("div", { class: "canvas-editor-head" },
      el("span", {}, titleText),
      closeBtn
    );

    const inputs = {};
    const fieldsWrap = el("div", { class: "fields" });

    function addField(id, label, inputEl, unitText) {
      inputs[id] = inputEl;
      const control = el("div", { class: "control" }, inputEl);
      if (unitText) control.append(el("span", { class: "unit" }, unitText));
      fieldsWrap.append(el("div", { class: "field" },
        el("label", { for: `ced-${id}` }, label),
        control
      ));
    }

    function numInput(id, val, step = "any") {
      const inp = el("input", {
        id: `ced-${id}`,
        type: "number",
        step,
        value: val !== undefined && val !== null ? String(val) : "",
      });
      inp.addEventListener("input", () => inp.classList.remove("is-invalid"));
      return inp;
    }

    function selectEl(id, options, currentVal) {
      const sel = el("select", { id: `ced-${id}` },
        options.map(([val, label]) => el("option", { value: val, selected: val === currentVal }, label))
      );
      return sel;
    }

    if (isLoad) {
      if (type === "point") {
        addField("W", "Load W (downward +)", numInput("W", item.W, "any"), "kN");
        addField("x", "Position x", numInput("x", item.x, "0.1"), "m");
        addField("case", "Case", selectEl("case", CASES, item.case || "Ed"));
      } else if (type === "udl") {
        addField("w", "Load w", numInput("w", item.w, "any"), "kN/m");
        addField("x1", "From x1", numInput("x1", item.x1, "0.1"), "m");
        addField("x2", "To x2", numInput("x2", item.x2, "0.1"), "m");
        addField("case", "Case", selectEl("case", CASES, item.case || "Ed"));
      } else if (type === "linear") {
        addField("w1", "Load w1 (at x1)", numInput("w1", item.w1, "any"), "kN/m");
        addField("w2", "Load w2 (at x2)", numInput("w2", item.w2, "any"), "kN/m");
        addField("x1", "From x1", numInput("x1", item.x1, "0.1"), "m");
        addField("x2", "To x2", numInput("x2", item.x2, "0.1"), "m");
        addField("case", "Case", selectEl("case", CASES, item.case || "Ed"));
      } else if (type === "moment") {
        const mag = Math.abs(item.M || 0);
        const dir = (item.M >= 0) ? "cw" : "ccw";
        addField("M", "Moment magnitude", numInput("M", mag, "any"), "kN·m");
        addField("dir", "Direction", selectEl("dir", DIRECTIONS, dir));
        addField("x", "Position x", numInput("x", item.x, "0.1"), "m");
        addField("case", "Case", selectEl("case", CASES, item.case || "Ed"));
      }
    } else {
      addField("x", "Position x", numInput("x", item.x, "0.1"), "m");
      addField("type", "Support type", selectEl("type", SUPPORT_TYPES, item.type || "pin"));
    }

    const applyBtn = el("button", { type: "button", class: "btn primary small" }, "Apply");
    const deleteBtn = el("button", { type: "button", class: "btn small" }, "Delete");

    const actions = el("div", { class: "actions" },
      deleteBtn,
      applyBtn
    );

    const panel = el("div", { class: "canvas-editor pop" },
      head,
      fieldsWrap,
      actions
    );

    const parseNum = (inp) => {
      const val = parseFloat(inp.value);
      if (Number.isNaN(val) || !Number.isFinite(val)) {
        inp.classList.add("is-invalid");
        return null;
      }
      return val;
    };

    const handleApply = () => {
      let valid = true;
      const updated = { ...item };

      if (isLoad) {
        if (type === "point") {
          const W = parseNum(inputs.W);
          const x = parseNum(inputs.x);
          if (W === null || x === null) valid = false;
          else {
            updated.W = W;
            updated.x = Math.max(0, Math.min(length, x));
            updated.case = inputs.case.value;
          }
        } else if (type === "udl") {
          const w = parseNum(inputs.w);
          const x1 = parseNum(inputs.x1);
          const x2 = parseNum(inputs.x2);
          if (w === null || x1 === null || x2 === null) valid = false;
          else {
            const cx1 = Math.max(0, Math.min(length, x1));
            const cx2 = Math.max(0, Math.min(length, x2));
            if (cx2 <= cx1) {
              inputs.x2.classList.add("is-invalid");
              valid = false;
            } else {
              updated.w = w;
              updated.x1 = cx1;
              updated.x2 = cx2;
              updated.case = inputs.case.value;
            }
          }
        } else if (type === "linear") {
          const w1 = parseNum(inputs.w1);
          const w2 = parseNum(inputs.w2);
          const x1 = parseNum(inputs.x1);
          const x2 = parseNum(inputs.x2);
          if (w1 === null || w2 === null || x1 === null || x2 === null) valid = false;
          else {
            const cx1 = Math.max(0, Math.min(length, x1));
            const cx2 = Math.max(0, Math.min(length, x2));
            if (cx2 <= cx1) {
              inputs.x2.classList.add("is-invalid");
              valid = false;
            } else {
              updated.w1 = w1;
              updated.w2 = w2;
              updated.x1 = cx1;
              updated.x2 = cx2;
              updated.case = inputs.case.value;
            }
          }
        } else if (type === "moment") {
          const M = parseNum(inputs.M);
          const x = parseNum(inputs.x);
          if (M === null || x === null) valid = false;
          else {
            const sign = inputs.dir.value === "ccw" ? -1 : 1;
            updated.M = sign * Math.abs(M);
            updated.x = Math.max(0, Math.min(length, x));
            updated.case = inputs.case.value;
          }
        }
      } else {
        const x = parseNum(inputs.x);
        if (x === null) valid = false;
        else {
          updated.x = Math.max(0, Math.min(length, x));
          updated.type = inputs.type.value;
        }
      }

      if (!valid) return;
      this.close();
      onApply(selection, updated);
    };

    applyBtn.addEventListener("click", handleApply);

    deleteBtn.addEventListener("click", () => {
      this.close();
      onDelete(selection);
    });

    panel.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleApply();
      } else if (e.key === "Escape") {
        e.preventDefault();
        this.close();
      }
    });

    this.host.append(panel);
    this.panel = panel;

    // Positioning
    const hostRect = this.host.getBoundingClientRect();
    const panelRect = panel.getBoundingClientRect();
    const pw = panelRect.width || 280;
    const ph = panelRect.height || 220;

    let targetX = screenPoint ? (screenPoint.x - hostRect.left) : (hostRect.width / 2);
    let targetY = screenPoint ? (screenPoint.y - hostRect.top) : (hostRect.height / 2);

    let left = targetX - pw / 2;
    left = Math.max(8, Math.min(left, hostRect.width - pw - 8));

    let top = targetY + 12;
    if (top + ph > hostRect.height - 8) {
      top = Math.max(8, targetY - ph - 12);
    }
    panel.style.left = `${Math.round(left)}px`;
    panel.style.top = `${Math.round(top)}px`;

    // Focus first input
    const firstInput = panel.querySelector("input, select");
    if (firstInput) {
      setTimeout(() => {
        firstInput.focus();
        if (firstInput.select) firstInput.select();
      }, 0);
    }

    // Delay binding outside listener so opening click doesn't close it immediately
    setTimeout(() => {
      if (this.panel) {
        document.addEventListener("pointerdown", this._outsideHandler, true);
      }
    }, 50);
  }
}
