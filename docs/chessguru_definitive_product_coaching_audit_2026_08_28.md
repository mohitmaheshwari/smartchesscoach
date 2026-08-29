# ChessGuru definitive product and coaching audit

**Date:** 2026-08-28  
**Status:** REVIEW COMPLETE — implementation not authorized by this document  
**Scope:** current product, chess intelligence, pedagogy, player personalization, routed experience, production use, reliability, competition, and the path to a personalized human chess coach  
**Supersedes as a current-state verdict:** numerical readiness claims in older reassessments, especially the July 2026 `7.4/10` beta recommendation

## Executive verdict

**VERDICT: NO — ChessGuru as it exists today is not yet the personalized human chess coach we envision.**

The direction is still right and the product is buildable. The current system has unusually valuable raw material: 14,250 games, 13,509 analyses, 424,642 move observations, an immediate game-review pipeline, Play with Coach, clock data, opening knowledge, own-game training positions, and a serious attempt to make chess explanations deterministic rather than letting an LLM invent chess.

But those assets do not yet combine into a coach. They combine into a large collection of analysis, explanation, lesson, focus, training, and progress systems that often disagree, are weakly adopted, and cannot yet prove that a player changed a behavior in real games.

The decisive distinction is:

> A chess tool explains positions. A chess coach changes how a particular player thinks, remembers what it is changing, chooses what comes next, and checks whether the change survived without help.

ChessGuru is strongest at the first sentence and incomplete on the second.

The current human-coach readiness is approximately **3/10**. That is not a code-quality score and it is not an average of arbitrary features. It means the system can already see and explain some important moments, but it cannot yet reliably run the complete sequence `observe -> diagnose -> prioritize -> teach -> rehearse -> test -> remember -> adapt` for even one focus in production.

I am confident in the product direction. I am not confident in a broad launch, paid promise, or 18-month revenue forecast until one closed coaching cycle works and retained users demonstrate that it matters.

## 1. What the product must make true

The product is not “AI chess analysis,” “personalized puzzles,” “Play with Coach,” or “a large lesson library.” Those are components.

The finished product should make a 600–1500 player feel:

1. **This coach really watched me.** It points to recurring decisions in my games, not a generic rating-band weakness.
2. **This coach knows what matters now.** It chooses one primary behavior and only a few supporting ideas I am ready to use.
3. **This coach explains chess, not engine output.** It names the piece, square, threat, plan, tradeoff, and practical decision in plain language.
4. **This coach teaches, not reports.** It asks me to predict, compare, replay, calculate, or apply—not just read.
5. **This coach remembers.** Home, Review, Training, Play with Coach, and Progress continue the same lesson.
6. **This coach adapts.** If explanation did not work, it changes the teaching method; if I learned the behavior, it moves on.
7. **This coach makes me smarter.** I begin noticing threats, plans, time decisions, opening ideas, and endgame rules without being prompted.
8. **This coach is honest.** It says improved, still recurring, or not enough evidence. It never decorates activity as progress.

That contract is the product. Every route and service should justify itself by its role in that sequence.

## 2. The six systems a human coach needs

A human-feeling coach is not one model. It is six connected systems.

### 2.1 Board truth — what happened in the position?

This includes tactical truth, strategic demands, candidate moves, opponent threats, material consequences, opening context, endgame theory, and clock context.

### 2.2 Player model — why is this recurring for this player?

This requires opportunity-aware rates, comparison with similar players, recency, severity, assistance history, time behavior, and uncertainty. A move can suggest a thinking failure; it cannot reveal a player’s psychology as fact.

### 2.3 Curriculum model — what is this player ready to learn next?

The coach must understand prerequisites and stage. It can honor a request to learn the Italian Game without dumping an opening library on a player whose current bottleneck is still leaving pieces undefended.

### 2.4 Teaching policy — what intervention should happen now?

Possible teaching acts include a direct explanation, prediction, comparison, board replay, hint, counterexample, short drill, silence, or celebration. “Generate a caption” is only one teaching act.

