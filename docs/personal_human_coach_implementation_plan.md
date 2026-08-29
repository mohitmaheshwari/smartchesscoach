# ChessGuru Personal Human Coach — Implementation Plan

**Status:** DRAFT v1 — awaiting Mohit sign-off before the next implementation phase.  
**Date:** 2026-08-28.  
**Decision:** EXTEND the approved Personal Improvement Cycle and One Surviving Instruction architecture. Do not create a parallel coach, focus store, training engine, progress model, caption path or pricing constant.

---

## 1. Outcome

ChessGuru will be a guided coach for 600–1500-rated players. It will watch the player's games, choose the most useful current improvement focus, show the exact positions that justify that choice, teach one reusable thinking instruction, recognize that focus during review and coached play, and use independent evidence from later games to decide whether the behaviour changed.

The product is complete only when the player experiences one continuous relationship:

```text
games → personal diagnosis → one instruction → focused practice
      → coached application → real-game evidence → honest verdict → next focus
```

The player may have one **primary focus** and up to two **supporting focuses**. The primary focus owns the active improvement cycle and Home recommendation. A supporting focus appears only when a current position or review provides relevant verified evidence. Supporting focuses never create three competing plans.

Play Mode and Coach Mode remain distinct. Play Mode is an ordinary opponent game whose evidence is analyzed later. Coach Mode provides carefully timed, system-controlled teaching during the game. Both modes feed the same player memory, focus and evidence authorities.

The commercial outcome is a credible path to ₹1 crore ARR in 18 months. That is a business target, not a product claim. It requires a retained paid coaching relationship and a repeatable acquisition channel; code completion alone does not satisfy it.

## 2. Existing-surface audit

### Existing foundations to extend

| Need | Existing authority or surface | Current state |
|---|---|---|
| Primary focus | `user_active_focus`, `focus_bridge.py`, `focus_resolver.py` | Built; rollout is flag/role gated |
| Stable instruction | `instruction_id`, `instruction_text`, `instruction_version` | Built for eligible PIC focus records |
| Home continuity | `HomePageNew.jsx` | PIC instruction and Focus Game entry exist |
| Prescribed practice | `teaching_engine.py`, `PICPieceSafetyLesson.jsx` | Built for piece safety; a second rep path still exists |
| Play With Coach | `coach_game_session.py`, `coach_play.py`, `PostGameReflection.jsx` | Focus bundle and instruction are wired; needs full journey validation |
| Focus Game | `focus_game_service.py`, coach routes | Commitment/correction flow exists; verdict remains measurement-pending |
| Game review | `game_decryption_v5_service.py`, `GameDecryptionV5.jsx` | Legacy weakness matching exists; canonical PIC focus is not the review contract |
| Learner-facing progress | `concept_mastery_service.py` plus legacy progress services/pages | Authority chosen but readers remain fragmented |
| Detector authorization | `detector_quality.py`, detector registry/gate | Built; unverified detectors remain Shadow/Disabled |
| Billing | Razorpay order + signature verification | One-time order is labelled monthly; no recurring lifecycle or expiry |

### Overlap decision

- Extend `user_active_focus`; do not introduce a new active-plan collection.
- Extend `focus_bridge`; every surface must use the same eligible focus bundle.
- Keep `concept_mastery_service` as the sole learner-facing progress projection.
- Keep `teaching_engine` as the lifecycle owner and `RepRunner` as the board-first renderer.
- Keep the verified caption pipeline as chess-truth authority. Focus context may change emphasis, never the engine-grounded claim.
- Replace unsafe/legacy billing paths before accepting production subscriptions.

## 3. Research translated into product rules

1. **Guidance beats a toolbox.** A 2026 randomized chess-training study found materially higher gains with system-controlled help than with unrestricted on-demand help. ChessGuru decides when to intervene, protects productive struggle and does not offer unlimited move reveals.
2. **Personalized analytics is validated, not unique.** Aimchess reached more than 100,000 registered users in roughly its first year and was acquired. Aimchess, Phiamos, Deepline and NextMove already market weakness reports and plans. “AI coach” and “find your leaks” are not a moat.
3. **The moat is verified continuity.** ChessGuru must prove the same instruction survives Review, Home, Training, Play With Coach and the later verdict, then measure transfer in an ordinary game.
4. **The first session must contain the revelation.** Subscription benchmarks show conversion is usually won or lost early, while AI-labelled apps churn faster. The free experience must reveal a specific, evidenced personal leak before the paywall.
5. **Retention is the business model.** The paid product is ongoing monitoring, checkpoints, Focus Games, verdict history, multiple-cycle continuity and the next plan—not additional engine-analysis credits.
6. **Launch globally, price locally.** India supplies a large active chess audience; global English customers improve blended revenue. Product and billing contracts must not assume INR-only forever.

