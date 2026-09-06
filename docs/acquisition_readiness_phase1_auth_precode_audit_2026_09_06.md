# Acquisition Readiness Phase 1 — Authentication Pre-code Audit

**Date:** 2026-09-06

**Program:** `docs/acquisition_readiness_program_scope.md`

**Status:** PASS — implementation may begin for the bounded slice below

## Bounded slice

Harden the existing authentication routes without creating a second auth
system:

1. normal web authentication uses the existing Secure, HttpOnly, SameSite
   session cookie only;
2. web Google OAuth returns `?auth=success` without a session token;
3. email/password login and registration stop returning session tokens in JSON;
4. browser code stops reading URL tokens or persisting session tokens and
   removes legacy stored web tokens;
5. bearer authentication remains available only for sessions explicitly marked
   `is_mobile=true`;
6. the native Google flow retains its app deep-link token, but starts OAuth in
   the system browser so an initiator cookie can bind the callback;
7. OAuth state is authenticated, expiring, one-browser-bound, URL encoded, and
   contains only an allowed platform plus a safe local frontend path; and
8. the existing PostHog URL sanitizer remains defense in depth, not the primary
   token control; and
9. the demo mobile-login route is unavailable outside `DEV_MODE` and its
   synthetic identity can never alias a real user.

## Gate 1 — Scope and architecture

**PASS.** Mohit approved the Acquisition Readiness program. This closes
`AR-AUTH-001`, `AR-AUTH-002` and the subsequently discovered `AR-AUTH-003` on
the canonical `routes/auth.py` and `App.js`
paths. It does not add an identity provider, token store, auth database, or
frontend auth context.

## Gate 2 — Web/mobile contract before code

**PASS.** The transport matrix is fixed:

| client | credential transport | response exposure |
|---|---|---|
| Web Google OAuth | Secure HttpOnly SameSite=Lax cookie | no token in URL or JSON |
| Web email/password | Secure HttpOnly SameSite=Lax cookie | no token in JSON |
| Native Google OAuth | bearer token in app deep link, persisted by the native app | mobile session only |
| Native Google access-token exchange | bearer token in JSON | mobile session only |
| Dev mode | localhost cookie | no token response field |
| Demo mobile QA | bearer token in JSON | `DEV_MODE` only; hashed demo identity; mobile session only |

A cookie takes precedence if both cookie and Authorization header are present.
A bearer token must resolve to a session carrying `is_mobile=true`.

## Gate 3 — OAuth state contract

**PASS.** State contains version, random nonce, exact platform, safe local path,
and issued-at time. It is authenticated with HMAC-SHA256 using the already
required Google client secret and URL-safe encoded. The same nonce is stored in
a short-lived Secure/HttpOnly/SameSite=Lax cookie scoped to the Google auth
routes.

The callback rejects missing, malformed, tampered, expired, future-dated,
wrong-platform, unsafe-redirect, missing-cookie and nonce-mismatch state before
calling Google or writing a session.

## Gate 4 — Redirect and failure behavior

**PASS.** A destination is accepted only when it parses as a local absolute
path beginning with one `/`, with no scheme, host, query, fragment or control
characters. Invalid values become `/home`; callback state itself still fails if
tampered.

OAuth/auth failure returns to the public app without preserving a browser
token. Analytics identity resets when auth is not valid. Product pages remain
unaware of the credential value.

## Gate 5 — Deferred work remains deferred

**PASS.** This slice does not absorb password reset/email verification, MFA,
account linking policy, session-management UI, OAuth provider expansion,
authorization/RBAC redesign, Claude's five perimeter fixes, or production
deployment.

## Verification required before handoff

- pure unit tests for safe redirects and signed state success/failure cases;
- auth dependency tests proving web-cookie acceptance, mobile-bearer acceptance,
  web-bearer rejection and cookie precedence;
- response-contract tests proving web login/register contain no token;
- frontend tests proving web token cleanup and mobile deep-link preservation;
- full frontend suite and production build;
- relevant backend auth/security suites;
- static scan proving no normal web token query/persistence path remains; and
- independent Claude review before production deployment.
