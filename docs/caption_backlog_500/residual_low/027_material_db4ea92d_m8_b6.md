# db4ea92d-83e m8 b6 — residual LOW #27

**Variant:** `why_user_missed_material`
**Position (FEN):** `r2qkb1r/pp3ppp/2n1bn2/2Ppp3/1P6/P3P3/5PPP/RNBQKBNR b KQkq - 0 8`
**Move played:** `b6` (cp_loss `116`)
**Engine's best (stored):** `a5`
**User color:** black

## Caption as shipped

> b6 is a mistake. a5 was better. a5 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `-144cp`  PV: `a5 b5 Na7 Nf3 e4 Nd4`
  #2 eval(W) `-113cp`  PV: `d4 Nf3 a5 b5 dxe3 Qxd8+`
  #3 eval(W) `-89cp`  PV: `Nd7 Bb2 a5 Bb5 axb4 Bxc6`

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
