# Engine 2 Phase 1 — Concept Mastery Tracker

**Status:** SHIPPED 2026-06-04. Awaiting backfill on production + Phase 2 build.
**Owner:** Mohit + Claude
**Scope:** small backend service, ~250 LOC + hook + scripts.

---

## 1. The problem

Engine 2 was supposed to "know what the user already knows" — track when concepts have been demonstrated repeatedly, then downgrade coaching about them. Audit on 2026-06-04 found the loop never closed in production:

- **1474 `user_concept_understanding` rows** across 78 users — population works.
- **99.7% (1469) have `acknowledged=False`** — the mastery signal almost never flips.
- **`shown_count`** climbs to **2223 for a single concept** on Mohit's account without any downgrading.
- The only writer of `acknowledged=True` was a `/coach/decryption/acknowledge` button endpoint that almost nobody uses.
- `track_concept_application(applied_correctly: bool)` exists as a function but is **never called** by any caller.

Result: the data model is right, the producer fires correctly, but nothing watches for demonstrated mastery from gameplay and updates the signal. PWC + the V5 caption pipeline read `acknowledged` — both see "False" for everything, so they teach every concept every time as if the user had never seen it.

## 2. The shape

Auto-detect mastery from games. After each game is analyzed:

1. Walk every user move in `decryption_v5_data`.
2. Collect the union of concepts violated (severity ∈ mistake/blunder/serious, picking up `principle_id_used` + `plan.concept_id` + `caption_facts_principles_violated[].principle_id`).
3. For every concept the user already has a row for in `user_concept_understanding`:
   - **Violated this game** → `streak_clean = 0`, `acknowledged = False`, `last_violation_at = now`, `violations_total += 1`.
   - **Not violated** → `streak_clean += 1`, `clean_games_total += 1`, `last_clean_game_at = now`. If `streak_clean >= streak_required` (default 3) AND not already acknowledged → set `acknowledged = True`, `mastered_at = now`.
4. Each (user, concept) idempotency via `last_evaluated_game_id` so re-runs don't double-count.

**Concept taxonomy** — the tracker accepts both signal vocabularies:
- Central pipeline principles: `TAC_HANGING_PIECE`, `TAC_PIN_PATTERN`, `STR_KING_SAFETY`, etc.
- V5 plan concepts: `piece_without_purpose`, `knight_on_rim`, `knight_fork`, etc.

Whichever was used to populate the user's row, the tracker matches it. No mapping table needed because the producers write the same vocabulary they detect with.

## 3. Schema additions to `user_concept_understanding`

```js
{
  // existing
  user_id, concept_id, concept_type, concept_text, source_position,
  shown_count, acknowledged, acknowledged_at, created_at, updated_at,
  applied_correctly_count, failed_to_apply_count,

  // NEW (added by tracker — null until first eval)
  streak_clean: 0,                   // consecutive clean games
  streak_required: 3,                // mastery threshold (per-concept override)
  mastered_at: null,                 // ISO ts when first reached mastery
  last_violation_at: null,           // ISO ts of latest violation
  last_clean_game_at: null,          // ISO ts of latest clean game
  violations_total: 0,
  clean_games_total: 0,
  last_evaluated_game_id: null       // idempotency key
}
```

## 4. Files

| File | Purpose |
|---|---|
| `backend/services/concept_mastery_tracker.py` | The tracker. Pure helpers + DB-bound updater. |
| `backend/analysis_worker.py` (patch) | Hook after `[opening-profile] refreshed`. Async sub-call with isolated motor client, same pattern as the existing opening-profile refresh. Non-fatal on exception. |
| `backend/scripts/backfill_concept_mastery.py` | Bootstrap. Walks every user's analyzed games oldest-first, replays streak math. Idempotent. |
| `backend/scripts/probe_concept_mastery.py` | Diagnostic. Prints one user's per-concept state sorted mastered → struggling. |
| `backend/scripts/patch_analysis_worker_mastery_hook.py` | One-shot patcher — kept in repo for repeatability. |

## 5. Idempotency

The tracker writes `last_evaluated_game_id` on each concept row after evaluating a game. Running the tracker on the same (user × game) again is a no-op. Effects:

- Worker re-running on retry → no double-counting.
- Backfill being re-run after deploy → only NEW games get evaluated.
- Manual replays for one user → harmless.

