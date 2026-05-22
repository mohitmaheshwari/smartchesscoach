# a9cd46d0-1a8 m14 a3 — residual LOW #11

**Variant:** `why_user_reply`
**Position (FEN):** `rnb2r2/2q1npkp/p1p1p1p1/1p2N3/2pP4/2N1P1P1/PP1Q1PBP/R4RK1 w - - 2 14`
**Move played:** `a3` (cp_loss `100`)
**Engine's best (stored):** `Ne4`
**User color:** white

## Caption as shipped

> a3 is a mistake. Ne4 was better. Opponent's strongest reply: f6.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+73cp`  PV: `Ne4 Nd7 Nxd7 Bxd7 b3 cxb3`
  #2 eval(W) `+39cp`  PV: `Rfd1 f6 Nf3 Nd7 Ne4 a5`
  #3 eval(W) `+38cp`  PV: `Rfc1 f6 Nf3 Nd7 Ne4 a5`

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
