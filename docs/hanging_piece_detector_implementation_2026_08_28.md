# Hanging-Piece Detector - Implementation Evidence

**Date:** 2026-08-28
**Decision:** Repaired and retained at **Shadow**.

## Implemented

- `services.caption_facts.legal_exchange_gain` remains canonical exchange
  truth.
- `legally_hanging_pieces` exposes a structured view containing the piece,
  square, exact material loss and legal winning capture.
- Chess Brain removed its independent attacked-and-undefended heuristic.
- The detector now requires:
  - legal, different played and engine-best moves;
  - the shared 100cp causal-mistake floor;
  - at least 150cp of exact legal material loss; and
  - a best-move issue set that is a strict subset of the played-move set.
- Pawn-only losses are suppressed, while 200cp minor-piece-for-pawn losses are
  preserved.
- Both moved-piece hangs and another piece left exposed are reported.
- Evidence includes the legal winning reply and the engine move that avoided
  the issue.
- Detector registration now requires an engine best move.

## Verification

The focused hanging-piece, exchange-truth, trapped-piece and king-safety suite
passed **38 tests**. New adversarial cases cover:

- a bishop moved onto a losing square;
- castling while leaving a knight exposed;
- a sound defended exchange;
- a defender revealed by an x-ray after capture;
- pawn-only loss below the coaching floor;
- a pre-existing hang left unchanged by both played and best moves;
- low or missing cp_loss, missing best move and played-equals-best abstention;
- required best-move registration and locked floors; and
- a source guard proving Chess Brain no longer computes attacker counts.

Both modified Python services compile successfully.

The consolidated detector-quality and Chess Brain suite passed **78 tests with
3 environment-dependent skips**. The quality report confirms the detector is
explicitly Shadow and has no caption, plan or mastery authorization.

The repository-mandated end-to-end script was invoked, but no local API server
was listening. It stopped on the first dashboard request with
`httpx.ConnectError` before exercising a product flow.

## Production evidence

The formula bake-off and rejected candidates are recorded in
`docs/hanging_piece_detector_data_lock_2026_08_28.md`.

On the same 200-analysis / 6,316-position sample, the old heuristic fired 1,476
times. The selected exact, strict-counterfactual, consequence-gated contract
left 197 candidates. A separate residual sample confirmed that both supported
subtypes occur frequently: 61 moved-piece and 55 other-piece issues.

These are candidate audit items, not verified semantic positives.

## Authorization

`brain:hanging_piece_detector` remains **Shadow**. It cannot influence a
player-facing surface under the quality gate. Promotion requires blinded
semantic review, hard negatives and an independent opportunity denominator.

No deployment, backfill, database write or production mutation was performed.
