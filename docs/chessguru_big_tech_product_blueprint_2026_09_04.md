# ChessGuru: company-level product blueprint

**Date:** 2026-09-04  
**Question:** If a product organization with Google/Microsoft-level discipline built ChessGuru, what would it do across product, learning, frontend, backend, trust, customer journey, growth, and revenue?  
**Basis:** Current repository, the existing ChessGuru product audits, current public competitor offerings, and established learning-product and reliability practices.

## Executive verdict

ChessGuru is pursuing a real problem and has the ingredients for a valuable product. It is not yet a coherent product.

The repository already contains more chess intelligence than most early products: game import, Stockfish analysis, move facts, concept detection, player profiles, active focuses, personal puzzles, game review, Play with Coach, opening/endgame/trap material, coach memory, and progress surfaces. The weakness is that these parts do not yet behave as one coach.

A mature product organization would not respond by adding more pages, detectors, or content. It would make one learning loop work exceptionally well:

> **Observe my real play → identify the most important behavior → explain it on my board → let me practise it → help me apply it → verify whether it changed in later games.**

That is the product. Game Review, Training, Coach Play, Openings, Endgames, Progress, notifications, and payment are delivery surfaces for that loop.

The strongest possible market position is no longer “personalized chess analysis.” Several current products already say that. ChessGuru's defendable position should be:

> **The chess coach that remembers how you think and proves that your habits are changing.**

The commercial verdict is **credible but unproven**. ₹1 crore ARR in 18 months is possible, but the present baseline—roughly 40 MAU and no validated recurring subscription revenue in the latest internal audit—makes it a product-and-distribution challenge, not merely an engineering milestone. The path requires a successful activation experience, measurable learning transfer, paid retention, and repeatable acquisition. Shipping more feature breadth without those proofs will not produce the target.

## What “Google or Microsoft would do” actually means

It does not mean making the UI look corporate or introducing more services. It means applying operating discipline:

1. **Start from a user outcome.** One company-wide definition of improvement, not separate success measures for every page.
2. **Reduce the product to a small number of journeys.** The user should not understand the internal architecture.
3. **Measure user experience and learning together.** Google’s HEART work maps goals to user-centered metrics; ChessGuru needs the same discipline, with learning transfer added.
4. **Create explicit quality contracts.** A detector, caption, lesson, and progress claim are not allowed to reach a player merely because they exist.
5. **Run a reliable platform.** User-centered SLIs/SLOs, idempotent jobs, tracing, failure recovery, cost visibility, and staged rollouts.
6. **Design trust in.** Explain what is observed, what is inferred, how confident the coach is, and what would count as improvement.
7. **Build inclusively and simply.** Board-first, keyboard accessible, mobile usable, readable at low chess literacy, and never dependent on jargon or color alone.
8. **Use experiments to answer uncertain business questions.** Price, free limits, intervention order, notification frequency, and plan length must be measured rather than selected by taste.

Google and Microsoft are not automatically right about product. Large organizations can overbuild too. The useful standard here is their discipline around evidence, reliability, accessibility, security, and staged delivery.

## Current-state assessment

These scores describe what a player receives today, not how much code exists.

| Dimension | Current assessment | Evidence and implication |
|---|---:|---|
| Product thesis | 8/10 | The “coach that remembers and improves the player” thesis is strong and specific. |
| Chess/data asset | 8/10 | Internal snapshots show roughly 14k games, 13k+ analyses, and over 420k move observations. This is a meaningful starting corpus. |
| Game-review rendering | 8/10 | A documented 120-game V5 render produced captions for all sampled blunders with no render failures. This is promising delivery quality, not proof of teaching quality. |
| Detector governance | 5/10 | Some detectors are strong; many do not yet have independent precision/recall evidence or player-facing authorization. Recent trap work also exposes data-integrity and role-parity issues. |
| Player diagnosis | 4/10 | An internal audit found highly repetitive top diagnoses and much more discriminating signals left unused. The system collects more individuality than it currently expresses. |
| Curriculum/teaching | 4/10 | Opening, trap, endgame, tactical, time, and thinking components exist, but they are not yet one adaptive curriculum with prerequisites and transfer checks. |
| Cross-surface personalization | 3/10 | Active focus does not reliably control review, training, coach play, and progress as one policy. |
| Customer journey | 3/10 | Existing launch work found severe diagnostic/onboarding abandonment and very low learner activation. |
| Frontend coherence | 4/10 | The router exposes 50+ routes and multiple overlapping ways to review, train, and play. The internal feature map leaks into the customer experience. |
| Backend coherence | 5/10 | There is substantial capability, but more than 250 top-level service files and duplicate/parallel coaching paths make consistency difficult. |
| Reliability and release confidence | 5/10 | Many tests exist, but CI and true routed journey coverage remain materially weaker than the code surface. |
| Trust and claim honesty | 6/10 | A claim-honesty model exists. It is not yet enforced everywhere a player sees “improved,” “fixed,” or “mastered.” |
| Monetization | 2/10 | Pricing UI exists, but the current Razorpay flow is a one-time order/verification prototype, not a complete recurring subscription lifecycle. |
| Distribution | 2/10 | There is no demonstrated repeatable acquisition channel or enough behavioral volume to establish paid funnel economics. |

