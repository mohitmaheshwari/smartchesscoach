# ChessGuru proprietary coaching architecture

**Date:** 2026-09-04  
**Purpose:** Define the backend, chess-reasoning, data, ML, frontend, reliability, and proprietary-technology architecture that could make ChessGuru a genuine personalized coach rather than an engine plus captions.

## Executive answer

If a Google- or Microsoft-calibre engineering organization built ChessGuru, it would probably **not** start by inventing a stronger chess engine or training a giant chess LLM.

Stockfish already answers “what is objectively strong?” far better than the target player needs. Public human-move models such as Maia answer parts of “what might a human at this level play?” Large language models can express supplied facts. None of these answers the complete coaching question:

> Given this player, this position, their history, current focus, clock context, previous instruction, and likely misconception, what should the coach do now—and what later evidence would show that the intervention worked?

That is where ChessGuru should create new technology.

The proposed proprietary system is a **Chess Learning OS** composed of four core inventions:

1. **Chess Decision Graph** — a verified, machine-readable explanation of the decision: threats, candidates, consequences, concepts, and counterfactuals.
2. **Player Learning Twin** — a probabilistic model of what this individual can recognize, calculate, choose, execute, retain, and transfer under different contexts.
3. **Coach Policy Engine** — a restrained teaching policy that chooses whether to speak and which intervention will be most useful now.
4. **Transfer Proof Engine** — an opportunity-conditioned system that observes later games and distinguishes exposure, practice success, promising transfer, durable change, and relapse.

Together these are substantially more defensible than “we call Stockfish and ask an LLM to explain it.”

## First principle: three different questions require three different engines

| Question | Correct technology | Unsafe shortcut |
|---|---|---|
| What is true on the board? | Legal move generation, Stockfish, tablebases, verified opening/trap/endgame data | Asking an LLM |
| What is a human likely to see or miss? | Rating/time-control human-move model, behavioral history, clock data, error statistics | Treating engine rank as human difficulty |
| What should this player learn next? | Player learning state, prerequisites, focus policy, intervention outcomes, teaching constraints | Picking the largest centipawn loss or most common tag |

The product becomes intelligent only when these engines cooperate without confusing their roles.

## What already exists in ChessGuru

The repository is not starting from zero. It already contains early forms of the future architecture:

- `backend/services/chess_brain/chess_brain.py` coordinates a Stockfish truth layer, detector registry, lesson selection, and a player fingerprint.
- `backend/services/chess_brain/detector_registry.py` and `advanced_detectors.py` cover tactical, positional, endgame, and behavioral concepts.
- `backend/services/caption_facts.py`, `caption_facts_verified.py`, `caption_claim_verifier.py`, and `caption_pipeline.py` separate some board facts from narration.
- `backend/services/coach_conductor.py` tries to connect recurring player concepts to live coaching with restraint.
- `backend/services/coach_memory.py` stores cross-session memory.
- `backend/services/concept_mastery_service.py` has an evidence reducer and explicitly distinguishes “studied” from “proven in games.”
- `backend/services/coaching_puzzle_service.py` connects personal and community positions to practice.
- `backend/analysis_worker.py` and `backend/stockfish_service.py` provide an asynchronous engine-analysis base.

These are valuable prototypes. The architectural problem is that there are multiple overlapping brains, memories, threshold systems, lesson selectors, and output paths. Some important constants are hard-coded in individual services with comments saying they should later be tuned from telemetry. The next architecture should consolidate these ideas rather than add another parallel “smart” service.

## The target system

```text
 Web / Mobile experience
        |
        v
 Experience API / typed coaching contract
        |
        v
 +---------------------------------------------------------+
 |                   COACH ORCHESTRATOR                    |
 | context -> evidence -> player state -> policy -> action |
 +---------------------------------------------------------+
      |             |             |              |
      v             v             v              v
 Board Truth    Human Model   Learning Twin   Curriculum Graph
 Stockfish      Maia-style    skill state     prerequisites
 tablebases     likelihood    confidence      interventions
 legality       difficulty    retention       examples
      \             |             |              /
       +------------+-------------+-------------+
                            |
                            v
                  Chess Decision Graph
                            |
                 +----------+----------+
                 |                     |
                 v                     v
        Teaching/Review Compiler   Transfer Proof Engine
                 |                     |
                 +----------+----------+
                            |
                            v
                 Event ledger + observability
```

