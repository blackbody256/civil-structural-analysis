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
        "summary": "Any beam drawn with its supports and loads, rectangular or flanged (T or L). The loads, "
                   "including a slab on the beam, are analysed by the matrix stiffness method first.",
        "checks": ["Matrix stiffness analysis", "Load from a one-way or two-way slab", "Durability, cover & fire",
                   "Sagging and hogging bending", "Vertical shear (strut inclination)", "Deflection of every span",
                   "Flange longitudinal shear", "Min/max steel, spacing & cracking"],
    },
    {
        "id": "slab", "title": "Slab", "subtitle": "Solid one-way & two-way, ribbed", "chapter": 3, "page": 17,
        "status": "active", "url": "/slab",
        "summary": "Solid one-way and two-way slabs, per metre width, and ribbed slabs on Maxpans, per rib as a T-beam: "
                   "loads analysed first, then bending, shear, deflection, fire and detailing.",
        "checks": ["Pattern-loaded strip analysis & two-way coefficients", "Ribbed slabs on Maxpans", "Durability, cover & fire",
                   "Sagging and hogging bending", "Shear resistance without links (vRd,c)",
                   "Deflection of every span", "Min/max steel, spacing & crack control"],
    },
    {
        "id": "flat-slab", "title": "Flat slab", "subtitle": "Column-supported", "chapter": 7, "page": 51,
        "status": "planned",
        "summary": "Slabs supported directly on columns.",
        "checks": ["Flexure", "Deflection", "Punching shear", "Detailing at columns"],
    },
    {
        "id": "foundation", "title": "Pad foundation", "subtitle": "Spread footing", "chapter": 6, "page": 43,
        "status": "active", "url": "/foundation",
        "summary": "Rectangular pad under a column: bearing pressure by the prescriptive method, overturning, "
                   "then bending at the column faces, beam shear, punching shear and detailing.",
        "checks": ["Bearing pressure (presumed values)", "Overturning (EQU)", "Bending at the column faces",
                   "Beam shear at d", "Punching shear with the ground reaction deducted", "Min/max steel, spacing & cracks"],
    },
    {
        "id": "retaining-wall", "title": "Retaining wall", "subtitle": "Cantilever wall", "chapter": 9,
        "page": 67, "status": "planned",
        "summary": "Embedded and gravity cantilever retaining walls.",
        "checks": ["Sliding", "Toppling", "Bearing", "Stem & base design"],
    },
]
