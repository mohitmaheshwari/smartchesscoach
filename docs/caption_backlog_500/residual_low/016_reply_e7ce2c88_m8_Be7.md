# e7ce2c88-008 m8 Be7 — residual LOW #16

**Variant:** `why_user_reply`
**Position (FEN):** `rnbqkb1r/pp3pp1/2p1p2p/4P3/3PpPP1/2P5/PP5P/R1BQKBNR b KQkq - 0 8`
**Move played:** `Be7` (cp_loss `159`)
**Engine's best (stored):** `Qh4+`
**User color:** black

## Caption as shipped

> Be7 is a mistake. Qh4+ was better. Opponent's strongest reply: Bg2.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `-41cp`  PV: `Qh4+ Kd2 c5 Kc2 Nc6 dxc5`
  #2 eval(W) `+93cp`  PV: `c5 Ne2 Nc6 dxc5 Qh4+ Ng3`
  #3 eval(W) `+107cp`  PV: `Bd7 Ne2 c5 Bg2 Nc6 O-O`

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
