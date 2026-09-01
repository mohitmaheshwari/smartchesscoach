# Personalized Game Review Coach — Spec

**Status:** APPROVED v1 — Mohit approved the recommended architecture decisions on 2026-09-01; Phase 0 measurement gates remain.  
**Version:** v1 (2026-09-01).  
**Scope:** Largest of the Game Review set; multi-phase to ship.  
**Product scope:** `docs/personalized_game_review_coach_scope.md` (locked 2026-09-01).

---

## 1. The problem

Game Review currently has strong pieces but no single coaching architecture. `caption_pipeline.build_move_teaching_decision()` is the shared authority for move-level teaching, while `decryption_voice.orchestrator` separately selects a truth line, player story, plan explanation and moments. `GameDecryptionV5.jsx` then renders both systems. Reflection is also split: Game Review invents options client-side from rendered prose, while `/reflect/v1` owns a deterministic predicate-backed option and awareness-gap engine.

The result can explain an evaluation loss but cannot reliably teach the whole game. It does not consistently connect opening purpose, opponent intent, successful ideas, missed tactical opportunities, board geometry, positional relationships, endgame rules, player belief and future practice into one lesson. It can also mistake “the detector fired” for “the player did not know,” or mark something learned without a measured real-game opportunity.

The signed product requirement is a private-coach review for 600–1500 players: understand the position, understand what the player believed through low-friction options, teach only verified chess, remember prior knowledge, choose a few useful moments, prescribe one next action and later measure transfer in real games. No deployed LLM is required or authorized to decide chess truth, diagnosis or lesson selection.

## 2. The shape — five contracts and seven event outcomes

```text
stored move evaluations + canonical content + player context
                              │
                              ▼
                MoveTeachingDecision (existing authority)
                              │
                     typed evidence adapter
                              ▼
                    TeachableEvent[] (new contract)
                              │
          ┌───────────────────┼────────────────────┐
          ▼                   ▼                    ▼
  reflection options    game planner       learning adapter
          │                   │                    │
          ▼                   ▼                    ▼
 PlayerReflection      GameTeachingPlan       LessonResult
          └───────────────────┼────────────────────┘
                              ▼
           reveal → practise → future opportunity → retain/relapse
```

**Contract A — `MoveTeachingDecision`** remains the only per-move chess-teaching authority for Review and Play with Coach. It receives stored engine facts, canonical recognizer outputs and player context. It returns text, visuals, severity, concept/principle identity, shape, trap, provenance and the Stage 4 causal/personal explanation. No planner or frontend reinterprets raw FEN independently.

**Contract B — `TeachableEvent`** is an immutable, structured statement about one moment. It references canonical concept/content IDs and records actor, opportunity state, outcome, evidence, authorization and visuals. It never stores a copied lesson.

```json
{
  "event_id": "game_id:ply:quality_id:outcome",
  "move": {"ply": 23, "number": 12, "san": "Bg5", "actor": "user"},
  "concept": {"id": "piece_relationships.pinned_defender", "content_ref": null},
  "outcome": "allowed",
  "opportunity": {"eligible": true, "before": "safe", "after": "bishop_undefended"},
  "evidence": {"quality_id": "shape:pin", "grade": "caption", "provenance": []},
  "teaching": {"caption": "", "principle": "", "visual": {}},
  "display": {"authorized": true, "reflection_eligible": true}
}
```

The seven outcomes are: `demonstrated`, `missed`, `allowed`, `answered`, `neutralized`, `introduced` and `silent`. Examples: using a fork is demonstrated; not playing an available fork is missed; walking into a pin is allowed; meeting a threat is answered; preventing a pawn break is neutralized; encountering an unknown endgame rule is introduced; insufficient evidence is silent.

**Contract C — `ReflectionPrompt` / `PlayerReflection`** asks one position-specific question before reveal when the answer can change the diagnosis. Options use stable IDs from the backend registry. The stored response includes all options shown, the selected option, elapsed time and `answered_before_reveal`. Objective chess evidence is immutable; reflection only refines the cognitive diagnosis.

