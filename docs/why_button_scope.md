# Scope: The "Why" button, and the both-sides mistake list

Status: DRAFT — needs Mohit's sign-off before any code.
Written 2026-09-25. Measurements in here are from real runs, cited by file.

---

## Why we are doing this

Today a caption has to produce a sentence for every mistake, instantly,
while the page renders. When the system cannot work out why a move was
bad, it still has to say something — so it says something it does not
know. That is where the bad captions come from. It is not a wording
problem and no amount of rewriting `R12_blunder.json` fixes it.

Mohit's idea changes the constraint: **the why sits behind a button.**
A button is allowed to take a few seconds. That buys us the time to do
the thing we could never afford during a page render — ask the engine
for several candidate moves, play each line out, and keep whichever one
we can actually explain from the board.

So the new rule is:

> We no longer pick the best move and then struggle to explain it.
> We look at the good moves and pick the one that explains itself.

---

## Part 1 — The "Why" button

### What the player sees

On a mistake card there is a button. They press it. It says something
like "Coach is working it out…" for a few seconds. Then one of two
things appears:

**(a) We found a reason.** A short, plain sentence saying what the move
allowed or missed, plus arrows on the board showing it.

**(b) We did not find a reason.** We say so. "We can't show a clear
reason here." Underneath we still show the plain board facts we are
sure of. **We never invent a sentence to fill the gap.** This happens
about 10% of the time and that is an accepted outcome, not a bug.

### What happens when they press it

1. Take the position before their move.
2. Ask Stockfish for its **top 8 moves**, at **depth 18**, single-threaded.
3. For each one, play the line out and ask the existing
   `punishment_resolver` whether it can name a concrete consequence —
   material won, a fork, a piece trapped, a forced retreat, a promotion,
   mate.
4. Walk the 8 in order, best first, and take **the first one that
   explains itself** — as long as it is within **50 centipawns** of the
   engine's top move.
5. If none of the 8 qualifies, return nothing and show outcome (b).

### Why these exact settings

All measured on the same 40 positions, on the server, single-threaded
(multi-threaded Stockfish returns a different line each run, so it is
useless for anything we need to reproduce).

| | depth 18, top 4 | depth 18, top 8 | depth 20, top 8 |
|---|---|---|---|
| typical wait | 2.9s | **5.5s** | 13.7s |
| slow case (p90) | 5.4s | **10.9s** | 22.6s |
| worst seen | 6.3s | **14.2s** | 37.2s |
| nothing explainable | 18% | **10%** | 7% |

Raw output: `clickcost18b.txt` (top 8), `m4.txt` (top 4),
`clickcost.txt` (depth 20).

**Top 8 at depth 18 is the choice.** Top 4 is twice as fast but the
"we can't explain this" rate doubles, from 10% to 18% — and that bucket
is exactly the one that produces bad captions today. Depth 20 only
buys 3 more points and costs 13.7 seconds, which is too long to sit
behind a button.

I should flag my own error here: I first recommended top 4, reasoning
from where the explainable moves ranked inside the top-8 run. Actually
running top 4 gave a worse result than that predicted (82% vs 94%),
because the engine searches differently when asked for fewer lines.
The table above is measured, not extrapolated.

### The 50-centipawn rule

We only recommend a move that is nearly as good as the engine's best.
If the only move we can explain is much worse, we stay quiet. We are
not going to teach someone an inaccuracy because it made a tidier
story. In practice this costs us almost nothing — the engine's top
move is itself explainable 25 of 36 times, and 31 of 36 land within
50cp.

### What this does NOT change

- Nothing about the captions that render on page load.
- No existing caption rule, variant file or detector is touched.
- The button is additive. If it returns nothing, the card looks
  exactly as it does today.

---

## Part 2 — Mistakes and blunders, both sides

### What the player sees

A section on the game review page listing every mistake and blunder in
the game, **theirs and their opponent's**, in move order. Each row: move
number, the move, how bad it was, and one short line on what it was.
Their own mistakes and the opponent's are visually distinct — the
opponent's are chances they had and did not take.

### Why it is nearly free

`services/game_summary_service.py` already computes this. `GameSummary`
already has `key_mistakes` (theirs) and `opportunities` (the opponent's),
plus the totals. The work is not building it. The work is:

1. It is stored on only **133 of 16,978** games — needs a backfill.
2. `get_display_summary()` has **zero callers** — needs an endpoint.
3. The review page does not read it — needs rendering.

One change to the existing logic: it currently keeps only the "1-3 most
important" mistakes. For this section we want all of them.

---

## How we will know it worked

- The button returns a real reason on ~90% of mistake positions.
- Every reason it gives can be replayed and checked against the board —
  no claim is trusted because of how it reads.
- On the ~10% where it finds nothing, it says nothing. If a manufactured
  sentence ever appears there, the feature has failed.

## Open question for Mohit

The 5.5-second typical wait. Acceptable behind a button with a "Coach
is working it out…" state, or too long?
