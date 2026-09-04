# Human Chess Intelligence Layer — Scope

**Status:** LOCKED v1 — Mohit approved with “go ahead” on 2026-08-31. Research protocol and architecture remain pre-code gates.
**Parent product scope:** [`complete_coaching_system_scope.md`](complete_coaching_system_scope.md).

## 0. Existing surfaces audit

### What already serves this user need

| Existing surface or authority | What it already provides | Decision |
|---|---|---|
| Complete Coaching System scope | The approved product contract: one coach across Home, Review, Training, Play with Coach and Progress | **INHERIT.** This scope closes intelligence and translation gaps inside that product; it does not define another coach. |
| Game Review (`/game/:gameId`, `LabV2` → `GameDecryptionV5`) | Board-based review with stored V5 move records, Stockfish evidence, captions, key moments and retry material | **EXTEND.** Keep the surface and make its explanation genuinely causal, personal and continuous with the active plan. |
| `services/caption_pipeline.py::build_move_teaching_decision` | The deterministic central caption decision used by V5 review and production Play with Coach; it verifies board claims and emits structured metadata | **EXTEND AS THE SOLE AUTHORITY.** Human-policy evidence and player context become typed inputs. They may change emphasis, never chess truth. |
| `decryption_voice/concept_templates.py` and other live prose paths | A second 19-template Game Review narrator plus smaller puzzle, opening and secondary-review prose generators | **CONSOLIDATE.** No competing path may outrank or bypass the central caption decision after migration. |
| Stockfish analysis and stored move evidence | Legal moves, evaluations, best move, principal variations and the truth foundation for detectors and captions | **KEEP.** Stockfish remains the soundness authority. Human models never overrule it. |
| Syzygy-backed detector gold and rule-of-square lock | Versioned tablebase evidence for a bounded endgame detector | **EXTEND.** Add a general Fathom/Syzygy verification adapter rather than another endgame truth source. |
| Detector registry and `detector_quality` | Tactical, positional, opening, trap and endgame recognizers with Plan/Caption/Shadow/Disabled authorization | **KEEP AS THE SPEAKING GATE.** Model probabilities are evidence, not detector promotion. |
| `user_active_focus` and `focus_bridge` | Canonical current priority and surviving instruction | **KEEP.** Captions read eligible focus context through the canonical bridge; they do not select or rewrite the focus. |
| `learning_sessions` and `services.teaching_engine` | Resumable lesson state and typed participation/attempt evidence | **EXTEND.** Practical difficulty and hint policy may consume human-policy evidence, while events remain canonical. |
| `services.concept_mastery_service` | The chosen learner-facing mastery and next-step projection | **KEEP.** Maia, Otter, puzzles and captions append evidence; none publishes a second mastery label. |
| Community puzzle and training pools | Real positions from the player's and community's games, presently selected mostly by broad labels and rating bands | **EXTEND.** Add verified decision-signature similarity and calibrated difficulty as derived indexes, not copied puzzle stores. |
| Production PGNs and `games.human_model` preparation | 13,597 of 14,516 games preserve `%clk`; 14,236 games have `human_model_prereq.v1` clock/rating preparation | **REUSE AND VERSION.** Treat the unexplained live preparation as input only after its producing script, provenance and determinism are versioned in the repository. |

### Measured problems this scope addresses

- A 2026-08-31 production audit of 500 games scanned 2,442 mistake/blunder captions. **254 (10.4%) had no detectable WHY**; the blunder failure rate was 12.6%.
- The WHY audit is only a floor. In Mohit's latest audited review, all four user mistake/blunder records had `weakness_match=false` and no `concept_id`; the associated coaching plans were generic or repeated.
- Game Review still contains a live 19-template concept narrator that can outrank the verified central caption path.
- The product has no repository implementation of Maia-2, Otter, Fathom or a model-neutral human-policy contract.
- Board complexity is not stored for Mohit's observations. The existing helper approximates complexity from move number, which is insufficient.
- Community retrieval currently means primarily same broad pattern and similar rating, not similar geometry, structure or decision problem.
- Attempt records do not consistently preserve first-attempt status, assistance, time or transfer eligibility, so model-based difficulty cannot yet become mastery evidence safely.

