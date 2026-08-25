# Personal Improvement Cycle — Scope Document

**Status:** APPROVED FOR IMPLEMENTATION v1.3 — PIC is the active product V1 and LES subject content is queued; the conditional validation relabel is incorporated.

## 0. Existing surfaces audit

### The user need

A new player should quickly experience one evidence-backed diagnosis, receive one memorable instruction, practise it in positions connected to their own games, carry it into later games, and see whether the behaviour improved. That cycle—not access to a collection of chess features—is what the paid subscription must continue.

### What already exists

| Existing surface or system | What it already gives the user | Decision |
|---|---|---|
| `Landing.jsx` | States the correct high-level promise: ChessGuru watches games, finds repeated loss patterns, trains the player on their own positions, and tracks when a pattern breaks. It also advertises many secondary features that compete with that promise. | **EXTEND:** keep the central promise; reduce feature-led positioning and make the improvement cycle the dominant story. |
| `ActivationHub.jsx` + `DiagnosticPuzzles.jsx` | Offers Chess DNA, a coached game, motivation capture, and account connection. The diagnostic can produce a headline weakness and route into pattern training. The current surface asks the user to choose among several ways to get value and describes a roughly 25-puzzle commitment before the first durable reward. | **TARGETED REPLACE:** keep the underlying diagnostic and coached-game capabilities, but replace the choice-heavy entry experience with one recommended fast path: connect real games first; use a short provisional diagnostic only when no game history is available. Do not create a parallel onboarding route. |
| `Onboarding.jsx` + the signed-off first-aha path | Connects Chess.com/Lichess, prioritizes a recent game, waits for analysis, and can send the user directly to that game review. | **EXTEND:** this becomes the canonical activation path and must land on a cross-game/personal insight, not merely a decoded loss. |
| `LabV2` / `GameDecryptionV5` + central caption pipeline | Shows engine-grounded turning points and strong move-specific explanations. This is the best existing trust-building surface. Cross-game learner context does not consistently appear in the main explanation the user studies. | **EXTEND:** add a compact repeated-pattern evidence block using the canonical active focus and observation history. No second caption or review engine. |
| `HomePageNew.jsx` + `home_coach_conversation` | Already implements the right emotional shape: one coach conversation, one action, continuity, and a relationship that deepens over time. It deliberately removed the competing dashboard-card stack. | **EXTEND:** make the coaching contract explicit—current focus, evidence, one instruction, and what must happen before the next verdict—without restoring dashboard clutter. |
| `user_active_focus` + `focus_resolver` + `focus_bridge` + pattern decay | Already forms the closest thing to a canonical current weakness: topic, evidence, baseline, instruction/mission, recent state and resolution. It feeds Home, Training and parts of Play With Coach. Outcome computation is currently unreliable because stored timestamps use incompatible types in the active check path. | **EXTEND AND REPAIR:** this remains the single source of truth. Fix its outcome lifecycle and route every eligible surface through its existing resolvers; do not add a new campaign/program collection unless the signed-off spec proves the canonical model cannot hold a required field. |
| `PrescribedTraining.jsx` + pattern-puzzle endpoints | Already resolves the current focus, serves the user's own positions first, falls back to community positions, records attempts, excludes solved puzzles and grants small decay recovery credit. | **EXTEND:** present a finite prescribed session tied to the one active instruction and end with the exact next transfer action. Do not build another drill page. |
| `CoachPlay.jsx` + session mission + `PostGameReflection.jsx` | Already carries active-focus context into some sessions, can show a postgame pattern verdict, and has the beginnings of one surviving instruction. It also contains many simultaneous coaching systems and the surviving-instruction path is gated rather than universal. | **EXTEND AND CONSOLIDATE:** make one mission dominant, keep ordinary moves quiet, and give a session-owned verdict. Reuse the central caption path and existing mission/focus bridge. |
| `UnifiedProgress` + improvement-proof engines + `FocusResolutionBanner` | Already has several ways to describe progress, reduction and focus resolution. Multiple improvement calculations exist across routes/services and can disagree. | **CONSOLIDATE:** expose one honest verdict sourced from the canonical focus outcome. Demote or retire rival calculations instead of adding another score. |
| `Pricing.jsx` + Razorpay billing | Provides Free/Pro checkout. The current offer is feature/limit-led: analysis counts, real-time coaching, LLM narratives, priority queue and auto-sync. Free already promises much of the central loop. | **REPLACE THE PACKAGING, EXTEND THE CHECKOUT:** Free discovers and demonstrates one problem; Pro continuously monitors, trains, evaluates and advances the player's focus. Reuse billing and entitlement infrastructure. |
| Existing community puzzle supply | User positions and community positions already feed training; provenance and rating/difficulty metadata exist in parts of the system. | **REUSE IN V1:** similar-player positions can support the personal treatment without building social networking. |
| `daily_fix_scope.md` | Defines a solo daily return ritual using existing missions, prescriptions, puzzles, attempts, recovery and streak infrastructure. It is not fully established as the canonical daily expression of an active focus. | **ABSORB INTO THIS CYCLE:** the daily action is the current focus's finite practice/transfer task, not a parallel habit product. |
| `coach_ladder_scope.md` and community-learning services | Define player-authored reasoning, contribution recognition, a Coach Ladder and social notifications. The scope itself parks the feature until a larger active-solver base exists. | **KEEP PARKED:** do not build a generic community, feed, forum, rating leaderboard or contribution economy in this V1. Revisit after the solo improvement cycle demonstrates retention. |
| `learning_experience_system_scope.md` v3.2 + canonical architecture | Knight-fork content is queued, but the subject-agnostic lesson lifecycle, learner projection, evidence tiers and cohort isolation remain applicable. | **INHERIT, DO NOT COPY:** PIC is the active product V1. It extends `services.teaching_engine` and `concept_mastery_service`, uses the existing content/evidence tiers and cohort rules, and leaves knight-fork content queued. |