Research references:

- System-regulated AI chess training: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5604932>
- Aimchess product and pricing: <https://aimchess.com/>
- Aimchess acquisition evidence: <https://live.euronext.com/sites/default/files/company_press_releases/attachments_oslo/2022/04/27/560151_en_Play%20Magnus%20Group%20Annual%20Report%202021.pdf>
- Chess subscription market: <https://www.chess.com/membership>
- Subscription conversion and retention benchmarks: <https://www.revenuecat.com/state-of-subscription-apps-2026-utilities>

## 4. Non-negotiable architecture and honesty locks

1. One primary focus owns one active cycle.
2. `user_active_focus` owns priority, immutable instruction and commitment state.
3. `concept_mastery_service` owns the learner-facing progress state.
4. Evidence producers append typed evidence; they do not independently declare mastery.
5. Assisted practice, unassisted checkpoints, committed external games and ordinary games remain separate evidence classes.
6. Piece-safety resolution requires `piece_safety.d_live.v1`; zero `simple_hang` flags is not proof.
7. Old pre-SEE observations (`schema_version < 16`) are ineligible for baselines and verdicts.
8. A focus may produce `improved`, `still recurring` or `insufficient evidence`. Thin data never becomes success.
9. No “rating improved because of ChessGuru” claim is allowed in V1.
10. Shadow or Disabled detectors cannot select a focus or produce an improvement claim.
11. Observable context may change tone; ChessGuru must not assert unobserved emotions or psychology.
12. Exact instruction continuity is release-blocking: the same `instruction_id` must resolve to the same literal text everywhere.
13. The coach detects, selects and explains the next focus; player approval is not required. A player can correct bad attribution or request a topic, but cannot be asked to configure the coaching algorithm.

## 5. Delivery phases

### Phase 0 — Establish a trustworthy baseline

**Goal:** know what works today, close release-safety holes and make every later result reproducible.

#### HC-000 · Make the test baseline real

- Make the existing backend test inventory runnable in CI with a recorded pass/fail manifest.
- Make the production frontend build run under `CI=true`.
- Separate known pre-existing failures from regressions; no silent skips.
- Record feature-flag values, schema versions and test commands in the QA evidence folder.
- Add an end-to-end seed fixture with a deterministic player, games, focus and D_live evidence.

**Done when:** a clean runner can reproduce the baseline; every changed phase reports unit, integration, E2E and frontend-build evidence.

#### HC-001 · Walk the existing PIC loop

- Enable `PERSONAL_IMPROVEMENT_CYCLE_ENABLED` and `PWC_SURVIVING_INSTRUCTION_ENABLED` for admin/reviewer roles only.
- Walk at least five representative journeys: chronic mistake, learner, clean player, sparse evidence and recurrence after practice.
- Capture payloads and screenshots for diagnosis, Home, Training, PWC, Focus Game and verdict.
- File each discontinuity against the task IDs below; do not repair by adding a parallel fallback.

**Done when:** every current path has an evidence artifact and every break has one owner/task.

#### HC-002 · Correct billing security and semantics

- Disable/remove the legacy authenticated `/subscription/upgrade` path that grants Pro without payment.
- Replace permanent one-time-order upgrades with a real recurring entitlement or an explicitly expiring paid period.
- Implement signed, idempotent provider webhooks for activation, renewal, cancellation, payment failure, refund and expiry.
- Store provider customer/subscription IDs, entitlement status, period start/end and last reconciled event.
- Make cancellation available from the account and align Terms/Refund copy with actual behaviour.
- Make access checks depend on current entitlement, never only `users.plan == "pro"`.
- Use the approved ₹199 PIC launch price as the first paid-beta control; remove the current ₹149 default and hardcoded price fragments.
- Add Razorpay test-mode E2E coverage, replayed webhook tests and an entitlement-reconciliation job.

**Done when:** an unsigned/replayed event cannot grant access, an expired/cancelled user loses paid access correctly, no endpoint can self-upgrade, and a reviewer completes purchase→renewal/cancellation in test mode.

#### HC-003 · Complete data hygiene