### Overlap and genuine differentiation

The product already analyzes moves, detects many chess ideas, stores real positions, runs lessons and tracks an active focus. The missing capability is not another analysis engine or another review page. It is a governed intelligence layer that separates:

1. what is objectively true;
2. what a human at this level is likely to see;
3. what this particular player has demonstrated;
4. why this decision failed here; and
5. how to translate that evidence into one useful coaching message.

### Overlap decision

**EXTEND the approved Complete Coaching System. CONSOLIDATE caption narration into the central pipeline. Add Fathom and the selected human-policy model behind evidence-only adapters. Do not create a new coach, player profile, mastery vocabulary, puzzle pool, caption path or UI destination.**

## 1. What it is

The Human Chess Intelligence Layer helps ChessGuru distinguish chess truth from human difficulty and individual learning. It uses exact endgame evidence, human-move probability and the player's own history to improve puzzle difficulty, coached-opponent behavior, position similarity and game explanations. Its main visible result is a Game Review that translates the player's actual decision in simple language: what they were trying to do, what changed on the board, why the move failed, what the better move accomplished, whether this resembles something they know or repeatedly miss, and one idea to carry into the next game. Every personal statement remains evidence-backed, and uncertainty is spoken honestly.

## 2. What the user sees

No new top-level page is added. Existing surfaces become consistent and more human.

### Game Review — position-specific and personal

```text
You checked with Ne3+, but the pawn on e5 was still available.

You had passed up that same capture on the previous move. The miss was not
calculation depth; you stopped scanning captures once you found an active move.

Try this next game:
Before playing a check, scan every capture once.

[ Show the reply ]  [ Let me retry ]
```

If history does not justify a personal cause:

```text
You checked with Ne3+, but the pawn on e5 was still available.

I can show what happened on the board, but I do not yet know whether this was
a one-off miss or something you need to study.

[ Show the reply ]  [ Let me retry ]
```

### Puzzle assignment — practical difficulty without engine language

```text
This position is close to the decisions you have been missing:
an active move is tempting, but one capture changes everything.

I am starting without a hint. If you need help, I will reveal one clue at a time.

[ Start ]
```

### Play with Coach — human opponent with a safety floor

```text
That reply is common in games around your level, and it creates the kind of
decision I want you to practise. The coach will never manufacture an absurd
blunder simply to let you win.
```

### Endgame lesson — exact and accepting

```text
Three moves keep this position won. Yours is one of them.

The shortest route is not the only correct route. Let us practise the idea that
all three winning moves preserve: keep their king cut off before pushing.
```

## 3. In scope (V1)