Quality, privacy, experimentation, cost, and versioning are control planes across every layer.

## Proprietary technology 1: Chess Decision Graph

### The problem

Stockfish returns evaluations and lines. A player needs a causal explanation. Most caption systems jump directly from engine output to prose, which creates brittle rules or hallucinated language.

### The proposed representation

For every teachable decision, create a graph whose nodes and edges are verified chess facts:

**Nodes**

- position before the move;
- move played;
- candidate moves;
- opponent forcing replies;
- attacked and defended pieces/squares;
- material and positional consequences;
- tactical motifs;
- opening/endgame structures;
- clock state;
- player concepts and current focuses;
- candidate intervention;
- expected observable outcome.

**Edges**

- `creates_threat`;
- `fails_to_answer`;
- `removes_defender`;
- `opens_line`;
- `overloads`;
- `forces_reply`;
- `transposes_to`;
- `demonstrates_concept`;
- `violates_principle`;
- `supports_claim`;
- `contradicts_claim`.

Every edge carries provenance: detector version, engine configuration, relevant line, confidence, and verification status.

### Why this matters

The same graph can power:

- a one-sentence beginner caption;
- a deeper advanced explanation;
- arrows and square highlights;
- a Socratic question;
- a retry position;
- a contrast example;
- a personal puzzle;
- a later transfer detector;
- a support/debug explanation of why the coach spoke.

This eliminates the present risk that review, training, and Coach Play each reinterpret the same position differently.

### Example

Suppose the player plays `Qf3` and misses an opponent fork.

The graph should not merely store `motif=fork`. It should express:

```text
Qf3 -> leaves c2 undefended
...Nd4 -> attacks c2 and e2
c2 contains a forcing check/fork consequence
Qe2 -> preserved both defenses
player previously missed knight double-attacks in low-clock positions
```

The teaching compiler can then say, at a lower level:

> Before moving the queen, check what it was protecting. After Qf3, the knight can jump to d4 and hit two targets.

For a more advanced player it may emphasize candidate comparison or prophylaxis. The chess truth remains identical.

## Proprietary technology 2: Player Learning Twin

### Not a personality profile

The twin is not “you are an aggressive player.” It is a time-aware estimate of capabilities, contexts, and uncertainty.

For each concept, track separate dimensions:

| Dimension | Meaning |
|---|---|
| Recognition | Did the player notice the relevant pattern or threat? |
| Calculation | Could the player calculate the forcing continuation? |
| Evaluation | Did they correctly judge the resulting position? |
| Selection | Did they choose the right candidate among alternatives? |
| Execution | Could they convert the plan or technique? |
| Retention | Can they recall it after delay? |
| Transfer | Can they apply it in a different-looking position? |

Each estimate includes:

- probability/distribution rather than a binary label;
- opportunity count and denominator;
- confidence interval or evidence strength;
- recency and decay;
- assistance level;
- context: time control, remaining clock, game phase, opening structure, side, and difficulty;
- source: imported game, Coach Mode, lesson, puzzle, or delayed test.

### Why current counts are insufficient

Ten clean games do not prove that a player learned a fork if no fork opportunity occurred. One correct guided move does not prove independent recall. One blunder under one second does not prove a general knowledge gap.

The learning twin models the latent capability behind observations. Bayesian Knowledge Tracing is a useful conceptual baseline because it explicitly updates uncertain skill state from learner interactions. ChessGuru will need a richer opportunity- and context-aware variant because chess positions are not interchangeable quiz items.

### Initial implementation

Do not begin with a neural network. Start with an interpretable probabilistic reducer:

```text
prior skill state
  + verified opportunity
  + action/result
  + assistance level
  + position difficulty
  + delay since teaching
  + context similarity
  = posterior skill state + uncertainty
```

The existing mastery reducer is a good seed but must be generalized across concepts and remove hard-coded concept-specific state logic from service files.

