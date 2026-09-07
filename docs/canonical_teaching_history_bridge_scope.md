# Canonical Teaching History Bridge — Scope

Status: LOCKED UNDER THE APPROVED COMPLETE COACHING SYSTEM PHASE 4

## 0. Existing surfaces audit

`learning_sessions.events` already stores versioned `LessonResult v2` evidence,
and `concept_mastery_service.reduce_lesson_results_shadow` already validates and
reduces it. `personal_teaching_profile` currently ignores that reducer and bases
its cross-session teaching memory on legacy `coach_memory.learning.skills` plus
the latest raw answer. The personalized lesson route already consumes the
teaching profile. Decision: **EXTEND** those services. Do not add a new ledger,
profile collection, mastery service, or lesson route.

## 1. What it is

A read-only bridge from validated LessonResult history into the existing
personal teaching profile. It lets delivery remember what happened for this
exact concept while keeping chess truth, public mastery, focus priority, and
content selection with their existing owners.

## 2. What the user sees

Behind the existing default-off personalized-teaching rollout, a returning
player receives a truthful continuation such as:

- “You solved this with support before. Next, try a fresh position without
  help.”
- “You solved a fresh position without help. The remaining question is whether
  you use it in a real game.”

The player is never called a visual/verbal learner. A current misconception
still outranks older history. No new mastery badge appears.

## 3. In scope

- Extend the generic shadow reducer with a fact-only evidence summary:
  latest accepted event, outcomes, assistance, successful help, and the next
  evidence type the coach still needs.
- Make the async teaching-profile builder read all canonical aliases for the
  requested skill and pass the validated projection into the existing profile.
- Prefer validated LessonResult history over legacy per-skill counters when
  both exist; retain legacy fallback for unmigrated players.
- Return a coach-only `next_evidence` recommendation and provenance.
- Preserve current-interaction precedence, canonical lesson truth, no-write
  behavior, default-off rollout, and `visible_mastery_changed=false`.

## 4. Explicitly out of scope

- Public mastery promotion or retirement of legacy mastery UIs.
- A numeric retention, transfer, or improvement threshold.
- Plan/Mastery promotion for any detector.
- Automatic focus changes, lesson skipping, or organic-game claims.
- A new frontend page or a second teaching profile.

## 5. Acceptance criteria

- A valid canonical LessonResult history changes delivery for the same lesson
  while leaving canonical chess content unchanged.
- Current-answer misconception remains the first and strongest anchor.
- Alias-backed sessions reduce into one canonical skill projection.
- Duplicate, malformed, forged, wrong-skill, or wrong-content events cannot
  personalize delivery.
- Successful help is remembered per concept, not globally.
- New, learning, helped, unassisted, and application histories each return an
  honest next-evidence value.
- The bridge performs no writes and does not change visible mastery.
- Focused profile, reducer, evidence-ledger, and teaching-engine tests pass.

## 6. Open questions

None for this shadow/default-off bridge. The number and timing of later-game
opportunities needed for an improvement verdict remain intentionally unlocked.

## 7. Rollback

Disable the existing personalized-teaching/complete-coaching rollout flags or
revert this additive bridge. Stored LessonResult evidence is retained. Legacy
profile fallback remains available and no data migration is required.
