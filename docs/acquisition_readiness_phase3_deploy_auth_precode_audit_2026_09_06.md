# Acquisition Readiness Phase 3 — Deployment Authentication Pre-code Audit

**Date:** 2026-09-06

**Program:** `docs/acquisition_readiness_program_scope.md`

**Status:** PASS — implementation may begin for the bounded integration repair

## Bounded slice

Make the existing Phase 8 strict deployment verifier compatible with the
Phase 1 browser/mobile authentication boundary without weakening either:

1. every verifier request representing a web player sends the credential as
   the HttpOnly-cookie equivalent `session_token` cookie;
2. no verifier request sends that web credential as `Authorization: Bearer`;
3. the preferred CLI and environment names become `--session-token` and
   `DEPLOY_VERIFY_SESSION_TOKEN`;
4. the prior `--auth-token` and `DEPLOY_VERIFY_AUTH_TOKEN` inputs remain a
   value-only migration alias for one deployment transition, but transport is
   still cookie-only; and
5. the one canonical deploy script forwards the preferred session secret and
   continues to fail closed when no credential is configured.

## Gate 1 — Verified integration defect

**PASS.** Phase 1's `get_current_user()` now accepts a bearer credential only
when the stored session has `is_mobile=true`; an ordinary browser session must
arrive in the `session_token` cookie. Phase 8's `verify_deployment.py` currently
sends `Authorization: Bearer <ordinary session>` for `/auth/me`, canonical
Game Review and the complete non-admin journey. Its own help text recommends a
normal login session. Those contracts cannot both pass as written.

This is recorded as `AR-QA-005`. The defect is source-level and deterministic;
no production request or secret inspection is needed to reproduce it.

## Gate 2 — Existing authority

**PASS.** No new authentication mechanism, session type, feature flag, cohort
list or deployment path is required:

- web credential authority: the existing `session_token` cookie;
- mobile credential authority: the existing `is_mobile=true` bearer session;
- journey verifier: `backend/scripts/verify_deployment.py`; and
- release path: `scripts/deploy.sh`.

The repair changes the verifier's transport, not the authentication policy.

## Gate 3 — Failure and compatibility contract

**PASS.** Missing session credentials remain a required-check failure in the
deploy script. An invalid/expired web session still produces a failed auth
check. The legacy option/env name may populate the same in-memory session
value during migration, but it never selects bearer transport and is not
forwarded as a second credential.

No credential value is printed, persisted in evidence, committed or sent to a
different host. The configured base URL remains under the existing deployment
operator's control.

## Gate 4 — Numeric and source-of-truth discipline

**PASS / NOT APPLICABLE.** This repair selects no threshold, ranking or cohort
size and creates no domain data source. It preserves the existing eight-check
Phase 8 gate and its strict required-check semantics.

## Gate 5 — Required verification

- unit test proves `/api/auth/me` receives the session cookie and no
  Authorization header;
- unit tests prove every GET/POST in both complete-journey branches receives
  the same cookie and no Authorization header;
- source test proves the deploy script requires/forwards
  `DEPLOY_VERIFY_SESSION_TOKEN` and does not forward the old variable;
- existing Phase 8 verifier, evidence and prerequisite suites pass;
- Phase 1 authentication transport suite remains green;
- `git diff --check` passes; and
- real deployment proof remains Claude-owned and must show the strict auth,
  contract and journey checks all PASS.

## Deferred work

This slice does not deploy, mint/rotate sessions, enroll users, change CORS,
alter auth callbacks, run production backfills, change detector authorization,
modify the Phase 8 denominator or raise any acquisition score.
