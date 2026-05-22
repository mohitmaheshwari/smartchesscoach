# fc3914fc-1de m27 c5 — residual LOW #30

**Variant:** `why_user_missed_material`
**Position (FEN):** `8/2p3pk/1b1pp2p/4p3/1PP1P3/7P/3KNr2/1R6 b - - 0 27`
**Move played:** `c5` (cp_loss `276`)
**Engine's best (stored):** `Rf3`
**User color:** black

## Caption as shipped

> c5 is a serious mistake. Rf3 was better. Rf3 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `-376cp`  PV: `Rf3 Nc1 Rxh3 Nb3 Bd4 Nxd4`
  #2 eval(W) `-369cp`  PV: `Kg6 Rb3 Kh5 Rc3 Kh4 Kd1`
  #3 eval(W) `-357cp`  PV: `Rh2 Rb3 g5 Rc3 Kg6 Kd1`

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