### Long-term model

After enough clean intervention data exists, train a specialized learner model to predict:

- next-opportunity success;
- delayed recall;
- transfer likelihood;
- relapse risk;
- which prerequisite is missing.

Prediction accuracy is not enough. The model must be calibrated, interpretable at the concept level, and compared with simple baselines.

## Proprietary technology 3: Counterfactual Error Attribution

### The real coaching question

“The move lost 180 centipawns” is not a diagnosis. The coach needs to distinguish among causes such as:

- failed to scan the opponent’s forcing move;
- did not see a piece was undefended;
- saw the tactic but stopped calculation early;
- evaluated the ending incorrectly;
- knew the principle but chose a tempting move;
- rushed under low time;
- remembered an opening line without understanding the position;
- executed the correct plan inaccurately.

### The engine

For a critical position:

1. Generate legal candidates.
2. Use MultiPV Stockfish to establish objective alternatives and refutations.
3. Use geometry and verified concept detectors to describe what changes between candidates.
4. Use a human-move model to estimate which candidates are natural at the player’s level and time control.
5. Compare the played move with previous decisions by this player.
6. Use optional low-friction evidence—what they clicked, which threat they identified, or a choice among two explanations—to refine the hypothesis.
7. Emit a ranked set of **cognitive hypotheses**, never a claim that the software read the player’s mind.

### Three-level output

```text
BOARD EVENT:       missed opponent knight fork
COGNITIVE SIGNAL:  forcing-reply scan likely stopped after checks
TEACHING TARGET:   after choosing a move, scan opponent checks/captures/threats
```

This separation is essential. The detector can be certain about the board event while uncertain about the mental cause.

## Proprietary technology 4: Coach Policy Engine

### What it decides

The policy engine is not a content recommender. It decides:

- whether to interrupt;
- what to prioritize;
- whether to explain, ask, demonstrate, retry, drill, or remain silent;
- how much detail to show;
- how difficult the next task should be;
- when to revisit a focus;
- when evidence is strong enough to advance or retire it.

### Inputs

- Chess Decision Graph;
- Player Learning Twin;
- active focuses and prerequisites;
- current mode: Review, Coach Mode, Play Mode, lesson;
- emotional/session context observable from behavior;
- time available;
- recent coach interventions and speech budget;
- intervention eligibility and quality authorization;
- expected learning value and player burden.

### Objective

Optimize for future independent behavior, subject to constraints:

```text
expected learning gain
  + continuity value
  + confidence value
  - interruption cost
  - cognitive overload
  - repetition fatigue
  - trust risk
```

Do not lock weights from intuition. Begin with transparent rules and log the candidates, chosen action, and eventual outcomes.

### When machine learning becomes justified

Only after the product records enough comparable interventions and delayed outcomes should it test a contextual bandit or outcome model. Contextual bandits have been used to choose learning activities, but optimizing immediate completion can produce engagement without durable learning. ChessGuru’s reward must include delayed retention and transfer, with safety constraints and randomized evaluation.

## Proprietary technology 5: Transfer Proof Engine

This is potentially ChessGuru’s most important invention.

### Opportunity-conditioned measurement

Most products say a player improved because:

- rating rose;
- puzzles were completed;
- the last game had fewer blunders;
- a course was finished.

Those measures are noisy or easy to game. ChessGuru should measure:

> When a later position contained a verified opportunity to use the taught behavior, did the player recognize and execute it independently?

For every concept, define:

- what constitutes an eligible opportunity;
- what counts as correct handling;
- allowed alternative moves;
- assistance exclusions;
- context similarity and transfer distance;
- minimum evidence for each user-facing claim;
- relapse/demotion rules;
- when the result should remain “insufficient evidence.”

### Claim ladder

1. **Observed:** the behavior occurred.
2. **Introduced/studied:** the player completed guided instruction.
3. **Remembered:** the player succeeded after delay without help.
4. **Promising in games:** the player handled later eligible opportunities.
5. **Consistent:** performance remains strong across contexts and time.
6. **Needs refresh:** verified misses recur after previous success.

