# Personal Improvement Cycle — Technical Spec

**Status:** APPROVED FOR IMPLEMENTATION v1.3 — PIC is active; the conditional D_live validation relabel is incorporated.  
**Scope class:** Largest / multi-day.  
**Rollout flag:** `PERSONAL_IMPROVEMENT_CYCLE_ENABLED=false` by default.

## 1. Feature summary

The Personal Improvement Cycle connects existing ChessGuru capabilities into one canonical journey:

`diagnosis → one active focus → one instruction → assisted practice → unassisted checkpoint → committed external Focus Game → honest outcome → continue or next focus`

This is an extension and consolidation of existing surfaces. It is not a new dashboard, program collection, caption engine or social product.

The valid corpus selects `piece_safety` as the first category. Current-schema `simple_hang` has 96.9% precision but only 61.61% recall inside its intended taxonomy, so it supports positive diagnosis only. `piece_safety.d_live.v1` is the implementation-checked proof fact: 22,583 decisions across 149,886 v16 moves (15.07%) and a 9.47% miss rate. Production SEE and an exhaustive capture-tree implementation agreed on 399/400 stratified positions; the shared stored `cp_loss ≥150` gate is not independently verified. Other focus types keep current coaching without V1 resolution language.

PIC is the active product V1. Knight-fork content is queued, while `learning_experience_system_architecture.md` remains canonical for subject-agnostic lesson lifecycle, learner projection, evidence tiers and cohort isolation.

## 2. Problem and product contract

ChessGuru can already import games, explain mistakes, prescribe puzzles, play coached games and show progress. Those features do not yet share one reliable lifecycle. Instructions can change between surfaces, assisted play can look like proof, zero detected failures can be misread as success, and multiple progress engines can disagree.

The implementation contract is:

- one canonical active focus;
- one immutable instruction for the lifetime of that focus;
- explicit evidence provenance;
- a corpus-validated comparable-decision denominator;
- exactly-once analysis completion;
- no improvement claim beyond detector capability;
- one next action on every eligible surface;
- default-off compatibility during rollout.

## 3. User states and outcomes

| State | Meaning | Allowed next action |
|---|---|---|
| `not_eligible` | No verified `simple_hang` focus or insufficient starting evidence | Continue current ChessGuru experience |
| `diagnosed` | Focus and starting examples exist; instruction is locked | Start first prescribed practice |
| `practice_assisted` | Player practises and may receive hints/reminders | Continue practice or choose a checkpoint |
| `checkpoint_insufficient_evidence` | Unassisted session lacks enough qualifying comparable decisions | Retry; no outcome movement |
| `checkpoint_unresolved` | Validated D_live miss rate does not meet the locked proof rule | Keep same instruction; prescribe bounded practice |
| `checkpoint_promising` | Recent verified-failure rate is lower but not yet sufficient for resolution | Keep focus; commit a real Focus Game |
| `external_insufficient_evidence` | Committed imported game lacks enough qualifying comparable decisions | Commit another game; no outcome movement |
| `external_unresolved` | Committed game adds one or more validated D_live misses | Keep same instruction and practice |
| `resolved` | Required independent evidence meets the data-locked bar | Close focus and select next canonical focus |

`just_play` is not a lifecycle state. Its observations may improve future diagnosis, but it cannot directly resolve the current focus.

## 4. Canonical data and single-source decisions

### Existing canonical sources to extend

