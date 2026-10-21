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

1. **Choose element**: the landing page lists every element in the guide. **Column** is available now;
   wall, beam, slab, flat slab, pad foundation and retaining wall are planned.
2. **Inputs**: materials, geometry, reinforcement, restraint, loads, and durability and fire, each in a
   collapsible section that shows a one-line summary when closed. Rarely used inputs sit under "More options".
   The cross-section and elevation are drawn to scale as you type. Small pop-over calculators work out NEd
   from Gk/Qk, φef (creep) and k from beam sizes. Examples, opening a saved inputs file and reset share
   one menu.
3. **Running checks**: an animated run through every test in the guide's order, with ✓/✕ per test.
4. **Report**: the verdict and the governing check first, a list of what needs attention and the
   utilisations from highest down, then the drawings, N–M interaction charts and the Fig 2/3 design path,
   then the full calculation sheet in collapsible groups. Every reference opens the guide at the right page.
   The **Export** menu downloads the PDF report or the inputs (JSON), or prints the page.

## Column checks (Chapter 5)

| Group | Check | Guide reference |
|---|---|---|
| Scope | C ≤ 50/60, 400 ≤ fyk ≤ 600; long side ≤ 4 × short side (else wall) | Ch 1, Ch 3 Fig 1, Ch 5 Walls |
| Durability & cover | Table 8 cover for exposure + class; bond cover to links and main bars | Ch 2 Tables 7–8, Exp 4.1; Ch 10 |
| Fire | Table 2 (method A) bmin / axis distance, with its validity limits | Ch 5 Table 2 |
| Slenderness | l0 (Exp 5.15 = Table 4, Exp 5.16, Fig 5), λ = 3.46·l0/h, λlim = 20ABC/√n | Ch 5 Figs 2, 5, 6, Table 4 |
| Design moments | ei, M01, M02; nominal curvature (Kr, Kφ, e2, M2); MEd = max(M02, M0e + M2, M01 + 0.5M2) | Ch 5 Fig 3, Fig 4 |
| Resistance | NRd,max; MRd at NEd by strain compatibility (Figs 7–8), As,req vs As,prov; biaxial Exp 5.39 | Ch 5 Figs 7–9, Table 5 |
| Detailing | φ ≥ 12; As,min / As,max; bar clear spacing; link Ø and spacing; 150 mm restraint rule; lap length | Ch 5 p.41–42, Ch 10 Tables 8, 13 |

The numeric tables from the guide (concrete properties, ψ factors, Table 4, Table 5, Table 13) are NumPy
arrays in `ec2/tables.py`. The tests check them against the formulas, for example that Exp 5.15 reproduces
every cell of Table 4. The section model reproduces the guide's design charts (Fig 9a–e).

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
  durability.py     Ch 2 Table 8 · fire.py  Ch 5 Table 2 · actions.py  Ch 1 combinations
  geometry.py       section and bar layout · interaction.py  N–M resistance
  slenderness.py    effective length, slenderness, nominal curvature
  column.py         the column procedure → report data
reports/column_pdf.py   downloadable PDF report (reportlab)
static/             HTML pages, JS, and fonts (IBM Plex for the pages, DejaVu for the PDF)
  css/base.css      theme tokens (light and dark) and shared components
  css/landing.css · form.css · run.css · report.css   one stylesheet per page
tests/              pytest suite
```

To add an element (for example a slab), put its procedure in `ec2/<element>.py` and return the same
report structure (`checks`, `summary`, `plots`). Then add a page under `static/` and mark it `active`
in `ec2/elements.py`.

## Limits

Rectangular sections only, normal-weight concrete up to C50/60, and 50-year durability covers with
20 mm aggregate. Fire is checked by the tabulated method A for braced columns. The tool is for
learning and preliminary checking: a qualified structural engineer must verify the inputs and results.
