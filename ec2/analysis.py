"""Beam analysis by the matrix stiffness method.

The solver class is the client's BeamViz Pro engine ("Beam Pro.py") without its user interface.
`analyse()` wraps it for the design checks: it builds the analytical model the way a textbook
does (a node at each end, at each support and where the stiffness changes), solves it on a finer
mesh so that every load acts exactly at a node or inside one element, and returns the reactions,
member end forces, joint displacements and the shear, moment and deflection along the beam.

Conventions of `analyse()`: x in m from the left end, loads in kN and kN/m acting downwards,
applied moments in kNm clockwise, reactions upwards and anticlockwise, sagging moments and
downward deflections positive.
"""
import math

import numpy as np

__all__ = ["BeamAnalysis", "AnalysisError", "analyse", "SUPPORT_TYPES"]

# support type → (vertical restraint, rotational restraint)
SUPPORT_TYPES = {"pin": (1, 0), "roller": (1, 0), "fixed": (1, 1)}


class AnalysisError(ValueError):
    """The beam cannot be analysed, for example because it is unstable."""


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



# ---------------------------------------------------------------- wrapper for the design checks

def _inertia_at(inertia, x):
    if isinstance(inertia, (int, float)):
        return float(inertia)
    for seg in inertia:
        if seg["x1"] - 1e-9 <= x <= seg["x2"] + 1e-9:
            return float(seg["I"])
    return float(inertia[-1]["I"])


def _internal(a, eid, x_loc):
    """Shear, moment and deflection at x_loc inside element eid, in the client's convention."""
    L = a.L[eid]
    V1, M1 = a.member_end_forces[eid][0], a.member_end_forces[eid][1]
    v1, t1, v2, t2 = [a.displacements[d] for d in a._get_elem_dofs(eid)]
    xi = x_loc / L
    deflection = ((1 - 3 * xi**2 + 2 * xi**3) * v1 + L * xi * (1 - xi)**2 * t1
                  + (3 * xi**2 - 2 * xi**3) * v2 + L * (xi**3 - xi**2) * t2)
    V, M = V1, -M1 + V1 * x_loc
    for ld in a.member_udl:
        if ld["elem"] == eid and x_loc > ld["l1"]:
            dx = min(x_loc, ld["l2"]) - ld["l1"]
            V -= ld["w"] * dx
            M -= ld["w"] * dx * (x_loc - ld["l1"] - dx / 2)
    for ld in a.member_linear_load:
        if ld["elem"] == eid and x_loc > ld["l1"]:
            w1, w2, l1, l2 = ld["w1"], ld["w2"], ld["l1"], ld["l2"]
            c = min(x_loc, l2) - l1
            w_c = w1 + (w2 - w1) * c / (l2 - l1)
            force = (w1 + w_c) * c / 2
            centroid = l1 + (c / 3 * (w1 + 2 * w_c) / (w1 + w_c) if abs(w1 + w_c) > 1e-12 else c / 2)
            V -= force
            M -= force * (x_loc - centroid)
    return V, M, deflection


def _key(x):
    return round(float(x), 6)


