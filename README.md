# EC2 Element Checker

A local web app that checks reinforced-concrete elements against the procedures in
*How to Design Concrete Structures using Eurocode 2* (The Concrete Centre, 2006), using the
UK National Annex values the guide uses. There is no login and nothing leaves your computer.

* **Backend:** Python (Flask). The engineering lives in `ec2/`; the PDF report is built in `reports/`.
* **Frontend:** plain HTML, CSS and JavaScript with hand-drawn SVG, so it works offline.
* **Look:** a colourful and modern interface with light and dark themes (the menu at the top right follows
  your system by default), set in IBM Plex Sans and IBM Plex Mono, bundled under the SIL Open Font License.

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Then open <http://127.0.0.1:5000>.

## How it works

1. **Home page**: a colourful hero band with a soft multi-stop gradient (light `#E0E7FF` → `#EDE9FE` → `#F0F9FF`; dark `#06080E` → `#0A0F1E` → `#0F0A1E`) and an animated SVG beam model drawing showing loads dropping, support reactions counting up, and shear force and bending moment diagrams tracing left-to-right. Active element cards (Beam and Column) feature unique accent colours, check chips, and hover effects, alongside planned elements as colorful tiles.
2. **Three-step workflow**:
   - **1 Analyse**: draw supports and loads on the beam canvas; solve member stiffness, support reactions, and envelope values.
   - **2 Design**: specify concrete, reinforcement, and durability; evaluate all checks against Eurocode 2 rules.
   - **3 Report**: inspect the verification summary, review substituted calculations, and export a clean PDF.
3. **Interactive canvas editor**: click on the beam or double-click an existing load or support to open an inline floating editor to change values and positions with instant updates.
4. **Report & Export**: the verdict and governing checks first, followed by drawings, design path, and full calculation sheets with substituted numbers. The PDF report features clean running headers ("Beam check to Eurocode 2") with no project name or reference in the header.

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

The beam module is split into three guided workflow tabs:

### 1. Analysis Tab
The user chooses a **rectangular** or **flanged** (T or L) section, sets the section size and concrete class (which sets $E_{cm}$), and draws the beam model.
* **Canvas Tools & Inline Editor**: place pinned, roller, or fixed supports, point loads, uniform loads, varying loads, or applied moments. Clicking the beam places an item and opens an inline floating editor (`CanvasEditor`); double-clicking an item re-opens the editor for quick value adjustments. Items can also be dragged or edited via the data tables.
* **Loads & Slab Distribution**: line load $w = 1.35\cdot g_k + 1.5\cdot q_k$ from self-weight, uniform loads, and optional slab load (one-way via tributary width; two-way via equivalent uniform loads for bending and shear).
* **Matrix Stiffness Solver**: clicking "Analyse" runs `ec2/analysis.py` (decoupled from design inputs so incomplete reinforcement does not block analysis).
* **Diagram Conventions**: Positive shear and hogging moments are drawn above the x-axis; negative shear and sagging moments below it.
* **Analytical Model Display**: nodes circled in orange, elements in teal, free DOFs in indigo, and restrained DOFs in violet.
* **Results Block**: envelope metrics ($M^+_{Ed}$, $M^-_{Ed}$, $|V|$, $\delta_{max}$, $w$), all 5 analytical figures (loading, model, reactions, diagrams, deflection), and tables for reactions, member end forces, and joint displacements.

