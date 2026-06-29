# Player Motivation — Scope

*Status: SIGNED OFF + BUILT 2026-06-29. Mohit signed off (and granted standing signoff for similar small, scoped features). Open-question calls (delegated to me): labels in easy English (compete/improve/learn/fun); existing-users = honest self-declared Home re-prompt (not an inferred proxy); read-out = `scripts/player_motivation_distribution.py`; field = `player_motivation`; question skippable. Ships to users on next prod deploy.*

A single self-declared "why are you here?" question at onboarding, to segment the user base. This is the **cheap strategic probe** (understand who actually shows up), NOT a per-persona coaching engine.

---

## 0. Existing surfaces audit  →  decision: **EXTEND**

**What touches this user need today:**
- **Onboarding.jsx — Step 2** ("Calibrate profile"): already collects FIDE rating + `focus_intent` via a radio-button picker, POSTing to `/settings/profile`. This is the natural home.
- **`focus_intent`** (`routes/settings.py:52`, options: *tactics / openings / endgames / stability*): captures **which chess topic** the user wants to improve.
- **`StyleProfile`** (`player_identity.py`): aggressive / positional — **how they play**.
- **`BehavioralProfile`** (`player_identity.py`): tilt, consistency, time-trouble — **in-game behavior**.

**Overlap vs differentiation:**
- `focus_intent` is the closest field, but it answers *"what chess area?"* — **orthogonal** to *"why are you here / how serious?"* A user can want to improve *tactics* (focus_intent) while being *here just for fun* (motivation). No duplication.
- Style/behavioral profiles describe play, not motivation. No duplication.
- **Verified: no engagement/motivation/persona field exists anywhere.** Genuinely new dimension.

**Decision: EXTEND onboarding Step 2** — add ONE question beside `focus_intent`, store ONE new field via the existing `/settings/profile` POST. No new page, no parallel surface. The only genuinely-new piece is a tiny read-out for Mohit (the distribution).

---

## 1. What it is

When a new user finishes linking their account, the onboarding profile step asks one extra question — *"What brings you to ChessGuru?"* — with a few plain-English options ranging from "serious about climbing" to "just here for fun." Their answer is saved to their profile. The point is **not** to change their experience yet — it's to give us an honest read on **who is actually signing up**, so we know whether we're building for serious improvers or casual players (today we assume everyone is a serious improver, and we've never checked).

## 2. What the user sees

Added as the last question in the existing onboarding Step 2, same radio-button style as the rating/focus pickers:

```
  Calibrate your profile
  ────────────────────────────────────────────
  Your rating:        [ 1100 ]   (auto-detected: 1080)

  What do you want to sharpen?     ← existing focus_intent
   ( ) Tactics   ( ) Openings   ( ) Endgames   ( ) Steadiness

  What brings you to ChessGuru?    ← NEW (this feature)
   (•) I want to compete and climb seriously
   ( ) I want to steadily get better
   ( ) I'm here to learn and enjoy the game
   ( ) I just want to play for fun

                                   [  Continue  → ]
```

No other UI changes anywhere. The answer is invisible to the user after this — it only feeds Mohit's read-out.

**Mohit's read-out (the only new surface):** a simple distribution, e.g.
```
  Player motivation — 84 users (62 answered)
    Compete & climb seriously .......  9   (15%)
    Steadily get better ............. 21   (34%)
    Learn & enjoy .................... 18  (29%)
    Just play for fun ............... 14   (23%)
    (not yet answered) .............. 22
```

## 3. In scope (V1)

- One new self-declared question in **Onboarding.jsx Step 2**, 4 fixed options (wording per §6).
- One new stored field (`player_motivation`) on the user record, written through the **existing** `/settings/profile` POST (mirror `focus_intent`: `routes/settings.py` model + `update_data`).
- The question is **skippable** — Continue works without answering (don't block onboarding completion).
- A **read-out for Mohit**: the distribution across all users (admin page count OR a one-shot script — decided in §6).
- Existing-user coverage handled per the §6 decision.

## 4. Explicitly out of scope (V1)

- **Any change to coaching tone, cadence, or content based on the answer.** V1 only *records*; it does not *act*. (The per-persona coaching engine is the deferred Value B — premature at 84 users until tone-churn is proven.)
- **The coachability axis** ("listens to coach"). Self-declaration can't capture it honestly (everyone says yes); it must be behavior-derived later. Deferred.
- **Behavior-derived motivation** (inferring serious-vs-casual from play frequency / training completion). Deferred — the self-declared answer comes first.
- **The 4-quadrant persona** (motivation × coachability). V1 captures only the motivation axis.
- **Per-persona feature gating / dashboard changes.** Deferred.

## 5. Success criteria

Behavior-changing for the **decision-maker (Mohit)**, since V1 is internal intelligence:
- **Answer rate ≥ 70%** of new onboarding completers leave a non-empty `player_motivation` within 2 weeks (proves the question is answerable and not skipped en masse).
- **The distribution is visible to Mohit** and he can name **one concrete roadmap conclusion** from it (e.g. "≥50% are casual → stop assuming serious-improver as the default product"). If the data changes or confirms a real decision, V1 worked. If it's collected and never looked at, it failed.

## 6. Open questions

- **Q: How do the existing 84 users get tagged?**
  Why unresolved: the onboarding question only catches *future* signups; the strategic value wants the current base too.
  Unblocking step: Mohit picks one — (a) one-time re-prompt modal on next login for users missing the field; (b) a behavioral proxy (segment existing users from play/review/training activity now — faster but inferred, not self-declared); (c) accept slow accumulation (new signups only). *Recommendation: (a) for honesty + (b) as a quick parallel read so you don't wait weeks.*

- **Q: Exact option wording and count (3 vs 4)?**
  Why unresolved: copy decision; "compete seriously" and "steadily get better" may be too close.
  Unblocking step: Mohit locks the final labels (this is a voice call, not a data lock).

- **Q: Where does Mohit read the distribution — an admin page or an ad-hoc script?**
  Why unresolved: depends whether he wants it recurring or one-look.
  Unblocking step: Mohit input. (Default: one-shot script now; admin tile later if useful.)

- **Q: Required or skippable?**
  Recommendation in §3 is skippable (don't hurt onboarding completion). Confirm.

## 7. Pre-code requirements

- Mohit has **explicitly signed off** on this scope document.
- Final **option labels** locked (§6).
- **Existing-user tagging** path chosen (§6 — a/b/c).
- **Field name** confirmed (`player_motivation` proposed).
- **Read-out location** chosen (script vs admin page).
