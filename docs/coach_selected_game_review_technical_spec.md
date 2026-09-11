# Coach-Selected Game Review — Technical Specification

**Status:** LOCKED FOR V1 IMPLEMENTATION
**Date:** 2026-09-11
**Scope:** `docs/coach_selected_game_review_scope.md`
**Data lock:** `docs/coach_selected_game_review_data_lock_2026-09-11.md`

## 1. Runtime boundary

`backend/services/coach_selected_review_service.py` is the only new orchestration authority. It may resolve the existing complete-coaching access decision, project stored reviews through `maybe_attach_phase5_review_fields`, read active focus, apply the locked selector, transition a prescription and return presentation-safe metadata.

It may not import Stockfish, python-chess, a detector, a caption generator or an LLM. A guard test enforces this boundary.

## 2. Prescription schema

Collection: `game_review_prescriptions`.

```json
{
  "prescription_id": "grp_rx_<stable hash>",
  "user_id": "server only",
  "game_id": "server only",
  "state": "recommended | started | dismissed | completed | superseded",
  "is_active": true,
  "selector_version": "focus_then_authorized_richness.v1",
  "plan_id": "existing safe GameTeachingPlan id",
  "plan_fingerprint": "existing plan input fingerprint",
  "focus_key": "referenced active focus or null",
  "focus_match": true,
  "resume": {"move_index": -1},
  "created_at": "UTC BSON date",
  "started_at": null,
  "updated_at": "UTC BSON date",
  "dismissed_at": null,
  "completed_at": null,
  "superseded_at": null,
  "superseded_reason": null
}
```

Public responses omit `user_id`, raw focus evidence, detector internals and plan fingerprints. A partial unique index on `user_id` where `is_active=true` prevents competing active prescriptions. Index creation is explicit; GET does not create indexes.

## 3. State transitions

| From | Action | To | Notes |
|---|---|---|---|
| none | select | recommended | Deterministic candidate; retry returns the same row. |
| recommended | start | started | Records once and returns the review URL. |
| started | save progress | started | Latest confirmed move index; never changes learning state. |
| recommended/started | dismiss | dismissed | Sets `is_active=false`; next selection excludes the game. |
| started | complete | completed | Sets `is_active=false`; existing completion projection remains. |
| recommended/started | plan unsafe or missing | superseded | Safety wins; existing progress remains auditable. |

Every mutation matches authenticated `user_id + prescription_id + allowed prior state`. Repeated requests return the reached public state rather than duplicating events.

## 4. Eligibility and selector

1. Load unreviewed, analyzed games owned by the authenticated user.
2. Exclude games with final dismissed or completed prescriptions.
3. Load their stored V5 moves and `game_teaching_plan`.
4. Run the same safe projection as the player-facing review route under the current quality configuration.
5. Keep only safe plans containing a selected chapter.
6. Derive topic keys only from projected event concept IDs/content references.
7. Rank by `(active_focus_match, selected_chapter_count, played timestamp, stable game-id tie-breaker)` descending.

The game-id tie-breaker supplies determinism, not meaning. Existing safe started prescriptions return before new selection. A recommended prescription also remains stable across refresh.

## 5. API

- `GET /api/game-review/recommendation` — rollout state, active prescription or honest empty state.
- `POST /api/game-review/recommendation/{prescription_id}/start` — start and return review URL.
- `POST /api/game-review/recommendation/{prescription_id}/progress` — body `{move_index}`; save resume position.
- `POST /api/game-review/recommendation/{prescription_id}/dismiss` — dismiss and return the next selection or exhausted state.
- Existing `POST /api/lab/{game_id}/complete-review` accepts optional `prescription_id`, preserves verified review statistics, completes the matching prescription and obtains `next_game` through the canonical service when enabled.

When complete-coaching access is disabled, the new GET returns `enabled:false`; mutations reject; existing Lab and completion behavior remain compatible.

## 6. Public contract

```json
{
  "enabled": true,
  "status": "recommended | started | empty | paused",
  "prescription": {
    "prescription_id": "grp_rx_...",
    "state": "recommended",
    "game": {
      "game_id": "...",
      "opponent": "Arjun",
      "result": "loss",
      "platform": "chess.com",
      "opening": "...",
      "played_at": "..."
    },
    "reason": {
      "headline": "I picked this game for your current lesson.",
      "body": "This game connects your current focus to a real decision.",
      "focus_match": true
    },
    "chapters": [{
      "event_id": "...",
      "role": "missed_opportunity",
      "label": "A possibility worth discovering",
      "text": "existing authorized teaching text"
    }],
    "resume": {"move_index": -1},
    "review_url": "/game/<id>?prescription=<id>&resume=-1"
  },
  "fallback": null
}
```

Chapter labels are presentation language keyed by the existing role enum. Chapter text comes from projected event teaching or the plan takeaway; the frontend does not invent chess prose.

## 7. Frontend

- `AllGames.jsx` fetches the legacy archive and prescription contract in parallel.
- Enabled users see the prescription first; disabled users retain current behavior.
- Starting and dismissing are server mutations with loading, retry and exhausted states.
- `LabV2.jsx` reads `prescription` and `resume`, saves move-index progress after navigation settles, and includes `prescription_id` on completion.
- Archive rows receive review-state labels where available and direct access remains independent.
- The Lab hero may consume the same contract during migration; it must not keep another selector.

## 8. Testing and rollout

- Pure service tests cover safe-plan eligibility, ranking, stable selection, lifecycle, idempotency, ownership, stale plans, dismissed exhaustion and active-row conflict.
- Route tests cover authentication, disabled access, malformed input, completion integration and no Shadow leakage.
- Frontend tests cover recommended, started, empty, start, dismiss, retry and flag-off archive parity.
- E2E covers recommendation → start → resume → dismiss → distinct replacement → start → complete → distinct next result.
- Rollout reuses the existing complete-coaching access decision and personalized-review enrollment. No new environment flag or cohort registry is added.
- Rollback disables existing complete-coaching access. Prescription rows remain inert and auditable.
