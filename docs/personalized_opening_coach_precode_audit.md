# Personalized Opening Coach — Pre-code Audit

Date: 2026-09-16

Status: **PASS for the truth-and-evidence V1 slice**

1. **Literal experience exists:** PASS. The exact repertoire, lesson and completion language is in `personalized_opening_coach_scope.md`.
2. **The feature teaches a position and idea, not a database label:** PASS. Player color, role and decision position lead; move notation is supporting evidence.
3. **Numeric decisions are measured:** PASS. V1 reuses the measured 20cp sound-alternative boundary and the existing 4-game / 23cp / 48cp repertoire bands. It introduces no automatic reliable or stale thresholds.
4. **Success is behavioral:** PASS. Independent later decisions in eligible real-game re-encounters are the target; lesson views and completion are not mastery.
5. **Deferred work remains deferred:** PASS. No new opening library, auto-authored theory, pricing work, broad redesign, or guessed mastery promotion is included.
6. **Scope sign-off exists:** PASS. Mohit approved the full scope on 2026-09-16 with “locked, go code”.

## Implementation boundary

This slice may:

- make `user_opening_mastery` the active read owner;
- store server-graded independent, assisted and sound-alternative practice evidence;
- correct false mastery copy;
- respect player color and opponent-system practice;
- fix unreachable mastery-history logic and color alignment;
- keep promotion fail-closed until a later evidence distribution exists.

It may not migrate legacy labels, enable production rollout, or claim branch reliability.

The rollout switch is `PERSONALIZED_OPENING_COACH_V1_ENABLED` and defaults to
off. Correctness fixes remain active; new engine-accepted alternatives, branch
evidence writes and recurring-decision recommendations require the switch.
