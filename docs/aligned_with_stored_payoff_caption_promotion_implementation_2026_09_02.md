# Exact pin/skewer Caption promotion — implementation record

Date: 2026-09-02

Quality id: `tactic:aligned_with_stored_payoff`

Authorized surface: **Caption only**

## Outcome

ChessGuru may now explain a pin or skewer after a puzzle attempt only when two
independent deterministic paths agree that:

1. the stored best move creates a new two-target line;
2. the attacker, front target and rear target are the same physical pieces
   throughout the stored continuation;
3. the continuation uses that exact line to gain material; and
4. the recorded mistake has at least 100 centipawns of stored loss.

The caption names the move, attacker, attacker square, both target pieces and
both target squares. It distinguishes a direct alignment from a discovered
alignment, where another move clears the attacker's line.

## Evidence packet

Canonical packet:
`backend/data/detector_gold/aligned_payoff_caption_promotion_v1.json`

Canonical JSON SHA-256:
`5fc64110390f739cfea3cdb12929d8994590bfd399dc4b016c3b3b8c8a56ec1e`

Selection fingerprint:
`de3ccb6ff3338b63e37c0945875dabb15151e4b8a85762283716d4dc53fc7c37`

The read-only corpus census scanned 52,085 stored puzzle documents and found
436 existing verified candidates from 363 distinct sources:

- 285 pins and 151 skewers;
- 374 direct and 62 discovered alignments;
- 178 bishop, 151 rook and 107 queen attackers;
- 104 community puzzles and 332 community training positions;
- zero candidate replay failures; and
- zero stored-fact mismatches.

No Stockfish run, LLM call or database write was performed. The packet contains
only 100 anonymized FENs with stored four-ply continuations and hashed source
tokens. It contains no user id, game id, email, credential or database address.

## Locked promotion result

The positive sample contains 25 pins and 25 skewers. Each subtype separately
scored 25/25 correct with an 86.68% Wilson lower confidence bound. Combined
precision was 50/50 with a 92.87% Wilson lower bound.

The negative sample contains 50/50 correct abstentions, five from each locked
failure family:

- no new alignment;
- incomplete line;
- insufficient stored consequence;
- insufficient net material gain;
- attacker leaves before the payoff;
- pinned front piece escapes;
- pin target is not captured;
- skewered front piece does not clear;
- skewered rear piece escapes; and
- skewer rear target is not captured.

Critical adversarial errors: zero.

## Runtime design

`aligned_tactic_puzzle_proof.py` remains the proof source. Version 3 adds only
verified explanatory facts: `creation_mode`, attacker piece, front piece and
rear piece. It does not widen the detector.

`verified_puzzle_feedback.py` remains the sole renderer. Direct alignments say
the move puts the attacking piece on the line. Discovered alignments say the
move clears a line for the existing attacking piece. Both explain the concrete
piece-and-square relationship before ending with a reusable board-reading
habit.

`detector_quality.py` authorizes this quality id at Caption grade. The exact
pin/skewer identity is deliberately unavailable to prompts, plans, recurrence
scoring and mastery. Those surfaces still use the verified broad category
`missed_tactic`.

The separate research identities `shape:pin` and `shape:skewer` remain
Shadow. No new learner skill, mastery opportunity or curriculum node was
created.

## Verification

- Focused promotion and contract suite: 31 passed.
- All direct dependents of proof, authorization, admission, feedback and
  verdict construction: 419 passed.
- Wider puzzle/training regression suite: 127 passed, 59 environment-dependent
  tests skipped.
- Python syntax compilation: passed.
- Diff whitespace check: passed.
- Coaching voice audit: clean. Captions avoid engine language and unsupported
  claims, explain the geometry in plain language, name squares, and end with a
  reusable principle.
- Repository live-HTTP `test_all_flows.py`: inconclusive because no local
  backend was listening; it stopped on the first connection attempt before any
  product assertion. It was not pointed at production because the suite
  contains mutation-capable flows.

## Operational boundary

This worktree made no production write and performed no deployment. Existing
stored admissions will need the normal version-aware reconciliation path after
integration so their version-2 proof records can be rebuilt under version 3.
That operational step must be dry-run, inspected and backed up before any
apply.