### Overlap

The recommended journey already exists in fragments: activation, first-game review, active focus, one Home action, own-game training, an in-game mission, postgame verdict, progress proof, daily practice, billing and community puzzle supply. A new standalone “program,” “campaign,” dashboard or learner-model store would duplicate those responsibilities and deepen the current fragmentation.

### Genuine differentiation still missing

- One canonical journey owns the handoff from first insight through training, transfer and resolution.
- The first paid-quality insight proves recurrence with concrete game examples instead of only naming a broad category.
- The same literal instruction survives across Review, Home, Training and Play With Coach.
- The focus lifecycle produces a trustworthy next-game/weekly verdict and automatically advances only when the evidence supports it.
- The paywall sells continued problem ownership and measured progress, not additional analysis volume.
- Community positions reinforce the active focus, while social/community mechanics remain deferred until there is a retained learning base.

### Section 0 decision

**Overall path: EXTEND existing, with targeted REPLACE decisions for activation presentation and paid packaging. No parallel feature.**

The implementation, after full-scope sign-off, should consolidate this existing spine:

`Onboarding/first aha → Game Review → user_active_focus → Home one action → Prescribed Training → Play With Coach mission → canonical focus outcome → Progress/next focus → Pro renewal`

Proposed scope path: `docs/personal_improvement_cycle_scope.md`.

## 1. What we are building

ChessGuru will become one continuous **Personal Improvement Cycle**, not a collection of chess features.

For each player, the product will:

1. Find one repeated, board-verifiable behaviour in the player's games.
2. Prove it with concrete examples from those games.
3. Give one memorable instruction.
4. Let the player practise with help.
5. Test the behaviour without help.
6. Ask the player to deliberately carry the instruction into one real game.
7. Use honest evidence to continue the same focus, resolve it, or choose the next focus.

The product will classify **evidence**, not the player's personality. It will never claim that a person was serious, focused, careless or dishonest merely because of a result, time control or platform. “Practice with help,” “silent checkpoint,” “ordinary play” and “committed Focus Game” are different evidence modes and will be labelled as such.

The valid external-game corpus strongly supports **piece safety** as the first category. Current `simple_hang` flags have 96.9% precision but only 61.61% recall inside their intended taxonomy, so they are approved for positive diagnosis and rejected for absence-based improvement or resolution. `piece_safety.d_live.v1` is the implementation-checked proof fact: 22,583 decisions across 149,886 v16 moves (15.07%), with a 9.47% miss rate. Production SEE and an exhaustive capture-tree implementation agreed on 399/400 stratified positions; the shared `cp_loss ≥150` gate and coaching meaning were not independently verified by that check. Other categories continue to receive coaching without “fixed” claims.

## 2. What the user sees

### A. First visit

```text
Let ChessGuru watch how you actually play

Connect Chess.com or Lichess
We will find one mistake you repeat and show you where it happened.

[ Connect my games ]

No game history? Take a provisional chess check instead.
```

Connecting real games is the recommended path. The existing diagnostic remains the fallback; changing its algorithm or length is not part of V1.

