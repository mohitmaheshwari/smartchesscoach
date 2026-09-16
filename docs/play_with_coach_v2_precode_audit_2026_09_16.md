# Play with Coach V2 — Pre-code and Single-source Audit

**Date:** 2026-09-16
**Scope:** docs/play_with_coach_v2_scope.md
**Spec:** docs/play_with_coach_v2_spec.md
**Approval:** Mohit explicitly said “go ahead” on 2026-09-16.
**Code baseline:** origin/working-code at 11d3184e, with approved personalized-opening work 26d1930c on top; 0 commits behind at audit time.

## Pre-code audit

**Result: PASS for Phase 0 and Phase 1 shadow work.** Player-facing V2 promotion remains blocked on the conductor bake-off, measured release gates, remote staging, and human UAT.

### 1. Literal UI mockup — PASS

The approved scope contains literal returning-player setup, new-player setup, quiet-turn, warning, positive reinforcement, opening, positional, Play-mode, and postgame copy. Backend fields are downstream of those surfaces.

### 2. Pattern-led narrative — PASS

Headlines are the thinking habit or board relationship: “Before moving a defender, check what it leaves loose,” “This is your London problem,” and “Improve the least active piece.” SAN is evidence inside the turning point, never the product headline.

### 3. Thresholds from data — PASS WITH A PROMOTION BLOCK

- 15+10, White recommendation, two advisory messages per rolling six player turns, and three critical warnings are inherited from the measured Unified V1 data lock.
- The 8.5 quality threshold is Mohit's explicit acceptance criterion, not an algorithm cutoff.
- No new soundness tolerance, conductor weight, severity cutoff, cohort size, latency gate, or behavior-change threshold may enter player-facing code in Phase 0/1.
- Lexicographic, weighted-learning-value, and phase-specific conductor policies run in shadow on identical candidates. Promotion is blocked until the repository lock-via-data process selects one.

### 4. Behavior-changing success metric — PASS

The primary outcome is later unassisted success on a verified opportunity for the session focus. Assisted puzzle completion, message count, activation, and generic click-through are not mastery.

### 5. Deferred work remains deferred — PASS

Voice, avatars, unrestricted chat, new pricing, new detector invention, content expansion, arbitrary live takebacks, and redesigns of other product surfaces remain outside this migration.

### 6. Explicit sign-off — PASS

Mohit's 2026-09-16 “go ahead” follows the complete scope, implementation spec, 8.5 acceptance clarification, and no-known-failure release contract.

## Single-source-of-truth audit