- Run the authoritative `games.user_rating` backfill in dry-run, review the histogram, then run the bounded write.
- Preserve `unknown` where no authoritative rating exists.
- Quarantine pre-SEE observations from every PIC baseline, diagnosis proof and verdict query.
- Suppress the untrustworthy “most improved” claim until it passes a registered null test.
- Fix event-time semantics: comparisons use game/decision time, not background-analysis completion time.

**Done when:** coverage and exclusions are published, queries have regression tests, and no learner-facing claim reads contaminated evidence.

#### HC-004 · Remove dead and unsafe parallel paths

- Inventory the dead `backend/coach_play/teaching_coach.py` path and any stale frontend routes that duplicate the enabled experience.
- Remove a legacy path only after reference search, flag-off comparison and replacement-contract tests prove it is unused.
- Keep cleanup commits separate from feature commits and preserve unrelated worktree changes.
- Delete duplicated constants/readers only after their canonical replacement is active and tested.

**Done when:** the enabled journey has one implementation per authority and no dead path can be accidentally re-routed into production.

### Phase 1 — Complete one piece-safety coaching cycle

**Goal:** make the central product promise true for one focus before adding breadth.

#### HC-100 · Put the primary focus into Game Review

- Add a review-level focus header with the immutable instruction and evidence source.
- Mark only verified moves relevant to the primary/supporting focus.
- Use focus context to order or emphasize existing captions; never rewrite engine truth.
- When the focus did not occur, say so or remain silent instead of forcing a match.
- Carry the same `instruction_id` into review analytics and typed next action.

**Done when:** Review, Home, Training, PWC and verdict display the same literal instruction; a cross-surface contract test fails on any mismatch.

#### HC-110 · Reconcile repetition paths

- Make `teaching_engine` the only lesson/session lifecycle owner.
- Make one rep schema support `is_safe`, `who_takes`, `find_loose`, move-choice and later `which_is_better` interactions.
- Make `RepRunner` the shared board-first frontend renderer.
- Migrate the PIC `best_move_san` lesson into that schema or retire the duplicate path.
- Collapse duplicate SEE/live-floor constants into one named authority.
- Preserve source game, decision fact, difficulty, assistance level and instruction ID on every attempt.
- Resolve player and rep difficulty from authoritative ratings and measured position evidence; replace the broad implicit 1200 fallback with an explicit `unknown` policy that cannot masquerade as personalization.

**Done when:** one generated rep can run through Home/Training/PWC entry points with one attempt record; duplicate lesson logic is unreachable behind the enabled flag.

#### HC-120 · Finish unassisted checkpoint and Focus Game evidence

- After assisted reps, require a bounded unassisted checkpoint.
- Preserve the same focus after failure and prescribe the next bounded action.
- Bind a Focus Game commitment to the next eligible newly imported game.
- Show the claimed Focus Game and retain the existing correction action.
- Record opportunity, handled/missed outcome and evidence provenance using D_live.

**Done when:** assisted success alone cannot resolve a focus and all no-opportunity games return `insufficient evidence`.

#### HC-130 · Implement honest verdict, resolution and transition

- Produce only `improved`, `still recurring` or `insufficient evidence` from eligible evidence.
- Resolve piece safety only after the registered D_live bar is met.
- Preserve a full immutable verdict history.
- Move a resolved focus to maintenance, select the next authorized focus and tell the player why it is next.
- Activation does not require approval, but the transition is visible and preserves correction/reporting actions for bad evidence or attribution.

**Done when:** synthetic chronic, learner, clean, sparse, no-opportunity and regressor cohorts all receive the expected outcome and no unsupported success wording appears.

#### HC-140 · Consolidate progress authority

- Make all learner-facing surfaces read the `concept_mastery_service` projection.
- Convert evidence services into producers, not competing progress calculators.
- Add a translation layer from internal states to calm human language.
- Retire or flag-off legacy progress cards only after two clean weeks at 100% rollout.

**Done when:** one fixture produces one state, evidence count and next action on every surface; no internal enum leaks to the UI.

### Phase 2 — Make the coach genuinely personal and human

**Goal:** select a focus that distinguishes this player and maintain a coherent relationship.

#### HC-200 · Cohort-distinctive diagnosis

- Compare the player with a rating-band cohort using opportunity-aware rates.
- Rank candidates by cohort deviation, recent recurrence, severity and likely rating impact.
- Require an authorized detector and enough evidence before selection.
- Return three concrete proof positions when available; never pad with weak examples.
- Backtest candidate ranking formulas side by side on stratified production users before locking one.