### B. First diagnosis

```text
This is costing you games

You moved a piece to safety, but the new square was still attacked.
We found the same behaviour in these games:

  vs Arjun — move 18        [See position]
  vs KnightRider — move 24  [See position]

Your one instruction
Before moving, ask: “What changed after their move?”

[ Practise this ]
```

This block uses engine-grounded examples and the canonical active focus. It does not invent a second caption engine.

### C. Home

```text
What we're working on

Keeping your pieces safe
Before moving, ask: “What changed after their move?”

Next: practise 5 positions from your games
[ Continue ]
```

Home remains one coach conversation and one next action. It does not become a metrics dashboard.

### D. Prescribed practice

```text
Practice 2 of 5
This position came from your game against Arjun.

What changed after their last move?
[ board ]

Need help? [Show the attacked squares]
```

The session is finite. Positions from the player's games come first; existing community positions from similar players fill the remaining slots.

### E. Transfer modes

```text
How do you want to use this game?

[ Practice with help ]
The coach may remind you. This builds the habit.

[ Test me silently ]
No reminders. This checks whether the habit is available.

[ Just play ]
Normal coaching. Useful for discovery, but not proof that the focus is fixed.
```

### F. Real-game commitment

```text
Make your next imported game a Focus Game?

Play normally on Chess.com or Lichess, but deliberately carry this:
“Before moving, ask: What changed after their move?”

[ Yes, mark my next game ]  [ Not now ]
```

The player opts in before the game is imported. After import, ChessGuru shows which game was claimed and allows “That was not my Focus Game” so accidental or casual games do not become forced proof.

### G. Honest verdict

```text
Checkpoint result

We checked 18 comparable decisions.
1 produced a board-verified simple hang.

This is lower than your starting sample, but the evidence is not sufficient yet.
We will keep the same instruction for the next checkpoint.

[ Practise 3 more ]  [ Mark my next Focus Game ]
```

If no decision meets the eventual comparison contract, the verdict says:

```text
No evidence this time
This game did not give us enough comparable evidence to test your current focus.
```

Assisted practice, silent checkpoints, committed external games and ordinary games are shown separately. A casual coached game cannot silently resolve the focus. Until the comparison denominator is locked and verified, the product may say only “a verified simple hang was detected” or “no simple hang was detected”; zero detected hangs is not proof that the instruction was followed.

### H. Resolution and paid continuation

```text
This habit is becoming reliable

Across comparable decisions:
Starting sample: 4 verified hangs in 40 decisions
Recent Focus Games: 1 verified hang in 48 decisions

Next focus: noticing loose pieces before calculating.

[ Start next focus ]
```

```text
Free
Discover one repeated problem and complete the first practice.

Pro — ₹199/month
ChessGuru keeps watching, builds personal practice,
runs honest checkpoints, and moves you to the next focus.
```

All numbers in these mockups are illustrative. Opportunity minimums, improvement bars and ranking formulas must be locked from observed data before implementation.

## 3. In scope for V1

