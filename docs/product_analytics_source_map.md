# Product Analytics Source Map

**Status:** Phase A plus Personal Curriculum baseline run-in implemented; live PostHog baseline export pending access  
**Last audited:** 2026-08-28  
**Canonical frontend registry:** `frontend/src/lib/analytics.js` → `ANALYTICS_EVENTS`

## Boundary

PostHog measures product interaction. MongoDB records product and learning
state. Payment-provider webhooks will own paid entitlement. A client event is
never authoritative proof that analysis completed, a skill improved, or money
settled.

No raw PGN, move list, private coaching text, email address or payment
identifier may be sent as an analytics property. Stable internal IDs may be
used only where needed to join a session/focus journey.

## Funnel source map

| Stage | PostHog event owner | Server-side truth | Current coverage |
|---|---|---|---|
| Activation choice | `funnel_activation_cta` from `ActivationHub.jsx` | None; navigation intent only | Live emitter |
| Diagnostic | `diagnostic_*`, `insight_shown` from `DiagnosticPuzzles.jsx` | Diagnostic session/result collections | Start, resume, answer, pause, abandon, completion and training CTA instrumented |
| Import/link | Reserved `funnel_import_done` | Connected account + imported `games` | **Gap:** registry entry exists; no current emitter |
| First aha | `funnel_first_aha` from `Onboarding.jsx` | Onboarding result payload | Live emitter; UI exposure only |
| Review | `funnel_review_opened` from `LabV2.jsx` | `games`, `game_analyses`, review state | **Partial:** open only; no review-complete event |
| Training | `funnel_training_solve` from `PrescribedTraining.jsx` | `puzzle_attempts`, `training_solve_attempts` | Attempt instrumented; completion/return derived server-side |
| Coach Play | `funnel_pwc_started` from `CoachPlay.jsx`; `pwc_insight_shown` from `PostGameReflection.jsx` | `coach_sessions`, `postgame_analyses` | Start and postgame insight instrumented; completion/return derived from server state |
| Home continuity | `funnel_home_*` from `HomePageNew.jsx` | Home payload and session timestamps | View, mirror read, conversation depth and CTA instrumented |
| PIC | `pic_*` from Home and `PICPieceSafetyLesson.jsx` | `user_active_focus` plus canonical evidence envelope | Lesson/start check, Focus Game update and next action instrumented; verdict-view event still missing |
| Personal Curriculum baseline | `curriculum_*`, `learn_viewed`, `progress_viewed`, `explore_opened`, `lesson_started`, `explanation_completed`, `guided_attempt`, `independent_attempt` | Existing recommendation, lesson, practice and mastery stores | Legacy Home/Lab recommendation, Study browsing, Progress, prescribed drills, opening practice, trap practice and endgame attempts instrumented; scheduled review and Back to plan have no honest legacy emitter |
| Paywall | `funnel_paywall_viewed` from `Pricing.jsx` | Billing config | Live emitter; checkout disabled until recurring scope ships |
| Payment | `funnel_payment_attempted`, `funnel_payment_success` from `Pricing.jsx` | Verified provider event and subscription ledger | Legacy emitter retained but unreachable while checkout is disabled; client success is not revenue truth |

## Canonical ownership rules

1. Event IDs are defined once in `ANALYTICS_EVENTS` and imported by emitters.
2. `track()` rejects unknown IDs. Development builds warn; production drops
   them so typos cannot create shadow funnels.
3. Frontend events describe views and actions only.
4. Completion, retention and return metrics are derived from authoritative
   timestamps where possible; do not emit synthetic “returned” events.
5. Paid conversion is counted only from the future idempotent verified
   subscription event ledger, never from `funnel_payment_success` alone.
6. Learning outcomes come from PIC/concept-mastery evidence, never PostHog.
7. Personal Curriculum emitters use `trackCurriculum()`. Its property allowlist
   drops moves, positions, free text, personal data and non-primitive payloads
   before capture; pages must not call raw PostHog APIs for this funnel.

## Required common properties

| Journey | Required properties when available |
|---|---|
| PIC | `cycle_version`, `focus_kind`, `instruction_id`, `evidence_mode`, rollout cohort |
| Coach Play | `session_id`, `instruction_id`, carried-forward flag |
| Home CTA | typed `cta`, conversation-presence flag |
| Diagnostic | puzzle position; completion carries early-exit flag and puzzle count |
| Personal Curriculum | `surface`, `content_type`, canonical `content_id`, `origin`, flag state; recommendation events add stable decision source/ID; attempt events add support level, outcome and coarse position index |

Properties must describe the event at emission time. They must not add a
frontend-computed improvement verdict.

## Baseline status

The repository contains the public PostHog project key but no authenticated
PostHog query credential or connector. Therefore current PostHog funnel counts
and conversion rates are **unknown**, not zero. The production Mongo census in
`backend/scripts/product_loop_census.py` is a separate operational baseline
and must not be mislabeled as the PostHog funnel.

To close this item, an authorized reviewer must export event counts and unique
users for a fixed UTC interval, record the query timestamp/timezone and test-
account exclusions, then observe one staging journey from emission through the
PostHog event inspector. Until then, Phase A A5 is implementation-complete but
evidence-pending.

The Personal Curriculum baseline emitters are code-complete but have not yet
produced a production observation window. Their default `flag_state` is
`legacy_control`, and their schema is
`personal_curriculum.baseline.v1`. Do not compare the future `/learn` variant
until deployment time, exclusion rules, and the fixed UTC baseline interval
are recorded and one end-to-end event is observed in PostHog.

## Known next instrumentation gaps

- Wire `funnel_import_done` at the authoritative successful-link/sync boundary.
- Add a review-completed event only after defining what completion means.
- Add PIC evidence-measured, verdict-viewed, focus-continued and focus-resolved
  events from the canonical backend outcome—not frontend inference.
- Replace legacy payment events with subscription-started/renewed/cancelled/
  failed events derived from the verified provider ledger after scope signoff.
