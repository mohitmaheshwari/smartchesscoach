# f5a5f58c-d52 m5 d6 — residual LOW #12

**Variant:** `why_user_reply`
**Position (FEN):** `r1bqk2r/pppp1ppp/2n2n2/2b1p3/P1B1P3/2PP4/1P3PPP/RNBQK1NR b KQkq - 0 5`
**Move played:** `d6` (cp_loss `273`)
**Engine's best (stored):** `a5`
**User color:** black

## Caption as shipped

> d6 is a serious mistake. a5 was better. Opponent's strongest reply: b4.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+16cp`  PV: `a5 Nf3 d6 O-O O-O h3`
  #2 eval(W) `+18cp`  PV: `O-O Nf3 a6 h3 d6 b4`
  #3 eval(W) `+20cp`  PV: `a6 Nf3 Ba7 O-O d6 h3`

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
