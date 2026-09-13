# Deterministic Teaching Intelligence — Pre-Code Audit

**Date:** 2026-09-13  
**Scope:** `docs/deterministic_teaching_intelligence_scope.md`  
**Data lock:** `docs/deterministic_teaching_intelligence_data_lock_2026-09-13.md`

## PRE-CODE AUDIT: PASS — EVIDENCE PREPARATION ONLY

The first implementation slice may prepare the fresh blind evidence cycle. Product proof-family implementation remains blocked until the fresh 100-game Codex inventory is frozen and the second data lock selects the families from measured gaps.

### 1. Literal UI mockup exists — PASS

The signed-off scope shows the actual player journey and literal copy for:

- the coach-selected game and reason;
- the connected whole-game story;
- opening purpose;
- a position-relative question;
- a missed line with replay and retry;
- an opponent opportunity;
- a positional exchange lesson;
- demonstrated good play;
- exact and absent endgame states;
- the final memory cue and honest learning status.

No schema or database shape was used as a substitute for the player contract.

### 2. Headlines are ideas and geometry, not SAN — PASS

The featured tactical headline is “Attack two pieces at once,” not `...d5`. Move notation appears inside the explanation and replay as evidence. Opening, exchange, opponent-plan and endgame headlines name what the player should understand rather than a historical game or move number.

### 3. Thresholds come from data — PASS FOR THIS SLICE

The fresh corpus lock cites a live anonymous census of 6,942 eligible games across 42 players. The eight-game player floor, 34-player holdout, 100-game development set, three-game development cap and rating allocation are derived from the observed per-player and rating distributions.

The three-featured-moment cap, candidate budget, selector order, explanation length and validation thresholds are inherited from earlier measured locks with their cited results. They are not reopened.

No proof-family frequency floor or priority formula is guessed. Product proof-family work is explicitly blocked until the fresh blind inventory produces the discriminating distribution and a second lock.

### 4. Success changes behavior — PASS

The primary release gate is useful causal teaching in the authorized rendered experience, evaluated against the current visible review with a paired player-clustered confidence requirement. Player recognition is measured on a different position before assistance, and later unassisted games remain the only evidence of real transfer. Activation, raw fact coverage and review impressions are diagnostic metrics rather than the success claim.

### 5. Deferred work remains deferred — PASS

The evidence slice does not add a detector, template, ranker, UI behavior, runtime model, historical backfill, rollout or deployment. Community explanations, reputation, human coaching, broad positional labels and mastery from practice remain out of scope. Maia/Otter remain candidate-ordering inputs only and are not needed to build the blind evidence packet.

### 6. Mohit explicitly approved the scope — PASS

Mohit approved the Section 0 decision with `extend` and approved implementation after the full scope with `go code` on 2026-09-13.

## Single-source-of-truth audit

**Concept being extended:** deterministic move-level chess truth and its player-facing teaching explanation.

Canonical owners already exist:

- `caption_facts.py` owns typed causal board and stored-line facts;
- `caption_pipeline.MoveTeachingDecision` owns the complete move teaching decision;
- `game_review_event_adapter.py` projects authorized decisions into review events;
- `game_review_contracts.py` owns event and plan contracts;
- `game_review_planner.py` owns selected moment ordering and caps;
- `whole_game_review_composer.py` presents the connected story without detecting chess again;
- `detector_quality.py` owns surface authorization;
- existing opening, trap, endgame and mastery sources retain their respective domain ownership.

**Decision:** extend these canonical owners only after the second data lock. Do not create another fact table, recognizer, caption renderer, principle bank, phase detector or concept taxonomy.

The evidence-preparation slice extends the existing `export_whole_game_review_evidence.py` selection and privacy machinery. Its packets are immutable evidence artifacts, not a new source of production chess knowledge.

## Authorized first implementation slice

- Reconcile the prior isolated whole-game branch onto current `origin/working-code` without whole-file replacement over newer upstream changes.
- Extend the existing evidence exporter with a new selection version that reconstructs and excludes the earlier development and holdout memberships.
- Select and seal the fresh 34-game holdout before the fresh 100-game development set.
- Export the blind development packet separately from the current player-visible baseline.
- Add deterministic membership, overlap, privacy, answer-hiding and reproducibility tests.
- Produce the identity-free census and packet fingerprints.
- Conduct and freeze Codex's complete-game chess inventory before joining the current product baseline.
- Produce the measured proof-family gap report and return to `/lock-via-data` before product logic changes.

## Still blocked after this audit

- New or changed chess proof families.
- New detector logic or promotion.
- Caption templates or player-facing wording changes.
- Story-ranking changes.
- UI changes.
- Review regeneration, migration, rollout, push or production deployment.

Those items require the second data lock and a focused pre-code recheck against the selected families.

