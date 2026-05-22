# 2d5ad07d-1cc m7 Bf1 — residual LOW #24

**Variant:** `why_user_missed_material`
**Position (FEN):** `rnb1kbnr/ppp3pp/8/3q1p2/4p3/5N2/PPPPBPPP/RNBQR1K1 w kq - 0 7`
**Move played:** `Bf1` (cp_loss `162`)
**Engine's best (stored):** `d3`
**User color:** white

## Caption as shipped

> Bf1 is a mistake. d3 was better. d3 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+322cp`  PV: `d3 Qd8 dxe4 Qxd1 Bxd1 fxe4`
  #2 eval(W) `+250cp`  PV: `Nc3 Qd8 Bb5+ c6 Bc4 Be7`
  #3 eval(W) `+237cp`  PV: `d4 Nf6 Nc3 Qd8 Bb5+ c6`

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
