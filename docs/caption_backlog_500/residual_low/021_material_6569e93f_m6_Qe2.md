# 6569e93f-a90 m6 Qe2 — residual LOW #21

**Variant:** `why_user_missed_material`
**Position (FEN):** `rnbqk1nr/pppp1ppp/8/2b1P3/5p2/2N2N2/PPPP2PP/R1BQKB1R w KQkq - 1 6`
**Move played:** `Qe2` (cp_loss `175`)
**Engine's best (stored):** `d4`
**User color:** white

## Caption as shipped

> Qe2 is a mistake. d4 was better. d4 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+225cp`  PV: `d4 Bb4 Bxf4 d5 Bd3 Bxc3+`
  #2 eval(W) `+142cp`  PV: `Bb5 a6 d4 axb5 dxc5 b4`
  #3 eval(W) `+131cp`  PV: `Nd5 Ne7 Nxf4 d6 d4 Bb6`

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
