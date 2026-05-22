# b39642d4-33e m4 Bc4 — residual LOW #40

**Variant:** `why_user_missed_material`
**Position (FEN):** `r1bqkbnr/pppp1ppp/2n5/8/4Pp2/5N2/PPPP2PP/RNBQKB1R w KQkq - 2 4`
**Move played:** `Bc4` (cp_loss `126`)
**Engine's best (stored):** `d4`
**User color:** white

## Caption as shipped

> Bc4 is a mistake. d4 was better. d4 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+29cp`  PV: `d4 g5 d5 g4 dxc6 gxf3`
  #2 eval(W) `-50cp`  PV: `Nc3 g5 h4 g4 Ng1 Bh6`
  #3 eval(W) `-100cp`  PV: `b3 Be7 Bc4 Bh4+ Kf1 d6`

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
