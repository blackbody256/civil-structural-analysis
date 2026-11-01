# RC Studio: Edwin's look for the EC2 checker (branch `Edwin`)

Same engine, API, inputs, checks, examples and reports as `main`; a different product to look at and move
around in. This branch is never merged into `main`; `main` is merged into it when it gains features.

## Idea

A site-office instrument. Reinforced concrete lives among cement grey, graphite steel and the yellow tags on
every rebar bundle, so the product takes those three: grey working surfaces, a graphite tool frame that stays
put, and tag yellow as the one signal colour, kept for the thing to press next or the thing that matters most
(the primary action, the current step, the governing utilisation). Everything else is quiet.

## Colour

| Token | Light | Dark | Use |
|---|---|---|---|
| graphite (`--chrome`) | `#1d2125` | `#101316` | sidebar, phone top bar, PDF header band |
| cement (`--bg`) | `#e7e8e4` | `#16191c` | page |
| slab (`--surface`) | `#f7f7f4` | `#1f2327` | cards, panels |
| tag yellow (`--signal`) | `#f2b705` | `#f5c130` | primary buttons (graphite text), current step, gauge, active nav |
| ochre ink (`--accent`) | `#7d5a00` | `#f5c130` | links and accent text/strokes that must be readable |
| ink (`--text`) | `#1d2125` | `#eceeeb` | text |

Status colours stay green / red / amber-orange / blue / grey, each AA on its own soft background, and the
amber is pushed towards orange so a warning is never mistaken for the yellow signal. Drawings keep loads red,
shear blue and moments green; their ink and concrete follow the page.

## Type

- Headings, the brand and large numbers: **DejaVu Sans Condensed Bold** (local), a narrow grotesque that reads
  like stencilled site labels. Only for display sizes.
- Everything else: **IBM Plex Sans** 400/500/600. Numbers in inputs and results: **IBM Plex Mono**.
- Scale (major third from 15 px): 13 · 15 · 18.75 · 23.4 · 29.3 · 36.6.

## Layout

```
┌──────────────┬──────────────────────────────────────────────┐
│ ▣ RC Studio  │  Column                                       │
│              │  Rectangular columns to Eurocode 2            │
│  Overview    │  (1)───────(2)───────(3)  Analysis Design Report│
│ ▌Column    5 │  ┌ card ───────────────────┐ ┌ preview ─┐     │
│  Beam      4 │  │ Materials        C32/40 ⌄│ │ section   │     │
│  Slab      3 │  └─────────────────────────┘ │ elevation │     │
│  Pad found. 6│  ┌ card ───────────────────┐ └──────────┘     │
│  Planned     │  ...                                          │
│   Wall       │  ┌ graphite action strip ──────[Run checks]┐  │
│ Guide (PDF)  │                                               │
│ Theme ⌄      │                                               │
└──────────────┴──────────────────────────────────────────────┘
```

- Sidebar 248 px, graphite in both themes, element list with the guide chapter, planned elements greyed,
  guide link and theme switch at the foot. At 720 px and below it becomes a graphite top bar with a Menu button
  that opens the list as a drawer.
- Element pages: Analysis → Design → Report as a stepper (done / current / locked), same tab logic underneath.
- Form sections stay collapsible (their one-line summaries are useful when closed) but read as cards.
- The action bar is a graphite strip that sticks to the bottom of the form.
- Results: the governing utilisation as a ring gauge, counts as chips, checks as rows with a status pill.
- Home: what the product does in one sentence beside the live beam analysis, then one tile per element
  (its worked-example drawing, chapter, number of checks, Start), then the planned elements.
- PDF: same content and fonts; graphite header band with a yellow rule, ochre headings, "RC Studio" name.

## Rules kept from main

No reference to the guide in reports; positive shear and hogging above the axis; G × 1.35, Q × 1.5; every
input `name` path, id used by scripts, check and example unchanged; offline (no CDN), local fonts only.
