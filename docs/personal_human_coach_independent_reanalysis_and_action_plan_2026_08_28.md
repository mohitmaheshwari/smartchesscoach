# ChessGuru: independent product reanalysis and action plan

**Date:** 2026-08-28  
**Status:** MOHIT AUTHORIZED PHASE A ON 2026-08-28; INDEPENDENT REVIEW PENDING  
**Decision covered:** whether ChessGuru should continue toward a personalized human chess coach and whether that direction can plausibly reach ₹1 crore ARR within 18 months  
**Implementation status:** Phase A implementation checkpoint complete locally; no production rollout authorized

This document is deliberately standalone. It does not assume that the reader trusts the prior session, prior plans, commit messages, or product claims. Every important conclusion is classified as code evidence, production evidence, market evidence, or an unverified hypothesis.

## Executive verdict

**VERDICT: YES — ChessGuru can plausibly become a ₹1 crore ARR product in 18 months, but the current production product cannot.**

The opportunity is not “another chess analysis or lesson library.” That market is already crowded. The viable product is a closed coaching relationship that:

1. observes a player's real games;
2. selects a small, stage-appropriate set of active focuses;
3. keeps one primary instruction stable across Home, Game Review, Training and Coach Play;
4. teaches with short, system-timed interventions instead of unlimited help;
5. checks the same behavior in later, unassisted external games; and
6. says **improved**, **not yet**, or **not enough evidence** without inventing progress.

The technical asset is credible: production contains 14,248 games, 13,466 analyses and 422,929 move observations. The product loop is not credible yet: 0 of 272 focus records has a measured `current_metric`, the new personal-improvement-cycle schema is not active in production, training use is near zero, and there are no verified successful payment records.

The commercial target is possible but distribution-heavy. At a hypothetical ₹399 consumer price inclusive of 18% GST and a 2% payment cost, approximately 2,515 concurrently paying subscribers are required for ₹1 crore net ARR. At the current ₹149 code default, the requirement is approximately 6,735. ChessGuru therefore needs both a higher-value product and a deliberate global-plus-India distribution model; product quality alone will not produce the ARR.

## Evidence and confidence rules

The following labels are used throughout:

- **VERIFIED — CODE:** directly inspected in the current working tree.
- **VERIFIED — TEST:** reproduced in this review by executing tests.
- **VERIFIED — PRODUCTION:** reproduced through read-only, aggregate-only queries inside the production backend container. No identity, PGN, position, token or user-level record was returned.
- **VERIFIED — MARKET:** checked against a current first-party page, official report, or primary paper on 2026-08-28.
- **HYPOTHESIS:** must be tested before it becomes a product or revenue claim.
- **PENDING:** evidence was not available in this review.

The repository is very dirty. This review did not attribute unrelated local changes to any one agent and did not modify runtime code.

## 0. Existing-surfaces audit

### What already exists

| User need | Current surface or service | What it actually provides | Evidence | Disposition |
|---|---|---|---|---|
| Home direction | `/home`, `HomePageNew.jsx` | Renders a personal-improvement-cycle card and instruction when the PIC payload exists | `frontend/src/pages/HomePageNew.jsx:363-369` | **EXTEND** |
| Immediate game review | `/game/:gameId`, `LabV2` → `GameDecryptionV5` | Strong move-by-move review and V5 captions; emphasis is based on legacy `known_weaknesses`, not the canonical active focus | `frontend/src/App.js`; `backend/services/game_decryption_v5_service.py:3429-3441`; `frontend/src/components/GameDecryptionV5.jsx:1490-1495` | **EXTEND AND REWIRE** |
| Guided practice | `/training/*`, `PrescribedTraining` | Existing pattern puzzles plus a newer PIC piece-safety lesson | `backend/routes/training.py`; `backend/services/teaching_engine.py`; `frontend/src/components/training/PICPieceSafetyLesson.jsx` | **CONSOLIDATE** |
| Coaching game | `/play-with-coach`, `CoachPlay` | Play mode and Coach mode, move feedback, guardian, lessons, immediate postgame analysis | `frontend/src/pages/CoachPlay.jsx`; `backend/routes/coach_play.py` | **EXTEND** |
| Canonical focus read | `focus_bridge.get_active_focus_bundle()` | Returns one active weakness with optional stable instruction fields | `backend/services/focus_bridge.py:248-324` | **CHANGE CONTRACT** |
| Outcome evidence | `focus_game_service`, `concept_mastery_service` | Can record external focus-game evidence, but verdict remains `measurement_pending` | `backend/services/focus_game_service.py:215-230`; `backend/services/focus_bridge.py:233-241` | **COMPLETE** |
| Detector authorization | `detector_quality.py` | Fail-closed Plan/Caption/Shadow/Disabled authority exists; strict enforcement is default-off | `docs/detector_quality_gate_implementation_2026_08_27.md` | **PROMOTE THEN ENFORCE** |
| Billing | `/pricing`, Razorpay order + HMAC verification | Securely verifies a one-time order, then permanently sets `plan=pro`; a separate mock endpoint also grants Pro | `backend/routes/billing.py`; `backend/routes/gamification.py:161-168`; `backend/subscription_service.py:211-223` | **REPLACE LIFECYCLE** |

