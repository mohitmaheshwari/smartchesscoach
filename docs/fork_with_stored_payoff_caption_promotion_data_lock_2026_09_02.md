# Fork With Stored Payoff Caption Promotion — Data Lock

**Date:** 2026-09-02
**Status:** LOCKED FOR PHASE 3 IMPLEMENTATION
**Parent evidence:** `docs/complete_coaching_system_phase0_data_lock_2026_09_02.md`
**Threshold authority:** `docs/detector_quality_threshold_lock_2026_08_27.md`

## Decision locked

`tactic:fork_with_stored_payoff` may be promoted from Shadow to Caption only after a versioned independent packet passes. Prompt, Plan and Mastery remain unauthorized.

The proof contract is:

1. the played and stored-best moves are legal, different, and carry at least the existing 100cp stored consequence;
2. after the stored best move, the moved knight, bishop, rook or pawn directly attacks at least two opponent kings or pieces worth at least a minor piece;
3. the stored continuation replays legally and completely;
4. material balance improves by at least the existing pawn-value floor across that continuation; and
5. the initiating side captures at least one of the original fork targets before that target leaves its square.

The Caption claim is deliberately narrower than the proof: it names only the simultaneous attacks. It does not promise that every opponent defence loses material.

## Selection evidence

A credential-safe, read-only production replay on 2026-09-02 measured:

| Population | Count |
|---|---:|
| Documents scanned across both pools | 52,060 |
| Stored fork candidates | 709 |
| Distinct stored source fingerprints | 589 |
| Independent exact passes among stored candidates | **709 / 709** |
| Stored verifier-fact mismatches | **0** |

Stored candidates by pool:

| Pool | Candidates |
|---|---:|
| `community_puzzles` | 155 |
| `community_training_positions` | 554 |

Stored candidates by forking piece were 451 knight, 118 bishop, 80 rook and 60 pawn. There were 651 two-target positions and 58 three-target positions. Every stored continuation contained four plies after the best move.

The same independent replay classified the full 52,060-position pool, providing abundant controls:

| Independent outcome | Positions |
|---|---:|
| Fewer than two qualifying targets | 46,872 |
| Incomplete/illegal stored continuation | 515 |
| Complete line but less than pawn-value net gain | 1,566 |
| Material gained without capturing an original fork target | 1,488 |
| Exact fork/payoff shape but stored consequence below 100cp | 35 |

It also found 1,288 exact fork/payoff positions overall. Only the 709 already attributed to this quality family form the promotion population; the others may have a higher-priority proof and are not silently relabelled here.

No user, account or game identity was emitted. Stockfish runs, LLM calls and database writes were zero.

## Promotion packet lock

The positive sample inherits the existing Caption minimum unchanged:

- 50 independently verified fires from 50 distinct source fingerprints;
- raw semantic precision at least 95%;
- 95% Wilson precision lower bound at least 85%;
- zero critical adversarial failures.

The negative packet uses 25 cases because five materially different observed failure modes must remain represented. Five deterministic cases are selected from each: fewer-than-two targets, incomplete line, insufficient net gain, no original target captured, and insufficient stored consequence. Reducing the packet to the generic 20-case minimum would omit a measured failure family without any evidence-based reason.

The positive sample must include both pools, all four supported forking pieces, and both observed target-count classes. Stable SHA-256 ordering makes selection reproducible. The output contains only board/proof facts and one-way case/source keys.

## Independent adjudication

Promotion gold must not import or call the canonical shape detectors, `build_fork_proof`, `_independent_fork_and_payoff`, `replay_stored_line`, or the stored verifier verdict. It independently:

1. parses the FEN, played move, best move and stored continuation;
2. pushes the best move and reconstructs attacks from the moved piece's square;
3. records every qualifying enemy target directly from the new board;
4. replays every stored ply legally while tracking material from board state;
5. tracks each original target by square, piece type and colour, removing it if it moves;
6. proves the initiating side captures an original still-present target;
7. compares all derived facts with the stored proof.

## Rejected candidates

- **Plan/Mastery promotion:** rejected because no fork learner skill, recall denominator or transfer evidence exists.
- **Use all 1,288 independently exact positions as stored candidates:** rejected because attribution priority is part of the existing admission contract.
- **Describe exactly two targets:** rejected because 58 verified candidates attack three targets.
- **Say every fork wins a piece:** rejected because one stored line is not an all-defence proof.
- **Reuse the canonical verifier as gold:** rejected because promotion requires an independent calculation path.
- **Create another detector or caption renderer:** rejected because canonical owners already exist.
