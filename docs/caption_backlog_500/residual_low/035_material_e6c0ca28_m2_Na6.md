# e6c0ca28-16a m2 Na6 — residual LOW #35

**Variant:** `why_user_missed_material`
**Position (FEN):** `rnbqkbnr/ppp1pppp/8/2Pp4/8/8/PP1PPPPP/RNBQKBNR b KQkq - 0 2`
**Move played:** `Na6` (cp_loss `204`)
**Engine's best (stored):** `e5`
**User color:** black

## Caption as shipped

> Na6 is a mistake. e5 was better. e5 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `-184cp`  PV: `e5 d4 exd4 e3 Bxc5 exd4`
  #2 eval(W) `-81cp`  PV: `Nd7 d4 e5 e3 g6 Nf3`
  #3 eval(W) `-71cp`  PV: `d4 Nf3 e5 Nxe5 Bxc5 g3`

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