### Overlap decision

**EXTEND AND CONSOLIDATE. Do not create a parallel “AI Coach” page or a second coaching system.**

The repository already has the four correct surfaces. The missing product is the shared coaching brain and evidence loop between them. A fifth top-level surface would add shelf clutter while leaving the core defect untouched.

Existing documents remain useful component specifications:

- `docs/personal_improvement_cycle_scope.md` and `docs/personal_improvement_cycle_spec.md` describe a candidate learning cycle.
- `docs/one_surviving_instruction_scope.md` describes stable instruction identity in Coach Play.
- detector data-lock and implementation documents contain reusable quality evidence.

They are not proof that the product is live. Production currently has no `cycle_version=1` focus records, no measured current metrics and effectively no stable instruction rollout.

## 1. What the finished product is

ChessGuru is a coach for motivated 600–1500 players who play several online rapid games per week, feel stuck, and do not know what to work on. It is not a content library and it does not ask the player to design a curriculum. It watches real decisions, chooses a primary focus plus a tightly limited set of supporting focuses, teaches only what the player is ready to use, and remembers those focuses everywhere. The player may request a topic such as the Italian Game, but the coach decides how to sequence it safely alongside the active improvement plan.

### The human-coach contract

A human-feeling ChessGuru must satisfy all of these behaviors:

- **It remembers.** The same instruction survives between games and surfaces until evidence changes it.
- **It prioritizes without tunnel vision.** One primary behavior leads the cycle; supporting issues can be acknowledged and taught when relevant.
- **It notices context.** Tone becomes warmer after a painful loss, quieter during overload, and more demanding after repeated clean execution. This is inferred from observable context and selectable preferences, not essay questions.
- **It intervenes with restraint.** Coach mode helps at selected teachable moments. It does not reveal every answer or interrupt every imperfect move.
- **It distinguishes practice from proof.** Assisted Coach Play and guided puzzles build skill; only eligible unassisted decisions can prove transfer.
- **It explains on the board.** The message names the move, square, threat or exchange that matters. It does not hide behind taxonomy labels.
- **It is honest.** No improvement, mastery, streak or “fixed” statement appears without its required evidence.

### Literal user experience contract

After an imported game:

> **Your main focus: check the landing square before moving a piece.**  
> You had three real chances to use it today. You handled two. On move 18, the bishop moved to g5 and Black could take it safely.  
> **Next:** replay that decision, then play one Coach game with this check active.

During Coach mode, at a relevant moment:

> **Your focus is active here.** Before you move the knight, check whether its new square is protected. Take your time; I will not show the move yet.

After later unassisted games:

> **Getting better:** in your baseline you protected the landing square on 11 of 20 comparable decisions. In your last five games, you handled 9 of 12. I need a few more decisions before I retire this focus.

If evidence is insufficient:

> **Not enough evidence yet.** You have only had two comparable decisions since practice. Keep the same focus; I am not going to guess.

## 2. Current production baseline

Read-only aggregate snapshot taken on 2026-08-28:

| Signal | Current value | Interpretation |
|---|---:|---|
| Users | 120 | Pre-launch/small cohort |
| Games | 14,248 | Strong longitudinal raw material |
| Game analyses | 13,466 | Analysis coverage is real |
| Move observations | 422,929 | Main data asset |
| Active-focus documents, all history | 272 | Multiple migrations/versions exist |
| Users with an active focus of any type | 52 | Focus does not cover the full user base |
| Active weakness focuses | 43 users / 43 records | Exactly one weakness focus per covered user |
| Active strengths | 39 | Production commonly has one weakness plus one strength |
| Focus records with `current_metric` | **0 / 272** | No measured learning outcome |
| PIC `cycle_version=1` records | **0** | New cycle is not live |
| Active records with an instruction ID | 1 | Stable instruction rollout is effectively absent |
| Focus resolutions | 50 `no_data`, 18 `metric_gap`, 204 empty | Historical outcome path failed or never ran |
| Puzzle attempts, lifetime | 400 across 18 users | Low adoption |
| Training solve attempts, lifetime | 118 across 13 users | Low adoption |
| Last 30 days: imported games | 1,854 across 38 users | A real active-game cohort exists |
| Last 30 days: analyzed games | 1,336 across 36 users | Enough data for a beta |
| Last 30 days: Coach Play | 18 sessions across 8 users | Weak adoption |
| Last 30 days: puzzle attempts | 6 attempts by 1 user | Training loop is not a habit |
| Last 30 days: training solve attempts | 0 | Prescribed training is not active behavior |
| Payment intents | 3, all `created` | Zero verified successful payment records |
| Users marked Pro | 2 | Cannot be treated as paying users; no successful intent supports them |