**Contract D — `GameTeachingPlan`** connects the ordered events into one review: human opening, game arc, selected chapters, demonstrated knowledge, opponent plan, new lesson, recurring personal connection, takeaway and canonical next action. It stores event IDs and content references, not duplicated detector facts or lesson prose.

**Contract E — `LessonResult` / learner projection** reuses `personal_curriculum.py` and the existing mastery reducer. Review can prove `learning`; assisted practice can prove `can_do_with_help`; an independent verified position can prove `can_do_alone`; only Plan/Mastery-authorized opportunity evidence can prove `used_in_games` or `reliable`.

## 3. Schema / files touched

**Existing authorities to extend**

- `backend/services/caption_pipeline.py`: add a typed evidence projection to `MoveTeachingDecision`; preserve `debug_facts` as audit-only. Do not move game-level selection into this file.
- `backend/services/game_decryption_v5_service.py`: after all decisions are built, adapt them to events and call the planner. Persist the plan with the same versioned regeneration lifecycle as V5.
- `backend/services/detector_quality.py`: keep the authorization ladder. Caption-grade may explain one current event; Plan/Mastery authorization is required for recurrence, prescription or application claims.
- `backend/quick_tag_registry.py` and `backend/awareness_gap_rules.py`: become the canonical option and reflection-diagnosis path. Extend predicates and stable IDs; do not create a second option table.
- `backend/routes/reflect.py`: accept the new event identity and reveal state; continue storing raw structured reflection for audit.
- `backend/services/personal_curriculum.py`: reuse `LessonResult`, `StudentState` and content references; add only backward-compatible event metadata needed to trace review origin.
- `backend/services/concept_mastery_service.py`: reduce eligible review, practice and application events without inventing a second mastery model.
- `backend/services/move_observation_deriver.py`: emit comparable opportunity outcomes when a promoted detector defines a denominator. Existing stored Stockfish analysis remains the source; Review does not rerun it.
- `backend/routes/coach.py`: return `game_teaching_plan`; add event-scoped reflection submit/reveal endpoints; flag-off response stays byte-compatible.
- `frontend/src/components/GameDecryptionV5.jsx`: render the plan and stop generating chess options in `_generateThoughtOptions` after migration parity.
- `frontend/src/components/GameMoments.jsx`, `PlayerDecryption.jsx` and related review blocks: adapt or retire once the new planner owns their useful outcomes.

**New orchestration files; no new chess-content files**

- `backend/services/game_review_contracts.py`: dataclasses and serialization for `TeachableEvent`, `ReflectionPrompt` and `GameTeachingPlan`; contains no detector rules or content prose.
- `backend/services/game_review_event_adapter.py`: converts typed `MoveTeachingDecision` outputs plus canonical opening/trap/endgame references into events. It does not recompute chess facts.
- `backend/services/game_review_planner.py`: deterministic game-level selection and story assembly from authorized events and learner context.
- `backend/services/review_reflection_service.py`: calls the existing quick-tag and awareness-gap authorities, validates event eligibility and returns the reveal payload.
- `backend/services/review_learning_adapter.py`: converts reveal, practice and later opportunity outcomes into existing `LessonResult`/learning-session events.
- `frontend/src/components/game-review/ReviewStory.jsx`, `ReviewChapter.jsx` and `ReviewReflectionCard.jsx`: presentation-only components consuming backend contracts.

**Mongo additions**

- `game_analyses.game_teaching_plan`: versioned `GameTeachingPlan`, generation timestamp, source V5 version and rollout mode.
- `reflection_sessions`: additive `schema_version`, `event_id`, `prompt_id`, `options_shown`, `answered_before_reveal`, `diagnosis_before`, `diagnosis_after` and evidence references.
- `learning_sessions.events`: existing append-only event stream receives review-origin `LessonResult` adapters; no new mastery collection.

