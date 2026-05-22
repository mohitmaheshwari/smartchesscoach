# d57e7eea-556 m7 a6 — residual LOW #13

**Variant:** `why_user_reply`
**Position (FEN):** `r2qk1nr/pp2ppbp/2np2p1/2p1P3/Q2P1Pb1/2P2N2/PP4PP/RNB1KB1R b KQkq - 2 7`
**Move played:** `a6` (cp_loss `150`)
**Engine's best (stored):** `Bxf3`
**User color:** black

## Caption as shipped

> a6 is a mistake. Bxf3 was better. Opponent's strongest reply: d5.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `-183cp`  PV: `Bxf3 gxf3 cxd4 cxd4 e6 Bb5`
  #2 eval(W) `-99cp`  PV: `cxd4 Nxd4 Bd7 Nxc6 Qc7 Qd4`
  #3 eval(W) `-53cp`  PV: `Bd7 Qb3 Nh6 d5 Na5 Qd1`

## Diagnosis

No tactical / positional detector matched this position. The engine has an opp_reply in its PV, so the engine-speak fallback fires. cp_loss is 100-249 (mistake tier) AND user is in a balanced position (per v51 gating).

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
