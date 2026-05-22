# b84a1c55-79a m10 a5 — residual LOW #29

**Variant:** `why_user_missed_material`
**Position (FEN):** `r1bqk2r/p1pp1ppp/2p5/4P3/1nP5/B7/P1P2PPP/R2QKB1R b KQkq - 2 10`
**Move played:** `a5` (cp_loss `205`)
**Engine's best (stored):** `Qe7`
**User color:** black

## Caption as shipped

> a5 is a mistake. Qe7 was better. Qe7 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+11cp`  PV: `Qe7 Bb2 d5 Be2 Bf5 O-O`
  #2 eval(W) `+85cp`  PV: `c5 Be2 O-O O-O d6 c3`
  #3 eval(W) `+169cp`  PV: `Rb8 c3 Na6 Qg4 g6 Qg3`

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