“Mastered” should be rare and concept-specific, not a universal gamification badge.

### Why this is technically defensible

The system accumulates a proprietary dataset competitors may not have:

```text
player state before intervention
  -> selected teaching action
  -> immediate response
  -> delayed response
  -> later real-game opportunity
  -> independent behavior
```

That dataset can eventually improve both learner-state estimation and teaching-policy selection. It is much more valuable than another collection of analysed PGNs.

## Human chess modeling

### Stockfish and Maia have different jobs

- **Stockfish:** truth, soundness, alternatives, tactical verification.
- **Maia-style model:** human likelihood, tempting mistakes, rating/time-control difficulty, opponent realism.

A human-likelihood model must never overrule Stockfish about chess truth.

### Recommended path

Use Maia-2 experimentally as a candidate ranker because its official implementation is MIT-licensed and it supports skill-aware human move prediction. Maia-3 is newer and more capable, but its official repository is AGPL-3.0; commercial integration needs an explicit legal and deployment review before adoption. Do not assume a model conversion changes the original license.

Uses worth testing:

- rank likely mistakes for hard-negative mining;
- measure how “findable” an engine move is for the player’s cohort;
- create human-like Coach Mode opponents;
- choose plausible distractors;
- distinguish an obvious miss from a computer-only miss;
- prioritize positions where the best move conflicts with the likely human move.

Do not use it to declare why a player erred or whether a tactical claim is sound.

### Would ChessGuru train its own model?

Eventually, perhaps—but not a new general chess engine.

The first valuable proprietary models would be smaller supervised systems:

1. **Error-cause ranker:** predicts validated cognitive hypotheses from decision-graph features and player history.
2. **Difficulty model:** predicts success probability for this player on this position with and without hints.
3. **Intervention outcome model:** predicts delayed retention/transfer from a proposed teaching action.
4. **Explanation ranker:** selects the clearest verified explanation variant for a player level.
5. **Relapse model:** identifies when a fading focus needs reinforcement.

Each model needs a simple rules baseline, calibration tests, slice evaluation, and an ablation proving that personalization improves outcomes.

## Concept-first explainability

Neural engine embeddings may contain chess concepts, but a probe detecting a concept inside a model is not automatically a faithful explanation. Research on concept bottleneck models is relevant because it routes predictions through human-understandable concepts and permits concept correction; other work warns that learned bottlenecks can leak information or fail to represent the intended concept.

ChessGuru should use **verified concept bottlenecks**:

```text
position/move
  -> deterministic or independently verified concept facts
  -> cognitive hypotheses with uncertainty
  -> teaching decision
  -> language
```

When learned concept models are introduced, require:

- independent board-verifier agreement where possible;
- false-positive and hard-negative suites;
- human correction flow;
- explanation faithfulness tests;
- abstention when confidence is low.

## The teaching compiler

The compiler turns one verified decision graph plus player state into different learning experiences.

### Output schema

```json
{
  "decision_id": "...",
  "claim_level": "observed",
  "primary_concept": "piece_safety.remove_defender",
  "board_facts": [],
  "cognitive_hypotheses": [],
  "active_focus_links": [],
  "intervention": {
    "type": "predict_opponent_reply",
    "prompt": "...",
    "board_overlays": [],
    "acceptable_moves": [],
    "hint_ladder": [],
    "completion_rule": "..."
  },
  "next_evidence": {
    "stage": "delayed_transfer",
    "eligibility_rule_version": "..."
  },
  "provenance": {
    "engine": "...",
    "detectors": [],
    "policy_version": "...",
    "language_version": "..."
  }
}
```

### Language stack

1. Compute verified facts.
2. Select teaching intent.
3. Fill a deterministic semantic frame.
4. Optionally let an LLM rewrite within locked facts and player-language constraints.
5. Parse/validate the output.
6. Run board-claim and voice checks.
7. Fall back to deterministic copy on any failure.

The LLM layer must be provider-neutral and replaceable. It is presentation infrastructure, not the coach’s source of truth or memory.

## Curriculum graph

One canonical graph should unify:

