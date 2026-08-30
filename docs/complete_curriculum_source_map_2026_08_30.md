# Complete Curriculum — Canonical Source Map

Date: 2026-08-30
Mode: single-source-of-truth audit before implementation

## Result

The implementation must **extend the existing Personal Curriculum and
canonical subject files**. It must not create another stored player profile,
mastery collection, curriculum catalog, or chess-fact table.

The one genuinely new component is a **read-only teaching-profile view**. It
normalizes evidence from existing owners at request time and returns provenance
for every personal claim. It does not persist a seventh interpretation of the
player.

## Curriculum and chess knowledge

| Concept | Canonical owner | Other sources and verdict | Implementation rule |
| --- | --- | --- | --- |
| Public curriculum state and evidence contract | backend/services/personal_curriculum.py | Legacy SkillProgress and mastery labels are inputs, not public state owners | Extend StudentState and LessonResult behavior here; do not create a second state machine |
| Active personal plan | coach_memory.learning.active_curriculum, written only by personal_curriculum.py | user_active_focus owns the detected repair focus, not the rendered curriculum plan | Preserve this reference and evidence watermark |
| Progression and prerequisites | backend/data/coaching/skill_tree.json | It currently contains stale mastery prose and a TODO concepts source | Keep it as an ID/index only; replace prose rules with references to the Personal Curriculum contract |
| Opening lesson truth | backend/data/opening_curriculum.json | ECO and opening normalizers perform recognition jobs; they are not lesson owners | Skill nodes reference canonical opening IDs |
| Trap lesson truth | backend/data/traps.json | Runtime hardcoded trap inventory was already replaced by an adapter on this branch | Skill nodes reference canonical trap IDs or verified groups |
| Endgame lesson truth | backend/data/coaching/endgame_theory_tree.json | backend/data/endgames.json is retired as a runtime owner on this branch | Skill nodes reference category/lesson IDs |
| Tactical lesson facts | backend/data/theory/tactical_patterns.json | pattern_catalog.json is the detection/puzzle taxonomy, not a prose lesson copy | Extend each canonical pattern with teaching checkpoints, counterexample, and misconception corrections |
| Foundation, calculation, defensive-response, and practical-routine truth | backend/data/coaching/phase_principles.json, promoted and versioned during migration | move_ideas.json, opponent_threats.json, fundamentals_checklist_service.py, thinking_coach.py, and repeated caption prompts contain fragments or delivery copy | Consolidate the transferable routine here; services supply position evidence and render it without redefining the rule |
| Strategic-imbalance lesson facts | backend/knowledge_base/strategic_imbalances.py | shape detectors identify board evidence; they do not own lesson truth | Extend the existing 10-concept canon and reference concept IDs from the skill tree |
| Pawn-structure lesson facts | backend/knowledge_base/pawn_structures.py | pawn_structure_service.py detects structures; it does not own the teaching explanation | Extend the existing 10-structure canon and reference structure IDs from the skill tree |
| Consequence wording | backend/data/theory/positional_rules.json | This file describes move consequences such as loses_piece and weakens_king; it is not a positional curriculum | Keep it scoped to consequence templates; do not add strategic lessons here |
| Opening-principle mistake lessons | backend/data/theory/opening_mistakes.json | Opening repertoire trees teach named openings, a different job | Reference the theory record for universal opening habits |
| Detection and puzzle tag identity | backend/data/pattern_catalog.json | Tactical theory may use the same label but does not redefine detector identity | Add cross-reference IDs, not copied names or thresholds |

Adding a lesson changes one canonical subject record and one progression
reference. The progression reference contains IDs, prerequisites, rating
suitability, capability, and source pointer; it does not repeat the lesson's
chess explanation.

### Positional compatibility migration

backend/services/structure_plan_database.py contains 20 teaching records and is
consumed by intelligent_position_coach.py. It overlaps the canonical pawn and
strategic knowledge while also mixing opening structures and endgames into one
service. It remains a compatibility reader during rollout, but it is not an
authoring destination.

The migration order is:

1. Add stable aliases from its structure IDs to canonical pawn-structure,
   strategic, opening, or endgame IDs.
2. Make intelligent_position_coach.py read canonical records through an
   adapter.
3. Add parity tests for every currently reachable structure.
4. Retire duplicated record bodies only after parity is proven.

phase_principles.json is promoted from a shallow fallback into the canonical
owner for cross-phase foundations and thinking routines. Its new records are
structured lessons, not free-floating slogans. principle_bank.json, caption
templates, detectors, and coaching services remain derived delivery or
detection sources. They may point to a canonical concept but may not redefine
its chess truth.

### Other compatibility migrations