### 2.5 Memory and continuity — what are we working on together?

The same primary instruction, supporting focus, recent evidence, and next commitment must survive across sessions and surfaces.

### 2.6 Transfer measurement — did it change unassisted behavior?

Assisted puzzle success is practice, not proof. Proof comes from comparable decisions in later unassisted games, with event-time windows and an honest insufficient-evidence state.

ChessGuru currently has substantial pieces of systems 2.1 and 2.4, fragments of 2.2–2.5, and no working production implementation of 2.6.

## 3. Current product evidence

### 3.1 Production snapshot

Aggregate-only production census on 2026-08-28:

| Signal | Current value | Meaning |
|---|---:|---|
| Users | 120 | Small pre-launch cohort |
| Imported games | 14,250 | Strong raw longitudinal material |
| Game analyses | 13,509 | Analysis pipeline is real |
| Move observations | 424,642 | Valuable player-decision corpus |
| Focus documents | 272 | Several historical focus migrations |
| Active focus records | 90 across 52 users | Coverage is partial and includes strengths/null types |
| Focus records with a current metric | **0 / 272** | No working outcome measurement |
| Personal-cycle v1 records | **0** | The proposed closed cycle is not live |
| Active records with an instruction ID | **1 / 90** | Stable instruction continuity is effectively absent |
| Lifetime puzzle attempts | 400 across 18 users | Low use |
| Lifetime prescribed-training solves | 118 across 13 users | Low use |
| Last 30 days: Coach Play | 18 sessions across 8 users | Weak coaching-game habit |
| Last 30 days: puzzle attempts | 6 by 1 user | Training loop is not active behavior |
| Last 30 days: prescribed-training solves | 0 | No recent use |
| Payment intents | 3, all `created` | No verified successful payments |
| Users marked Pro | 2 | Not supported by successful payment records |

This is the clearest current truth: players generate game data, but almost nobody completes a repeated learning loop.

### 3.2 Product and architecture scale

The routed product currently contains 57 frontend routes, 54 page files, 261 top-level backend service files, and 248 backend test files.

Scale is not automatically a defect. Here it is a coherence risk because several domains have multiple recognizers, teaching engines, focus readers, progress calculators, and legacy/current pages. The player experiences the consequences as competing CTAs, different labels, and a coach that can sound intelligent locally without maintaining one relationship globally.

### 3.3 Reliability coverage

Current CI:

- parses backend Python files;
- directly runs four pure-logic backend test files;
- runs frontend `src/lib` tests only;
- builds the frontend;
- does not render routed components in CI;
- does not run an authenticated browser journey;
- does not exercise MongoDB, Stockfish, onboarding, import, Review, Training, or Play with Coach end to end.

The repository has many tests, but the deployed product journey is lightly protected. A large test count must not be read as launch confidence.

## 4. Chess-understanding audit

### 4.1 Tactics

**What exists**

- Cognitive gaps, caption principles, shape patterns, mastery detectors, and Chess Brain detectors cover hanging pieces, forks, pins, skewers, discoveries, back-rank ideas, overload, removal of defenders, trapped pieces, mating patterns, and related themes.
- Own-game tactical positions can become training material.
- The caption system has strong board-specific explanation work and engine-backed facts.

**What is reliable enough today**

- The strict detector authority inventories 116 IDs.
- Only `gap:piece_safety:simple_hang` is Plan-grade.
- 112 are Shadow and 3 are Disabled.
- Strict enforcement is default-off because enabling it would silence most current teaching.
- The hanging-piece caption path previously produced 14.4% concerning claims under a reused static verifier before exchange truth was corrected.
- Fork coverage on Lichess-tagged puzzles is promising, but tag absence is not negative truth and causal attribution remains unadjudicated.

**Verdict: PARTIAL, narrow truth inside broad coverage.**

ChessGuru can responsibly build its first complete cycle around simple piece safety. It cannot responsibly present itself as a fully validated tactical coach yet. Detector count is not tactical understanding; verified causal explanation is.

### 4.2 Positional play and plans

**What exists**

