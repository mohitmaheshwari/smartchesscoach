# Personalized Game Review Coach - Phase 3 Implementation

**Date:** 2026-09-01  
**Status:** COMPLETE IN SHADOW - no player-facing rendering or API field

## Outcome

Phase 3 now builds one deterministic whole-game teaching plan from the exact
typed decisions already produced by the canonical V5 caption pipeline:

```text
stored Stockfish facts
        |
canonical move_observation deriver (in memory, no write)
        |
MoveTeachingDecision (existing move-level authority)
        |
TeachableEvent[] (only authorized current-schema evidence survives)
        |
measured shadow planner
        |
game_analyses.game_teaching_plan (rollout_mode=shadow)
```

The new plan is persisted alongside V5 for future analyzed games and lazy V5
regenerations. It is deliberately absent from the current V5 Mongo projection,
response serializer and frontend. The existing
`PERSONALIZED_GAME_REVIEW_COACH_ENABLED=false` behavior remains the legacy
player experience. Shadow measurement does not require turning that visible
feature flag on.

## Data lock

The aggregate read-only production bake-off is versioned at
`backend/data/corpus_snapshots/personalized_game_review_phase3_planner_bakeoff_2026-09-01.json`.

- 947 current-schema `simple_hang` observations across 813 games.
- 947/947 current decisions regenerated `final_verified` from stored engine
  facts; zero Stockfish runs, zero LLM calls and zero database writes.
- Strict eligible reach is 5.96% of 13,637 stored V5 games.
- Formula D (teaching completeness, critical flag, stored loss, earliest)
  selected complete teaching in 70.23% of affected games.
- The shadow moment cap is two; 97.05% of affected games have at most two
  eligible events.
- The shadow reflection budget is one; a first structural candidate reaches
  74.1%, while requiring two drops to 51.3% and no production reflection
  behavior exists yet.

These are shadow measurement settings, not visible-release locks. Human
importance and story-coherence validation is still required before the planner
can render.

## Implementation

- `backend/services/game_review_planner.py`
  - pure deterministic Formula D ranking;
  - two-moment cap and one-reflection budget;
  - chronological chapter display after importance selection;
  - explicit independent-moment wording instead of invented causality;
  - recurrence and next action remain absent unless explicit Plan-grade
    evidence is supplied.
- `backend/services/game_review_shadow_runtime.py`
  - reuses `move_observation_deriver.py`; no second detector;
  - accepts only schema 16+ `piece_safety/simple_hang`;
  - adapts the exact live `MoveTeachingDecision`, including its verification,
    text, principle, visual and provenance;
  - all other or unverified signals fail closed;
  - serializes an auditable no-plan result for genuinely quiet games.
- `backend/services/game_decryption_v5_service.py`
  - optional output collector preserves every existing caller's return type;
  - collects events at the central-decision call site, never from prose after
    the fact;
  - differentiates derivation failure from a valid zero-event game.
- `backend/analysis_worker.py`
  - stores the shadow artifact for newly analyzed games in the same analysis
    document as V5.
- `backend/routes/coach.py`
  - stores the shadow artifact during lazy V5 generation;
  - does not fetch or return it on the current endpoint.

## Honesty and rollout guards

- Only the single Plan-authorized detector ID
  `gap:piece_safety:simple_hang` can currently produce a plan chapter.
- Schema below 16 is rejected.
- `final_verified=false` or a skipped central decision becomes a silent audit
  event and cannot enter a player plan.
- The planner imports no board parser, database client, network client, engine
  or LLM.
- No recurrence, improvement, mastery, intent or causal bridge is inferred.
- No bulk regeneration or backfill was run.
- No frontend, deployment, commit, push or production data mutation was done.

## Verification

Compilation passed for all changed services, routes, worker and tests.

The prior Phase 1/2 boundary suite plus all Phase 3 planner/runtime tests:

```text
125 passed in 1.91s
```

The nearest central caption boundary baseline remains unchanged from Phase 2:
79 passed and 6 pre-existing failures in forced-recapture / CoachExtras /
SocraticExtras assertions. The live-HTTP V5 suite produced 15 setup errors
because no backend URL/server was configured; no Phase 3 assertion ran there.

`git diff --check` passed with only the repository's existing Windows
LF-to-CRLF warnings.

## What remains before visible release

1. Build the blinded representative full-game packet from stored shadow plans.
2. Have Mohit and two coaches grade chess truth, moment importance, teaching
   clarity, personalization, reflection usefulness and story coherence.
3. Lock the visible formula/cap only from those labels plus behavior data.
4. Complete Phase 4's shadow learner-evidence loop.
5. Implement the default-off frontend only after those gates pass.
