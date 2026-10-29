# EC2 Element Checker

A local web app that checks reinforced-concrete elements against the procedures in
*How to Design Concrete Structures using Eurocode 2* (The Concrete Centre, 2006), using the
UK National Annex values the guide uses. There is no login and nothing leaves your computer.

* **Backend:** Python (Flask). The engineering lives in `ec2/`; the PDF report is built in `reports/`.
* **Frontend:** plain HTML, CSS and JavaScript with hand-drawn SVG, so it works offline.
* **Look:** a warm "Stone & Petrol" palette with light and dark themes (the menu at the top right follows
  your system by default), set in IBM Plex Sans and IBM Plex Mono, bundled under the SIL Open Font License.

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Then open <http://127.0.0.1:5000>.

## How it works

1. **Choose element**: the landing page lists every element in the guide. **Column** and **beam** are
   available now; wall, slab, flat slab, pad foundation and retaining wall are planned.
2. **Inputs**: each group of inputs sits in a collapsible section that shows a one-line summary when
   closed. Rarely used inputs sit under "More options". The cross-section and elevation are drawn to scale
   as you type. Examples, opening a saved inputs file and reset share one menu.
3. **Running checks**: an animated run through every test in the guide's order, with ✓/✕ per test.
4. **Report**: the verdict and the governing check first, a list of what needs attention and the
   utilisations from highest down, then the drawings and the design path, then the full calculation sheet
   in collapsible groups. The **Export** menu downloads the PDF report or the inputs (JSON), or prints the page.

The report has no reference column and no references to the guide's figures and tables: each check shows
its formula with the numbers substituted. The PDF is set in Times New Roman 12 pt. If Times New Roman is not
installed (`ttf-mscorefonts-installer` on Ubuntu), the bundled Liberation Serif is used; it has the same
metrics. The web report uses the same face for the calculation sheet, inputs and assumptions.

## Column (Chapter 5)

The user enters the axial load and the end moments. **Bending** is either uniaxial (moments about y–y
only) or biaxial (moments about both axes). The link spacing is calculated, not entered.

| Group | Check |
|---|---|
| Scope | C ≤ 50/60, 400 ≤ fyk ≤ 600; long side ≤ 4 × short side (else wall) |
| Durability & cover | Cover for the exposure and concrete class; bond cover to links and main bars |
| Fire | Minimum width and axis distance, with the validity limits of the tabulated method |
| Slenderness | l0 from the end stiffnesses or the standard cases, λ = 3.46·l0/h, λlim = 20ABC/√n |
| Design moments | ei, M01, M02; nominal curvature (Kr, Kφ, e2, M2); MEd = max(M02, M0e + M2, M01 + 0.5M2) |
| Resistance | NRd,max; MRd at NEd by strain compatibility, As,req vs As,prov; biaxial interaction when biaxial |
| Detailing | φ ≥ 12; As,min = 0.1NEd/fyd ≥ 0.002Ac; As ≤ 0.04Ac; bar spacing; link φ ≥ max(6, φ/4); 150 mm restraint rule; lap length |
| Links | s = min(12φ, 0.6·bmin, 240) near beams and slabs, 1.67 × that elsewhere, rounded down to 25 mm |

## Beam (Chapter 4)

The user first chooses a **rectangular** or **flanged** (T or L) section, then draws the beam: its length,
its supports (pinned, roller or fixed, anywhere along it) and its loads. On the drawing canvas a tool is
picked and the beam clicked to place a support, point load, part-length uniform load, varying load or
moment; items can be dragged, their ends stretched, and deleted. The same supports and loads appear in
tables for exact values.

The check then works in three steps:

1. **Loading.** The design line load w = 1.35·gk + 1.5·qk (no 0.925 reduction) from the uniform loads,
   the beam's self-weight and, with "Slab on top of the beam", the slab: a one-way slab through its
   tributary width (w = wslab × btrib), a two-way slab through the equivalent uniform loads for bending,
   wslab × (Lx/6)·[3 − (Lx/Ly)²], and for shear, wslab × (Lx/4)·[2 − Lx/Ly], on the long beam (Lx/3 and
   Lx/4 on the short beam). Further loads are entered as design values or as gk or qk, which are factored.
