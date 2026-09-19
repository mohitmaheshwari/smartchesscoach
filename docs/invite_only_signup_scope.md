# Invite-only signup

**Status:** building, 2026-09-19. Decisions confirmed by Mohit.

## What this is

ChessGuru goes on social media, but only people Mohit chooses get in. The
public site keeps its marketing page; the signup call-to-action is replaced by
a "request an invite" form. Mohit reviews requests in Admin and invites with
one click. The invited person then signs in with Google and their account is
created on first login.

## What a visitor sees

- Landing page: unchanged marketing. Every "Build my plan" CTA opens the
  invite-request form instead of Google sign-in.
- Login page: "Sign in" stays (existing users must keep working). The
  create-an-account mode is hidden.
- An un-invited person who tries Google sign-in is NOT shown an error. They
  land back on the invite form with a friendly line saying ChessGuru is
  invite-only right now and their email is on the list.

## What Mohit sees

- Admin → Waitlist: every request with name, email, note, when.
- One "Invite" button per row. No email is sent by the product; Mohit tells
  them however he likes. (Confirmed: he does NOT want an email on each
  request — he will check the list.)

## How the gate works

Account CREATION is blocked; authentication is untouched. Existing users —
all ~120 of them, plus Farhan — keep signing in exactly as now, because
Google callback matches on `email` and finds them.

Three creation paths are gated:
  - `POST /auth/register`
  - `GET  /auth/google/callback`  (only the insert-new-user branch)
  - `POST /auth/google/mobile`    (same)

A creation is allowed when EITHER
  - `SIGNUPS_OPEN=true` (env, default false — the pre-launch posture), OR
  - the email has a `waitlist` row with `status: "invited"`.

So "one-click Invite" means: set that row to invited. Nothing else is
required, and no password is ever issued.

## Data

`waitlist` collection, one row per email:
  email (unique, lowercased), name, note, source, status (pending|invited),
  created_at, invited_at, invited_by.

## Deliberately NOT in scope

- No invite emails from the product (Mohit's call).
- No invite codes or tokens — the allowlist is the email itself.
- No change to billing, onboarding, or anything post-login.
- Existing `POST /admin/users` stays as-is; it remains a valid way to
  pre-create someone.

## How we will know it works

- An un-invited new Google email cannot create an account, and lands on the
  invite form.
- An invited email can, on first Google sign-in.
- Every existing user still logs in. This is the one that must not break.
