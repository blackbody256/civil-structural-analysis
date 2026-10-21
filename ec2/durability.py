"""Durability and cover: Chapter 2, Table 8.

Recommendations for normal-weight reinforced concrete with at least a 50-year working
life and 20 mm maximum aggregate (from BS 8500). Each exposure row maps a cement group
to eight cells, one per nominal cover 15…50 mm (+Δcdev):
  None       – not recommended ("—" in the table)
  BS8500     – "See BS 8500"
  SAME       – "<<<", same quality as the cell to the left
  dict       – minimum strength class, max w/c, min cement content, designated concrete
"""
from .materials import strength_fck

COVERS = (15, 20, 25, 30, 35, 40, 45, 50)
BS8500 = "BS8500"
SAME = "<<<"
NR = None


def _q(cls, wc, cement, designated=None, notes=""):
    return {"class": cls, "wc": wc, "cement": cement, "designated": designated, "notes": notes}


EXPOSURE_ROWS = [
    {
        "id": "XC1", "classes": "XC1", "orientation": "any",
        "example": "Internal elements (except humid locations)",
        "groups": {"All": [_q("C20/25", 0.70, 240, "RC20/25"), SAME, SAME, SAME, SAME, SAME, SAME, SAME]},
    },
    {
        "id": "XC2", "classes": "XC2 + AC-1", "orientation": "any",
        "example": "Buried concrete in AC-1 ground conditions",
        "note": "For sections less than 140 mm thick refer to BS 8500.",
        "groups": {"All": [NR, NR, _q("C25/30", 0.65, 260, "RC25/30"), SAME, SAME, SAME, SAME, SAME]},
    },
    {
        "id": "XC3/4", "classes": "XC3 & XC4", "orientation": "vertical",
        "example": "Vertical surface protected from direct rainfall",
        "groups": {"All except IVB": [
            NR, _q("C40/50", 0.45, 340, "RC40/50"), _q("C30/37", 0.55, 300, "RC30/37"),
            _q("C28/35", 0.60, 280, "RC28/35"), _q("C25/30", 0.65, 260, "RC25/30"), SAME, SAME, SAME]},
    },
    {
        "id": "XC3/4-XF1", "classes": "XC3 & XC4 + XF1", "orientation": "vertical",
        "example": "Exposed vertical surfaces",
        "groups": {"All except IVB": [
            NR, _q("C40/50", 0.45, 340, "RC40/50"), _q("C30/37", 0.55, 300, "RC30/37"),
            _q("C28/35", 0.60, 280, "RC28/35"), SAME, SAME, SAME, SAME]},
    },
    {
        "id": "XC3/4-XF3", "classes": "XC3 & XC4 + XF3", "orientation": "horizontal",
        "example": "Exposed horizontal surfaces",
        "groups": {"All except IVB": [
            NR, _q("C40/50", 0.45, 340, "RC40/50XF", "freeze/thaw resisting aggregates"),
            SAME, SAME, SAME, SAME, SAME, SAME]},
    },
    {
        "id": "XC3/4-XF3-air", "classes": "XC3 & XC4 + XF3 (air entrained)", "orientation": "horizontal",
        "example": "Exposed horizontal surfaces, air-entrained concrete",
        "groups": {"All except IVB": [
            NR, NR, _q("C32/40", 0.55, 300, None, "plus air; freeze/thaw resisting aggregates"),
            _q("C28/35", 0.60, 280, "PAV2", "plus air; freeze/thaw resisting aggregates"),
            _q("C25/30", 0.60, 280, "PAV1", "plus air; may not suit severe abrasion"), SAME, SAME, SAME]},
    },
    {
        "id": "XD1", "classes": "XD1", "orientation": "any",
        "example": "Elements subject to airborne chlorides",
        "note": "Also adequate for exposure class XC3/4.",
        "groups": {"All": [
            NR, NR, _q("C40/50", 0.45, 360), _q("C32/40", 0.55, 320), _q("C28/35", 0.60, 300), SAME, SAME, SAME]},
    },
    {
        "id": "XD3", "classes": "XD3", "orientation": "horizontal",
        "example": "Car park decks and areas subject to de-icing spray",
        "note": "Also adequate for exposure class XC3/4.",
        "groups": {
            "IIB-V, IIIA": [NR] * 5 + [_q("C35/45", 0.40, 380), _q("C32/40", 0.45, 360), _q("C28/35", 0.50, 340)],
            "CEM I, IIA, IIB-S, SRPC": [NR] * 5 + [BS8500, _q("C40/50", 0.40, 380), _q("C35/45", 0.45, 360)],
            "IIIB, IVB-V": [NR] * 5 + [_q("C32/40", 0.40, 380), _q("C28/35", 0.45, 360), _q("C25/30", 0.50, 340)],
        },
    },
    {
        "id": "XD3-XF2", "classes": "XD3 + XF2", "orientation": "vertical",
        "example": "Vertical elements subject to de-icing spray and freezing",
        "note": "Also adequate for exposure class XC3/4.",
        "groups": {
            "IIB-V, IIIA": [NR] * 5 + [_q("C35/45", 0.40, 380), _q("C32/40", 0.45, 360), _q("C32/40", 0.50, 340)],
            "CEM I, IIA, IIB-S, SRPC": [NR] * 5 + [BS8500, _q("C40/50", 0.40, 380), _q("C35/45", 0.45, 360)],
            "IIIB, IVB-V": [NR] * 5 + [_q("C32/40", 0.40, 380), _q("C32/40", 0.45, 360), _q("C32/40", 0.50, 340)],
        },
    },
    {
        "id": "XD3-XF4", "classes": "XD3 + XF4", "orientation": "horizontal",
        "example": "Car park decks, ramps and external areas subject to freezing and de-icing salts",
        "note": "Also adequate for exposure class XC3/4.",
        "groups": {
            "CEM I, IIA, IIB-S, SRPC": [NR] * 5 + [
                BS8500, _q("C40/50", 0.40, 380, None, "freeze/thaw resisting aggregates"), SAME],
            "IIB-V, IIIA, IIIB (air entrained)": [NR] * 5 + [
                _q("C28/35", 0.40, 380, None, "air entrained; freeze/thaw resisting aggregates"),
                _q("C28/35", 0.45, 360, None, "air entrained; freeze/thaw resisting aggregates"),
                _q("C28/35", 0.50, 340, None, "air entrained; freeze/thaw resisting aggregates")],
        },
    },
    {
        "id": "XS1-XF1", "classes": "XS1 + XF1", "orientation": "vertical",
        "example": "Exposed vertical surfaces near the coast",
        "note": "Also adequate for exposure class XC3/4.",
        "groups": {
            "CEM I, IIA, IIB-S, SRPC": [NR, NR, NR, BS8500, _q("C35/45", 0.45, 360), _q("C32/40", 0.50, 340), SAME, SAME],
            "IIB-V, IIIA": [NR, NR, NR, BS8500, _q("C32/40", 0.45, 360), _q("C28/35", 0.50, 340),
                            _q("C25/30", 0.55, 320), SAME],
            "IIIB": [NR, NR, NR, _q("C32/40", 0.40, 380), _q("C25/30", 0.50, 340), _q("C25/30", 0.50, 340),
                     _q("C25/30", 0.55, 320), SAME],
        },
    },
    {
        "id": "XS1-XF4", "classes": "XS1 + XF4", "orientation": "horizontal",
        "example": "Exposed horizontal surfaces near the coast",
        "note": "Also adequate for exposure class XC3/4.",
        "groups": {"CEM I, IIA, IIB-S, SRPC": [
            NR, NR, NR, BS8500, _q("C40/50", 0.45, 360, None, "freeze/thaw resisting aggregates"), SAME, SAME, SAME]},
    },
]