The concise diagnosis is the one already visible in the internal launch report: **an approximately 8-quality coaching engine is sitting behind an approximately 4-quality front door.**

## The competitive reality in September 2026

ChessGuru should not copy a competitor wholesale. It should understand what each one has trained customers to expect.

| Product | What it owns | What ChessGuru must learn | Where ChessGuru can win |
|---|---|---|---|
| Chess.com | Playing network, breadth, polish, Game Review, retry, lessons, puzzles, Insights, Play Coach, personality/creator coaches | Immediate post-game gratification, excellent board interactions, familiar language, reliability, freemium packaging | Do not compete on breadth or playing liquidity. Connect isolated tools into a longitudinal coaching relationship. |
| Lichess | Free, fast, trusted, open chess utility | The baseline price of analysis, studies, puzzles, and play is effectively zero | Charge for guidance, memory, prioritization, and verified change—not engine access. |
| Chessly | Creator trust, engaging instruction, 70+ courses, simple learning experience, motivation systems | Teaching quality, delight, and distribution through a trusted human | Use the player's own games to choose and adapt instruction instead of presenting a broad course catalogue. |
| ChessDojo | Serious improvement plan, cohorts, accountability, community, coach credibility | People pay for structure and commitment, not only explanations | Deliver daily personal guidance at software scale, then selectively add human/community accountability. |
| DecodeChess | Rich natural-language position and game explanations; $8.25 monthly or $84 yearly | “Explain why” is already a paid category | Explain less but remember more; connect explanations to recurring behavior and later proof. |
| Chessigma | Own-game diagnosis, personalized daily plan, opening trainer, human-like bots; currently advertises $14 monthly/$97 yearly | The “one personalized kit from your games” promise is already explicit | Earn more trust through detector evidence, focus continuity, and honest transfer measurement. |
| Phiamos | Connect, diagnose patterns across games, produce a focused plan; advertises $4.99/month billed yearly | Even small entrants now use nearly the same top-line personalization language | Become a real teaching system rather than a report plus external resource links. |
| Chessy | Insights, puzzles from personal blunders, weekly AI report; advertises $7.99 monthly/$49.99 yearly | Personal puzzles and reports are becoming table stakes | Close the loop inside later play and show behavioral change, not merely generated material. |

### Competitive conclusion

“AI coach,” “your games,” “personalized plan,” “plain-English review,” and “puzzles from your mistakes” are becoming commodity claims. ChessGuru cannot win by saying them more loudly.

The scarce capability is a trustworthy longitudinal teaching policy:

- it chooses the right thing now;
- it relates today’s lesson to what happened in the player's games;
- it changes its intervention when the player succeeds or struggles;
- it recognizes the same idea across new positions;
- it remembers the player across sessions;
- it can show the evidence without overstating causality.

That is both the product moat and the technical architecture to build.

## The product contract

Every important experience should satisfy seven promises:

1. **You watched me.** The coach references real moves, time usage, positions, and repeated decisions.
2. **You know what matters.** It prioritizes impact, recurrence, readiness, and teachability rather than displaying every issue.
3. **You can explain chess.** It names the threat, square, piece, alternative, and principle in language suitable for the player.
4. **You can teach, not just report.** The player retrieves, predicts, compares, and plays—not only reads.
5. **You remember.** Review, Training, Coach Play, and the next visit share the same active focuses and history.
6. **You adapt.** Difficulty, detail, tone, intervention timing, and next steps change from observed behavior.
7. **You are honest.** The system separates observation, short-term evidence, promising change, durable resolution, and mastery.

If a feature does not strengthen one of these promises, it should be deferred.

