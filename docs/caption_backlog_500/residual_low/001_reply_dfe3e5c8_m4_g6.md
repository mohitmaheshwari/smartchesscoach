# dfe3e5c8-927 m4 g6 — residual LOW #1

**Variant:** `why_user_reply`
**Position (FEN):** `r1bqkbnr/pp1ppppp/2n5/8/3PP3/8/PP3PPP/RNBQKBNR b KQkq - 0 4`
**Move played:** `g6` (cp_loss `149`)
**Engine's best (stored):** `d5`
**User color:** black

## Caption as shipped

> g6 is a mistake. d5 was better. Opponent's strongest reply: d5.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `+43cp`  PV: `d5 Nc3 Nf6 e5 Ne4 Bb5`
  #2 eval(W) `+52cp`  PV: `e6 d5 exd5 exd5 Bb4+ Nc3`
  #3 eval(W) `+57cp`  PV: `e5 dxe5 d6 Nc3 dxe5 Qxd8+`

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
