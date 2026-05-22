# d57e7eea-556 m6 Bg4 — residual LOW #28

**Variant:** `why_user_missed_material`
**Position (FEN):** `r1bqk1nr/pp2ppbp/2np2p1/2p1P3/3P1P2/2P2N2/PP4PP/RNBQKB1R b KQkq - 0 6`
**Move played:** `Bg4` (cp_loss `180`)
**Engine's best (stored):** `cxd4`
**User color:** black

## Caption as shipped

> Bg4 is a mistake. cxd4 was better. cxd4 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `-50cp`  PV: `cxd4 cxd4 dxe5 fxe5 Bg4 Bb5`
  #2 eval(W) `-24cp`  PV: `dxe5 dxe5 Qxd1+ Kxd1 f6 Be3`
  #3 eval(W) `+21cp`  PV: `Nh6 d5 Nb8 h3 O-O Bc4`

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