| Concept | Canonical source | Decision |
|---|---|---|
| Current focus | Mongo `user_active_focus` | Owns coaching priority and surviving instruction; does not publish mastery |
| Focus continuation/closure | Existing focus resolver/outcome path | Consumes eligible evidence and decides priority; does not invent learner-facing states |
| Instruction | Existing focus bridge/canonical instruction resolver | Store resolved `instruction_id` and literal text on focus activation; reuse everywhere |
| Lesson lifecycle | `backend/services/teaching_engine.py` | Extend through a store adapter; no PIC lesson dispatcher |
| Learner-facing mastery | `backend/services/concept_mastery_service.py` | Extend to `Learning / Remembered / Proven in games`, current/highest checkpoints, demotion and `Refresh needed` |
| Reviewed learning content | Existing LES `learning_content_manifest` contract | Reuse Gold/Provisional/Verified tier semantics; do not duplicate source positions |
| Learning evidence | LES resumable session/event contract plus named game/session adapters | Practice events stay in their owning lesson session; game application stays on game/session evidence |
| Cohort assignment | LES backend-enforced admin/calibration/confirmatory contract | Reuse; calibration users never enter confirmatory analysis |
| Move observations | Existing analyzed-game observation pipeline | Sole observation emitter; extend the shared completion hook to Play With Coach |
| Piece-safety geometry | `coach_blunder_guard.material_hung_after/see_gain` | Reuse raw SEE; do not add another hang detector |
| Puzzle supply/attempts | Existing pattern-puzzle and `puzzle_attempts` paths | Reuse |
| Rating bands | `backend/deterministic_coach_service.py` | Reuse; no new table |
| Gap taxonomy | Existing cognitive-gap definitions | Reuse; no new taxonomy |
| Price/entitlement | Existing billing config + Razorpay subscription service | Make backend config authoritative; frontend renders returned price |
| Coaching text | Existing central caption/voice pipeline | Reuse |

### Additive `user_active_focus` fields

| Field | Contract |
|---|---|
| `cycle_version`, `focus_kind` | Version 1; `piece_safety/simple_hang` |
| `instruction_id`, `instruction_text` | Immutable for the active focus |
| `proof_eligibility` | `diagnosis_only / verified` |
| `diagnosis_detector_id`, `proof_detector_id` | `move_observation.simple_hang.v16`; `piece_safety.d_live.v1` |
| `pending_focus_game` | committed timestamp, `waiting/claimed/cancelled/corrected`, optional game id |
| `evidence_summary` | baseline/recent D_live decisions and misses, last verdict, measured timestamp |

Raw evidence stays on its owning game/session. The focus stores bounded aggregates and references, not an unbounded duplicate event log.

### Additive evidence envelope

Eligible analyzed games and completed coach sessions carry: version, focus and
instruction ids; environment; evidence mode; assisted and pre-committed flags;
positive-simple-hang diagnoses; D_live decisions/misses; verdict; measured
timestamp; and an analysis-completion idempotency key.

All new timestamps use BSON UTC datetimes in Mongo comparisons. API serializers convert them at the boundary. ISO strings are not compared directly with BSON datetimes.

## 5. Rules and gates

An evidence item can affect focus resolution only when every rule below passes:

1. The rollout flag is enabled for the user.
2. The active focus is `piece_safety/simple_hang` and `proof_eligibility=verified`; `diagnosis_only` cannot resolve.
3. The evidence `focus_id` and `instruction_id` match the current focus.
4. The evidence includes D_live decisions and outcomes from the independently validated canonical implementation.
5. The mode is `checkpoint_unassisted` or `external_focus_game`.
6. `assisted=false`.
7. External evidence was committed before the game was imported and has not been corrected/rejected.
8. The idempotency key has not already been applied.
9. The data-locked sample and comparison requirements are satisfied before `resolved`.

Assisted practice records learning activity but never independent proof. Ordinary play records discovery observations but never directly resolves the focus. Insufficient evidence changes neither proof status nor lifecycle. A zero-`simple_hang` game is a detector result, not proof. Only validated D_live evidence may enter an absence-based outcome.

The instruction is resolved once when the focus becomes active. `user_active_focus` owns priority and instruction; `concept_mastery_service` owns the user-facing `Learning / Remembered / Proven in games` projection and any `Refresh needed` demotion. Surfaces are readers; they may not independently select, rewrite or translate either authority.

## 6. Interfaces and expected files

### Backend interfaces

