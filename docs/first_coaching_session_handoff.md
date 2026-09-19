# Onboarding extension — first repair handoff

Updated: 2026-09-19. Worktree: `_first_coaching_session`. Branch: `codex/first-coaching-session-v1`. Original base: `8c6685c1`. Commit parent at handoff: `0445b7ca258197b57969e79e2b52a3178ec97b50` (Claude's fork-question work, preserved unchanged).

## Actual status

Existing diagnostic interaction, feedback persistence and conservative assessment wording are implemented locally and packaged in the commit containing this handoff. The approved adaptive observe → teach → changed-position-check product is NOT complete, enabled or deployed. Nothing has been pushed, migrated or enrolled by this work. The root workspace's unrelated changes were not touched. Mohit clarified and approved puzzle-led discovery before teaching on 2026-09-19; a fixed starter lesson is not the design.

Pre-commit rerun on parent `0445b7ca`: 79 targeted backend tests passed (including Claude's 20 fork-question tests); 2 focused frontend suites / 24 tests passed. This commit does not incorporate Claude's earlier commit as newly authored work; it remains a separate ancestor. Review/cherry-pick the onboarding commit explicitly rather than copying whole files or merging every branch ancestor without inspection. Full first-session release gates below remain open.

Changed runtime files: `frontend/src/pages/DiagnosticPuzzles.jsx`, `backend/routes/diagnostic.py`, `backend/services/diagnostic_service.py`.

- Feedback and the played board remain until explicit continuation, including the final answer.
- Intermediate `step_verdict` and legacy `is_correct` responses render correctly instead of defaulting to failure.
- Next-position numbering follows the API; intermediate steps do not count as completed puzzles.
- Same-render duplicate move callbacks cannot double-submit locally.
- A failed/ambiguous response preserves the board and offers a server-state reload; it never automatically resends a possibly saved move or calls it wrong.
- An unsuccessful early finish no longer silently navigates away.

Additional repairs:

- New frontend negotiates `explicit_v1` from the start response, submits the session start identity and exact starting FEN. Older servers still use the previous client behavior.
- Backend saves the attempted board, feedback receipt and advancement in one Mongo document update. Compare-and-set binds the session, previous attempts, current step and absence of unread feedback. Identical submissions before acknowledgement replay the same response; conflicting/stale ones are rejected.
- `/diagnostic/start` restores unread feedback, including final feedback and cases where background analysis has since superseded the diagnostic. `/diagnostic/feedback/continue` acknowledges it; repeats of the latest acknowledgement are idempotent. Legacy and V2 grading paths are covered.
- New-session final focus projection happens on acknowledgement, not before the final answer is durable. Acknowledgement and checkpoints project provisional focus without incrementing weakness occurrences. Existing legacy callers keep their prior default; the old helper's repeat-safe comment was inaccurate because it increments a counter. A delayed final acknowledgement skips diagnostic focus projection when real-game analysis already supersedes it.
- Removed claims that a capture proves a net material win, that a pool theme proves a fork/pin, or that a good alternative necessarily leaves the player ahead. This is narrower truthful fallback feedback, NOT rich causal teaching. New summary text is provisional; uncalibrated diagnostic rating is no longer displayed on this screen (underlying scoring unchanged).

Unchanged: grading thresholds, acceptance maps, concept-selection staircase, curriculum, import processing, PWC and detector authorizations. No engine/model calls or production operations.

## Verification

- Full frontend suite: 69 suites / 336 tests passed, exit 0 (rerun after persistence changes; focused rerun after summary copy).
- Focused diagnostic and partial-exit tests: 2 suites / 24 tests passed, exit 0 (19 new diagnostic tests).
- Backend receipt/adaptive-start/Home-fallback tests: 30 passed on final rerun, exit 0. Tests use an in-memory Mongo boundary; the HTTP contract test mounts the real router with an overridden authentication dependency. Not a real Mongo concurrency or live-auth proof.
- Existing engine-free diagnostic script: 52 assertions passed, zero failed. One obsolete assertion was corrected: a theme label must not establish a fork explanation by itself.
- Tracked diff whitespace check: clean.
- Ordinary production build (`CI=false`), rerun after 2026-09-19 frontend changes: exit 0, compiled with warnings (existing review-hook dependency, missing dependency source map, and bundle-size warning). Bundle `main.81376e7a.js`.
- Strict production build (`CI=true`): exit 1 on `GameDecryptionV5.jsx:430`, missing `applyCaptionArrows` hook dependency. That file is byte-unchanged against the base; no unrelated review behavior was modified to silence it.
- Existing static onboarding contract test: 2 passed / 1 failed. Its text-order assertion finds the account-restoration `setChessComVerified(true)` before the later link-response guard. Both `Onboarding.jsx` and the test are byte-unchanged against the base. This is not a clean backend-suite result.
- Mandatory `test_all_flows.py` attempted against explicit `http://127.0.0.1:8001`, exit 1: connection refused on first Home request. No live-suite pass, real-browser authenticated E2E or production-latency claim. The first route-test attempt used a Python missing bcrypt; rerunning with the existing backend virtual environment resolved collection without changing dependencies.

## Important remaining work

The feedback receipt protocol is implemented and locally tested; real-Mongo integration and a non-admin browser round trip remain release gates. This is not the complete first-session teaching state machine: hints, assisted retries and changed-position encounters are not integrated.

No richer explanation, hint, demonstration, changed-position pairing, new first-session CTA or early-session finish rule is being passed off as delivered. Full feature remains blocked by content review and teaching-state integration. Existing pool-builder grade maps establish move evaluations, not causal mechanisms or independent transfer.

Local canonical content inventory (not a production or publishability count): `endgame_theory_tree.json` has 20 lessons / 60 positions; all 60 have `idea`, only 3 have `reason_contract`, and none has a `demonstration` field. Absence of that named field does not prove no replay evidence exists elsewhere. Do not assign this fixed endgame curriculum to every new player. The diagnostic pool still needs the separate read-only inventory below.

Voice review: the new UI acknowledges move quality, not inferred understanding; failure messages describe request state rather than chess failure. Existing diagnostic explanation templates remain a non-central coaching path and an explicit future repair, not newly certified teaching.

## Read-only evidence needed next

### Preferred next operator check (2026-09-19)

The implemented `backend/scripts/audit_diagnostic_teaching_readiness.py` supersedes the simple field-count snippet below for readiness decisions. It has no write/apply path and prints only fixed-schema aggregate counts. It calls existing deterministic chess proofs only with `--derive-reasons`; it never runs an engine/model or rebuilds the pool. Database failures return a sanitized error and exit 1, never a fabricated empty-pool report.

From the configured backend environment after reviewing the script:

```bash
python -m scripts.audit_diagnostic_teaching_readiness
python -m scripts.audit_diagnostic_teaching_readiness --derive-reasons --limit 10
```

The second command is a deliberately limited operational probe, NOT a statistical sample or acceptance threshold. Review its cost/errors, then remove `--limit` for the full scan if appropriate. The output names the row limit and collection size; it does not claim a transactional snapshot while the pool is changing. Return the aggregate JSON only. No raw FEN, move, puzzle ID, user ID, email or credential export is requested. Do not deploy the whole branch just to run the audit.

Interpretation: `UNDERSTOOD:pass` means the stored grader accepts the move AND the existing proof supports destination-piece safety; it does not prove understanding or explain the entire puzzle. `MISSING:pass` is possible and important: a safe landing square does not make a good move. Missing grades, duplicate occurrences, unsupported pawn/king reasons and stale/malformed evidence are separate counts. `ready_for_player_exposure` stays false even with full coverage: independent teachability and changed-position pairing are not graded by this audit.

Local example for review: `docs/first_coaching_session_teaching_example.md`. It uses existing test-only adjudicated gold, not production onboarding content. Do not insert this test fixture into the production pool.

Additional verification this turn: combined audit, canonical reason, receipt, adaptive-start and Home-fallback suite **59 passed**, exit 0. Of these, **19** test the new audit/example; no live pool result is claimed. Mandatory all-flows suite reattempted against `http://127.0.0.1:8001`: exit 1 on connection failure at Home, so E2E is still unverified. No frontend changes this turn; prior frontend/build results above were not rerun. No commit, push, deployment or production change.

### Earlier inventory/access notes

Two listening local Mongo connections were found (27017/27018). Both unauthenticated probes returned OperationFailure; a subsequent attempt using the existing repository database configuration was also rejected. No production documents or credentials were printed/exported and no writes occurred. Do not interpret unavailable access as an empty pool.

Claude/operator can run this inside the configured backend environment to return counts and field names only. No identities, FENs, game URLs, moves or credentials leave the database:

```python
import json, os
from pymongo import MongoClient

client = MongoClient(os.environ['MONGO_URL'])
pool = client[os.environ['DB_NAME']].diagnostic_pool
coverage = list(pool.aggregate([
    {'$group': {
        '_id': {'pool_version': '$pool_version', 'grade_version': '$grade_version',
                'concept': '$concept', 'tier': '$tier'},
        'positions': {'$sum': 1},
        'with_grade_map': {'$sum': {'$cond': [{'$isArray': '$step_grades'}, 1, 0]}},
        'with_fingerprint': {'$sum': {'$cond': [
            {'$eq': [{'$type': '$grade_fingerprint'}, 'string']}, 1, 0]}}
    }}
], maxTimeMS=10000))
fields = list(pool.aggregate([
    {'$project': {'keys': {'$map': {'input': {'$objectToArray': '$$ROOT'},
                                  'as': 'field', 'in': '$$field.k'}}}},
    {'$unwind': '$keys'},
    {'$group': {'_id': '$keys', 'documents': {'$sum': 1}}}
], maxTimeMS=10000))
print(json.dumps({'coverage': coverage, 'field_presence': fields}, default=str))
client.close()
```

This inventory is not a content-quality gate or export authorization. Next, inspect existing proof/teaching fields and their referenced canonical sources before deciding what anonymous examples, if any, need separate export approval. Do not rebuild the pool or run Stockfish.

Mohit confirmed Claude will trace the player who experienced the hour-long wait. Do not duplicate that investigation or request the player's identity again. That trace is separate from the content inventory and does not block local interaction work. No delay cause has been established here.

## Review and release boundary

Review this repair separately from the full new experience. Refresh the integration base before applying, rerun regressions, and verify current, legacy and multi-step diagnostic behavior with a non-admin account. No bulk migration is required; new fields are written on explicit-protocol attempts. Deploy compatible backend/frontend together. Do not roll back to a frontend unable to render unread receipts without an operator-reviewed preservation/drain plan; never delete attempts to undo the release. New session behavior needs Mongo-backed race/failure tests and a browser test before shipping. Claude retains push/deploy ownership; this document is not an instruction to enable the new first-session rollout.