- Recognizers and templates exist for weak squares, outposts, bad bishops, space, open files, seventh-rank rooks, pawn majorities, isolated/doubled/backward pawns, coordination, piece activity, king activity, and pawn breaks.
- Position services attempt to turn Stockfish and board geometry into human explanations.
- Decode-style per-position explanation is possible in parts of the pipeline.

**Current limitation**

- Most positional detectors are Shadow and lack independently reviewed semantic precision/recall.
- `position_strategy_analyzer.py` includes simplified mobility heuristics and an explicitly unfinished pin/skewer section.
- A good engine move does not uniquely identify the human strategic lesson. A move may improve several things at once, and a readable LLM explanation can still select the wrong cause.
- There is no verified contrast-position curriculum that teaches a player to choose between two reasonable plans and explains the tradeoff.

**Verdict: EARLY.**

ChessGuru can sometimes explain a positional move. It cannot yet diagnose and teach recurring positional decision-making with human-coach reliability.

### 4.3 Calculation and thinking process

**What exists**

- Reflection, candidate-move prompts, guardian checks, escape-square logic, prediction/replay components, critical-move analysis, and thinking-score services.
- The system can identify a costly move and sometimes reconstruct what the player needed to see.

**Current limitation**

- The product rarely observes the player’s actual thought process; it infers from a move trace.
- Several interaction models coexist and are not sequenced by one teaching policy.
- The escape-squares endpoint is currently hard-disabled even though older documentation describes it as active.
- No shared model decides whether this player needs threat scanning, candidate generation, calculation depth, evaluation, or simply a safety habit.

**Verdict: PROMISING COMPONENTS, NO COHERENT THINKING CURRICULUM.**

### 4.4 Time management

**What exists**

- PGN clock parsing is honest: it emits nothing when clock data is absent.
- It compares critical-move time with the player’s own median rather than using one absolute time threshold.
- Production contains a large body of timed moves and time-stat games.
- Time-trouble, impulsive-move, and tilt-style detectors exist.

**Current limitation**

- “Rushed” and “took time” are heuristics, not yet a complete opportunity/outcome model.
- Time usage depends on time control, increment, game state, remaining time, move difficulty, and practical decision quality. Median-relative timing alone does not explain whether time was well spent.
- Rich time signals are not a canonical measured focus in production.

**Verdict: ONE OF THE BEST NEXT DIFFERENTIATORS, BUT NOT YET A PROVEN COACHING LOOP.**

Time management is more player-distinctive than the current piece-safety-heavy diagnosis and is poorly taught by most engine tools. It should be the second or third complete coaching cycle only after its truth model is validated.

### 4.5 Openings

**What exists**

- 79 top-level opening curriculum entries.
- Opening naming, theory lookup, deviation, profile, mastery, assessment, fit, and walkthrough services.
- Opening guidance and trap suggestions can appear during Play with Coach and Review.
- The player can deliberately choose an opening lesson.

**Current limitation**

- This breadth can become exactly the library product we do not want.
- Recognition, deviation, explanation, repertoire fit, and mastery are spread across many services.
- There is no single stage-aware request contract: `start now`, `supporting focus`, `scheduled next`, or `foundation first`.
- Line recall is not the same as understanding typical plans, pawn structures, tactical warnings, and recovery after leaving theory.

**Verdict: STRONG CONTENT ASSET, WEAK PERSONAL CURRICULUM.**

The correct product is not “79 openings.” It is “the coach knows which two ideas from the Italian matter for you now, notices them in your games, and revisits them later.”

### 4.6 Traps

**What exists**

- 28 opening families and approximately 54 trap lessons.
- Trap alerts, inline lessons, practice links, and a routed teaching catalog.

**Current limitation**

- The generic trap lesson mostly asks the player to reproduce an expected move sequence and reveals the expected move when wrong.
- Replaying a line can produce short-term recall without recognition in a changed position.
- Trap selection is not consistently driven by the player’s actual openings, opponent pool, stage, and demonstrated misunderstanding.

