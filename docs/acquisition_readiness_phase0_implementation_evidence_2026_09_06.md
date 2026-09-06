# Acquisition Readiness Phase 0 — Implementation Evidence

**Date:** 2026-09-06

**Base:** `origin/working-code` at
`8b6e5ac34580e63d971e359eb18e911ff993f9a4`

**Scope:** privacy-safe, account-attributable product measurement only

**Deployment:** not deployed; Claude owns push and production deployment

## Outcome

The existing PostHog path now captures explicit allowlisted events only. It no
longer records sessions, automatically captures DOM interactions or lifecycle
page events, or retains URL query strings/fragments in automatic URL
properties. This specifically prevents login/session tokens present in URLs
from entering analytics through `$current_url` or referrer properties.

Authenticated real players are identified with the existing opaque `user_id`.
No email, name, platform username, rating, game/session identifier, FEN, line,
caption, PGN, free text, or payment identifier is sent by the central capture
boundary. Staff, reviewers, demo/dev accounts, and explicitly excluded accounts
receive `metrics_eligible=false`. Identity resets on logout, expired auth, and
account switching.

MongoDB remains authoritative for chess facts, learning, mastery, transfer and
billing. No new analytics collection, event registry or journey store exists.

## Files and authority

- `frontend/src/lib/analytics.js`: one event registry, property allowlist,
  pseudonymous identity and actor context.
- `frontend/public/index.html`: PostHog automatic-capture shutdown and URL
  sanitization.
- `backend/routes/auth.py`: exposes only the existing coarse `is_demo` plus new
  `analytics_excluded` provenance booleans to the authenticated client.
- `frontend/src/App.js`, `Layout.jsx`, `Settings.jsx`: auth/logout lifecycle
  wiring.
- `frontend/src/pages/PrivacyPolicy.jsx`: factual disclosure; counsel review is
  still required.
- `docs/product_analytics_source_map.md`: canonical ownership and privacy
  contract.

## Production data compatibility — read only

The deployed database was queried from the backend container without printing
credentials or identities and without writes:

```yaml
users: 125
internal user IDs failing the allowed opaque-ID format: 0
actor classification under the new contract:
  player: 117
  staff: 3
  reviewer: 3
  demo/dev: 2
  explicitly excluded: 0
```

The 117 is a compatibility count, **not a retention denominator**. Existing
ordinary-looking test accounts have not yet been adjudicated, no clean PostHog
window exists, and no target has been locked.

## Verification

| Check | Result |
|---|---|
| Backend analytics-provenance contract | **2 passed** |
| Frontend focused privacy/identity/wiring suite | **25 passed** |
| Complete frontend suite | **29 suites, 148 tests passed** |
| Production frontend build | **passed** with pre-existing hook/source-map/bundle warnings |
| Single direct `posthog.capture` source path | **passed** — application capture remains in `frontend/src/lib/analytics.js`; tests only otherwise |
| `git diff --check` | **passed** after removing two Markdown whitespace violations |

## Inconclusive and pre-existing evidence

- `backend/tests/test_all_flows.py` is not a self-contained suite. It terminated
  on its first request because no HTTP server was running. No assertion ran.
- `tests/test_runtime_bypass_hardening.py` produced nine passes and one failure.
  Upstream `origin/working-code` already contains both sides of the
  contradiction: `MoveEvaluationRequest` includes `submission_id`, while the
  test asserts that only `puzzle_id` and `user_move` may exist. This slice does
  not modify either file.
- A normal clean `npm ci` fails on the React 19 / `react-day-picker@8.10.1`
  peer-range conflict. `npm ci --legacy-peer-deps` installed 1,558 locked
  packages, after which the full tests and build passed. This is tracked as
  `AR-QA-004`, not hidden as a successful ordinary clean install.

## Score and closure decision

No frozen product or acquisition score changes from code completion alone.
`AR-PRIV-001` is improved in source but remains open until:

1. Claude independently reviews the diff;
2. counsel reviews the disclosure and consent/withdrawal requirements;
3. deployed PostHog inspection proves the configuration and payload; and
4. a fixed clean window produces reproducible, correctly excluded metrics.