## 6. What this does NOT do (Phase 1 boundary)

- **No consumer.** This phase only WRITES the mastery signal. PWC and the V5 caption pipeline still read `acknowledged` and treat the existing data correctly, but no DOWNGRADE/SUPPRESS logic fires yet.
- **No backfill of historical `shown_count`.** The `shown_count` field stays as it is (already populated by the V5 service). We only add streak/violation fields.
- **No new concepts created.** The tracker updates rows that already exist. Concepts the user has NEVER been shown stay absent from the collection (creating them would require running the V5 service, which the producer already handles).
- **No A/B feature flag.** This is a write-only signal; nothing user-facing changes. Phase 2 (the PWC mastery gate that READS this signal) is where flag gating belongs.

## 7. Test plan

1. **Pure helpers**: `extract_concepts_from_move(rec)` returns the right set for known move records.
2. **Idempotency**: backfill twice on the same user; second run reports `skipped_idempotent` = all concepts × all games.
3. **Streak math**: synthesize a user with 3 concepts and 5 fake games where games 1-3 violate concept A and 4-5 are clean. After backfill: concept A has `violations_total=3, streak_clean=2, acknowledged=False`; concepts B/C have `streak_clean=5, acknowledged=True, mastered_at != null`.
4. **Worker hook smoke test**: re-analyze one game, confirm `[mastery-tracker]` log line appears.
5. **Probe sanity**: `probe_concept_mastery.py --user-id user_8b599930d7ef` shows non-empty mastered list + non-empty struggling list (not all rows the same state).

## 8. Phase 2 preview (next, after sign-off)

`services/user_mastery_gate.py` — a single function that PWC + V5 caption pipeline call right before emitting a coaching message:

```python
async def get_mastery_state(db, user_id, concept_id) -> Literal["mastered", "slipping", "learning", "unseen"]
```

PWC's `coaching_voice` and V5's caption finalize hook wrap their emission:

- `mastered` → SUPPRESS (just the move, no caption)
- `slipping` → DOWNGRADE (brief reminder)
- `learning` / `unseen` → SHOW (full caption)

Gated behind `PWC_SKILL_GATE_ENABLED=true` for A/B rollout. Already-shipped env-flag infrastructure; this phase just turns it on.

## 9. Rollback

Pure additive change. To reverse:
- Remove the patch block from `analysis_worker.py` (the worker still completes normally; tracker simply stops firing).
- The new fields on `user_concept_understanding` rows can stay — they're optional and ignored by anything that doesn't know about them.
- The collection schema isn't enforced; nothing breaks.

## 10. Decisions