- Put the entire experience behind a default-off rollout flag. With the flag off, current routes and behaviour remain unchanged.
- Keep `user_active_focus` as the canonical focus record. Existing focus resolvers and bridges remain its readers; V1 will not create a rival learner-program store.
- Keep `user_active_focus` responsible for coaching priority and the surviving instruction, not mastery. `backend/services/concept_mastery_service.py` remains the only learner-facing status and next-step projection.
- Extend `backend/services/teaching_engine.py` for prescribed practice/checkpoint lifecycle. Do not build a PIC-specific lesson dispatcher.
- Reuse LES's `Learning → Remembered → Proven in games` projection, separate current/highest checkpoints, failed-evidence demotion and `Refresh needed` modifier.
- Reuse the existing content tiers: Gold for independently reviewed cohort teaching/assessment content; Provisional for admin walking skeletons only; Verified for offline screening. A player's engine-verified own-game position may support factual diagnosis or assisted practice, but cannot independently advance mastery.
- Reuse LES cohort isolation: admin correctness dry run, named calibration cohort, separate confirmatory cohort, then measured expansion.
- Repair the active-focus outcome path, including incompatible date representations and idempotent analysis completion.
- Carry one immutable `instruction_id` and literal `instruction_text` across Game Review, Home, Training, Play With Coach and the postgame verdict.
- Use current-schema `simple_hang` only for positive diagnosis. It may not supply “no hang,” improvement or resolution evidence.
- Hard-exclude all pre-SEE observations from diagnosis baselines, D_live evidence and verdicts; PIC diagnosis accepts SEE-backed `schema_version >= 16`, while D_live additionally requires fact version `piece_safety.d_live.v1`. The 1,145 historic pre-SEE `simple_hang` events never enter a user outcome.
- Emit `piece_safety.d_live.v1` through the existing canonical SEE/observation path: a knight, bishop, rook or queen moved where the opponent can legally capture it; miss only when destination SEE ≥150 and Stockfish `cp_loss ≥150`; otherwise handled. The exhaustive checker remains audit-only.
- Backfill `games.user_rating` where it can be recovered from an authoritative game/profile source, report coverage, and preserve `unknown` where it cannot. Rating-aware PIC behavior remains disabled for unknown rows rather than silently assigning a band.
- Add a compact repeated-pattern evidence block to the existing game review. Reuse the central caption pipeline.
- Extend the existing Home conversation with the active focus, its one instruction and its single next action. Do not restore dashboard clutter.
- Turn existing Prescribed Training into a finite session using the player's positions first and existing community positions second.
- Extend existing Play With Coach sessions with three explicit evidence modes: `practice_assisted`, `checkpoint_unassisted` and `just_play`.
- Promote completed Play With Coach games through the canonical analysis-complete path so they receive `analyzed_at`, canonical observations, decay updates and eligible evidence exactly once.
- Let a player pre-commit their next newly imported Chess.com/Lichess game as a Focus Game, cancel before import, and correct an incorrectly claimed game afterward.
- Store and display evidence provenance: environment, assistance, explicit commitment, number of comparable decisions and board-verified failures.
- Require the data-locked comparison contract before any checkpoint improvement or resolution claim. Before that lock, “hang detected” and “no hang detected” are correctness facts only; neither is silently converted into habit mastery.
- Make canonical focus outcome the authoritative source for Progress and resolution. Existing rival improvement summaries are demoted only after the rollout proves compatibility.
- Repackage the existing Free/Pro pricing surface around the cycle and use the existing Razorpay entitlement system. The proposed single Pro price is ₹199/month.
- Instrument each handoff: diagnosis viewed, practice started/completed, mode chosen, Focus Game committed/claimed/corrected, opportunity measured, verdict viewed, focus continued/resolved and paywall viewed/converted.
- Add unit, integration and end-to-end coverage, including flag-off compatibility and idempotent repeated analysis events.

## 4. Explicitly out of scope

- A generic community, activity feed, forum, chat, player following, rating leaderboard or Coach Ladder.
- Strong improvement/resolution claims for focus types other than `piece_safety → simple_hang`.
- Knight-fork LES content, authoring, detector changes and fork cohorts. Only the shared architecture is inherited by PIC.
- A second lesson dispatcher, mastery service, learner-state vocabulary, content review tier or cohort-assignment system.
- Automatically inferring seriousness, motivation or intent from a win, loss, time control, platform, move speed or rating.
- Letting an ordinary or assisted game silently resolve an active focus.
- Rewriting the diagnostic algorithm, its puzzle count or its scoring model.
- A new streak economy, XP, badges, leagues or other gamification system.
- A new caption engine, cognitive-gap taxonomy, rating-band table, instruction bank, billing-price constant or parallel active-focus collection.
- Claims that ChessGuru caused rating improvement. V1 measures the targeted board behaviour.
- Deleting legacy progress surfaces before controlled rollout and a clean observation window.
- Unrelated mobile, opening, performance or visual redesign work.

## 5. Definition of success

The feature is complete only when all of the following are true:

1. **Instruction continuity:** for every eligible cycle, Review, Home, Training, Play With Coach and the verdict show the same `instruction_id` and literal text. Any mismatch is release-blocking.
2. **Honest evidence:** assisted, unassisted, external-committed and ordinary-play evidence never collapse into one undifferentiated score.
3. **Comparison denominator:** a verdict uses the independently validated D_live decision/outcome fact. A game without qualifying D_live decisions reports “No evidence.” Zero stored `simple_hang` flags alone cannot move the focus to resolution.
4. **No unsupported claims:** automated tests and sampled records show zero “improved,” “reliable,” “fixed” or “resolved” claims without the required independent evidence.
5. **Continuity after failure:** an unresolved checkpoint preserves the same focus and instruction and prescribes the next bounded action.
6. **Behaviour change:** among players with validated D_live decisions, the post-launch D_live miss rate improves over a pre-registered post-launch starting sample. The required sample, comparison window and pass bar are locked before evaluation. If the required sample is not reached, status is “insufficient evidence” and rollout pauses; it does not pass on thin data.
7. **Journey completion:** eligible users can move from diagnosis to first practice, then to checkpoint or Focus Game, without a dead end. Current usage is `unknown`; the existing MAU, WAU, attempt, training-user and conversion counts are explicitly not a baseline. Required post-launch sample and funnel decision rules are pre-registered; unmet sample pauses the decision.
8. **Retention:** D7 and D30 are measured from post-launch cohorts only, using a pre-registered minimum sample and, if used, a concurrent non-overlapping control. Pre-launch accounts and historic product behaviour are not the comparator. Insufficient sample produces “unknown,” never success.
9. **Paid value:** the paywall is reached after the user has seen a personal diagnosis and completed the free first practice. Conversion is measured separately from trial activation.
10. **Compatibility:** the default-off control path is unchanged, the core backend suites pass, the frontend builds, and analysis completion is idempotent.