- Extend the existing active-focus response to return `focus_kind`, immutable instruction, proof eligibility, evidence summary, next action and pending Focus Game state.
- Extend `services.teaching_engine` through its generic interaction/store-adapter contract for prescribed practice and silent checkpoints. Existing Play With Coach lesson callers retain their compatibility path.
- Extend `concept_mastery_service` to reduce eligible PIC evidence into current/highest checkpoint, `Learning / Remembered / Proven in games`, and `Refresh needed`. No focus route writes those labels.
- Apply LES content tiers at the backend: Provisional content is admin-only; Gold content may enter calibration/confirmation; Verified machine evidence may screen or support factual diagnosis but cannot itself advance mastery.
- Persist cohort role before the first interaction and reject calibration/confirmatory overlap server-side.
- Extend the canonical analyzed-move observation emitter with `piece_safety.d_live.v1`: eligible moved-piece type, legal destination capture, canonical destination SEE, Stockfish corroboration and the locked handled/missed outcome. Do not import the exhaustive audit checker into runtime.
- Require SEE-backed `schema_version >=16` on every PIC diagnosis baseline and exact fact version `piece_safety.d_live.v1` on D_live evidence queries/verdicts. Never read the 1,145 pre-SEE events into a user outcome.
- Add an idempotent `games.user_rating` backfill from authoritative stored game/profile sources, coverage reporting and an explicit `unknown` result; never guess a rating band.
- Extend `POST /api/coach/play/start` with an optional mode and reuse completed-session postgame analysis for the evidence envelope; flag-off callers retain current behavior.
- Add Focus Game commit/cancel/correct actions under the existing focus routes and route imported/PWC completion through one idempotent analysis-complete service.
- Extend dashboard/home intelligence with one cycle presentation model and billing config with the canonical ₹199 returned to Pricing.

### Frontend contract

Every cycle-aware payload exposes eligibility/state; focus label; immutable
instruction id/text; the canonical learner projection (state, refresh flag,
current/highest checkpoint); evidence counts/provenance; and one typed next
action with href/label.

The frontend displays this model; it does not calculate improvement or choose a new focus.

### Expected existing files to extend

Backend candidates are the current config, focus bridge/resolver/picker,
`teaching_engine`, `concept_mastery_service`, `coach_blunder_guard`,
`move_observation_deriver`, `mission_scoreboard`, coach/play, games and
billing routes, plus their existing tests.

Frontend candidates are Activation/Onboarding, the routed
`LabV2 → GameDecryptionV5` review, Home, Prescribed Training, Coach Play
setup/sidebar/reflection, Pricing and the current Progress surface.

This is a candidate list, not permission to touch every file. Before the first code patch, the pre-code audit must identify the narrowest shared chokepoints and protect unrelated dirty-worktree changes.

## 7. Measurement, analytics and threshold lock

### Events

Instrument diagnosis viewed; practice start/complete; play-mode selection;
Focus Game commit/claim/correction; evidence measured; verdict viewed; focus
continued/resolved; paywall viewed; and subscription started under the
`cycle_*` namespace.

Every event carries `cycle_version`, `focus_kind`, `instruction_id`, rollout cohort and evidence mode where applicable. It must not contain raw PGN or private coaching text.

**Evidence boundary.** The external-game chess corpus is valid for mistake prevalence, detector coverage, legality, provenance and board correctness because those games were played on Chess.com/Lichess outside the changing product. The last reported snapshot is 13,425 analyzed games, 17,710 `piece_safety` observations and 183 machine-eligible fork candidates; these are source facts to re-query, not product-response metrics.

Existing MAU, WAU, puzzle-attempt, training-user and conversion counts are contaminated by a changing pre-launch product. Current product usage and response are `unknown`. Those numbers are excluded from funnel, retention, conversion and Focus Game baselines.

### Numeric decision procedure

No sample minimum, improvement percentage, focus-ranking weight, funnel target or retention declaration is locked in this document.