def analyse(length, supports, loads, E=33e6, inertia=0.003):
    """Analyse a straight beam.

    length    total length in m
    supports  [{"x": m, "type": "pin" | "roller" | "fixed"}]
    loads     [{"type": "point", "W", "x"}, {"type": "udl", "w", "x1", "x2"},
               {"type": "linear", "w1", "w2", "x1", "x2"}, {"type": "moment", "M", "x"}]
    E         kPa (kN/m²)
    inertia   m⁴, or [{"x1", "x2", "I"}] for a beam whose stiffness changes along its length
    """
    L = float(length)
    if not supports:
        raise AnalysisError("Add at least one support.")
    sups = {}
    for sp in supports:
        x = _key(sp["x"])
        if sp["type"] == "fixed" or x not in sups:
            sups[x] = sp["type"]
    segments = [] if isinstance(inertia, (int, float)) else inertia

    # analytical model: ends, supports and changes of stiffness
    model_x = sorted({0.0, _key(L), *sups, *(_key(s[k]) for s in segments for k in ("x1", "x2") if 0 < s[k] < L)})
    # mesh: the model nodes, every load position and a fine subdivision for the deflected shape
    mesh_x = set(model_x)
    for ld in loads:
        for k in ("x", "x1", "x2"):
            if k in ld:
                mesh_x.add(_key(ld[k]))
    target = L / 48
    for x0, x1 in zip(model_x, model_x[1:]):
        n = max(4, math.ceil((x1 - x0) / target))
        mesh_x.update(_key(x0 + (x1 - x0) * i / n) for i in range(1, n))
    mesh_x = sorted(x for x in mesh_x if 0 <= x <= L)
    merged = [mesh_x[0]]
    for x in mesh_x[1:]:
        if x - merged[-1] > 1e-6 * max(L, 1):
            merged.append(x)
    mesh_x = merged
    index = {x: i for i, x in enumerate(mesh_x)}

    def node_at(x):
        x = _key(x)
        return index[x] if x in index else min(index.values(), key=lambda i: abs(mesh_x[i] - x))

    a = BeamAnalysis()
    a.num_nodes = len(mesh_x)
    a.nodes = dict(enumerate(mesh_x))
    a.total_dofs = 2 * a.num_nodes
    a.num_elements = a.num_nodes - 1
    for i in range(a.num_elements):
        a.elements[i] = (i, i + 1)
        a.E[i] = float(E)
        a.I[i] = _inertia_at(inertia, 0.5 * (mesh_x[i] + mesh_x[i + 1]))
        a.L[i] = mesh_x[i + 1] - mesh_x[i]
    for x, kind in sups.items():
        a.supports[node_at(x)] = list(SUPPORT_TYPES[kind])

    # the client's engine takes downward loads as negative and moments with the opposite sense
    for ld in loads:
        kind = ld["type"]
        if kind == "point":
            a.point_loads.append({"node": node_at(ld["x"]), "Fy": -ld["W"], "M": 0.0})
        elif kind == "moment":
            a.point_loads.append({"node": node_at(ld["x"]), "Fy": 0.0, "M": ld["M"]})
        elif kind in ("udl", "linear"):
            x1, x2 = ld["x1"], ld["x2"]
            w1, w2 = (ld["w"], ld["w"]) if kind == "udl" else (ld["w1"], ld["w2"])
            for e in range(a.num_elements):
                s, f = max(mesh_x[e], x1), min(mesh_x[e + 1], x2)
                if f - s <= 1e-9:
                    continue
                ws = w1 + (w2 - w1) * (s - x1) / (x2 - x1)
                wf = w1 + (w2 - w1) * (f - x1) / (x2 - x1)
                l1, l2 = s - mesh_x[e], f - mesh_x[e]
                if abs(ws - wf) < 1e-12:
                    a.member_udl.append({"elem": e, "w": -ws, "l1": l1, "l2": l2})
                else:
                    a.member_linear_load.append({"elem": e, "w1": -ws, "w2": -wf, "l1": l1, "l2": l2})

    a.assemble_global_stiffness()
    a.assemble_force_vector()
    restrained = a.get_restrained_dofs()
    free = [d for d in range(a.total_dofs) if d not in restrained]
    if free and np.linalg.matrix_rank(a.K_global[np.ix_(free, free)]) < len(free):
        raise AnalysisError("The beam is unstable with these supports: add a support or make one end fixed.")
    a.apply_boundary_conditions_and_solve()
    a.calculate_member_end_forces()
    return _results(a, L, model_x, sups, segments, E, inertia)