| Concept | Existing owner(s) | Finding | V2 action |
|---|---|---|---|
| Experience eligibility/version | backend/services/pwc_experience.py | One canonical rollout selector; Unified V1 only | EXTEND with pwc_v2 and keep version immutable per session |
| Session model/persistence | backend/coach_play/coach_game_session.py and coach_sessions | Canonical dataclass/document already stores the complete game | EXTEND; no second session collection or model |
| Session revision | CoachGameSession.action_revision | Existing monotonic revision | RETAIN; V2 commands require expected action_revision |
| Atomic move append | backend/routes/coach_play.py::_append_session_move_once | Correct compare-and-swap exists in the giant route | EXTRACT into canonical session persistence and retire route-local ownership |
| Current board/history | coach_sessions.current_fen and move_history | Canonical server truth | RETAIN; browser never invents recovery state |
| Pending live move | frontend useCoachFlow plus implicit evaluate/commit state | Browser owns an unpersisted pending move; source of races | REPLACE for V2 with one server pending_attempt; legacy retains its path during rollout only |
| Engine evidence | backend/services/fast_eval_service.py plus existing engine pool | Trusted hot-path evaluation already exists | RETAIN; one result packet per attempt |
| Caption truth/prose | backend/services/caption_pipeline.py | Central verified renderer | RETAIN; all V2 teaching text passes through it or a verified canonical-focus instruction |
| Player-facing candidate selection | message_decision_engine.py and unified_pwc_coaching.py | True duplicate generations; old engine also contains unmeasured hardcoded scores | REPLACE with one V2 conductor; legacy modules become adapters only during shadow and are retired after cutover |
| Opponent move candidate selection | backend/coach_play/teaching CandidateMove/IntentScore | Different concern: selects sound engine moves, not player messages | RETAIN as a separate concern; add soundness proof before using pedagogical preference |
| Active focus | backend/services/focus_bridge.py::build_coaching_context | Canonical cross-surface focus with authorization | RETAIN unchanged; snapshot once into session.coaching_context |
| Opening identity/readiness | canonical opening recognizer/curriculum plus personalized opening coach | Several historical views exist, but the approved opening work establishes the read path | ADAPT by ID; never copy opening lists or explanations into PWC |
| Live decision history | coach_sessions.coaching_decisions | Existing Unified V1 trail | EXTEND with candidate policy/version, suppression, opportunity, and outcome; no coaching_events duplicate |
| Help history | coach_sessions.coaching_help_events | Existing help trail | EXTEND with opportunity_id and numeric help_level |
| Assistance/mastery | learning_sessions events through concept_mastery_service and personal_teaching_profile | Canonical cross-session mastery projection already distinguishes help evidence | RETAIN; V2 emits compatible evidence rather than a second mastery store |
| Journey analytics | coach_sessions.unified_journey plus analytics events | Existing journey container | ADAPT naming for V2; do not create a second journey document |
| Postgame story | unified_pwc_coaching.build_unified_postgame_summary | One honest summary exists but counts messages more than learning | EXTEND/REPLACE in the same player-facing slot; preserve one summary |
| Browser interaction state | frontend/src/coachFlow/useCoachFlow.js | Legacy browser-authoritative state with timers and callbacks | RETIRE for V2; new thin reducer renders server state and commands only |
| Play-mode visibility | focus_bridge mode projection plus frontend conditional suppression | Backend stripping exists, but legacy UI still depends on suppression | RETAIN backend stripping; V2 renders a component tree with no coaching capability in Play mode |

## Canonical V2 ownership decisions

1. CoachGameSession and coach_sessions remain the sole session truth.
2. action_revision is the only concurrency version.
3. One extracted compare-and-swap writer owns board advancement.
4. focus_bridge is the only active-focus reader.
5. caption_pipeline is the only position-specific teaching renderer.
6. coaching_decisions and coaching_help_events are extended, not copied.
7. The V2 conductor becomes the sole player-facing selector after cutover.
8. Opponent teaching remains a different subsystem and can only consume the selected session intent through an adapter.
9. The V2 browser reducer displays server outcomes; it does not decide chess, cadence, or commitment.

## Phase 0/1 code boundary authorized by this audit

- Add PWC V2 rollout identity default-off, without admitting ordinary users.
- Add version-compatible session fields by extending CoachGameSession.
- Extract and test the canonical atomic session mutation contract.
- Define one proof-carrying coaching-candidate contract that replaces player-facing MessageCandidate after cutover.
- Add shadow candidate capture and policy comparison with no player-visible output.
- Add tests and measurement scripts for the shadow packet.

Not yet authorized for player-facing use:

- Choosing a conductor winner.
- Changing cadence or warning budgets.
- Pedagogically re-ranking opponent moves.
- Enabling a production cohort.
- Counting any shadow result as mastery.

## Required verification before the next gate

- Unit tests for version resolution, session revision, idempotency, proof validation, and fail-closed candidate admission.
- Integration tests proving shadow collection cannot change the response, commit a move, or write a player-facing message.
- A stratified shadow report with all three policies on identical candidate sets.
- Human chess review of disagreement cases and hard negatives.
- A data-lock note choosing the conductor policy and release thresholds.

PRE-CODE AUDIT: PASS

Feature: Play with Coach V2
Proceeding to default-off Phase 0/1 implementation only.
