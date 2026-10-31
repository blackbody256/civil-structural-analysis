"""2D frame analysis by the matrix stiffness method.

Linear elastic 2D frame solver ported from the client's analysis tool
("Truss, beam and frame analysis tool by Group 10.html", solveStructureJS),
using 3 degrees of freedom per node: horizontal displacement ux, vertical uy,
and in-plane rotation rz.

Sign conventions in solve():
- Global axes: x right (+), y up (+), rotation rz anticlockwise (+).
- Node loads: fx right (+), fy up (+), mz anticlockwise (+).
- Member local axes: local x from node1 to node2; local y 90 degrees CCW (to the left
  of node1 -> node2; for a left-to-right horizontal beam, local y points up).
- Member loads:
  * "udl": local transverse distributed load w (+ in local y).
  * "point": local transverse point load P (+ in local y) at distance a from node1.
  * "udl_gravity": vertical downward load w > 0 per metre of member length.
- Member internal forces:
  * axial N: tension positive (+).
  * shear V and moment M follow the beam convention (Hibbeler): sagging moment (+),
    dV/dx = w, dM/dx = V.
  * M is drawn on the tension side (sagging plots below the member, hogging above).
"""
import math

import numpy as np

__all__ = ["solve", "analyse_frame", "column_actions"]


