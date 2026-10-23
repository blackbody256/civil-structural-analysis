"""Structural elements covered by the guide, shown on the landing page."""

ELEMENTS = [
    {
        "id": "column", "title": "Column", "subtitle": "Pillar", "chapter": 5, "page": 33,
        "status": "active", "url": "/column",
        "summary": "Braced or unbraced rectangular columns under axial load and bending about both axes.",
        "checks": ["Durability & cover", "Fire resistance", "Effective length & slenderness",
                   "Second-order moments (nominal curvature)", "Axial + bending resistance (N–M)",
                   "Biaxial bending", "Reinforcement & link detailing"],
    },
    {
        "id": "wall", "title": "Wall", "subtitle": "Load-bearing wall", "chapter": 5, "page": 41,
        "status": "planned",
        "summary": "Vertical elements longer than four times their thickness.",
        "checks": ["Fire resistance", "Minimum vertical & horizontal steel", "Bar spacing"],
    },
    {
        "id": "beam", "title": "Beam", "subtitle": "Rectangular & flanged", "chapter": 4, "page": 25,
        "status": "active", "url": "/beam",
        "summary": "Simply supported, continuous or cantilever beams, rectangular or flanged (T or L).",
        "checks": ["Durability & cover", "Fire resistance", "Bending (K, K′, lever arm)",
                   "Compression steel where K > K′", "Vertical shear (strut inclination)",
                   "Deflection (span/depth)", "Flange longitudinal shear", "Min/max steel, spacing & cracking"],
    },
    {
        "id": "slab", "title": "Slab", "subtitle": "One-way, two-way & ribbed", "chapter": 3, "page": 17,
        "status": "planned",
        "summary": "Solid and ribbed slabs supported on beams or walls.",
        "checks": ["Flexure", "Deflection (span/depth)", "Shear vRd,c", "Two-way moment coefficients",
                   "Spacing rules"],
    },
    {
        "id": "flat-slab", "title": "Flat slab", "subtitle": "Column-supported", "chapter": 7, "page": 51,
        "status": "planned",
        "summary": "Slabs supported directly on columns.",
        "checks": ["Flexure", "Deflection", "Punching shear", "Detailing at columns"],
    },
    {
        "id": "foundation", "title": "Pad foundation", "subtitle": "Spread footing", "chapter": 6, "page": 43,
        "status": "planned",
        "summary": "Pad footings designed to Eurocode 7 and Eurocode 2.",
        "checks": ["Bearing pressure", "Overturning (EQU)", "Bending", "Beam shear & punching shear"],
    },
    {
        "id": "retaining-wall", "title": "Retaining wall", "subtitle": "Cantilever wall", "chapter": 9,
        "page": 67, "status": "planned",
        "summary": "Embedded and gravity cantilever retaining walls.",
        "checks": ["Sliding", "Toppling", "Bearing", "Stem & base design"],
    },
]