| Existing source or reader | Current problem | Migration |
| --- | --- | --- |
| data/theory/endgame_principles.json | Duplicates canonical endgame truth and contains claims that are too absolute | Project verified facts from endgame_theory_tree.json into chess_theory_service.py and Game Decryption, then retire this file as an authoring source |
| data/coaching/move_ideas.json | Unreferenced generic prose includes unsafe slogans such as always trading when ahead | Replace any future use with canonical subject or phase-principle references; do not migrate its wording blindly |
| data/coaching/opponent_threats.json | Unreferenced copy of tactical and strategic definitions | Resolve tactical IDs to tactical_patterns and strategic IDs to the strategic canon; defensive routines resolve to phase_principles |
| fundamentals_checklist_service.py and thinking_coach.py | Repeat useful routines as hardcoded delivery copy | Keep deterministic position evidence and migrate displayed rules/questions to canonical phase-principle IDs |
| data/coaching/skill_tree.json metadata | Still names retired trap_library.py and proposes a new concepts.json | Replace source metadata with the canonical map in this document; the skill tree remains an index |

The current positional readers are blunder_intelligence_service.py and the
player deep-dive routes through positional_coaching_service.py. The overlapping
StructurePlanDatabase is read by intelligent_position_coach.py. Endgame theory
duplicates are read by chess_theory_service.py and game_decryption_v5_service.py.
These readers receive adapters and parity tests before any duplicate body is
retired.

## Player evidence and personalization

| Signal | Authoritative owner | Use in the teaching-profile view |
| --- | --- | --- |
| Current answer, prediction, requested help, and misconception | Current learning-session events using the existing LessonResult schema family | Highest-priority teaching evidence |
| Per-skill attempts and application artifacts | coach_memory.learning.skills plus versioned LessonResult events | Known prerequisites and prior help/result history |
| Real-game concept opportunities and outcomes | user_concept_understanding plus detector-quality registry | Organic application evidence only |
| Current repair focus | user_active_focus through services/focus_bridge.py | Why this topic was selected |
| Active curriculum continuity | coach_memory.learning.active_curriculum | Preserve one lesson and return target |
| Ranked decayed weaknesses | root backend/player_profile_service.py output in player_profiles | Corroborating historical context; never the only proof of a misconception |
| Behavioral/style identity | player_identity_engine.py and services/player_identity.py | Use only high-confidence, position-relevant claims |
| Dimension-level chess understanding | services/chess_understanding.py | Complexity fallback, not concept mastery |
| Repertoire and opening progress | user_opening_progress and user_opening_mastery | Choose relevant color/family and connect examples |
| Explicit player preference | Existing user/player settings when present | Respect concise/detailed or help preference; never infer a permanent learner type |

## Existing duplication that must not spread

Two modules named player_profile_service.py write different shapes into the
same player_profiles collection:

- backend/player_profile_service.py owns decayed weakness, strength, trend,
  tone, and coarse learning-style fields used by analysis/import paths.
- backend/services/player_profile_service.py owns a cached narrative and
  profile_data used by the player narrative endpoint.

This is a true schema overlap. The complete-curriculum implementation will not
add fields to either shape and will not write another profile document. The
derived teaching-profile view treats both as optional inputs with explicit
field provenance. A later consolidation can move the narrative to a derived
response without blocking this feature.

Player identity, chess understanding, coach memory, and concept understanding
are related but not duplicates: identity describes recurring player behavior,
understanding summarizes broad dimensions, memory owns continuity and skill
history, and concept understanding owns game-application evidence. The new view
joins them; it does not replace their jobs.

## Canonical derived view

The new service may return:

- verified anchors for why the lesson is personal;
- known prerequisite and vocabulary evidence;
- current-interaction misconception;
- assistance history and preferred next teaching action;
- relevant repertoire, goal, and active focus;
- complexity fallback;
- an honesty state: personalized, diagnostic_required, or general_truth_only;
- provenance containing owner, record identity, content version, and evidence
  strength for every personal claim.

It may not:

- store a new player profile collection;
- copy lesson explanations or chess rules;
- invent a learning-style label;
- promote mastery;
- make a personal claim without a resolvable owner;
- let an LLM choose or alter chess truth.

## Guard tests

1. Adding a curriculum skill requires one canonical content edit and one skill
   index reference, never copied lesson prose.
2. Every skill-tree content reference resolves to a verified canonical record.
3. Every personal teaching anchor includes owner and evidence reference.
4. The derived teaching-profile builder performs no database writes.
5. No public surface reads the two legacy profile shapes directly for lesson
   delivery after migration; it reads the canonical view.
6. The public learning state comes only from personal_curriculum.py.
7. Retired trap/endgame inventories cannot re-enter a runtime catalog.
