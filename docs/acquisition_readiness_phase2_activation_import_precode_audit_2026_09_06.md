# Acquisition Readiness Phase 2 — Activation Import Pre-code Audit

**Date:** 2026-09-06

**Program:** `docs/acquisition_readiness_program_scope.md`

**Status:** PASS — implementation may begin for the bounded slice below

## Bounded slice

Repair the existing account-link → game-import last wire and make its reach
observable through the existing analytics authority:

1. onboarding calls the existing authenticated `/api/import-games` route for
   every account successfully linked during that onboarding session;
2. a failed import is visible and stops the flow before ChessGuru implies it
   has begun learning from games it did not receive;
3. successful onboarding and the existing Import Games page emit the already
   registered `funnel_import_done` event;
4. the event carries only coarse allowlisted fields (`source`, `status`,
   `total_items`) and never a username, platform identity, game id or PGN; and
5. the existing `/api/import-games` response and Mongo game/queue records
   remain server truth. The client event is reach evidence only.

## Gate 1 — Verified current defect

**PASS.** `Onboarding.jsx` calls `POST /api/games/sync` and deliberately catches
and discards any error. The games router documents that route but does not
implement it. The registered working import route is `POST /api/import-games`
in `routes/analysis.py`; `server.py` includes that router at `/api`.

Therefore onboarding currently advances to first-aha/DNA/diagnostic after a
guaranteed `404`, making account verification look like successful import.
This is recorded as `AR-UX-004`.

## Gate 2 — Existing surfaces and authorities

**PASS.** No new route, importer, event registry, analytics store or game store
is needed:

- account verification/link: `/api/settings/link-account`;
- game import and queueing: `/api/import-games`;
- interaction event: `ANALYTICS_EVENTS.FUNNEL_IMPORT_DONE`;
- privacy/property gate: `frontend/src/lib/analytics.js`; and
- product truth: Mongo `games` and `analysis_queue`.

## Gate 3 — Success and failure contract

**PASS.** A linked account is import-eligible using the normalized platform and
username already verified and retained in component state. Each verified
account receives one import request. The flow continues only when every
requested import returns success. `imported=0` is still a successful current
state (the games may already exist); HTTP failure is not.

After success, the event reports:

- `source`: `onboarding` or `import_page`;
- `status`: `new_games` when at least one new game was stored, otherwise
  `already_current`; and
- `total_items`: the number of newly stored games returned by the backend.

The event does not claim analysis, insight, learning or retention.

## Gate 4 — Numeric decision discipline

**PASS / NOT APPLICABLE.** This slice chooses no conversion, retention,
completion or release threshold. `total_items` is observed server output, not
a threshold. The fresh-cohort D1/D7 target remains unavailable until the
locked retention data prerequisites are satisfied.

## Gate 5 — Deferred work remains deferred

**PASS.** This slice does not redesign onboarding, add a background sync
service, change import volume, re-run Stockfish, define review completion,
choose the first-value metric, change Phase 8 eligibility, modify billing, or
touch Claude's perimeter lane.

## Verification required before handoff

- component test proves onboarding calls `/api/import-games` with the verified
  normalized account and never calls `/api/games/sync`;
- component test proves success emits one privacy-safe `funnel_import_done`;
- component test proves import failure is visible, emits no completion event,
  and does not navigate to first aha;
- source test proves both player import entry points use the canonical event;
- full frontend suite and production build pass;
- static scan finds no `/games/sync` player caller; and
- independent review plus deployed PostHog inspection is required before the
  event is treated as measured reach.
