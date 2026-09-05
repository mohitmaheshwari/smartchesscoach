# Forced-Mate Exact Caption Promotion — Implementation Record

**Date:** 2026-09-05
**Quality ID:** tactic:forced_mate_exact
**Authorized surface:** Caption only
**Status:** implemented locally on codex/complete-coaching-system-spec-v1; targeted production re-admission complete; application code not pushed or deployed

## Outcome

ChessGuru may now explain a missed mating continuation after a verified puzzle attempt when two deterministic paths agree that:

1. the played and best moves are different legal moves;
2. the stored consequence is finite, nonnegative, and at least 100cp;
3. the complete stored continuation replays legally;
4. its terminal board is checkmate delivered by the player side; and
5. the first move, final mating move, mating piece and square, checked king square, zero legal replies, mate ply, and replayed move identity all match independent adjudication.

Mate-in-one captions say that the SAN move gives checkmate and name the checked king's square and absence of replies; SAN already carries the piece, destination, and mate marker. Longer captions show the complete stored line, name the terminal king fact, and explicitly say the opponent can defend differently. They do not say “forced,” “unavoidable,” “only move,” or “mate in N,” because one stored principal variation does not prove every defensive branch.

## Runtime changes

- forced_mate_puzzle_proof.py is versioned to v3, requires the actual played move, rejects played-best equality, and emits only independently reconstructible terminal facts.
- verified_puzzle_builder.py supplies the played move to that proof contract.
- verified_puzzle_feedback.py remains the sole verified-puzzle renderer and uses the new fact set for concrete mate-in-one wording or a complete longer line without implying forcedness.
- detector_quality.py promotes only this quality ID from Shadow to Caption. Prompt, Plan, and Mastery remain unauthorized.
- The explicit Caption allow-list test now names this evidence packet deliberately.

No new detector, caption pipeline, concept identity, focus store, learner skill, grader, or mastery projection was created.

## Production evidence

The current read-only audit scanned 54,400 documents across both stored puzzle pools through a localhost SSH tunnel. Audit code ran locally; no repository source was installed in the production container.

| Gate | Result |
|---|---:|
| Mate-in-one positives | 25/25 |
| Longer-line positives | 25/25 |
| Mate-in-one Wilson lower bound | 86.68% |
| Longer-line Wilson lower bound | 86.68% |
| Combined Wilson lower bound | 92.87% |
| Natural/adversarial controls | 50/50 abstained |
| Reproducible stored candidates | 264/264 matched |
| Stored fact mismatches | 0 |
| Rows not reproducible from puzzle document alone | 3/3 abstained |
| Critical errors | 0 |

The checked-in evidence is aggregate-only. It contains no production FEN, move, source key, case record, user ID, game ID, account detail, or credential. The current deterministic selection fingerprint is 7df797a67df10c1a94d29c80601b0a6b67842d0ee397fd7b8cfbbfdb899aa18b.

Aggregate manifest: backend/data/detector_gold/forced_mate_exact_caption_promotion_v1.json

Manifest SHA-256: d690ea6763ddb78e5664ce98032addd83d99a2e3375b5f8094ed55c91fbbc5a2

## Puzzle-document abstentions and source recovery

Three stored rows have the quality ID and verifier facts but do not expose all
evidence required by the puzzle-document-only audit. That audit correctly
excludes them; it does not claim the source consequence is absent.

The targeted re-admission recovered the original move evidence from
`game_analyses`, rebuilt all 267 stored candidates, independently validated the
actual captions and mating facts across 239 distinct FENs, and found zero
violations or cross-pool conflicts. The apply updated 27 `community_puzzles`
rows and 240 `community_training_positions` rows. Post-write readback confirmed
all 267 carry broad status, Caption grade, both verified reason codes, and the
v3 detector/verifier versions.

## Verification

- Final aggregate production packet: PASS; exit code 0; zero case records exported.
- Targeted production dry run: 267/267 captions and facts validated; zero violations.
- Targeted production apply: 267 rows updated; post-write v3 Caption readback 267/267.
- Focused proof/promotion suite: 14 passed.
- Direct admission/rendering/training regression suite: 131 passed.
- Full proof/authorization/Phase-2 compatibility family: 197 passed.
- Python syntax compilation: passed for every changed Python file.
- git diff --check: passed; line-ending warnings only.
- Voice audit: clean. The text uses pieces and squares, avoids unexplained jargon and centipawn language, ends with a reusable scan habit, and extends the existing verified-puzzle renderer rather than adding a new coaching path.

The repository-mandated live HTTP tests/test_all_flows.py was attempted against its safe default http://localhost:8001; no backend was listening, so it stopped on the first connection before a product assertion. It was not redirected to production because the suite contains mutation-capable flows.

One wider run that deliberately included test_caption_pipeline_boundary.py produced six unrelated failures in forced-recapture, coach-extra, and Socratic question/hint expectations. None of those failing assertions exercises a changed forced-mate path. The same run's only in-scope failure was the explicit Caption allow-list, which was updated with this evidence reference; all in-scope suites then passed.

## Operational boundary

The targeted database re-admission is complete. No application deployment,
merge, push, cohort enrollment, or rollout change was made. At verification
time the running production container still loaded
`forced_mate_puzzle_proof.v2`, Shadow authorization, and
`personal_teaching_profile.v1`; therefore the updated rows remain unavailable
to players until the reviewed application branch is deployed. Phase 8 cohort
enrollment remains a product decision outside this implementation.
