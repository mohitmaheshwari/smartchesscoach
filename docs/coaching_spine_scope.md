# Coaching Spine — closing the loop between Home and Play

**Date:** 2026-07-03
**Author:** Claude (Mohit signed off "go do it")
**Target:** 3/10 → 8/10 on the coaching-pillars audit

## The problem, in one sentence

HomePage promises "your focus this week is King safety." Play with Coach never reads it. The user can feel the seam between two clicks — and that's the retention killer for Mohit's coaching-as-relationship product.

## The audit found

- **Playing 3/10** — Coach opponent is pure Stockfish keyed only on user_rating. Doesn't read the mission.
- **Learning 3/10** — Zero grep hits for `primary_weakness_picker` or `user_active_focus` in `coach_play/*`. **Verified independently.**
- **Coach 4/10** — Session mission text exists but no scoreboard. `teaching_recall` capped at 1/session; fresh users get silence.
- **Engaged 2/10** — MistakeFreeStreak component exists but not on HomePage. No day-N-of-14 progress grid. No mastery bar on Home.

## Scope (P0–P3)

### P0 — One source of truth (spine)
- `coach_play/coach_game_session.py`: on `start()`, read `user_active_focus` (weakness) via `services.primary_weakness_picker`. Pipe topic + subtype histogram into `session_goal_service.derive_session_goal`.
- New helper `services/focus_bridge.py` — `get_active_focus_for_session(user_id)` returns the same shape the FocusCard consumes. This becomes the ONE reader all four playing/coaching surfaces call.
- Deprecate the rival focus sources (`users.focus`, `coach_memory.learning.current_focus`) by having them delegate to focus_bridge. Not deleted yet (backwards compat); just no longer authoritative.

### P1 — Mission scoreboard
- `MissionScoreboard` dataclass on `CoachGameSession`:
  - `focus_topic`, `focus_subtype`
  - `critical_moments_matching_focus`: count of moves where the position matched focus (e.g., king_safety-relevant if focus is king_safety)
  - `handled_correctly`: count of those where user played best-or-close move
  - `handled_incorrectly`: count of misses
- Populated live per move using cognitive_gap classifiers we already built (`services/cognitive_gap_subtypes.py`).
- New API field on `/coach/play/session/{id}`: `mission_scoreboard: {matched: N, handled_correctly: M}`.
- Frontend `PostGameStreakResult` gets a new section: **"Today's Mission"** showing scoreboard + baseline delta.

### P2 — HomePage daily loop visible
- Import `MistakeFreeStreak` on `HomePage.jsx` — above `FocusCard`.
- New component `FocusDayGrid` — 14-day dot grid; a dot is green if that day had an analyzed game AND the mission scoreboard >0 matched moments. Reads `/coach/focus-day-grid` (new endpoint).
- When `check_focus_outcome` resolution=improved: HomePage shows celebration banner. When regressed: shows escalation card with CTA to `/play-with-coach?intensity=high`.

### P3 — Warm greeting
- New service `services/session_greeting_service.py` — `build_session_greeting(user_id)` reads:
  - Days into current focus
  - Last session's mission scoreboard result
  - Last session's biggest focus-relevant mistake (game_id, move, subtype)
- Returns a 1-2 sentence coaching greeting: "You're on day 6 of your king-safety focus. Last game you slipped on move 14 with Bxh6 — same square is under fire today."
- Injected at session start into the first coach message.

## Non-goals (deferred)

- P4 — Opponent-play biased toward user's focus subtype. Structural change to `PedagogicalOpportunityService`. Deferred.
- Merging the 4 focus sources into 1 (only P0 hard-wires the reader; deletion is post-migration).
- Building new pages. All UI changes are additions to HomePage + PostGame.

## Acceptance criteria — the scoring rubric

Each pillar re-scored after implementation. Target ≥ 8 per pillar. Evidence I'll present for each score:

**Playing (target 8/10)**
- ✓ `/coach/play/start` response contains a `mission` field derived from `user_active_focus`
- ✓ `session_goal_service` output includes topic + subtype pulled from focus bridge
- ✓ Sidebar shows the mission at all times

**Learning (target 8/10)**
- ✓ Grep `primary_weakness_picker` or `focus_bridge` in `coach_play/*` returns hits
- ✓ New game's session goal for Parth includes "time_management" (his current focus)
- ✓ New game's session goal for Mohit includes "time_management"
- ✓ Rival focus sources delegate (log message: "delegated to focus_bridge")

**Coach (target 8/10)**
- ✓ Session start API response includes `session_greeting.text` with days + last-game reference
- ✓ Post-game response includes `mission_scoreboard` with concrete numbers
- ✓ At least one live coach message references "you're working on X" during play

**Engaged (target 8/10)**
- ✓ HomePage `/home/dashboard-v2` response includes streak + focus_day_grid
- ✓ FocusDayGrid renders 14 dots for Parth's active focus, with correct green dots on days he played
- ✓ Celebration/escalation banner shows when `check_focus_outcome.resolution ∈ {improved, regressed}`

## Rollout order

1. Verify audit + write scope (this doc) — DONE
2. Build `services/focus_bridge.py`
3. Wire into `coach_game_session.py.start()` + `session_goal_service.derive_session_goal`
4. Build `MissionScoreboard` dataclass + populate live in the move-handling loop
5. Extend `/coach/play/session/{id}` + `/coach/play/start` to include mission
6. Build `services/session_greeting_service.py` + inject at session start
7. Extend `HomePage.jsx`: add `MistakeFreeStreak` + `FocusDayGrid` component
8. Extend `/home/dashboard-v2` to include streak + focus_day_grid data
9. Backend celebration/escalation banner data
10. End-to-end trace for Parth + Mohit: assert focus flows Home → Session → Post-game
11. Re-score pillars against rubric above
12. Commit + push
