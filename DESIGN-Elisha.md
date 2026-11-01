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
