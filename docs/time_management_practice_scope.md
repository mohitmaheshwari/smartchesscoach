# Time Management Practice — Scope

Signed off 2026-09-09 (Mohit, in conversation).

## 0. Why this exists

`/training/pattern/time_collapse` rendered an empty puzzle board: "No puzzles
for Calculate the Reply yet", "No puzzle available", "Nothing to solve here
right now" — while Progress simultaneously named time discipline the player's
number one focus. A focus was being promoted with nothing behind it.

Two things were wrong underneath:

- `focus_resolver.FOCUS_TO_GAP` maps `time_collapse` to `calculation_depth`, so
  a clock problem was silently reinterpreted as a calculation problem and
  served calculation puzzles titled "Calculate the Reply".
- An earlier fix (mine, v-series work on 2026-09-09) aliased `time_collapse` to
  `["tactical_miss", "hanging_piece"]` in `coaching_puzzle_service` so that
  *something* would load. Wrong shape: hanging-piece puzzles do not train
  clock use. That alias is removed here.

## 1. What the evidence says

Measured on `user_8b599930d7ef`, read-only over stored PGN clock stamps
(`[%clk]`, present in 14,298 of 15,274 games):

| fact | value |
|---|---|
| games lost on the clock | **144 of 783 (18%)** |
| clock burned by move 10 (timeout losses) | 20.3% |
| clock burned by move 20 (timeout losses) | 45.8% |
| average longest single think | 103s |
| worst single think | 362s |
| **thinks ≥ 60s per game** | **1.2** |
| longest think lands in moves 1-10 | 26% |
| longest think lands in moves 11-20 | 47% |

The detection was correct all along; losing on time is this player's single
most repeated way of losing. The 1.2 figure is the design input: the player is
not slow, they play at a normal pace and then one or two decisions per game
balloon. Practice has to change one moment, not a whole game.

## 2. What we are training

A **stopping rule** — knowing when thinking has stopped paying — not
calculation.

This is why a timer bolted onto the existing puzzle page would fail. A normal
puzzle asks for the best move and implicitly rewards taking as long as needed,
which trains the exact habit that loses these games. A time exercise inverts
the success criterion:

| | normal puzzle | time exercise |
|---|---|---|
| goal | the best move | a **sound** move |
| 95s and perfect | pass | **fail** |
| 18s and good enough | worse | **pass** |

## 3. In scope (V1 — the mirror)

V1 ships the diagnostic, because it is true today, needs no authored content,
and every later slice is built from the same numbers.

- `services/time_management_service.py` computes a time profile for a user from
  stored PGNs: timeout-loss count and rate, clock burned by move 10 and 20,
  longest-think average and worst, thinks ≥60s per game, where the longest
  think lands, and the specific burn moments (game, move number, seconds).
- `GET /api/training/time-profile` serves it for the current user.
- `/training/pattern/time_collapse` renders the profile instead of an empty
  puzzle board. No board, no fabricated puzzle.
- Remove the `time_collapse` puzzle alias.
- Stop `time_collapse` resolving to the `calculation_depth` lesson label, so
  the page can never again say "Let's Practise Calculate The Reply" about the
  clock.
- Everything shown is derived from the player's own clocks. No estimates, no
  invented thresholds.

## 4. Explicitly out of scope (V1)

- The prescribed rule and its verification (V2, below).
- The timed drill on burn positions (V3, below).
- Changing how any other focus selects or renders.
- Any claim that coaching has improved the player's clock use. V1 measures;
  it does not assert improvement.
- Splitting the opening-unfamiliarity cases (see open question).

## 5. Later slices

- **V2 — one rule, verified.** Prescribe a single measurable budget for the
  next game (e.g. "no single move over 90 seconds before move 25") and check
  compliance from that game's own clock stamps. This is the product's existing
  prescribe → watch a real game → confirm loop, and it is the only focus where
  verification needs no engine judgement at all: the clock has no opinions.
- **V3 — timed drill on real burn positions.** The move that burned the clock
  is known for every one of these games, so the positions are already the
  curriculum. Show the position, give a budget, accept any sound move, and
  count slow-but-correct as a failure.

## 6. Success criteria

- A player whose clock is fine never sees this surface.
- Every number shown is reproducible from that player's stored PGN clocks.
- The page never renders a board or a puzzle prompt for a clock focus.
- `time_collapse` never renders a calculation lesson label again.
- V2 can measure whether V1+V2 changed behaviour using three objective
  numbers: clock at move 20, thinks ≥60s per game, timeout rate.

## 7. Open question (V1 does not answer it)

26% of longest thinks land in moves 1-10. Thinking hard on move 8 usually
means the position is unfamiliar, which is an opening-knowledge problem wearing
a clock costume — and there is already an opening curriculum for that. Treating
it with a stopping-rule drill would be treating the symptom. Splitting the two
causes needs a check of whether those early thinks happen in positions still
inside the player's own repertoire, and is deliberately left to V2.
