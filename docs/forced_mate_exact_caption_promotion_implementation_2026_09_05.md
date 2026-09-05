# Forced-Mate Exact Caption Promotion — Implementation Record

**Date:** 2026-09-05
**Quality ID:** tactic:forced_mate_exact
**Authorized surface:** Caption only
**Status:** implemented locally on codex/complete-coaching-system-spec-v1; not pushed or deployed

## Outcome

ChessGuru may now explain a missed mating continuation after a verified puzzle attempt when two deterministic paths agree that:

1. the played and best moves are different legal moves;
2. the stored consequence is finite, nonnegative, and at least 100cp;
3. the complete stored continuation replays legally;
4. its terminal board is checkmate delivered by the player side; and
5. the first move, final mating move, mating piece and square, checked king square, zero legal replies, mate ply, and replayed move identity all match independent adjudication.

Mate-in-one captions name the mating piece, square, checked king, and absence of replies. Longer captions name the first move and the verified finish. They deliberately say “verified continuation,” not “forced,” “unavoidable,” “only move,” or “mate in N,” because one stored principal variation does not prove every defensive branch.

## Runtime changes

- forced_mate_puzzle_proof.py is versioned to v3, requires the actual played move, rejects played-best equality, and emits only independently reconstructible terminal facts.
- verified_puzzle_builder.py supplies the played move to that proof contract.
- verified_puzzle_feedback.py remains the sole verified-puzzle renderer and uses the new fact set for concrete, square-led explanations.
- detector_quality.py promotes only this quality ID from Shadow to Caption. Prompt, Plan, and Mastery remain unauthorized.
- The explicit Caption allow-list test now names this evidence packet deliberately.

No new detector, caption pipeline, concept identity, focus store, learner skill, grader, or mastery projection was created.

## Production evidence

The read-only audit scanned 53,882 current documents across both stored puzzle pools through a localhost SSH tunnel. Audit code ran locally; no repository source was installed in the production container and no database write occurred.

| Gate | Result |
|---|---:|
| Mate-in-one positives | 25/25 |
| Longer-line positives | 25/25 |
| Mate-in-one Wilson lower bound | 86.68% |
| Longer-line Wilson lower bound | 86.68% |
| Combined Wilson lower bound | 92.87% |
| Natural/adversarial controls | 50/50 abstained |
| Reproducible stored candidates | 261/261 matched |
| Stored fact mismatches | 0 |
| Legacy rows missing consequence | 3/3 abstained |
| Critical errors | 0 |

The checked-in evidence is aggregate-only. It contains no production FEN, move, source key, case record, user ID, game ID, account detail, or credential. The deterministic selection fingerprint is 628ce54facc3378f5087e3a53f59b73bad54956c73c186211faf2b8902cbbd41.

Aggregate manifest: backend/data/detector_gold/forced_mate_exact_caption_promotion_v1.json

Manifest SHA-256: 1e1bbe7fc3cc23f4fafa3503f3c65d4cde9784b73bafd4e290834da167db7da9

## Three fail-closed legacy rows

Three stored community_puzzles admissions have the quality ID and verifier facts but no exposed cp_loss. They cannot be independently re-authorized from the stored puzzle row and are not included in the positive denominator.

They remain stale/quarantined after the proof-version and authorization change until the normal reconciliation path recovers the original source move from game_analyses and rebuilds the verdict. No consequence is guessed and this implementation performs no backfill or production mutation.

## Verification

- Final aggregate production packet: PASS; exit code 0; zero case records exported.
- Focused proof/promotion suite: 14 passed.
- Direct admission/rendering/training regression suite: 131 passed.
- Full proof/authorization/Phase-2 compatibility family: 197 passed.
- Python syntax compilation: passed for every changed Python file.
- git diff --check: passed; line-ending warnings only.
- Voice audit: clean. The text uses pieces and squares, avoids unexplained jargon and centipawn language, ends with a reusable scan habit, and extends the existing verified-puzzle renderer rather than adding a new coaching path.

The repository-mandated live HTTP tests/test_all_flows.py was attempted against its safe default http://localhost:8001; no backend was listening, so it stopped on the first connection before a product assertion. It was not redirected to production because the suite contains mutation-capable flows.

One wider run that deliberately included test_caption_pipeline_boundary.py produced six unrelated failures in forced-recapture, coach-extra, and Socratic question/hint expectations. None of those failing assertions exercises a changed forced-mate path. The same run's only in-scope failure was the explicit Caption allow-list, which was updated with this evidence reference; all in-scope suites then passed.

## Operational boundary

This worktree made no production write, backfill, deployment, merge, push, or rollout change. Existing v2 forced-mate admissions become structurally stale under v3 and require the normal dry-run, inspected, version-aware reconciliation before any player can receive the new caption. The three incomplete rows must remain excluded unless their original analysis consequence is recovered exactly.
