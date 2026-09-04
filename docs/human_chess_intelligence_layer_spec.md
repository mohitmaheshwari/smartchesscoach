# Human Chess Intelligence Layer — Architecture Spec

**Status:** DRAFT v1 — implementation requires bake-off verdicts and final Mohit approval  
**Date:** 2026-08-31  
**Scope:** `docs/human_chess_intelligence_layer_scope.md`  
**Research gate:** `docs/human_chess_intelligence_bakeoff_protocol.md`

## 1. Problem

ChessGuru has strong raw ingredients—stored Stockfish analysis, named detectors, game history, lessons, puzzles, coaching focus, and mastery—but they do not yet form one reliable interpretation loop.

The current product can identify many bad moves, yet a player still sees generic explanations, incomplete personal connections, crude puzzle difficulty, approximate board complexity, pattern/rating retrieval presented as similarity, and fragmented proof that an idea was learned and then transferred to real games. Game Review is the clearest symptom: its verified central caption can be displaced by a parallel 19-template voice path, and a live audit found 10.4% of sampled mistake/blunder captions lacked a causal WHY.

The system must translate chess truth into one simple coaching explanation: what happened, why it happened on this board, whether it is part of this player's demonstrated pattern, what to learn next, and what later evidence would prove improvement. Maia-2/Otter may add human-likelihood context and Fathom may add exact endgame truth, but neither may replace Stockfish, detector authorization, or measured player history.

## 2. Product Shape and Outcomes

The layer is an extension of the existing coaching architecture:

```text
games + stored analysis + clock provenance
                 |
       chess-truth adapters
      Stockfish / Fathom-Syzygy
                 |
    human-policy evidence (shadow first)
        Maia-2 / Otter / baseline
                 |
 authorized detectors + player history
                 |
 build_move_teaching_decision (one authority)
                 |
 verified renderer + surface adapters
 Game Review / Training / PWC / Plan / Progress
                 |
 attempt -> assistance -> retention -> game transfer
```

Every move/lesson decision resolves to one of four honest outcomes:

- **Board truth only:** explain the position without claiming a personal weakness.
- **Human-context evidence available:** describe what is likely hard to notice at this level, without using it as truth.
- **Personal connection authorized:** connect to the player's history because the detector and evidence meet the speaking gate.
- **Insufficient evidence:** omit the claim and record why it was not measured.

The visible experience remains conversational: one lesson at a time, one board-specific WHY, one action, and a clear later check. Internal probabilities and centipawn values stay out of player copy.

## 3. Schema and File Changes

### Canonical decision contract

Extend the existing `MoveInputs` and `MoveTeachingDecision` owned by `backend/services/caption_pipeline.py`; do not create a parallel caption decision object. Add typed optional fields:

- `truth_evidence`: source, version, position fingerprint, played/better move, evaluation/result preservation;
- `human_policy_evidence`: provider, model version, input fingerprint, legal candidate probabilities, calibration segment, clock mode;
- `decision_context`: complexity evidence, time evidence, candidate-set evidence, phase;
- `personal_evidence`: detector ID/version/quality grade, supporting game/move IDs, recurrence/recency, current focus relation;
- `teaching_target`: concept/skill ID, board-specific causal mechanism, transferable instruction;
- `verification`: eligible claims, rejected claims with reason codes, renderer version.

Absent evidence remains null with an explicit availability reason. It is never coerced to a neutral score.

### Model-neutral adapters

Introduce one internal human-policy protocol, with providers behind it:

- `HumanPolicyRequest`: FEN, legal moves, player/opponent rating, time-control metadata, optional validated clocks/history;
- `HumanPolicyEvidence`: normalized legal-move distribution, entropy, provider/model provenance, latency, coverage, warnings;
- provider implementations for the selected Maia-2/Otter candidates and an offline baseline;
- one validation layer that rejects illegal, incomplete, mismatched, or unversioned output.

Provider output is derived evidence, not an authority. A provider can be replaced without changing downstream coaching contracts.

### Exact endgame adapter

Add a Fathom/Syzygy truth service returning WDL, DTZ where available, legal result-preserving moves, tablebase provenance, and coverage reason. Attach the proof to the owning lesson, puzzle, detector fixture, or move decision; do not create a second mastery record.

### Derived evidence storage

Use a regenerable cache keyed by position fingerprint, complete model-input fingerprint, provider/model version, and policy configuration. Cache records must include expiry/retention policy and must never contain credentials. Selected evidence referenced by a user-facing decision is stored with the decision provenance needed to reproduce it.