- Freeze a versioned, reproducible research corpus and chronological train/evaluation split from eligible 600–1500 player games.
- Recover clock history from original PGNs and version the producer for `human_model_prereq.v1`; no unexplained production-only enrichment remains authoritative.
- Run a Fathom/Syzygy audit across routed endgame lessons, detector gold, eligible community positions and a stratified real-game sample.
- Compare Maia-2, Otter with history, Otter with history plus real clock, a rating-frequency baseline and Stockfish as a deliberately non-human baseline.
- Measure actual-move likelihood, calibration, blunder-risk prediction, clock sensitivity, practical puzzle difficulty, latency and resource cost by rating band and time control.
- Run a bounded MultiPV probe for candidate-move research only; do not reanalyze the entire stored corpus.
- Define one model-neutral human-policy evidence contract containing model/checkpoint provenance, legal move probabilities, uncertainty, clock inputs and inference version.
- Keep every human-policy output in Shadow until its use case passes its own validation. One passing use case does not authorize every use case.
- Define board complexity as a derived, versioned decision-context record combining verified board facts, sound candidate structure and human-policy uncertainty.
- Define community similarity from verified position and decision signatures; rating and broad pattern may constrain retrieval but cannot be the similarity claim by themselves.
- Establish a stratified caption gold set covering tactics, piece safety, calculation, king safety, positional decisions, openings, traps, endgames, time-related errors and good moves.
- Grade captions separately for truth, causal explanation, better-move purpose, plain language, transferable lesson, non-repetition, personal evidence and confidence honesty.
- Consolidate all primary Game Review captions into `build_move_teaching_decision`; retire or adapt the competing `concept_templates` priority path after contract comparison.
- Add typed player-context inputs from `focus_bridge`, learning evidence and prior same-concept decisions. Context may select emphasis and continuity but may not alter verified board facts.
- Preserve a structured caption decision before rendering: position truth, failure mechanism, better-move purpose, player connection, transferable instruction, confidence and provenance.
- Feed first-attempt, assistance, elapsed-time and transfer eligibility into the canonical learning event stream before practical difficulty contributes to mastery.
- Roll out each player-facing use separately behind default-off flags with stored comparison evidence and rollback.

## 4. Explicitly out of scope (V1)

- Replacing Stockfish as the soundness authority.
- Treating Maia, Otter, an LLM or model attention as proof that a chess concept exists.
- Fine-tuning a personal neural model for each player.
- Shipping Maia-3 or any AGPL service without a separate legal and architecture decision.
- Replacing python-chess or rewriting the backend around fastchess.
- Reanalyzing every historical game with Stockfish.
- Promising a rating gain or a fixed number of improvement days.
- Declaring blindness, rushing, tilt, confidence or another psychological cause from a single move.
- Creating a new mastery collection, active-focus store, puzzle collection, caption system or player-facing progress vocabulary.
- Letting generated prose bypass the final deterministic claim verifier.
- Redesigning the Game Review page layout; this scope changes the intelligence and copy contract, not the page shell.
- Promoting every existing Shadow detector. Detector promotion remains evidence-specific work.

## 5. Success criteria

### Research validity

- Every reported result can be reproduced offline from a versioned corpus manifest, split manifest, exact model/checkpoint hashes and command.
- No player's later game appears in that player's earlier-history input, and no position from one game leaks across evaluation partitions.
- The chosen human-policy approach beats the simple rating-frequency baseline on held-out ChessGuru decisions and is better calibrated for the use case it is assigned.
- Clock-conditioned claims are evaluated only on records with reconstructed, internally consistent clock evidence.
- Model selection is use-case-specific: puzzle difficulty, opponent behavior and lapse-risk prediction may choose different winners.

### Chess truth and safety

- Fathom-backed positions preserve exact WDL for every accepted move; no lesson rejects a tablebase-equivalent correct move.
- Every player-facing candidate remains inside the empirically locked Stockfish soundness policy or exact tablebase result.
- Every model, detector, tablebase and caption claim carries versioned provenance.
- Shadow evidence cannot write a weakness, mastery state or player-facing causal claim.

### Caption quality

- Zero sampled player-facing captions contain a false board claim after independent verification.
- Every mistake/blunder caption with sufficient evidence explains the failure mechanism and the better move's purpose; terse fallback frequency improves materially from the measured 10.4% baseline, with the final target locked from the gold distribution.
- Every personal statement cites eligible prior evidence; when that evidence is insufficient, the caption explicitly stays position-specific.
- Blind coach review prefers the new translation over the stored baseline on the dimensions defined in the gold rubric; the rollout threshold is locked after the baseline round rather than chosen in advance.
- The same structured caption decision is rendered consistently in Game Review and Play with Coach, subject only to surface-length constraints.

### Learning and product effect

