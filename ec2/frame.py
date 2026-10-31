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
  * "point_gravity": vertical downward point load P > 0 at distance a from node1.
- Member internal forces:
  * axial N: tension positive (+).
  * shear V and moment M follow the beam convention (Hibbeler): sagging moment (+),
    dV/dx = w, dM/dx = V.
  * M is drawn on the tension side (sagging plots below the member, hogging above).

Conventions in analyse_frame():
- Frame sections given as b × h in mm.
- In analyse_frame(), gravity loads are positive downwards:
  * member "udl" and "point" loads act straight down (positive downwards).
  * node loads have fy positive downwards (global Fy = -fy), fx positive rightwards,
    mz positive anticlockwise.
  * load cases: "Ed" (as entered, × 1.0), "G" (permanent, × 1.35), "Q" (variable, × 1.5).
  * self-weight: 25 kN/m³ × b × h on every member as permanent gravity load (G).
"""
import math

import numpy as np

from .inputs import Reader, ValidationError
from .materials import CONCRETE_TABLE
from .slenderness import PINNED, stiffness_k

__all__ = ["solve", "analyse_frame", "column_actions"]

LOAD_FACTORS = {"Ed": 1.0, "G": 1.35, "Q": 1.5}


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
        Member loads: {"member": str, "load_type": "udl"|"point"|"udl_gravity"|"point_gravity",
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

            elif lType == "point_gravity":
                # Downward gravity point load: P > 0 downwards
                a = float(ld["a"]) if "a" in ld else L / 2.0
                if a < -1e-6 or a > L + 1e-6:
                    raise ValueError(f"Point load position a={a} is outside member length {L}")
                a = max(0.0, min(L, a))
                b = L - a

                pa = -P * s
                pt = -P * c

                feq[0] += pa * b / L
                feq[1] += pt * b * b * (3.0 * a + b) / (L ** 3)
                feq[2] += pt * a * b * b / (L ** 2)
                feq[3] += pa * a / L
                feq[4] += pt * a * a * (a + 3.0 * b) / (L ** 3)
                feq[5] += -pt * a * a * b / (L ** 2)

                f["N1"] += pa * b / L
                f["V1"] += pt * b * b * (3.0 * a + b) / (L ** 3)
                f["M1"] += pt * a * b * b / (L ** 2)
                f["N2"] += pa * a / L
                f["V2"] += pt * a * a * (a + 3.0 * b) / (L ** 3)
                f["M2"] += -pt * a * a * b / (L ** 2)

                elem_loads[target].append({"type": "point_gravity", "P": P, "a": a, "pa": pa, "pt": pt})

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
        stype = sup.get("type")
        dx = sup.get("dx") if "dx" in sup else (stype in ("fixed", "pin"))
        dy = sup.get("dy") if "dy" in sup else (stype in ("fixed", "pin", "roller"))
        rz = sup.get("rz") if "rz" in sup else (stype == "fixed")
        if dx:
            fixed_dofs.add(ni * 3)
        if dy:
            fixed_dofs.add(ni * 3 + 1)
        if rz:
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
        stype = sup.get("type")
        dx = sup.get("dx") if "dx" in sup else (stype in ("fixed", "pin"))
        dy = sup.get("dy") if "dy" in sup else (stype in ("fixed", "pin", "roller"))
        rz = sup.get("rz") if "rz" in sup else (stype == "fixed")
        reactions[nid] = {
            "Rx": float(R_all[ni * 3]) if dx else 0.0,
            "Ry": float(R_all[ni * 3 + 1]) if dy else 0.0,
            "Mz": float(R_all[ni * 3 + 2]) if rz else 0.0,
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
            if ld["type"] in ("point", "point_gravity"):
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
                elif ld["type"] == "point_gravity":
                    if x > ld["a"]:
                        N += ld["pa"]
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
                elif ld["type"] == "point_gravity":
                    if x > ld["a"]:
                        V += ld["pt"]
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
                elif ld["type"] == "point_gravity":
                    if x > ld["a"]:
                        M += ld["pt"] * (x - ld["a"])
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
            "b": m.get("b"),
            "h": m.get("h"),
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


def analyse_frame(data):
    """The column page's frame analysis.

    Validates with ec2.inputs.Reader, converts units and signs, applies load case
    factors, self-weight, and calls solve().

    Parameters
    ----------
    data : dict
        Request payload containing "frame" (or frame keys at top level).

    Returns
    -------
    dict
        The solve() result augmented with input topology, sections, loads, and
        vertical member IDs.
    """
    r = Reader(data)
    prefix = "frame." if ("frame" in data and isinstance(data["frame"], dict)) else ""

    # Nodes
    raw_nodes = r.raw(f"{prefix}nodes")
    if not isinstance(raw_nodes, list) or len(raw_nodes) == 0:
        r.errors[f"{prefix}nodes"] = "At least one node is required."
        nodes = []
    else:
        nodes = []
        for i in range(len(raw_nodes)):
            p = f"{prefix}nodes.{i}"
            nid = r.text(f"{p}.id")
            if not nid:
                r.errors[f"{p}.id"] = "Required."
            x = r.number(f"{p}.x", lo=-1000.0, hi=1000.0)
            y = r.number(f"{p}.y", lo=-1000.0, hi=1000.0)
            nodes.append({"id": nid, "x": x, "y": y})

    # Members
    raw_members = r.raw(f"{prefix}members")
    if not isinstance(raw_members, list) or len(raw_members) == 0:
        r.errors[f"{prefix}members"] = "At least one member is required."
        members = []
    else:
        members = []
        for i in range(len(raw_members)):
            p = f"{prefix}members.{i}"
            mid = r.text(f"{p}.id")
            if not mid:
                r.errors[f"{p}.id"] = "Required."
            n1 = r.text(f"{p}.node1")
            if not n1:
                r.errors[f"{p}.node1"] = "Required."
            n2 = r.text(f"{p}.node2")
            if not n2:
                r.errors[f"{p}.node2"] = "Required."
            b = r.number(f"{p}.b", lo=50, hi=5000, default=300)
            h = r.number(f"{p}.h", lo=50, hi=5000, default=300)
            members.append({"id": mid, "node1": n1, "node2": n2, "b": b, "h": h})

    # Supports
    raw_supports = r.raw(f"{prefix}supports")
    supports = []
    if isinstance(raw_supports, list):
        for i, s in enumerate(raw_supports):
            p = f"{prefix}supports.{i}"
            nid = r.text(f"{p}.node")
            if not nid:
                r.errors[f"{p}.node"] = "Required."
            stype = r.choice(f"{p}.type", ("fixed", "pin", "roller"), default=None)
            dx = s.get("dx") if isinstance(s, dict) and "dx" in s else (stype in ("fixed", "pin"))
            dy = s.get("dy") if isinstance(s, dict) and "dy" in s else (stype in ("fixed", "pin", "roller"))
            rz = s.get("rz") if isinstance(s, dict) and "rz" in s else (stype == "fixed")
            supports.append({
                "node": nid,
                "type": stype or ("fixed" if (dx and dy and rz) else "pin" if (dx and dy) else "roller"),
                "dx": bool(dx), "dy": bool(dy), "rz": bool(rz),
            })

    # Loads
    raw_loads = r.raw(f"{prefix}loads")
    loads = []
    if isinstance(raw_loads, list):
        for i, ld in enumerate(raw_loads):
            p = f"{prefix}loads.{i}"
            ltype = r.choice(f"{p}.type", ("node", "udl", "point"), default="node")
            case = r.choice(f"{p}.case", ("Ed", "G", "Q"), default="Ed")
            if ltype == "node":
                nid = r.text(f"{p}.node")
                if not nid:
                    r.errors[f"{p}.node"] = "Required."
                fx = r.number(f"{p}.fx", lo=-1e6, hi=1e6, default=0.0)
                fy = r.number(f"{p}.fy", lo=-1e6, hi=1e6, default=0.0)
                mz = r.number(f"{p}.mz", lo=-1e6, hi=1e6, default=0.0)
                loads.append({"type": "node", "node": nid, "fx": fx, "fy": fy, "mz": mz, "case": case})
            elif ltype == "udl":
                mid = r.text(f"{p}.member") or r.text(f"{p}.element")
                if not mid:
                    r.errors[f"{p}.member"] = "Required."
                w = r.number(f"{p}.w", lo=-1e6, hi=1e6, default=0.0)
                loads.append({"type": "udl", "member": mid, "w": w, "case": case})
            elif ltype == "point":
                mid = r.text(f"{p}.member") or r.text(f"{p}.element")
                if not mid:
                    r.errors[f"{p}.member"] = "Required."
                P = r.number(f"{p}.P", lo=-1e6, hi=1e6, default=0.0)
                a = r.number(f"{p}.a", lo=0.0, hi=1000.0, optional=True)
                item = {"type": "point", "member": mid, "P": P, "case": case}
                if a is not None:
                    item["a"] = a
                loads.append(item)

    self_weight = r.flag(f"{prefix}self_weight", default=True)
    E_method = r.choice(f"{prefix}E_method", ("concrete", "entered"), default="concrete")
    if E_method == "entered":
        E_gpa = r.number(f"{prefix}E", lo=0.1, hi=1000.0, default=30.0)
    else:
        concrete_class = r.choice("materials.concrete", CONCRETE_TABLE, default="C30/37")
        E_gpa = CONCRETE_TABLE[concrete_class][3]

    if r.errors:
        raise ValidationError(r.errors)

    # Convert to solve() units: E in kN/m² (1 GPa = 1e6 kN/m²)
    E_kpa = E_gpa * 1e6

    solve_members = []
    for m in members:
        b_m = m["b"] / 1000.0
        h_m = m["h"] / 1000.0
        A = b_m * h_m
        I = b_m * (h_m ** 3) / 12.0
        solve_members.append({
            "id": m["id"],
            "node1": m["node1"],
            "node2": m["node2"],
            "E": E_kpa,
            "A": A,
            "I": I,
            "b": m["b"],
            "h": m["h"],
        })

    solve_loads = []
    # Self-weight: 25 kN/m³ × b × h factored as permanent load G (× 1.35)
    if self_weight:
        for sm in solve_members:
            sw_char = 25.0 * sm["A"]  # kN/m
            sw_factored = LOAD_FACTORS["G"] * sw_char
            solve_loads.append({
                "member": sm["id"],
                "load_type": "udl_gravity",
                "w": sw_factored,
                "case": "G",
            })

    for ld in loads:
        factor = LOAD_FACTORS.get(ld.get("case", "Ed"), 1.0)
        ltype = ld["type"]
        if ltype == "node":
            # In analyse_frame, fy positive downwards -> global Fy is negative
            solve_loads.append({
                "node": ld["node"],
                "fx": ld.get("fx", 0.0) * factor,
                "fy": -ld.get("fy", 0.0) * factor,
                "mz": ld.get("mz", 0.0) * factor,
                "case": ld.get("case", "Ed"),
            })
        elif ltype == "udl":
            # Gravity UDL positive downwards
            solve_loads.append({
                "member": ld["member"],
                "load_type": "udl_gravity",
                "w": ld.get("w", 0.0) * factor,
                "case": ld.get("case", "Ed"),
            })
        elif ltype == "point":
            item = {
                "member": ld["member"],
                "load_type": "point_gravity",
                "P": ld.get("P", 0.0) * factor,
                "case": ld.get("case", "Ed"),
            }
            if "a" in ld:
                item["a"] = ld["a"]
            solve_loads.append(item)

    try:
        result = solve(nodes, solve_members, supports, solve_loads)
    except ValueError as err:
        raise ValidationError({"frame": str(err)}) from err

    # Classify vertical members
    node_coords = {n["id"]: (float(n["x"]), float(n["y"])) for n in nodes}
    vertical_members = []
    for m in members:
        x1, y1 = node_coords[m["node1"]]
        x2, y2 = node_coords[m["node2"]]
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        L = math.sqrt(dx * dx + dy * dy)
        if L > 0 and (dx / L) < 0.05:
            vertical_members.append(m["id"])

    result["nodes"] = nodes
    result["elements"] = members
    result["members_input"] = members
    result["supports"] = supports
    result["loads"] = loads
    result["combined_loads"] = solve_loads
    result["self_weight"] = self_weight
    result["E_method"] = E_method
    result["E"] = E_gpa
    result["vertical_members"] = vertical_members

    return result


def column_actions(result, member_id, members, supports):
    """Extract design actions for the column check from one vertical member.

    Parameters
    ----------
    result : dict
        Analysis result from solve() or analyse_frame().
    member_id : str
        ID of the vertical column member to design.
    members : list of dict
        Member input list [{"id", "node1", "node2", "b", "h", ...}].
    supports : list of dict
        Supports input list.

    Returns
    -------
    dict
        {
            "member": str,
            "NEd": float,
            "M_top": float,
            "M_bottom": float,
            "M_top_signed": float,
            "M_bottom_signed": float,
            "curvature": "single" | "double",
            "l": float,
            "k_top": float,
            "k_bottom": float,
            "top_node": str,
            "bottom_node": str,
        }
    """
    m_res = next((m for m in result.get("members", []) if m["id"] == str(member_id) or m.get("element") == str(member_id)), None)
    if not m_res:
        raise ValueError(f"Member '{member_id}' not found in frame analysis result")

    m_def = next((m for m in members if str(m["id"]) == str(member_id)), None)
    if not m_def:
        raise ValueError(f"Member '{member_id}' not found in members list")

    # Get node coordinates
    if "nodes" in result:
        node_coords = {str(n["id"]): (float(n["x"]), float(n["y"])) for n in result["nodes"]}
    else:
        raise ValueError("Node coordinates not found in analysis result")

    n1 = str(m_def["node1"])
    n2 = str(m_def["node2"])
    x1, y1 = node_coords[n1]
    x2, y2 = node_coords[n2]

    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    L = math.sqrt(dx * dx + dy * dy)
    if L == 0 or (dx / L) >= 0.05:
        raise ValueError(f"Member '{member_id}' is not vertical")

    # Axial force: solve() uses tension (+), compression (-)
    N1 = m_res.get("axial_start", m_res.get("axial", 0.0))
    N2 = m_res.get("axial_end", m_res.get("axial", 0.0))
    comp1 = -N1
    comp2 = -N2
    N_comp = max(comp1, comp2)
    if N_comp <= 0:
        raise ValueError(f"Member '{member_id}' is in tension (N = {max(N1, N2):.2f} kN)")

    # Heights for top and bottom nodes
    if y2 >= y1:
        top_node = n2
        bottom_node = n1
        m_top_signed = m_res["moment_end"]
        m_bottom_signed = m_res["moment_start"]
    else:
        top_node = n1
        bottom_node = n2
        m_top_signed = m_res["moment_start"]
        m_bottom_signed = m_res["moment_end"]

    m_top = abs(m_top_signed)
    m_bottom = abs(m_bottom_signed)

    # Curvature: single when end moments have same sign in member convention
    m_start = m_res["moment_start"]
    m_end = m_res["moment_end"]
    curvature = "single" if (m_start * m_end >= 0) else "double"

    # Column stiffness EI/l
    if "I" in m_def:
        col_I = float(m_def["I"])
    elif "b" in m_def and "h" in m_def:
        col_I = (float(m_def["b"]) * (float(m_def["h"]) ** 3)) / (12.0 * 1e12)
    else:
        col_I = 1e-4

    def end_k(node_id):
        # Check supports
        sup = next((s for s in supports if str(s["node"]) == str(node_id)), None)
        if sup is not None:
            stype = sup.get("type")
            rz = sup.get("rz") if "rz" in sup else (stype == "fixed")
            if rz or stype == "fixed":
                return 0.1
            else:
                return PINNED

        # Interior joint: gather non-vertical framing members
        beams = []
        for om in members:
            if str(om["id"]) == str(member_id):
                continue
            on1, on2 = str(om["node1"]), str(om["node2"])
            if on1 == str(node_id) or on2 == str(node_id):
                ox1, oy1 = node_coords[on1]
                ox2, oy2 = node_coords[on2]
                odx = abs(ox2 - ox1)
                ody = abs(oy2 - oy1)
                oL = math.sqrt(odx * odx + ody * ody)
                if oL > 0 and (odx / oL) >= 0.05:
                    if "I" in om:
                        Ib = float(om["I"])
                    elif "b" in om and "h" in om:
                        Ib = (float(om["b"]) * (float(om["h"]) ** 3)) / (12.0 * 1e12)
                    else:
                        Ib = 1e-4
                    beams.append((Ib, oL))

        if not beams:
            return PINNED
        return stiffness_k(col_I, L, beams)

    k_top = end_k(top_node)
    k_bottom = end_k(bottom_node)

    return {
        "member": str(member_id),
        "NEd": N_comp,
        "M_top": m_top,
        "M_bottom": m_bottom,
        "M_top_signed": m_top_signed,
        "M_bottom_signed": m_bottom_signed,
        "curvature": curvature,
        "l": L,
        "k_top": k_top,
        "k_bottom": k_bottom,
        "top_node": top_node,
        "bottom_node": bottom_node,
    }
