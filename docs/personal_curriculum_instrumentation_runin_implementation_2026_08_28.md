# Personal Curriculum — Instrumentation-Only Run-In Implementation

**Status:** DEPLOYED — 2026-08-28. Public release health is verified;
event-inspector verification and the fixed observation interval remain pending.

## Outcome

The unchanged legacy learning experience now emits a comparable Personal Curriculum funnel. No recommendation, page layout, navigation destination, lesson sequence, chess result, mastery state, or player-facing copy changed.

All event IDs and the privacy boundary live in `frontend/src/lib/analytics.js`. Pages import the canonical constants and call `trackCurriculum()`; they do not define local event vocabularies or call PostHog directly.

## Implemented coverage

| Existing surface | Events now emitted |
|---|---|
| Home coach focus | visible `curriculum_decision_shown`; `curriculum_primary_clicked` on the existing primary action |
| Learn/Lab | `learn_viewed`; visible Engine 2 recommendation impression; primary recommendation click |
| Study catalogue | `explore_opened` for openings/endgames categories and lesson selections |
| Progress | `progress_viewed` |
| Prescribed/pattern training | `lesson_started`; `independent_attempt` with result and puzzle index |
| Opening lesson | `lesson_started`; `explanation_completed` when the walkthrough moves into practice |
| Opening practice | `lesson_started`; `guided_attempt` when a hint is visible/requested, otherwise `independent_attempt` |
| Trap practice | `lesson_started`; `guided_attempt` because the current legacy line supplies move guidance |
| Endgame lesson | `lesson_started`; `explanation_completed` after the intro; `guided_attempt` because the concept visual remains on the board |

Recommendation impressions require at least 60% viewport intersection on Home and Learn. An API response alone is not counted as an impression.

## Intentionally reserved without legacy emitters

- `curriculum_review_clicked`: the current product has no canonical due-review item.
- `review_attempt`: a restart or ordinary practice attempt is not evidence of a scheduled review.
- `back_to_plan`: the current product has no coach-owned Personal Curriculum plan to return to.

These IDs are registered now so the future variant uses the same vocabulary, but emitting them from the current UI would manufacture a baseline.

## Event schema and privacy

Every run-in event receives:

```text
instrumentation_version = personal_curriculum.baseline.v1
flag_state = legacy_control
```

The central allowlist accepts only coarse primitive dimensions such as surface, canonical content ID/type, decision source/ID, origin, support level, result, and position index. It drops unrecognized properties and all objects.

The allowlist explicitly excludes FEN, PGN, moves, move lists, email, username, coaching text, user ID, game ID, and session ID. String dimensions are capped at 120 characters. PostHog remains interaction evidence only; MongoDB remains authoritative for learning outcomes.

Rating band is not derived in the browser because the frontend has no canonical rating-band resolver. Duplicating the backend's rating thresholds for analytics would violate single-source ownership. Segment by an authoritative server/user property when the production export is prepared.

## Verification

- `npm test -- --runInBand --watchAll=false src/lib/analytics.test.js` — **3 passed**.
- `python -m pytest backend/tests/test_analytics_event_registry.py -q` — **4 passed**.
- `npm run build` — **exit 0**; the new Home hook warning found on the first build was corrected. The final build reports only pre-existing repository warnings plus the existing missing chess.js source map and stale Browserslist data.
- `git diff --check` on the changed instrumentation files — **clean**.
- Raw PostHog calls and raw-string `trackCurriculum()` emitters outside the canonical analytics module — **none found**.

## Production run-in checklist

1. Deploy the unchanged-UX instrumentation build with the Personal Curriculum UI flag still off.
2. Record deployment timestamp in UTC and the production release identifier.
3. In PostHog's live event inspector, verify one test journey for each available surface and confirm forbidden properties are absent.
4. Record test-account exclusions before querying results.
5. Lock the fixed UTC observation interval before viewing conversion results.
6. Export aggregate event counts and unique users by surface, content type, origin, support level, result, and authoritative rating band when available.
7. Version the aggregate-only export; include no raw person, session, game, or event rows.
8. Use the distributions to lock Phase 4 minimum-sample, rollout, rollback, and behavior-success thresholds.

This implementation closes the missing-emitter problem and is live in
`static/js/main.c35c6cf9.js`. It does not yet close the baseline-data gate:
historical events cannot be recovered, no production observation interval has
been collected, and this environment has neither a PostHog connector nor a
PostHog query credential. The supported browser runner was retried after
Mohit's visual approval and still failed before opening a tab with Windows
sandbox launcher OS error 206.