- tactics and tactical defense;
- calculation habits;
- positional concepts;
- openings, structures, plans, and traps;
- endgame recognition and technique;
- time management;
- thinking-process habits.

Each skill node needs:

```text
stable ID
human name and plain-language definition
prerequisites
board manifestations
detectors and authorization levels
teaching objectives
worked examples
contrasts and hard negatives
practice sources/generators
difficulty features
transfer detector
claim rules
copy variants
version and ownership
```

A trap is not a separate educational universe. It is a structured example involving opening recognition, threat detection, calculation, and tactical concepts. The graph lets the coach teach whichever prerequisite the player actually lacked.

## Data architecture

### Do not microservice the product yet

At the current product scale, a disciplined modular monolith is safer than many network services. The present problem is policy fragmentation, not insufficient service decomposition.

Organize the backend into explicit domains:

```text
ingestion/
analysis/
chess_knowledge/
evidence/
player_model/
pedagogy/
experience/
billing/
platform/
```

Each domain owns schemas and exposes a narrow interface. Existing flat service files migrate behind these boundaries incrementally; do not perform a big-bang rewrite.

### Storage now

MongoDB can continue serving raw games, analysis documents, lesson records, and player-state projections if the team adds:

- schema validation;
- stable IDs;
- explicit version fields;
- normalized time types;
- unique and compound indexes;
- idempotency keys;
- append-only evidence events;
- derived projections that can be rebuilt;
- migration tooling and compatibility tests.

Do not change databases because a large company might. Change when a domain’s guarantees require it.

### Storage later

Introduce specialized systems only when measured needs appear:

- object storage for large immutable engine artifacts and corpora;
- Redis or equivalent for short-lived cache, locks, and queue coordination;
- a relational store for billing/entitlements if transactional constraints become difficult in Mongo;
- an analytical warehouse for event/funnel/model datasets;
- a model registry and feature pipeline when trained models enter production.

A vector database is not required for V1. Board-aware fingerprints, graph features, FEN normalization, and transposition-aware matching are more faithful starting tools for chess-position retrieval. Add embeddings only if they outperform those baselines on a defined retrieval benchmark.

### Event-sourced evidence

Learning evidence should be append-only:

```text
GameImported
MoveAnalyzed
OpportunityDetected
BehaviorObserved
FocusActivated
InterventionDelivered
AttemptRecorded
DelayedRecallObserved
TransferOpportunityObserved
FocusStateChanged
ClaimRendered
ClaimChallenged
```

Current state is a projection of these events. This makes improvement claims reproducible and lets new learning models replay history safely.

## Analysis compute architecture

### Progressive analysis

Use three budgets:

1. **Immediate:** legal facts, cached positions, shallow engine result, obvious high-confidence moments.
2. **Background:** deeper MultiPV on critical decisions, all acceptable alternatives, concept verification.
3. **Research/offline:** deep detector audits, hard-negative mining, cohort baselines, model training.

The player can receive a useful result quickly without treating the fast pass as the final truth.

### Position cache

Cache engine results using normalized position, rule state, engine version, network/version if relevant, depth/nodes, and MultiPV configuration. Never cache only by piece placement; side to move, castling, en passant, and repetition context can change truth.

### Job semantics

Every job should have:

- immutable input reference;
- idempotency key;
- state and attempt count;
- versioned engine/configuration;
- lease/heartbeat;
- bounded retry policy;
- failure category;
- partial-output marker;
- completion event;
- replay support.

The frontend sees analysis state explicitly rather than polling ambiguous documents.

## API architecture

Create one typed coaching contract instead of exposing internal services directly.

Recommended surfaces:

- `POST /games/import`
- `GET /analysis-jobs/{id}` or server-sent progress
- `GET /today`
- `GET /reviews/{game_id}`
- `POST /interventions/{id}/attempts`
- `POST /coach-games`
- `POST /coach-games/{id}/moves`
- `GET /player/focuses`
- `GET /player/progress`
- `POST /claims/{id}/challenge`

Use Pydantic schemas, generated frontend types, explicit API versions, pagination, idempotency headers, correlation IDs, and compatibility tests. Server-sent events are enough for most analysis progress; WebSockets are appropriate for Coach Mode if the interaction truly needs bidirectional low latency.