**Verdict: A USEFUL TOOL, NOT A COACHING SYSTEM.**

Traps should be contextual seasoning: “you face this structure and missed this idea twice,” not a front-page catalog.

### 4.7 Endgames

**What exists**

- The routed teaching catalog contains 18 lessons across 6 categories.
- Separate data covers essential mating, opposition, rule of the square, Lucena, Philidor, and related principles.
- Endgame offers and explanation templates exist.

**Current limitation**

- The rule-of-square detector is Disabled after weak/rare evidence.
- Most registered endgame concepts fired too rarely in broad game samples to validate from ordinary production games.
- Line-following lessons do not yet prove recognition or execution from varied positions.
- Tablebase/generated targeted strata and human-reviewed curriculum tests are required for rare theoretical endgames.

**Verdict: FOUNDATION CONTENT EXISTS; DETECTION, SEQUENCING, AND TRANSFER ARE NOT READY.**

### 4.8 Defense, conversion, and practical play

ChessGuru contains signals for missed opponent blunders, ignored threats, conversion, resourcefulness, critical moves, and opening recovery. Production audits found that these signals vary meaningfully between players, but the current focus ranking barely uses them.

**Verdict: HIGH-VALUE UNUSED PERSONALIZATION.**

These may distinguish players better than assigning piece safety to almost everyone. They need opportunity-aware definitions and teaching interventions, not just dashboard statistics.

### 4.9 Emotion, confidence, and coach tone

The coach may adapt tone using observable context: result streak, repeated miss, clean execution, time pressure, session length, and explicit preference taps. It must not claim to know frustration, fear, tilt, or personality from a move unless the player said so.

Today tone logic is distributed across personality helpers, captions, Home, and Play with Coach. There is no one inspectable policy governing warmth, directness, interruption, praise, or silence.

**Verdict: VOICE EXISTS; RELATIONSHIP POLICY DOES NOT.**

## 5. Product-journey audit

### Onboarding and first value

Onboarding has been a real blocker. Local fixes now address a welcome-screen navigation deadlock and browser-to-third-party account verification, but those fixes are not production evidence until deployed and walked end to end.

The first-session promise should be extremely small:

1. connect/import;
2. show one evidence-backed leak;
3. show two or three boards proving it;
4. give one instruction;
5. complete one short rehearsal;
6. explain what the coach will watch next.

No library exploration is needed before this revelation.

### Home

Home should be the coach’s conversation: what we are working on, what changed, and the one next action. It should not be a feature dashboard.

### Game Review

Review contains strong move-level material, but its weakness emphasis reads legacy player identity rather than the canonical active-focus contract. Earlier production data found `weakness_match=false` on all 11,852 stored review cards sampled. Review therefore behaves more like a smart analysis of this game than a continuation of the player’s current lesson.

### Training

Own-game positions, community positions, prescribed training, daily fixes, skills, motifs, quizzes, openings, and PIC lessons overlap. The issue is not a shortage of exercises. It is the absence of one assignment and one attempt ledger connected to the active focus and later proof.

### Play with Coach

Play with Coach has real potential and growing local intelligence. It also has a very large orchestration surface with feedback, guardian behavior, opening guidance, trap alerts, lessons, postgame analysis, and several coaching pipelines. Without one intervention budget it risks talking too much and teaching whatever detector happens to fire.

Play Mode and Coach Mode should remain distinct:

- **Play Mode:** behaves like an opponent; no live instruction; the game becomes later evidence.
- **Coach Mode:** uses sparse, system-timed interventions; teaches a primary focus while acknowledging other verified issues when useful.

### Progress

Progress should display behavior change and evidence, not activity. Today no production focus has a current metric, so a trustworthy improvement story does not exist yet.

## 6. Competitive reality in 2026

The market does validate willingness to pay for improvement. It also shows that ChessGuru’s old feature-level differentiation has largely disappeared.

