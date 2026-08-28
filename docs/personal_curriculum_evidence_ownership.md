# Personal Curriculum — Evidence Ownership Audit

**Status:** OWNERSHIP LOCK v2 — 2026-08-28. Phase 3 contracts consume existing owners; no independent content, selector, or mastery store was added.

## Rule

The Personal Curriculum is a composition and translation layer. It may select an action and narrate evidence, but it does not copy lesson content, detect chess truth, or store an independent mastery verdict.

## Canonical content sources

| Domain | Canonical V1 source | Readers/adapters | Decision |
|---|---|---|---|
| Openings | `backend/data/opening_curriculum.json` through `services/opening_unified_source.py` | opening lessons, lookup, walkthrough, PWC guidance, mastery tracker | Locked. New opening content is authored once here. |
| Traps | `backend/data/traps.json` through `services/trap_library.py` | recognition, scanner, practice, PWC, mastery | Locked. New trap content is authored once here. |
| Endgame routed lessons | `backend/data/coaching/endgame_theory_tree.json` through `services/endgame_theory_service.py` | Study catalogue, `EndgameLesson`, generic teaching engine | Locked for Personal Curriculum V1. |
| Endgame legacy/PWC lessons | `backend/data/endgames.json` through `services/endgame_teaching.py` | legacy PWC endgame selection and principles | Legacy adapter only. Do not author a V1 lesson in both files. Migrate selected V1 content to the routed canonical source before parity removal. |
| Curriculum identity | `backend/data/coaching/skill_tree.json` | next-skill builder and mastery summaries | Conditional. It owns stable skill IDs and content references, but its prerequisites and rating gates require audit before they can influence selection. |
| Recurring repair topics | existing focus/concept registries | PIC/focus services, detectors, game review | Locked by their existing owners. Curriculum stores references only. |

## Canonical evidence ownership

| Evidence question | Owner | Personal Curriculum use |
|---|---|---|
| Did the student open, attempt, use a hint, or finish a lesson? | `learning_sessions` plus the lesson adapter that produced the event | Translate participation into New, Learning, or Can do with help. |
| Did the student independently solve a distinct valid position? | `learning_sessions` with explicit assistance and checkpoint eligibility | Translate to Can do alone; never infer from lesson completion. |
| Did a board concept occur and was it violated or handled? | `user_concept_understanding`, updated by audited concept detectors from analyzed games | Translate verified opportunities into missed/used evidence. Absence does nothing. |
| What recurring weakness is actively being repaired? | active focus/PIC services and their evidence records | Candidate for REPAIR; curriculum does not recompute the weakness. |
| Did the student study or quiz an opening? | `user_opening_progress` | Lesson participation, practice count, quiz history, and notes only. |
| How did the student play an opening in analyzed games? | `user_opening_mastery` | Game accuracy, guidance phase, branch exposure, trap encounters, and application evidence. |
| Did the student encounter, fall for, avoid, or execute a trap? | trap scanner plus `trap_mastery_tracker`, stored with opening-game evidence | Verified trap opportunity and outcome. |
| What did Engine 2 record about generic skill attempts? | `coach_memory.learning.skills` | Candidate-generation input and legacy compatibility; not universal mastery truth. |
| What does the older V5 aggregate say? | `user_learning_progress` | Legacy analytics only. It is not eligible to choose or advance a curriculum item. |

## Duplicate-source findings, ranked by add-cost and risk

### 1. Opening learner state — highest risk

- Sources: `user_opening_progress`, `user_opening_mastery`, and `coach_memory.learning` opening lists/skills.
- Add-cost today: a new opening can touch curriculum content, skill-tree identity, two progress systems, route mappings, and tests.
- Classification: partly legitimate separate concerns, partly duplicated verdicts.
- Lock: `user_opening_progress` owns study participation; `user_opening_mastery` owns analyzed-game behavior; `coach_memory.learning` is a compatibility/index view. None alone owns the student-facing state.
- Required guard: playing an opening accurately cannot mark it studied; finishing a guided lesson cannot mark it reliable in games.

