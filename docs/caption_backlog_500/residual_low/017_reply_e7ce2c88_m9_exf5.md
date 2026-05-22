# e7ce2c88-008 m9 exf5 — residual LOW #17

**Variant:** `why_user_reply`
**Position (FEN):** `rnbqk2r/pp2bpp1/2p1p2p/4PP2/3Pp1P1/2P5/PP5P/R1BQKBNR b KQkq - 0 9`
**Move played:** `exf5` (cp_loss `163`)
**Engine's best (stored):** `Bh4+`
**User color:** black

## Caption as shipped

> exf5 is a mistake. Bh4+ was better. Opponent's strongest reply: Ne2.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `-257cp`  PV: `Bh4+ Kd2 c5 Bb5+ Nc6 Kc2`
  #2 eval(W) `-118cp`  PV: `c5 Ne2 cxd4 Qxd4 exf5 Qxd8+`
  #3 eval(W) `-97cp`  PV: `h5 Bf4 Bh4+ Bg3 Qg5 Nh3`

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
