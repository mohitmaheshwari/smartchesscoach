# Sign-up paths — scope

**Status:** ON HOLD. On 2026-11-07 Mohit chose a coach link from the landing page over this flow (shipped). The full sign-up stays unbuilt unless he reopens it.
**Author:** Claude, 2026-11-06, against `origin/working-code` at de61ae1d.
**Mockup:** clickable, all three paths — linked in the sign-off record at the end.

Mohit, 2026-11-06: *"how about sign up, let's ask age, fide rating, and
everything on signup, signup as coach or student."*

---

## 0. Existing surfaces audit

| Existing | What it does today | Use here |
|---|---|---|
| `Login.jsx`, `POST /auth/register` | Name (optional), email and password, or Google. Nothing about who the account is for | **Keep** as the account step. No new fields on it |
| Google sign-in | The account is created at the callback, so sign-up cannot send extra fields. `redirect_to` carries one local path (`auth.py` `_safe_frontend_redirect_path`; `Login.jsx` also has its own allow-list) | The path must be chosen **before** sign-in and finished **after** it |
| `GET /onboarding/status` + `ProtectedRoute` | A new account with no games or linked account goes to `/welcome` | **Extend**: a new account with no path chosen goes to `/start`. Finishing a path sets `onboarding_completed`, which the gate already reads |
| `ActivationHub` (`/welcome`), `Onboarding.jsx` | The adult flow: chess accounts, FIDE rating, goal, self-rated level, why you play | **Keep** as the rest of the player path. Not rebuilt |
| `users.fide_rating` | Saved from onboarding. **Nothing in the backend or frontend reads it** (`git grep` outside `settings.py` finds only the sending line) | Keep collecting it, but say so plainly in section 6: today it changes nothing |
| `users.role` | **A permissions field**: `user`, `student`, `admin`, `super_admin` | **Never written by sign-up.** The path goes in a new field, `account_kind`. A form that could set `role` would be a way to become admin |
| `POST /academy` (`kind: family` or academy), `POST /academy/batch/:id/students`, `give_consent` | Set-up for a family or academy, adding a child, recording consent. `/academy` has an "I am a parent" option, but the parent has to find it | **Reused** for the parent and coach paths. No second copy of child or consent logic |
| First steps placement | Finds a child's level from three tasks | So the parent is **not** asked the child's level |
| Landing page | Written for adult players rated 600–1500 | Its buttons point at `/start`. Its words are not changed here |
| Terms and Privacy (updated 2026-11-06) | No minimum age; under-18s need a parent | The rules this scope follows |

**Decision: EXTEND.** One new page (`/start`) in front of the existing account
step, one small parent home (`/family`), and a new `account_kind` field. The
child, consent and academy logic already exist.

---

## 1. What it is

The first thing a new visitor sees asks who ChessGuru is for: my child, me, or
my students. Each answer leads to a short path that asks only what that person
needs, and ends somewhere useful: a parent's child starting their first class,
a player connecting their games, a coach with an academy ready to fill. Children
do not sign up alone; a child is sent to a parent.

## 2. What the user sees

```
/start  "Who is ChessGuru for?"
  [ My child ]        a parent setting up a child
  [ Me ]              I play and want to improve
  [ My students ]     I coach or run an academy
        │ then Google or email (the existing account step)
        ▼
MY CHILD                     ME                        MY STUDENTS
1 Your name, WhatsApp        1 How old are you?        1 Your name, WhatsApp
2 Child's first name, age,     under 18 → ask a parent 2 Academy name, city,
  why chess                  2 Your name, why you play   how many students
  More details (optional):   3 The existing onboarding   I am 18 or over
    Lichess, Chess.com,        (chess accounts, FIDE     More details (optional):
    FIDE ID, FIDE rating        rating, goal)             FIDE title, FIDE ID
3 What we keep; I am the                               ▼
  parent; I agree                                      "Sunrise Chess is ready.
▼                                                       Add your first child."
"Aarav is ready."                                       → /academy
Start the first class
Send it to a tablet
→ /family
```

A child who picks "Me" and says they are under 18 sees: "Ask a parent to set
this up", with a button that shares the sign-up link.

`/family` is the parent's home: each child with their next class, class link and
report link, plus "Add another child" and "Stop and delete".