| Product | Current first-party promise | What it makes non-differentiating |
|---|---|---|
| [Chess.com](https://support.chess.com/en/articles/8584089-how-does-game-review-work) | Game Review, explanations, retries, opening stats, lessons, and [live Play Coach](https://support.chess.com/en/articles/10877257-how-do-i-play-against-the-coach) | Move explanation, retries, lessons, and playing against a coach |
| [Lichess](https://lichess.org/features) | Free engine analysis, learn-from-mistakes, insights, studies, opening explorer, and puzzles from user games | Analysis and own-game tactics as paid standalone value |
| [Aimchess](https://aimchess.com/) | Rating-cohort comparison across six skills, personalized lessons from games, weekly plans, time training, retry mistakes, and own-game trainers | Aggregate analysis, time metrics, own-game practice, weekly planning |
| [Chessigma Supercoach](https://www.chessigma.com/supercoach) | 1,000-game/250+ metric profile, daily 15-minute plan, live modules, and an AI coach, aimed first at sub-1400 players | Large-history analysis, daily plan, AI conversation, blunder modules |
| [Chessy](https://chessyapp.com/) | Own-game plans, puzzles, weekly AI report, 80+ openings, cross-platform apps | The exact “your games, your patterns, your plan” pitch |
| [Phiamos](https://phiamos.com/) | Finds the player’s number-one leak, explains why, builds a plan, and claims to track the fix | “One leak at a time” and proof language as positioning |
| [Caissablanca](https://www.caissablanca.com/) | Own-game puzzles and Stockfish-verified AI claims with published release evaluations | Engine-grounded explanations and public accuracy evidence |
| [DecodeChess](https://decodechess.com/) | Deep explanations of threats, plans, piece functions, and concepts | Position explanation, especially positional explanation |
| [ChessDojo](https://www.chessdojo.club/) | Structured rating-cohort program, daily/weekly tasks, tests, progress, community, and paid human review | Guided structure, accountability, and visible progression |

Some competitor metrics are self-reported and should not be treated as independently verified outcomes. They still matter commercially because they set user expectations.

### The actual wedge

ChessGuru cannot win by having more features than Chess.com, more free tools than Lichess, a larger library than Chessable-style products, deeper single-position explanation than DecodeChess, or a more polished “personal plan” claim than every new AI coach landing page.

The credible wedge is:

> **A continuous coaching relationship that chooses one evidence-backed behavior, teaches it across Review and Coach Play, varies the intervention when it is not working, and earns an honest transfer verdict from later unassisted games.**

Even that sentence is not defensible as marketing until the product demonstrates it. The durable moat is the accumulated intervention-outcome data: which teaching act changed which behavior for which kind of player. Competitors can copy a caption or puzzle. They cannot immediately copy years of clean, causal coaching evidence.

## 7. Why earlier confidence was misplaced

Earlier reviews often converted implementation presence into product readiness:

- “focus exists” became “personalization works” even though no focus had a current metric;
- “detector exists” became “coach understands the concept” without semantic precision/recall;
- “lesson exists” became “concept is taught” without recognition or transfer checks;
- “many tests exist” became “no known bugs” while the routed journey was absent from CI;
- “analysis and puzzles are available” became “closed loop” while recent training use was nearly zero;
- “Pro users exist” became revenue possibility without a verified successful payment.

This audit rejects those substitutions.

## 8. Gap hierarchy

### P0 — stop false confidence and make one journey dependable

1. Deploy and independently walk onboarding/account connection/import recovery.
2. Remove or lock any unpaid Pro entitlement path; implement real recurring-entitlement truth before taking payment.
3. Establish one staging journey test: signup -> connect -> analysis -> diagnosis -> Review -> practice -> Coach game -> next-game evidence.
4. Make CI exercise routed components and one authenticated browser journey.
5. Declare one canonical authority each for focus, instruction, attempts, progress, and detector authorization.
6. Suppress “closed loop,” “improved,” and similar claims until the evidence contract passes.

### P1 — complete one real coaching cycle

Use the only current Plan-grade focus: simple hanging-piece prevention.

1. Select a primary focus from verified evidence.
2. Keep one literal instruction stable on Home, Review, Training, and Coach Mode.
3. Highlight only genuinely focus-relevant Review moments.
4. Run one canonical sequence of own-game and contrast reps.
5. Require an unassisted checkpoint.
6. Bind the focus to later eligible external games.
7. Return `improved`, `still recurring`, or `insufficient evidence` from comparable decisions.
8. Keep the focus or transition visibly based on evidence.

Until this works, additional detector families and lesson catalogs make the product wider without making it more like a coach.

### P1 — make diagnosis genuinely individual

Rerun focus ranking using opportunity-aware, rating-cohort comparisons. Candidate signals should include:

- leaving pieces loose;
- failing to notice opponent blunders;
- ignoring immediate threats;
- impulsive critical decisions;
- poor time allocation;
- conversion of winning positions;
- opening-specific repeated deviations;
- defensive resourcefulness;
- phase-specific collapse.

Do not lock a ranking formula from intuition. Bake off candidate formulas on stratified production users, then have a qualified chess coach review whether the selected focus is actually the highest-leverage teachable issue.

### P1 — create one coaching policy

Build an inspectable conductor that decides:

- when to speak and when to stay silent;
- primary versus supporting focus;
- explanation versus question versus board task;
- rating/stage depth;
- repetition and intervention fatigue;
- tone from observable context;
- what the player requested;
- what was already tried and whether it worked.

The LLM may improve language after chess truth and teaching intent are fixed. It must not decide board truth, player psychology, focus priority, or mastery.

### P2 — add breadth through the same cycle

Recommended order is evidence-dependent, not a permanent syllabus:

1. simple piece safety;
2. threat awareness / missed opponent opportunities;
3. time management;
4. one validated tactical motif family;
5. conversion/resourcefulness;
6. selected opening concepts requested or repeatedly encountered;
7. targeted endgame fundamentals with tablebase-backed truth;
8. positional decisions using contrast positions and human-reviewed plans.

Every new focus must bring its own diagnosis fact, teaching intervention, unassisted checkpoint, external-game opportunity definition, and transfer verdict. A detector without that package stays an explanation aid, not a coaching focus.

## 9. What to stop doing now

- Stop rating detectors “10/10” from implementation agreement, firing volume, or a few agreeable examples.
- Stop adding isolated detectors before a promoted detector completes the learning loop.
- Stop adding top-level pages when an existing surface owns the job.
- Stop treating opening/trap/endgame counts as teaching depth.
- Stop using an LLM to make missing chess truth feel personalized.
- Stop presenting assisted success, activity, rating fluctuation, or empty samples as improvement.
- Stop broad paid-launch work before entitlement security, activation, and retained value exist.
- Stop accepting old internal scores when newer production evidence contradicts them.
- Stop trying to make every feature visible. A coach chooses; a library exposes.

## 10. Time-constrained execution sequence

These are operating windows, not delivery promises. Each phase has a gate; missing the gate pauses expansion.

### Weeks 1–2: truth and reliable entry

- deploy the local onboarding repairs behind an appropriate release process;
- walk the full new-user journey on staging and production-safe accounts;
- establish core route/component and browser-level tests;
- close billing entitlement bypasses;
- inventory which local changes are actually deployed;
- choose one canonical focus/instruction/attempt/progress contract.

**Gate:** a new user can reach one evidence-backed diagnosis and start the assigned action without manual rescue.

### Weeks 3–8: one complete piece-safety coach

- wire the exact instruction through Home, Review, Training, and Coach Mode;
- consolidate duplicate rep/lesson paths;
- record assistance and opportunity evidence;
- add unassisted checkpoint and next external Focus Game;
- compute an honest outcome;
- test chronic, learning, clean, sparse, sacrifice, and no-opportunity cohorts.

**Gate:** the same player receives one coherent lesson and a reproducible honest verdict end to end.

### Weeks 9–14: human pilot and distinctive diagnosis

- observe real sessions, not only database traces;
- have a qualified coach independently review selected focuses and teaching messages;
- bake off cohort-distinctive ranking candidates;
- establish the silence/intervention/tone policy;
- measure whether players return after a newly imported game and start a second cycle.

**Gate:** users do not merely admire the report; they complete assigned work and return to continue the relationship.

### Months 4–6: paid beta and second/third focus

- add only the next best validated focus, likely threat awareness or time management based on the ranking audit;
- implement real recurring subscription lifecycle and provider-backed entitlements;
- offer a free diagnosis and first coaching experience, then charge for monitoring, continuity, later cycles, and verdict history;
- test price and packaging rather than declaring a permanent price.

**Gate:** some activated users pay, renew, and begin a second coaching cycle.

### Months 7–12: curriculum depth and one distribution engine

- expand tactical, opening, endgame, and positional teaching only through the same proof contract;
- learn which intervention works for which focus/player state;
- build one attributable acquisition channel with creators, coaches, academies, or shareable diagnosis;
- do not scale paid acquisition until retained revenue supports it.

### Months 13–18: scale only what retained

- scale the validated channel;
- expand global and Indian packaging from observed net ARPU and churn;
- invest in native/mobile breadth only if the retention funnel shows it is the bottleneck;
- reconcile ARR to provider-backed active entitlements.

## 11. Revenue reality

₹1 crore ARR equals approximately ₹8.33 lakh net monthly recurring revenue.

Illustrative concurrent paying-customer requirements, assuming the displayed price includes 18% GST and approximately 2% payment cost:

| Gross monthly price | Approximate net monthly revenue per payer | Approximate active payers for ₹1 crore net ARR |
|---:|---:|---:|
| ₹199 | ₹165 | 5,050 |
| ₹399 | ₹331 | 2,520 |
| ₹699 | ₹581 | 1,435 |
| ₹899 | ₹747 | 1,115 |

These are arithmetic scenarios, not forecasts. Competitors currently anchor personalized chess software around roughly $4.99–$11/month, while structured human-supported programs charge much more. ChessGuru should not try to justify a premium with “AI” or feature count. The premium must come from continuity, restraint, trustworthy diagnosis, and visible behavior change.

Current revenue verdict:

- **Could the direction support ₹1 crore ARR? YES, conditionally.**
- **Does current production evidence support forecasting it in 18 months? NO.**
- **Would launching the current product broadly make it likely? NO.**

The forecast becomes responsible only after we know activation, D30 retention, paid conversion after value, renewal, net ARPU, and channel acquisition cost.

## 12. Non-negotiable proof that the player became smarter

For a single focus, the system should eventually show all of the following:

1. The player can explain the instruction in plain language.
2. The player succeeds on an unassisted, unlabeled checkpoint.
3. The player recognizes the idea in varied positions, not only the memorized source position.
4. Comparable unassisted game opportunities are identified honestly.
5. The behavior’s handled/missed rate changes or remains unresolved with insufficient evidence.
6. The coach changes the method after repeated failure rather than repeating identical copy.
7. The lesson survives time and pressure in later games.
8. The next focus is chosen from new evidence, with the previous focus retained for maintenance if needed.

Rating improvement is an important long-run outcome, but it is noisy and should not be attributed to ChessGuru without stronger experimental evidence.

## 13. The next implementation decision

Do not begin a broad “make the coach understand everything” implementation. That will create another layer of partially wired intelligence.

The next product milestone should be named:

> **One player, one recurring simple-hang behavior, one instruction, one coherent coaching cycle, one honest external-game verdict.**

At the same time, stabilize entry, security, and the routed journey. Once that works with real users, add the next focus through the same architecture. That is how ChessGuru becomes broad without becoming a library, and human without pretending an LLM is a coach.

## Final position

We are not building the wrong idea. We have been building too many correct-looking parts before proving the relationship between them.

ChessGuru’s best chance is not to know every chess concept on day one. It is to be unusually good at choosing the right concept for one player, teaching it in a way that changes behavior, remembering it everywhere, and knowing when to move on. If we do that, tactical breadth, positional understanding, time management, openings, traps, and endgames become chapters in one coaching relationship. If we do not, they remain a large library with a coach avatar.
