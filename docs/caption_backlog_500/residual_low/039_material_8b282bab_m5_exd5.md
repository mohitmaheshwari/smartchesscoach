# 8b282bab-b71 m5 exd5 — residual LOW #39

**Variant:** `why_user_missed_material`
**Position (FEN):** `rnbqkb1r/ppp2ppp/7n/3pp3/2B1P3/3P1Q2/PPP2PPP/RNB1K1NR w KQkq - 0 5`
**Move played:** `exd5` (cp_loss `118`)
**Engine's best (stored):** `Bxd5`
**User color:** white

## Caption as shipped

> exd5 is a mistake. Bxd5 was better. Bxd5 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+243cp`  PV: `Bxd5 c6 Bb3 Qe7 Qg3 a5`
  #2 eval(W) `+134cp`  PV: `exd5 Nf5 Qe4 Be7 Nf3 O-O`
  #3 eval(W) `+133cp`  PV: `Bb3 dxe4 dxe4 Qe7 Ne2 Bg4`

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