**Done when:** the registered 60-day evaluation can distinguish the player's weakness from the cohort and the selected issue passes sampled human review.

#### HC-210 · Deterministic named leaks

- Give a recurring behaviour a memorable evidence-grounded name, such as “the defender you stop checking.”
- Derive the name from verified subtype/facts, not an LLM personality inference.
- Show the same name in diagnosis, review, training, PWC and verdict.
- Fall back to a plain category label when evidence is insufficient.

**Done when:** every displayed leak name maps to inspectable facts and voice tests pass for the 600–1500 audience.

#### HC-220 · Primary and supporting focus hierarchy

- Keep one primary cycle and allow zero to two supporting focuses.
- Let supporting focuses surface only on verified relevance.
- Let the player request a topic; the coach decides whether it becomes primary, supporting or queued, with a plain explanation.
- Prevent multiple simultaneous training plans, competing Home CTAs or multiple resolution clocks.
- Keep Play Mode free from live instruction; reserve system-timed interventions for Coach Mode while both continue to generate later review evidence.

**Done when:** Home always gives one recommended action and a relevant supporting focus can still be acknowledged in Review/PWC.

#### HC-230 · Human continuity and restraint

- Say “again” only when the same authorized focus/subtype recurs with prior evidence.
- Begin sessions with the last unfinished commitment when relevant.
- End with what changed, what repeated and one next action.
- Praise the decision/process rather than the game result.
- Add non-shaming stop-playing guidance after a verified damaging streak, with opt-out.
- Adjust tone from observable context only; keep input to taps or two/three choices where possible.
- Add a coach-silence budget so ordinary moves do not generate noise.

**Done when:** continuity, voice, restraint and unsupported-psychology test suites pass and sampled sessions read like one coach rather than independent captions.

### Phase 3 — Activation and paid beta

**Goal:** deliver the first revelation quickly, charge for ongoing value and measure retention honestly.

#### HC-300 · Guided first-session activation

- Connect Chess.com/Lichess or import games.
- Show honest analysis progress and recovery from API/analysis failure.
- Present one diagnosis, three evidence boards and one named instruction.
- Run a bounded first practice session of approximately eight reps, subject to a data-locked session-length experiment.
- End with one plan and one next action; do not expose the full library.

**Done when:** a new eligible user reaches first completed practice without navigating unrelated pages and all funnel events are recorded once.

#### HC-310 · Daily coaching cascade

Home recommends exactly one action in this order:

1. Continue an interrupted lesson.
2. Review a newly analyzed focus-relevant game.
3. Complete the active-focus checkpoint.
4. Play/commit a Focus Game.
5. Do a short maintenance activity.

**Done when:** deterministic fixtures cover every branch and no state produces competing primary CTAs.

#### HC-320 · Value-based paywall

- Keep personal diagnosis, evidence boards and first practice free.
- Paywall ongoing monitoring, checkpoints, Focus Games, verdict history, supporting-focus continuity and later cycles.
- Trigger the paywall only after the free value event is recorded.
- Measure exposure, checkout start, payment success, activation and renewal separately.
- Never advertise “unlimited AI” as the product.

**Done when:** free users receive the promised revelation, paid entitlements are provider-backed, and checkout failure cannot destroy the completed free work.

#### HC-330 · Price and packaging experiment

- Retain ₹199/month as the signed-off paid-beta control.
- Do not lock the long-term price from competitor pages alone.
- After a preregistered activated-user sample, compare a low monthly offer, a market-aligned monthly offer and an annual-first offer.
- Evaluate 60-day collected revenue per activated user, paid retention, refunds and support burden—not checkout conversion alone.
- Add USD/global packaging only after recurring entitlement and tax/currency behaviour are verified.

**Done when:** the winning package has a written data lock with sample, distribution and rejected candidates.

### Phase 4 — Add breadth through the same cycle

**Goal:** broaden coaching without turning ChessGuru into a content library.

#### HC-400 · Time management

- Audit clock coverage and repair or withdraw the current detector.
- Separate impulsive critical moves, timeout risk and legitimate fast moves.
- Build independent opportunity/outcome facts before allowing resolution claims.

#### HC-410 · Endgame coaching

- Promote only verified endgame detectors: rule of square, opposition, king activity and conversion.
- Route each focus through the same instruction, rep, checkpoint and evidence contracts.

#### HC-420 · Positional and tactical breadth

