# fc97ee1d-ba3 m7 Bb5 — residual LOW #23

**Variant:** `why_user_missed_material`
**Position (FEN):** `r1bqkbnr/pppp3p/n4p2/3Pp1p1/4P3/2P2N1P/PP3PP1/RNBQKB1R w KQkq - 0 7`
**Move played:** `Bb5` (cp_loss `210`)
**Engine's best (stored):** `Nxe5`
**User color:** white

## Caption as shipped

> Bb5 is a mistake. Nxe5 was better. Nxe5 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+408cp`  PV: `Nxe5 Ke7 d6+ cxd6 Nc4 d5`
  #2 eval(W) `+343cp`  PV: `Nxg5 Nh6 Qh5+ Ke7 f4 exf4`
  #3 eval(W) `+341cp`  PV: `Bxa6 bxa6 Nxe5 h5 Ng6 Rh7`

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