def solve(nodes, members, supports, loads):
    """Linear elastic 2D frame by the matrix stiffness method.

    Parameters
    ----------
    nodes : list of dict
        [{"id": str, "x": float, "y": float}] in metres.
    members : list of dict
        [{"id": str, "node1": str, "node2": str, "E": float, "A": float, "I": float}]
        with E in kN/m², A in m², I in m⁴.
    supports : list of dict
        [{"node": str, "dx": bool, "dy": bool, "rz": bool}]
    loads : list of dict
        Nodal loads: {"node": str, "fx": float, "fy": float, "mz": float}
        Member loads: {"member": str, "load_type": "udl"|"point"|"udl_gravity",
                       "w": float, "P": float, "a": float}

    Returns
    -------
    dict
        {
            "displacements": {node_id: {"ux": float, "uy": float, "rz": float}},
            "reactions": {node_id: {"Rx": float, "Ry": float, "Mz": float}},
            "members": [
                {
                    "id": str, "element": str, "node1": str, "node2": str, "L": float,
                    "axial": float, "axial_start": float, "axial_end": float,
                    "shear_start": float, "shear_end": float,
                    "moment_start": float, "moment_end": float,
                    "node1_disp": dict, "node2_disp": dict,
                    "x": list of float, "N": list of float,
                    "V": list of float, "M": list of float,
                    "diagram": {"x": ..., "N": ..., "V": ..., "M": ...}
                },
                ...
            ],
            "determinacy": {"value": int, "label": str}
        }
    """
    node_map = {}
    for i, n in enumerate(nodes):
        nid = str(n["id"])
        if nid in node_map:
            raise ValueError(f"Duplicate node id '{nid}'")
        node_map[nid] = i

    n_nodes = len(nodes)
    if n_nodes == 0:
        raise ValueError("The frame has no nodes")

    total_dof = n_nodes * 3
    K = np.zeros((total_dof, total_dof), dtype=float)
    F = np.zeros(total_dof, dtype=float)

    member_data = []
    member_map = {}
    for m in members:
        mid = str(m["id"])
        if mid in member_map:
            raise ValueError(f"Duplicate member id '{mid}'")
        n1_id = str(m["node1"])
        n2_id = str(m["node2"])
        if n1_id not in node_map:
            raise ValueError(f"Member '{mid}' references unknown node '{n1_id}'")
        if n2_id not in node_map:
            raise ValueError(f"Member '{mid}' references unknown node '{n2_id}'")
        if n1_id == n2_id:
            raise ValueError(f"Member '{mid}' connects node '{n1_id}' to itself")

        i1 = node_map[n1_id]
        i2 = node_map[n2_id]
        x1 = float(nodes[i1]["x"])
        y1 = float(nodes[i1]["y"])
        x2 = float(nodes[i2]["x"])
        y2 = float(nodes[i2]["y"])

        dx = x2 - x1
        dy = y2 - y1
        L = math.sqrt(dx * dx + dy * dy)
        if L < 1e-9:
            raise ValueError(f"Member '{mid}' has zero length")

        E = float(m["E"])
        A = float(m["A"])
        I = float(m.get("I", 1e-4))
        c = dx / L
        s = dy / L

        EA_L = E * A / L
        EI = E * I
        k12 = 12.0 * EI / (L ** 3)
        k6 = 6.0 * EI / (L ** 2)
        k4 = 4.0 * EI / L
        k2 = 2.0 * EI / L

        kl = np.array([
            [ EA_L,  0.0,   0.0, -EA_L,  0.0,   0.0 ],
            [ 0.0,   k12,   k6,   0.0,  -k12,   k6  ],
            [ 0.0,   k6,    k4,   0.0,  -k6,    k2  ],
            [-EA_L,  0.0,   0.0,  EA_L,  0.0,   0.0 ],
            [ 0.0,  -k12,  -k6,   0.0,   k12,  -k6  ],
            [ 0.0,   k6,    k2,   0.0,  -k6,    k4  ],
        ], dtype=float)

        T = np.array([
            [ c,  s, 0.0, 0.0, 0.0, 0.0],
            [-s,  c, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0,  c,  s, 0.0],
            [0.0, 0.0, 0.0, -s,  c, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        ], dtype=float)

        kg = T.T @ kl @ T
        dofs = [i1 * 3, i1 * 3 + 1, i1 * 3 + 2, i2 * 3, i2 * 3 + 1, i2 * 3 + 2]
        for ii, di in enumerate(dofs):
            for jj, dj in enumerate(dofs):
                K[di, dj] += kg[ii, jj]

        ed = {
            "m": m, "mid": mid, "i1": i1, "i2": i2, "L": L, "c": c, "s": s,
            "dofs": dofs, "T": T, "EA_L": EA_L,
            "k12": k12, "k6": k6, "k4": k4, "k2": k2
        }
        member_data.append(ed)
        member_map[mid] = ed

    # Nodal loads
    for ld in loads:
        if "node" in ld:
            nid = str(ld["node"])
            if nid not in node_map:
                raise ValueError(f"Load references unknown node '{nid}'")
            ni = node_map[nid]
            F[ni * 3] += float(ld.get("fx", 0.0))
            F[ni * 3 + 1] += float(ld.get("fy", 0.0))
            F[ni * 3 + 2] += float(ld.get("mz", 0.0))

    # Member loads & Equivalent nodal loads
    elem_FEF = {m["id"]: {"N1": 0.0, "V1": 0.0, "M1": 0.0, "N2": 0.0, "V2": 0.0, "M2": 0.0} for m in members}
    elem_loads = {m["id"]: [] for m in members}

    for ld in loads:
        target = ld.get("member") if "member" in ld else ld.get("element")
        if target is not None:
            target = str(target)
            if target not in member_map:
                raise ValueError(f"Load references unknown member '{target}'")
            ed = member_map[target]
            L, c, s, dofs, T = ed["L"], ed["c"], ed["s"], ed["dofs"], ed["T"]
            lType = ld.get("load_type", "udl")
            w = float(ld.get("w", 0.0))
            P = float(ld.get("P", 0.0))

            feq = np.zeros(6, dtype=float)
            f = elem_FEF[target]

            if lType == "udl":
                # Local transverse UDL (local +y positive)
                feq[1] += w * L / 2.0
                feq[2] += w * L * L / 12.0
                feq[4] += w * L / 2.0
                feq[5] += -w * L * L / 12.0

                f["V1"] += w * L / 2.0
                f["M1"] += w * L * L / 12.0
                f["V2"] += w * L / 2.0
                f["M2"] += -w * L * L / 12.0

                elem_loads[target].append({"type": "udl", "w": w})

            elif lType == "udl_gravity":
                # Downward gravity UDL: w > 0 downwards
                qa = -w * s
                qt = -w * c

                feq[0] += qa * L / 2.0
                feq[1] += qt * L / 2.0
                feq[2] += qt * L * L / 12.0
                feq[3] += qa * L / 2.0
                feq[4] += qt * L / 2.0
                feq[5] += -qt * L * L / 12.0

                f["N1"] += qa * L / 2.0
                f["V1"] += qt * L / 2.0
                f["M1"] += qt * L * L / 12.0
                f["N2"] += qa * L / 2.0
                f["V2"] += qt * L / 2.0
                f["M2"] += -qt * L * L / 12.0

                elem_loads[target].append({"type": "udl_gravity", "w": w, "qa": qa, "qt": qt})

            elif lType == "point":
                a = float(ld["a"]) if "a" in ld else L / 2.0
                if a < -1e-6 or a > L + 1e-6:
                    raise ValueError(f"Point load position a={a} is outside member length {L}")
                a = max(0.0, min(L, a))
                b = L - a

                feq[1] += P * b * b * (3.0 * a + b) / (L ** 3)
                feq[2] += P * a * b * b / (L ** 2)
                feq[4] += P * a * a * (a + 3.0 * b) / (L ** 3)
                feq[5] += -P * a * a * b / (L ** 2)

                f["V1"] += P * b * b * (3.0 * a + b) / (L ** 3)
                f["M1"] += P * a * b * b / (L ** 2)
                f["V2"] += P * a * a * (a + 3.0 * b) / (L ** 3)
                f["M2"] += -P * a * a * b / (L ** 2)

                elem_loads[target].append({"type": "point", "P": P, "a": a})
            else:
                raise ValueError(f"Unknown load type '{lType}'")

            fg = T.T @ feq
            for ii, di in enumerate(dofs):
                F[di] += fg[ii]

    # Supports / Restrained DOFs
    fixed_dofs = set()
    for sup in supports:
        nid = str(sup["node"])
        if nid not in node_map:
            raise ValueError(f"Support references unknown node '{nid}'")
        ni = node_map[nid]
        if sup.get("dx"):
            fixed_dofs.add(ni * 3)
        if sup.get("dy"):
            fixed_dofs.add(ni * 3 + 1)
        if sup.get("rz"):
            fixed_dofs.add(ni * 3 + 2)

    free_dofs = [d for d in range(total_dof) if d not in fixed_dofs]
    U = np.zeros(total_dof, dtype=float)

    if free_dofs:
        Kff = K[np.ix_(free_dofs, free_dofs)]
        Ff = F[free_dofs]
        try:
            if np.linalg.matrix_rank(Kff) < len(free_dofs):
                raise ValueError("The frame is unstable: check the supports")
            Uf = np.linalg.solve(Kff, Ff)
            for idx, d in enumerate(free_dofs):
                U[d] = Uf[idx]
        except (np.linalg.LinAlgError, ValueError) as err:
            raise ValueError("The frame is unstable: check the supports") from err

    # Reactions: R = K*U - F
    R_all = K @ U - F
    reactions = {}
    for sup in supports:
        nid = str(sup["node"])
        ni = node_map[nid]
        reactions[nid] = {
            "Rx": float(R_all[ni * 3]) if sup.get("dx") else 0.0,
            "Ry": float(R_all[ni * 3 + 1]) if sup.get("dy") else 0.0,
            "Mz": float(R_all[ni * 3 + 2]) if sup.get("rz") else 0.0,
        }

    # Nodal displacements
    displacements = {
        str(n["id"]): {
            "ux": float(U[i * 3]),
            "uy": float(U[i * 3 + 1]),
            "rz": float(U[i * 3 + 2]),
        }
        for i, n in enumerate(nodes)
    }

    # Member forces and diagram sampling
    members_out = []
    for ed in member_data:
        m, mid = ed["m"], ed["mid"]
        L, dofs, T = ed["L"], ed["dofs"], ed["T"]
        u_el = U[dofs]
        ul = T @ u_el

        EA_L = ed["EA_L"]
        k12, k6, k4, k2 = ed["k12"], ed["k6"], ed["k4"], ed["k2"]

        fl0 = EA_L * (ul[0] - ul[3])
        fl1 = k12 * (ul[1] - ul[4]) + k6 * (ul[2] + ul[5])
        fl2 = k6 * (ul[1] - ul[4]) + k4 * ul[2] + k2 * ul[5]
        fl4 = -k12 * (ul[1] - ul[4]) - k6 * (ul[2] + ul[5])
        fl5 = k6 * (ul[1] - ul[4]) + k2 * ul[2] + k4 * ul[5]

        fef = elem_FEF[mid]
        N1 = -fl0 + fef["N1"]
        V1 = fl1 - fef["V1"]
        M1 = -(fl2 - fef["M1"])
        V2 = -fl4 + fef["V2"]
        M2 = fl5 - fef["M2"]

        # Sample at least 21 uniform points plus at point loads
        x_set = set(k * L / 20.0 for k in range(21))
        for ld in elem_loads[mid]:
            if ld["type"] == "point":
                a = ld["a"]
                eps = 1e-6 * L
                x_set.add(max(0.0, a - eps))
                x_set.add(a)
                x_set.add(min(L, a + eps))
        x_arr = sorted(list(x_set))

        def axial_at(x):
            N = N1
            for ld in elem_loads[mid]:
                if ld["type"] == "udl_gravity":
                    N -= ld["qa"] * x
            return N

        def shear_at(x):
            V = V1
            for ld in elem_loads[mid]:
                if ld["type"] == "udl":
                    V += ld["w"] * x
                elif ld["type"] == "udl_gravity":
                    V += ld["qt"] * x
                elif ld["type"] == "point":
                    if x > ld["a"]:
                        V += ld["P"]
            return V

        def moment_raw(x):
            M = M1 + V1 * x
            for ld in elem_loads[mid]:
                if ld["type"] == "udl":
                    M += 0.5 * ld["w"] * x * x
                elif ld["type"] == "udl_gravity":
                    M += 0.5 * ld["qt"] * x * x
                elif ld["type"] == "point":
                    if x > ld["a"]:
                        M += ld["P"] * (x - ld["a"])
            return M

        M_resid = M2 - moment_raw(L)

        N_arr = [axial_at(x) for x in x_arr]
        V_arr = [shear_at(x) for x in x_arr]
        M_arr = [moment_raw(x) + M_resid * (x / L) for x in x_arr]

        members_out.append({
            "id": mid,
            "element": mid,
            "node1": str(m["node1"]),
            "node2": str(m["node2"]),
            "L": L,
            "axial": N1,
            "axial_start": N1,
            "axial_end": N_arr[-1],
            "shear_start": V1,
            "shear_end": V2,
            "moment_start": M1,
            "moment_end": M2,
            "node1_disp": displacements[str(m["node1"])],
            "node2_disp": displacements[str(m["node2"])],
            "x": x_arr,
            "N": N_arr,
            "V": V_arr,
            "M": M_arr,
            "diagram": {
                "x": x_arr,
                "N": N_arr,
                "V": V_arr,
                "M": M_arr,
            },
        })

    m_cnt = len(members)
    r_cnt = len(fixed_dofs)
    j_cnt = n_nodes
    det = 3 * m_cnt + r_cnt - 3 * j_cnt
    det_label = (
        "Statically Determinate" if det == 0 else
        f"Statically Indeterminate (Degree {det})" if det > 0 else
        "Unstable / Mechanism"
    )

    return {
        "displacements": displacements,
        "reactions": reactions,
        "members": members_out,
        "determinacy": {"value": det, "label": det_label},
    }
