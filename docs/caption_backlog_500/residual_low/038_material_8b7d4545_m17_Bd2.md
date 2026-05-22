# 8b7d4545-94d m17 Bd2 — residual LOW #38

**Variant:** `why_user_missed_material`
**Position (FEN):** `2rqr1k1/b1p2pp1/p3b2p/1p1np3/4N3/P1PP1Q1P/BP3PP1/R1B2R1K w - - 1 17`
**Move played:** `Bd2` (cp_loss `210`)
**Engine's best (stored):** `Bxh6`
**User color:** white

## Caption as shipped

> Bd2 is a mistake. Bxh6 was better. Bxh6 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+186cp`  PV: `Bxh6 Nf4 Bxf4 exf4 Bxe6 Rxe6`
  #2 eval(W) `+26cp`  PV: `g4 f6 Be3 Bb6 c4 Nf4`
  #3 eval(W) `+26cp`  PV: `Be3 Nxe3 Bxe6 Rxe6 fxe3 Qe8`

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
