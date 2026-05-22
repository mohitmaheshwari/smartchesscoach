# 23b2a4f0-e0e m6 Qd2 — residual LOW #33

**Variant:** `why_user_missed_material`
**Position (FEN):** `r1b1kb1r/pp2pppp/2n2n2/qNpp4/2PP1B2/8/PP2PPPP/R2QKBNR w KQkq - 6 6`
**Move played:** `Qd2` (cp_loss `105`)
**Engine's best (stored):** `Bd2`
**User color:** white

## Caption as shipped

> Qd2 is a mistake. Bd2 was better. Bd2 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+22cp`  PV: `Bd2 Qd8 cxd5 Nxd4 Nxd4 cxd4`
  #2 eval(W) `-26cp`  PV: `Qd2 Qxd2+ Bxd2 Nxd4 Nxd4 cxd4`
  #3 eval(W) `-324cp`  PV: `b4 Nxb4 Bd2 dxc4 a3 Qxb5`

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
