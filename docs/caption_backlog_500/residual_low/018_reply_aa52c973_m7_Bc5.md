# aa52c973-d5b m7 Bc5 — residual LOW #18

**Variant:** `why_user_reply`
**Position (FEN):** `rnbqkb1r/pp3ppp/2p1pn2/8/2B3P1/4PQ1P/PP1P1P2/RNB1K1NR b KQkq - 0 7`
**Move played:** `Bc5` (cp_loss `100`)
**Engine's best (stored):** `b5`
**User color:** black

## Caption as shipped

> Bc5 is a mistake. b5 was better. Opponent's strongest reply: Ne2.

## Live engine view (depth 15, multipv 3)

  #1 eval(W) `-120cp`  PV: `b5 Be2 Bb7 d4 Qc7 Qg2`
  #2 eval(W) `-93cp`  PV: `c5 Nc3 a6 Qg2 Nc6 g5`
  #3 eval(W) `-91cp`  PV: `a6 Nc3 c5 Qg2 Nc6 g5`

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
