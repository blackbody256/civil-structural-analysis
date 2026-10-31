// The pad foundation's worked examples, shared by the input page and the home page card.
const PROJECT = { name: "", ref: "", engineer: "", date: "" };
const MATERIALS = { concrete: "C30/37", fyk: 500, ductility: "B", dg: 20, gamma_c: 1.5, gamma_s: 1.15, alpha_cc: 0.85 };

export const EXAMPLES = {
  pass: {
    project: { ...PROJECT },
    column: { cx: 400, cy: 400 },
    base: { L: 3.2, B: 3.0, h: 600, soil_depth: 0.5, gamma_soil: 18 },
    soil: { type: "stiff_clay", q_allow: 200 },
    actions: { Gk: 1000, Qk: 500, MGk: 20, MQk: 60, category: "B" },
    materials: { ...MATERIALS },
    reinforcement: { x_dia: 16, x_s: 150, y_dia: 16, y_s: 150, cover: 50, delta_c_dev: 10, cast: "blinding" },
    durability: { exposure: "XC2", cement_group: "All" },
  },
  fail: {
    project: { ...PROJECT },
    column: { cx: 300, cy: 300 },
    base: { L: 2.6, B: 2.6, h: 450, soil_depth: 0.5, gamma_soil: 18 },
    soil: { type: "firm_clay", q_allow: 150 },
    actions: { Gk: 1000, Qk: 500, MGk: 20, MQk: 150, category: "B" },
    materials: { ...MATERIALS, concrete: "C25/30" },
    reinforcement: { x_dia: 12, x_s: 200, y_dia: 12, y_s: 200, cover: 50, delta_c_dev: 10, cast: "soil" },
    durability: { exposure: "XC2", cement_group: "All" },
  },
};
