# Stage 1 validation — branch-owned mate truth

Date: 2026-09-03  
Base: `fbe6514c2e222b84c523d63bbcec330387d63d2b`  
Branch: `codex/hidden-opportunities-chess-gold-v1`

## Verdict

Stage 1 passes its no-leak acceptance bar on the locked evidence.

The two audited captions that reversed the direction of mate are repaired in the central caption pipeline. Mate evidence now belongs separately to the played branch and the best branch, the renderer uses an explicit mover-relative transition, and the final rendered sentence is checked by an independent replay before it can ship.

This is not a claim that all caption teaching is complete. It is the truth-boundary repair that makes later chess-reasoning work safe to expose.

## What changed

- `caption_facts.py` builds separate played/best mate results from stored legal continuations and stored mate-sentinel evaluations.
- `caption_rules.py` and `R01_mate.json` render `delivered`, `preserved`, `missed`, `allowed`, or `already_lost`; they no longer infer direction from one merged mate flag.
- `caption_claim_verifier.py` verifies the structured transition.
- `narrator_claim_verifier.py` independently reconstructs both branches and rejects contradictory mate language.
- `caption_pipeline.py` has one final fail-closed boundary after all caption enrichment, so later text cannot bypass verification.
- The strict sacrifice verifier now treats a legal immediate recapture as proof and never mistakes a missing continuation for proof that a piece survived.

## The two repaired failures

Before:

- `Kg2 allows mate in 2.`
- `fxg3 allows mate in 2.`

After:

- `Kg2 misses mate in 2. f5+ was the move. Before moving, check every forcing move: checks, captures, and threats.`
- `fxg3 misses mate in 2. Qxf6+ was the move. Before moving, check every forcing move: checks, captures, and threats.`

Both now resolve to `missed_forced_mate` and pass final independent verification.

## Locked 80-game replay

The replay used 80 complete anonymized games, 5,931 plies, and 467 meaningful decisions. It used stored evidence only: no Stockfish rerun, database access, network access, or production write.

| Measure | Result |
| --- | ---: |
| Captions produced | 463 / 467 (99.14%) |
| Rows with no caption by design | 4 |
| Rows quarantined by verifier outage | 0 |
| Machine-falsifiable exact claims checked | 25 |
| Proven exact failures | **0** |
| Render errors | **0** |
| WHY failures among 364 obligations | 18 (4.95%) |

The four rows without captions are low-loss moves (30–40 cp) already represented as an empty `R_FALLBACK`; they were not rejected by the new truth boundary.

## Tests

- Focused caption, stored-line, adapter, puzzle-proof, and Stage 4 suites: **68 passed, 0 failed**.
- New adversarial branch-direction and verifier cases: **9 passed, 0 failed**.
- Caption boundary suite on feature tree: **79 passed, 6 failed**.
- Same suite on untouched base: **79 passed, 6 failed**.
- Stage 1 regression delta: **0**.

The six boundary failures are inherited and reproduced exactly on the clean base. The repository's `test_all_flows.py` was also attempted, but it is a live-HTTP script and stopped because no backend server was running in the isolated worktree; that result is inconclusive.

## Locked 100-position no-regression replay

The standalone validator replayed all 200 stored branches legally and reproduced the reviewed runtime baseline exactly: 47 non-null legacy analyzer outputs, one known `UnboundLocalError`, and zero output drift.

That known crash is deliberately not disguised as a Stage 1 success. Stage 1 changed the caption truth boundary, not the legacy Hidden Opportunities analyzer. Fixing the crash and replacing best-branch-only narration with differential causal proofs belongs to the next implementation stage.

## Release boundary

Nothing was deployed, regenerated, or written to production. A later release must bump the caption content version and regenerate or lazily refresh stored reviews only after the next integration audit is green.

Machine-readable evidence: `backend/data/corpus_snapshots/mate_branch_truth_stage1_validation_v1_2026-09-03.json`.
