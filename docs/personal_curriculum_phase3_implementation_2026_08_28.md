# Personal Curriculum — Phase 3 implementation

**Status:** COMPLETE 2026-08-28 — default-off contracts and probes only.

## Delivered

- Added `services/personal_curriculum.py` as the versioned composition and
  lesson-result contract.
- Kept `PERSONAL_CURRICULUM_ENABLED` false by default. Flag-off callers receive
  no replacement decision.
- Encoded the six signed outcomes: OBSERVE, REPAIR, EXPAND, CONTINUE, REVIEW,
  and APPLY.
- Limited a response to one primary item and at most one distinct review.
  Explore is explicitly non-replacing.
- Added explicit trustworthy, sparse, stale, conflicting, and not-measured
  evidence states. REPAIR and APPLY require trustworthy evidence.
- Added lesson-result evidence for explanation, guided, independent, review,
  and application attempts without adding a mastery store or write path.
- Enforced that assistance or answer reveal cannot become Can do alone.
- Enforced that did-not-occur and unclear game opportunities change no state.
- Enforced Plan-grade detector authorization for Used in games and APPLY.
  Rule of the Square remains capped at Can do alone.
- Rejected Reliable until delayed-recall and repeated-application thresholds
  are separately data-locked.

## Single-source change

The existing endgame content-reference alias map moved from
`services/today_composer.py` to `services/endgame_theory_service.py`.
Today and Personal Curriculum now resolve the same canonical lesson identity
and route. No lesson names, moves, explanations, or prerequisites were copied.

## Verification

- **75 passed**: Phase 3 contract probes plus Rule of the Square, opposition,
  Scholar’s Mate, and Fried Liver regression tests.
- Python compilation passed for all changed Python files.
- The mandated `tests/test_all_flows.py` E2E suite was attempted. It could not
  reach the code because no local API was running; starting the API then failed
  during import because the local Windows Python environment lacks `bcrypt`.
  This is an environment-blocked E2E, not a passing result.

## Phase boundary

Phase 3 adds no route, navigation change, database write, lesson adapter, or
new player-facing copy. Phase 4 remains blocked on the live desktop/mobile
audit, current analytics baselines, and representative-player mockup testing.
