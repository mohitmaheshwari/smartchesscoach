# Aligned With Stored Payoff Caption Promotion — Data Lock

**Date:** 2026-09-02
**Status:** LOCKED before runtime code
**Decision:** `tactic:aligned_with_stored_payoff` may reach Caption only if pin and skewer independently pass. Prompt, Plan, and Mastery remain unauthorized.

## Measured stored population

The read-only production-container census used only stored FEN, moves, Stockfish consequence, continuation, and admission evidence. No engine, LLM, or database write ran.

| Population | Count |
|---|---:|
| Documents scanned across both pools | 52,085 |
| Stored aligned candidates | 436 |
| Distinct stored source fingerprints | 363 |
| Independent exact pins | 285 |
| Independent exact skewers | 151 |
| Direct alignments | 374 |
| Discovered alignments | 62 |
| Stored fact mismatches | 0 |

Pool supply is 104 `community_puzzles` and 332 `community_training_positions`. Distinct-source supply is 233 pins and 130 skewers. Pin supply includes 197 direct and 36 discovered sources; skewer supply includes 116 direct and 14 discovered sources. Both kinds occur with bishop, rook, and queen attackers.

The initial audit incorrectly required the best move to land on the attacking slider. That rejected all 62 discovered alignments. Comparing the independent and canonical ray keys showed the geometry itself matched; the attacker simply sat elsewhere. The corrected contract is “the best move creates a new alignment,” either directly or by clearing a line. This correction changes narration, not detection.

## Positive packet lock

The packet contains exactly 50 positives from 50 distinct source keys:

- 25 independently exact pins;
- 25 independently exact skewers;
- both stored pools;
- bishop, rook, and queen attackers;
- direct and discovered creation in each semantic family.

At 25/25, each subtype's 95% Wilson precision lower bound is 86.68%, above the locked 85% Caption bar. The combined 50/50 bound is 92.87%. A proportional sample was rejected because it would let the larger pin population subsidize confidence in skewer wording.

## Negative packet lock

Five distinct-source controls are selected from each of ten measured failure modes, for 50 total. Original-piece identity is tracked during replay so a target moving, being replaced, or never being captured cannot collapse into the same vague outcome:

| Failure mode | Full-pool supply |
|---|---:|
| No newly created alignment | 41,305 |
| Incomplete or illegal stored line | 609 |
| Less than pawn-value net gain | 4,666 |
| Original attacker leaves before payoff | 1,963 |
| Original pin front piece escapes | 350 |
| Original pin front piece is not captured | 1,423 |
| Original skewer front piece is not cleared first | 280 |
| Original skewer rear piece escapes | 69 |
| Original skewer rear piece is not captured | 443 |
| Stored consequence below 100cp | 44 |

## Independent adjudication

Promotion gold must not import or call `_aligned_pieces_evidence`, `_ray_alignments`, `build_aligned_tactic_proof`, `replay_stored_line`, or the stored verifier verdict. It independently:

1. parses the legal FEN, played move, best move, and stored continuation;
2. reconstructs every bishop/rook/queen ray before and after the best move;
3. accepts only a newly created two-opponent-blocker line with unequal front/rear values;
4. labels `pin` only when the front piece is less valuable than the rear piece, and `skewer` only when the front piece is more valuable;
5. records whether creation is direct or discovered and names all three pieces and squares from the board;
6. replays the complete stored line legally;
7. for a pin, requires the original attacker to capture the original front piece before that front piece moves;
8. for a skewer, requires the original front piece to move first and the original attacker then to capture the original rear piece;
9. requires at least one pawn of net material gain and at least 100cp stored consequence.

## Rejected alternatives

- **One pooled 50-case precision number:** rejected because pin and skewer are different visible claims.
- **Only direct alignments:** rejected because 62 verified stored candidates are discovered alignments and need different wording.
- **Promote the generic shape detectors:** rejected because their independent semantic precision remains unmeasured.
- **Say “wins material” or “must move”:** rejected because one stored line is not an all-defence proof.
- **Create separate new quality IDs:** rejected because the canonical proof and admission family already exists; subtype confidence is enforced inside one packet.
- **Use stored verifier facts as gold:** rejected because promotion requires a fresh calculation path.

## Lock

Promotion requires 25/25 true pins, 25/25 true skewers, 50/50 correct abstentions, both subtype Wilson bounds at or above 85%, all stored candidates independently exact, zero stored-fact mismatches, and zero critical semantic errors. Any failure keeps the family Shadow.