**Canonical content remains referenced, never copied**

- Openings: `backend/data/opening_curriculum.json` through `opening_unified_source.py`.
- Traps: `backend/data/traps.json` through `trap_library.py` and `trap_scanner.py`.
- Endgames: final canonical owner is a §10 blocking decision; adapters must make adding a lesson a one-source edit.
- Detector/user-surface authority: `detector_quality.py`.
- Curriculum destinations and learner states: `personal_curriculum.py`.

## 4. New facts / data the system needs

The system needs new typed projections, not a new chess database:

- Event identity: game, ply, actor, phase, canonical concept/content reference and detector quality ID.
- Opportunity lifecycle: whether a comparable opportunity existed before the move; what the player did; whether it remained, expired, was created or was prevented.
- Relationship evidence: attacker, target, defender, whether the defender is legally usable, relevant rays/squares and the verified continuation that proves the claim.
- Intent candidates: actions the move objectively attempted—attack, defend, develop, exchange, improve, restrict, break, promote or respond—without claiming which one the player believed.
- Opponent-plan evidence: only concrete threats, opening-plan references, pawn breaks or multi-move continuations established by existing facts/PVs.
- Reflection eligibility: which answer could change the diagnosis and which options are factually possible.
- Knowledge context: prior explanation, assistance, independent solves, real-game applications, current focus and most recent comparable opportunity.
- Assistance provenance: hint, board reveal, line animation, correction or answer reveal, so guided success is never counted as independent success.
- Planner features: event novelty, personal recurrence, causal importance, transfer value, current-focus alignment and whether a positive example balances the review. Their numeric weights and caps remain data-lock decisions.

Stored engine analysis and existing V5 outputs are reused. Maia/Otter may later add findability or clock-conditioned likelihood fields, but those fields cannot change correctness, detector authorization or event outcome.

## 5. Gating — preventing the “smart-sounding but untrue coach” trap

- **Chess Truth Gate:** every event must cite stored engine/tablebase truth or deterministic board facts. Invalid FEN, illegal move or missing proof fails closed.
- **Authorization Gate:** Shadow remains audit-only; Caption may explain the current position; Plan/Mastery is required to diagnose recurrence, prescribe from the event or claim real-game application.
- **Single Authority Gate:** the planner consumes `MoveTeachingDecision`; it cannot call a competing caption brain. The frontend cannot infer chess from prose.
- **Canonical Reference Gate:** opening, trap, endgame and skill content are referenced by stable ID and source. A guard test rejects copied lesson bodies in plans.
- **Reflection Possibility Gate:** an option appears only when its backend predicate is true or it is an explicit self-report option such as `not_sure` or `none_of_these`.
- **Hindsight Gate:** belief questions lock before the explanation is revealed; responses after reveal are marked contaminated and cannot drive diagnosis.
- **Self-Report Restraint Gate:** one answer describes one position. A persistent player tendency requires repeated independent evidence.
- **Personalization Gate:** “again,” “you know this,” “you improved” and “you applied it” require explicit history and the appropriate quality surface.
- **Opportunity-Denominator Gate:** no absence-of-mistake mastery. Application/retention requires an eligible comparable opportunity with an explicit outcome.
- **Narrative Causality Gate:** selected chapters must form a board-supported cause-and-effect sequence; unrelated high-cp-loss moments cannot be stitched into a false story.
- **Friction Gate:** questions appear only when expected diagnostic information is non-zero and within the data-locked review budget.
- **Voice Gate:** all user copy passes the 600–1500 voice rules; it names pieces and squares before jargon and never translates centipawn loss into material lost.

## 6. Test strategy

**Phase 1 — stateless probes.** Build versioned position packets for every event outcome and reflection branch. Assert legal moves, typed evidence, authorization, option possibility, stable IDs, visuals and exact fail-closed reasons. Include wins, quiet moves, opponent moves, false pins, defended “loose” pieces, expired opportunities and `none_of_these`.

