# 9e6941fc-ae7 m16 Qe4 — residual LOW #36

**Variant:** `why_user_missed_material`
**Position (FEN):** `rb1q1rk1/1b1p1pp1/p5np/np1PP3/2p5/P1NQ1N2/1PB2PPP/R1B1R1K1 w - - 0 16`
**Move played:** `Qe4` (cp_loss `168`)
**Engine's best (stored):** `Qf5`
**User color:** white

## Caption as shipped

> Qe4 is a mistake. Qf5 was better. Qf5 wins material in the resulting line.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+198cp`  PV: `Qf5 Nb3 Rb1 Nc5 h4 Nd3`
  #2 eval(W) `+112cp`  PV: `Qe4 Nb3 Rb1 Nxc1 Rbxc1 f5`
  #3 eval(W) `+85cp`  PV: `Qd1 Nb3 Rb1 Nxc1 Rxc1 Bc7`

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