## Who the first product is for

The launch wedge should be **existing 600–1500 online players with enough recent games to reveal patterns**. They feel the pain, supply immediate behavioral data, and can recognize a specific insight as valuable.

New players still need a supported journey, but the product must not pretend to know them before evidence exists. Their early experience is a starter coach that learns about them. It becomes truly personalized after observed decisions and games accumulate.

Do not split engineering into two independent products. Both journeys should converge on the same coaching loop and player model.

## Customer journey: existing player

### 1. Promise

The landing page should make one claim:

> Connect your games. Meet the mistake pattern costing you the most. Train it. See whether it disappears.

The page should show one realistic example from game to lesson to later proof. It should not lead with a feature grid.

### 2. Connect

Ask for Chess.com or Lichess identity with the minimum friction permitted by the platforms. Explain exactly what will be read and why. Do not ask the player to write a self-assessment.

Optional lightweight choices may be chips, not forms: improvement goal, usual time control, available session length, and whether feedback should be gentle or direct. Tone should continue adapting from observable context.

### 3. Analyse visibly

Show progress with useful work already available: games found, games analysed, and the first evidence card as soon as it is trustworthy. Background work must be resumable; leaving the page should not lose progress.

### 4. Deliver the “mirror moment”

The first value is not an accuracy number. It is a specific, defensible statement such as:

> In four recent rapid games, you moved before checking the opponent’s forcing reply. Here are the three positions where the same habit appeared.

Let the player replay those positions. Show the evidence. Avoid a generic personality label.

### 5. Assign a focus

The coach may select multiple active focuses, as required by the product vision, but only one should lead the current session. Other active focuses remain visible as secondary work. The coach does not need approval to detect a focus; the player can dismiss or challenge bad evidence.

### 6. Teach on the board

Use a short sequence:

- reconstruct what the player was likely considering;
- reveal the missed opponent resource;
- teach one reusable cue;
- test it in a near position;
- test it in a different-looking transfer position;
- state where it will appear next—in review, Coach Mode, or ordinary play.

### 7. Apply

Offer one primary next action: a short practice set, Coach Mode, or Play Mode. The coaching policy chooses it from readiness and evidence; the UI does not dump all options on the player.

### 8. Close the loop

When later games arrive, the coach looks for genuine opportunities to use the skill. It reports what happened and updates focus state. “No relevant opportunity yet” is better than a false claim of improvement.

### 9. Build the relationship

The next visit begins with continuity: what we were working on, what happened since, and what the coach recommends today. It should feel like returning to the same coach, not reopening a dashboard.

## Customer journey: new player

### 1. Welcome without a long diagnostic

Ask only what is necessary, using board interactions and a few choices. Let the player start immediately.

### 2. Establish a transparent baseline

Use a small adaptive set of board decisions or a Coach Mode game. Say “I’m learning how you play,” not “I found your biggest weakness.”

### 3. Teach universal high-value habits

Begin with board vision, piece safety, forcing moves, basic checkmates, opening principles, and time habits as demonstrated—not a large content menu. What appears depends on observed readiness.

### 4. Create early success

The coach should help the player notice and execute one idea, then recognize it when it reappears. Confidence is earned through a concrete board success, not confetti alone.

### 5. Personalize progressively

As evidence accumulates, generic starter work is replaced by personal focuses. The UI should visibly explain that transition: “I have enough games now to distinguish a one-off miss from a pattern.”

## Experience architecture

### Primary navigation

The customer-facing information architecture should be reduced to four primary destinations:

1. **Today** — the coach’s recommended session and continuity.
2. **Review** — recent games and the selected teaching moments.
3. **Play** — clearly separated Play Mode and Coach Mode.
4. **Progress** — evidence of behavior change, current focuses, and history.

Openings, endgames, traps, tactical motifs, and exercises remain available under **Explore**, but the normal journey enters them through a coach recommendation. This preserves player agency without turning ChessGuru into another library.

### One coach surface

The coach should have one stable visual identity, voice policy, and memory across the product. Page-specific components may render it, but they consume the same coaching decision and evidence contract.

### Game Review

Default review should be three chapters, not every move:

- what shaped the game;
- the most valuable decision to revisit;
- how it relates to an active focus and what to do next.

Allow full analysis as a secondary tool. Active focuses should be emphasized where relevant, not inserted where chess evidence does not support them. A missed trap can be surfaced as an opportunity only after soundness, role, reachability, and explanation checks pass.