## 3. In scope (V1)

- `/start` with the three cards, in the kids look. The choice survives the
  Google redirect (kept in the browser, checked again on the server).
- `account_kind` on the user: `parent`, `player` or `coach`. Written once, by a
  new route. Sign-up never touches `role`.
- **Parent path:** name, WhatsApp, child's first name, age, why chess; optional
  Lichess, Chess.com, FIDE ID and FIDE rating; the consent points with two
  unticked boxes. Creates the family and child through the existing code and
  records the same consent record as the consent page, text version included.
- **Player path:** age; under 18 goes to "Ask a parent"; 18 and over gives name
  and why you play, then the existing `/welcome` flow.
- **Coach path:** name, WhatsApp, academy name, city, roughly how many students,
  a required "I am 18 or over" tick; optional FIDE title and ID. Creates the
  academy and a first batch through the existing code, then opens `/academy`.
- **Age** is stored as a year of birth only, worked out from the age given. No
  date of birth.
- `/family`, the parent's home, in the kids look. After sign-in a parent goes
  there and a coach goes to `/academy`, not the adult Home.
- `ProtectedRoute`: a new account with no `account_kind` and no onboarding goes
  to `/start`. **Accounts that already have games, a linked account or
  `onboarding_completed` are never sent there.**
- Landing and Login "create account" links lead to `/start`. Sign-in is unchanged.
- Allow-lists updated: `/start` and `/family` in `Login.jsx`, and the mobile
  app's sign-in return.
- Analytics: which path, each step reached, path finished.

## 4. Explicitly out of scope (V1)

- **Asking the existing 132 or so users who the account is for.** A separate
  one-time prompt.
- **Rewriting the Landing page for parents.** It needs its own design pass.
- **Automatic FIDE lookup.** We store the ID. Whether we may read ratings from
  FIDE automatically is unchecked (section 6).
- **Using the FIDE rating in coaching.** Stored only, as today.
- **Phone number checks by OTP, and email verification.**
- **Coaches inviting parents in bulk, or importing a student list.**
- **The coach pages in the kids look.**
- **Children's own logins.** A child still uses the class link.
- **Payment.**

## 5. Success criteria

1. **More people finish.** Of new accounts, the share who reach something useful
   within a day: a child's first class started, a player's games connected, or
   a coach's first child added. Compared with the same measure before launch.
2. **Parents reach the class quickly.** Time from `/start` to a child's first tap
   in a class. Measured on the first real families; the bar is set after the
   first ten, not guessed now.
3. **It answers the business question.** The split of paths, and of "why chess",
   across real sign-ups. If parents do not choose "thinking skills", the
   positioning is wrong, and this is the cheapest way to learn that.

Not success: sign-ups alone, or fields filled in.

## 6. Open questions

| Question | Why unresolved | Unblocking step |
|---|---|---|
| Is a ticked box from a signed-in adult enough for parental consent under the DPDP Act? | Not checked against the law; the law asks for verifiable consent | The lawyer, with the question already on their list |
| Does asking a parent for a child's age and "why chess" need anything more? | Same | The lawyer |
| May we look up FIDE ratings by ID automatically? | Not checked | Read FIDE's terms before any lookup is built |
| Should a self-declared FIDE rating do anything? | Nothing reads it today, so asking implies a use we do not have | Mohit: keep collecting it as context, or use it to seed the child's level |
| Non-Indian phone numbers | `normalise_phone` assumes India for a bare ten-digit number and accepts 11–15 digits with a country code | A country-code picker only if families abroad appear |
| Which accounts count as "new" for the `/start` redirect | An abandoned adult sign-up may have no games yet | Test against the prod user shapes before the gate changes |

## 7. Pre-code requirements

- Mohit signs off this document and the mockup.
- The rule for "existing accounts are never sent to `/start`" is checked against
  all current prod users with a read-only count, expected to be only accounts
  with nothing to lose.
- A test proves no sign-up route can write `role`.
- The redirect is tested on the phone app's Google return as well as the web.

---

## Sign-off record

- 2026-11-06 — drafted. Awaiting Mohit.
- Mockup (clickable, all three paths): https://claude.ai/artifact/UqXTLTXENYGSCtnf7EVG1h
