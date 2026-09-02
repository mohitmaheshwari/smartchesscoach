# Free-Piece Exact Caption Promotion — Data Lock

**Date:** 2026-09-02
**Status:** LOCKED FOR PHASE 3 IMPLEMENTATION
**Parent evidence:** `docs/complete_coaching_system_phase0_data_lock_2026_09_02.md`
**Threshold authority:** `docs/detector_quality_threshold_lock_2026_08_27.md`

## Decision locked

`tactic:free_piece_exact` may be promoted from Shadow to Caption only after a versioned independent packet passes. It may not become Plan, Prompt or Mastery.

The exact publishable claim is:

> The stored best move legally captures an opponent knight, bishop, rook or queen on the named square, the played move is different, the stored consequence is at least the existing 100cp proof floor, and the opponent has no legal immediate recapture on that square.

The caption may say that the opponent has no legal recapture. It may not strengthen this to a general claim that the material remains won through every later tactic.

## Selection evidence

The versioned Phase 0 snapshot selected this family first with 1,603 documents and 1,302 distinct stored sources. A read-only production replay on 2026-09-02 found modest corpus growth:

| Pool | Candidate documents | Distinct source fingerprints | Independent exact passes |
|---|---:|---:|---:|
| `community_puzzles` | 403 | 403 | 403 |
| `community_training_positions` | 1,204 | 1,159 | 1,204 |
| Cross-pool union | 1,607 | **1,305** | **1,607** |

The independent replay found zero captured-piece mismatches, zero captured-value mismatches and zero recapture-fact mismatches. Target distribution was 579 bishops, 533 knights, 277 rooks and 218 queens.

Near-negative supply across the same two pools is abundant:

| Independent outcome | Stored positions |
|---|---:|
| Best capture has a legal immediate recapture | 4,612 |
| Best capture takes only a pawn/lower-value target | 6,261 |
| Best move is not a capture | 34,278 |
| Stored consequence is below the existing proof floor | 4,280 |

No user identifier, game identifier, move, FEN, PGN, caption, credential or connection string was emitted by the aggregate measurement. Stockfish runs and database writes were zero.

## Promotion packet lock

The packet reuses the already-locked Caption minimums rather than inventing new thresholds:

- 50 independently verified fires from 50 distinct source fingerprints;
- at least 20 true-negative/non-opportunity cases;
- raw semantic precision at least 95%;
- 95% Wilson precision lower bound at least 85%;
- zero critical errors in the adversarial packet.

The 20 negative cases are split evenly across four observed guard families so no one easy negative type satisfies the bar: immediate recapture, lower-value target, non-capture, and insufficient stored consequence. The positive sample must contain both pools and all four target-piece types.

Stable SHA-256 ordering makes the selection reproducible. Case output contains only the board/proof facts needed for audit and one-way case/source keys; account, user and game identities are omitted.

## Independent adjudication

The gold verifier must not import or call `detect_free_piece`, `build_free_piece_proof`, or the stored verifier verdict. It independently:

1. parses the FEN and both moves;
2. proves both moves are legal and different;
3. proves the best move is a capture;
4. identifies the captured piece directly from the board;
5. enforces the existing minor-piece value floor;
6. pushes the best move on a fresh board;
7. enumerates every legal opponent capture back onto the destination square;
8. compares the independently derived fact with the stored candidate and rendered claim.

The packet is generated from stored Stockfish evidence but does not rerun or second-guess Stockfish.

## Rejected candidates

- **Plan/Mastery promotion:** rejected because there is no canonical skill, independent opportunity recall packet or prospective transfer evidence.
- **Promote from 1,607 positive passes alone:** rejected because the Caption bar also requires true negatives and adversarial cases.
- **Use `cp_loss` as semantic truth:** rejected because it measures consequence, not the reason.
- **Call every undefended pawn a free piece:** rejected; the current exact contract starts at knight value.
- **Create a second detector or caption template:** rejected because the canonical proof and centralized renderer already exist.