### Play Mode and Coach Mode

- **Play Mode:** a normal opponent experience, minimally interrupted, analysed afterward.
- **Coach Mode:** an explicitly instructional game. The coach pauses selectively, asks prediction questions, highlights current focuses, and teaches naturally across multiple issues without hijacking every move.

The intervention budget is essential. A human coach notices many things but chooses when to speak.

### Training

Training is a prescribed session, not a catalogue. Each item says why it was selected and which game evidence it came from. Difficulty should follow demonstrated performance, not rating alone.

### Progress

Replace activity vanity metrics with evidence:

- how often the behavior appeared when the opportunity existed;
- performance before and after instruction;
- success in same-pattern practice;
- success in transfer positions;
- success in later games;
- confidence and sample sufficiency.

Rating remains useful but is a lagging, noisy result—not the proof behind every coaching claim.

### Frontend quality bar

- Board remains the visual center of teaching.
- One primary CTA per state.
- Mobile layouts are designed, not compressed desktop screens.
- Complete keyboard control and screen-reader labels.
- Do not communicate move quality with color alone.
- Plain-language copy for a 600-rated player, with optional deeper detail.
- Stable loading, empty, retry, offline, and partial-analysis states.
- Resume exactly where the player left.
- Fast perceived response through progressive rendering and cached facts.
- Instrument meaningful actions, not every click.

## The backend a serious product organization would build

### 1. Canonical coaching domain model

Create a versioned, auditable model around these entities:

- `Player`
- `Game`
- `MoveObservation`
- `ConceptEvidence`
- `Focus`
- `Intervention`
- `PracticeAttempt`
- `TransferOpportunity`
- `Outcome`
- `CoachMemory`

Each claim should be traceable to observations, detector version, analysis version, relevant FEN/move facts, and time. Event time and derivation time must be distinct types, not overloaded fields.

### 2. One skill graph

Tactics, calculation, positional play, openings, traps, endgames, and time management should live in one concept graph with:

- prerequisites;
- manifestations in games;
- valid detectors;
- teaching objectives;
- example and contrast positions;
- practice generators or curated positions;
- transfer criteria;
- age/rating/language-safe copy variants.

This is the single source of truth. Pages must not maintain independent lists of what ChessGuru teaches.

### 3. One coaching orchestrator

The orchestrator receives player state and context, then returns:

- what matters now;
- why it was selected;
- whether to speak;
- which intervention type to use;
- which evidence may be shown;
- what outcome to observe next.

Review, Today, Training, Coach Play, notifications, and Progress consume this policy rather than implementing their own recommendation logic.

### 4. Separate chess truth from language

Stockfish, legal-move generation, tablebases, opening/trap data, and verified deterministic facts decide chess truth. An LLM may control expression, summaries, conversational follow-ups, and tone only within supplied facts. It must not invent attacks, squares, material, legal lines, or improvement claims.

This is especially important commercially: generated eloquence without board truth destroys coach trust faster than plain deterministic language.

### 5. Detector authorization pipeline

Every detector progresses through explicit states:

1. Research
2. Shadow
3. Caption-authorized
4. Focus/plan-authorized
5. Transfer-authorized

Promotion requires a versioned gold set, stratified precision/recall, hard negatives, role correctness, legal lines, board-verifier coverage, and review by a qualified chess owner. A single quality score is not enough; a detector can be safe for a caption and unsafe for prescribing a long-term focus.

### 6. Reliable asynchronous analysis

Game ingestion and analysis should be idempotent and resumable, with:

- explicit job states;
- bounded retries and dead-letter handling;
- deduplication keys;
- per-stage timings;
- dependency timeouts;
- backpressure and concurrency limits;
- partial results that never masquerade as complete;
- cached engine facts keyed by position and analysis configuration.

### 7. Observability and cost

Trace one game from import through analysis, coaching decision, rendered message, practice, and later outcome. For every player-visible statement, support staff should be able to answer “why did the system say this?”

Track compute cost per imported game, reviewed game, coached game, activated user, and paid retained user. Keep deterministic logic central and use LLM calls only where their added teaching or relational value is measurable.

### 8. Privacy and security

- Explicit consent for connected accounts and imported history.
- Export and deletion that remove derived profiles as well as raw games.
- Retention policy for PGNs, analysis, telemetry, and model-evaluation samples.
- Separation of product data from research/gold corpora.
- Secrets management, dependency scanning, rate limiting, audit logging, and least privilege.
- Clear disclosure when language is AI-generated and when a claim is uncertain.

