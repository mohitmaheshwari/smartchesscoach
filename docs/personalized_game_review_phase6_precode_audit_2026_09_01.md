# Personalized Game Review Coach — Phase 6 pre-code audit

Date: 2026-09-01

## Scope status

Phase 6 is already part of the signed `personalized_game_review_coach_scope.md` and `personalized_game_review_coach_spec.md`. Mohit explicitly approved implementation with “build it” after the required validation harness was described: account-only enablement, same-game old/new comparison, structured coach scoring, and instrumentation verification.

## Existing-surfaces audit

Decision: **EXTEND existing**.

- `/game/:gameId` and `GameDecryptionV5.jsx` are the canonical player review. Validation controls must live there and must not create another review route.
- `GET /api/coach/decryption/v5/{game_id}` already owns the legacy-versus-personalized response boundary. Comparison mode extends this endpoint rather than duplicating review generation.
- `users.feature_flags` is the existing per-account experimental-feature authority. The harness adds one namespaced entry there rather than creating an email list or validation-user collection.
- `PERSONALIZED_GAME_REVIEW_COACH_ENABLED` remains the emergency master switch.
- `frontend/src/lib/analytics.js` remains the only custom-event client boundary.
- Existing move-level feedback is not a substitute for a whole-review rubric. Phase 6 therefore needs one new, canonical validation rubric and one private validation-review evidence store.

## Literal internal UI contract

```text
┌ Internal validation · visible only to approved accounts ┐
│ [Review A]  [Review B]                                   │
│ Compare the same game, blinded and counterbalanced.       │
│                                      [Score this version] │
└───────────────────────────────────────────────────────────┘

Score this version
Chess truth          [Correct] [Minor issue] [Critical false claim]
Moment choice        [Strong]  [Mixed]       [Missed the key moment]
Explanation clarity  [Clear]   [Mostly clear] [Confusing]
Personalization      [Specific] [Partly generic] [Generic or false]
Reflection value     [Useful]  [Neutral]     [Leading or unhelpful]
Story coherence      [Coherent] [Loose]      [False connection]
Next action          [Useful] [Weak] [Unsupported/wrong] [Not shown]
Optional note        [.............................................]
                                             [Save this scorecard]
```

All dimension and option labels come from the backend rubric. The frontend does not maintain a second copy.

## Six audit gates

1. **Literal UI mockup:** pass — recorded above.
2. **Pattern/geometry headline:** not applicable — this is an internal validation toolbar and scorecard, not chess teaching. It renders the canonical review unchanged beneath it.
3. **Data-derived thresholds:** pass — Phase 6 introduces no scoring threshold, cohort percentage, or rollout pass mark. The first validation round supplies the evidence used to lock later rollout gates.
4. **Behavior-changing metric:** pass — the harness records completion/reflection/follow-up behavior plus independent human judgments and critical truth failures. It does not treat impressions as success.
5. **Deferred work remains deferred:** pass — no 10% rollout, 100% rollout, legacy deletion, bulk regeneration, Maia/Otter integration, or new detector promotion is included.
6. **Mohit sign-off:** pass — explicit “build it” on 2026-09-01.

## Security and privacy gates

- Global master off always wins.
- Explicit `review_variant` requests are rejected unless the authenticated user has the validation-comparison flag. A/B-to-mode mapping is deterministic and backend-only.
- Validation-account membership is stored by user ID in the existing private user document, never hardcoded by email in application code.
- The scorecard stores rubric IDs, presentation mode, plan/version references and optional reviewer notes. It stores no FEN, PGN, caption body, detector internals, reflection answer, or community data.
- Protocol and mode validation are backend-owned; changing URL parameters cannot grant access.

## Single source-of-truth lock

- Rollout decision: `game_review_contracts.py` plus `users.feature_flags.personalized_game_review_coach`.
- Rubric definitions: one backend validation service; the API sends the rubric to the frontend.
- Review chess truth: existing `TeachableEvent` and `GameTeachingPlan`; the harness never reinterprets it.
- Behavior telemetry: existing analytics registry.

## Pre-code verdict

**PASS.** Proceed with the Phase 6 validation harness.
