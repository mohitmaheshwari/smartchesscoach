# Forced-Mate Exact Caption Promotion — Data Lock

**Date:** 2026-09-05
**Status:** LOCKED before runtime code
**Decision:** `tactic:forced_mate_exact` may reach Caption only for reproducible evidence whose legal stored continuation ends in checkmate for the player. Prompt, Plan, Mastery, and the word `forced` remain unauthorized.

## Decision locked

Promote the proof family only if mate-in-one and longer-line captions independently clear the existing Caption precision bar, every reproducible stored candidate passes an independent legal replay, all controls abstain, and the three currently unreproducible legacy admissions remain fail-closed.

## Read-only production measurement

`backend/scripts/measure_forced_mate_caption_promotion.py` scanned both stored puzzle pools inside the production backend container. It ran no engine or LLM and performed no database write.

| Population | Count |
|---|---:|
| Documents scanned | 53,861 |
| Stored `tactic:forced_mate_exact` candidates | 264 |
| Distinct candidate source keys | 241 |
| Independently exact candidates | 261 |
| Mate in one | 97 |
| Longer line | 164 |
| Candidate rows missing reproducible consequence | 3 |
| Stored fact mismatches among reproducible rows | 0 |

The 261 reproducible cases cover both pools: 22 `community_puzzles` and 239 `community_training_positions`. By subtype and pool:

| Subtype | Community puzzles | Training positions | Distinct sources |
|---|---:|---:|---:|
| Mate in one | 12 | 85 | 86 |
| Longer line | 10 | 154 | 153 |

Stored mate lengths are deliberately narrow: 97 at one ply, 84 at three plies, and 80 at five plies. The existing data therefore supports a first-move-plus-finish caption without presenting a long memorized variation.

The wider 53,861-row corpus supplies natural negatives:

| Independent outcome | Count |
|---|---:|
| Legal line does not end in checkmate | 46,527 |
| Insufficient stored consequence | 4,684 |
| Illegal or incomplete line | 1,509 |
| Missing/invalid consequence | 307 |
| Player already played the best move | 296 |
| Missing/invalid played move | 248 |

## Positive packet lock

The packet contains 50 positives from 50 distinct source keys:

- 25 mate-in-one cases;
- 25 longer-line cases;
- at least five cases from each stored pool in each subtype;
- all observed mate lengths of one, three, and five plies.

Twenty-five perfect cases per visible subtype produce an 86.68% 95% Wilson precision lower bound, above the already-locked 85% Caption bar. The combined 50/50 bound is 92.87%. A pooled-only score is rejected because easy mate-in-one wording cannot subsidize a wrong longer-line claim.

## Negative packet lock

The packet contains five distinct-source controls from each of ten independently graded strata:

1. legal stored line that does not end in mate;
2. illegal or incomplete stored line;
3. consequence below 100cp;
4. player already chose the best move;
5. missing or invalid played move;
6. missing or invalid consequence;
7. an exact line truncated before the mating move;
8. an exact line extended after checkmate;
9. an exact case with a different legal leading move while retaining the old continuation;
10. an exact case whose final mating move is replaced by a legal non-mating move.

The first six strata have measured natural supply. The final four are deterministic mutations of distinct locked positives and attack the precise assumptions that a loose marker scan could miss. Five per stratum is an adversarial coverage count, not a precision estimate; every one must abstain, and the full reproducible candidate population is checked separately.

The live corpus added 21 documents between the initial lock and the final packet run. The final aggregate rerun scanned 53,882 documents; the forced-mate candidate counts remained exactly 264 stored, 261 reproducible, and three fail-closed. No case-level production record was exported or committed. The checked-in manifest contains aggregates and the deterministic selection fingerprint only.

## Independent adjudication contract

Promotion gold must not import or call the canonical missed-mate detector, forced-mate proof builder, stored-line verifier, admission verdict, stored quality verdict, engine, or LLM. It independently:

1. parses the FEN, played move, best move, and continuation;
2. requires played and best moves to be distinct legal moves;
3. requires a finite nonnegative stored consequence of at least 100cp;
4. normalizes continuations that include or omit the best move;
5. replays every move legally and rejects truncation, illegal moves, or moves after checkmate;
6. requires the terminal board to be checkmate delivered by the original player side;
7. records the first move, final mating move, mating piece and square, checked king square, terminal legal-reply count, and full replay identity;
8. compares `mate_ply` and `replayed_uci` with the stored verifier facts.

This proves the displayed continuation. It does **not** prove that every defensive branch loses. Consequently V1 must not display `forced`, `unavoidable`, `only move`, or `mate in N` for longer lines.

## The three unreproducible legacy admissions

Three `community_puzzles` rows have a stored forced-mate quality ID and matching verifier facts but no top-level `cp_loss`. Their historical verdict fingerprint proves that some prior calculation occurred; it does not expose the missing value for independent re-adjudication.

They are excluded from the positive denominator and may not inherit Caption authorization. After integration, the normal version-aware reconciliation must either recover the source move and its consequence from `game_analyses` or quarantine the row. No value is guessed and no production update is authorized by this packet.

## Rejected candidates

- **Promote all 264 stored rows:** rejected because three lack reproducible consequence evidence.
- **Use one pooled 50-case score:** rejected because mate-in-one and longer-line wording are different claims.
- **Say “forced mate” from one principal variation:** rejected because legal replay establishes one continuation, not every defence.
- **Display `mate in N` from line length:** rejected because stored PV length is not an all-defence mate-distance proof.
- **Run Stockfish in the player request path:** rejected; stored analysis remains the truth source and runtime explanation remains deterministic.
- **Create a new mate detector or caption path:** rejected; every required authority already exists.

## Promotion gate

Promotion requires 25/25 mate-in-one truths, 25/25 longer-line truths, 50/50 correct abstentions, both subtype Wilson lower bounds at or above 85%, all 261 reproducible candidates independently exact, zero stored-fact mismatches, zero critical semantic errors, and explicit fail-closed handling of the three unreproducible rows. Any failure keeps the family Shadow.