### 9. Test and release system

The minimum release pyramid is:

- deterministic unit tests for chess facts and state transitions;
- service-contract tests for each coaching payload;
- integration tests with Mongo, Stockfish, queues, and billing sandbox;
- routed browser tests for both customer journeys;
- golden visual tests for board orientation and highlights;
- production shadow evaluation for detectors;
- staged rollout with rollback and version compatibility.

Repository size is not quality. The critical metric is whether the few customer journeys can ship repeatedly without regressions.

## Learning system, not content library

Research on learning supports the product direction but also raises the bar. Practice testing and distributed practice have broad evidence, and intelligent tutoring systems can improve outcomes when they actually model the learner and adapt instruction. A recent large longitudinal chess study also reported deliberate-practice-aligned activity as substantially more learning-efficient than gameplay alone.

ChessGuru should therefore use this sequence:

1. **Diagnose from authentic play.**
2. **Elicit the player's thought, where useful, with a choice or board action rather than mandatory prose.**
3. **Explain the causal chess reason.**
4. **Ask for retrieval, not rereading.**
5. **Provide immediate factual feedback.**
6. **Repeat after spacing.**
7. **Interleave related and contrasting positions.**
8. **Test transfer in a new-looking position.**
9. **Observe the behavior in later games.**
10. **Retire, maintain, or reopen the focus based on evidence.**

Openings should teach plans, pawn breaks, piece placement, opponent ideas, traps, refutations, and resulting middlegames—not merely lines. Endgames should teach recognition, plan selection, execution, and conversion under realistic time. Tactical concepts should include both successful use and opponent threats. Positional concepts need verified counterfactuals and should arrive later than high-confidence tactical facts unless evidence is strong.

## Company metrics

### North-star outcome

Use **Verified Focus Transfer**:

> The share of eligible active focuses for which a player demonstrates the target behavior in later, genuinely relevant game opportunities, with sufficient evidence and an honest confidence state.

This is intentionally harder than counting analyses, puzzles, sessions, or rating points. It is the closest product metric to the promise of a coach.

### Metric tree

**Acquisition**

- qualified visitors;
- connected accounts;
- acquisition source and cost;
- share with sufficient game history.

**Activation**

- time to first credible personal insight;
- percentage who inspect its board evidence;
- percentage who begin and finish the first intervention;
- percentage who select the recommended next action.

**Learning**

- detector confidence and precision;
- retrieval success;
- delayed retention;
- near and far transfer;
- later-game behavior when an opportunity occurs;
- focus state transitions and reversals.

**Relationship**

- return after a new game;
- weekly coached loops completed;
- coach helpfulness and trust;
- dismissed/challenged insights;
- continuity recognition.

**Revenue**

- free-to-trial and free-to-paid conversion;
- trial completion;
- renewal and cancellation;
- retained net revenue by cohort;
- refunds and payment failures;
- gross margin and compute per retained payer.

**Guardrails**

- false chess claims;
- wrong-side or illegal-line incidents;
- latency and analysis failures;
- notification complaints;
- privacy/deletion failures;
- harmful or discouraging tone reports.

Numeric funnel, quality, SLO, and price targets should not be locked from this report. The repository's `lock-via-data` rule is correct: establish baselines and distributions, then lock values at observed cliffs or through controlled tests.

## Revenue model

### What the customer pays for

Not Stockfish. Not a puzzle database. Not generic explanations.

The paid value is:

- continuous analysis across the player's games;
- persistent coach memory;
- prioritization of what to learn now;
- personalized instruction and practice;
- Coach Mode interventions;
- longitudinal evidence of change;
- saved time and reduced confusion.

### Packaging

Launch with one free plan and one paid plan. Do not introduce three weakly differentiated tiers before willingness to pay is known.

**Free — prove the coach is real**

- connect an account and receive a genuine initial diagnosis;
- limited recurring reviews;
- one leading active focus;
- a small personal practice allowance;
- visible progress evidence;
- enough repeat value to establish trust.

**Coach Pro — run the complete loop continuously**

- continuous sync/analysis within fair-use limits;
- full personalized review and training;
- multiple active focuses with one session priority;
- Coach Mode;
- spaced review and transfer tracking;
- deeper coach memory and progress history.

Avoid “unlimited” promises until unit economics and abuse patterns are measured. Communicate generous fair use in player language.

