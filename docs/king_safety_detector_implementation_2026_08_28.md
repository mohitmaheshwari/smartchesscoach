# King-Safety Detector - Implementation Evidence

**Date:** 2026-08-28
**Decision:** Repaired and kept **Disabled**.

## Implemented

- services.board_state_describer now exposes one structured KingSafetyState.
- Existing board-state captions and Chess Brain share the same pawn-shelter
  and unique king-zone-attacker geometry.
- Pawn-shield issues require two missing shelter pawns and an opponent queen.
- King-zone issues require three unique enemy attacking pieces.
- The Chess Brain detector fires only when:
  - cp_loss is present and reaches the shared 100cp causal-error floor;
  - the position is not an endgame under GamePhaseCalculator;
  - played and engine-best moves are both legal and different; and
  - the best-move issue set is a strict subset of the played-move issue set.
- Strict set reduction rejects a move that merely swaps one king-safety issue
  for another.
- The detector registration now requires an engine best move.
- The old file-based castling inference and duplicated shield/attacker loops
  were removed from Chess Brain.

## Verification

The focused king-safety and trapped-piece suite passed **20 tests**. New
adversarial coverage includes:

- a move that breaks a pawn shield while the best move preserves it;
- a move that walks into a three-piece king-zone attack;
- a pure endgame that must abstain;
- a best move that swaps pawn-shield risk for king-zone pressure;
- low or missing cp_loss, missing best move and played-equals-best abstention;
- required best-move registration and a shared consequence threshold; and
- a source guard proving Chess Brain delegates to canonical state.

Both modified services pass Python compilation.

The broader Chess Brain unit/integration suite passed **28 tests with 3
environment-dependent skips** after its two stale registry-count assertions
were aligned with the canonical 10 tactical / 20 strategic / 3 behavioral
inventory. A consolidated canonical-truth run passed **78 tests**; its only
failure is an unrelated pre-existing severity mismatch for the development-gap
board-state fact (test expects 20, implementation returns 15).

The repository-mandated end-to-end script was also invoked, but no local API
server was listening, so it stopped on its first HTTP request with
httpx.ConnectError before exercising a product flow.

## Production evidence

The measured contracts and rejected formulas are recorded in
docs/king_safety_detector_data_lock_2026_08_28.md.

The previous implementation fired 3,339 times across 9,443 user-move
positions in 300 analyses, including 2,311 fires at <=50cp. On a fresh
500-analysis sample, the selected phase-aware, subtype-aware, strict-subset
contract left 90 audit candidates (0.18 per analysis): 65 pawn-shield and 25
king-zone-attack candidates. They are not verified semantic positives.

## Authorization

brain:king_safety_detector remains **Disabled**. It cannot influence captions,
plans, mastery, prompts or player state. Reconsideration requires blinded
semantic review, hard-negative review and an independent opportunity
denominator.

No deployment, backfill, database write or production mutation was performed.
