"""Figures for 2D frame analysis: model geometry and N, V, M diagrams.

Uses Fig from reports/beam_figures.py so diagrams can be rendered on the web page
via static/js/figure-spec.js (renderFigure) and in the PDF report via reports/beam_pdf.py.

Conventions:
- Scale frame to 1000 units wide.
- Colours:
  * "ink": general lines, text
  * "muted": baseline, dimension lines
  * "accent": member being designed
  * "load": loads and arrows
  * "sfd": shear force diagrams (V)
  * "bmd": bending moment diagrams (M), drawn on the tension side
  * "react": axial force diagrams (N)
"""
import math

from reports.beam_figures import Fig

W = 1000
MARGIN = 90


def _bounds(nodes):
    xs = [float(n["x"]) for n in nodes]
    ys = [float(n["y"]) for n in nodes]
    return min(xs), max(xs), min(ys), max(ys)


def _transformers(nodes):
    xmin, xmax, ymin, ymax = _bounds(nodes)
    dx = max(xmax - xmin, 0.5)
    dy = max(ymax - ymin, 0.5)

    # Frame drawing area inside W=1000
    avail_w = W - 2 * MARGIN
    # Choose height to comfortably fit aspect ratio
    scale_x = avail_w / dx
    # Let max height be around 550, min 380
    scale = min(scale_x, 420.0 / dy)
    scale = max(scale, 10.0)

    frame_w = dx * scale
    frame_h = dy * scale
    H = int(max(400, frame_h + 180))

    x0 = (W - frame_w) / 2.0
    y_bot = H - (H - frame_h) / 2.0

    def X(x):
        return x0 + (float(x) - xmin) * scale

    def Y(y):
        return y_bot - (float(y) - ymin) * scale

    return X, Y, H, scale


