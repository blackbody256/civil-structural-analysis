# Structural Analysis & Design: Elisha's look for the EC2 checker (branch `Elisha`)

Same engine, API, input paths and checks as `main`, with a completely different interface and its own worked
examples. Alex (`main`) and Elisha are in the same class, so nothing should look shared. This branch is never merged
into `main`; `main` is merged into it when it gains features.

## Where the look comes from

Elisha's own earlier work: the "2D Structural Analysis Suite" (MATLAB App Designer, `Structural_Analysis_and_Design`).
It is a desktop app: module tabs across the top (TRUSSES, BEAMS, FRAMES, RESULTS), a grey window (#E6E6E6) with
white panels, a graph-paper drawing area beside tabbed data tables (Nodes, Members, Supports, Loads), a row of tool
buttons (Node, Member, Support, Load, Run Analysis, Clear All) and a results tab with diagram switches. This web
version keeps that vocabulary.

## Structure (how it differs from main)

| | main (Alex) | Elisha |
|---|---|---|
| Navigation | slim top bar with breadcrumbs | title bar + uppercase module tabs (HOME, COLUMN, BEAM, SLAB, PAD FOUNDATION) |
| Actions | sticky bar at the bottom of the form | toolbar at the top of the workspace |
| Workflow | underlined tabs | boxed MATLAB tab group: ANALYSIS, DESIGN, REPORT joined to their page |
| Inputs | a long stack of collapsible sections | the sections of a step become a tab strip, one section shown at a time |
| Drawings | right-hand column | left-hand graph-paper panel |
| Results | list of rows | gauge plus a numbered results table |
| Examples | Alex's | Elisha's own, for every element |

## Elisha's worked examples

| Element | Correct example | Example with mistakes |
|---|---|---|
| Column, frame | two-bay workshop frame, interior column C2 400 × 400, C35/45, 8H20: 14 pass | pinned-base portal, C1 230 × 230, 4H10, cover 15: 5 fail |
| Column, direct | 450 × 300, C40/50, 6H25, NEd 2600 kN: 17 pass | 300 × 300, C28/35, 4H16, NEd 2400 kN: 5 fail |
| Beam | two 7.5 m spans, 350 × 650, C32/40, G + Q and a point load: 17 pass | 300 × 500, C25/30, 3H20: 6 fail |
| One-way slab | two 5.2 m spans, h 200, C32/40: 16 pass | h 140, C25/30, no top bars: 7 fail |
| Two-way slab | 4.8 × 6.0 m corner panel, h 190: 16 pass | h 130, H8 @ 300, no top bars: 7 fail |
| Ribbed slab | 7" Maxpans, 125 mm ribs, two 5.0 m spans: 14 pass | 5" Maxpans, 100 mm ribs, C20/25, cover 15: 5 fail |
| Pad foundation | 450 × 450 column, 3.4 × 3.4 × 0.7 m on compact sand: 17 pass | 3.0 × 3.0 × 0.65 m, H16 @ 200, cast on soil: 7 fail |

The home page drawings show these examples too.

## Colour and type

- Window `#e6e6e6`, panels `#ffffff`, borders `#c4c4c4`, text `#1f1f1f`; MATLAB blue `#0072bd` for selection and
  the primary action, MATLAB orange `#d95319` only for the active module tab's marker. Dark mode: window `#1e1e1e`,
  panels `#2a2a2a`, blue `#4ea1e3`.
- Status: pass `#2e7d32`, fail `#c62828`, warning `#e65100`, information `#1565c0`, not applicable `#6b6b6b`
  (lighter tones in dark mode), all AA on their backgrounds. Drawings keep loads red, shear blue, moments green.
- Text in the system UI sans (Segoe UI, Helvetica, Arial), numbers in DejaVu Sans Mono (local). Square corners
  (2 px), 1 px borders, no shadows except menus.

## Rules kept from main

No reference to the guide in reports; positive shear and hogging above the axis; G × 1.35, Q × 1.5; every input
`name` path, every id used by scripts and every check unchanged; offline (no CDN), local fonts or system stacks only.
