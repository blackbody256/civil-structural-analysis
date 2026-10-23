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