ROWS_BY_ID = {row["id"]: row for row in EXPOSURE_ROWS}


def rows_for(orientation):
    """Exposure rows relevant to an element; columns and walls use the vertical rows."""
    return [r for r in EXPOSURE_ROWS if r["orientation"] in ("any", orientation)]


def resolved_cells(row_id, group):
    cells, previous = [], NR
    for cell in ROWS_BY_ID[row_id]["groups"][group]:
        cell = previous if cell == SAME else cell
        cells.append(cell)
        previous = cell
    return cells


def durability_cover(row_id, group, concrete_class):
    """Smallest Table 8 cover (before Δcdev) that suits the chosen concrete class.

    Returns a dict with status 'ok' (cover found) or 'too_weak' (the class is below every
    recommendation in the row), plus 'bs8500_below': the covers smaller than the one found
    for which the table defers to BS 8500 (a smaller cover may be possible there).
    """
    fck = strength_fck(concrete_class)
    cells = resolved_cells(row_id, group)
    options = [(c, cell) for c, cell in zip(COVERS, cells) if isinstance(cell, dict)]
    for cover, cell in options:
        if strength_fck(cell["class"]) <= fck:
            below = [c for c, x in zip(COVERS, cells) if x == BS8500 and c < cover]
            return {"status": "ok", "cover": cover, "spec": cell, "options": options, "bs8500_below": below}
    weakest = min(options, key=lambda o: strength_fck(o[1]["class"]))
    return {"status": "too_weak", "cover": weakest[0], "spec": weakest[1], "options": options, "bs8500_below": []}
