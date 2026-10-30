import copy
import pytest
from ec2.beam import check_beam
from reports.beam_figures import diagrams_figure

CLIENT = {
    "project": {"name": "Example", "ref": "B2"},
    "section": {"shape": "rectangular", "b": 400, "h": 750},
    "span": {"l": 20, "supports": [{"x": 0, "type": "fixed"}, {"x": 10, "type": "roller"}, {"x": 20, "type": "roller"}]},
    "materials": {"concrete": "C30/37", "fyk": 500, "class": "B", "aggregate": "quartzite", "dg": 20},
    "reinforcement": {"bottom_n": 4, "bottom_dia": 20, "top_n": 4, "top_dia": 25, "link_dia": 10, "legs": 2, "cover": 35},
    "durability": {"exposure": "XC1", "cement_group": "All", "fire_period": "R60"},
    "actions": {"mode": "analysis", "gk": 0, "qk": 0, "self_weight": False, "category": "B",
                "loads": [{"type": "linear", "case": "Ed", "w1": 30, "w2": 0, "x1": 0, "x2": 6},
                          {"type": "point", "case": "Ed", "W": 200, "x": 6},
                          {"type": "moment", "case": "Ed", "M": 90, "x": 10},
                          {"type": "point", "case": "Ed", "W": 150, "x": 15}]},
    "stiffness": {"E_method": "enter", "E": 28, "I_method": "enter",
                  "segments": [{"x1": 0, "x2": 6, "I": 8700}, {"x1": 6, "x2": 20, "I": 5800}]},
}


def test_diagram_convention_shear_above_moment_below():
    report = check_beam(copy.deepcopy(CLIENT))
    fig = diagrams_figure(report["plots"]["analysis"])
    items = fig["items"]

    # Baselines are horizontal lines at y = 150 for shear and y = 420 for moment
    shear_baseline = next(it for it in items if it.get("k") == "line" and it["p"][1] == 150 and it["p"][3] == 150)["p"][1]
    moment_baseline = next(it for it in items if it.get("k") == "line" and it["p"][1] == 420 and it["p"][3] == 420)["p"][1]

    # Find the open polylines (curve strokes, closed=False)
    sfd_poly = next(it for it in items if it.get("k") == "poly" and it.get("c") == "sfd" and not it.get("closed"))
    bmd_poly = next(it for it in items if it.get("k") == "poly" and it.get("c") == "bmd" and not it.get("closed"))

    # Points are stored as flat [x0, y0, x1, y1, ...]
    # At x = 0 (first point), V = +146.33 kN. Positive shear is ABOVE the baseline (smaller y).
    assert sfd_poly["p"][1] < shear_baseline

    # In BMD, find the point near x = 15 (sagging moment +251.04).
    # Since x coords are scaled with X(x), we can pair up (x_px, y_px).
    # X(15) is 3/4 along span [X0, X1] where X0=90, X1=920 -> 90 + 0.75 * 830 = 712.5.
    pts = list(zip(bmd_poly["p"][0::2], bmd_poly["p"][1::2]))
    pt_x15 = min(pts, key=lambda p: abs(p[0] - (90 + 15 / 20 * (920 - 90))))
    # Sagging moment is positive, drawn BELOW the baseline (larger y).
    assert pt_x15[1] > moment_baseline


def test_strip_figure():
    from reports.slab_figures import strip_figure
    sec = {
        "slab_type": "one_way",
        "b": 1000, "h": 200, "cover": 25,
        "bottom_x": {"dia": 12, "s": 200, "As": 565},
        "bottom_y": {"dia": 10, "s": 300, "As": 262},
        "top_x": {"dia": 12, "s": 200, "As": 565},
        "top_y": {"dia": None, "s": 200, "As": 0},
    }
    fig = strip_figure(sec)
    assert fig["w"] == 1000
    assert fig["h"] > 200
    # Checks circles for bottom x bars and top x bars
    circles = [it for it in fig["items"] if it.get("k") == "circle"]
    assert len(circles) >= 5  # at 200 spacing across 1000 mm
    # Checks lines for dimensions, cover and bottom y bar
    lines = [it for it in fig["items"] if it.get("k") == "line"]
    assert len(lines) >= 5


def test_panel_figure():
    from reports.slab_figures import panel_figure
    panel = {
        "lx": 5.0, "ly": 6.0,
        "edges": {"top": "continuous", "bottom": "continuous", "left": "continuous", "right": "discontinuous"},
        "case": {"id": "one_short_discontinuous", "label": "One short edge discontinuous"},
        "coefficients": {"bsx_mid": 0.036, "bsx_sup": 0.048, "bsy_mid": 0.024, "bsy_sup": 0.032},
        "moments": {"msx_mid": 9.15, "msx_sup": 12.20, "msy_mid": 6.10, "msy_sup": 8.13},
        "shears": {"VEd": 30.49, "vEd": 0.174, "vRd_c": 0.450, "basis": "0.6 n lx"},
    }
    fig = panel_figure(panel)
    assert fig["w"] == 1000
    assert fig["h"] == 640
    texts = [it["t"] for it in fig["items"] if it.get("k") == "text"]
    assert any("One short edge discontinuous" in t for t in texts)
    assert any("lx = 5.00 m" in t for t in texts)
    assert any("ly = 6.00 m" in t for t in texts)
    # Check that sagging moment is in bmd colour and hogging in accent
    bmd_texts = [it for it in fig["items"] if it.get("k") == "text" and it.get("c") == "bmd"]
    accent_texts = [it for it in fig["items"] if it.get("k") == "text" and it.get("c") == "accent"]
    assert len(bmd_texts) >= 2  # msx_mid and msy_mid
    assert len(accent_texts) >= 2  # top continuous and left continuous

