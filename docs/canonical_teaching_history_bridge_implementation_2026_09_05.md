# Canonical Teaching History Bridge — Implementation Record (2026-09-05)

## Outcome

The existing personal teaching profile now consumes the canonical, validated
`LessonResult v2` history instead of relying only on legacy skill counters.
This is an additive Phase 4 bridge behind the existing default-off rollout; it
does not promote public mastery or create another learner model.

## Runtime changes

- `concept_mastery_service.reduce_lesson_results_shadow` now returns fact-only
  outcome, assistance, successful-help, latest-event, and next-evidence fields.
- `get_learning_shadow_projection` reads all exact canonical skill aliases and
  can require an exact content identity before evidence is accepted.
- `personal_teaching_profile` prefers validated canonical history over legacy
  counters, while a current answer or misconception still comes first.
- The additive profile response is versioned as `personal_teaching_profile.v2`.
- The coach remembers successful help per concept and uses direct language for
  the next step: guided practice, an unassisted fresh position, real-game
  application, or later retention.
- `visible_mastery_changed` remains false. No writes, migrations, focus changes,
  detector promotions, or frontend replacements were added.

## Failure-closed behavior

Malformed events, forged earned states, duplicate source events, mismatched
outer/inner skill IDs, unrelated skill aliases, and wrong content identities do
not affect delivery. Players without valid canonical history keep the existing
legacy fallback or receive an honest diagnostic.

## Verification

- Focused bridge/profile/evidence/teaching suite: 53 passed.
- Wider curriculum, review, PIC, profile, teaching and evidence suite: 125
  passed before the final copy-only refinement; the focused suite was rerun
  afterward.
- Python syntax compilation passed for both changed services.
- New coaching copy was checked against the 600–1500 voice rules: concrete,
  short, no engine language, no unexplained chess jargon, no permanent learner
  label, and no unproved improvement claim.

## Remaining Phase 4 work

This bridge does not complete Phase 4. The next high-value gaps are:

1. make every registered concept expose a verified guided example and distinct
   unassisted checkpoint through the same teaching engine;
2. emit later-game opportunity outcomes for quality-authorized concepts;
3. data-lock transfer/verdict rules per concept family;
4. replace competing player-facing mastery readers only after shadow parity;
5. wire the one projection across Home, Review, Training, Play with Coach and
   Progress in Phase 7.