**Academy/coach product — later, not now**

After the consumer loop is proven, let human coaches use ChessGuru as a between-lessons assistant: cohort progress, evidence review, focus assignment/override, homework, and alerts. This can improve distribution and revenue, but building it before consumer learning proof would split the team.

### Pricing approach

Current public competitors span roughly $50–$120 per year for software-led improvement products, with premium guided or human-supported programs much higher. ChessGuru should run localized willingness-to-pay tests rather than copy one price.

Candidate tests—not decisions—could compare:

- a lower-friction India annual plan;
- a stronger-value India annual plan with Coach Mode;
- a global annual plan positioned below a single human lesson per month;
- monthly versus annual framing;
- trial with and without payment method;
- a limited free diagnosis versus a short full-coach trial.

The existing ₹149 one-time Razorpay order path is not proof of a viable subscription. Before charging recurring revenue, implement subscriptions, entitlements, renewals, cancellation, grace periods, failed-payment recovery, refunds, webhooks, invoices/tax handling, and customer support visibility.

### ₹1 crore ARR arithmetic

₹1 crore ARR equals ₹10,000,000 in annualized recurring revenue, excluding tax. The subscriber requirement depends on net annual revenue per paid account:

| Net annual revenue per paid account | Paid accounts required |
|---:|---:|
| ₹3,000 | 3,334 |
| ₹4,000 | 2,500 |
| ₹5,000 | 2,000 |
| ₹6,000 | 1,667 |

For illustration, a customer price of ₹3,999/year inclusive of 18% GST produces about ₹3,389 before payment fees, requiring roughly 2,951 equivalent annual subscribers for ₹1 crore ARR. This is arithmetic, not the recommended price.

The credible route is likely a mix of India and global consumer revenue, followed by academy distribution only after the loop works. A consumer-only path is possible but demands thousands of retained payers and therefore a much larger activated audience than ChessGuru has today.

### Commercial gates

Do not forecast ARR from signups. Unlock investment in sequence:

1. People consistently reach a credible personal insight.
2. They complete a full coaching loop.
3. Their target behavior improves in later opportunities.
4. They return when new games arrive.
5. A meaningful segment pays for continuation.
6. Paid cohorts renew after the novelty period.
7. Acquisition channels recover their cost within the business's chosen payback window.

If any gate fails, solve that gate before scaling traffic.

## Go-to-market

### Positioning

Avoid “all-in-one chess improvement.” It is broad, unprovable, and dominated by larger platforms.

Use a narrower story:

> You already play enough chess. ChessGuru finds the recurring decision behind your losses, coaches it using your positions, and checks your next games to see whether it changed.

### Acquisition loops

1. **Shareable coach insight:** a privacy-safe “pattern card” with real evidence and a useful takeaway.
2. **Post-game ritual:** browser/mobile reminders after new imported games, only when analysis is ready and valuable.
3. **Creator demonstrations:** strong players/coaches review whether ChessGuru’s diagnosis of real subscribers is correct; credibility matters more than sponsorship reach.
4. **Improvement challenges:** a bounded focus challenge with before/after opportunity evidence—not promises of rating gains.
5. **Coach/academy pilots:** later, let coaches validate recommendations and use the product between sessions.
6. **Search content:** answer specific pain (“why do I keep hanging pieces in rapid?”), then demonstrate the closed loop rather than publish generic chess articles.

### Retention loop

New games are the natural trigger. Each sync can produce new evidence, confirm progress, or adjust the plan. Notifications should fire only when the coach has something specific to say. Artificial streak pressure should never outrank learning value.

## Operating model

A serious but small team does not need big-company headcount. It needs clear ownership.

### Four accountable functions

- **Product/learning:** owns the coaching contract, journeys, research, and north-star metric.
- **Chess quality/data:** owns concept truth, detector authorization, gold sets, and claims.
- **Experience engineering:** owns the board-first web/mobile journey, accessibility, and analytics.
- **Platform/growth:** owns ingestion, reliability, billing, experimentation, cost, and lifecycle communication.

A titled coach or demonstrably qualified chess educator should be a recurring product-quality owner, not an occasional content reviewer.

### Weekly cadence

- Watch real onboarding and coaching sessions.
- Review false claims and challenged insights.
- Inspect one end-to-end funnel and one learning cohort.
- Review reliability and compute cost.
- Decide what to stop as well as what to build.
- Ship behind flags; compare versions; document reversals.