def model_figure(result, member=None):
    """Draws analytical model: nodes, members, supports, loads."""
    nodes = result.get("nodes", [])
    if not nodes:
        fig = Fig(300)
        fig.text(500, 150, "No frame model", c="muted", size=16)
        return fig

    X, Y, H, scale = _transformers(nodes)
    fig = Fig(H)
    node_map = {str(n["id"]): n for n in nodes}

    # 1. Members
    elements = result.get("elements") or result.get("members_input") or result.get("members", [])
    for el_def in elements:
        mid = str(el_def["id"])
        n1 = node_map.get(str(el_def["node1"]))
        n2 = node_map.get(str(el_def["node2"]))
        if not n1 or not n2:
            continue
        x1, y1 = X(n1["x"]), Y(n1["y"])
        x2, y2 = X(n2["x"]), Y(n2["y"])

        is_target = (member is not None and str(mid) == str(member))
        c_line = "accent" if is_target else "ink"
        sw_line = 3.2 if is_target else 2.0
        fig.line(x1, y1, x2, y2, c=c_line, sw=sw_line)

        # Member label (boxed)
        mx = (x1 + x2) / 2.0
        my = (y1 + y2) / 2.0
        Lpx = math.hypot(x2 - x1, y2 - y1)
        if Lpx > 1:
            # Normal vector in screen space
            nx = (y2 - y1) / Lpx
            ny = -(x2 - x1) / Lpx
            # Offset label
            lx = mx + nx * 18
            ly = my + ny * 18
            lbl = f"{mid}"
            if el_def.get("b") and el_def.get("h"):
                lbl_sec = f"{el_def['b']}×{el_def['h']}"
            else:
                lbl_sec = ""

            bw = max(24, len(lbl) * 8 + 10)
            fig.poly(
                [(lx - bw / 2, ly - 9), (lx + bw / 2, ly - 9), (lx + bw / 2, ly + 9), (lx - bw / 2, ly + 9)],
                c="accent" if is_target else "muted",
                f="paper",
                closed=True,
                sw=1.2,
            )
            fig.text(lx, ly + 4, lbl, c="accent" if is_target else "ink", size=12, a="m", b=is_target)

    # 2. Supports
    supports = result.get("supports", [])
    for sup in supports:
        nid = str(sup["node"])
        n = node_map.get(nid)
        if not n:
            continue
        sx, sy = X(n["x"]), Y(n["y"])
        stype = sup.get("type", "pin")
        rz = sup.get("rz") or stype == "fixed"

        if rz or stype == "fixed":
            # Fixed support base
            fig.line(sx - 16, sy + 4, sx + 16, sy + 4, c="ink", sw=2.4)
            # Hatch lines
            for hx in range(-14, 15, 6):
                fig.line(sx + hx, sy + 4, sx + hx - 5, sy + 11, c="muted", sw=1.0)
        elif stype == "pin":
            fig.poly([(sx, sy), (sx - 10, sy + 15), (sx + 10, sy + 15)], c="ink", f="paper", closed=True, sw=1.3)
            fig.line(sx - 14, sy + 15, sx + 14, sy + 15, c="ink", sw=1.5)
            for hx in range(-12, 13, 6):
                fig.line(sx + hx, sy + 15, sx + hx - 5, sy + 21, c="muted", sw=1.0)
        else:  # roller
            fig.poly([(sx, sy), (sx - 10, sy + 12), (sx + 10, sy + 12)], c="ink", f="paper", closed=True, sw=1.3)
            fig.circle(sx - 5, sy + 16, 2.5, c="ink", f="paper", sw=1.0)
            fig.circle(sx + 5, sy + 16, 2.5, c="ink", f="paper", sw=1.0)
            fig.line(sx - 14, sy + 20, sx + 14, sy + 20, c="ink", sw=1.5)
            for hx in range(-12, 13, 6):
                fig.line(sx + hx, sy + 20, sx + hx - 5, sy + 26, c="muted", sw=1.0)

    # 3. Loads
    loads = result.get("loads", [])
    for ld in loads:
        ltype = ld.get("type")
        case = ld.get("case", "Ed")
        lbl_case = f" ({case})" if case != "Ed" else ""
        if ltype == "node":
            nid = str(ld.get("node"))
            n = node_map.get(nid)
            if not n:
                continue
            nx, ny = X(n["x"]), Y(n["y"])
            fx = float(ld.get("fx", 0.0))
            fy = float(ld.get("fy", 0.0))
            if abs(fx) > 1e-4:
                # fx > 0 points right
                dir_x = 1.0 if fx > 0 else -1.0
                fig.arrow(nx - 42 * dir_x, ny, nx - 2 * dir_x, ny, c="load", sw=1.8, head=8)
                fig.text(nx - 46 * dir_x, ny - 6, f"{abs(fx):g} kN{lbl_case}", c="load", size=12, a="r" if dir_x > 0 else "l")
            if abs(fy) > 1e-4:
                # In analyse_frame, fy > 0 is downwards -> on screen points downward
                dir_y = 1.0 if fy > 0 else -1.0
                fig.arrow(nx, ny - 42 * dir_y, nx, ny - 2 * dir_y, c="load", sw=1.8, head=8)
                fig.text(nx + 8, ny - 30 * dir_y, f"{abs(fy):g} kN{lbl_case}", c="load", size=12, a="l")
        elif ltype == "udl":
            mid = str(ld.get("member") or ld.get("element"))
            el_def = next((e for e in elements if str(e["id"]) == mid), None)
            if el_def:
                n1 = node_map.get(str(el_def["node1"]))
                n2 = node_map.get(str(el_def["node2"]))
                if n1 and n2:
                    x1, y1 = X(n1["x"]), Y(n1["y"])
                    x2, y2 = X(n2["x"]), Y(n2["y"])
                    w = float(ld.get("w", 0.0))
                    # Downward arrow row
                    arrow_len = 26
                    num_arrows = 5
                    for k in range(num_arrows):
                        t = (k + 0.5) / num_arrows
                        bx = x1 + t * (x2 - x1)
                        by = y1 + t * (y2 - y1)
                        fig.arrow(bx, by - arrow_len, bx, by - 2, c="load", sw=1.2, head=5)
                    # Connecting line across tops of arrows
                    fig.line(x1, y1 - arrow_len, x2, y2 - arrow_len, c="load", sw=1.2)
                    fig.text((x1 + x2) / 2.0, (y1 + y2) / 2.0 - arrow_len - 6, f"{abs(w):g} kN/m{lbl_case}", c="load", size=12, a="m")
        elif ltype == "point":
            mid = str(ld.get("member") or ld.get("element"))
            el_def = next((e for e in elements if str(e["id"]) == mid), None)
            if el_def:
                n1 = node_map.get(str(el_def["node1"]))
                n2 = node_map.get(str(el_def["node2"]))
                if n1 and n2:
                    x1, y1 = X(n1["x"]), Y(n1["y"])
                    x2, y2 = X(n2["x"]), Y(n2["y"])
                    P = float(ld.get("P", 0.0))
                    dx = float(n2["x"]) - float(n1["x"])
                    dy = float(n2["y"]) - float(n1["y"])
                    L_real = math.hypot(dx, dy)
                    a = float(ld.get("a", L_real / 2.0))
                    t = a / L_real if L_real > 0 else 0.5
                    bx = x1 + t * (x2 - x1)
                    by = y1 + t * (y2 - y1)
                    fig.arrow(bx, by - 40, bx, by - 2, c="load", sw=2.0, head=8)
                    fig.text(bx, by - 46, f"{abs(P):g} kN{lbl_case}", c="load", size=12, a="m")

    # 4. Nodes (drawn on top)
    for n in nodes:
        nx, ny = X(n["x"]), Y(n["y"])
        fig.circle(nx, ny, 12, c="ink", f="paper", sw=1.4)
        fig.text(nx, ny + 4, str(n["id"]), c="ink", size=12, a="m", b=True)

    return fig