- Add `which_is_better` positional reps using verified contrast positions.
- Add “tap where the game was lost” using decisive-swing truth and calibration scoring.
- Add fork/pin/motif focuses only after detector quality authorization and an independent proof fact exist.

#### HC-430 · Curated openings and variety

- Curate the opening experience from the large catalogue to two guided starting paths.
- Allow requested openings to queue without replacing the primary weakness silently.
- Use concept tags and spaced variety to avoid repetitive reps while preserving focus.

**Done for Phase 4 when:** every new category uses the existing cycle, has separate diagnosis/proof authorization, and adds no parallel progress or lesson system.

### Phase 5 — Distribution and ₹1 crore ARR path

**Goal:** make growth a product loop, not a post-build marketing task.

#### HC-500 · Acquisition artifact

- Create a free username-based Chess Leak Diagnosis.
- Make three evidence positions and the leak name shareable without exposing private game data.
- Deep-link the shared result into the matching first practice—not a generic dashboard.

#### HC-510 · Repeatable channels

- Launch English-first for global reach with localized Indian pricing.
- Test creator/coach affiliate links with source-to-renewal attribution.
- Use coaches and academies as distribution partners before building a separate B2B product.
- Add referral credit at a verified milestone such as focus resolution, not arbitrary activity.
- Do not scale paid acquisition until retained revenue supports the acquisition cost.

#### HC-520 · Revenue operating model

- Track ARR from active provider-backed entitlements, excluding GST, refunds, failed payments and complimentary/admin plans.
- Report paid users, blended net ARPU, renewal, involuntary churn and cohort retention.
- Treat approximately 2,500–3,500 active paid customers as the working mixed-price planning range; recalculate from observed net ARPU.
- At 5% monthly churn, 3,000 subscribers require 150 replacement subscribers per month before growth; acquisition planning must include this replacement load.

**Done when:** one acquisition cohort has measurable payback and renewal, ARR is reconciled to provider records, and growth does not rely on untracked organic assumptions.

## 6. Quality strategy and release gates

### Required test layers

1. **L0 chess-truth gold:** human-signed positions with origin, destination, reply candidates and engine verification.
2. **L1 unit/property:** boundaries, idempotency, event-time handling, evidence invariants and no illegal state transitions.
3. **L2 detector quality:** precision, recall, confusion matrix, rating bands, held-out users and adversarial positions.
4. **L3 pipeline integration:** import→analysis→observation→focus→practice→checkpoint→external verdict.
5. **L4 synthetic cohorts:** chronic, learner, clean, sparse, no-opportunity, regressor, sacrificer and wrong-phase.
6. **L5 honesty:** zero unsupported improved/fixed/reliable claims; assisted evidence never resolves; no opportunity means no evidence.
7. **L6 voice/continuity:** exact instruction identity, named-leak consistency, no jargon/psychology and no parallel coaching text.
8. **Billing/security:** signature, replay, owner mismatch, webhook ordering, cancellation, expiry, refund and entitlement reconciliation.

### Per-task evidence package

Every implementation task must hand the reviewer:

- scope/spec reference and task ID;
- files changed and canonical authority used;
- exact test commands and unedited output;
- before/after payload or screenshot;
- migration/dry-run report when data changes;
- feature-flag state and rollback action;
- known limitations and unverified claims;
- independent sampled records for any detector or user-facing assertion.

“Tests passed” without the command, output and covered contract is not release evidence.

## 7. Rollout

Reuse the existing default-off flags:

- `PERSONAL_IMPROVEMENT_CYCLE_ENABLED=false`
- `PERSONAL_IMPROVEMENT_CYCLE_ROLES=admin,super_admin`
- `PWC_SURVIVING_INSTRUCTION_ENABLED=false`

Sequence for behaviour-changing phases:

1. Default-off deployment.
2. Admin/reviewer A/B and complete journey walk.
3. Small eligible-user cohort with monitoring and support contact.
4. 10% eligible rollout after the registered gate passes.
5. One-week observation, then 100% eligible rollout.
6. Two clean weeks at 100%, then delete the replaced legacy path.

Rollback disables the reader/experience flag but preserves immutable evidence and payment records. Data migrations are additive and idempotent. Billing rollback must fail closed for paid-only access while preserving the customer's entitlement record for reconciliation.

## 8. Measurement plan

### Product funnel

Track unique, idempotent events for:

```text
account_connected
analysis_started / analysis_completed / analysis_failed
diagnosis_seen
evidence_board_opened
first_practice_started / completed
checkpoint_started / completed
focus_game_committed / imported / corrected
verdict_seen
focus_resolved / focus_continued
next_cycle_started
paywall_seen / checkout_started / payment_activated / renewed / cancelled
```