The existing production `games.human_model` field may become the canonical clock/model prerequisite only after its producer, schema, validation, and migration ownership are committed. Until then it is research-only and untrusted.

### Existing authorities to extend

- caption/teaching decision: `backend/services/caption_pipeline.py`;
- active focus: `user_active_focus` through `focus_bridge`;
- lesson lifecycle: `learning_sessions` through `teaching_engine`;
- mastery: `concept_mastery_service`;
- detector speaking authority: `detector_quality`;
- engine truth: stored Stockfish analysis;
- player evidence: existing games, observations, attempts, and coaching memory with versioned joins.

`decryption_voice/concept_templates.py` becomes a renderer/input library under the central decision, not a competing selector. Any other route that authors move meaning independently must be migrated or explicitly classified as non-authoritative display copy.

## 4. New Facts and Data Flow

### Human-policy facts

Store model identity, model-input fingerprint, legal-move probabilities, rank of played move, rank of safe candidates, entropy, clock/history availability, calibration segment, and inference warnings. Never store “panic,” “confidence,” “understood,” or “knew.”

### Truth facts

Stockfish facts include the existing stored evaluation and line provenance. Tablebase facts include material eligibility, WDL/DTZ, legal result-preserving set, and file/version provenance. Tablebase truth supersedes heuristic endgame claims for covered positions.

### Decision-context facts

Complexity is built from a formula selected by bake-off over explicit features. Positional similarity records the method/version, query fingerprint, match features, exclusions, and relevance score. Neither label is user-visible until validated.

### Personalization facts

A personal statement must cite repeated observations from an authorized detector, recent evidence, the current focus or a justified next concept, and contradictory/clean evidence. One surprising move is a board event, not a permanent trait.

### Learning loop events

Normalize the existing lifecycle without replacing it:

1. diagnosis exposure;
2. explanation understood/uncertain response;
3. unassisted first attempt;
4. assisted or revealed attempt;
5. delayed retention check measured in games with calendar backstop;
6. transfer opportunity in a real game;
7. clean or repeated outcome;
8. focus review and plan adjustment.

Assisted success cannot count as independent mastery. “Not measured” must remain distinct from failure.

## 5. Safety, Honesty, and Authorization Gates

1. **Legality gate:** all candidate moves must be legal in the exact position.
2. **Truth gate:** chess claims require stored Stockfish evidence or covered tablebase proof.
3. **Soundness gate:** human-policy likelihood may rank only candidates already inside the data-locked safe set.
4. **Detector gate:** named weaknesses and personal traits require an authorized detector grade.
5. **Evidence gate:** personal claims require sufficient recent, repeated, joinable observations; exact thresholds come from the selection data lock.
6. **Clock gate:** rushed/time-pressure language requires validated clock evidence and a promoted clock diagnosis; otherwise time is not measured.
7. **Mastery gate:** unassisted attempt, retention, and game transfer are separate states.
8. **Renderer gate:** every factual caption slot must be traceable to typed evidence and pass the board verifier.
9. **Version gate:** unversioned model, tablebase, detector, or schema output cannot speak.
10. **Failure behavior:** fail closed for unsupported claims while preserving a useful board-truth explanation whenever possible.

No LLM is permitted to choose chess truth, invent causality, or create personal evidence. If an LLM renders approved facts, it receives only the eligible typed facts and its output is revalidated before display.

## 6. Test Strategy

### Unit and contract tests

- provider request/output schema, legal-move normalization, clock absence, and model-version rejection;
- tablebase WDL/DTZ and multiple-valid-answer cases;
- `MoveTeachingDecision` eligibility and rejection reason codes;
- assisted/mastery/transfer state separation;
- exact skill/concept join normalization and legacy aliases;
- parallel caption paths cannot outrank the canonical decision.

### Offline corpus tests

- frozen bake-off snapshots for calibration, coverage, latency, and regressions;
- detector- and rating-stratified caption gold;
- tablebase verification for every covered content item;
- chronological future-game evaluation with no player/position leakage;
- puzzle first-attempt difficulty calibration and distractor verification;
- complexity and similarity comparisons against current baselines.

### Integration and end-to-end tests

- one stored game flows through truth, detector, personal evidence, canonical decision, Game Review render, lesson, delayed check, and transfer update;
- missing provider/model/tablebase falls back without breaking review or training;
- stale caches are ignored after model/config/schema changes;
- all player-visible claims expose internal provenance for audit without exposing raw technical scores to the player;
- current backend core, frontend suites, and production verification script remain green.