### 2. Endgame lesson truth — high risk

- Sources: `endgame_theory_tree.json`, `endgames.json`, and hard-coded mappings in mastery/today composition.
- Add-cost today: a new endgame may require two content edits plus route and skill mappings.
- Classification: true content overlap serving different legacy delivery paths.
- Lock: routed V1 lessons use `endgame_theory_tree.json`; `endgames.json` remains a legacy adapter source until selected PWC flows migrate.
- Required guard: every V1 endgame skill resolves to one routed lesson and one source of authored moves/explanations.

### 3. Generic concept mastery — high semantic risk

- Sources: `coach_memory.learning.skills`, `user_concept_understanding`, `learning_sessions`, and PIC projection events.
- Add-cost today: a concept can require a skill node, detector, lesson route, session events, and mastery translation.
- Classification: legitimate evidence sources with incompatible meanings, currently presented too similarly.
- Lock: lesson sessions own assistance/recall; concept-understanding owns game opportunities; PIC owns its audited repair lifecycle. Personal Curriculum translates but never collapses them into one numeric score.
- Required guard: one correct guided attempt may become studied/with-help, never reliable.

### 4. Legacy V5 learning aggregate — low add-cost, high confusion

- Source: `user_learning_progress`, written and read only by `v5_learning_tracker.py`, with a parallel summary also written into coach memory.
- Classification: isolated legacy aggregate.
- Lock: exclude it from curriculum selection and state advancement. Retain only for legacy analytics until removal is separately scoped.

## Canonical student-state translation

| State | Minimum semantic requirement | Forbidden shortcut |
|---|---|---|
| New | No eligible participation or game evidence | Missing row interpreted as weakness |
| Learning | Explanation or lesson started | Merely recommended |
| Can do with help | Correct eligible attempt with recorded assistance | Forced line called independent |
| Can do alone | Correct unassisted attempt on a distinct verified position | Same-position retry after answer reveal |
| Used in games | Verified relevant opportunity handled correctly | Clean game where the idea never occurred |
| Reliable | Delayed independent recall plus repeated verified game use | One completion, one good move, or elapsed time alone |

Selection boundaries are owned by `docs/personal_curriculum_selection_data_lock_2026_08_28.md`, not duplicated here.

## One-selector decision

`services/today_composer.py` is the closest existing central composition path because it already combines repair focus, Engine 2 next skill, rating, destinations, and Home-facing actions. V1 should extend or extract this responsibility into one canonical composer. Direct player-facing calls to `engine2_skill_builder.pick_next_skill` become candidates consumed by that composer, not parallel final decisions.

## Guard tests required before implementation rollout

- Adding one opening or trap requires one content edit, with generated/index references checked automatically.
- Every V1 skill ID resolves to exactly one canonical content record and valid destination.
- Home and Learn receive the same primary curriculum decision for the same user and clock.
- Guided completion cannot produce Can do alone, Used in games, or Reliable.
- A game with no relevant opportunity cannot advance or demote knowledge.
- `user_learning_progress` cannot affect curriculum selection.
- Opening study and opening game performance remain independently attributable.
- No player-facing response exposes Engine 2, tier, gate, internal skill ID, or conflicting mastery percentages.

## Phase 3 outcome and Phase 4 blockers

- Review after **3 fully D_live-instrumented games** is locked in the versioned review-opportunity snapshot. The 21-day backstop is a check-in only.
- Endgame content-reference aliases moved from `today_composer.py` into the canonical `endgame_theory_service.py`; Personal Curriculum resolves Rule of the Square through that owner.
- `personal_curriculum.py` is a default-off composition/result contract. It accepts normalized owner evidence and cannot read `user_learning_progress`, rank raw Mongo records, copy lesson content, or persist mastery.
- Mohit signed off on route ownership, non-replacing Explore, compact plan references, and Rule of the Square as the first controlled lesson slice.
- Before Phase 4, complete the live desktop/mobile route audit, analytics baselines, and representative-player mockup tests. Real-game Rule of the Square claims remain suppressed until its detector is Plan-grade.
