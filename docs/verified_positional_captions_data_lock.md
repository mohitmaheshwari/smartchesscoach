# Verified Positional Captions - Data Locks

These decisions use the live `positional_reason_queue` and `user_pattern_events` collections measured on 2026-09-09. The queue measurement used all 240 stored positions. The engine comparison used Stockfish 17.1 with 20,000 nodes per root move and MultiPV 5. The mastery replay collapsed repeated events to one outcome per user, pattern, and game, with a miss taking precedence when both outcomes occurred in one game.

## Decision 1: positional queue eligibility

**DECISION LOCKED:** A position may enter the positional gold set only when it has the explicit `eligible_positional` disposition and a complete contrastive proof. Centipawn loss and engine rank may order the review queue, but neither may authorize a teaching reason.

**VALUE:** No universal centipawn or expected-result cutoff. The deterministic promotion gate is `disposition == eligible_positional` plus complete better-move facts, played-move facts, contrast, reusable lesson, and reviewer provenance.

**EVIDENCE:**

- The queue's stored loss values range from 153cp to 9,666cp, with a median of 311cp. The distribution has no boundary that separates positional teaching from tactics or decided games.
- Twenty-six positions have a fresh stored loss of at most 175cp, while the fixed-node WDL comparison finds 65 positions with no more than a one-percentage-point expected-result drop. The candidate filters disagree too strongly to treat either as truth.
- The deeper comparison changes the stored best move in 63 of 240 positions. Engine rank is therefore evidence to review, not a stable semantic label.
- The product already has human dispositions for `not a mistake` and `already decided`. Preserving those judgements is safer and more auditable than recreating them from an arbitrary score threshold.

**REJECTED CANDIDATES:**

- `fresh_cp_loss <= 175` means `not a mistake`: it catches 26 positions but confuses evaluation size with teaching value.
- `WDL drop <= 1%` means `not a mistake`: it catches 65 positions because Stockfish's WDL model saturates in already winning and already losing positions.
- `abs(eval_before) >= N` means `already decided`: counts change from 114 at 300cp to 50 at 500cp and 21 at 600cp, with no defensible cliff.

**MEASUREMENT METHOD:** Read-only Mongo histograms plus a fixed-node Stockfish replay of every queued FEN, played move, and stored best move.

## Decision 2: acceptable moves and concept hits

**DECISION LOCKED:** A concept hit is based on a verified board goal, not equality with one engine-best move.

**VALUE:** The played move must satisfy the concept's deterministic aligned-move predicate, preserve every required fact after the move, and pass the existing engine-safety/severity gate. The event is `unknown` when those conditions cannot prove either hit or miss.

**EVIDENCE:**

- Stockfish selected a different first move from the stored best in 63 of 240 positions.
- In 53 of those 63 positions, the stored move remained within two percentage points of the newly selected move's expected result. Penalizing those moves solely because their rank changed would create false misses.
- Existing caption principles already describe aligned moves and engine endorsement. Reusing that semantic rule preserves one source of truth.

**REJECTED CANDIDATES:**

- Exact equality with engine rank 1: unstable across analysis runs and falsely treats equivalent moves as failures.
- Any move within a global centipawn tolerance: positions with the same numerical gap can teach completely different ideas.
- Any move within a global WDL tolerance: saturated won and lost positions make strategically different moves appear identical.

**MEASUREMENT METHOD:** MultiPV 5 comparison of the stored best, played move, and fixed-node best move on all 240 queue positions.

## Decision 3: mastery streak

**DECISION LOCKED:** Retain the existing requirement of three consecutive clean concept opportunities for V1. Count only explicit `hit` opportunities as clean; `unknown` and ineligible dispositions are neutral.

**VALUE:** `streak_required = 3`, inherited from the existing mastery tracker.

**EVIDENCE:**

- The replay covered 110,010 events, 1,007 user-pattern pairs, 65,717 hits, and 44,293 misses.
- The next-opportunity miss rate falls gradually: 35.41% after at least one consecutive hit, 33.43% after two, 31.45% after three, 29.30% after four, and 27.26% after five. There is no cliff supporting a replacement threshold.
- Three leaves 13,762 later opportunities for continued measurement, compared with 9,321 at four and 6,507 at five. Raising the threshold would reduce usable evidence without a sharp reliability gain.
- The value three already exists in `concept_mastery_tracker.DEFAULT_STREAK_REQUIRED`; retaining it avoids an unsupported behavior change.

**REJECTED CANDIDATES:**

- Two consecutive hits: 33.43% later miss rate and weaker evidence of repeated application.
- Four consecutive hits: lower later miss rate, but the improvement is gradual and removes 32% of the follow-up sample available at three.
- Five consecutive hits: lower later miss rate, but removes 53% of the follow-up sample available at three and has no distinct distribution cliff.

**MEASUREMENT METHOD:** Chronological per-game replay of the live pattern-event ledger, collapsing duplicate same-game concept events and giving misses precedence.

## Decision 4: caption quality gate

**DECISION LOCKED:** Specific claims require complete independent verification; teaching usefulness is evaluated separately from factual truth.

**VALUE:** 100% verifier support for shipped claims and at least 85% held-out teaching match for a promoted concept family.

**EVIDENCE:**

- The existing caption-distillation workflow defines verified truth as a hard ship gate and uses 85% verified-and-gold match as the promotion target.
- A reason can be true yet fail to distinguish the better move from the played move. The contrastive proof requirement prevents that class of empty explanation.
- The scope's blind-review questions test the two additional outcomes the user requested: understanding this position and carrying the lesson to another game.

**REJECTED CANDIDATES:**

- Overall caption pass rate that mixes truth and teaching value: a high average can hide false board claims.
- Model confidence as the ship gate: confidence is not proof and is not calibrated against this queue.
- Coverage as the primary target: forcing a caption increases fluent but unsupported explanations.

**MEASUREMENT METHOD:** Existing distillation quality contract plus held-out contrastive review of eligible positional examples.

## Rollout lock

The stricter event-ledger projection uses the existing `DETECTOR_QUALITY_GATE_ENFORCED` switch. With the switch off, the current V5 mastery and legacy pattern-progress readers remain unchanged. With it on, only events with an explicit opportunity, a known hit or miss, complete proof provenance, `tracker_eligible=true`, a currently Mastery-authorized quality ID, and a passing concept-specific `tracker_proof` may change or describe progress. Candidate admin reasons, unknown outcomes, and demoted detectors remain neutral.

The 240-position queue is review data. No score threshold or semantic similarity job may silently assign its dispositions. RAG or embeddings may suggest offline duplicate groups later, but runtime captions and mastery use canonical IDs, deterministic board predicates, and independent verification.