def _results(a, L, model_x, sups, segments, E, inertia):
    # samples along each element, both ends included, so jumps at nodes keep both values
    xs, vs, ms, ds = [], [], [], []
    per_m = 400 / L
    for e in range(a.num_elements):
        n = max(6, math.ceil(a.L[e] * per_m))
        for i in range(n + 1):
            xl = a.L[e] * i / n
            v, m, d = _internal(a, e, xl)
            xs.append(a.nodes[e] + xl)
            vs.append(-v)
            ms.append(-m)
            ds.append(d * 1000)
    xs, vs, ms, ds = (np.array(t) for t in (xs, vs, ms, ds))

    def side(x, values, right):
        idx = np.where(np.abs(xs - x) < 1e-9)[0]
        if not len(idx):
            return float(np.interp(x, xs, values))
        return float(values[idx[-1] if right else idx[0]])

    # analytical model: nodes, elements and degrees of freedom numbered as in the textbook method
    mesh_index = {_key(x): i for i, x in a.nodes.items()}
    nodes = []
    for j, x in enumerate(model_x):
        kind = sups.get(x)
        fix = SUPPORT_TYPES[kind] if kind else (0, 0)
        i = mesh_index[x]
        nodes.append({"n": j + 1, "x": x, "support": kind, "fix": list(fix),
                      "v_mm": -float(a.displacements[2 * i]) * 1000, "theta": -float(a.displacements[2 * i + 1])})
    number = 1
    for nd in nodes:
        nd["dofs"] = [None, None]
        for k in (0, 1):
            if not nd["fix"][k]:
                nd["dofs"][k] = number
                number += 1
    free_dofs = number - 1
    for nd in nodes:
        for k in (0, 1):
            if nd["fix"][k]:
                nd["dofs"][k] = number
                number += 1

    elements = []
    for j, (x0, x1) in enumerate(zip(model_x, model_x[1:])):
        elements.append({
            "e": j + 1, "start": j + 1, "end": j + 2, "x1": x0, "x2": x1, "L": x1 - x0, "E": float(E),
            "I": _inertia_at(inertia, 0.5 * (x0 + x1)),
            # member end forces: shear up and moment anticlockwise at each end
            "Q": [side(x0, vs, True), -side(x0, ms, True), -side(x1, vs, False), side(x1, ms, False)],
        })

    reactions = []
    for nd in nodes:
        if not nd["support"]:
            continue
        i = mesh_index[nd["x"]]
        reactions.append({"node": nd["n"], "x": nd["x"], "type": nd["support"],
                          "Ry": -float(a.reactions[2 * i]),
                          "M": -float(a.reactions[2 * i + 1]) if nd["fix"][1] else None})

    i_sag, i_hog, i_v, i_d = int(np.argmax(ms)), int(np.argmin(ms)), int(np.argmax(np.abs(vs))), int(np.argmax(np.abs(ds)))
    envelope = {
        "sagging": {"M": max(float(ms[i_sag]), 0.0), "x": float(xs[i_sag]), "i": i_sag},
        "hogging": {"M": min(float(ms[i_hog]), 0.0), "x": float(xs[i_hog]), "i": i_hog},
        "shear": {"V": float(abs(vs[i_v])), "x": float(xs[i_v]), "i": i_v},
        "deflection": {"d": float(ds[i_d]), "x": float(xs[i_d]), "i": i_d},
    }
    return {
        "length": L, "E": float(E), "segments": segments, "free_dofs": free_dofs,
        "nodes": nodes, "elements": elements, "reactions": reactions, "envelope": envelope,
        "x": xs.round(5).tolist(), "V": vs.round(4).tolist(), "M": ms.round(4).tolist(), "delta": ds.round(5).tolist(),
        "events": _events(xs, vs, ms, model_x, a),
    }


def _events(xs, vs, ms, model_x, a):
    """Points worth labelling: values either side of every node, peaks and zero moments."""
    out = {"V": [], "M": [], "zeros": []}
    marked = sorted({*model_x, *(_key(v) for v in a.nodes.values() if _is_load_node(a, v))})
    for x in marked:
        idx = np.where(np.abs(xs - x) < 1e-9)[0]
        for name, values in (("V", vs), ("M", ms)):
            left, right = float(values[idx[0]]), float(values[idx[-1]])
            out[name].append({"x": x, "left": left, "right": right})
    # moment peaks between nodes, where the shear changes sign under a distributed load
    ux, first = np.unique(xs, return_index=True)
    um = ms[first]
    for i in range(1, len(ux) - 1):
        if (um[i] - um[i - 1]) * (um[i + 1] - um[i]) < 0 and abs(um[i]) > 1e-6 and _key(ux[i]) not in marked:
            out["M"].append({"x": float(ux[i]), "left": float(um[i]), "right": float(um[i]), "peak": True})
    tol = 1e-6 * max(float(np.max(np.abs(ms))), 1e-9)
    for i in range(len(xs) - 1):
        if xs[i + 1] > xs[i] and ms[i] * ms[i + 1] < 0 and min(abs(ms[i]), abs(ms[i + 1])) > tol:
            t = ms[i] / (ms[i] - ms[i + 1])
            out["zeros"].append(float(xs[i] + t * (xs[i + 1] - xs[i])))
    return out


def _is_load_node(a, x):
    n = next(i for i, v in a.nodes.items() if v == x)
    return any(p["node"] == n for p in a.point_loads)
