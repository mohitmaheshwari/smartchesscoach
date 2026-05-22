# c25fea91-894 m20 Qe6 — residual LOW #7

**Variant:** `why_user_reply`
**Position (FEN):** `4rk2/p1p2ppp/2p3q1/8/5B2/2PP2P1/P1P1bPQP/4R1K1 b - - 7 20`
**Move played:** `Qe6` (cp_loss `321`)
**Engine's best (stored):** `Bg4`
**User color:** black

## Caption as shipped

> Qe6 is a serious mistake. Bg4 was better. Opponent's strongest reply: Be3.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+110cp`  PV: `Bg4 Rxe8+ Kxe8 f3 Be6 Qe2`
  #2 eval(W) `+124cp`  PV: `Bh5 Be3 Kg8 Kf1 f5 c4`
  #3 eval(W) `+225cp`  PV: `c5 Be3 Qh5 Qc6 Re5 Qxc7`

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
