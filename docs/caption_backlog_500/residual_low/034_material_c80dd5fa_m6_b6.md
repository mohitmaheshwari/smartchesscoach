# c80dd5fa-c98 m6 b6 — residual LOW #34

**Variant:** `why_user_missed_material`
**Position (FEN):** `r2qkb1r/pp2pppp/2n2n2/2pp4/2PP2b1/1Q2PN2/PP1N1PPP/R1B1KB1R b KQkq - 2 6`
**Move played:** `b6` (cp_loss `203`)
**Engine's best (stored):** `Na5`
**User color:** black

## Caption as shipped

> b6 is a mistake. Na5 was better. Na5 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `-18cp`  PV: `Na5 Qc3 cxd4 exd4 Bxf3 Nxf3`
  #2 eval(W) `+6cp`  PV: `e6 cxd5 exd5 Ne5 Bc8 Bb5`
  #3 eval(W) `+59cp`  PV: `cxd4 cxd5 Nxd5 Nxd4 Nxd4 exd4`

## Diagnosis

Engine PV shows a material gain in the resulting line, but the eval guard rejected the specific piece_capture claim (eval not +400cp after best move from user POV). Detector downgraded to the generic 'wins material' fallback.

This is **not a bug** — the v51 asymmetric threshold + v55 winning/losing
flags correctly suppress the variants in winning/losing positions. They
fire only in balanced positions where:
- cp_loss 100-249 (mistake tier)
- No tactical detector (mate / piece_capture / clearance / king_pawn / hanging / capture / check)
- No positional detector (curriculum_deviation / blocked_pawn / board_state)
- User is neither decisively winning nor losing

Most-likely paths to address (in order of effort):

1. **Accept as floor.** 79 LOW captions / 11,441 user moves = 0.7%.
   That's the noise floor with the current detector set.
2. **Delete the engine-speak variants.** Replaces them with bare
   `X is a mistake. Y was better.` (MID tier). Less informative but no
   engine-speak.
3. **Build a new detector** that catches positional / move-quality
   reasons in balanced positions where current detectors miss. Hard.

## Pattern bucket

For grouping in your review: `engine_speak_balanced_position`
(this caption is correctly LOW per the pipeline; the question is
whether to leave it or eliminate the variants entirely).
