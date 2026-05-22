# c25fea91-894 m19 Kf8 — residual LOW #6

**Variant:** `why_user_reply`
**Position (FEN):** `4r1k1/p1p2ppp/2p3q1/8/5B2/2PP2P1/P1P1bPQP/R5K1 b - - 5 19`
**Move played:** `Kf8` (cp_loss `179`)
**Engine's best (stored):** `Qf6`
**User color:** black

## Caption as shipped

> Kf8 is a mistake. Qf6 was better. Opponent's strongest reply: Be3.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `-2cp`  PV: `Qf6 Bd2 Bf3 Qf1 c5 Re1`
  #2 eval(W) `+6cp`  PV: `Re6 Rb1 h6 Be3 Qh5 h3`
  #3 eval(W) `+30cp`  PV: `Bg4 f3 Bd7 c4 c5 Bxc7`

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
