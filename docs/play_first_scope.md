# Play first — scope

Status: DRAFT, awaiting Mohit's sign-off. No code until then.
Plain English on purpose. Decided 2026-09-18.

---

## The problem, in three numbers

Measured on production today:

- The diagnostic asks a new person for **20 chess positions**.
- **42% answer zero.** **5% finish.** Half of those who answer anything quit by
  position 2.
- Meanwhile **62% of users go and play the coach**, and only 22% touch a lesson.

People are telling us what they want. They want to play. We hand them a
twenty-question exam first.

And the exam is not even the first wall. `/welcome` — the activation hub whose
own scope says "value-first, no account wall" — sits behind `ProtectedRoute`.
An anonymous visitor's `/auth/me` returns 401, so they are bounced back to the
landing page. **The account wall is still the first thing a stranger meets.**
The hub moved it by one step; it did not remove it.

The launch readiness report scores Coaching Quality **8.0** and marks it *not*
a blocker. Activation (3.0) and First Session (3.5) are the only two blockers
in the whole report. This scope is about those two and nothing else.

---

## What a stranger sees

### 1. Landing

One button, above everything else:

    ┌──────────────────────────────────────────┐
    │                                          │
    │   Play a game. I'll tell you what        │
    │   I noticed.                             │
    │                                          │
    │        [ Play the coach ]                │
    │                                          │
    │   No signup. Takes about 5 minutes.      │
    └──────────────────────────────────────────┘

No email. No username. No puzzles. Clicking it starts a game.

### 2. The game

Exactly the Play-with-Coach we already have. Nothing new is built here — it is
the part of the product that already works and that 62% of users find on their
own.

### 3. The moment the game ends

This is the whole point of the change. One finding, from **their** game:

    ┌──────────────────────────────────────────┐
    │  Here's the thing I noticed.             │
    │                                          │
    │  [ board: the position it happened in ]  │
    │                                          │
    │  Twice you moved a piece to a square     │
    │  your opponent could simply take it on.  │
    │  Move 14 was the one that cost you.      │
    │                                          │
    │  That's the pattern I'd work on first.   │
    │                                          │
    │  [ Save this and keep going ]            │
    └──────────────────────────────────────────┘

Only now do we ask for an account, and the sentence is "save this", not
"sign up".

### 4. If they say no

They lose nothing we promised them. They already got the finding.

---

## What has to change

1. **A guest can play.** A visitor gets a real session without an email. That
   is the only genuinely new mechanism in this scope.
2. **The landing leads with the game**, not with pricing or a feature list.
3. **The end of a guest's first game produces one finding** from that game.
4. **The account ask moves** to after the finding.
5. **The 20-position diagnostic stops being the front door.** It is not deleted
   — it stays available for anyone who wants it, and `diagnostic_v2` work is
   untouched. It simply stops being what a stranger meets first.

The finding itself uses what we already have: the game is analysed the way
every coach game already is, and the finding comes from the existing
cognitive-gap path. **No new detector is needed and none of this waits on
detector review.**

---

## How we know it worked

Today's baseline, so the comparison is honest later:

| | today |
|---|---|
| finish the diagnostic | **5%** (2 of 40) |
| answer zero positions | **42%** |
| reach any coaching at all without an account | **0%** — it is not possible |

After:

- **% of landing visitors who finish a game** — the number that matters
- **% who see a finding** (should be ~100% of finishers; if not, the analysis
  is too slow and that is the bug)
- **% who create an account after seeing it** — the real conversion
- **time from landing to first coach sentence** — target under two minutes

If finish-a-game does not clearly beat 5%, the idea is wrong and we say so.

---

## Risks, stated up front

- **Junk accounts.** Guest sessions create records. They need a marker and a
  cleanup, or every future metric is polluted by people who bounced. Guests
  must be excluded from user counts by default.
- **Engine cost.** A guest game costs Stockfish time from someone who may never
  return. Acceptable at our size; revisit if it is ever abused.
- **Abuse.** No email means no rate limit by identity. Needs a per-IP cap.
- **The finding could be wrong.** It comes from the same cognitive-gap path as
  everything else, and the mate-gate fix today changed 6,153 labels precisely
  because that path had been wrong. A wrong first impression is worse than a
  bland one, so the finding must come from the categories we trust most, and
  say nothing at all rather than say something unverified.

---

## Not in this scope

- Detector review and promotion — parked. Coaching is 8.0 and not the blocker,
  and the queue is built and waiting whenever we want it.
- Tier C tactics, endgame build-out, second lesson category — all behind this
  door. See `docs/coaching_buildout_plan_2026_09_18.md`.
- Deleting the diagnostic. It stops being the front door; it does not go away.