### Important data-model finding

Production has 90 active focus records across 52 users: 38 users have two active records, but those are normally one weakness and one strength. No user has multiple active weakness records. The canonical reader calls `find_one()` with no ordering and returns only one weakness. This does not yet satisfy the requirement that a player may have multiple active learning focuses while every surface understands their hierarchy.

The recommended contract is:

- one **primary active focus** with the stable instruction used for prioritization and intervention;
- zero to two **supporting active focuses** that may be acknowledged or taught when a real moment occurs;
- strengths remain separate positive evidence, not disguised as another weakness;
- user-requested topics enter a visible request queue and are either started, scheduled, or explained as premature.

The exact supporting-focus limit must be data-locked from cognitive load and pilot behavior; it is not hardcoded by this document.

## 3. Verified product gaps

### P0 — trust, correctness and paid-launch blockers

#### G01. The outcome loop never reaches a real verdict

- **Evidence:** 0/272 production focus records have `current_metric`; `focus_bridge` and `focus_game_service` still emit `measurement_pending`.
- **Failure:** ChessGuru can prescribe but cannot honestly say whether the prescription transferred to real games.
- **Required correction:** one event-time definition, one opportunity denominator, baseline and comparison windows, assisted/unassisted eligibility, idempotent evidence writes, and a deterministic verdict evaluator.

#### G02. The canonical focus is not canonical across the product

- **Evidence:** Home and Coach Play read PIC instruction text. Game Review still prioritizes legacy `known_weaknesses`; canonical instruction fields are default-off and role-gated in `focus_bridge`.
- **Failure:** the player can be told to work on one behavior at Home, study unrelated moves in Review, and receive generic Coach Play commentary.
- **Required correction:** a versioned coaching-context response consumed by all four surfaces, with the same focus and instruction IDs in analytics and persisted evidence.

#### G03. Multiple active focuses have no explicit hierarchy contract

- **Evidence:** the production schema separates one weakness and one strength; `get_active_focus_bundle()` returns one arbitrary matching weakness via `find_one()`.
- **Failure:** future additional focuses will be inconsistent or whichever document Mongo returns first.
- **Required correction:** ordered primary/supporting/requested states, deterministic selection, stable IDs, and migration tests.

#### G04. Detector truth is too narrow for a broad human coach

- **Evidence:** the current authorization report contains 116 IDs: **1 Plan, 110 Shadow, 5 Disabled**. Strict enforcement is default-off. Hanging piece is Shadow; king safety and trapped piece are Disabled; fork/pin/skewer remain Shadow.
- **Failure:** enforcing safety today would silence most teaching, while leaving enforcement off allows unpromoted detectors to influence existing surfaces.
- **Required correction:** promote a small high-coverage coaching ladder with independent semantic gold before expanding breadth. Reuse the locked Plan/Caption thresholds in `docs/detector_quality_threshold_lock_2026_08_27.md`; do not lower them to ship faster.

#### G05. Two training systems encode the same job

- **Evidence:** `rep_generator.py`/`RepRunner.jsx` create deterministic piece-safety reps while the PIC teaching path separately serves own-game `best_move_san` puzzles.
- **Failure:** different practice records, thresholds and verdict eligibility will drift.
- **Required correction:** one canonical rep contract and attempt ledger; generators become adapters, not parallel products.

#### G06. Billing is not a recurring subscription and has a privilege bypass

- **Evidence:** `billing.py` creates a Razorpay order and verifies its HMAC, then permanently sets `plan=pro`. There is no subscription ID, renewal, expiry, cancellation or payment-failure webhook lifecycle. `POST /subscription/upgrade` calls a function explicitly documented as mock and grants Pro to any authenticated caller.
- **Failure:** an authenticated user can obtain Pro without payment; a one-time ₹149 order is presented as monthly; cancellation and retry promises in Terms/Refund pages are not implemented.
- **Required correction:** remove/lock the mock endpoint, implement provider subscription lifecycle and webhook idempotency, derive entitlements from subscription state, and align policies with reality before accepting money.

#### G07. The product currently promises a “full closed loop” it does not deliver

- **Evidence:** Pricing copy says “every game watched, every pattern tracked” and “the full closed loop”; production has no measured focus outcome and near-zero training use.
- **Failure:** trust and consumer-protection risk.
- **Required correction:** suppress the claim until the closed-loop acceptance test passes. Sell only demonstrated value.

### P1 — human-coach experience gaps

#### G08. Diagnosis is personalized by history, but not reliably distinctive

