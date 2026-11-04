# Structural Analysis & Design: Elisha's version of the EC2 checker (branch `Elisha`)

Same engine (`ec2/`), API, input paths and checks as `main`, with a different way of entering the inputs, a 3D
model of every element, a different report and its own worked examples. Alex (`main`) and Elisha are in the same
class, so nothing should look shared. This branch is never merged into `main`; `main` is merged into it when it
gains features.

## Where the look comes from

Elisha's earlier "2D Structural Analysis Suite" (MATLAB App Designer): module tabs across the top, a grey window
with white panels, MATLAB blue and orange. The CAD viewport and the calculation pad come from engineering practice:
a dark 3D view as in analysis software, and the ruled Ref | Calculation | Output sheet engineers write calculations on.

## How it differs from main

| | main (Alex) | Elisha |
|---|---|---|
| Navigation | slim top bar with breadcrumbs | title bar + uppercase module tabs (HOME, COLUMN, BEAM, SLAB, PAD FOUNDATION) |
| Entering inputs | one long page of collapsible sections in Analysis / Design / Report tabs | a guided wizard: one step at a time, a rail of numbered steps down the side (with each step's summary), Back / Next, Enter moves on, a review of everything entered before the checks run, then the results and the report as the last steps |
| Element view | 2D section and elevation beside the form | a live 3D model (WebGL, written for this app, no library) on top, the 2D drawings under it as tabs |
| 3D model | none | builds itself with an animation, sways, turns and zooms; x-ray shows the cage; each step lights up the parts it is about (bars and links on Reinforcement, loads on Loads); the frame for the column page's analysis steps, then the column |
| Run page (pad) | the section drawing | the pad in 3D, parts turning red as their checks fail |
| Web report | summary first, collapsible groups, Times New Roman | a calculation pad in DejaVu Sans: boxed title block, sections A Design data (input schedule beside the 3D model, failed parts red), B Drawings and analysis, C Design checks in Ref / Calculation / Output columns with guide references and PASS / FAIL stamps, D Conclusion (verdict stamp, governing check, every utilisation), E Assumptions; sections slide in, bars fill, the stamp lands |
| PDF | Times New Roman 12 pt, blue band header, "Page n of N" | DejaVu Sans; a boxed title block on every sheet (project, element, sheet n of N, made by, date); check sheets ruled into Ref / Calculation / Output columns; a 3D view of the element on the first sheet; the conclusion with a verdict stamp and a utilisation chart at the end; the foot carries the element, the result and the print time |
| Home | element cards with drawings | each element's example turning in 3D |
| Examples | Alex's | Elisha's own, for every element |

## Elisha's worked examples

| Element | Correct example | Example with mistakes |
|---|---|---|
| Column, frame | two-bay workshop frame, interior column C2 400 × 400, C35/45, 8H20: 14 pass | pinned-base portal, C1 230 × 230, 4H10, cover 15: 5 fail |
| Column, direct | 450 × 300, C40/50, 6H25, NEd 2600 kN: 17 pass | 300 × 300, C28/35, 4H16, NEd 2400 kN: 5 fail |
| Beam | two 7.5 m spans, 350 × 650, C32/40, G + Q and a point load: 17 pass | 300 × 500, C25/30, 3H20: 6 fail |
| One-way slab | two 5.2 m spans, h 200, C32/40: 16 pass | h 140, C25/30, no top bars: 7 fail |
| Two-way slab | 4.8 × 6.0 m corner panel, h 190: 16 pass | h 130, H8 @ 300, no top bars: 7 fail |
| Ribbed slab | 7" Maxpans, 125 mm ribs, two 5.0 m spans: 14 pass | 5" Maxpans, 100 mm ribs, C20/25, cover 15: 4 fail |
| Pad foundation | 450 × 450 column, 3.4 × 3.4 × 0.7 m on compact sand: 17 pass | 3.0 × 3.0 × 0.65 m, H16 @ 200, cast on soil: 7 fail |

## Code

- `static/js/wizard.js`: the steps. A step is a `<section class="wz-step">` in the page (title, prompt, the parts
  to focus on, and for the Analyse and Review steps the button its Next presses). Moving to a step in another
  panel presses that panel's tab, so the page's own Analysis / Design / Report logic still decides what is open.
- `static/js/viewer3d.js`: the WebGL viewport. `static/js/models3d.js`: the column, frame, beam, slab (one-way,
  two-way, ribbed) and pad models, built from the same inputs the form sends. `static/js/model-view.js` ties
  them to a page.
- `static/js/report.js`, `static/css/report.css`: the web report. `reports/pdf_base.py`: the PDF sheets;
  `reports/iso3d.py`: the PDF's 3D view.

## Colour and type

- Window `#e6e6e6`, panels `#ffffff`, MATLAB blue `#0072bd`, orange `#d95319` for the current step and the pad's
  margin rule. The 3D viewport is dark in both themes: concrete grey, bars orange, links yellow, loads red,
  supports green, ground pressure light blue, failed parts red.
- Reports: navy `#0b3a5c` title block and headings, blue pad ruling, stamps in pass green, fail red, warning orange.
- UI text in the system sans, numbers in DejaVu Sans Mono, reports in DejaVu Sans (all local).

## Rules kept from main

The engine, every input `name` path, every id used by scripts and every check are unchanged: main's and Elisha's
examples give byte-identical `/api/<element>/check` responses on both branches. Positive shear and hogging above
the axis; G × 1.35, Q × 1.5; offline (no CDN), local fonts or system stacks only.
