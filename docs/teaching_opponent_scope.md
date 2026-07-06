# Teaching Opponent — Scope

**Date:** 2026-07-06
**Author:** Claude (drafting for Mohit's signoff)
**Status:** SCOPE — no code until signed off.

## The problem (in plain English)

PWC sets the coach-opponent's playing strength from ONE number: the student's
derived rating. `rating_to_skill_level(rating)` maps it to a Stockfish skill
level (0–20). For a beginner this backfires badly:

- Shobhit's derived rating is **556** → `rating_to_skill_level(556) = 0`.
- Stockfish **skill 0 plays near-random**: it injects blunders and **misses
  free material**.
- Shobhit's #1 weakness is **piece_safety — 1227 events (hanging pieces).**
- So Shobhit hangs a rook, the skill-0 coach doesn't take it, and the single
  most important lesson for him never lands. The mechanism meant to make the
  opponent "easy" is the exact thing that makes it **useless as a teacher.**

**The confusion is between two different knobs that are currently welded
together:**

| Knob | What it should track | Currently |
|---|---|---|
| **Opponent strength** — how good the moves the coach *plays* are | tuned for LEARNING | tied 1:1 to student rating |
| **Teaching pedagogy** — language, thresholds, what's emphasized | tuned to the STUDENT's level | (already ~correct) |

## The principle

> **A teaching opponent should be weak in DEPTH, not weak in FUNDAMENTALS.**

It shouldn't find 4-move combinations or grind the beginner down positionally
(that just crushes and teaches nothing). But it MUST **punish a blunder** —
take the hanging piece, grab the free pawn, recapture. That is where the
consequence, and therefore the learning, lives. A real 800 human won't
out-calculate you, but they *will* take your free rook. Stockfish skill levels
give the opposite: they weaken the engine by making it miss the obvious. Wrong
knob.

## What we build

### 1. Punish-override — the mirror of the blunder guard

We already have `_apply_blunder_guard` on `CoachOpponent` (coach_opponent.py:221):
before the opponent plays, it vetoes a move that hangs the coach's OWN material.
The punish-override is its mirror: before the opponent plays, if the student
left material hanging and the weak engine's proposed move IGNORES it, substitute
the capture that takes it.

- Same integration point (right after the engine proposes, in `_get_move_sync`).
- Same primitive: **SEE** (`see_gain` / `material_hung_after` from
  `coach_blunder_guard` — the single source of truth for one-move material,
  the same code the simple_hang fix now uses).
- **One-move SEE only** — punish immediate free material, deliberately NOT
  multi-move tactics. This makes the opponent take your free rook without
  becoming a tactical monster that finds shots the beginner can't understand.

Mechanism: on the current board (opponent to move), find the capture with the
highest positive `see_gain`. If it clears the punish floor and the engine's
proposed move isn't that capture, play the capture instead.

### 2. Skill floor — stop the sub-800 random play

Raise the floor of `rating_to_skill_level` so the opponent never plays pure
noise (skill 0). Even a beginner deserves an opponent that makes *sensible*
moves and only loses because it doesn't calculate deep — not one that plays
random junk. The student stays winning by out-playing a limited-but-sane
opponent, reinforced by the punish-override so their blunders still cost them.

### 3. Teaching pedagogy — unchanged

The coaching calibration (band language, encouragement, fundamentals focus)
stays keyed to the student's real derived rating (556 → beginner). That knob is
already right; we are only decoupling the OPPONENT knob from it.

## Open decisions (need your call before I build)

1. **Punish floor (cp).** What SEE gain forces the capture?
   - `>= 200` — only punish a real piece+ hang (minor/rook/queen). Cleaner, but
     lets a free pawn slide.
   - `>= 100` — punish any free material incl. a pawn. Harsher, more
     thorough piece-safety training.
   - *Recommendation:* start at **200** (punish the trust-and-lesson-defining
     piece hangs), revisit with data. Per our "threshold before distribution is
     a sin" rule, I'll pull the distribution of student-hang sizes before
     locking a number rather than guessing.

2. **Always punish, or high-probability?** A real beginner opponent occasionally
   misses too. 100% punish is the most reliable teacher but can feel robotic.
   - *Recommendation:* **100% for a piece+ hang** (the lesson must land),
     optionally probabilistic for pawns. Your call.

3. **Skill floor level.** Raise sub-800 from skill 0 to skill **3** (still very
   weak, but not random)? Or higher? *Recommendation: 3.*

4. **Flag + default.** Ship behind `PWC_TEACHING_OPPONENT` (default off), like
   the blunder guard, so we validate before it reaches everyone.

## Acceptance

- **Punish test (the core one):** a suite of positions where the student has
  just hung material (piece / pawn / with a defender / SEE-negative decoy). The
  opponent MUST capture the real free material and MUST NOT grab SEE-losing bait.
- **Beatability preserved:** the opponent still loses/ draws to reasonable
  beginner play in a self-play or fixture check — the override only fires on
  hangs, it doesn't turn the opponent into a strong player.
- **Non-regression:** the blunder guard still works (coach doesn't hang its
  own pieces); the two guards compose without fighting.
- Unit tests + a documented before/after on Shobhit-style hang positions.

## Non-goals

- Multi-move tactical punishment (forks/combos that win material over 2+ moves).
  One-move SEE only. Deferred.
- Positional strength scaling ("play more accurately in quiet positions"). The
  opponent stays limited in depth on purpose.
- Changing the rating DERIVATION (separate issue — see the two-rating-systems
  smell: live PWC derives 1184 for Mohit while `assessed_rating` is 1241).
- Any change to the teaching/caption layer.

## Rollout

1. Sign off this scope.
2. Pull the distribution of student-hang sizes (lock the punish floor with data).
3. Build `_apply_punish_override` + skill floor, behind `PWC_TEACHING_OPPONENT`.
4. Tests (punish suite + beatability + guard-composition).
5. Validate on Shobhit hang positions; measure the opponent now punishes hangs.
6. Flag on in prod after your review.