### 2. Design Tab
Enabled once an analysis succeeds (or when entering actions directly).
* **Design Values from Analysis**: read-only summary of $M^+_{Ed}$, $M^-_{Ed}$, and $V_{Ed}$. Ticking "Adjust these design values" unlocks the fields and switches to direct mode.
* **Design Inputs**: flange parameters ($b_{eff}$ calculation or manual entry), reinforcement (bottom, top, and link sizing and layers), durability and fire resistance, and options (partitions, $K'$ limit).
* **Checks & Verdict**: clicking "Run design checks" validates the beam against Eurocode 2 with animated result rows grouped by check type, highlighting failing checks.

### 3. Report Tab
Enabled after design checks pass.
* Embeds the full calculation report inside an auto-resizing clean iframe (`?embed=1` hides the top bar and inputs link).
* Action buttons for **Download PDF report** (`/api/beam/report.pdf`), **Print**, and **Open in a new tab** (`/beam/report`).

### Examples
The **Examples and files** menu provides:
1. **Client's example (correct)**: 20 m beam, fixed and two rollers, varying load ($30 \to 0$ kN/m), 200 kN and 150 kN point loads, 90 kN·m moment, $E = 28$ GPa and $1.5I$ over the first 6 m. Reactions: 146.33 kN and 281.19 kN·m at node 1, 243.46 kN at node 3, 50.21 kN at node 4. All 17 checks pass.
2. **Client's example with mistakes (wrong)**: Same beam and loads, but with a 300 × 500 mm section, C25/30 concrete, 2H16 top and bottom bars, H6 links, XC3/4 exposure, and R90 fire period. Exactly 6 checks fail (`cover_durability`, `tension_sag`, `tension_hog`, `deflection`, `cracking_bottom`, `cracking_top`).

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

## Slab (solid one-way and two-way, ribbed) (Chapter 3)

The slab module checks solid reinforced concrete slabs designed per metre width ($b = 1000$ mm), and ribbed
slabs on Maxpan clay blocks designed per rib (see "Ribbed slab" below).

### Method
* **One-way solid slab**: Analysed as a 1 m wide continuous strip across supports.
  - **Pattern loading**: For continuous slabs with two or more spans, three load cases are solved:
    * Case A: all spans loaded ($1.35\cdot n_g + 1.5\cdot n_q$)
    * Case B: all spans $1.35\cdot n_g$, odd spans also $1.5\cdot n_q$
    * Case C: all spans $1.35\cdot n_g$, even spans also $1.5\cdot n_q$
  - The governing envelope yields maximum sagging moment, maximum hogging moment, and maximum shear force with their locations and governing case.
* **Two-way solid slab**: Rectangular panel supported on four edges by beams or walls with restrained corners.
  - Bending moments are determined using Table 8 moment coefficients from the guide (BS 8110-1 Table 3.14) across all 9 edge boundary combinations with linear interpolation in $l_y/l_x \le 2.0$.
  - Design moments: $m_{sx} = \beta_{sx}\cdot n\cdot l_x^2$ and $m_{sy} = \beta_{sy}\cdot n\cdot l_x^2$ per metre width.
  - Design shear: $V_{Ed} = 0.5\cdot n\cdot l_x$ (or $0.6\cdot n\cdot l_x$ at continuous long edges).

### Checks
| Group | Check |
|---|---|
| Scope | Concrete class $\le$ C50/60, $400 \le f_{yk} \le 600$ MPa |
| Durability & cover | $c_{nom} \ge c_{min,dur} + \Delta c_{dev}$; bond cover to outer bars (no links) |
| Fire | Tabulated minimum slab thickness $h_s$ and axis distance $a$ (BS EN 1992-1-2 Table 5.8 / Guide Table 2) |
| Design actions | Envelope of pattern loading (one-way) or Table 8 moment coefficients (two-way) |
| Bending | $K = M/(b\cdot d^2\cdot f_{ck}) \le K'$ (0.168 limited); no compression steel in slabs (fail requires thickness increase); $z = \min(d/2(1 + \sqrt{1 - 3.53K}), 0.95d)$; $A_{s,req} = M/(f_{yd}\cdot z)$ vs provided $A_s$ |
| Shear | Design shear stress $v_{Ed} = V_{Ed}/(b\cdot d) \le v_{Rd,c}$ (EC2 Cl 6.2.2 concrete shear capacity without reinforcement; no shear links in slabs) |
| Deflection | Span-to-effective-depth ratio $l/d \le (l/d)_{allow} = \text{basic } l/d \times F_1 \times F_2 \times F_3$ (quasi-permanent stress $\sigma_s$) |
| Detailing | $A_{s,min} = \max(0.26\frac{f_{ctm}}{f_{yk}}bd, 0.0013bd)$, $A_{s,max} = 0.04bh$; secondary steel $\ge 20\%$ main steel (one-way); bar spacing limits ($\min(2h, 250)$ mm main, $\min(3h, 400)$ mm secondary); clear spacing; crack control ($h \le 200$ mm deemed satisfied; crack table limits for $h > 200$ mm) |

### Examples
1. **One-way slab (correct)**: Three equal spans of 4.5 m (L = 13.5 m), $h = 175$ mm, C30/37 concrete, $g_k = 1.5$ kN/m² + self-weight, $q_k = 2.5$ kN/m², category B, XC1, R60, cover 25 mm. Reinforcement: bottom x H12 @ 200, bottom y H10 @ 300, top x H12 @ 200. All 17 checks pass.
2. **One-way slab with mistakes**: Same spans and loads, but $h = 125$ mm, C25/30 concrete, bottom x H8 @ 300, no top bars, cover 15 mm, exposure XC3/4, fire R90. Exactly 7 checks fail.
3. **Two-way slab (correct)**: Interior panel $5.0 \times 6.0$ m with all four edges continuous, $h = 200$ mm, C30/37 concrete, $g_k = 1.5$ kN/m² + self-weight, $q_k = 2.5$ kN/m², XC1, R60, cover 25 mm. Reinforcement: H10 @ 200 in all layers. All 16 checks pass.
4. **Two-way slab with mistakes**: Same panel with all four edges discontinuous, $h = 140$ mm, bottom bars H8 @ 300 both ways, no top bars. Exactly 5 checks fail.
5. **Ribbed slab, worked example 3 (correct)**: see below. All 14 checks pass.
6. **Ribbed slab with mistakes**: 4" Maxpans, 100 mm ribs, C20/25, 2H8 bottom, no top bars, no fabric, cover 15 mm. Exactly 6 checks fail
   (cover, sagging, hogging, shear, deflection, fabric).

### Ribbed slab (client's notes LN11, Example 3)

The user picks the Maxpan size and enters the rib width $b_w$ and the topping $h_f$; the slab is then
$h = $ pan height $+ h_f$ deep with ribs at $s = b_w + 300$ mm centres. The span, supports and loads are entered
as for a one-way slab (continuous edges become continuous spans) and **one rib is analysed as a beam**.

| Maxpan | 4" | 5" | 6" | 7" | 8" | 9" | 12" |
|---|---|---|---|---|---|---|---|
| Mass (kg) | 6.80 | 7.50 | 8.50 | 9.80 | 11.0 | 12.3 | 16.5 |
| Height (mm) | 100 | 125 | 150 | 175 | 200 | 230 | 300 |

All pans are 300 × 300 mm, 8 per m². Loads per rib (kN/m): concrete $25\,(b_w\,h_{pan} + s\,h_f)$, Maxpans
$m \cdot 9.81\times10^{-3}/0.3$, finishes $g_k\,s$, imposed $q_k\,s$; $w = 1.35\,g + 1.5\,q$.

The rib is then checked like a beam: sagging as a T-section with $b_{eff} = b_w + 2\min(0.2b_1 + 0.1l_0, 0.2l_0, b_1)$,
hogging as a rectangle of width $b_w$, shear in the rib ($V_{Rd,c}$, links designed if they are entered), span/depth
with $F_1 = 1 - 0.1(b_{eff}/b_w - 1) \ge 0.8$, minimum and maximum steel, bar spacing in the rib, crack control,
and the fabric in the topping ($\ge 0.13\%$ of $1000\,h_f$). Fire uses the beam table for the rib and the slab
table for the topping.

Example 3 (200 mm slab: 6" pans, $b_w = 150$, $h_f = 50$, three 4.5 m spans, C25/30, $g_k = 1.2$, $q_k = 3.0$
kN/m², 2H10 top and bottom, A98) matches the notes: loads 1.943 + 1.35 kN/m per rib, $w = 4.65$ kN/m,
$b_{eff} = 450$ mm, $V_{Ed} = 12.55$ kN against $V_{Rd,c} = 15.2$ kN. The moments differ a little from the notes because
the app uses a pattern-loaded elastic analysis ($M^+ = 8.37$, $M^- = 9.41$ kNm) where the notes use coefficients with
20 % redistribution ($M = 0.086FL = 8.1$ kNm). The app's $F_1$ follows the guide's formula (0.8) where the notes take 0.85.

## Pad foundation (Chapter 6)

A rectangular pad $L \times B \times h$ under a rectangular column $c_x \times c_y$ at its centre. The inputs are the
characteristic column loads $G_k$, $Q_k$ and moments $M_{Gk}$, $M_{Qk}$ (at the underside of the base, along $L$), the
soil over the base, and the ground: a soil type from Table 5 (presumed allowable bearing values from BS 8004, which
fills in a value) or the allowable pressure from the site investigation.

| Group | Check |
|---|---|
| Durability & cover | $c_{nom} \ge \max(c_{min,dur} + \Delta c_{dev},\ \phi + \Delta c_{dev})$ and $\ge 40$ mm on blinding or 75 mm against the soil |
| Bearing | Characteristic $P = G_k + Q_k +$ base + soil; $e = M/P$; $p_{max} = P/A\,(1 + 6e/L)$, or $2P/[3B(L/2 - e)]$ when $e > L/6$ (warning: part of the base lifts off), against the allowable value |
| Overturning (EQU) | $1.1M_{Gk} + 1.5M_{Qk} \le 0.9\,(G_k + \text{base} + \text{soil})\,L/2$ |
| Bending | $N_{Ed} = 1.35G_k + 1.5Q_k$, $M_{Ed} = 1.35M_{Gk} + 1.5M_{Qk}$; net pressure on the cantilever at each column face; $K \le K'$ (no compression steel), $A_{s,req}$ against the bars both ways |
| Beam shear | At $d$ from each face: $v_{Ed} = V_{Ed}/(b\,d) \le v_{Rd,c}$ (Table 6) |
| Punching | Column face: $\beta (V_{Ed} - \Delta V_{Ed})/(u_0 d) \le v_{Rd,max} = 0.5\nu f_{cd}$ (Table 7). Control perimeters (rounded corners) from $0.5d$ to $2d$, the ground reaction inside each deducted, $\beta = 1 + k\,M_{Ed}u/(V_{Ed,red}W)$: $v_{Ed} \le v_{Rd,c}\cdot 2d/a$ at the critical one |
| Detailing | $A_{s,min}$ both ways, $A_{s,max} = 0.04A_c$, clear spacing, crack control ($w_{max} = 0.3$ mm, quasi-permanent stress) |

Checked by hand (tests/test_foundation.py): 400 × 400 column, 3.0 × 3.0 × 0.6 m base, $G_k = 1000$, $Q_k = 500$ kN:
bearing 1635 kN / 9 m² = 181.7 kPa; net design pressure 233.3 kPa, $M = 233.3 \times 3 \times 1.3^2/2 = 591.5$ kNm,
$A_{s,req} = 2642$ mm² ($d = 542$); beam shear 530.6 kN, $v_{Ed} = 0.326 \le v_{Rd,c} = 0.391$ MPa; punching at the face
2.41 ≤ 5.28 MPa.

Examples: **Pad foundation (correct)**: 400 × 400 column, 3.2 × 3.0 × 0.6 m base under 0.5 m of soil on stiff clay
(200 kPa), $G_k = 1000$, $Q_k = 500$ kN, $M_{Gk} = 20$, $M_{Qk} = 60$ kNm (wind), C30/37, H16 @ 150 both ways, cover 50
on blinding, XC2. All 17 checks pass. **With mistakes**: 300 × 300 column on a 2.6 × 2.6 × 0.45 m base on firm clay
(150 kPa), $M_{Qk} = 150$ kNm, C25/30, H12 @ 200, cast against the soil with 50 mm cover. Exactly 8 checks fail.

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
  flexure.py        bending, shear and span/depth for beams and slabs
  analysis.py       matrix stiffness beam analysis (the client's BeamViz Pro solver)
  column.py · beam.py · slab.py · ribbed.py · foundation.py   each element's procedure → report data
reports/            PDF reports (reportlab): pdf_base.py shared layout, one module per element;
                    beam_figures.py, slab_figures.py and foundation_figures.py draw figures for page and PDF
static/             HTML pages, JS, and fonts (IBM Plex for the pages, Liberation Serif for the PDF)
  css/base.css      theme tokens (light and dark) and shared components
  css/landing.css · form.css · run.css · report.css   one stylesheet per page
  js/form-kit.js    shared input-page helpers; js/report-<element>.js  each element's drawings
  js/beam-canvas.js the beam drawing canvas; js/canvas-editor.js on-canvas floating value editor
  js/beam-analysis-view.js shared analysis results builder for form and report
  js/figure-spec.js draws the analysis figures
tests/              pytest suite
```

## Limits

Rectangular columns; rectangular, T and L beams; solid one-way and two-way slabs; ribbed slabs on Maxpans;
rectangular pad foundations under one central column (moment along one axis, bearing by presumed values); normal-weight concrete up to C50/60; 50-year durability
covers with 20 mm aggregate. Fire is checked by the tabulated method. The beam and slab analysis is linear elastic
(no redistribution) with the gross section unless I is entered. The tool is for learning and preliminary
checking: a qualified structural engineer must verify the inputs and results.
