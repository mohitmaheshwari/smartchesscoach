# Acquisition Readiness Phase 0 — Pre-code Audit

**Date:** 2026-09-06

**Program:** `docs/acquisition_readiness_program_scope.md`

**Status:** PASS — implementation may begin for the bounded slice below

## Bounded slice

Create a privacy-safe, attributable product-measurement foundation on the
canonical frontend analytics path. This slice does not change any coaching UI,
chess claim, detector, curriculum decision, billing behavior, deployment, or
production data.

The slice will:

1. keep `frontend/src/lib/analytics.js` as the single event registry and
   capture boundary;
2. disable PostHog session replay, automatic page-view capture, automatic
   page-leave capture, and DOM autocapture;
3. identify authenticated accounts only by the existing internal `user_id`,
   never by email, name, platform username, game id, position, caption, or PGN;
4. attach a coarse actor class and `metrics_eligible` boolean to every explicit
   event so staff, reviewers, demos, dev users, and explicitly excluded accounts
   cannot contaminate player metrics;
5. fail closed on event properties through the central analytics boundary;
6. reset analytics identity on logout; and
7. update the factual privacy disclosure and analytics source map.

## Gate 1 — Scope and surface

**PASS.** Mohit approved the complete Acquisition Readiness program on
2026-09-06. This slice is Phase 0 evidence infrastructure inside that locked
scope. It introduces no new player-facing surface and no new dashboard.

## Gate 2 — Single source of truth

**PASS.** `frontend/src/lib/analytics.js` remains the only frontend event
registry and the only direct `posthog.capture` caller.
`docs/product_analytics_source_map.md` remains the authority split:

- PostHog: product interactions and retention journeys;
- MongoDB: chess, learning, mastery, transfer, and billing truth.

No parallel registry, analytics collection, user model, or journey ledger will
be created.

## Gate 3 — Schema before implementation

**PASS.** The account context is fixed before code:

| field | allowed values | purpose |
|---|---|---|
| `analytics_context_version` | fixed version string | distinguishes the measurement contract |
| `actor_type` | `anonymous`, `player`, `staff`, `reviewer`, `demo`, `excluded` | coarse cohort separation |
| `metrics_eligible` | boolean | the only inclusion switch for player metrics |

Authenticated identity is the existing opaque `user_id`. Email, name, chess
platform username, session id, game id, FEN, move line, caption, free text, and
payment identifiers are prohibited at the capture boundary.

## Gate 4 — Metric honesty

**PASS.** No D1, D7, activation, or retention target is selected in this slice.
The retention data lock correctly rejects the current contaminated candidates.
A target may be locked only after a clean-window export proves that:

1. account identity is stable;
2. `metrics_eligible=true` excludes non-player activity;
3. the event path is explicit rather than automatic browser capture; and
4. the denominator and observation window are stated.

Practice completion will not be represented as real-game transfer. PostHog
interaction events will not overwrite MongoDB learning state.

## Gate 5 — Privacy and failure behavior

**PASS.** Analytics remains non-blocking. Missing or failed PostHog calls do not
change application behavior. Automatic DOM capture and session replay are off.
Only allowlisted primitive properties can leave the page. Identity is reset on
logout to prevent cross-account attribution.

The privacy copy will describe what the implementation actually does and will
remain marked for counsel review; it will not claim broader legal compliance.

## Gate 6 — Deferred work remains deferred

**PASS.** This slice does not silently absorb:

- Claude's five owned perimeter/security fixes;
- URL-token removal or the broader authentication redesign;
- billing/subscription repair;
- consent-management UX or legal sign-off;
- retention target selection;
- new detectors, target-line phases, Stockfish runs, Maia/Otter work;
- coaching UI redesign; or
- deployment and production rollout.

Those stay visible in the approved program baseline.

## Verification required before handoff

- focused unit tests for account classification, capture allowlisting,
  identity/reset behavior, and failure isolation;
- backend contract test proving `/auth/me` exposes demo/exclusion flags without
  exposing new personal data;
- static assertion that PostHog automatic capture and session replay are off;
- `git diff --check`;
- clean frontend build; and
- evidence that no direct `posthog.capture` path exists outside
  `frontend/src/lib/analytics.js`.
