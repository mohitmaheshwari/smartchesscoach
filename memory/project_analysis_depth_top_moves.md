---
name: analysis-depth-top-move-rankflips
description: STOCKFISH_DEPTH=18 in the analysis pipeline occasionally rank-flips between near-equal top moves vs deeper search. V5 records the d18 best_move_san; captions like "X was better" can name a move that isn't strictly Stockfish #1 at d22+. Not factually wrong (X is still better than what was played) but imprecise. Future improvement: detect near-equal multipv at analysis time and hedge the caption.
metadata:
  type: project
---

Surfaced 2026-05-17 while triaging Parth fb_0edf478fc60e. Parth flagged
"Qf3 loses about 1 pawn. Nxf2 was better" claiming "Qf3 is best." The
analysis pipeline at d18 stored `best_move_san: "Nxf2"`. Stockfish d22
re-check showed `Ne3 #1 (+566), Nxf2 #2 (+559), Qf3 #4-ish (+482)` —
both Nxf2 and Ne3 are real "better than Qf3" moves; the d18 pipeline
just picked the #2 instead of the #1 at depth.

## Where the depth lives

`backend/config.py:33` — `STOCKFISH_DEPTH = 18`. Used by
`analysis_worker.py:1045` and propagated to every per-move analysis
in the V5 pipeline.

## Why it matters

- Captions naming a specific "better move" rely on `best_move_san`. When
  d18 picks a move that's #2 at d22+, the caption names a real
  improvement but not the strictly-best one.
- For positions with near-equal top moves (<= 50cp apart), the rank
  order is depth-sensitive.
- Parth at 1800 noticed because he confirms with deeper analysis at
  home before flagging.

## Why not just raise STOCKFISH_DEPTH

Raising to d22 multiplies analysis time per move ~4-10×. For a 60-move
game, that's the difference between ~1 min and ~10 min of background
work. The lazy-regen mechanic compounds this on V5 version bumps.

## Future improvement (not implemented yet)

At analysis time, run `multipv=3` and capture the eval gap between
#1 and #2. If gap <= 50cp:
- Mark `best_moves_near_equal: True` in the analysis record.
- Caption renderer hedges: "a different move was better" or
  "Ne3 / Nxf2 were both better than Qf3" instead of specifically
  naming one.

This is cheap (~1.5× analysis time, not 10×) and addresses the
underlying issue: at the d18 contract, sometimes you can't tell which
of 2-3 near-equal moves is THE best.

## Related

- `[[no-yes-man]]` — verify against FEN; in this case Parth's framing
  ("Qf3 is best") didn't hold up even at d22, but his concern about the
  caption's specificity was valid.
- `[[feedback-chess-content-verification]]` — audit at the rendered
  string layer. The string "Nxf2 was better" is true; "Nxf2 is THE
  best" would be wrong at d22+.