**Phase 2 — boundary suites.** Add tests for `MoveTeachingDecision → TeachableEvent → GameTeachingPlan`, reflection submit/reveal, `LessonResult`, regeneration versioning and flag-off byte parity. Existing caption boundary, detector-quality, personal-curriculum, Reflect and frontend review suites must stay green. Add a guard proving Review and Play with Coach produce the same move-level concept identity for the same packet.

**Phase 3 — offline production snapshot.** Run old and new pipelines over a versioned stratified corpus without production credentials. Report event coverage by concept and quality grade, silence, unsupported-claim rejection, selected-story coherence, reflection-option validity, personalized connection rate, lesson reach and old/new visible diffs. Numeric planner candidates are compared here; no formula is selected in advance.

**Phase 4 — human review.** Mohit and at least two coaches review blinded old/new outputs and the board evidence. They grade chess truth, importance, explanation clarity, personalization, reflection usefulness, story coherence and next-action quality. Any critical false chess claim blocks rollout regardless of average score.

Frontend tests cover keyboard/touch selection, reveal locking, board arrows, chapter navigation, refresh/re-entry, loading/error states, mobile layout and accessibility. E2E proves one complete path: open review → answer before reveal → inspect visual → start prescribed practice → emit learning event.

## 7. Risk + rollback

**Feature flag:** `PERSONALIZED_GAME_REVIEW_COACH_ENABLED=false` by default. Shadow generation may run while visible responses remain legacy. The stored plan includes `rollout_mode` and never overrides legacy fields while the flag is false.

**Primary risks**

- Sparse promoted detectors make the review truthful but quiet. Mitigation: report coverage by concept and promote detectors through evidence packets; never widen with unsupported claims.
- Too many chapters or questions reduce completion. Mitigation: data-lock the planner and friction budget before visible rollout.
- Reflection options lead the player or expose the answer. Mitigation: possibility and hindsight gates plus blinded coach review.
- A game story falsely implies causality. Mitigation: require linked event evidence and an explicit story verifier; otherwise render independent moments without a causal bridge.
- Duplicate learning writes inflate mastery. Mitigation: idempotent source-event IDs and one learning adapter.
- Old stored reviews and new plans disagree. Mitigation: schema/version matching and lazy regeneration behind the flag until backfill policy is approved.
- Review and Play with Coach drift. Mitigation: shared boundary packets and a cross-surface parity test.

**Rollback:** set `PERSONALIZED_GAME_REVIEW_COACH_ENABLED=false` and restart the backend/frontend deployment. The API returns the current V5 fields and the frontend renders the legacy review. Additive `game_teaching_plan` and reflection fields remain inert and auditable; no destructive database rollback is required. If a content migration causes drift, revert its adapter commit while retaining canonical source data.

## 8. What this spec does NOT cover

- Authoring or promoting every missing detector; each detector keeps its independent quality packet and promotion process.
- A replacement engine analysis pipeline or rerunning Stockfish for stored games.
- Free-form chess chat, LLM narration or LLM-generated reflection options.
- Maia/Otter integration beyond reserving optional human-likelihood evidence fields.
- Rebuilding Learning, Progress, Home or Play with Coach UI.
- Final content expansion for every opening, trap, positional theme or endgame; this architecture makes existing and future canonical content reachable.
- Bulk production regeneration before shadow, A/B and rollout gates pass.
- A fixed promise that every game will contain every chapter type; silence is valid when evidence is absent.

## 9. Implementation order

