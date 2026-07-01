# Habit Tracker — Scope

**Status:** Drafted 2026-07-01. Awaiting Mohit's signoff before code.
**Related:** [primary_weakness_picker_scope.md](primary_weakness_picker_scope.md), [move_observations_scope.md](move_observations_scope.md).
**Parent theme:** Theme 3 — Curriculum Engine.

---

## TL;DR

The Primary Weakness Picker locks a **pattern** for 14 days. But patterns are fixed by **habits**, not by awareness. A user can know "I hang pieces" and still hang them next game.

The Habit Tracker turns each active focus into a **daily 3-second habit** — "before every move, ask 'is anything of mine attacked?'" — with a daily prompt, a streak counter, and a completion check that measures whether the user actually built the habit (not just intended to).

Every locked focus maps to a specific habit. The habit is the intervention; the focus is the diagnosis.

---

## Why this exists

The Picker + Focus card + Moments page tell the user **what** to work on. They don't tell them **how**.

Real chess improvement is habit formation, not information consumption. A user who reads "you hang pieces" 20 times will keep hanging pieces. A user who does the 3-second scan for 7 days straight will stop hanging pieces.

Without this, the Picker + Focus card is a diagnosis without a prescription — the same failure mode that all "insight dashboards" have.

---

## Data model

### `user_active_habits` collection

One document per (user, habit_key) that is currently in-progress or has been completed. Never deleted — historical habits are the user's improvement timeline.

