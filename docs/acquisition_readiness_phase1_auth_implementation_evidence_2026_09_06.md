# Acquisition Readiness Phase 1 — Authentication Implementation Evidence

**Date:** 2026-09-06

**Branch:** `codex/acquisition-readiness-program-v1`

**Scope:** `docs/acquisition_readiness_phase1_auth_precode_audit_2026_09_06.md`

**Status:** SOURCE COMPLETE — independent review and live web/native proof pending

## Outcome

The canonical authentication path now separates browser and native credentials:

- browser Google OAuth, email login and registration use an HttpOnly session
  cookie and do not return or accept a normal web token through a URL, JSON
  response or persistent browser storage;
- native Google OAuth still returns an app deep-link bearer token, and the
  access-token exchange still returns a bearer token, but the resulting
  session is explicitly marked `is_mobile=true`;
- the auth dependency accepts bearer credentials only for such mobile
  sessions, while a valid cookie takes precedence when both transports are
  present;
- logout revokes the native mobile session and clears the local native token;
- invalid and expired explicit credentials return `401` instead of falling
  through to the development identity; and
- legacy browser bearer callers in `NextRecommendation` and
  `MistakeMastery` now use the session cookie.

## OAuth state protection

Google OAuth state now contains only version, issued-at time, random nonce,
allowed platform and a safe local redirect path. It is URL-safe encoded and
authenticated with HMAC-SHA256 using the configured Google client secret. The
same nonce is stored in a ten-minute HttpOnly, SameSite=Lax initiator cookie
scoped to `/api/auth/google`.

Before any Google token exchange or database write, callback processing rejects:

- missing or malformed state;
- a bad signature;
- expired or excessively future-dated state;
- a missing or mismatched browser nonce;
- an unsupported platform; and
- a redirect containing a scheme, host, query, fragment, double slash or
  control character.

The normal browser callback now returns `<safe path>?auth=success`; the
credential is present only in the Secure HttpOnly session cookie. The mobile
flow begins at ChessGuru's backend in the system browser so that the nonce
cookie is present when Google returns, then deep-links the mobile credential
to the app as before.

## Additional critical finding closed in source

The final token-path scan discovered `AR-AUTH-003`: `/auth/demo-login` was
available without a `DEV_MODE` check, accepted an arbitrary email and reused
the real account's `user_id` when that email already existed. Before this
phase's mobile-only bearer restriction, that was an account-impersonation
path.

The route now rejects before database access outside `DEV_MODE`. In development
it creates a deterministic hashed `demo_` identity rather than looking up by
email, so it cannot alias a real user and its analytics-safe `user_id` cannot
contain an email. Its returned session is explicitly mobile-only.

## Verification evidence

### Focused backend security contract

Command:

```powershell
C:\Users\MIISCO\smartchesscoach\backend\.venv\Scripts\python.exe -m pytest tests/test_auth_transport_security.py tests/test_auth_analytics_context.py -q
```

Result: **35 passed**, with two existing dependency/deprecation warnings.

The tests exercise cookie acceptance, mobile-bearer acceptance, web-bearer
rejection, cookie precedence, expired/invalid credential failure, safe redirect
selection, signed-state success and every fail-closed case, nonce cookie
issuance, native redirect initiation, rejection before outbound Google access,
successful web/mobile callbacks, tokenless email login/registration, production
and localhost cookie settings, production demo-route closure and native logout
revocation.

### Complete frontend regression

Command:

```powershell
.\node_modules\.bin\craco.cmd test --watchAll=false --runInBand
```

Result: **30 suites passed, 156 tests passed, 0 failed**.

### Production frontend build

Command:

```powershell
.\node_modules\.bin\craco.cmd build
```

Result: **exit 0**. The existing chess.js source-map warning, hook warnings and
bundle-size warning remain visible; none were introduced as successful-build
evidence or silently suppressed.

### Existing broader auth/bypass tests

Result: **7 passed, 33 environment-skipped, 1 failed**. The single failure is
the pre-existing Phase 0 contradiction in
`test_runtime_bypass_hardening.py`: the test requires exactly
`{puzzle_id, user_move}` while the production model also intentionally carries
`submission_id`. It is recorded as existing QA debt and is unrelated to auth.

### Static credential-path inspection

- no `auth=success&token=...` browser callback remains;
- no browser code reads a token from `location.search`;
- no normal browser component reads `authToken` or sends its own bearer header;
- browser startup deletes legacy `session_token` and `authToken` storage; and
- remaining bearer-return paths are the two explicit native Google paths and
  the `DEV_MODE`-only demo mobile path. Other `session_token` occurrences are
  server-side session records/cookies, not web response exposure.

## Required proof before closure or deployment

This phase must not be marked live or used to raise a product score until all
of the following exist:

1. independent review of the complete diff against the canonical base;
2. confirmation that Claude's exact-origin credentialed CORS change is present;
3. real browser tests for Google login, email login, registration, protected
   reload, logout, malicious redirect and URL/history/localStorage absence;
4. a real Android/iOS test for system-browser start, callback deep link,
   authenticated protected request and logout revocation; and
5. a live response inspection proving Secure/HttpOnly/SameSite cookie behavior
   at the production proxy boundary.

No production write, push, deployment or score change was performed in this
phase.