1. **Phase 0 — lock evidence and migration decisions.** Produce source inventory, detector-to-concept authorization matrix, endgame-source comparison, reflection implementation bake-off, planner candidate definitions and versioned reference corpus. Run the numeric data locks. Expected commit: `docs(data): lock personalized game review evidence and migration choices`.
2. **Phase 1 — contracts only, no visible behavior.** Add typed contracts, serializers, guard tests and flag-off parity tests. Persist nothing and render nothing. Expected commit: `feat(review): add game teaching contracts behind default-off flag`.
3. **Sign-off gate:** Phase 2 does not start until Mohit approves §10 decisions and Phase 0 measurements.
4. **Phase 2 — canonical event and reflection adapters.** Extend the central decision projection, adapt backend quick tags, store event-scoped reflections and prove no client-invented options are needed. Default off. Expected commit: `feat(review): unify verified events and structured reflection`.
5. **Phase 3 — planner in shadow.** Generate `GameTeachingPlan` alongside legacy output, run offline corpus comparison and human validation, but do not render it. Expected commit: `feat(review): generate personalized game plans in shadow`.
6. **Phase 4 — learning loop in shadow.** Emit idempotent review/practice events and compare learner projections without changing visible mastery. Expected commit: `feat(review): connect review lessons to evidence ledger in shadow`.
7. **Phase 5 — frontend default-off.** Add story, chapter, reflection and next-action components. Flag false preserves the existing DOM and behavior. Expected commit: `feat(review-ui): render personalized coach review behind flag`.
8. **Phase 6 — Mohit + coach A/B for one week.** Enable only for the validation accounts; compare old/new on the same games and collect manual findings plus instrumented behavior.
9. **Phase 7 — 10% rollout for one week.** Monitor false-claim reports, review completion, reflection completion, follow-up starts, latency, regeneration failures and support complaints. Automatic rollback on any critical truth failure.
10. **Phase 8 — 100% rollout.** Enable after the pre-locked gates pass; continue old/new audit logging during the observation window.
11. **Phase 9 — delete legacy after two clean weeks at 100%.** Remove post-game selection ownership from `decryption_voice.orchestrator`, remove `_generateThoughtOptions`, retire duplicate intent/reflection adapters and stop writing obsolete voice fields after consumers migrate. Expected commit: `refactor(review): remove legacy parallel coaching paths`.

## 10. Decisions / Open questions for Mohit

Mohit approved the recommended direction on 2026-09-01:

1. **Authorization ladder — approved:** Caption-grade may explain one position. Plan/Mastery-grade is required for recurrence, prescription and applied/retained claims.
2. **Endgame canonical owner — approved and measured:** `backend/data/coaching/endgame_theory_tree.json` is canonical. Its 18 lessons contain 54/54 legal checked answer moves; the six-lesson legacy file has no practice positions and four illegal stored solution lines. Stable legacy IDs must resolve through an adapter, and unique teaching text must be migrated before retirement.
3. **Reflection placement — approved:** inline Game Review reflection is canonical; `/reflect` becomes a queue/deep-link into the same event contract.
4. **No-text default — approved:** normal reflection is options-only with `not_sure` and `none_of_these`; optional board-line demonstration remains, free typing does not.
5. **Historical reviews — approved direction:** lazy regeneration first; active-user backfill only if Phase 0 cost and revisit measurements justify it.
6. **Planner and mastery numbers — approved as unlocked:** moment caps, question budget, selection weights and mastery transitions remain blocked until the required corpus bake-offs produce auditable locks.
7. **Validation timing — approved:** independent Mohit/two-coach validation is the final internal rollout gate before visible release, not a blocker for Phase 1 contracts. The representative full-game packet must exist before the Phase 3 planner can leave shadow, and parity fixtures must exist before Phase 2 changes live adapters.

Phase 0 source and coverage decisions are recorded in `docs/personalized_game_review_phase0_data_lock_2026_09_01.md` with the aggregate snapshot at `backend/data/corpus_snapshots/personalized_game_review_phase0_2026-09-01.json`. Unsupported behavioral numbers remain explicitly unclaimed. Product implementation remains subject to the separate pre-code audit and representative-review requirements in the signed scope.
