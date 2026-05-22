# fc6a7bad-9d3 m4 Bc5 — residual LOW #37

**Variant:** `why_user_missed_material`
**Position (FEN):** `r1bqkb1r/pppp1ppp/2n2n2/4p3/4P1P1/2P2Q2/PP1P1P1P/RNB1KBNR b KQkq - 0 4`
**Move played:** `Bc5` (cp_loss `337`)
**Engine's best (stored):** `d5`
**User color:** black

## Caption as shipped

> Bc5 is a serious mistake. d5 was better. d5 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `-333cp`  PV: `d5 exd5 Bxg4 Qg2 Qxd5 Qxd5`
  #2 eval(W) `-166cp`  PV: `h6 h3 d5 d3 Be6 Qe2`
  #3 eval(W) `-61cp`  PV: `d6 g5 Nd7 Bc4 Qe7 d3`

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
