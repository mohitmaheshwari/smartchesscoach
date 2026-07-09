# Coach Geometry Arrows — Scope

**Status:** draft for Mohit signoff · 2026-07-10
**Goal in one line:** show the player a **living map of the plans on the board — theirs and the coach's — as persistent arrows and zones**, so a 600–1500 player learns to think in *plans*, not just moves.

---

## Why this, why now

At 600–1500 the missing skill isn't calculation — it's **seeing**. A stronger player looks at a
position and sees *lines of force*: this file is mine to seize, this diagonal is loaded, this pawn
is weak, this square is a hole, this break opens the position. A 1200 sees pieces, not plans.

Captions teach *after* a mistake. This teaches *during* the game — the geometry that is *always*
there. And it pairs with the new 1500-floor coach: when you're playing someone stronger, "here's
your plan, here's mine" is exactly the coaching that turns a loss into a lesson.

Mohit (2026-07-10): "I want to see both my plans and your plans." "Arrows don't disappear — they
stay until the geometry changes, so the player sees everything together." Not just king/queen
tactics — **attack, defend, control, break, target — the whole strategic conversation.**

---

## What the player SEES (the experience, before any code)

A live overlay on the Play-with-Coach board. At a glance:

```
   Default view (distilled — the two competing plans)
   ┌─────────────────────────────┐
   │  . . . . . k . .            │   GREEN  = your plan
   │  . . . . . p p p            │   AMBER  = coach's plan
   │  . . . . . . . .            │
   │  . . ▓ . . . . .   ← green zone: hole on c5 (your knight belongs here)
   │  . .═╪══════════▶  ← green arrow: your rook seizes the open c-file
   │  . . . P . . . .            │
   │  ◀╌╌╌╌╌╌╌ . . . .  ← amber dashed: coach's bishop eyes your king down the long diagonal
   │  . R . . . K . .            │
   └─────────────────────────────┘
   caption strip:  "Your plan: take the c-file and land a knight on c5.
                    My plan: pressure your king on the long diagonal — watch that bishop."
```

- **Solid arrow** = a real, live pattern (a pin that holds, a rook actually controlling an open
  file, a fork on the board).
