# Acquisition Readiness Phase 2 — Activation Import Implementation Evidence

**Date:** 2026-09-06

**Branch:** `codex/acquisition-readiness-program-v1`

**Scope:** `docs/acquisition_readiness_phase2_activation_import_precode_audit_2026_09_06.md`

**Status:** SOURCE COMPLETE — independent review and deployed journey proof pending

## Outcome

The existing account-link → game-import boundary is now explicit and honest:

- onboarding calls the registered authenticated `POST /api/import-games`
  authority once for every account verified in that onboarding session;
- the nonexistent `POST /api/games/sync` caller and its swallowed failure are
  removed;
- any import HTTP failure is shown to the player, stops first-aha navigation,
  emits no import-complete event and does not mark onboarding complete;
- profile persistence, which marks onboarding complete, runs only after every
  selected import succeeds;
- a reload after an interrupted import restores previously linked account
  names as verified, retryable state instead of redirecting the player away;
- `imported=0` is represented honestly as `already_current`, not a failure and
  not a false claim that new games were found; and
- both onboarding and the existing Import Games page emit the canonical
  privacy-filtered `funnel_import_done` interaction event only after a
  successful server response.

The event remains reach telemetry, not product truth. Mongo `games` and
`analysis_queue` records, plus the import endpoint response, remain the
authority for whether games were actually stored and queued.

## Analytics contract

The two player entry points use `ANALYTICS_EVENTS.FUNNEL_IMPORT_DONE` and pass
only fields already accepted by the Phase 0 allowlist:

- `source`: `onboarding` or `import_page`;
- `status`: `new_games` or `already_current`; and
- `total_items`: the backend-reported number of newly stored games.

No email, username, platform account identifier, game id, PGN, FEN or URL is
sent. Phase 0's player-eligibility context still determines whether this event
is eligible for product-metric analysis.

## Verification evidence

### Focused frontend contract

Command:

```powershell
npm test -- --runInBand --watchAll=false src/pages/Onboarding.test.jsx src/lib/analyticsWiring.test.js src/lib/analytics.test.js
```

Result: **3 suites passed, 30 tests passed, 0 failed**.

The component cases cover successful import, visible failure, import-before-
completion ordering, retry state after reload, already-current success and
both linked accounts being imported. Static analytics checks cover both
player entry points and the canonical event registry.

### Complete frontend regression

Command:

```powershell
npm test -- --runInBand --watchAll=false
```

Result: **30 suites passed, 162 tests passed, 0 failed**.

### Production frontend build

Command:

```powershell
npm run build
```

Result: **exit 0**. Existing chess.js source-map, React hook and bundle-size
warnings remain visible and are not represented as resolved by this phase.

### Static last-wire proof

No non-test file under `frontend/src` contains `/games/sync`. The only import
callers changed by this phase target the already registered `/api/import-games`
route.

## Required proof before closure or deployment

This phase must not be marked live or used to raise a product score until all
of the following exist:

1. independent review of the complete Phase 2 diff against the canonical base;
2. a deployed non-admin browser journey proving link → import → first aha;
3. a deployed failure-path check proving an import error remains visible and
   retryable;
4. Mongo evidence that the journey stored/recognized games and queued analysis;
5. PostHog inspection proving one allowlisted import-complete event, no raw
   identity fields and correct player-metric eligibility; and
6. a deployed already-current case proving zero newly imported games does not
   generate misleading copy.

No production write, push, deployment or score change was performed in this
phase.
