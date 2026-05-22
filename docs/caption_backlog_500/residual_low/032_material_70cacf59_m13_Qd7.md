# 70cacf59-14e m13 Qd7 — residual LOW #32

**Variant:** `why_user_missed_material`
**Position (FEN):** `r2q1rk1/pb2npbp/1n1pp1p1/2p5/4PP2/1BN1BN1P/PPP3P1/1R1Q1RK1 b - - 5 13`
**Move played:** `Qd7` (cp_loss `100`)
**Engine's best (stored):** `c4`
**User color:** black

## Caption as shipped

> Qd7 is a mistake. c4 was better. c4 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `-259cp`  PV: `Bxc3 bxc3 c4 Ba4 Bxe4 Bb5`
  #2 eval(W) `-250cp`  PV: `c4 Ba4 Bxc3 bxc3 Bxe4 Bb5`
  #3 eval(W) `-205cp`  PV: `Ba6 Rf2 Bxc3 bxc3 c4 Bxb6`

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