- **Dashed arrow** = a *latent* line — your rook and my king share a file but pieces sit between
  ("a line to watch," not a claim it's a pin *yet*). This is your rook→king-through-pieces case.
- **Highlighted square / zone** = a target or a hole (weak pawn to attack, outpost square to take).
- **Green = your plan, Amber = the coach's plan.** Always both sides.

Then a **"Show more" control** (slider or toggle) that layers in the fuller picture on demand — up
to *everything* (all active control lines, both sides) for when the player wants to study the whole
geometry. Off by default.

---

## The plan taxonomy (what can be drawn, both sides)

Each is detectable from the board (deterministic) and carries its own arrow/zone + one plain line.

| Plan | Visual | Example line |
|---|---|---|
| **Control** (file / rank / diagonal a long-range piece owns or can seize) | arrow along the line | "The c-file is open — your rook belongs there." |
| **Attack** (pieces converging on a target — king zone or a piece) | arrows to the target | "Two pieces already eye f7." |
| **Defend** (a piece holding a weakness / king shelter) | arrow piece→defended | "This knight is the only thing guarding your king." |
| **Break** (a pawn push that opens lines) | arrow of the pawn push | "Play …c5 to break open the centre." |
| **Target** (a weak/undefended pawn or piece) | highlighted square | "Their d6 pawn is weak and can't be defended again." |
| **Weak square / hole** (square no enemy pawn can cover) | highlighted square | "c5 is a hole — a knight there is untouchable." |
| **Pin / skewer / fork / battery / x-ray** (tactical geometry) | arrow along the line | "Your bishop pins their knight to the king." |

Latent vs live: **live** patterns (real pin, real fork, actual control) = solid; **latent** ones
(the line exists but is blocked / not yet a pin) = dashed. Verified either way (see Truth below).

---

## The anti-noise design (this is the whole ballgame)

Persistence *amplifies* clutter — a middlegame has 20+ active lines. "Everything, always" =
unreadable. The fix is **distill by default, expand on demand.**

- **Tier 1 — default, always on (cap ~3–4 total):** only the **dominant plan for each side**,
  chosen by a significance rank. Your main idea (1–2 arrows/zones) + the coach's main idea (1–2).
- **Tier 2 — "Show more" (opt-in, layered):** secondary plans → then all active control lines →
  full overlay. The player dials it up when studying.

**Significance gate** — what earns a Tier-1 slot (ranked, keep the top few):
king-facing (attack or defence) > a real live pin/fork > an open/half-open file a rook can take >
a weak target that can't be re-defended > a pawn break that opens lines > a hole worth occupying.
A coincidental alignment with nothing behind it earns *nothing*.

---

## Persist-until-changed lifecycle

Each drawn plan is a small state object, recomputed every move:

- **Appears** when its geometry becomes active (line opens, piece lands on the file, pin forms).
- **Persists** unchanged across moves while its geometry holds — the board feels stable.
- **Only diffs animate** — a new plan fades in, a broken one fades out; unchanged ones don't
  redraw. (No flicker every move.)
- **Clears** when the geometry breaks: the piece leaves the line, the line closes, the pin
  resolves, the target gets defended or traded, the break is played.

---

## Truth & never-mislead (same rule as captions)

An arrow is a claim; a wrong one is a *visual* hallucination.

- **Real pin** → verified with `board.is_pinned` before a solid "pin" arrow renders.
- **Fork / control / attack** → verified from the board (piece really attacks both targets; file
  really open; piece really bears on the square).
- **Latent line** (rook→king through pieces) → drawn **dashed** and worded as "a line to watch,"
  never "pinned."
- **Plans** (control / break / target) are *ideas*, framed as such ("the idea here is…") and
  grounded in a **fact** (this file *is* open, this pawn *is* undefended) — no ungrounded strategy.
- **Deterministic first.** Geometric plans need no engine. The deeper, long-horizon maneuvers lean
  on the engine PV, are shown sparingly, and abstain when not clear.

---

## Where it lives + what already exists

- **Surface:** Play-with-Coach board first (live planning); game review second (learn the pattern).
- **Already built (≈70%):** the board renders arrows (`CoachPlayBoard` takes `coachArrows`;
  `CoachPlay.jsx` has the state; there's an **"Arrows + ideas"** toggle in setup). The geometry is
  computed — `shape_detectors.py` emits every pattern as `mover` + `targets` (exactly the arrow
  endpoints), with ray-walkers, `is_pinned`, fork detection. Same detectors power "Pattern of the day."
- **New work:** the plan taxonomy detectors (control/break/target/hole/defend on top of the tactical
  ones), the **significance ranking**, the **persist/clear lifecycle** (state across moves), the
  **two-tier + Show-more UI**, and the your-green/their-amber + solid/dashed rendering.

---

## Rollout

Behind a default-off flag (`PWC_GEOMETRY_ARROWS`), per house style:
1. **Phase 1** — Tier-1 only, geometric plans (control / pin / fork / open-file / target / break),
   both sides, persist lifecycle, verified. Ship to Mohit's own PWC first.
2. **Phase 2** — the "Show more" layers + secondary plans.
3. **Phase 3** — engine-assisted deeper maneuvers (sparingly, framed as ideas).
4. Flip the flag once the acceptance bar clears.

---

## Acceptance bar (how we know it's good, not vibes)

- **Readable:** default view never shows more than ~4 marks; both sides always represented.
- **Truthful:** on a sample of live positions, **0 false "pin"/"fork" claims** (verifier passes);
  latent lines all dashed.
- **Both plans present:** each side gets at least its top plan when one exists.
- **Stable:** unchanged geometry does not re-animate move to move.
- **Teaches:** Mohit reads a handful of positions and can answer "what's my plan / what's theirs"
  from the overlay alone.

---

## Out of scope (this pass)
- Full engine "best plan" search per move (Phase 3, limited).
- Opening-book plan libraries (separate).
- Purely positional judgments with no board-grounded fact behind them (abstain).

---

## Companion quick-win (separate, smaller): the teaching-framing voice
Not part of this feature, but requested alongside it and cheap: the coach opens each PWC session
with a line like *"I'm not here to beat you — I'm here to help you see the board. Let's learn."*
and reinforces it after a loss / a good save (*"the result doesn't matter — the pattern you just
saw does"*). Ship this independently; it pairs with the 1500-floor coach and the arrows.
