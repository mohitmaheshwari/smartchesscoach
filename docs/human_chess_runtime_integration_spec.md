# Human Chess Runtime Integration — Architecture Spec

**Status:** LOCKED for implementation on 2026-09-01
**Scope:** `docs/human_chess_runtime_integration_scope.md`
**Base:** `origin/working-code` at `daa65167`

## Evidence-locked decisions

| Decision | Locked value | Evidence |
|---|---|---|
| Preferred human-policy provider | Otter 0.2.0 with verified history | 55.7% held-out top-1, 91.6% top-5, NLL 1.351 across 3,257 moves; won every rating band |
| No-history fallback | Maia-2 0.11.0 Rapid | 51.8% top-1 and complete coverage; materially beat the 10.5% frequency baseline |
| Clock-conditioned diagnosis | Rejected | Otter history+clock was worse than history-only on top-1, NLL and Brier |
| Endgame truth | Complete local Fathom/Syzygy legal-move partition | Exact WDL truth; incomplete or unsupported probes abstain |
| Public sound-and-findable band | Not authorized | 25cp+same-WDL passed engine research but still requires blinded coach review |
| Safe V1 human move choice | Rank only candidates already accepted by the existing verified safety boundary; exact-evaluation ties may be preferred | Human probability cannot widen the safety set |
| Puzzle difficulty | Shadow only | Existing attempts have zero known assistance and zero attempt-time ratings |

No new numeric cutoff is introduced by this integration.

## Truth hierarchy

```text
Fathom/Syzygy exact WDL (covered endings)
              or
stored/live Stockfish evidence (all other positions)
                       ↓
detector/content authorization and legal-board verifier
                       ↓
Otter/Maia likelihood may rank the already-safe set
                       ↓
central MoveTeachingDecision / existing opponent / existing puzzle attempt
```

## Canonical contracts

`ExactEndgameEvidence` contains the normalized FEN, WDL, optional DTZ, complete legal move partition, result-preserving moves, provider/version, table hashes or bundle identity, input fingerprint and rejection reason. Construction fails unless every legal move appears exactly once in the partition.

`HumanPolicyEvidence` contains provider/version, input fingerprint, legal move probabilities, entropy, played-move rank, history/clock modes, latency, warnings and rejection reason. Otter history-only inference uses the measured controlled-neutral clock value `0.5`; observed player clock is excluded and cannot support a causal “you rushed” claim. Maia probabilities use the same unrounded package-internal inference path as the locked research. The evidence cannot contain correctness, weakness, mastery, intention or psychological labels.

Both contracts serialize to plain dictionaries for Mongo. Consumers validate schema and provenance before use.

## Integration points

1. `analysis_worker.py` and V5 lazy regeneration derive eligible exact-endgame evidence and optional human-policy evidence once, then store it with the analysis/review record.
2. `caption_pipeline.build_move_teaching_decision` accepts the typed evidence as optional inputs. Exact endgame evidence may enrich the verified board explanation. Human-policy evidence remains metadata unless a separately authorized use consumes it.
3. `game_review_event_adapter` projects exact endgame evidence through the existing event/cause consistency contract. It does not create a parallel endgame event graph.
4. `CoachOpponent` asks the human-policy selector to rank only candidates returned by the strong safety analysis. Any error, missing model or unsafe output returns the existing guarded choice.
5. Puzzle extraction/training stores shadow findability and verified distractor candidates. Public difficulty, answer admission and ordering remain unchanged.
6. Endgame lesson grading accepts every exact result-preserving move, then applies an explicitly named teaching constraint only when the lesson requires one.

## Flags and fallback

- `EXACT_ENDGAME_ENGINE_ENABLED=false`
- `EXACT_ENDGAME_REVIEW_ENABLED=false`
- `HUMAN_POLICY_EVIDENCE_ENABLED=false`
- `PWC_HUMAN_POLICY_OPPONENT_ENABLED=false`
- `PUZZLE_HUMAN_DIFFICULTY_SHADOW_ENABLED=false`
- `HUMAN_CHESS_ANALYSIS_ENRICHMENT_ENABLED=false`

Mandatory provenance when a corresponding flag is enabled:

- `FATHOM_BINARY_PATH`, `FATHOM_BINARY_SHA256`
- `SYZYGY_TABLEBASE_PATH`, `SYZYGY_TABLEBASE_BUNDLE_ID`, `SYZYGY_TABLEBASE_MANIFEST_SHA256`, `SYZYGY_MAX_MEN`
- `OTTER_MODEL_PATH` must point to the audited `otter-0.2.0-eb8dc98b.safetensors`
- `MAIA2_MODEL_PATH` must point to the audited `rapid_model.pt`

The runtime computes the model/file hashes itself and requires the pinned package/model family. A label or configured expected hash without a byte-for-byte match is insufficient.

Exact-endgame visibility also requires the existing Personalized Review and Quality V2 gates. Every failure falls back to the current merged behavior. Rollback is a flag change; no mastery or curriculum state is rewritten.

## Verification

- Contract and adversarial unit tests for both evidence types.
- Fathom fixture tests plus every committed tablebase snapshot position.
- Review tests proving WDL wording, alternative acceptance, provenance and legacy parity.
- Provider tests proving legal normalization, history preference, Maia fallback, missing-model fallback and no clock causal claim.
- PWC tests proving a model cannot widen the safe set and exceptions keep the guarded move.
- Puzzle tests proving shadow fields never affect answer, order or visible difficulty.
- Existing Quality V2, caption, PWC, puzzle, backend core and frontend suites.