### Coaching truth

- instruction mismatch rate: must be zero;
- unsupported success claims: must be zero;
- eligible focuses ending in a measured result versus `insufficient evidence`;
- D_live opportunity, handled and missed rates before/after;
- diagnosis specificity versus rating-band cohort;
- manual-review agreement on selected focus and named leak.

### Retention and revenue

- completion of first practice;
- return after the next imported game;
- start of a second coaching cycle;
- post-launch D7/D30 retention;
- diagnosis→paid activation and activation→renewal;
- net ARPU, voluntary/involuntary churn and provider-reconciled ARR.

Historic behavioural counts are not launch baselines. Minimum samples, comparison windows and pass/pause rules must be preregistered with production distributions before a numeric decision is locked.

## 9. Dependency order

```text
HC-000 test baseline ─┬─ HC-001 current-loop walk
                      ├─ HC-002 billing safety
                      └─ HC-003 data hygiene

HC-001 ── HC-100 review focus ─┐
         HC-110 unified reps ──┼─ HC-120 checkpoint/focus game
         HC-140 progress ──────┘          │
                                          └─ HC-130 verdict/resolution

HC-130 ── HC-200 personal ranking ── HC-210 named leaks
                                  ├── HC-220 focus hierarchy
                                  └── HC-230 human continuity

HC-100..230 + HC-002 ── HC-300 activation ── HC-320 paywall
                                      ├────── HC-310 daily cascade
                                      └────── HC-330 pricing test

Proven piece-safety loop ── HC-400..430 breadth
Paid retained cohort ────── HC-500..520 distribution and scale
```

No breadth task may delay the Phase 1 closed loop. No acquisition scaling begins before billing reconciliation and retained-value evidence.

## 10. Planning windows and decision gates

These are operating windows, not delivery promises:

| Window | Intended outcome | Gate to continue |
|---|---|---|
| Weeks 1–2 | Phase 0 baseline, journey audit, billing security design | Reproducible tests; no free Pro escalation path |
| Weeks 3–6 | Review continuity, one rep path, progress projection | Cross-surface instruction contract passes |
| Weeks 7–10 | Checkpoint, Focus Game evidence, verdict and resolution | Synthetic cohorts and honesty suite pass |
| Weeks 11–14 | Cohort diagnosis, named leaks, human continuity | Sampled users receive genuinely distinctive diagnoses |
| Months 4–6 | Guided activation and paid beta | Users return after new games and some begin a second cycle |
| Months 7–12 | One repeatable acquisition channel; limited breadth | Provider-backed renewal and channel attribution exist |
| Months 13–18 | Scale retained channel toward ₹1 crore ARR | Net ARPU/churn math supports required paid-user count |

If users enjoy the report but do not return after subsequent games, pause breadth and fix the coaching loop. If payment converts but the second cycle does not retain, do not compensate with more acquisition spend.

## 11. Explicitly deferred

- A general-purpose LLM chat coach.
- Unlimited help or unrestricted move-reveal buttons.
- More than one simultaneous primary training plan.
- Claims that ChessGuru caused rating growth.
- Focus resolution outside categories with an independent authorized proof fact.
- A broad course marketplace or restoration of the full opening catalogue as Home choices.
- A separate academy/coach product before B2C retention is proven.
- Native-app work solely to chase store conversion benchmarks.
- Gamification, leagues, badges and streak economies unrelated to the coaching cycle.
- Paid-ad scaling before provider-backed retention and payback are measured.

## 12. Sign-off decisions

The product direction and existing PIC scope are already approved. This implementation plan needs explicit sign-off on the following sequencing decisions:

1. Treat billing entitlement/security (HC-002) as a Phase 0 release blocker.
2. Build focus→Review and rep consolidation before any additional detector category.
3. Keep one primary focus plus at most two contextual supporting focuses.
4. Keep ₹199 as the paid-beta control, then use post-launch data to select long-term pricing.
5. Require a complete, measured piece-safety cycle before expanding to time/endgame/tactical focuses.
6. Treat distribution work as part of implementation beginning with activation instrumentation, not something started after the product is “finished.”

After explicit sign-off, the next action is not broad coding. It is Phase 0: record the test baseline, walk the admin PIC journey, write the billing-security scope/spec, and turn each observed discontinuity into the task/evidence contract above.