Two separate locks are required before those constants are committed.

**A. Corpus feasibility and correctness**

The completed measurement is `docs/simple_hang_corpus_evidence.md`.

1. Current `simple_hang` positive precision is 96.9%; taxonomy-eligible recall is 61.61%. **Lock:** stored `simple_hang` flags are diagnosis-only and never support absence-based improvement.
2. D_live exposure is confirmed: 22,583 decisions across 149,886 v16 moves (**15.07%**), close to the earlier 16.3% sample.
3. D_live outcome is locked: a knight/bishop/rook/queen is legally capturable on its destination; miss requires canonical destination SEE ≥150 and Stockfish `cp_loss ≥150`. The corpus split is 90.53% handled / 9.47% missed.
4. A pre-registered 400-position exhaustive-capture-tree check produced 399/400 overall SEE-outcome agreement: 99/100 in the candidate-miss stratum and 100/100 elsewhere. This is implementation agreement, not precision/recall; both sides reused the same stored `cp_loss` gate.
5. The 28.6% sample was not reproduced. Static SEE alone (43.83%), `cp_loss` alone (17.39%) and raw attacked-square SEE+cp (8.55%) are rejected for causal/legal-contract reasons.
6. D_live is emitted only by the canonical analyzed-move observation path. The independent checker remains audit-only, and resolution minimums/comparison bars remain a separate post-launch data lock.
7. Before confirmatory rollout, human/engine review grades approximately 50 stratified D_live misses for coach-meaning validity. This semantic audit is pre-launch, not pre-code.

**B. Post-launch product response**

1. Pre-register the minimum sample and pause rule separately for activation, journey completion, Focus Game use, paid conversion, D7 and D30.
2. Collect those measures only after the stable treatment launches. Pre-launch accounts are a correctness testbed, not a behavior baseline.
3. If a control is used, it is a concurrent, non-overlapping post-launch cohort. Historic users are not the control.
4. If the required sample is not reached, the result remains `unknown` and the rollout pauses; thin data never satisfies a gate.
5. Record every chosen value, rejected candidate and data citation in a dated decision artifact and tests.

The current external-game corpus can decide detector feasibility and correctness. It cannot decide whether users will complete, return, commit a Focus Game or pay.

## 8. Test plan

### Unit

- eligibility only for the verified V1 focus kind;
- immutable instruction resolution and exact text reuse;
- evidence-mode classification;
- positive-simple-hang diagnosis plus validated D_live decision/miss counting;
- SEE-backed schema evidence, exact D_live fact version and hard rejection of pre-SEE observations;
- rating backfill idempotency, authoritative-source precedence and preserved `unknown`;
- insufficient-evidence verdict and zero-hang non-proof guard;
- LES learner projection fixtures for current/highest checkpoint, demotion and `Refresh needed`;
- Gold/Provisional/Verified content-tier enforcement;
- admin/calibration/confirmatory cohort exclusion;
- assisted evidence excluded from resolution;
- Focus Game commitment/claim/cancel/correction;
- BSON datetime comparisons;
- idempotency under repeated completion events;
- canonical ₹199 config serialization;
- flag-off fallbacks.

### Integration

- imported game → analysis complete → observation → eligible external evidence → focus summary;
- Play With Coach checkpoint → postgame analysis → evidence once → verdict;
- assisted practice → activity recorded → resolution unchanged;
- ordinary play → discovery observation → resolution unchanged;
- active-focus response → Home/Training/PWC identical `instruction_id` and text;
- teaching-engine session evidence → concept-mastery projection → identical learner state on Home/Training/PWC;
- Provisional/admin evidence cannot advance mastery, and calibration users cannot enter confirmatory analysis;
- correction of a claimed external game reverses only that evidence and recomputes safely;
- billing config → Pricing → Razorpay order amount consistency.

### End to end

