# QA Gate — Personalized Game Review production API

**Repo:** smartchesscoach  
**Deployment:** production at chessguru.ai  
**Engineer:** Codex implementation; Claude integration/deployment  
**Date:** 2026-09-01  
**Mode:** Production

## Scope

This gate covers the deployed Personalized Game Review Coach API, Phase 6
validation surface, caption-pipeline dependency, and the requested validation
account `bhutramohit@gmail.com`.

## Components touched

| Component | Main paths |
|---|---|
| Review contracts and planner | `backend/services/game_review_*.py` |
| Learning adapter and curriculum evidence | `backend/services/review_learning_adapter.py`, `backend/services/personal_curriculum.py` |
| Caption and V5 review projection | `backend/services/caption_pipeline.py`, `backend/services/game_decryption_v5_service.py` |
| Validation API and UI | `backend/routes/coach.py`, `frontend/src/components/review/` |

## Layer 1 — unit and build evidence

- Current-base backend Phase boundary: **175 passed**.
- Personalized-review UI, validation panel, and analytics: **14 passed**.
- Current-base production frontend build: **passed**.
- Deployed imports: contracts, planner, shadow runtime, validation service,
  caption pipeline, and V5 service all import successfully.
- Deployed planner: `personalized_game_review_planner.v1`.
- Deployed V5 coaching version: `138`.

The pre-fix current-base boundary was **33 failed / 138 passed**. The drift
resolution produced the passing results above without changing production
detector authorization.

## Layer 2 — production integration evidence

Read-only production checks found:

- account resolves to `user_8b599930d7ef`;
- 766 owned games and 735 corresponding analyses;
- recent complete reviews are stored at V5 version 137;
- no V5 version 138 review exists yet for this account;
- all sampled recent analyses have no stored personalized teaching plan;
- unauthenticated `/api/auth/me` returns `401`;
- unauthenticated personalized V5 route returns `401`;
- the account has no `personalized_game_review_coach` feature enrollment.

Production rollout state after controlled enablement:

```text
PERSONALIZED_GAME_REVIEW_COACH_ENABLED=true
PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT=validation
CAUSAL_PERSONAL_CAPTIONS_ENABLED=0
DEV_MODE=false
GIT_COMMIT=7bc99da4ee61542ca9050dc7b698368045d07835
```

Exactly one account is enrolled. An existing production session token was not
extracted or reused from MongoDB. With Mohit's explicit approval, the test
created a random ten-minute session, used it only inside the backend container,
and deleted it afterward. The browser-control fallback remained unavailable
because of the known Windows OS 206 sandbox-helper failure.

Authenticated production evidence:

- `/api/auth/me`: `200`, exact requested account;
- one no-eligible-event game regenerated `137 -> 138` and honestly produced no
  personalized plan (`comparison_ready=false`);
- one current-schema `simple_hang` game regenerated `137 -> 138`;
- both A and B completed with 71 moves;
- validation packets were identical after removing only `active_variant`;
- both packets reported `comparison_ready=true`;
- exactly one variant projected the personalized plan;
- stored shadow payload selected one event, rejected zero, and contained one
  plan chapter;
- the public plan had a server-owned `plan_id` and schema, with no unsupported
  `next_action` (correct for Caption-grade evidence);
- validation submission returned `200`, exposed only the public scorecard
  fields, and appeared on the next read;
- the automated scorecard was deleted after verification;
- the temporary session was deleted, with zero matching sessions remaining.

Legacy isolation evidence combines the legacy member of the blinded response
(no personalized plan) with the deployed access resolver against a real
non-enrolled user document (`enabled=false`). The remaining 119 accounts are not
enrolled. A second-account authenticated UI run remains part of manual QA, not
this account-scoped automated test.

## Layer 3 — end-to-end

**API E2E passed.** Remaining human evidence:

1. Visually review A and B without revealing their mapping.
2. Submit genuine coach ratings through the UI (the automated QA scorecard was
   deliberately removed so it cannot contaminate the study).
3. Open one review as a non-enrolled account during manual regression QA.

## Gate status

**Scoped API evidence: green.** Configuration, account isolation, V5
regeneration, blinded projection, plan persistence, validation submission, and
cleanup all behaved as designed. Visual quality and second-account UI isolation
remain for Mohit's manual gate.

## Mohit's gate

**Verdict:** Pending

**Notes:** Await the authenticated, enrolled-account evidence above.
