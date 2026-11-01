// The pad foundation's worked examples (Elisha's), shared by the input page and the home page card.

export const EXAMPLES = {
  // 450 x 450 column on a 3.4 x 3.4 x 0.7 m base on compact sand
  pass: {
    project: { name: "", ref: "", engineer: "", date: "" },
    column: { cx: 450, cy: 450 },
    base: { L: 3.4, B: 3.4, h: 700, soil_depth: 0.6, gamma_soil: 19 },
    soil: { type: "compact_sand", q_allow: 300 },
    actions: { Gk: 1600, Qk: 750, MGk: 30, MQk: 45, category: "B" },
    materials: { concrete: "C32/40", fyk: 500, ductility: "B", dg: 20, gamma_c: 1.5, gamma_s: 1.15, alpha_cc: 0.85 },
    reinforcement: { x_dia: 20, x_s: 175, y_dia: 20, y_s: 175, cover: 50, delta_c_dev: 10, cast: "blinding" },
    durability: { exposure: "XC2", cement_group: "All" },
  },
  // the base too small and too thin for the load, cast against the soil
  fail: {
    project: { name: "", ref: "", engineer: "", date: "" },
    column: { cx: 350, cy: 350 },
    base: { L: 3, B: 3, h: 650, soil_depth: 0.6, gamma_soil: 19 },
    soil: { type: "boulder_clay", q_allow: 250 },
    actions: { Gk: 1600, Qk: 750, MGk: 30, MQk: 120, category: "B" },
    materials: { concrete: "C25/30", fyk: 500, ductility: "B", dg: 20, gamma_c: 1.5, gamma_s: 1.15, alpha_cc: 0.85 },
    reinforcement: { x_dia: 16, x_s: 200, y_dia: 16, y_s: 200, cover: 40, delta_c_dev: 10, cast: "soil" },
    durability: { exposure: "XC2", cement_group: "All" },
  },
};