## Frontend technology architecture

### Current risk

The frontend currently combines React 19 with a CRA/CRACO foundation and includes multiple chessboard libraries. The immediate response should not be a fashionable rewrite. First reduce product state and create stable adapters.

### Target structure

```text
app-shell/
journeys/
  onboarding/
  today/
  review/
  play/
  progress/
domain/
  coaching-contract/
  board/
  player-state/
design-system/
telemetry/
```

### Important technical decisions

- Use one board adapter so the product can change the underlying library without rewriting journeys.
- Represent onboarding, analysis, teaching, and Coach Mode as explicit state machines, not collections of booleans across hooks.
- Generate API types from backend schemas.
- Cache queries by contract/version and invalidate from events.
- Persist resumable journey state.
- Make board overlays declarative from the Decision Graph.
- Build visual regression tests for orientation, arrows, highlights, and responsive layouts.
- Split public marketing delivery from the authenticated application only if SEO/performance measurement justifies it.
- Migrate away from unsupported build infrastructure incrementally after contract and journey consolidation.

## Reliability architecture

Define user-centered SLIs before infrastructure metrics:

- imported games becoming available;
- analysis completion and freshness;
- time to first credible insight;
- Coach Mode move response;
- coaching payload correctness/version compatibility;
- payment-to-entitlement propagation;
- evidence events not lost or duplicated.

Set SLOs from measured baselines and player tolerance, then use error budgets to decide whether the next sprint emphasizes reliability or feature work. Average latency is insufficient; inspect tail percentiles and dependency-specific failure.

For every player-visible claim, retain a reproducible trace:

```text
claim -> language frame -> policy decision -> player state
      -> concept evidence -> detector output -> engine/board facts
```

## Quality and evaluation platform

This should be a product inside the company.

### Evaluation datasets

- verified positives;
- verified negatives;
- hard negatives that resemble the concept;
- transpositions;
- both player colors and board orientations;
- rating and time-control slices;
- opening/endgame slices;
- adversarial legal edge cases;
- duplicate clusters isolated between train and test;
- real user challenges and corrections.

### Separate scorecards

1. **Board correctness:** legality, side, squares, line, material, evaluation.
2. **Detector quality:** precision, recall, calibration, abstention.
3. **Attribution quality:** board event versus cognitive-hypothesis agreement.
4. **Teaching quality:** clarity, appropriate level, misconception repair.
5. **Policy quality:** whether the intervention was the right one and not excessive.
6. **Learning quality:** immediate, delayed, transfer, and later-game outcomes.
7. **Experience quality:** completion, effort, trust, retention.

### Release path

```text
offline research
 -> frozen benchmark
 -> shadow production
 -> internal/chess-expert review
 -> limited player captions
 -> teaching authorization
 -> focus authorization
 -> transfer/claim authorization
```

Every model, detector, curriculum node, policy, and caption version must be replayable against historical events before promotion.

## Data needed for real innovation

Imported games alone are insufficient. ChessGuru needs ethically collected learning trajectories.

### Existing/recoverable data

- FEN and move history;
- engine facts and alternatives;
- player/opponent rating;
- time control and clocks where available;
- repeated concepts;
- review and puzzle interactions;
- active focuses;
- Coach Mode history.

### New high-value events

- whether the player inspected the explanation or line;
- first candidate selected before reveal;
- threat/cause choice from two or three options;
- hint level used;
- time to decision;
- confidence choice when useful;
- delayed recall outcome;
- transfer distance;
- eligible later-game opportunity and handling;
- player challenge: wrong, irrelevant, confusing, already knew;
- intervention shown versus eligible but withheld;
- coach/human correction with reason.

Do not collect keystrokes or invasive behavioral data merely because it is possible. Every event needs a learning or reliability purpose, retention period, and access rule.

### Public data

Lichess publishes games, puzzles, evaluations, and openings under licenses that permit broad reuse; the primary database page currently describes the main exports as CC0. Use these for chess coverage, negatives, position difficulty, and cohort behavior. They cannot provide ChessGuru’s most valuable label: which intervention changed an individual’s later behavior. That data can only come from the product loop.