The 2026-08-13 production audit found that 47/50 profiled users received piece safety first while unused behavioral signals varied much more between users. Current production still has 192 historical piece-safety focus documents versus very small counts for most other topics. This is historical evidence, not a newly reproduced distribution audit, so it must be rerun before changing the ranking formula.

The next ranking bake-off must compare recurrence, severity, rating-band deviation, controllability and teachability on the same stratified users. No new formula is locked here.

#### G09. Tone is local copy, not a shared coach policy

Tone should be inferred from observable state: recent result, repeated miss, clean handling, time pressure, session length, assistance history and selected preference. Today those decisions are spread across captions, Home, Coach Play and personality helpers. There is no inspectable deterministic policy that guarantees the same coach temperament everywhere.

#### G10. Coach Play can become interruption-heavy

The product contains move feedback, guardian prompts, lessons, escape-square quizzes, openings and pattern coaching. Without a shared intervention budget and focus priority, more intelligence can make the coach feel less human. The 2026 randomized chess-learning study strengthens the correct direction: system-timed help outperformed unrestricted on-demand help, 64% versus 30% improvement after 12 weeks.

#### G11. User-requested learning is not part of the same plan

A player must be able to request the Italian Game or an endgame topic without turning ChessGuru into a library. The request needs a guided state—`start now`, `scheduled next`, or `foundation first`—and must coexist with the primary improvement focus.

#### G12. The app contains too many overlapping training and progress surfaces

The correct path is not to delete useful capabilities blindly. It is to make Home the coach's conversation, Review the evidence, Training the assigned work, Coach Play the assisted rehearsal, and Progress the proof. Pages that cannot explain their role in that loop should be merged, demoted or removed after route analytics and user observation.

### P2 — commercial and defensibility gaps

#### G13. The idea alone is no longer differentiated

Current direct competitors now claim much of the same language:

