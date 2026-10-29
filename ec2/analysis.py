"""Matrix Stiffness Method 2D Beam Analysis Engine.

Integrated from the client's BeamViz Pro analysis tool. Provides full 1D
finite-element beam analysis for arbitrary continuous beams with nodes,
elements, support conditions, and member span loads (point loads, UDLs,
concentrated moments, and linear/trapezoidal loads).

Solves global stiffness equations Ku = F, support reactions, member end
forces, continuous shear (V), bending moment (M), and deflection curves.
"""
import math
import numpy as np

__all__ = [
    "BeamAnalysis",
    "solve_beam",
    "MAP_LENGTH",
    "MAP_E",
    "MAP_I",
    "MAP_FORCE",
    "MAP_MOMENT",
    "MAP_DIST_LOAD",
]

MAP_LENGTH = {"m": 1.0, "cm": 0.01, "mm": 0.001, "in": 0.0254, "ft": 0.3048}
MAP_E = {"GPa": 1e6, "MPa": 1e3, "kPa": 1.0, "psi": 6.89476, "ksi": 6894.76}
MAP_I = {"m⁴": 1.0, "cm⁴": 1e-8, "mm⁴": 1e-12, "in⁴": 4.162314e-7, "ft⁴": 0.00863097}
MAP_FORCE = {"kN": 1.0, "N": 0.001, "lb": 0.00444822, "kip": 4.44822}
MAP_MOMENT = {"kN·m": 1.0, "N·m": 0.001, "lb·ft": 0.00135582, "kip·ft": 1.35582}
MAP_DIST_LOAD = {"kN/m": 1.0, "N/m": 0.001, "lb/ft": 0.0145939, "kip/ft": 14.5939}


