# Deterministic Teaching Opportunities — Implementation Record

Date: 2026-09-14
Branch: `codex/deterministic-whole-game-teaching-review-v1`
Status: implemented in Shadow; independent development review pending; no player-facing authorization

## Outcome

The approved four-family slice now turns stored, legally replayable game branches into typed teaching comparisons:

1. `forced_mate_story`
2. `multi_move_material_accounting`
3. `queen_safety_or_greedy_capture`
4. `unpunished_opponent_opportunity`

The implementation does not use an LLM, run an engine, read production, open the sealed holdout, or make a production write. It reuses the existing canonical stored-line verifier for legal replay and settled material truth. All four quality IDs remain independently registered at Shadow grade.

## What was wired

- `caption_facts.py` owns the typed causal opportunity and exact consequence identity.
- `stored_line_verifier.py` remains the single owner of legal replay and settled material payoff.
- `caption_pipeline.py` renders compact, position-specific comparison copy from typed facts only.
- `game_decryption_v5_service.py` opts batch Game Review into Shadow collection and stores the whole-game aggregate.
- `game_review_planner.py` validates, deduplicates, and summarizes the Shadow candidates. Consecutive descriptions of one mating episode become one story.
- `game_review_event_adapter.py` and `routes/coach.py` both strip the Shadow field from public output.
- `detector_quality.py` registers four separate Shadow identities; no family borrows another family's grade.

Play with Coach and other latency-sensitive callers do not run this extra settlement work. Collection requires the explicit `collect_teaching_opportunity_shadow=True` batch-review input.

## Proof boundaries

Every retained comparison must have:

- complete legal replay for both played and stronger branches;
- explicit player/opponent identity;
- an exact consequence piece, square, branch and ply when material is claimed;
- settled material scores from the canonical verifier rather than the first capture;
- matching proof authority and proof version;
- exact fact, cause and source-evidence SHA-256 fingerprints;
- family-specific invariants, including terminal mate for mate stories, at least two captures for multi-move material, and a player-owned queen consequence for queen safety.

Known false-claim classes are locked in tests: delayed recapture, fork beyond the stored line, quiet check before a later capture, player/opponent reversal, equal trade presented as a win, incomplete or illegal continuation, counterfactual history phrased as real history, and repeated captions for one mating episode.

## Coaching-language boundary

Visible development copy names what happened on the board and supplies one short memory action. It does not expose centipawns, detector names, schema terms or generic rules such as “never trade queens.” Examples include:

- “Ne2 lets Bxd3 take your queen on d3.”
- “After the first capture, count every capture back and check.”
- “They could have played Bc3, starting a line that takes your rook on h8.”

These are review claims, not yet player claims. Copy is still subject to independent semantic review.

## Frozen development measurement

The offline 100-game measurement reconstructed 3,775 stored positions and produced 250 deduplicated Shadow candidates across 75 games and all 34 anonymized players:

| Family | Raw | Deduplicated |
|---|---:|---:|
| Forced-mate story | 40 | 33 |
| Multi-move material accounting | 165 | 165 |
| Queen safety or greedy capture | 20 | 20 |
| Unpunished opponent opportunity | 32 | 32 |

Seven adjacent mate descriptions were merged into their continuous episodes. These counts measure incidence, not correctness. A high count does not grant authorization.

Artifacts:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `backend/data/corpus_snapshots/deterministic_teaching_opportunity_family_measurement_v3_2026-09-14.json` | 773,602 | `94118ca95446a692e7aff7737c3149c74e26f03ccd4fc568d2b22273026a459e` |
| `backend/data/detector_gold/deterministic_teaching_opportunity_blinded_development_review_v1.json` | 229,812 | `135d764c3a3253c299c8bfed941ef142a71de19a25cd17c598586e09981318f8` |
| `backend/data/detector_gold/deterministic_teaching_opportunity_blinded_development_answer_key_v1.json` | 101,710 | `0caff14cc4c9ae247342bdfc396d311b7bea4d395461c4c55c9099a980cb3208` |

The public review packet contains FENs, side-to-move context, the played and stronger moves, replay lines, and the exact proposed coaching copy. It contains no email, user ID, game ID, source-game alias, detector family, quality ID, proof version, centipawn loss, answer or internal fingerprint. The answer key is a separate file and must not be shown to the reviewer.

## Verification

Final combined focused matrix:

```text
191 passed, 34 skipped
```

This covers the four families, packet blinding and scoring, stored-line adversarial settlement, detector authorization, caption-pipeline boundaries, V5 review generation, planner behavior, adapter/API Shadow stripping, candidate-caption boundaries and interactive/phased V5 regressions.

All changed Python modules and scripts compile. `git diff --check` passes, with Windows line-ending warnings only.

`python tests/test_all_flows.py` was also attempted. It stopped before its first assertion because no HTTP backend was running at the configured URL (`httpx.ConnectError: All connection attempts failed`). This is inconclusive and is not recorded as either a pass or a product regression.

## Independent review and promotion rule

Give an independent reviewer only:

`backend/data/detector_gold/deterministic_teaching_opportunity_blinded_development_review_v1.json`

The reviewer must assess every case once, without reading detector code or the answer key. The local scorer rejects incomplete, duplicate, unbound or non-independent reviews. This development packet may reveal defects but can never promote a detector.

After defects are fixed and the implementation is frozen, build fresh non-holdout evidence. Each family must independently have at least 50 reviewed visible claims, at least 95% semantic precision, a Wilson 95% lower bound of at least 85%, and zero critical false chess claims. The sealed holdout remains closed until those decisions are frozen.

The current development packet already shows that three families do not have 50 cases (`33`, `20`, `32`). They require fresh evidence; their samples cannot be pooled with the 165 multi-move cases to pass a gate.

## Explicitly not done

- no Caption or Plan promotion;
- no public Game Review card or replay button for these four families;
- no ranking policy among overlapping families;
- no regeneration, migration or backfill;
- no database access or write;
- no engine or model call;
- no holdout opening;
- no push or deployment.

Player-facing projection and ranking are deliberately deferred until at least one family earns Caption authorization. Wiring an ungraded Shadow candidate into the existing comparison card would violate the locked safety boundary.