```
{
  "_id": ObjectId,
  "user_id": "user_xxx",
  "habit_key": "piece_safety_scan",
  "linked_focus_id": ObjectId,     // → user_active_focus._id, so habit auto-graduates when focus does
  "status": "in_progress" | "completed" | "abandoned",
  "started_at": ISODate,
  "target_streak_days": 7,          // default 7; can be longer for harder habits
  "current_streak_days": 0,
  "best_streak_days": 0,            // preserved even after abandonment
  "last_checked_in_on": "2026-07-01",  // YYYY-MM-DD, user's timezone-normalized
  "check_ins": [                    // ledger — one entry per day the user acknowledged
    { "date": "2026-07-01", "acknowledged_before_play": true, "n_games_after": 3 },
    { "date": "2026-07-02", "acknowledged_before_play": true, "n_games_after": 5 },
    ...
  ],
  "outcome_evidence": {             // populated at habit completion
    "baseline_rate": 1.40,          // per-game rate of the underlying pattern before habit
    "current_rate": 0.85,           // after habit period
    "delta_pct": -39,               // negative = improved
    "outcome": "improved" | "stuck" | "regressed"
  },
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### `habit_definitions` (in-code constant, not a DB collection)

Editorial content — the actual habits users can be assigned. Keyed by topic (matches primary_weakness_picker topics) → habit spec.

```python
HABIT_DEFINITIONS = {
    "piece_safety": {
        "habit_key": "piece_safety_scan",
        "name": "The Piece Safety Scan",
        "prompt": "Before every move: look at each of your pieces. Is anyone attacking it?",
        "one_liner": "3-second scan before every move.",
        "target_streak_days": 7,
        "how_to_practice": "Play 3 games with this scan. Say the piece names out loud if you have to. It's 3 seconds per move — you'll feel slow at first, then it disappears into instinct.",
    },
    "ignoring_king_safety_threats": {
        "habit_key": "king_safety_check",
        "name": "The King-Safety Question",
        "prompt": "Every 3 moves: '*Where would checkmate come from right now?*'",
        "one_liner": "Ask the king-safety question every 3 moves.",
        "target_streak_days": 7,
        "how_to_practice": "Even when winning. Especially when winning. Set a mental timer.",
    },
    "fork_misses": {
        "habit_key": "fork_scan",
        "name": "The Knight-Move Fork Scan",
        "prompt": "Any move with a knight: 'What does the knight attack besides its target?'",
        "one_liner": "Scan for fork geometry on every knight move.",
        "target_streak_days": 7,
        "how_to_practice": "This applies to your knights AND your opponent's. Both directions matter.",
    },
    "neglecting_development": {
        "habit_key": "no_early_attack",
        "name": "The Development Discipline",
        "prompt": "No queen moves or captures until both bishops, both knights, and castling are done.",
        "one_liner": "Develop all pieces before touching the queen or capturing.",
        "target_streak_days": 7,
        "how_to_practice": "Boring for 8 moves. Then you unleash a full army instead of a solo queen.",
    },
    "poor_piece_activity": {
        "habit_key": "worst_piece_relocation",
        "name": "The Worst-Piece Question",
        "prompt": "After each opponent move: 'Which of my pieces is doing the least right now?'",
        "one_liner": "Ask which piece is worst — every turn.",
        "target_streak_days": 7,
        "how_to_practice": "The strong players' secret: they relocate the WORST piece every 5-6 moves.",
    },
    "threat_awareness": {
        "habit_key": "opponent_move_scan",
        "name": "The Opponent-Threat Question",
        "prompt": "After every opponent move: 'What NEW thing does this move threaten?'",
        "one_liner": "Read opponent's threats before making your own.",
        "target_streak_days": 7,
        "how_to_practice": "One question, no other plan, until you have the answer.",
    },
    "punish_blunders": {
        "habit_key": "blunder_punishment_switch",
        "name": "The Punishment Switch",
        "prompt": "If opponent's move loses >100cp: stop everything and calculate the punishment.",
        "one_liner": "Switch modes when opponent hands you material.",
        "target_streak_days": 7,
        "how_to_practice": "Highest-EV moment in chess. Don't waste it playing your own plan.",
    },
}
```

---

## Mechanics

### Assignment
- **Automatic**: when a Primary Weakness Picker focus is assigned (`assign_focus`), a matching habit is created via `habit_definitions[topic_key]`. Same `assign_focuses.py` cron does both.
- **No focus, no habit.** Habits are always tied to a locked focus. When the focus completes/escalates, the habit closes too.

### Daily check-in
The user's daily interaction:
1. HomePage shows a **HabitPrompt** at the top: *"Today's habit — {name}. Play 1 game with this in mind. Come back and tap to confirm."*
2. After they play a game (analyzed by the worker), they can tap **"I did it today"** on the prompt.
3. That triggers `POST /api/coach/habit-check-in` which appends a check-in and increments `current_streak_days`.
4. Missed day breaks the streak (or resets to zero, TBD).

### Streak
- **Rolling 7-day streak** is the default target.
- On day 7 (or hitting target), the habit auto-completes and triggers an outcome check.
- Outcome check: compare `baseline_rate` (recorded at habit start) with `current_rate` (per-game rate of the underlying pattern across games played since habit started).

### Outcome
Same three outcomes as the Picker's focus check:
- **improved** (rate down ≥20%): celebrate + close habit + prompt for the next focus
- **stuck** (rate ±10%): extend streak target by another 7 days, keep the habit alive
- **regressed** (rate up ≥10%): close habit as "abandoned", escalate — recommend a Play-with-Coach session on this pattern

---

## Endpoints (2 new)

### `GET /api/coach/active-habit`
Consumed by `HabitPrompt` component.

```
{
  "has_habit": true,
  "habit_key": "piece_safety_scan",
  "name": "The Piece Safety Scan",
  "prompt": "Before every move: look at each of your pieces...",
  "one_liner": "3-second scan before every move.",
  "current_streak_days": 3,
  "target_streak_days": 7,
  "already_checked_in_today": false,
  "days_since_start": 3,
  "n_games_played_since_start": 8
}
```

### `POST /api/coach/habit-check-in`
Called when user taps "I did it today".

Body:
```
{ "note": "Actually caught myself twice today" }   // optional user text
```

Response:
```
{
  "current_streak_days": 4,
  "target_streak_days": 7,
  "streak_complete": false,
  "outcome": null       // populated if streak_complete: true
}
```

---

## UI surfaces

### HabitPrompt (top of HomePage — ABOVE FocusCard)
- Small strip: "Today's habit: {one_liner}"
- Streak counter: `● ● ● ○ ○ ○ ○ (3 of 7)`
- Two buttons: "**I did it today**" and "*What's the habit?*" (expands to full prompt)
- Silent (renders nothing) if `has_habit: false` OR `already_checked_in_today: true`

### HabitStreakHistory (on Progress page)
- Timeline: past habits, streaks completed, outcomes
- Motivation surface — user sees their improvement history

---

## Success criteria

Ship if:
1. ✅ 100% of users with an active focus also get a habit assigned within 1 minute of focus creation.
2. ✅ At least 30% of users check in on any given day (base rate for optional daily-prompt features).
3. ✅ Users who complete a 7-day streak see ≥15% improvement in the underlying focus pattern rate (measured via `outcome_evidence`).
4. ✅ HomePage HabitPrompt disappears cleanly once daily check-in is done (no UI clutter).

---

## Implementation plan

### Phase 1 — Service + data model (1 day)
- `services/habit_engine.py` — `HABIT_DEFINITIONS`, `create_habit_for_focus()`, `check_in()`, `check_streak_outcome()`, `close_habit()`
- `user_active_habits` collection + 2 indexes: `(user_id, status)`, `(linked_focus_id)`
- Integration with `assign_focuses.py`: create habit when focus is created

### Phase 2 — Endpoints (half day)
- `GET /api/coach/active-habit`
- `POST /api/coach/habit-check-in`

### Phase 3 — Frontend HabitPrompt (1 day)
- Component that consumes `/active-habit`, renders the strip + streak counter
- Placed on HomePage above `FocusCard`
- Silent when no habit or already checked in today

### Phase 4 — Outcome check wiring (half day)
- Cron script `run_habit_outcome_checks.py` — runs daily, closes streaks that hit target, computes outcome, and fires the appropriate follow-up (celebrate/extend/escalate)
- Integrate with existing `run_focus_outcome_checks.py` — they run together

### Phase 5 — HabitStreakHistory page section (half day)
- Add to Progress page — motivational surface

**Total: ~4 days.** Shippable end-to-end.

---

## Open questions for Mohit

1. **Missed day: break streak or freeze?**
   v1 default: **break** — hard commitment. Freeze is softer but reduces the habit-forming pressure.

2. **Multiple habits at once?**
   v1 default: **no.** One focus, one habit. Consistent with the "pick one thing" philosophy.

3. **Manual check-in vs auto-detection?**
   v1 default: **manual.** User taps "I did it." Auto-detection would require measuring whether the user actually did the 3-second scan (impossible from the analyzer). Manual is honest and builds the metacognitive muscle.

4. **Target streak length — 7, 14, or 21 days?**
   Default: **7.** Research literature says 7-9 days is the minimum for early automaticity. 14/21 are behavioral-science lore (66-day myth), not real thresholds. 7 keeps it achievable.

5. **How does this interact with the Play-with-Coach subsystem?**
   v1: no interaction. Habits are self-reported. v2: PWC could show a habit-prompt overlay before each move — but that's the intrusive path and needs its own scope.

---

## What Mohit is signing off on

1. The `user_active_habits` schema (~15 fields)
2. The `HABIT_DEFINITIONS` editorial content (7 habits mapping to focus topics)
3. The daily check-in mechanic (manual, streak-based, 7-day default)
4. The completion outcome model (improved/stuck/regressed, same thresholds as Picker)
5. The 4-phase, ~4-day implementation plan