2. **Analysis.** The client's matrix stiffness solver (`ec2/analysis.py`, from BeamViz Pro) analyses the
   beam. The analytical model is numbered as in the textbook method (nodes at the ends, supports and
   changes of stiffness; free degrees of freedom first), and the report shows the beam with its loads and
   dimensions, the analytical model, the support reactions, the shear force and bending moment diagrams
   (positive values below the axis) and the deflected shape, with tables of reactions, member end forces
   and joint displacements. The live diagrams on the input page come from the same analysis.
3. **Design.** Every critical value from the analysis is designed for: the largest sagging moment with
   the bottom bars, the largest hogging moment with the top bars, and the largest shear. A value that is
   zero is not designed for.

The default example is the client's: a 20 m beam fixed at one end on two rollers, with a 30 kN/m varying
load, 200 kN and 150 kN point loads and a 90 kN·m moment, E = 28 GPa and 1.5I over the first 6 m. It gives
the reactions 146.33 kN and 281.19 kN·m, 243.46 kN and 50.21 kN.

| Group | Check |
|---|---|
| Scope | C ≤ 50/60, 400 ≤ fyk ≤ 600 |
| Durability & cover | Cover for the exposure and concrete class; bond cover to links and main bars |
| Fire | Minimum web width and axis distance of the bottom bars |
| Design actions | w from the loads and the slab; reactions and the design values from the analysis |
| Bending | For sagging and for hogging: K = M/(b·d²·fck) against K′, lever arm z, As,req, compression steel when K > K′; flanged sections with the neutral axis in the flange or the web |
| Shear | Concrete strut capacity; link spacing calculated from Asw/s with ρw,min and 0.75d; spacing of link legs; longitudinal shear in the flange |
| Deflection | For every span: basic span/depth ratio × F1 × F2 × F3 against the actual l/d (K from the span's end conditions); the elastic deflection for information |
| Detailing | As,min of each tension face, As,max, clear spacing of the bottom and top bars, crack control |

The numeric tables from the guide (concrete properties, ψ factors, effective length, biaxial exponent,
K′, strut capacity, minimum shear ratio, crack control, lap lengths) are NumPy arrays in `ec2/tables.py`.
The tests check them against the formulas they come from. The column section model reproduces the guide's
design charts.

## Tests

```bash
.venv/bin/python -m pytest -q
```

## Layout

```
app.py              Flask routes: pages, JSON API, PDF download, guide PDF
ec2/                calculation engine (no web code)
  tables.py         numeric tables from the guide (NumPy)
  materials.py      concrete and reinforcement
  durability.py     cover · fire.py  fire tables · actions.py  load combinations
  geometry.py       column section and bar layout · interaction.py  N–M resistance
  slenderness.py    effective length, slenderness, nominal curvature
  flexure.py        bending, shear and span/depth for beams
  analysis.py       matrix stiffness beam analysis (the client's BeamViz Pro solver)
  column.py · beam.py   each element's procedure → report data
reports/            PDF reports (reportlab): pdf_base.py shared layout, one module per element;
                    beam_figures.py draws the analysis figures once for the page and the PDF
static/             HTML pages, JS, and fonts (IBM Plex for the pages, Liberation Serif for the PDF)
  css/base.css      theme tokens (light and dark) and shared components
  css/landing.css · form.css · run.css · report.css   one stylesheet per page
  js/form-kit.js    shared input-page helpers; js/report-<element>.js  each element's drawings
  js/beam-canvas.js the beam drawing canvas; js/figure-spec.js draws the analysis figures
tests/              pytest suite
```

To add an element (for example a slab), put its procedure in `ec2/<element>.py` and return the same
report structure (`checks`, `summary`, `plots`), add a PDF module in `reports/` and register both in
`ELEMENT_HANDLERS` in `app.py`. Then add `static/<element>.html`, a `report-<element>.js` for its drawings,
and mark it `active` in `ec2/elements.py`. The run and report pages serve every element.

## Limits

Rectangular columns; rectangular, T and L beams; normal-weight concrete up to C50/60; 50-year durability
covers with 20 mm aggregate. Fire is checked by the tabulated method. The beam analysis is linear elastic
(no redistribution) with the gross section unless I is entered. The tool is for learning and preliminary
checking: a qualified structural engineer must verify the inputs and results.