## 6. Decision record and remaining blockers

1. **Category choice — approved; proof source narrowed:** external-game corpus evidence keeps `piece_safety` first. Current `simple_hang` flags are diagnosis-only because taxonomy recall is 61.61%. `piece_safety.d_live.v1` is the approved proof denominator/outcome fact.
2. **Free boundary — still a hypothesis:** diagnosis plus first prescribed practice is Free; ongoing monitoring, checkpoints, Focus Games, verdict history and later focus cycles are Pro. This remains a product judgment to test post-launch, not a conclusion from existing accounts.
3. **External Focus Game rule — approved:** use the next newly imported game after commitment, show the claimed game and allow “not my Focus Game” correction. No existing WAU claim supports expected firing.
4. **Numeric proof bars — approved:** lock corpus correctness/coverage values from external-game data and product-response values from post-launch data only. Pre-launch behavior is not a baseline.
5. **Price — approved for launch testing:** ₹199/month is the single production Pro price, supplied by canonical billing config. No annual plan is added in this scope.
6. **PIC versus LES sequencing — RESOLVED:** PIC is the active product V1. Knight-fork content is queued, while LES's subject-agnostic `teaching_engine`, `concept_mastery_service`, learner-state/demotion, content-tier and cohort contracts remain canonical for PIC.
7. **D_live outcome — APPROVED FOR IMPLEMENTATION:** strict v16 exposure is 15.07%; legal-destination-capture plus SEE/Stockfish corroboration yields 90.53% handled / 9.47% missed. Two SEE implementations agreed on 399/400 stratified positions. This is implementation agreement, not external precision/recall; the shared `cp_loss` gate and coach-meaning validity remain explicit limitations. The unexplained 28.6% sample and other formula candidates are rejected.

## 7. Pre-code requirements

No implementation starts until:

- **Implementation-owner certification — Codex, 2026-08-25:** the conditional validation relabel is incorporated and v1.3 matches the task authorization to start implementation. The independent reviewer's recommendation is review evidence, not recorded as owner sign-off.
- The completed corpus audit in `docs/simple_hang_corpus_evidence.md` remains the data citation; old-schema events stay excluded.
- The validated D_live implementation and rejected alternatives remain recorded in `docs/simple_hang_corpus_evidence.md`.
- A stratified human/engine read of approximately 50 D_live misses is completed before confirmatory rollout; it measures coach-meaning validity and is not a pre-code blocker.
- `games.user_rating` coverage is backfilled where authoritative and measured; unrecoverable rows stay `unknown`.
- Every diagnosis baseline and verdict enforces SEE-backed `schema_version >= 16`; all 1,145 pre-SEE events are excluded, and D_live requires its exact nested fact version.
- Existing behavioral counts are marked contaminated and excluded from all product-response baselines; required post-launch sample sizes and pause rules are pre-registered.
- The technical spec identifies every canonical source, field, endpoint, event and touched file.
- The technical spec references LES shared authorities rather than restating or replacing their rules; `user_active_focus` owns priority/instruction while `concept_mastery_service` owns learner-facing state.
- The data-lock plan separates valid external-game corpus evidence from unknown product-response behavior and names the exact procedure for choosing each numeric bar.
- The literal mockups above are accepted as the experience contract; visual polish may change, information hierarchy may not.
- One shared analysis-complete hook and its idempotency key are identified for imported games and Play With Coach games.
- The dirty worktree is checked and unrelated user changes are protected.
- Every new coaching sentence passes the existing voice rules before commit.
- The pre-code audit passes all six gates and is signed by the implementation owner before runtime code lands.