## Experimentation system

### What to experiment on

- explanation frame;
- question versus demonstration;
- same-game retry versus delayed revisit;
- spacing interval;
- difficulty progression;
- Coach Mode interruption timing;
- one leading focus versus different session ordering;
- tone and detail;
- free-plan boundary and paid packaging.

### What not to optimize alone

- clicks;
- session length;
- exercise completion;
- messages read;
- streaks.

These can rise while learning falls. Primary experiment outcomes should include delayed and transfer results, with trust, frustration, and retention as guardrails.

### Causal discipline

- Randomize at the player or focus episode where contamination demands it.
- Predefine outcome windows and eligible opportunities.
- Separate content difficulty from policy effects.
- Log propensity/eligibility for future off-policy evaluation.
- Never train and evaluate on near-duplicate positions across splits.
- Do not claim causality from ordinary before/after rating movement.

## Billing and revenue technology

A subscription business needs a financial source of truth independent of UI state.

Build:

- product/price catalogue;
- customer and subscription records;
- webhook inbox with signatures and idempotency;
- entitlement projection;
- renewal, cancellation, grace, failure, recovery, refund, and expiry states;
- usage metering and fair-use controls;
- invoice/tax data;
- customer-support timeline;
- finance reconciliation;
- experiment assignment that never corrupts entitlements.

The coaching system asks the entitlement service what is available; it never infers paid status from a frontend flag or successful order alone.

Track contribution margin by action:

```text
revenue
- payment/tax effects
- engine compute
- model inference
- LLM narration
- storage/egress
- support/refunds
= retained contribution
```

## Security, privacy, and responsible AI

- Player owns connected-account data and derived profile.
- Export/delete includes raw, derived, event, and model-feature data.
- Product and research datasets are separated with consent and de-identification.
- Every model has a model card: purpose, data, slices, limitations, license, and rollback.
- Generated language is disclosed appropriately.
- The coach can abstain and the player can challenge a claim.
- Sensitive logs omit tokens, credentials, and unnecessary personal data.
- Role-based access, secrets rotation, dependency scanning, rate limiting, and audit logs are standard.
- Children require a distinct privacy, consent, language, and safety design—not merely a lower rating setting.

## What could be genuinely novel

The following combination may be protectable as know-how and possibly through intellectual-property filings after counsel review:

1. A verified chess decision graph that compiles into multiple teaching modalities.
2. A context- and opportunity-aware player learning twin built from real games plus instruction.
3. Counterfactual error attribution combining engine truth, human move likelihood, clock behavior, and personal recurrence.
4. A constrained coach policy optimized for delayed independent transfer rather than immediate puzzle success.
5. Opportunity-conditioned proof of behavioral change in future games.
6. A longitudinal intervention dataset connecting real-game errors to teaching and later transfer.

The last two are the strongest moat. Algorithms can be copied; a trustworthy, consented history of what teaching works for which chess behavior is much harder to reproduce.

Patentability is a legal question and should not drive product architecture. Keep critical training data, labeling policy, benchmark design, and policy features as controlled know-how unless there is a clear reason to publish or patent them.

## What not to build

- A giant end-to-end model that takes a PGN and emits an unverified coaching plan.
- A replacement for Stockfish.
- A chatbot that can freely invent board analysis.
- Microservices for every detector.
- A vector database before a retrieval benchmark exists.
- A unique model before the product has unique labels.
- “Emotion detection” inferred from a loss or fast moves.
- A universal mastery score with no opportunity denominator.
- Reinforcement learning optimizing clicks before delayed outcomes exist.
- More parallel memory and recommendation systems.

## Build sequence

### Stage A: consolidate what exists

- Inventory all brains, memories, concept IDs, policies, and output contracts.
- Select canonical implementations and put legacy paths behind adapters.
- Define Decision Graph and evidence-event schemas.
- Version detector, engine, policy, and language provenance.
- Route one existing concept through the full architecture.

### Stage B: build the learning substrate

