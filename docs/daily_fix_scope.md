# Daily Fix — Scope Document

> Status: DRAFT — awaiting Mohit signoff. No code until signed off.
> The solo daily-return hook. Sequenced BEFORE the (parked) Coach Ladder because it works at any user
> count and grows the active-solver base the community loop will need. Framed as **marketing-readiness**:
> when we drive traffic, this is what makes arriving users come back on day 2 instead of leaking away.

---

## 0. Existing surfaces audit (EXTEND / PARALLEL / REPLACE)

Almost every piece already exists in parts. This is an EXTEND + one integration wire, not a new system.

| Piece of the loop | Decision | Evidence |
|---|---|---|
| A "today's task" engine | **EXTEND** | `GET /missions/today` fully built (generate → start → steps → complete → history) `missions.py:89` |
| The home "Today" card | **EXTEND** | `HomePageNew.jsx:230` already renders `todayExercise` + a 7-day focus prescription card `:218` |
| Streak | **EXTEND** | `streak.py` + `mistake_streak_service` — `streak_data` on the user, but **game-based (mistake) streak**, not day/practice |
| Progress / evidence | **EXTEND** | `/progress/improvement-proof` + decay recovery credit (`pattern_decay_service`) |
| Reminder nudge | **EXTEND** | Re-engagement email infra exists (`moments_topic_registry.py`, `generate_reengagement_emails.py`) — but hand-run, no scheduler |
| Puzzle supply | **OK** | 4,196 community puzzles + user-game drill extraction — no thin-pool risk |

**The one SSoT hazard + fix (the crux of "best of both"):** `get_today_mission` picks its own `focus_pattern`
independently (`missions.py:100`), which can disagree with the active prescription's `issue_detected`. V1 wires the
mission's focus to **come from the active prescription** (fallback to the mission's own decay-picker when there is
no active prescription). This makes prescription (week) → mission (day) → streak (habit) **one funnel with one
source of truth for "what to work on,"** instead of two "today" systems that can contradict.

**Net decision: EXTEND-dominant, one integration wire.** Genuinely new: (a) a day-based practice streak, (b) an
automated daily-reminder scheduler, (c) surfacing mission completion + streak + evidence on the existing Today card.

---

## 1. What it is

Daily Fix gives a player one small, finishable reason to open the app every day: a short set of drills pulled from
the exact weakness their coach is already focused on this week, from positions in their own games. Finishing it
keeps a practice streak alive and shows a line of proof that they're getting better. It turns the coaching the app
already does into a daily habit — the coach picks the week's focus (the prescription), today's mission is the small
concrete instance of it, the streak rewards showing up, and a daily nudge brings them back. It's the same coaching
engine, made into a ritual.

---

## 2. What the user sees (mockups — the product contract)

### 2a. Home — the Daily Fix card (extends the existing "Today" card)
```
┌───────────────────────────────────────────────┐
│  This week: keeping your pieces safe 🎯        │   ← prescription (the why)
│                                                │
│  ┌───────────────────────────────────────────┐ │
│  │ TODAY'S FIX          🔥 6-day streak       │ │
│  │ Spot the hanging piece — 4 drills · ~6 min │ │   ← mission (the do)
│  │ from your own recent games                 │ │
│  │            ●●○○  0/4 done                   │ │
│  │              [ Start today's fix → ]        │ │
│  └───────────────────────────────────────────┘ │
└───────────────────────────────────────────────┘
```

### 2b. After completing it
```
┌───────────────────────────────────────────────┐
│  ✓ Fix done. 🔥 7-day streak — nice.           │
│  You've caught the hanging-piece pattern 3×    │   ← evidence (improvement-proof / decay recovery)
│  faster than two weeks ago.                    │
│           [ Review a game ]  [ Play a game ]   │
└───────────────────────────────────────────────┘
```

### 2c. The daily reminder (email V1; the one new automated nudge)
```
Subject: Your fix is ready — keep your 6-day streak alive 🔥
Body:    Today's 6-minute fix on piece safety is waiting.
         [ Do today's fix → ]   (links to /home, per email→page contract)
```

### 2d. Streak-at-risk reminder (only when a streak exists and the day is ending)
```
Subject: Don't break your 6-day streak
Body:    A quick 4-drill fix keeps it going. [ Do it now → ]
```

