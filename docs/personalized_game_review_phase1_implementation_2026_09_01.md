# Personalized Game Review Coach — Phase 1 Implementation

**Date:** 2026-09-01  
**Status:** COMPLETE — contracts only, default off, no visible behavior

## Outcome

Phase 1 adds one inert backend contract module:

- `backend/services/game_review_contracts.py`

It defines:

- `TeachableEvent` and its move, concept, opportunity, evidence, teaching and visual references;
- the seven signed outcomes: demonstrated, missed, allowed, answered, neutralized, introduced and silent;
- `ReflectionPrompt`, `ReflectionOption` and `PlayerReflection`;
- `GameTeachingPlan`, reference-only chapters and a canonical next action;
- deterministic serializers, event indexing and the default-off parity boundary.

No route imports the module. No database or frontend file was changed by Phase 1. Nothing is persisted or rendered.

## Locked guards

- `PERSONALIZED_GAME_REVIEW_COACH_ENABLED` defaults to false and is read at call time.
- Flag-off returns the exact original legacy response object and byte-identical JSON.
- Detector authorization uses `detector_quality.is_authorized`, not the rollout-sensitive compatibility gate. Unknown and Shadow detectors therefore fail closed even when the older enforcement flag is off.
- Unverified evidence cannot reach Caption or Plan surfaces.
- Silent events are diagnostic-only and cannot contain teaching or reflection.
- Diagnostic-only events cannot be referenced by a player plan.
- Recurring personal connections require Plan-grade evidence.
- Prescribed next actions require Plan-grade evidence and must originate from a selected chapter.
- Reflection is options-only, requires `not_sure` and `none_of_these`, records the exact options shown and cannot submit an invented option.
- Plan chapters store event IDs and canonical content references, not copied lesson bodies.
- Phase 1 plans are forced to `shadow`; the contract rejects `visible`.
- The module imports no database, network or LLM dependency.

## Verification

Focused regression command:

```text
python -m pytest -q tests/test_game_review_contracts.py \
  tests/test_detector_quality_gate.py \
  tests/test_personal_curriculum_contracts.py \
  tests/test_stage4_caption_contract.py
```

Result: **82 passed in 1.19s**.

Syntax compilation passed for the new service and test module.

`python tests/test_all_flows.py` was attempted as required, but was inconclusive: no backend server was listening on localhost, so it failed on the first HTTP connection before executing a product assertion. This is not reported as green and is not a Phase 1 regression.

## Scope protection

Phase 1 does not:

- adapt `MoveTeachingDecision` into events;
- generate reflection options;
- select game chapters;
- write learner evidence;
- add an API field;
- change a route or UI;
- invent moment caps, planner weights, question budgets or mastery thresholds.

## Phase 2 gate

Before Phase 2 changes a live adapter:

1. snapshot full current response fixtures for Game Review, Reflect and Play with Coach;
2. prove the new adapter consumes `MoveTeachingDecision` rather than raw FEN reinterpretation;
3. prove backend reflection options replace, rather than duplicate, the frontend generator;
4. keep the feature flag false and retain byte parity;
5. run the focused suites plus the live core flow suite with a backend server available.