## 18-month execution blueprint

### Phase 0: establish truth — now to 2 weeks

- Freeze net-new customer-facing breadth except correctness fixes.
- Baseline the two journeys from landing through first value.
- Establish event definitions and data-quality checks.
- Audit every routed surface and choose keep, merge, redirect, or retire.
- Define the canonical coaching payload and claim levels.
- Complete the billing-gap inventory and unit-cost instrumentation.
- Conduct observed sessions with existing and new players.

**Exit:** the team can replay a user session, explain every coaching decision, and quantify where the journey fails.

### Phase 1: repair the front door — weeks 3–6

- Replace long onboarding with connect-or-play paths.
- Deliver the first evidence-backed mirror moment rapidly and progressively.
- Consolidate navigation around Today, Review, Play, and Progress.
- Add resume, retry, empty, and partial-analysis states.
- Cover both primary journeys with routed browser tests.
- Instrument the complete first-session funnel.

**Exit:** users consistently reach and understand the first personal value without founder assistance.

### Phase 2: prove one complete coaching loop — weeks 7–12

- Make active focus the shared control plane across Review, Training, Coach Mode, and Progress.
- Choose the best-supported concept family from production evidence; do not pick it from intuition.
- Implement retrieval, spacing, transfer opportunities, and later-game observation.
- Enforce observation/promising/resolved/mastery language.
- Validate detector, teaching, and transfer precision independently.

**Exit:** a real cohort can move from diagnosis through later-game evidence with auditable, trustworthy claims.

### Phase 3: monetize the working loop — months 4–6

- Implement real recurring billing and entitlements.
- Test one paid plan, localized presentation, trial structure, and free limits.
- Instrument cancellation reasons, refunds, payment failure, support, and gross margin.
- Sell continuation of proven value, not locked feature boxes.

**Exit:** at least one paid cohort renews because the coach remains useful after the initial report.

### Phase 4: expand deliberately — months 7–12

- Add concept families only through the detector/teaching authorization pipeline.
- Build the canonical opening, trap, middlegame, time, and endgame graph.
- Expand Coach Mode intervention types under a speech budget.
- Develop creator and challenge acquisition loops.
- Begin coach/academy pilots without forking the learning engine.

**Exit:** multiple concepts complete the same proven loop and at least one acquisition channel is repeatable.

### Phase 5: scale toward the ARR target — months 13–18

- Improve conversion and retention from cohort evidence.
- Localize price, copy, payments, and support where economics justify it.
- Add academy administration only when pilots demonstrate pull.
- Harden SLOs, incident response, data lifecycle, fraud/abuse controls, and capacity planning.
- Scale acquisition only when paid retention and unit economics survive larger cohorts.

**Exit:** the business has enough retained paid accounts at measured net ARPA to support ₹1 crore annualized recurring revenue—not merely an optimistic run-rate from trials.

## What to stop, merge, and defer

### Stop

- Treating every detector or lesson as a feature launch.
- Calling one correct puzzle or one clean game “fixed.”
- Adding generic dashboards before the main journey works.
- Allowing page-specific recommendation logic.
- Using LLM prose as chess evidence.
- Counting route count, test count, or content count as player value.

### Merge

- Overlapping home/coach/dashboard concepts into Today.
- Parallel game-review implementations behind one canonical review contract.
- Training pages behind one prescribed-session model.
- Opening/trap recognizers and data into one curriculum source.
- Coach personalities into presentation variants over one evidence-backed coach brain.

### Defer

- Large social systems and leaderboards.
- Broad academy administration.
- More gamification than is needed to sustain deliberate practice.
- Advanced concepts without reliable detection and teaching evidence.
- Voice/avatar novelty unless it improves comprehension or retention.
- Native mobile apps until the responsive core journey proves demand, unless current usage data shows mobile web is the dominant blocker.

## Board-level risks