1. Eligible free user sees diagnosis, completes first practice and reaches the continuing-value paywall.
2. Pro user practises with help, takes a silent checkpoint, sees “No evidence” when appropriate, then receives an unresolved verdict with the same instruction.
3. Pro user commits a next external game, syncs it, verifies the claimed game and sees a verdict sourced from validated D_live facts.
4. Flag-off user sees the current production experience unchanged.

Required existing gates include the core backend flow suite, relevant focused pytest suites and a production frontend build. Test commands will be confirmed against the actual repository before implementation.

## 9. Rollout, risk and rollback

### Key risks

- An invalid comparison denominator turns zero detected hangs into false confidence.
- A PIC-specific lesson state machine or mastery label forks the canonical LES authorities.
- A Verified/Provisional position is accidentally treated as Gold or advances mastery.
- Multiple analysis-complete paths double-count evidence.
- Instruction text drifts across surfaces.
- Old and new progress claims conflict.
- A user accidentally commits or imports the wrong external game.
- A backend/frontend price mismatch charges a different amount from the displayed offer.
- The cycle adds more UI instead of removing competing choices.

### Rollout

1. **Developer-only:** flag on for local/dev users; run fixtures and manual board verification.
2. **Internal correctness dry run:** Mohit and Parth exercise treatment and flag-off paths; this verifies plumbing and board claims only and contributes no behavioral baseline.
3. **Post-launch calibration cohort:** use a named, newly exposed cohort; lock product-response denominators and exclude this cohort from confirmatory success claims.
4. **10% confirmatory cohort:** monitor errors, false claims, insufficient-evidence frequency, journey completion and support feedback. If its pre-registered minimum sample is not reached in the declared window, pause with status `unknown`.
5. **100% eligible users:** only after the predeclared correctness, sample and product-response gates pass.
6. **Legacy deletion:** after two clean weeks at 100%, remove superseded presentation paths and the rollout flag in a dedicated cleanup change.

### Rollback

Set `PERSONAL_IMPROVEMENT_CYCLE_ENABLED=false`. All schema changes are additive, so control readers ignore them. Do not delete evidence during rollback. Fix forward, recompute bounded summaries from owning games/sessions if needed, and re-enable only after verification.

## 10. Implementation sequence and decisions

### Expected commit sequence

1. `data: lock d-live geometry and outcome against independent board review`
2. `docs: lock personal improvement cycle scope and inherited LES authorities`
3. `feat: add default-off cycle config and canonical raw evidence fields`
4. `feat: extend teaching engine and concept mastery for PIC evidence`
5. `fix: unify analysis completion and active-focus datetime handling`
6. `feat: add coach-play evidence modes and honest verdicts`
7. `feat: add external focus-game commitment lifecycle`
8. `feat: connect review home training and progress presentation`
9. `feat: package pro cycle at canonical ₹199 price`
10. `test: cover authorities tiers cohorts idempotency and flag-off path`
11. `chore: roll out cycle and later remove superseded presentation`

Commits are expected boundaries, not authorization to commit automatically.

### Decision record and remaining blockers

1. `piece_safety` is approved first. Current `simple_hang` flags are locked to diagnosis-only; `piece_safety.d_live.v1` is the approved proof fact.
2. The Free/Pro boundary remains a launch hypothesis: first diagnosis/practice Free; continued cycle Pro.
3. The next-imported Focus Game rule with correction is approved.
4. Corpus thresholds come from external-game data; product-response thresholds come only from post-launch data. Insufficient sample pauses.
5. ₹199/month is approved for launch testing through canonical billing config.
6. **Resolved:** PIC is the active product V1. LES knight-fork content is queued; its shared authorities, learner projection, evidence tiers and cohort isolation are inherited.
7. **Resolved for implementation:** D_live passed the pre-registered SEE implementation-agreement gate. Its shared `cp_loss` gate and semantic coach meaning are not mislabeled as externally validated; the latter is a pre-launch audit.

Codex signs the six-gate pre-code audit before the first runtime patch. The independent reviewer is not recorded as the product approver.
