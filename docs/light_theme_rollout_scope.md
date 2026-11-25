# Scope: put the /coach2 look on the real site

Written for Mohit, to sign off before any code is written.
Date: 2026-11-25. Nothing in here is built yet.

---

## Status, 2026-11-25 evening

Step 1 is **half done and live**. Nothing changed for any user: the
default is still dark.

Shipped in `a69923d3`, deployed, and verified by rendering
`https://chessguru.ai/shell2` in both themes:

- The six CSS rules are fixed. The cause was not missing light styles —
  the dark values were written onto the *shared* `.experience-v1`
  selector instead of `.dark .experience-v1`, so they beat the correct
  light rules that already existed at `index.css:99` on source order.
  Moving them to `.dark` was the whole fix.
- The board surround is now a token, `--experience-board-frame`:
  walnut in light, unchanged `#141618` in dark.
- The scrim is now a token, `--cg-overlay`: 50% in light, 66% in dark.
  All **four** shared overlays use it — dialog, alert-dialog, sheet and
  drawer. All four previously said `bg-black/80`.
- `/shell2` is a new unlinked harness that renders the real `Layout`
  with a stub user. `Layout` takes `user` as a prop and guards every
  fetch, so it renders with no backend. That is how this was verified
  without a login.

Measured on the live page, not estimated: sidebar `#0d0e10` to cream,
mobile bar near-black to cream, board surround `rgb(21 23 25)` to
`rgb(111 74 47)`. Glyph contrast 5.07:1, 5.32:1, 17.51:1 and 5.86:1 —
all pass AA. Dark re-rendered and is unchanged.

**Still open:** the ~32 dark-assuming spots inside the product screens
(these need a login or your eyes), the rest of step 2, and step 3.

---

## The short version

The light theme already exists. It has existed for a while. The site
looks dark because the theme defaults to dark, not because the light
theme is missing.

So this is not a rebuild. It is a switch, plus a list of about forty
places that were written assuming dark and would look wrong the moment
the switch is thrown.

---

## What I checked, and where

Everything below is verified by reading the live code today.

**The light palette is already there.** `frontend/src/index.css:1085`
defines `.experience-v1` with `--background: 42 41% 96%`,
`--card: 42 48% 99%`, and the page painted `#f4efe4`. That is the same
cream the /coach2 preview uses. When I built /coach2 I copied these
values out of this very block.

**The site is dark because of one default.**
`frontend/src/context/ThemeContext.jsx:4`, `:13` and `:15` all default
to `"dark"`. The dark palette lives at `index.css:1130` under
`.dark .experience-v1`, and it only applies because that default puts a
`dark` class on the page.

**Anyone can already switch to light, today.** The toggle is a real
switch on the Settings page (`frontend/src/pages/Settings.jsx:408`) and
is also wired in `frontend/src/components/Layout.jsx:65`. So this is
not only a future plan. A user who flips that switch right now gets a
half-broken screen. That is a live bug, whatever we decide about the
default.

**The screens themselves are nearly all clean.** I counted the
hardcoded dark colours in the eleven files that the real routes
actually render:

| File | dark backgrounds | white text | raw colours |
|---|---|---|---|
| Layout.jsx | 0 | 0 | 0 |
| HomePageNew.jsx | 1 | 0 | 0 |
| Dashboard.jsx | 0 | 4 | 0 |
| CoachPlay.jsx | 2 | 0 | 0 |
| LabV2.jsx | 1 | 7 | 0 |
| PrescribedTraining.jsx | 0 | 0 | 2 |
| Reflect.jsx | 0 | 0 | 5 |
| UnifiedProgress.jsx | 0 | 0 | 0 |
| Settings.jsx | 0 | 0 | 0 |
| OpeningRepertoire.jsx | 0 | 0 | 10 |

That is about thirty-two places, and many already carry a `dark:`
variant, meaning they were written theme-aware and will be fine.

The scary numbers you would get from searching the whole folder — 209
dark backgrounds, 299 white texts, 474 raw colours — are real, but they
live mostly in the other 119 page files, and most of those are not
routed. We should not pay to fix screens nobody opens.

**The CSS is where the actual work is.** Six rules sit on the *light*
selector but hardcode dark values, so they stay dark when the theme
flips:

| Line | Rule | What it does |
|---|---|---|
| 635 | `.experience-board-stage` | board surround stays `#141618` |
| 1158 | `.experience-sidebar` | sidebar stays `#0d0e10`, text stays near-white |
| 1165 | `.experience-sidebar .text-foreground` | near-white text |
| 1173 | `.experience-sidebar …:hover` | white hover |
| 1190 | `.experience-coach-cta` | dark text on the accent |
| 1299 | `.experience-mobile-nav` | mobile bar stays near-black |

Fix those six and the shell goes light. That is the bulk of it.

---

## The thing you should push back on

The dark palette was not an accident. The comment above it at
`index.css:1120` says: *"Dark — the coaching room. Values from
docs/design/chessguru-pwc-dark-mockup.html, approved 2026-09-23."*
That file exists.

The comment does not say who approved it, and I have not verified that,
so I am not going to put a name to it. But a decision was taken, and
going light reverses it. You should say out loud that you mean to.

---

## What I propose to build

**Step 1 — make light mode correct.** Fix the six CSS rules and the
thirty-two screen spots. Nothing changes for anyone yet, because the
default is still dark. This step is worth doing on its own: it closes
the live bug where the Settings toggle produces a broken screen.

**Step 2 — carry over the /coach2 wins.** These are not about light or
dark, and each can ship on its own:

- the thick warm frame around the board, coordinates inside the frame
- player strips at full board width
- cards instead of pills for the decisions
- labels on every rail and bottom-bar icon
- dialogs: a 50% scrim instead of 80%, a 384px box instead of 512,
  and two equal buttons filling the row

The dialog change matters most. `CoachPlay.jsx:4055` and
`OpeningRepertoire.jsx:326` both hand-roll their own near-black
overlay, and the shared `components/ui/dialog.jsx` uses `bg-black/80`.
That is the single change that would be felt on every screen.

**Step 3 — flip the default.** One line in ThemeContext. Only after
steps 1 and 2 are seen and approved on real screens.

Keep the toggle either way. People who want the dark coaching room
should keep it.

---

## What I need from you before step 1

I cannot see the real screens. The app requires a login, my local copy
has no backend (`frontend/.env` has an empty `REACT_APP_BACKEND_URL`),
and when I tried to reuse the deploy gate's session token from the
server my own sandbox refused it as unauthorized access. That refusal
was right and I did not work around it.

So right now I would be changing forty things across ten screens
without ever seeing them. I am not willing to hand you that and call it
done.

Pick one:

1. Give me a login for a throwaway account I can drive headlessly.
2. Let me run the backend locally against a copy of the data.
3. I ship step 1 behind the toggle, and you look at the screens
   yourself and tell me what is wrong.

Option 3 works but makes you the QA, which we agreed I should stop
doing.

---

## Not in scope

- The 119 unrouted page files.
- The landing page, which has its own styling and is not part of the
  token system.
- The board itself. The squares and pieces do not change.