- Puzzle difficulty predicts first-attempt success better than the current cp-loss/difficulty labels on a held-out cohort.
- Assistance and first-attempt evidence reach `learning_sessions` and the canonical mastery projection without creating a second progress interpretation.
- For an eligible taught concept, later unassisted real-game opportunities can be compared with the pre-teaching baseline; the product may report improved, still recurring or insufficient evidence.
- A user can open Review, Training and Play with Coach and recognize the same focus and instruction without contradictory wording.

## 6. Open questions

- **Question:** Which model wins each human-policy use case: Maia-2, Otter without clock, Otter with clock or a governed ensemble?
  **Why unresolved:** Published accuracy does not establish performance on ChessGuru's 600–1500 corpus or product tasks.
  **Unblocking step:** Run the chronological bake-off and calibration analysis before selecting any production model.

- **Question:** What Stockfish candidate-soundness policy should constrain “findable” teaching moves and the coached opponent?
  **Why unresolved:** Stored analyses do not contain enough alternative candidate evaluations, and a fixed centipawn cutoff would be a gut lock.
  **Unblocking step:** Run the bounded MultiPV sample, inspect outcome/state changes by rating and position type, then lock via data.

- **Question:** Which board-complexity formulation best predicts mistakes and excess/insufficient thinking time?
  **Why unresolved:** No canonical complexity values currently exist.
  **Unblocking step:** Bake off candidate formulations using board facts, candidate spread, human-policy entropy and clock behavior on held-out games.

- **Question:** What caption-quality rollout threshold is high enough for trust without silencing too much useful teaching?
  **Why unresolved:** The current 10.4% no-WHY baseline does not measure deeper personalization, transfer or false-pass rates.
  **Unblocking step:** Build and double-review the stratified caption gold set, then lock thresholds from its distribution.

- **Question:** Should deterministic rendering remain the only production renderer, or may an LLM rewrite an already-verified structured decision?
  **Why unresolved:** Easy language may improve with constrained rewriting, but consistency, latency and claim drift must be measured.
  **Unblocking step:** Blindly compare deterministic and verifier-constrained rewrites on the same fact packets; no LLM receives authority over facts.

- **Question:** What local Syzygy coverage is operationally appropriate?
  **Why unresolved:** Exact coverage, storage and latency trade-offs differ for five-, six- and seven-piece tables.
  **Unblocking step:** Inventory eligible production positions and compare local storage/cache options using the Fathom audit corpus.

- **Question:** Who owns final manual chess adjudication for the caption gold set?
  **Why unresolved:** Mohit has offered a final panel of coaches, but reviewer assignment and disagreement resolution are not yet recorded.
  **Unblocking step:** Define the review packet, blinded rubric and adjudication rule before the final acceptance round.

## 7. Pre-code requirements

- Mohit explicitly signs off on this complete scope document.
- The research protocol identifies corpus eligibility, chronological split, leakage guards, metrics, baselines and artifact paths before any model is installed.
- The producer and provenance for existing `games.human_model` records are recovered or those records are regenerated from a committed, reviewed script.
- Model code, weights, data provenance, transitive dependencies and commercial-use obligations receive a recorded license review.
- Fathom, Maia-2 and Otter run only in isolated offline research environments during the bake-off; production requests do not depend on them.
- A read-only corpus snapshot or manifest makes the experiments reproducible without distributing production credentials.
- The bounded MultiPV population is specified and approved; no whole-corpus Stockfish reanalysis is permitted.
- The canonical caption call graph is reverified against the current branch and production flags; every competing live narrator has a named migration disposition.
- The caption gold rubric, sampling strata, independent board-verification method and reviewer packet are written before template or renderer changes.
- Every numeric threshold and formula is left open until its production distribution or bake-off result is measured and recorded through the data-lock process.
- Feature flags, comparison writes, rollback and deletion criteria are defined in the architecture spec.
- The working-tree baseline and relevant test suites are recorded before implementation.
- Mohit signs off separately on the subsequent architecture/spec decisions before the first production code change.