- Generalize the mastery reducer into the first Player Learning Twin.
- Define opportunity and transfer contracts.
- Make active focus an orchestrator input everywhere.
- Build a single intervention schema and frontend renderer.
- Add player challenge/correction events.

### Stage C: add human modeling

- Benchmark Maia-2 candidate likelihood against local cohort games.
- Test whether it improves hard-negative mining and difficulty prediction.
- Keep it shadow-only until added value is proven.
- Complete legal review before considering Maia-3.

### Stage D: learn which teaching works

- Collect intervention and delayed-outcome trajectories.
- Establish rules and simple statistical baselines.
- Train calibrated difficulty and outcome models.
- Run controlled policy experiments.
- Introduce a constrained contextual policy only if it beats transparent rules on transfer and trust.

### Stage E: scale the platform

- Extract services only where independent scaling, ownership, or reliability requires it.
- Add warehouse/model registry when training and experimentation need them.
- Harden billing, data lifecycle, abuse protection, incident response, and capacity planning.

## Confidence levels

### High confidence

- Stockfish must remain the chess-truth authority.
- LLMs must be downstream of verified facts.
- The current backend needs consolidation into one orchestrator and canonical domain contracts.
- Learning must be measured per eligible opportunity, not raw game count.
- A modular monolith is preferable to premature microservices now.
- Event provenance and replayability are prerequisites for honest progress claims.

### Medium confidence; validate with product data

- A Bayesian/knowledge-tracing-style Player Learning Twin will outperform count/streak logic.
- Maia-2 likelihood will improve position prioritization and distractors.
- One Decision Graph can serve review, training, and Coach Mode without becoming too general.
- A single leading session focus with secondary active focuses will feel more human than equal-weight multitasking.

### Experimental

- Personalized neural human-move models at ChessGuru’s available per-player data volume.
- Learned cognitive-cause attribution from passive game data alone.
- Contextual-bandit teaching policy.
- Neural concept embeddings as the primary retrieval or explanation layer.
- Strong causal claims about rating improvement.

## Final recommendation

ChessGuru should present itself internally as a **learning-systems company using chess as the first domain**, while remaining externally a simple chess coach.

The company’s technical ambition should not be “we have more detectors.” It should be:

> We built a system that converts a player’s real decisions into verified teaching, maintains a probabilistic model of their understanding, chooses restrained interventions, and measures transfer back into real play.

That is sufficiently ambitious for a serious technology company, but it is also buildable in stages from the repository that exists today.

## Research sources

- Maia-2 paper and official implementation: [NeurIPS paper](https://proceedings.neurips.cc/paper_files/paper/2024/hash/250190819ff1dda47cd23cecc0c5a69b-Abstract-Conference.html), [official repository](https://github.com/CSSLab/maia2)
- Maia-3 / Chessformer: [official repository](https://github.com/CSSLab/maia3), [ICLR 2026 paper](https://openreview.net/forum?id=2ltBRzEHyd)
- Individualized Bayesian Knowledge Tracing: [Yudelson, Koedinger, and Gordon](https://www.cs.cmu.edu/~ggordon/yudelson-koedinger-gordon-individualized-bayesian-knowledge-tracing.pdf)
- Adaptive curriculum with contextual bandits: [Belfer, Kochmar, and Serban](https://arxiv.org/abs/2207.14003)
- Concept Bottleneck Models: [Google Research / ICML 2020](https://research.google/pubs/concept-bottleneck-models/)
- Interactive Concept Bottleneck Models: [AAAI 2023](https://ojs.aaai.org/index.php/AAAI/article/view/25736)
- Chess concept representation in AlphaZero: [PNAS paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC9704706/)
- Concept-guided chess commentary: [NAACL 2025 paper](https://aclanthology.org/anthology-files/pdf/naacl/2025.naacl-long.481.pdf)
- Lichess open database and license: [database.lichess.org](https://database.lichess.org/)
- Google SRE service-level objectives: [SLO chapter](https://sre.google/sre-book/service-level-objectives/)
- Microsoft responsible AI: [principles and standard](https://support.microsoft.com/en-US/Privacy/what-is-responsible-ai)