| Product | Current public offer | What it means for ChessGuru |
|---|---|---|
| [Chess.com Premium](https://www.chess.com/membership) | Game Review, coach explanations, retries, lessons and Play Coach; $4.17–$16.67/month when billed yearly on the page reviewed | Scale, play network and breadth cannot be ChessGuru's wedge |
| [Aimchess](https://aimchess.com/) | Aggregate analysis of up to 1,000 online games and generalizable guidance | “We analyze all your games” is established, not unique |
| [Chessy](https://chessyapp.com/) | Own-game insights, puzzles from blunders and weekly AI coaching report; $7.99/month, $49.99/year or $79.99 lifetime | Own-game puzzles plus a personalized plan are commodity claims |
| [NextMove](https://nextmove-chess.com/pricing) | Weakness fingerprint, evolving plan, spaced review and “proof-of-fix”; $6.99/month | Even proof language is already public positioning |
| [DecodeChess](https://decodechess.com/pricing-plans/) | Plain-language reasons behind engine moves; $8.25/month or $84/year | Explanations alone are not a subscription moat |
| [ChessDojo](https://www.chessdojo.club/plans-pricing) | Structured plans, progress, community and human feedback tiers; $12/month annually for Core | Accountability and guided sequencing have proven willingness to pay |

The defensible wedge must therefore be executed behavior, not marketing words:

> **One evidence-backed coaching instruction that persists across review, guided practice and live coaching, then earns a real-game transfer verdict.**

#### G14. Distribution has no demonstrated engine

Aimchess reached more than 100,000 registered users in about a year and was acquired for approximately $485,000, validating demand but also showing that a useful chess analytics product is not automatically a huge business. ChessGuru currently has 120 users, no verified successful payments and no evidence in this review of a repeatable acquisition channel.

#### G15. Current price and packaging sell usage limits, not the coaching outcome

The Pricing page lists analysis quotas, LLM narratives, queue priority and auto-sync. Those are costs/features. Players pay to stop recurring mistakes and improve. Packaging must sell continuity, accountability and verified progress.

## 4. Why the direction is still right

### Demand is validated

- Aimchess's official acquisition announcement reported more than 100,000 registered users in its first year, consistent MRR growth and a $7.99 subscription.
- Direct products charge roughly $6.99–$12/month for automated or structured training; human-assisted tiers are much higher.
- Chess.com's current paid bundle prominently sells Game Review, coach explanations, lessons and Play Coach.

### Guided teaching is supported by evidence

The 2026 field experiment with more than 200 chess students found that system-regulated AI help produced 64% performance improvement versus 30% when students could request unlimited help. The mechanism was productive struggle and engagement. This supports ChessGuru's intended guided-coach model and argues against unlimited answer reveal.

Source: [Academy of Management Proceedings — Self-Regulated AI Use Hinders Long-Term Learning](https://journals.aom.org/doi/10.5465/AMPROC.2026.383bp).

### The data asset can support real personalization

ChessGuru already stores move-level behavior, timing, recurrence and game context. Research such as [Maia4All](https://arxiv.org/abs/2507.21488) shows individual chess behavior can be modeled from as few as 20 games. ChessGuru does not need Maia4All for V1, but this confirms that behavior-level personalization is technically plausible. The V1 core should remain deterministic and auditable; model-based prediction is a later shadow experiment.

### The caution

RevenueCat's 2026 benchmark reports median download-to-paid conversion of 0.9% on Android and 2.6% on iOS; freemium is approximately 2.1%, while hard paywalls are materially higher. AI apps can monetize well but often retain worse. This makes retention and an early “this coach understands me” moment as important as feature depth.

Sources: [RevenueCat on the Android paywall gap](https://www.revenuecat.com/blog/engineering/android-paywall-gap) and [RevenueCat State of Subscription Apps 2026](https://www.revenuecat.com/state-of-subscription-apps/).

## 5. Revenue model and ₹1 crore ARR math

### Definition

₹1 crore ARR means ₹10,000,000 annual recurring revenue, or approximately ₹833,333 monthly recurring revenue. It does not mean cumulative cash collected over 18 months.

The following sensitivity table assumes consumer prices include 18% GST and payment cost is 2%. These are planning assumptions, not accounting advice or a locked price.

| Monthly consumer price | Approx. net monthly revenue/subscriber | Active subscribers for ₹1 crore net ARR |
|---:|---:|---:|
| ₹149 — current code default | ₹124 | 6,735 |
| ₹299 | ₹248 | 3,356 |
| ₹399 | ₹331 | 2,515 |
| ₹499 | ₹414 | 2,011 |
| ₹699 | ₹581 | 1,436 |

### Recommended business model

**Free proof, paid continuity.**

Free should deliver enough real coaching value to establish trust:

- account connection and sync;
- first evidence-backed diagnosis with examples;
- limited immediate game review;
- one short guided practice experience; and
- an honest preview of what the coach will monitor next.

Paid should fund the ongoing relationship:

- continuous eligible-game monitoring;
- primary and supporting focus management;
- assigned practice and spaced review;
- full Coach Play guidance;
- real-game outcome checkpoints;
- weekly/monthly coach brief; and
- access to requested learning plans when stage-appropriate.

Do not sell “more Stockfish” or a giant lesson catalog as the main reason to subscribe.

### Price decision

**Not locked.** The ₹149 default is commercially weak for the ARR target and the current one-time entitlement is invalid. The paid beta should test candidate price/package cells after a user experiences a full coaching loop. Candidate cells should be selected from competitor anchors and India/global willingness-to-pay evidence, then decided by observed checkout, activation, refund and retention behavior—not preference surveys alone.

### Distribution requirement

Illustrative case only: to sustain 2,500 active paid subscribers with 5% monthly payer churn over 18 months, the business needs roughly 207 new paid subscribers per month on average. At 2.1% download-to-paid conversion, that implies about 177,000 cumulative qualified downloads; at 5% conversion, about 75,000. A ramped business will need higher acquisition in later months than these simple averages.

This is why “build it accurately” is necessary but insufficient. A creator, SEO, referral, coach-partner or app-store acquisition engine must prove repeatability by month 6, not be postponed until the product is “finished.”

## 6. Implementation plan

Assumption: one small senior product/engineering team. Week estimates are sequencing aids, not promises. Any threshold or ranking formula goes through the existing data-lock process before code is written.

### Phase A — establish truth and remove launch hazards (Weeks 0–2)

| ID | Task | Implementation targets | Done evidence |
|---|---|---|---|
| A1 | Reproducible production census | Add an admin/read-only aggregate report for the baseline in this document; version query semantics and timestamp fields | A second agent reproduces all counts within expected live-data drift; no PII output |
| A2 | Product-claim honesty register | Inventory Home, Progress, Pricing, email and review claims; suppress “improved/fixed/full loop” claims without evidence | Automated tests fail on ungrounded claim states; copy matrix reviewed |
| A3 | Close the Pro bypass | Remove or admin/test-gate `/subscription/upgrade`; test authorization and entitlement boundaries | An ordinary authenticated account cannot become Pro without a verified provider event |
| A4 | Subscription scope | Write the recurring-billing scope: subscription creation, webhook verification, renewal, cancellation, grace, failure, expiry, refund and policy alignment | Scope signed off before billing code; provider test-mode sequence reproducible |
| A5 | Analytics source map | Export current PostHog funnel baselines and define canonical event owners/IDs across activation, review, training, PWC, paywall and payment | Events observed end-to-end in staging; no duplicate event definitions |

#### Phase A implementation checkpoint — 2026-08-28

| ID | Local implementation evidence | Remaining gate |
|---|---|---|
| A1 | Read-only aggregate-only `backend/scripts/product_loop_census.py`; production execution reproduced the baseline within live-data drift; helper tests added | Independent reviewer rerun |
| A2 | `docs/product_claim_honesty_register.md`; unsupported Home, Review, Progress, focus-lock, email, Landing and Pricing claims suppressed; regression tests added | Copy/product review |
| A3 | Mock upgrade route/helper removed; legacy order checkout disabled by default and incapable of running with live Razorpay keys | Production deployment plus security review |
| A4 | `docs/recurring_subscription_scope.md` written | **Mohit must sign off this specific scope before lifecycle code starts**; provider test-mode capability/event matrix still required |
| A5 | `ANALYTICS_EVENTS` is the executable frontend registry; all emitters use it; unknown events fail closed; `docs/product_analytics_source_map.md` records owners and gaps | Authenticated PostHog baseline export and one observed staging journey; current live funnel remains unknown |

Focused local result: 48 tests passed. All modified Python modules compile and
all 12 modified JavaScript/JSX files parse with the installed Babel parser.
The repository-wide HTTP flow suite still requires a running backend, and the
frontend production build did not complete within the bounded local run; these
are reported validation gaps, not passing evidence.

### Phase B — one coaching contract across all surfaces (Weeks 2–6)

| ID | Task | Implementation targets | Done evidence |
|---|---|---|---|
| B1 | Canonical coaching-context API | Replace singular unordered read with versioned ordered `primary`, `supporting`, `strengths`, `requested_topics`, stable instruction IDs and evidence eligibility | Deterministic ordering tests; migration is idempotent; no surface queries focus collections independently |
| B2 | Focus ranking bake-off | Compare candidate rankings on stratified production users using recurrence, impact, cohort distinctiveness, controllability and teachability | Data-lock note names winner, rejected formulas and per-user output review |
| B3 | Game Review integration | Inject coaching context into the V5 service; prioritize matching moments without changing engine truth; show active-focus badge and exact supporting evidence | Same instruction ID appears on Home, Review and Coach Play; unrelated moves remain available but visually secondary |
| B4 | Coach Play integration | Carry fresh coaching context into session goal, intervention selection and postgame reflection; remove admin-only dependency after cohort gate passes | Focus-relevant intervention and postgame verdict share ID; stale session snapshot cannot overwrite a newer focus |
| B5 | Home and Progress consolidation | Home states today's assignment; Progress shows evidence/verdict history; remove competing generic “most improved” claims | Each surface has one role in the loop; route-level snapshot and accessibility review pass |

### Phase C — complete the learning and proof loop (Weeks 5–10)

| ID | Task | Implementation targets | Done evidence |
|---|---|---|---|
| C1 | Canonical opportunity record | Define opportunity, handled/missed, detector quality ID, event time, game context, assistance mode and idempotency key | Reprocessing the same game produces no duplicate evidence; backfill time is never treated as play time |
| C2 | One practice contract | Consolidate `rep_generator`, PIC puzzles and attempts behind one schema; preserve multiple exercise renderers | Every attempt has focus/instruction/source/assistance fields; one mastery service consumes all attempts |
| C3 | Assisted versus transfer evidence | Guided puzzles and Coach Play update practice state only; imported ordinary games can qualify for transfer | Tests prove assisted success cannot retire a focus and external eligible decisions can |
| C4 | Deterministic outcome evaluator | Baseline/comparison windows, minimum evidence, confidence and verdict state machine | Historical replay yields reproducible verdicts; missing evidence returns “not enough evidence,” never improvement |
| C5 | Immediate analysis guarantee | Track game-complete → analysis-ready → review-ready latency; make retries and failure state visible | Staging and cohort latency distribution is measured; no silent failed analysis |

### Phase D — safe coaching breadth and human behavior (Weeks 8–14)

| ID | Task | Implementation targets | Done evidence |
|---|---|---|---|
| D1 | First trusted focus ladder | Promote high-coverage candidate behaviors in measured order; likely candidates include simple hangs, threat response, missed free material/punish blunders and time management | Every Plan promotion meets the already locked 95% precision/Wilson/recall/negative/adversarial packet; authorization report is reviewed |
| D2 | Caption safety breadth | Promote enough Caption-grade principles/shapes that strict quality enforcement does not destroy teaching value | Staging quality gate on; caption coverage and abstention audited; no critical false claims |
| D3 | Enable detector quality enforcement | Cohort rollout, then global only after D1/D2 | Unknown/Shadow/Disabled IDs cannot influence caption, plan or mastery in enforcement cohort |
| D4 | Shared deterministic tone policy | Context signals → tone state → allowed moves/messages; templates remain 600–1500 friendly | Same scenario produces consistent tone across surfaces; no subjective writing required from user |
| D5 | Intervention budget | Primary focus, position criticality, prior help and productive struggle decide whether Coach Play prompts, waits or stays silent | Recorded sessions show explainable intervention decisions; no stacked prompts |
| D6 | Requested-learning queue | User can request opening/endgame topics; coach returns start/schedule/foundation decision and a bounded next step | Italian Game request works without replacing or silently ignoring primary focus |

### Phase E — paid beta and product-market fit (Weeks 12–20)

| ID | Task | Implementation targets | Done evidence |
|---|---|---|---|
| E1 | Concierge beta | Observe complete loops with motivated 600–1500 rapid players; capture confusion, trust, lesson usefulness and return behavior | Session notes plus funnel data; issues categorized by truth, UX, pedagogy or motivation |
| E2 | Subscription lifecycle | Implement signed webhooks, idempotent state transitions, expiry/grace/cancel/failure, receipts and self-service status | Provider test-mode matrix and security tests pass; policy text exactly matches behavior |
| E3 | Packaging experiment | Test free-first-cycle versus guided-trial entry and candidate India/global price cells | Pre-registered experiment; decision uses paid conversion, refunds, activation and early retention together |
| E4 | First-channel experiments | Creator partnerships, coach referral, own-game insight SEO/share cards and app-store/onboarding tests | At least one channel has measured visitor → connected account → insight → paid economics; no vanity-impression decision |

### Phase F — scale toward the 18-month target (Months 6–18)

1. Scale only the acquisition channel with acceptable retained-subscriber economics.
2. Add new focus families in measured coverage order, not feature-request order.
3. Use real-game verdict history to improve focus sequencing and difficulty.
4. Add a human-coach review tier or academy channel only after the self-serve loop retains; do not let B2B complexity distract V1.
5. Expand globally in English while retaining India-localized pricing and payments.
6. Review the ARR model monthly using net ARPU, payer churn and verified active subscription state.

## 7. Dependency order

```text
A1/A2/A3
   ↓
B1 canonical coaching contract
   ├── B3 Game Review
   ├── B4 Coach Play
   └── B5 Home/Progress
   ↓
C1 opportunity record → C2 practice contract → C3 evidence eligibility → C4 verdict
   ↓
D1/D2 detector promotions → D3 strict enforcement
   ↓
E1 observed beta + E2 real subscriptions + E3 packaging
   ↓
E4 repeatable acquisition → Phase F scale
```

Billing work A3/A4/E2 can run alongside the coaching kernel, but paid launch cannot precede E2. Detector work can run in parallel, but no detector may enter an active plan before its Plan-grade packet passes.

## 8. Acceptance gates before calling this a personalized human coach

### Gate 1 — one coach

- One canonical coaching-context API.
- Same primary focus and instruction identity on Home, Review, Training and Coach Play.
- Supporting focuses have explicit priority and cannot randomly replace the primary.
- Requested topics receive a visible decision.

### Gate 2 — true chess

- Every player-facing detector has the required authorization grade.
- Strict detector quality gate is enabled for the release cohort.
- Critical false claims are zero in adversarial packets.
- Abstention is accepted as a correct outcome.

### Gate 3 — real learning

- Guided practice and unassisted transfer are recorded separately.
- A replayable baseline and opportunity denominator exist.
- The product can produce all three honest outcomes: improved, not yet, insufficient evidence.
- No progress claim is generated from chronology-free or backfill-time data.

### Gate 4 — safe payment

- No mock or client-driven entitlement upgrade.
- Verified recurring subscription lifecycle, cancellation, expiry and payment-failure handling.
- Pricing and policies match code.
- Revenue reporting excludes GST and unverified entitlements.

### Gate 5 — demonstrated value and growth

Numeric commercial gates are intentionally not invented here. Before paid beta, pre-register and data-lock thresholds for:

- connected-account → first personal insight;
- insight → first guided practice;
- first practice → later external-game evidence;
- trial/free proof → paid;
- four-week learner retention;
- monthly and annual payer retention;
- refund rate;
- channel CAC, net ARPU and payback.

## 9. North-star and operating metrics

**North star:** externally verified focus cycles completed per weekly active learner.

This is better than games analyzed, captions generated, puzzles solved or time in app because it represents the promised outcome: the coach observed a recurring behavior, taught it and found credible transfer evidence.

Supporting measures:

- time to first undeniable personal insight;
- eligible opportunities per focus;
- handled-opportunity rate before and after practice;
- practice completion and return-to-real-game rate;
- intervention acceptance versus interruption/override;
- detector abstention, critical-error and authorization coverage;
- focus continuity across surfaces;
- paid conversion, net ARPU, payer churn and cohort ARR;
- acquisition by retained-subscriber channel, not registrations alone.

## 10. What not to build yet

- A broad new lesson library.
- Unlimited topic browsing as the primary experience.
- More top-level dashboards or a second “coach home.”
- New rare detectors before the first trusted focus ladder is live.
- LLM-selected focus or LLM-authored chess truth.
- Social leaderboards, streak systems or gamification unrelated to the active plan.
- Native apps solely to chase installs before the web loop retains.
- A marketplace or academy product before self-serve coaching proves value.

LLMs may later vary phrasing under strict fact slots and verification, but focus selection, opportunity truth, evidence eligibility and outcome verdicts remain deterministic and auditable.

## 11. Risks and explicit kill/change conditions

The product direction should be changed—not defended indefinitely—if a properly instrumented beta shows any of the following:

- players do not recognize the diagnosis as personally relevant after evidence is shown;
- guided practice completion does not lead players back to real games;
- real-game opportunity data is too sparse to produce timely honest verdicts;
- required detector precision makes useful coverage too narrow;
- players value Game Review but not ongoing continuity enough to pay recurrently;
- no acquisition channel can produce retained subscribers at sustainable economics.

The response would be to narrow the ICP, focus family or delivery model, not to add more generic features.

## 12. Review instructions for the next agent

The reviewer should independently:

1. reproduce the production aggregate table using the read-only route in `docs/REVIEW_BRIEF.md`;
2. verify the singular `find_one()` focus contract and cross-surface wiring;
3. rerun the detector authorization report and focused tests;
4. prove or refute the billing bypass and absence of recurring lifecycle;
5. compare the competitor claims on their live first-party pages;
6. recompute the ARR table including GST/fees;
7. challenge the phase dependencies and identify any task that can claim success without user behavior;
8. flag every recommendation that silently invents a numeric threshold.

### Verification reproduced in this review

- Focus/PIC/instruction tests: **46 passed in 53.04s**.
- Detector authorization report: **116 total — 1 Plan, 110 Shadow, 5 Disabled**.
- Production snapshot: aggregate-only queries, no writes and no identity/game content returned.

Passing focused tests does not contradict the production gap. It proves the current code's tested branches; production shows that the new cycle and stable instruction are not rolled out and no measured outcome exists.

## 13. Sources

### Repository evidence

- `docs/REVIEW_BRIEF.md`
- `docs/product_thesis_audit_production_data_addendum_2026_08_13.md` — historical audit evidence, not treated as current counts
- `docs/detector_quality_threshold_lock_2026_08_27.md`
- `docs/detector_quality_gate_implementation_2026_08_27.md`
- `docs/hanging_piece_detector_implementation_2026_08_28.md`
- `docs/king_safety_detector_implementation_2026_08_28.md`
- `docs/trapped_piece_detector_implementation_2026_08_27.md`
- `backend/services/focus_bridge.py`
- `backend/services/focus_game_service.py`
- `backend/services/primary_weakness_picker.py`
- `backend/services/game_decryption_v5_service.py`
- `backend/services/teaching_engine.py`
- `backend/services/rep_generator.py`
- `backend/routes/billing.py`
- `backend/routes/gamification.py`
- `backend/subscription_service.py`
- `frontend/src/pages/Pricing.jsx`
- `frontend/src/lib/analytics.js`

### Market and research evidence

- [Chess.com membership](https://www.chess.com/membership)
- [Chess.com Game Review documentation](https://support.chess.com/en/articles/8584089-how-does-game-review-work)
- [Aimchess](https://aimchess.com/)
- [Play Magnus Group acquisition announcement for Aimchess](https://kommunikasjon.ntb.no/ir-files/16823864/566/744/Download%20announcement%20as%20PDF.pdf)
- [Play Magnus Group 2021 Annual Report](https://live.euronext.com/sites/default/files/company_press_releases/attachments_oslo/2022/04/27/560151_en_Play%20Magnus%20Group%20Annual%20Report%202021.pdf)
- [Chessy](https://chessyapp.com/)
- [NextMove pricing](https://nextmove-chess.com/pricing)
- [DecodeChess pricing](https://decodechess.com/pricing-plans/)
- [ChessDojo pricing](https://www.chessdojo.club/plans-pricing)
- [Self-Regulated AI Use Hinders Long-Term Learning](https://journals.aom.org/doi/10.5465/AMPROC.2026.383bp)
- [RevenueCat Android paywall conversion analysis](https://www.revenuecat.com/blog/engineering/android-paywall-gap)
- [RevenueCat State of Subscription Apps 2026](https://www.revenuecat.com/state-of-subscription-apps/)
- [Maia4All](https://arxiv.org/abs/2507.21488)

## Final recommendation

Proceed, but proceed narrowly:

> **Build the smallest system that can carry one trusted coaching instruction through Review → Practice → Coach Play → later external games → honest verdict, while allowing a bounded set of supporting focuses. Then sell the continuity of that relationship.**

Do not add broad features until that loop is live, used and paid for. The next implementation step after independent review and explicit signoff is **Phase A**, followed by a scoped canonical coaching-context contract. No runtime coding should begin from this document before that signoff.
