# Personalized Game Review Coach  Phase 2 Implementation

**Date:** 2026-09-01  
**Status:** COMPLETE  canonical adapters and storage, default off, no visible UI behavior

## Outcome

Phase 2 creates one path from the existing central move decision to future
Game Review teaching:

```text
MoveTeachingDecision
        |
        v
MoveEventContext (upstream detector/content identity; no FEN inference)
        |
        v
TeachableEvent
        |
        +--> backend quick-tag options --> ReflectionPrompt
        |                                  |
        |                                  v
        |                         event-scoped reflection
        |
        +--> future Phase 3 GameTeachingPlan
```

The adapter imports no board parser, engine, detector implementation, database,
network client or LLM. It cannot reinterpret a position. It only projects the
typed output of `caption_pipeline.build_move_teaching_decision` plus explicit
upstream evidence identity.

## Implemented files

- `backend/services/game_review_event_adapter.py`
  - immutable `MoveEventContext`;
  - `MoveTeachingDecision -> TeachableEvent` projection;
  - central shape/principle identity consistency checks;
  - fail-closed downgrade of unsupported evidence to Diagnostic;
  - Silent outcome for skipped, unverified or empty teaching;
  - deterministic Review/PWC identity;
  - default-off V5 response projection with nested Shadow removal.
- `backend/services/review_reflection_service.py`
  - exact backend-tag to options-only prompt projection;
  - stable prompt and reflection IDs;
  - exact shown-option validation;
  - event-scoped, idempotent storage in the existing `reflection_sessions`
    collection;
  - narrow public receipt with no detector provenance.
- `backend/reflect_constants.py` and `backend/quick_tag_registry.py`
  - canonical `none_of_these` ID and label;
  - new two-escape behavior is opt-in only;
  - the existing V1 quick-tag call keeps its original keys and behavior.
- `backend/routes/coach.py`
  - default-off collection of precomputed, authorized events/prompts;
  - flag-off returns the original legacy object unchanged.
- `backend/routes/reflect.py`
  - default-off `/reflect/v2/game-review-event` submission;
  - game ownership is checked before analysis lookup;
  - prompt and event are loaded from server-owned analysis, never accepted from
    the browser;
  - no FEN, PGN, best move, played move or free text in the request contract.
- `backend/data/corpus_snapshots/personalized_game_review_phase2_legacy_contracts_2026-09-01.json`
  - synthetic, credential-free response fixtures for Game Review, Reflect and
    Play with Coach; this is contract evidence, not chess-content authority.

## Locked guards

- `PERSONALIZED_GAME_REVIEW_COACH_ENABLED` remains false by default.
- The shipped V1 quick-tag response does not gain `none_of_these` or a new
  response field unless the new adapter explicitly opts in.
- Gap identities require a stored `move_observation:*` provenance reference.
- Shape/principle identities must equal the corresponding typed ID on the
  central move decision.
- Unknown and Shadow evidence can be audited but cannot speak to a player.
- The API rechecks `final_verified` and the exact authorized surface instead of
  trusting a stored display boolean.
- Nested `teachable_event` and `reflection_prompt` records are removed from the
  public move list; only authorized top-level projections are exposed.
- Reflection includes both `not_sure` and `none_of_these`, records the exact
  options shown, and rejects invented or changed options.
- Reflection storage is one idempotent document per user/game/event and contains
  no raw board position or free text.
- Review and Play with Coach produce identical event identity for the same
  canonical decision packet.

## Verification

Compilation passed for all changed backend modules and routes.

Combined focused and boundary suite:

```text
python -m pytest -q \
  tests/test_game_review_contracts.py \
  tests/test_game_review_event_adapter.py \
  tests/test_review_reflection_service.py \
  tests/test_review_reflection_route.py \
  tests/test_detector_quality_gate.py \
  tests/test_personal_curriculum_contracts.py \
  tests/test_stage4_caption_contract.py
```

Result: **108 passed in 1.72s**.

`git diff --check` passed for the scoped Phase 2 files. The only output was the
repository's existing Windows LF-to-CRLF warning.

The broader central caption boundary suite produced **79 passes and 6 failures**.
The failures are in pre-existing forced-recapture / CoachExtras / SocraticExtras
assertions. Phase 2 does not modify `caption_pipeline`, severity, CoachExtras or
SocraticExtras. They are recorded as an existing baseline, not reported green
and not attributed to this phase.

`python tests/test_all_flows.py` was attempted. It remains inconclusive because
no backend is listening on localhost; the suite stopped on its first HTTP
connection before a product assertion ran.

The Windows unit environment also lacks the transitive `bcrypt` dependency
needed to import the complete auth route. Therefore the V2 route has structural
boundary checks here, while all validation, persistence and receipt behavior is
executed as pure/service tests. A live-backend run remains required before any
visible rollout.

## Deliberately not done

- No GameTeachingPlan selector or numeric moment/question policy (Phase 3).
- No learner-evidence/mastery projection (Phase 4).
- No frontend component or removal of `_generateThoughtOptions` (Phase 5).
- No regeneration/backfill, production write, deployment, commit or feature
  enablement.

## Phase 3 gate

Phase 3 may now generate plans in shadow from authorized events. It must use the
versioned representative corpus, compare candidate planner formulas from data,
and keep every visible surface on the legacy path until human validation and
later rollout gates pass.