### Human review

Mohit and the coach panel receive blind A/B reviews. They grade correctness first, then clarity, usefulness, personalization truth, and repetition. Any false chess or fabricated personal claim is a blocking defect, regardless of average score.

## 7. Risk, Flags, Rollback, and Observability

Independent default-off flags:

- `HUMAN_POLICY_SHADOW_ENABLED=false`
- `FATHOM_ENDGAME_VERIFY_ENABLED=false`
- `PERSONAL_CAPTION_DECISION_V2_ENABLED=false`
- `HUMAN_POLICY_PUZZLE_DIFFICULTY_ENABLED=false`
- `HUMAN_POLICY_PWC_OPPONENT_ENABLED=false`
- `POSITION_COMPLEXITY_V2_ENABLED=false`
- `POSITION_SIMILARITY_V2_ENABLED=false`

Risks include model/license drift, inference cost, calibration drift, clock reconstruction errors, false personalization, user-visible silence from excessive gating, and duplicate authority. Mitigations are pinned weights/hashes, shadow mode, coverage dashboards, typed rejection reasons, safe fallbacks, independent flags, and canonical-path tests.

Every feature retains the current behavior as rollback until its observation period passes. Rollback is a flag change plus cache invalidation; it does not rewrite historical attempts or mastery. Observability must report coverage, fallback reason, calibration segment, latency, caption rejection class, truth source, and user-surface reach.

## 8. Explicitly Out of Scope

- replacing Stockfish with Maia-2 or Otter as chess truth;
- using Maia-3 without a separate AGPL/legal decision;
- bulk re-running Stockfish over already-analyzed games;
- claiming guaranteed Elo gains or a fixed “1100 to 1200 in 21 days” result;
- inferring psychology, emotion, or intention from move probability;
- rebuilding the entire attempt/mastery store before adapters prove insufficient;
- replacing python-chess with fastchess in the product runtime;
- a second learner profile, curriculum engine, caption pipeline, or lesson lifecycle;
- exposing probabilities, centipawns, model names, or research metrics in normal coaching copy.

## 9. Implementation and Rollout Order

0. Lock the research manifests, split candidates, provenance schemas, and decision thresholds through data.
1. Build offline Fathom and human-policy research adapters; no routes, production writes, or UI.
2. Run the complete bake-off and publish ADOPT/SHADOW/REJECT verdicts.
3. Add the model-neutral evidence contracts and derived cache behind shadow flags.
4. Extend the canonical caption decision; shadow-diff it against V5 and remove selector precedence from parallel voice templates.
5. Add Fathom verification to endgame content admission, puzzle ambiguity checks, and eligible move explanations.
6. Add shadow puzzle difficulty and verified distractors; promote only after first-attempt calibration evidence.
7. Add a selected human-like Play-with-Coach opponent behind the existing soundness guard; preserve the current opponent as fallback.
8. Promote clock-conditioned context only if its ablation wins and the clock producer is versioned.
9. Add validated complexity and positional-similarity services.
10. Connect the normalized learning events to focus review and personalized plan updates.

Each user-facing feature rolls out independently: default off → Mohit plus coach-panel A/B for at least one measured review cycle → 10% eligible users with explicit monitoring → 100% only after the predeclared gates pass → remove that feature's legacy path after two clean weeks and a rollback review. Pre-launch behavior is not used as an engagement baseline.

## 10. Decisions and Open Questions

Locked decisions:

- extend the current coach rather than create a new architecture;
- keep Stockfish/tablebase as truth and human models as behavioral evidence;
- extend `MoveTeachingDecision` as the single caption/teaching authority;
- preserve current focus, lesson, mastery, and detector-quality authorities;
- use player-facing conversational language, never internal metrics;
- track learning through unassisted attempt, retention, and game transfer;
- deploy no model before a reproducible offline bake-off.

Must be decided from evidence before implementation:

- Maia-2, Otter, both for different jobs, or neither;
- validated clock producer and whether clock conditioning adds enough value;
- the safe-candidate loss definition for sound-and-findable moves;
- local Syzygy coverage and storage/runtime strategy;
- human-policy cache retention and acceptable latency/cost envelope;
- promoted caption quality gates and renderer choice;
- selected complexity formula and similarity method;
- minimum evidence for a personal statement, curriculum change, and mastery transfer;
- whether the coach panel's blind review reveals category-specific rollout needs.

Implementation is blocked until the bake-off decision packet answers these questions and Mohit approves the resulting build sequence.
