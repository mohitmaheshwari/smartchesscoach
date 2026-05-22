# fc97ee1d-ba3 m8 Bc4 — residual LOW #3

**Variant:** `why_user_reply`
**Position (FEN):** `r1bqkbnr/pp1p3p/n1p2p2/1B1Pp1p1/4P3/2P2N1P/PP3PP1/RNBQK2R w KQkq - 0 8`
**Move played:** `Bc4` (cp_loss `217`)
**Engine's best (stored):** `Bxa6`
**User color:** white

## Caption as shipped

> Bc4 is a mistake. Bxa6 was better. Opponent's strongest reply: d6.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+379cp`  PV: `Nxe5 h5 Ng6 Rh6 Bxa6 bxa6`
  #2 eval(W) `+332cp`  PV: `Bxa6 g4 Nxe5 fxe5 Bc4 Nf6`
  #3 eval(W) `+301cp`  PV: `Nxg5 Nh6 Qh5+ Ke7 Bc4 b5`

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
