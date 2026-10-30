"""Fire resistance by the tabulated method (BS EN 1992-1-2 method A).

Columns: Chapter 5, Table 2. Each option is a minimum column width b_min and axis
distance a; the table offers alternatives, and meeting any one of them is sufficient.
"""

FIRE_PERIODS = ("none", "R60", "R90", "R120", "R240")


def _opt(b_min, a, min_bars=0, note=""):
    return {"b_min": b_min, "a": a, "min_bars": min_bars, "note": note}


# period -> {"multi": {mu_fi: [options]}, "one": [options]}
COLUMN_TABLE = {
    "R60": {"multi": {0.5: [_opt(200, 36), _opt(300, 31)],
                      0.7: [_opt(250, 46), _opt(350, 40)]},
            "one": [_opt(155, 25)]},
    "R90": {"multi": {0.5: [_opt(300, 45), _opt(400, 38, 8)],
                      0.7: [_opt(350, 53), _opt(450, 40, 8)]},
            "one": [_opt(155, 25)]},
    "R120": {"multi": {0.5: [_opt(350, 45, 8), _opt(450, 40, 8)],
                       0.7: [_opt(350, 57, 8), _opt(450, 51, 8)]},
             "one": [_opt(175, 35)]},
    "R240": {"multi": {0.5: [_opt(450, 75, 8)],
                       0.7: [_opt(600, 70, 0, "method B of BS EN 1992-1-2")]},
             "one": [_opt(295, 70)]},
}


def column_options(period, exposure, mu_fi):
    entry = COLUMN_TABLE[period]
    return entry["one"] if exposure == "one" else entry["multi"][mu_fi]


def check_column_fire(period, exposure, mu_fi, b_min, a, n_bars):
    """Evaluate every Table 2 option; the column passes if it meets any of them."""
    evaluated = []
    for opt in column_options(period, exposure, mu_fi):
        ok = b_min >= opt["b_min"] and a >= opt["a"] and n_bars >= opt["min_bars"]
        evaluated.append({**opt, "ok": ok})
    passing = [o for o in evaluated if o["ok"]]
    governing = passing[0] if passing else min(
        evaluated, key=lambda o: max(o["b_min"] / b_min, o["a"] / a))
    return bool(passing), governing, evaluated


# Beams: Chapter 4, Table 2 (bmin/a pairs in mm). Columns A–D for simply supported beams,
# E–H for continuous beams. Meeting any one pair is sufficient.
BEAM_TABLE = {
    "R60": {"simple": [(120, 40), (160, 35), (200, 30), (300, 25)], "continuous": [(120, 25), (200, 12)]},
    "R90": {"simple": [(150, 55), (200, 45), (300, 40), (400, 35)], "continuous": [(150, 35), (250, 25)]},
    "R120": {"simple": [(200, 65), (240, 60), (300, 55), (500, 50)],
             "continuous": [(200, 45), (300, 35), (450, 35), (500, 30)]},
    "R240": {"simple": [(280, 90), (350, 80), (500, 75), (700, 70)],
             "continuous": [(280, 75), (500, 60), (650, 60), (700, 50)]},
}


def check_beam_fire(period, support, b_min, a):
    evaluated = [{"b_min": bm, "a": am, "ok": b_min >= bm and a >= am} for bm, am in BEAM_TABLE[period][support]]
    passing = [o for o in evaluated if o["ok"]]
    governing = passing[0] if passing else min(evaluated, key=lambda o: max(o["b_min"] / b_min, o["a"] / a))
    return bool(passing), governing, evaluated


# Slabs: Chapter 3, Table 2 (p.18, matching BS EN 1992-1-2 Table 5.8).
# Minimum thickness hs and axis distance a (mm) for solid slabs.
SLAB_FIRE_TABLE = {
    "R60": {"hs": 80, "one_way": 20, "two_way_le_1_5": 10, "two_way_gt_1_5": 15},
    "R90": {"hs": 100, "one_way": 30, "two_way_le_1_5": 15, "two_way_gt_1_5": 20},
    "R120": {"hs": 120, "one_way": 40, "two_way_le_1_5": 20, "two_way_gt_1_5": 25},
    "R240": {"hs": 175, "one_way": 65, "two_way_le_1_5": 40, "two_way_gt_1_5": 50},
}


def check_slab_fire(period, kind, h, a, ly_lx=None):
    """Check fire resistance for a solid slab (Guide Ch 3 Table 2 / BS EN 1992-1-2 Table 5.8).

    kind is 'one_way' or 'two_way'.
    Returns (ok, required {'hs', 'a'}, lines).
    """
    if period == "none":
        return True, {"hs": 0, "a": 0}, ["Fire resistance check: none specified"]
    if period not in SLAB_FIRE_TABLE:
        raise ValueError(f"Unknown fire period {period!r}; expected one of {FIRE_PERIODS}")
    if kind not in ("one_way", "two_way"):
        raise ValueError(f"Unknown slab kind {kind!r}; expected 'one_way' or 'two_way'")

    entry = SLAB_FIRE_TABLE[period]
    hs_req = entry["hs"]
    if kind == "one_way":
        a_req = entry["one_way"]
        desc = f"{period}, one-way solid slab"
    else:
        if ly_lx is None or ly_lx <= 1.5 + 1e-9:
            a_req = entry["two_way_le_1_5"]
            ratio_desc = "ly/lx ≤ 1.5"
        else:
            a_req = entry["two_way_gt_1_5"]
            ratio_desc = "1.5 < ly/lx ≤ 2.0"
        desc = f"{period}, two-way solid slab ({ratio_desc})"

    ok = (h >= hs_req) and (a >= a_req)
    lines = [
        desc,
        f"Minimum slab thickness: {h:g} mm vs required {hs_req} mm ({'satisfied' if h >= hs_req else 'not satisfied'})",
        f"Axis distance: a = {a:.1f} mm vs required {a_req} mm ({'satisfied' if a >= a_req else 'not satisfied'})",
    ]
    return ok, {"hs": hs_req, "a": a_req}, lines