def diagram_figure(result, kind):
    """Draws internal force diagram for 'N', 'V', or 'M'."""
    nodes = result.get("nodes", [])
    members = result.get("members", [])
    if not nodes or not members:
        fig = Fig(300)
        fig.text(500, 150, f"No diagram for {kind}", c="muted", size=16)
        return fig

    X, Y, H, scale = _transformers(nodes)
    fig = Fig(H)
    node_map = {str(n["id"]): n for n in nodes}

    # Find maximum absolute value across all members
    max_val = 0.0
    for m in members:
        diag = m.get("diagram", {})
        vals = diag.get(kind, [])
        for v in vals:
            if abs(v) > max_val:
                max_val = abs(v)
    if max_val < 1e-6:
        max_val = 1.0

    diag_scale = 42.0 / max_val
    col = "sfd" if kind == "V" else "bmd" if kind == "M" else "react"
    diag_sign = -1.0 if kind == "M" else 1.0  # M on tension side (sagging + plots below baseline)

    title_map = {"N": "Axial Force Diagram N (kN)", "V": "Shear Force Diagram V (kN)", "M": "Bending Moment Diagram M (kNm)"}
    fig.text(50, 30, title_map.get(kind, kind), c="ink", size=15, a="l", b=True)

    for m in members:
        n1 = node_map.get(str(m["node1"]))
        n2 = node_map.get(str(m["node2"]))
        if not n1 or not n2:
            continue
        x1c, y1c = X(n1["x"]), Y(n1["y"])
        x2c, y2c = X(n2["x"]), Y(n2["y"])
        Lpx = math.hypot(x2c - x1c, y2c - y1c)
        if Lpx < 1:
            continue

        # Baseline
        fig.line(x1c, y1c, x2c, y2c, c="muted", sw=1.0, dash=[4, 3])

        # Normal vector pointing "above" beam in screen space
        ldx = (x2c - x1c) / Lpx
        ldy = (y2c - y1c) / Lpx
        nx = ldy
        ny = -ldx

        diag = m.get("diagram", {})
        x_arr = diag.get("x", [0.0, m.get("L", 1.0)])
        v_arr = diag.get(kind, [0.0, 0.0])
        L_real = m.get("L", 1.0)
        if L_real <= 0:
            L_real = 1.0

        curve_pts = []
        for xi, val in zip(x_arr, v_arr):
            t = xi / L_real
            bx = x1c + t * (x2c - x1c)
            by = y1c + t * (y2c - y1c)
            off = val * diag_scale * diag_sign
            curve_pts.append((bx + nx * off, by + ny * off))

        # Filled polygon along baseline
        fill_poly = [(x1c, y1c)] + curve_pts + [(x2c, y2c)]
        fig.poly(fill_poly, c=col, f=col, fo=0.18, sw=1.5, closed=True)

        # Drop lines at ends
        fig.line(x1c, y1c, curve_pts[0][0], curve_pts[0][1], c=col, sw=1.0)
        fig.line(x2c, y2c, curve_pts[-1][0], curve_pts[-1][1], c=col, sw=1.0)

        # Labels: at ends and at peak
        def place_val_label(val, pt):
            if abs(val) < max_val * 0.04:
                return
            px, py = pt
            out_dir = 1.0 if (val * diag_sign >= 0) else -1.0
            lx = px + nx * 14 * out_dir
            ly = py + ny * 14 * out_dir
            txt = f"{val:.1f}"
            fig.text(lx, ly + 3, txt, c=col, size=11, a="m", b=True)

        place_val_label(v_arr[0], curve_pts[0])
        place_val_label(v_arr[-1], curve_pts[-1])

        # Interior extreme
        peak_idx = -1
        peak_abs = 0.0
        for idx in range(1, len(v_arr) - 1):
            if abs(v_arr[idx]) > peak_abs:
                peak_abs = abs(v_arr[idx])
                peak_idx = idx
        if peak_idx > 0 and peak_abs > max_val * 0.08:
            place_val_label(v_arr[peak_idx], curve_pts[peak_idx])

    # Nodes on top
    for n in nodes:
        nx, ny = X(n["x"]), Y(n["y"])
        fig.circle(nx, ny, 4, c="ink", f="paper", sw=1.0)

    return fig


def frame_figures(result, member=None):
    """Returns {"model", "N", "V", "M"} specs."""
    return {
        "model": model_figure(result, member=member).spec(),
        "N": diagram_figure(result, "N").spec(),
        "V": diagram_figure(result, "V").spec(),
        "M": diagram_figure(result, "M").spec(),
    }
