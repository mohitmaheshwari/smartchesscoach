# 461ece5c-604 m11 e4 — residual LOW #22

**Variant:** `why_user_missed_material`
**Position (FEN):** `r2qk2r/1ppn1p2/p2bpp1p/5b2/2pP4/2N2NP1/PP2PPBP/R2QR1K1 w kq - 0 11`
**Move played:** `e4` (cp_loss `145`)
**Engine's best (stored):** `Nh4`
**User color:** white

## Caption as shipped

> e4 is a mistake. Nh4 was better. Nh4 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+155cp`  PV: `Nh4 Bh7 Bxb7 Rb8 Bxa6 Rxb2`
  #2 eval(W) `+123cp`  PV: `Nd2 c6 Nxc4 Bc7 e4 Bg6`
  #3 eval(W) `+66cp`  PV: `a4 c6 a5 Bc7 Qa4 O-O`

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