| Risk | Why it matters | Mitigation |
|---|---|---|
| False personalization | Generic labels dressed in personal language destroy trust | Evidence cards, discriminating diagnosis, uncertainty, challenge flow |
| Correct engine, wrong teaching | Best move alone does not explain the player's misconception | Board facts + misconception model + retrieval/transfer design |
| Feature sprawl | Users cannot find the coaching loop; engineers duplicate policy | Four-destination IA and one orchestrator |
| Detector false positives | A wrong coach is worse than no coach | Authorization stages, gold sets, hard negatives, shadow rollout |
| LLM hallucination | Natural language can assert impossible chess | Deterministic fact slots, board verifier, constrained generation |
| Improvement theater | Activity and short streaks are presented as learning | Opportunity-based later-game measurement and claim levels |
| Cold start | New players have too little history for personal claims | Transparent starter curriculum that learns progressively |
| Weak distribution | Good product cannot reach ARR without an audience | Creator proof, shareable insight, challenges, academy pilots |
| Subscription leakage | One-time payment logic cannot support ARR operations | Full recurring lifecycle and entitlement source of truth |
| Compute economics | Deep analysis and LLM use can erase margin | Cost tracing, caching, staged depth, fair use |

## The decisions I would make now

1. **Keep the product direction.** Do not pivot to a course library or another engine UI.
2. **Make existing online players the initial acquisition wedge.** Preserve a transparent starter journey for new players.
3. **Adopt Verified Focus Transfer as the north-star outcome.** Rating remains a secondary business/user result.
4. **Turn active focus into the shared control plane.** Multiple focuses are allowed; one leads each session.
5. **Collapse the frontend into one coach journey with four primary destinations.**
6. **Use deterministic chess truth and constrained AI language.** Personalization does not require an LLM at its core.
7. **Stop expanding concept breadth until one concept completes the whole loop.** Select that concept from production evidence.
8. **Do not enable recurring Pro until billing and entitlement lifecycle are real.**
9. **Test one paid plan, not a tier maze.** Treat price values as hypotheses pending observed willingness and retention.
10. **Manage the next 18 months by gates, not feature dates.** Activation, transfer, renewal, and acquisition economics decide when to scale.

## Final answer

If Google or Microsoft-level product discipline were applied here, ChessGuru would probably have fewer visible features in the next release, not more. It would feel substantially more capable because every screen would remember the same player, pursue the same focuses, use the same chess truth, and lead to the next best action.

The opportunity is real, but the language of the market has caught up. Competitors can now say “personalized plan from your games.” ChessGuru must be the product that can demonstrate: **I noticed this habit, I taught you differently because of it, you used the lesson later, and here is the honest evidence.**

That is strong enough to support a company. It is also a much narrower and more demanding build than the current route and service count suggests.

## Sources

Repository evidence:

- `docs/REVIEW_BRIEF.md`
- `docs/launch_readiness_report.md`
- `docs/chessguru_definitive_product_coaching_audit_2026_08_28.md`
- `docs/product_thesis_audit_production_data_addendum_2026_08_13.md`
- `docs/product_claim_honesty_register.md`
- `docs/guided_chess_curriculum_scope.md`
- `frontend/src/App.js`
- `frontend/src/pages/Pricing.jsx`
- `backend/routes/billing.py`

External evidence, accessed 2026-09-04:

- Google Research, [HEART user-centered metrics](https://research.google/pubs/measuring-the-user-experience-on-a-large-scale-user-centered-metrics-for-web-applications/)
- Google SRE, [Service Level Objectives](https://sre.google/sre-book/service-level-objectives/)
- Microsoft, [Designing inclusive software](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/designing-inclusive-software)
- Microsoft, [Responsible AI principles and standard](https://support.microsoft.com/en-US/Privacy/what-is-responsible-ai)
- Chess.com, [current membership offering](https://www.chess.com/membership)
- Chess.com Help, [Game Review](https://support.chess.com/en/articles/8584089-how-does-game-review-work)
- Chess.com Help, [Play Coach](https://support.chess.com/en/articles/10877257-how-do-i-play-against-the-coach)
- Lichess, [free-for-everyone patron model](https://lichess.org/patron)
- Chessly, [product and course offering](https://chessly.com/)
- ChessDojo, [training program and pricing](https://www.chessdojo.club/prices)
- DecodeChess, [features and pricing](https://decodechess.com/pricing-plans/)
- Chessigma, [Supercoach and pricing](https://www.chessigma.com/supercoach)
- Phiamos, [personal coach and pricing](https://phiamos.com/)
- Chessy, [personalized training and pricing](https://chessyapp.com/)
- Dunlosky et al., [effective learning techniques](https://www.psychologicalscience.org/journals/pspi/1529100612453266/)
- Ma et al., [intelligent tutoring systems meta-analysis](https://doi.org/10.1037/a0037123)
- Southwick et al., [longitudinal evidence from chess practice](https://www.psychologicalscience.org/journals/psychological-science/09567976261452568/)
