# Admin "view as user" — see the product through their eyes

## Why

2026-09-17: Mohit sat with Farhan, whose pages appeared empty. Diagnosing it
took reading nginx logs, comparing accounts, checking sessions and cookie
origins. None of that was available in the moment, in front of the person.

The ask: a super-admin can pick a user and browse the product exactly as that
user sees it — same home page, same coach message, same lesson, same puzzle
supply — without asking them for anything.

## The shape

A banner is pinned to the top of every page for as long as it is active:

    ┌────────────────────────────────────────────┐
    │ 👁  Viewing as Farhan Hassan · read-only    │
    │    farhan.engineer07@gmail.com     [ Exit ] │
    └────────────────────────────────────────────┘

Every page below it renders from that user's data.

## Read-only, enforced at one choke point

Decided with Mohit, 2026-09-17. Writes are blocked, not sandboxed.

This product's entire premise is that a player's coaching reflects *their*
play. If an admin can solve a puzzle while viewing as someone, that person's
mastery state, decay model and "you have improved" message become partly
about somebody else's moves — and there is no way to tell afterwards which
were theirs.

Enforcement lives in `get_current_user`, which every authenticated endpoint
already depends on. While a view-as session is active, any request whose
method is not GET/HEAD/OPTIONS is refused with 403. A new endpoint cannot
forget to opt in, because it never opts in — it inherits the block from the
dependency it already uses.

The one exemption is the exit endpoint, which must work while a session is
active.

## Rules

- **Who:** `super_admin` only, re-checked on every request through the
  existing `require_super_admin` conditions (role *and* the admin email
  allowlist). If the admin's role is revoked mid-session, the next request
  stops resolving.
- **Who cannot be viewed:** another `super_admin`. Nothing in this feature
  should be a route to a higher privilege than the caller already has.
- **Expiry:** 30 minutes, and one active session per admin.
- **No credential exposure:** a fresh token is minted for the view-as
  session. The target's own `session_token` is never read and never returned.
- **Audit:** every start and end is written to `admin_view_sessions` with the
  admin, the target, the time and the IP, and rows are kept after the session
  ends.
- **The admin stays logged in as themselves.** `session_token` is untouched;
  the view-as token is a second, separate cookie. Exiting is one request and
  never risks logging them out.

## Scope

- NEW `backend/services/admin_view_as.py` — session lifecycle and the rules.
- `backend/routes/auth.py` — `get_current_user` resolves a view-as session and
  applies the write block; `/auth/me` reports `viewing_as` so the UI can
  render the banner.
- `backend/routes/admin.py` — start and exit endpoints.
- NEW `frontend/src/components/ViewAsBanner.jsx`, mounted app-wide.
- `frontend/src/pages/AdminDashboard.jsx` — a "View as" action per user.

## Not in scope

- Sandboxed writes. Considered and rejected above.
- Viewing as a user who has never logged in — nothing stops it, but there is
  nothing to see.

## Acceptance

1. With a view-as session active, `GET /api/home/dashboard-v2` returns the
   target's data, byte-identical to what the target receives.
2. Every non-GET request returns 403 while it is active, except the exit.
3. A non-super-admin cannot start one, and cannot forge one by setting the
   cookie.
4. Starting a session against a `super_admin` target is refused.
5. `/auth/me` reports who is being viewed, so the banner cannot be missed.
6. Exiting restores the admin's own identity on the very next request.