class BeamAnalysis:
    """Matrix stiffness solver for 1D beam structures."""

    def __init__(self):
        self.reset_data()

    def reset_data(self):
        self.num_nodes = 0
        self.num_elements = 0
        self.nodes = {}           # {node_idx: x_coordinate (m)}
        self.elements = {}        # {elem_idx: (start_node_idx, end_node_idx)}
        self.E = {}               # {elem_idx: E in kPa (kN/m²)}
        self.I = {}               # {elem_idx: I in m⁴}
        self.L = {}               # {elem_idx: length in m}
        self.supports = {}        # {node_idx: [fix_vertical (0/1), fix_rotational (0/1)]}
        self.point_loads = []     # [{'node': n, 'Fy': kN, 'M': kNm}]
        self.member_point_loads = []  # [{'elem': eid, 'W': kN, 'l1': m}]
        self.member_udl = []      # [{'elem': eid, 'w': kN/m, 'l1': m, 'l2': m}]
        self.member_moment = []   # [{'elem': eid, 'M0': kNm, 'l1': m}]
        self.member_linear_load = []  # [{'elem': eid, 'w1': kN/m, 'w2': kN/m, 'l1': m, 'l2': m}]
        self.total_dofs = 0
        self.K_global = None
        self.F_global = None
        self.displacements = None
        self.reactions = None
        self.member_end_forces = {}
        self.Qf = {}

    def element_stiffness_matrix(self, elem_id):
        E, I, L = self.E[elem_id], self.I[elem_id], self.L[elem_id]
        EI = E * I
        L2, L3 = L * L, L * L * L
        return (EI / L3) * np.array([
            [12.0, 6.0 * L, -12.0, 6.0 * L],
            [6.0 * L, 4.0 * L2, -6.0 * L, 2.0 * L2],
            [-12.0, -6.0 * L, 12.0, -6.0 * L],
            [6.0 * L, 2.0 * L2, -6.0 * L, 4.0 * L2]
        ])

    def fixed_end_forces_udl(self, w, l1, l2, L):
        """Fixed end forces for partial UDL from l1 to l2 (downward load w is negative)."""
        dl1 = l2 - l1
        dl3 = l2**3 - l1**3
        dl4 = l2**4 - l1**4
        return np.array([
            (w / L**3) * (L**3 * dl1 - L * dl3 + 0.5 * dl4),
            (w / L**2) * (0.5 * L**2 * (l2**2 - l1**2) - (2.0 / 3.0) * L * dl3 + 0.25 * dl4),
            (w / L**3) * (L * dl3 - 0.5 * dl4),
            (-w / L**2) * ((1.0 / 3.0) * L * dl3 - 0.25 * dl4)
        ])

    def fixed_end_forces_point_load(self, W, l1, L):
        """Fixed end forces for point load W at distance l1 (downward load W is negative)."""
        l2 = L - l1
        return np.array([
            W * l2**2 * (3.0 * l1 + l2) / L**3,
            W * l1 * l2**2 / L**2,
            W * l1**2 * (l1 + 3.0 * l2) / L**3,
            -W * l1**2 * l2 / L**2
        ])

    def fixed_end_forces_moment(self, M0, l1, L):
        """Fixed end forces for concentrated moment M0 at distance l1."""
        l2 = L - l1
        return np.array([
            -6.0 * M0 * l1 * l2 / L**3,
            M0 * l2 * (l2 - 2.0 * l1) / L**2,
            6.0 * M0 * l1 * l2 / L**3,
            M0 * l1 * (2.0 * l2 - l1) / L**2
        ])

    def fixed_end_forces_linear_load(self, w1, w2, l1, l2, L):
        """Fixed end forces for linearly varying load from w1 at l1 to w2 at l2."""
        c = l2 - l1
        if abs(c) < 1e-12:
            return np.zeros(4)
        A = (w1 * l2 - w2 * l1) / c
        B = (w2 - w1) / c
        dl1 = c
        dl2 = l2**2 - l1**2
        dl3 = l2**3 - l1**3
        dl4 = l2**4 - l1**4
        dl5 = l2**5 - l1**5
        Fs_b = (1.0 / L**3) * (
            A * (L**3 * dl1 - L * dl3 + 0.5 * dl4)
            + B * (0.5 * L**3 * dl2 - 0.75 * L * dl4 + 0.4 * dl5)
        )
        Fm_b = (1.0 / L**2) * (
            A * (0.5 * L**2 * dl2 - (2.0 / 3.0) * L * dl3 + 0.25 * dl4)
            + B * ((1.0 / 3.0) * L**2 * dl3 - 0.5 * L * dl4 + 0.2 * dl5)
        )
        Fs_e = (1.0 / L**3) * (
            A * (L * dl3 - 0.5 * dl4)
            + B * (0.75 * L * dl4 - 0.4 * dl5)
        )
        Fm_e = (-1.0 / L**2) * (
            A * ((1.0 / 3.0) * L * dl3 - 0.25 * dl4)
            + B * (0.25 * L * dl4 - 0.2 * dl5)
        )
        return np.array([Fs_b, Fm_b, Fs_e, Fm_e])

    def _get_elem_dofs(self, elem):
        s, e = self.elements[elem]
        return [2 * s, 2 * s + 1, 2 * e, 2 * e + 1]

    def assemble_global_stiffness(self):
        self.K_global = np.zeros((self.total_dofs, self.total_dofs))
        for i in range(self.num_elements):
            k = self.element_stiffness_matrix(i)
            dofs = self._get_elem_dofs(i)
            for a in range(4):
                for b in range(4):
                    self.K_global[dofs[a], dofs[b]] += k[a, b]

    def assemble_force_vector(self):
        self.F_global = np.zeros(self.total_dofs)
        for load in self.point_loads:
            n = load["node"]
            self.F_global[2 * n] -= load["Fy"]
            self.F_global[2 * n + 1] += load["M"]

        load_map = [
            (self.member_udl, lambda ld: self.fixed_end_forces_udl(ld["w"], ld["l1"], ld["l2"], self.L[ld["elem"]])),
            (self.member_point_loads, lambda ld: self.fixed_end_forces_point_load(ld["W"], ld["l1"], self.L[ld["elem"]])),
            (self.member_moment, lambda ld: self.fixed_end_forces_moment(ld["M0"], ld["l1"], self.L[ld["elem"]])),
            (self.member_linear_load, lambda ld: self.fixed_end_forces_linear_load(ld["w1"], ld["w2"], ld["l1"], ld["l2"], self.L[ld["elem"]]))
        ]
        for loads, func in load_map:
            for ld in loads:
                fef = func(ld)
                dofs = self._get_elem_dofs(ld["elem"])
                for i in range(4):
                    self.F_global[dofs[i]] -= fef[i]

    def apply_boundary_conditions_and_solve(self):
        rest = self.get_restrained_dofs()
        free = [i for i in range(self.total_dofs) if i not in rest]
        if not free:
            self.displacements = np.zeros(self.total_dofs)
            self.reactions = -self.F_global.copy()
            return

        K_ff = self.K_global[np.ix_(free, free)]
        F_f = self.F_global[free]
        d_f = np.linalg.solve(K_ff, F_f)
        self.displacements = np.zeros(self.total_dofs)
        for i, d in enumerate(free):
            self.displacements[d] = d_f[i]
        self.reactions = np.zeros(self.total_dofs)
        for d in rest:
            self.reactions[d] = self.K_global[d, :] @ self.displacements - self.F_global[d]

    def calculate_member_end_forces(self):
        for eid in range(self.num_elements):
            k = self.element_stiffness_matrix(eid)
            dofs = self._get_elem_dofs(eid)
            d_elem = np.array([self.displacements[d] for d in dofs])
            fef = np.zeros(4)
            for ld in self.member_udl:
                if ld["elem"] == eid:
                    fef += self.fixed_end_forces_udl(ld["w"], ld["l1"], ld["l2"], self.L[eid])
            for ld in self.member_point_loads:
                if ld["elem"] == eid:
                    fef += self.fixed_end_forces_point_load(ld["W"], ld["l1"], self.L[eid])
            for ld in self.member_moment:
                if ld["elem"] == eid:
                    fef += self.fixed_end_forces_moment(ld["M0"], ld["l1"], self.L[eid])
            for ld in self.member_linear_load:
                if ld["elem"] == eid:
                    fef += self.fixed_end_forces_linear_load(ld["w1"], ld["w2"], ld["l1"], ld["l2"], self.L[eid])
            self.Qf[eid] = fef.copy()
            self.member_end_forces[eid] = k @ d_elem + fef

    def get_restrained_dofs(self):
        res = []
        for n, c in self.supports.items():
            if c[0] == 1:
                res.append(2 * n)
            if c[1] == 1:
                res.append(2 * n + 1)
        return sorted(res)

    def run_analysis(self):
        self.assemble_global_stiffness()
        self.assemble_force_vector()
        self.apply_boundary_conditions_and_solve()
        self.calculate_member_end_forces()

    def get_diagram_data(self, num_points=50):
        """Computes continuous internal actions along the beam.

        Returns (x, V, M, d):
          x: global position along beam (m)
          V: shear force (kN)
          M: bending moment (kNm, sagging positive)
          d: vertical deflection (m, downward positive)
        """
        x_all, v_all, m_all, d_all = [], [], [], []
        for eid in range(self.num_elements):
            L = self.L[eid]
            s_node, e_node = self.elements[eid]
            x_start = self.nodes[s_node]
            V1 = self.member_end_forces[eid][0]
            M1 = self.member_end_forces[eid][1]
            v1, t1, v2, t2 = [self.displacements[d] for d in self._get_elem_dofs(eid)]

            pts = num_points if eid == self.num_elements - 1 else num_points
            for i in range(pts + 1):
                # Avoid duplicate point at shared internal nodes
                if i == 0 and eid > 0:
                    continue
                x_loc = L * i / pts
                x_glob = x_start + x_loc
                xi = x_loc / L if L > 0 else 0.0

                # Hermite cubic shape functions for transverse deflection
                N1 = 1.0 - 3.0 * xi**2 + 2.0 * xi**3
                N2 = L * xi * (1.0 - xi)**2
                N3 = 3.0 * xi**2 - 2.0 * xi**3
                N4 = L * (xi**3 - xi**2)
                deflection = N1 * v1 + N2 * t1 + N3 * v2 + N4 * t2

                # Static equilibrium for internal shear and moment
                # V1 and M1 are end reactions in local member coordinate
                # With downward loads entered as negative (w < 0, W < 0):
                V = V1
                M = -M1 + V1 * x_loc
                for ld in self.member_point_loads:
                    if ld["elem"] == eid and x_loc >= ld["l1"]:
                        V -= ld["W"]
                        M -= ld["W"] * (x_loc - ld["l1"])
                for ld in self.member_udl:
                    if ld["elem"] == eid:
                        if x_loc > ld["l2"]:
                            dx = ld["l2"] - ld["l1"]
                            V -= ld["w"] * dx
                            M -= ld["w"] * dx * (x_loc - (ld["l1"] + ld["l2"]) / 2.0)
                        elif x_loc > ld["l1"]:
                            dx = x_loc - ld["l1"]
                            V -= ld["w"] * dx
                            M -= ld["w"] * dx * (dx / 2.0)
                for ld in self.member_moment:
                    if ld["elem"] == eid and x_loc >= ld["l1"]:
                        M -= ld["M0"]
                for ld in self.member_linear_load:
                    if ld["elem"] == eid:
                        w1, w2, l1s, l2s = ld["w1"], ld["w2"], ld["l1"], ld["l2"]
                        if x_loc >= l2s:
                            c = l2s - l1s
                            Wa = (w1 + w2) * c / 2.0
                            xa = l1s + c * (w1 + 2.0 * w2) / (3.0 * (w1 + w2)) if abs(w1 + w2) > 1e-12 else l1s
                            V -= Wa
                            M -= Wa * (x_loc - xa)
                        elif x_loc > l1s:
                            dx = x_loc - l1s
                            w_at_x = w1 + (w2 - w1) * (dx / (l2s - l1s))
                            V -= (w1 + w_at_x) * dx / 2.0
                            M -= (dx**2 / 6.0) * (2.0 * w1 + w_at_x)

                x_all.append(float(x_glob))
                v_all.append(float(V))
                m_all.append(float(M))
                d_all.append(float(deflection))

        # Standard Eurocode sign convention:
        # Sagging moment is positive (tension at bottom)
        # Shear force starts positive at left support under downward load
        return np.array(x_all), -np.array(v_all), -np.array(m_all), np.array(d_all)

    def get_key_indices(self, y_vals, x_vals):
        """Smart feature detection for diagrams: nodes, zero-crossings, peaks."""
        key_idxs = set()
        for xn in self.nodes.values():
            idx = int(np.argmin(np.abs(x_vals - xn)))
            key_idxs.add(idx)
        for i in range(len(y_vals) - 1):
            if y_vals[i] * y_vals[i + 1] < 0:
                key_idxs.add(i)
        for i in range(1, len(y_vals) - 1):
            if (y_vals[i] > y_vals[i - 1] and y_vals[i] > y_vals[i + 1]) or \
               (y_vals[i] < y_vals[i - 1] and y_vals[i] < y_vals[i + 1]):
                key_idxs.add(i)

        sorted_idxs = sorted(list(key_idxs))
        filtered_idxs = []
        min_dist = max(1, int(len(x_vals) * 0.05))
        for idx in sorted_idxs:
            if not filtered_idxs or (idx - filtered_idxs[-1]) >= min_dist:
                filtered_idxs.append(idx)
            else:
                if abs(y_vals[idx]) > abs(y_vals[filtered_idxs[-1]]):
                    filtered_idxs[-1] = idx
        return filtered_idxs