| Decision | Choice |
|---|---|
| Mastery threshold (default streak) | **3 consecutive clean games** |
| Re-violation behavior | **Forces `acknowledged=False`** (un-master, restore full coaching) |
| Concept taxonomy | **Accept both** principle_id (central pipeline `TAC_/OP_/MID_/END_/DEF_/STR_`) AND plan.concept_id (V5 plan namespace `piece_without_purpose`, `knight_fork`, `golden_*_principle_N`). Single concept-namespace per user row. |
| Namespace bridging | Tracker AUTO-CREATES `user_concept_understanding` rows for principle_ids it sees but the user has no row for. Closes the gap between the older V5 producer (only emits plan namespace) and the central caption pipeline (emits principle namespace). `concept_type` is derived from prefix. |
| Worker integration | **Synchronous-in-async pattern** mirroring opening-profile refresh. Non-fatal. |
| First-evaluation rule | If `last_evaluated_game_id` is None and the game IS a violation → counts as violation. If it's clean → counts as clean. No special "warm-up" period; the user's first analyzed game starts producing signal. |
| Relevance requirement | A concept must be PRESENT in the game (fired in any user move's analysis) for streak math to apply. Absence is NOT clean demonstration — concepts that the user simply never faced don't accumulate streak. First-pass version skipped this check and auto-mastered concepts that had never come up; corrected 2026-06-04 mid-backfill. |

## 11. Population-wide aggregate (43 users with mastery signal)

After full backfill across all users with prior concept tracking:

| Metric | Count |
|---|---|
| Users with mastery signal | 43/51 (the other 8 had concept rows but no v5_data to evaluate) |
| Total user×concept rows | 2,720 (up from 1,474 baseline; +1,246 auto-created in principle namespace) |
| MASTERED rows | 379 |
| STRUGGLING (≥3 violations) | 799 |
| LEARNING (mid-streak) | 360 |

### Top 10 universal struggles

These are the highest-leverage targets for new R12 predicates + PWC live nudges:

| # | Concept | Total violations | Users affected |
|---|---|---|---|
| 1 | **TAC_CHANGED_AFTER_MOVE** | 8,594 | 43/43 |
| 2 | TAC_CHECKS_CAPTURES_THREATS | 5,489 | 43/43 |
| 3 | TAC_HANGING_PIECE | 5,045 | 43/43 |
| 4 | TAC_DEFENDER_COUNT | 3,877 | 43/43 |
| 5 | MID_ROOK_OPEN_FILE | 2,380 | 41 |
| 6 | MID_PAWN_BREAK | 2,048 | 40 |
| 7 | MID_KEEP_ATTACKERS | 1,921 | 39 |
| 8 | DEF_MOST_ATTACKED | 1,659 | 39 |
| 9 | OP_SAME_PIECE_TWICE | 1,578 | 40 |
| 10 | DEF_TRADE_ATTACKERS | 1,485 | 39 |

### Top 10 widely-mastered

These are the concepts to SUPPRESS in Phase 2's mastery gate first — they're already learned:

| # | Concept | Users mastered |
|---|---|---|
| 1 | TAC_DISCOVERED_PATTERN | 38 |
| 2 | TAC_PIN_PATTERN | 36 |
| 3 | TAC_FORK_PATTERN | 33 |
| 4 | OP_CLAIM_CENTER | 25 |
| 5 | OP_FINISH_DEVELOPMENT | 23 |
| 6 | OP_BISHOP_TRADE_DOUBLES_PAWN | 19 |
| 7 | MID_KING_SAFETY | 18 |
| 8 | END_KING_ACTIVE | 17 |
| 9 | OP_NOT_CASTLED | 15 |
| 10 | OP_PAWN_HEAVY | 15 |

### Strategic findings

1. **`TAC_CHANGED_AFTER_MOVE` is the #1 universal weakness** — 8,594 violations across literally every evaluated user. The "what did your opponent's move change?" prompt is the single highest-leverage coaching intervention we could ship.
2. **Tactical pattern recognition is solid** — pin/fork/discovered mastered by 77-88% of users. Existing detectors and repetition coaching work for these.
3. **Defense vocabulary is uniformly thin AND weakly mastered.** Only one DEF concept appears in the mastered tier; two appear in the struggling top 10. Suggests expanding the DEF_ taxonomy (4-6 new detectors) is a priority for Phase 2+.
4. **Middlegame planning is the development gap** — rook on open file, pawn breaks, keeping attackers all in struggling top 10. The MID_ taxonomy has 5 concepts; needs to roughly double.

## 12. Validated on Mohit (340 games)

After backfill:
- 76 concepts on file (41 original plan-namespace + 35 auto-created principle-namespace)
- **68 MASTERED** (acknowledged=True) — including `END_RULE_OF_SQUARE` (18 streak, 1 hist. violation), `END_OPPOSITION`, `OP_KNIGHT_ON_RIM`, `TAC_BACK_RANK`
- **8 STRUGGLING** (≥3 violations, current streak ≤ 2):
  - `TAC_CHANGED_AFTER_MOVE` — 299 violations / 7 clean = his biggest blind spot
  - `TAC_CHECKS_CAPTURES_THREATS` — 179 viol / 75 clean
  - `MID_KEEP_ATTACKERS` — 74 viol
  - `DEF_MOST_ATTACKED` — 66 viol
  - `OP_SAME_PIECE_TWICE` — 39 viol
  - `OP_QUEEN_OUT_EARLY` — 21 viol
  - `OP_FINISH_DEVELOPMENT` — 13 viol
  - `OP_F2_F7_STRIKE` — 8 viol

Phase 2 (mastery gate) will use this signal to DOWNGRADE captions about `END_RULE_OF_SQUARE` when they fire in Mohit's games (he's clearly demonstrated it), and ESCALATE captions about `TAC_CHANGED_AFTER_MOVE` (he keeps slipping there).