---

## 3. In scope (V1)

- **Wire the daily mission's focus to the active prescription** (`/coaching/current-prescriptions` → mission
  `focus_pattern`); fall back to the mission's existing decay-picker when no active prescription. (The SSoT funnel.)
- **Surface the Daily Fix on the home Today card**: mission title, drill count, est. minutes, progress dots, Start
  CTA, and completion state — extending `HomePageNew.jsx:230`, reusing `/missions/today` → start → step → complete.
- **Day-based practice streak** — extend `mistake_streak_service` / `streak_data` with a practice-streak dimension
  that increments on daily-mission completion (distinct from the existing game-mistake streak). **Forgiving**: one
  grace/freeze day so a single miss doesn't zero it.
- **Streak chip** on home (hero + Today card).
- **Post-completion evidence line** — reuse `/progress/improvement-proof` + decay recovery to show one concrete
  "you're improving on X" line after the fix.
- **Automated daily reminder (email)** — a scheduler (per `CRON_JOBS.md`) that sends "your fix is ready" and
  "streak at risk" via the existing re-engagement email infra + `moments_topic_registry` (email→page contract),
  linking to `/home`.

## 4. Explicitly out of scope (V1)

- **Web push / browser notifications** — email only in V1; push is a later channel (service worker + scheduler).
- **The Coach Ladder / community contribution loop** — parked (`docs/coach_ladder_scope.md`), resumes after the
  active-solver base grows.
- **Real-time / social notifications** ("someone solved yours") — density-gated, deferred.
- **Changing prescription-generation logic** — V1 consumes the prescription as-is; it does not redesign it.
- **Leaderboard / competitive ranking** — untouched.
- **A second scoring system** — streak + existing gamification XP only; no new points engine (SSoT).
- **Spaced-repetition scheduling of missed drills** — desirable, but deferred to V2 to keep V1 a clean ritual.

## 5. Success criteria (behavior-changing)

- **Daily-return lift:** users who start a Daily Fix show higher D1/D7 return than matched non-starters (the core
  reason the feature exists).
- **Completion:** ≥ [X]% of users who see the Daily Fix card start it, and ≥ [Y]% of starters complete it, within 3
  weeks.
- **Habit formation:** a measurable share of active users reach a ≥3-day practice streak (distribution, not a single
  number).
- **Nudge efficacy:** reminder-email open → "do the fix" CTR ≥ [Z]%.

(Bracketed numbers deferred to Open Questions — same low-traffic caveat as Coach Ladder; set provisionally and
re-lock once real usage exists rather than gut-locking.)

## 6. Open questions

- **Question:** How many drills = one "complete" Daily Fix, and how long should it feel?
  **Why unresolved:** should anchor to the mission engine's existing `goal_target` rather than invent a number.
  **Unblocking step:** read the current `goal_target` / `estimated_minutes` the generator already produces; reuse it.
- **Question:** Streak forgiveness — how many grace/freeze days before a streak resets?
  **Why unresolved:** product-feel call for a 400–1200 audience (forgiving retains better). Recommendation: 1 freeze
  day. **Unblocking step:** Mohit confirm.
- **Question:** Reminder timing + frequency (one/day? what local time? suppress if already done today?).
  **Why unresolved:** needs a call; must not over-nudge. **Unblocking step:** Mohit input; default: once/day,
  suppressed once the fix is done, streak-at-risk only when a streak exists.
- **Question:** The success-criteria numbers ([X]/[Y]/[Z]).
  **Why unresolved:** near-zero current traffic — same finding as Coach Ladder. **Unblocking step:** set
  provisional, instrument, re-lock after a real traffic cohort exists.

## 7. Pre-code requirements (hard gates)

- Mohit has explicitly signed off on this full scope document.
- Confirmed: the daily task uses the **Mission `/today` lane wired to the prescription** (best-of-both funnel), not
  a new or parallel "today" system (SSoT).
- Daily-fix size reused from the mission engine's existing `goal_target` (no invented number).
- Streak-forgiveness (grace days) + reminder timing/frequency decided (Mohit).
- Reminder scheduler/cron path confirmed available (per `CRON_JOBS.md`).
- Card mockups (§2) approved as the product contract.
- `/audit-pre-code` run before the first file.