def solve_beam(span_m, system="simple", loads=None, supports=None, E_kpa=33e6, I_m4=0.003, self_weight=0.0, num_points=60):
    """High-level beam solver integrating with EC2 concrete design.

    Parameters:
      span_m: total beam span in metres (or list of span lengths for continuous beams)
      system: "simple", "cantilever", "end", "interior", or "custom"
      loads: list of load dicts:
         - {'type': 'point', 'W': kN, 'x': m}
         - {'type': 'udl', 'w': kN/m, 'l1': m, 'l2': m}
         - {'type': 'moment', 'M0': kNm, 'x': m}
         - {'type': 'linear', 'w1': kN/m, 'w2': kN/m, 'l1': m, 'l2': m}
      supports: custom supports (dict of {node_or_x: [fix_v, fix_m]} or list of dicts)
      E_kpa: Elastic modulus in kPa (kN/m²), scalar or list/dict
      I_m4: Second moment of area in m⁴, scalar or list/dict
      self_weight: Self weight UDL in kN/m (positive, acting downwards)
    """
    if isinstance(span_m, (int, float)):
        spans = [float(span_m)]
    else:
        spans = [float(s) for s in span_m]

    total_len = sum(spans)
    loads = loads or []

    # Collect key x-coordinates where nodes should be placed for exact solution
    x_nodes = [0.0]
    curr_x = 0.0
    support_xs = [0.0]
    span_bounds = []
    for s in spans:
        x_start_span = curr_x
        n_sub = max(4, int(math.ceil(s / 1.0)))
        for j in range(1, n_sub):
            x_nodes.append(round(curr_x + j * (s / n_sub), 4))
        curr_x += s
        x_nodes.append(round(curr_x, 4))
        support_xs.append(round(curr_x, 4))
        span_bounds.append((x_start_span, curr_x))

    if supports is not None:
        if isinstance(supports, dict):
            for k in supports.keys():
                if isinstance(k, (int, float)):
                    x_nodes.append(round(float(k), 4))
        elif isinstance(supports, list):
            for sp in supports:
                if isinstance(sp, dict) and "x" in sp:
                    x_nodes.append(round(float(sp["x"]), 4))

    for ld in loads:
        ltype = ld.get("type")
        if ltype == "point":
            x_nodes.append(round(float(ld.get("x", 0.0)), 4))
        elif ltype == "moment":
            x_nodes.append(round(float(ld.get("x", 0.0)), 4))
        elif ltype in ("udl", "linear"):
            x_nodes.append(round(float(ld.get("l1", 0.0)), 4))
            x_nodes.append(round(float(ld.get("l2", total_len)), 4))

    # Keep unique within bounds [0, total_len]
    x_nodes = sorted(list(set(x for x in x_nodes if 0.0 <= x <= total_len)))
    if len(x_nodes) < 2:
        x_nodes = [0.0, total_len]

    node_map = {i: x for i, x in enumerate(x_nodes)}
    x_to_node = {x: i for i, x in enumerate(x_nodes)}

    a = BeamAnalysis()
    a.num_nodes = len(x_nodes)
    a.nodes = node_map
    a.total_dofs = 2 * a.num_nodes
    a.num_elements = len(x_nodes) - 1

    def _resolve_prop(prop, x_mid):
        if isinstance(prop, (int, float)):
            return float(prop)
        if isinstance(prop, (list, tuple)):
            if len(prop) == 0:
                return 1.0
            if isinstance(prop[0], dict):
                for item in prop:
                    x1 = float(item.get("l1", item.get("x1", 0.0)))
                    x2 = float(item.get("l2", item.get("x2", total_len)))
                    if x1 <= x_mid <= x2:
                        return float(item.get("val", item.get("value", item.get("I", item.get("E", 1.0)))))
                return float(prop[-1].get("val", prop[-1].get("value", prop[-1].get("I", prop[-1].get("E", 1.0)))))
            for s_idx, (sx0, sx1) in enumerate(span_bounds):
                if sx0 <= x_mid <= sx1:
                    return float(prop[min(s_idx, len(prop) - 1)])
            return float(prop[0])
        return float(prop)

    for i in range(a.num_elements):
        a.elements[i] = (i, i + 1)
        x_mid = 0.5 * (x_nodes[i] + x_nodes[i + 1])
        a.E[i] = _resolve_prop(E_kpa, x_mid)
        a.I[i] = _resolve_prop(I_m4, x_mid)
        a.L[i] = float(x_nodes[i + 1] - x_nodes[i])

    # Assign boundary conditions
    # 0 = free, 1 = fixed
    # [fix_vert, fix_rot]
    if supports is not None:
        if isinstance(supports, dict):
            for k, val in supports.items():
                if isinstance(k, (int, np.integer)) and int(k) in a.nodes:
                    a.supports[int(k)] = [int(val[0]), int(val[1])]
                else:
                    x_val = float(k)
                    best_n = min(a.nodes.keys(), key=lambda n: abs(a.nodes[n] - x_val))
                    a.supports[best_n] = [int(val[0]), int(val[1])]
        elif isinstance(supports, list):
            for sp in supports:
                if isinstance(sp, dict):
                    x_val = float(sp.get("x", 0.0))
                    best_n = min(a.nodes.keys(), key=lambda n: abs(a.nodes[n] - x_val))
                    a.supports[best_n] = [int(sp.get("fix_v", 1)), int(sp.get("fix_m", 0))]
    elif system == "cantilever":
        # Fixed at node 0, all others free
        a.supports[0] = [1, 1]
    elif system == "simple":
        # Pin at start, roller at end
        a.supports[0] = [1, 0]
        a.supports[x_to_node[total_len]] = [1, 0]
    elif system == "end":
        # Pin at start, intermediate supports roller, continuous end
        a.supports[0] = [1, 0]
        for sx in support_xs[1:]:
            if sx in x_to_node:
                a.supports[x_to_node[sx]] = [1, 0]
    elif system == "interior":
        # All support points pinned/roller
        for sx in support_xs:
            if sx in x_to_node:
                a.supports[x_to_node[sx]] = [1, 0]
    else:
        a.supports[0] = [1, 0]
        a.supports[x_to_node[total_len]] = [1, 0]

    # Apply self-weight across all elements (downward load is negative)
    if self_weight > 0:
        for i in range(a.num_elements):
            a.member_udl.append({
                "elem": i,
                "w": -float(self_weight),
                "l1": 0.0,
                "l2": a.L[i]
            })

    # Apply member loads
    for ld in loads:
        ltype = ld.get("type")
        if ltype == "point":
            x_pos = float(ld.get("x", 0.0))
            w_val = float(ld.get("W", 0.0))
            if x_pos in x_to_node:
                n = x_to_node[x_pos]
                a.point_loads.append({"node": n, "Fy": -w_val, "M": 0.0})
            else:
                for eid in range(a.num_elements):
                    x0 = a.nodes[a.elements[eid][0]]
                    x1 = a.nodes[a.elements[eid][1]]
                    if x0 <= x_pos <= x1:
                        a.member_point_loads.append({"elem": eid, "W": -w_val, "l1": x_pos - x0})
                        break

        elif ltype == "moment":
            x_pos = float(ld.get("x", 0.0))
            m_val = float(ld.get("M0", 0.0))
            if x_pos in x_to_node:
                n = x_to_node[x_pos]
                a.point_loads.append({"node": n, "Fy": 0.0, "M": m_val})
            else:
                for eid in range(a.num_elements):
                    x0 = a.nodes[a.elements[eid][0]]
                    x1 = a.nodes[a.elements[eid][1]]
                    if x0 <= x_pos <= x1:
                        a.member_moment.append({"elem": eid, "M0": m_val, "l1": x_pos - x0})
                        break

        elif ltype == "udl":
            w_val = float(ld.get("w", 0.0))
            l1_abs = max(0.0, float(ld.get("l1", 0.0)))
            l2_abs = min(total_len, float(ld.get("l2", total_len)))
            for eid in range(a.num_elements):
                x0 = a.nodes[a.elements[eid][0]]
                x1 = a.nodes[a.elements[eid][1]]
                overlap_start = max(x0, l1_abs)
                overlap_end = min(x1, l2_abs)
                if overlap_end > overlap_start:
                    a.member_udl.append({
                        "elem": eid,
                        "w": -w_val,
                        "l1": overlap_start - x0,
                        "l2": overlap_end - x0
                    })

        elif ltype == "linear":
            w1 = float(ld.get("w1", 0.0))
            w2 = float(ld.get("w2", 0.0))
            l1_abs = max(0.0, float(ld.get("l1", 0.0)))
            l2_abs = min(total_len, float(ld.get("l2", total_len)))
            span_ld = l2_abs - l1_abs
            for eid in range(a.num_elements):
                x0 = a.nodes[a.elements[eid][0]]
                x1 = a.nodes[a.elements[eid][1]]
                overlap_start = max(x0, l1_abs)
                overlap_end = min(x1, l2_abs)
                if overlap_end > overlap_start and span_ld > 0:
                    t_start = (overlap_start - l1_abs) / span_ld
                    t_end = (overlap_end - l1_abs) / span_ld
                    w_start = w1 + (w2 - w1) * t_start
                    w_end = w1 + (w2 - w1) * t_end
                    a.member_linear_load.append({
                        "elem": eid,
                        "w1": -w_start,
                        "w2": -w_end,
                        "l1": overlap_start - x0,
                        "l2": overlap_end - x0
                    })

    # Solve the system
    a.run_analysis()

    # Extract diagram data
    pts_per_elem = max(10, num_points // max(1, a.num_elements))
    x_pts, v_pts, m_pts, d_pts = a.get_diagram_data(pts_per_elem)

    # In structural engineering sign convention:
    # Sagging moment is positive (tension at bottom), hogging is negative (tension at top)
    # Deflection downward is positive
    max_sagging = float(np.max(m_pts)) if len(m_pts) else 0.0
    max_hogging = float(np.min(m_pts)) if len(m_pts) else 0.0
    abs_max_m = float(np.max(np.abs(m_pts))) if len(m_pts) else 0.0
    abs_max_v = float(np.max(np.abs(v_pts))) if len(v_pts) else 0.0
    max_defl_m = float(np.max(np.abs(d_pts))) if len(d_pts) else 0.0

    # Build reactions list
    reactions_list = []
    for n in sorted(a.supports.keys()):
        reactions_list.append({
            "node": n + 1,
            "x": float(a.nodes[n]),
            "Ry": float(a.reactions[2 * n]),
            "M": float(a.reactions[2 * n + 1])
        })

    # Build displacements list
    displacements_list = []
    for n in range(a.num_nodes):
        displacements_list.append({
            "node": n + 1,
            "x": float(a.nodes[n]),
            "dy_mm": float(a.displacements[2 * n] * 1000.0),
            "theta_rad": float(a.displacements[2 * n + 1])
        })

    # Member end forces list
    member_forces_list = []
    for eid in range(a.num_elements):
        f = a.member_end_forces[eid]
        member_forces_list.append({
            "elem": eid + 1,
            "V1": float(f[0]),
            "M1": float(f[1]),
            "V2": float(f[2]),
            "M2": float(f[3])
        })

    key_idxs = a.get_key_indices(m_pts, x_pts)
    key_points = []
    for idx in key_idxs:
        key_points.append({
            "x": float(x_pts[idx]),
            "M": float(m_pts[idx]),
            "V": float(v_pts[idx]),
            "d_mm": float(d_pts[idx] * 1000.0)
        })

    return {
        "analysis": a,
        "x": [round(float(x), 4) for x in x_pts],
        "M": [round(float(m), 3) for m in m_pts],
        "V": [round(float(v), 3) for v in v_pts],
        "delta_mm": [round(float(d * 1000.0), 3) for d in d_pts],
        "max_sagging_kNm": max_sagging,
        "max_hogging_kNm": max_hogging,
        "abs_max_M_kNm": abs_max_m,
        "abs_max_V_kN": abs_max_v,
        "max_deflection_mm": max_defl_m * 1000.0,
        "reactions": reactions_list,
        "displacements": displacements_list,
        "member_forces": member_forces_list,
        "key_points": key_points
    }
