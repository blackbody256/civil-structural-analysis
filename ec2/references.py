"""Where each rule lives in 'How to Design Concrete Structures using Eurocode 2'.

Pages are the printed page numbers of the guide; the PDF file page is printed + 4.
"""

PDF_PAGE_OFFSET = 4

GUIDE = {
    "ch1_combinations": ("Ch 1, Tables 3–5: combinations of actions", 3),
    "ch2_concrete": ("Ch 2, Table 4: concrete properties", 11),
    "ch2_steel": ("Ch 2, Table 5: reinforcement properties", 12),
    "ch2_cover": ("Ch 2, Exp (4.1): nominal cover", 12),
    "ch2_cover_bond": ("Ch 2, Minimum cover for bond", 13),
    "ch2_table8": ("Ch 2, Table 8: durability and cover", 14),
    "ch2_imperfections": ("Ch 2, Stability and imperfections", 15),
    "ch3_scope": ("Ch 3, Fig 1: scope ≤ C50/60", 19),
    "ch5_table2": ("Ch 5, Table 2: fire resistance of columns", 34),
    "ch5_fig2": ("Ch 5, Fig 2: braced column flow chart", 35),
    "ch5_design_moments": ("Ch 5, Design moments", 35),
    "ch5_fig3": ("Ch 5, Fig 3: nominal curvature method", 36),
    "ch5_eff_length": ("Ch 5, Effective length (Fig 5)", 36),
    "ch5_table4": ("Ch 5, Table 4: effective length factor F", 37),
    "ch5_slenderness": ("Ch 5, Slenderness limit λlim", 37),
    "ch5_fig7_8": ("Ch 5, Figs 7–8: stress block and strains", 37),
    "ch5_resistance": ("Ch 5, Column design resistance", 38),
    "ch5_creep": ("Ch 5, Creep", 38),
    "ch5_biaxial": ("Ch 5, Biaxial bending, Exp (5.39)", 38),
    "ch5_fig9": ("Ch 5, Figs 9a–e: column design charts", 38),
    "ch5_table5": ("Ch 5, Table 5: exponent a", 41),
    "ch5_unbraced": ("Ch 5, Unbraced columns", 41),
    "ch5_walls": ("Ch 5, Walls", 41),
    "ch5_steel_areas": ("Ch 5, Max/min areas of reinforcement", 41),
    "ch5_spacing": ("Ch 5, Spacing requirements for columns", 42),
    "ch1_scope_steel": ("Ch 1, Part 1–1 note 8: fyk 400–600 MPa", 5),
    "ch10_cover": ("Ch 10, Cover", 80),
    "ch10_columns": ("Ch 10, Columns and walls (Table 8)", 86),
    "ch10_table13": ("Ch 10, Table 13: anchorage and lap lengths", 88),
}


def ref(key):
    label, page = GUIDE[key]
    return {"label": label, "page": page}


def ec2(clause):
    return {"label": f"BS EN 1992-1-1 cl. {clause}", "page": None}


def refs(*keys, clauses=()):
    return [ref(k) for k in keys] + [ec2(c) for c in clauses]
