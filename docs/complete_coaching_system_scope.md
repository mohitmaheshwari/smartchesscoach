# Complete Coaching System — Scope

**Status:** LOCKED — MOHIT APPROVED 2026-08-28
**Product owner and primary chess adjudicator:** Mohit, 2100 Elo  
**Decision already confirmed:** extend the existing product, consolidate or replace duplicate authorities, and validate with an isolated database rather than altering real player records

## 0. Existing surfaces audit

### What already serves this user need

| Existing surface or authority | What it already provides to the player | Decision |
|---|---|---|
| Onboarding, Welcome and account linking | Creates the account, asks for limited player information, connects Chess.com/Lichess and starts the first-data journey | **EXTEND.** Make this the reliable entrance for new players; do not create another intake flow. |
| Home (`/home`) | Coach message, current focus material, recent game, patterns, strengths and possible next actions | **EXTEND.** Home becomes the coach's single conversation and one recommended next action. |
| Game Review (`/game/:gameId`, `LabV2` -> `GameDecryptionV5`) | Board-based move review, opening information, tactical and strategic explanations, key moments and retry/teaching material | **EXTEND.** Keep the complete review, but make it read the same active coaching context as every other surface. |
| Training (`/training/*`, prescribed training, Daily Fix, skills, motifs, openings and PIC lessons) | Own-game positions, community positions, pattern practice, opening work, tactical drills and several lesson renderers | **CONSOLIDATE.** Keep useful exercises, but give them one assignment contract, one attempt record and one progress interpretation. |
| Play with Coach (`/play-with-coach`) | Play and Coach modes, engine opponent, move feedback, guardian behavior, opening guidance, trap suggestions, lessons and postgame analysis | **EXTEND AND SIMPLIFY.** Keep the surface; replace competing coaching decisions with one conductor and one intervention budget. |
| Progress (`/progress` and related progress cards/services) | Ratings, patterns, skill/mastery claims, historical trends and coaching narratives from several sources | **CONSOLIDATE.** Keep one learner-facing progress story and retire competing progress calculations after migration. |
| `user_active_focus` | Historical and active weakness/strength focus records; newer records can carry stable instruction fields | **EXTEND.** It remains the focus authority and gains an explicit primary/supporting/requested/maintenance hierarchy. |
| `focus_bridge` and `focus_resolver` | Partially shared focus reads, with legacy fallback behavior | **CONSOLIDATE.** `focus_bridge` becomes the sole reader; other readers become adapters and then retire. |
| `concept_mastery_service` plus legacy progress systems | A candidate learner-facing mastery projection alongside many older mastery, decay, mission and journey calculations | **CONSOLIDATE.** `concept_mastery_service` becomes the sole player-facing interpretation; evidence producers retain their own facts. |
| `teaching_engine`, RepRunner/PIC lessons and older teaching integrations | Trap, opening, endgame and piece-safety lesson lifecycles plus several parallel interaction shapes | **CONSOLIDATE.** `teaching_engine` owns lifecycle; one board-first lesson contract supports every teaching method. |
| Detector families and `detector_quality` | Broad tactical, positional, behavioral, opening and endgame recognizers, with one quality authority controlling Plan/Caption/Shadow/Disabled status | **EXTEND THE AUTHORITY; CONSOLIDATE DUPLICATE FACTS.** No detector influences a player beyond the surface it has earned. |
| Opening, trap and endgame curricula | 79 top-level opening entries, approximately 54 traps and 18 routed endgame lessons, plus recognizers and mastery services | **CURATE AND CONNECT.** Preserve the content, but let the coach sequence it instead of presenting it as the product. |

### Overlap and genuine differentiation

The existing product already contains nearly every visible component needed by a complete coach. The missing value is not another page. It is the shared relationship between the pages: one understanding of the player, one ordered focus set, one teaching history, one definition of improvement and one coach policy.

The genuine new product is therefore the **complete coaching system**, not a new “AI Coach” surface. It connects and governs the existing surfaces so they behave like one coach across months.

### Overlap decision

**EXTEND the five main player surfaces. CONSOLIDATE or REPLACE the duplicate authorities behind them. Do not create a parallel coach, focus store, lesson store, progress engine, caption path or player dashboard.**

Home remains the conversation, Review the evidence, Training the assigned work, Play with Coach the assisted application, and Progress the proof. Old routes and services are retired only after their replacement has passed contract comparison and rollout.

## 1. What it is

The Complete Coaching System turns ChessGuru into a persistent personal chess coach for 600–1500 players. It studies the player's games across fundamentals, tactics, thinking, positional play, time management, openings, traps, endgames, conversion and defense; identifies what matters at the player's current stage; keeps a clear set of active and requested learning goals; teaches with the right board-based activity; remembers what has already been tried; and checks later unassisted games before saying that the player improved. It can discuss several important issues in a game, while still guiding the player toward a manageable next action instead of becoming a library of unlimited choices.

## 2. What the user sees

### New player with enough connected games

```text
Welcome to ChessGuru

Connect the games you already play.
[ Chess.com ]  [ Lichess ]  [ Import a PGN ]

How would you like me to coach?
( ) Calm and encouraging
( ) Direct and practical
( ) Adjust to the moment

[ Study my games ]
```

The coach analyzes the available history and then leads with a conversation, not a dashboard:

```text
I've studied 42 of your recent rapid games.

You already do something valuable:
When your opponent's king is exposed, you usually find attacking ideas.

The biggest thing holding you back right now:
After choosing your own plan, you sometimes stop checking what your
opponent can do immediately. I found this in 8 comparable decisions.

PRIMARY FOCUS
Before committing to your move, check their checks, captures and threats.

I will also watch:
• how you use time in critical positions
• the Italian structures you reach often

[ Show me the evidence ]  [ Start my first lesson ]
```

If the evidence is not sufficient:

```text
I'm still learning your chess.

I can see a possible threat-awareness pattern, but I do not have enough
comparable decisions to make it your plan yet.

[ Play a normal game ]  [ Play with Coach ]  [ Try a short diagnostic ]
```

### New player without game history

```text
I need to see how you make decisions before I build your plan.

Choose the easiest way to begin:
[ Play a game ]  [ Short chess diagnostic ]  [ Connect games later ]

For now I'll teach at your rating level and say clearly when advice is
general rather than personal.
```

### Existing ChessGuru player

The player does not repeat onboarding:

```text
Your coach has been updated

I rebuilt your plan from 186 games and preserved your completed work.

What I still believe:
You create good attacking chances.

What changed:
Time use in critical positions now looks more important than your old
generic "piece safety" label.

[ Review my updated plan ]
```

If old evidence cannot be migrated honestly:

```text
I kept your lesson and attempt history, but I cannot verify the old
"improved" label with the new evidence rules. I will watch the next
few comparable decisions before making a new claim.
```

### Home — the coach's conversation

```text
Good to see you, Mohit.

TODAY'S FOCUS
Before committing, check their checks, captures and threats.

Your last game has two moments worth reviewing. One shows the old habit;
the other shows you catching the threat correctly.

[ Review those 2 moments ]

Also active
• Critical-position time use — watching
• Italian Game plans — requested lesson, ready after today's review
```

Home presents one recommended action. Supporting and requested subjects remain visible without creating competing primary buttons.

### Complete Game Review

```text
Game Review

Coach's view
You handled your main focus on moves 12 and 19. On move 24, you committed
to an attack before checking ...Qh2+.

OPENING
Your Italian setup was sound. The important idea was preparing c3 and d4,
not memorizing another move.

KEY MOMENTS
  ✓ Move 12 — you noticed the threat before continuing your plan
  ! Move 24 — PRIMARY FOCUS: check their forcing moves first
  ! Move 31 — a separate fork pattern worth learning
  ✓ Move 42 — patient rook activity in the endgame

[ Replay move 24 ]  [ Learn the fork ]  [ Continue review ]
```

Review explains the whole game: good decisions, tactical errors, positional plans, time use, opening ideas, endgame decisions and missed opponent opportunities. Active-focus moments are emphasized, but the coach does not suppress important unrelated lessons.

### Teaching and practice

The coach chooses among different teaching acts rather than presenting every activity as the same puzzle:

```text
Your focus: check their forcing moves before committing.

Position from your game — move 24

What can Black do immediately?
[ Tap a checking move on the board ]

Need help?
[ Show attacked squares ]  [ Give me one hint ]
```

```text
Two plans look reasonable here.

A. Push the kingside pawns
B. Double rooks on the open c-file

Choose one, then tell me what the opponent is trying to do.
[ A ]  [ B ]
```

```text
Italian Game: the idea behind c3

You asked to learn this opening. Your main focus remains threat awareness,
so I will teach the plan without giving you a second competing program.

[ Play the position ]
```

Lessons may use prediction, comparison, replay, calculation, recognition, execution, resistance play or direct explanation. Assistance is recorded so hinted success cannot masquerade as independent skill.

### Play Mode and Coach Mode

```text
How do you want to play?

[ PLAY MODE ]
A normal opponent. No live help. We review the game afterward.

[ COACH MODE ]
I will pause at selected teaching moments, especially when your active
focus is relevant. I will not interrupt every imperfect move.
```

During Coach Mode:

```text
Pause here — your main focus is active.

You found an attacking idea. Before committing, what forcing reply does
Black have?

[ Let me think ]  [ One hint ]
```

At another important moment the coach may teach a fork, opening idea, positional plan or endgame rule even when it is not the primary focus. It explains why the moment matters and does not silently replace the improvement plan.

### Progress and transfer

```text
Threat awareness

Practice: 7 of 9 without a hint
Unassisted checkpoint: passed
Later games: 9 of 12 comparable decisions handled

COACH VERDICT
Getting more reliable — keep this as a supporting focus while we begin
critical-position time use.

Evidence
[ View the 12 real-game decisions ]
```

If no genuine opportunity occurred:

```text
Not enough evidence yet

You completed practice, but your last three games contained only one
comparable decision. I will not call this improved yet.
```

If training did not transfer:

```text
You can solve this when the task points to it, but it is still being missed
inside real games. I am changing the lesson from explanation to recognition
practice and keeping the focus active.
```

### Long-term coach conversation

```text
This month

Improved
• You now catch immediate threats more consistently
• Your Italian positions reach playable middlegames more often

Still inconsistent
• You spend too much time on routine opening moves, then rush critical ones

New lesson
• Rook activity is now relevant because your recent games are reaching more
  rook endings

[ Start the next coaching block ]
```

## 3. In scope (V1)

- One continuous coaching journey for both new and existing players: observe, diagnose, prioritize, teach, rehearse, test, observe later games, issue an honest verdict and adapt.
- Reliable entry through the existing Welcome/Onboarding/account-link/import path, including honest insufficient-data and recovery states.
- A shared coaching context consumed by Home, Game Review, Training, Play with Coach and Progress.
- An explicit ordered focus model supporting a primary focus, a bounded set of supporting focuses, player-requested learning and maintenance of previously improved concepts.
- The ability for Game Review to discuss every important part of the game while visibly emphasizing active-focus and improvement-plan moments.
- One canonical lesson lifecycle and attempt record supporting direct explanation, prediction, comparison, replay, calculation, recognition, execution, resistance play and opening/endgame walkthroughs.
- Separate Play Mode and Coach Mode behavior, with Coach Mode using selected interventions and Play Mode remaining unassisted evidence.
- One coach conductor governing when to speak, when to stay silent, which focus is relevant, which teaching method to use, how much assistance to offer and how tone changes from observable context.
- Coach continuity: the same focus, instruction, evidence and unfinished commitment survive across surfaces and sessions.
- Player-requested openings, traps, endgames or other subjects enter the guided plan without silently replacing the coach-selected priority.
- A canonical concept registry covering fundamentals, tactics, calculation/thinking, positional play, time management, openings, traps, endgames, conversion, defense and practical decision-making.
- Every registered concept declares whether it may support a caption, become a plan, provide curriculum only, or remain research-only.
- Every concept capable of becoming a focus declares a detection opportunity, safe explanation, teaching methods, unassisted checkpoint and later-game transfer fact.
- Shared-machinery contract fixtures for all registered concept families, including first occurrence, recurrence, assisted success, unassisted failure, improvement, no opportunity, regression, conflicting focuses and user-requested learning.
- Detector authorization remains fail-closed: unapproved concepts may be researched but cannot determine a plan, mastery claim or unsupported coaching statement.
- Complete concept-data programs:
  - fundamentals: piece safety, defender/attacker awareness, immediate threats, development and king safety;
  - tactics: forks, pins, skewers, discoveries, overloads, deflections, removal of defenders, trapped pieces, back-rank and mating patterns;
  - thinking: candidate moves, forcing-move scan, calculation, visualization, comparison and evaluation;
  - positional play: activity, coordination, weak squares, outposts, pawn structures, files, space, exchanges, plans and prophylaxis;
  - time management: impulse, critical-position allocation, routine-move overspending and time-pressure performance;
  - openings and traps: recognition, ideas, recurring deviations, requested repertoire learning, transpositions, plans and tactical warnings;
  - endgames: king activity, basic mates, pawn races, opposition, passed pawns, rook endings, conversion and defense;
  - practical play: opponent-error recognition, advantage conversion, resourcefulness, defense and post-mistake recovery.
- Curated stage and prerequisite guidance so the coach can decide what a player is ready to use without exposing an unlimited curriculum menu.
- One learner-facing progress interpretation based on evidence, with only `improved`, `still recurring` and `insufficient evidence`-style outcomes until a stronger claim earns its own proof contract.
- Strict separation of assisted practice, unassisted checkpoints, Coach Mode, Play Mode and ordinary external games in progress evidence.
- Migration of existing players that preserves legitimate games, attempts, preferences and evidence while withdrawing legacy claims that cannot be reproduced.
- An isolated validation database on the production Mongo server, populated with anonymized referentially consistent production samples, synthetic player histories, detector gold, generated endgames and adversarial cases.
- Mohit as primary chess and pedagogy adjudicator, with engine/legal replay for objective tactics and tablebases for theoretical endgames; unresolved specialist cases may seek an additional reviewer.
- Product analytics for new-player activation, existing-player migration, first completed lesson, next-game return, transfer verdict, second coaching cycle and later paid conversion.
- Default-off, reviewer-first rollout with preserved evidence and a reversible reader/UI flag.

## 4. Explicitly out of scope (V1)

- A new top-level AI Coach page or a second player dashboard.
- A second focus store, progress engine, teaching engine, caption pipeline, opening source or concept taxonomy.
- Allowing every detector to become a player focus merely because it exists or fires frequently.
- Claiming that all 116 current detector IDs are separate teachable skills; duplicate facts must consolidate and internal facts may remain invisible.
- Mutating real player history, timestamps, attempts, focus records, mastery or payments to manufacture validation scenarios.
- Letting an LLM decide chess truth, player psychology, focus priority, mastery, progress or the next curriculum stage.
- Unlimited live hints, unrestricted move reveal or commentary after every ordinary move.
- A fixed syllabus that forces every player through openings, tactics and endgames in the same order.
- Hiding important game-review lessons because they do not match the primary focus.
- Treating lesson completion, hinted puzzle success, rating fluctuation or game results alone as proof of improvement.
- Public claims that ChessGuru caused Elo improvement without a separate appropriately designed outcome study.
- A course marketplace, creator-content marketplace or restoration of the entire content catalog as the Home experience.
- Native mobile applications solely for feature parity; responsive web quality remains required.
- Social leagues, leaderboards, badges or streak economies unrelated to the coaching relationship.
- A general-purpose unlimited chat coach in V1. Bounded questions about a reviewed position may use the verified coaching context.
- Academy management, coach dashboards or a separate B2B product. Coaches may participate as reviewers/distribution partners without creating another product line.
- Multilingual coaching before the English coaching truth, continuity and learning loop pass their release gates.
- Broad paid acquisition or a guaranteed ₹1 crore ARR claim before activation, retention, renewal and channel economics exist.

## 5. Success criteria

- A new eligible player can connect or import games, receive one evidence-backed coach conversation, inspect its proof and complete the assigned first teaching activity without manual rescue or navigating unrelated pages.
- A new player without sufficient history receives honest general guidance and a bounded path to create evidence; no personal diagnosis is invented.
- An existing player is migrated without repeating onboarding, losing legitimate history or retaining an improvement claim that the new evidence rules cannot reproduce.
- Home, Review, Training, Play with Coach and Progress display the same immutable instruction for the same focus; any instruction-ID/text mismatch is release-blocking.
- Game Review covers the important chess story of the game and emphasizes verified active-focus moments without forcing unrelated moves into the focus.
- Every registered concept family passes the same lifecycle fixtures from opportunity through teaching, checkpoint and later-game verdict, even when a concept remains Shadow and is tested only in validation.
- Every player-facing Plan concept meets the locked Plan-grade detector bar; every player-facing deterministic explanation meets the applicable Caption-grade bar; zero known critical false claims are allowed through the registered adversarial packets.
- Assisted practice cannot resolve a focus. A no-opportunity game cannot count as clean evidence. Missing event time cannot be silently placed into a before/after window.
- Chronic, learner, clean, sparse, no-opportunity, regressing, sacrifice, missing-clock, requested-topic and legacy-migration synthetic players receive the expected coaching state across every applicable concept family.
- When a player repeatedly fails after one teaching method, the coach can select a different registered method and retain that intervention history.
- Coach Mode respects the active focus and an intervention budget while still teaching other important verified moments; Play Mode remains free of live instruction.
- The player can request an opening, trap, endgame or concept and always receives a visible answer: begin, support current work, schedule next, or learn a prerequisite first.
- All learner-facing progress claims link to inspectable evidence and use an insufficient-evidence state when the proof window is incomplete.
- Mohit can review a sampled player's diagnosis, Review narrative, assigned lesson and verdict and find that they form one coherent human coaching plan.
- The isolated validation database can reproduce every release scenario without reading or writing a real player's mutable coaching state.
- The real-user pilot demonstrates the intended behaviors: players understand their focus, complete assigned work, return after another game and continue into a later coaching cycle. Numeric launch thresholds are locked from baseline/pilot distributions before rollout, not invented in this scope.
- Paid promises remain disabled until a free value event is reproducible, entitlements are provider-backed and some activated players return for continued coaching rather than only consuming the first report.

## 6. Open questions

- **Question:** How many supporting focuses can be active without confusing the player?
  - **Why unresolved:** the product must allow multiple active focuses, but the correct visible limit depends on real cognitive load and completion behavior.
  - **Unblocking step:** compare candidate focus-set sizes using current player distributions and a small observed pilot; lock the limit with `/lock-via-data`.

- **Question:** How many and which historical games are required before a new personal diagnosis is strong enough to present?
  - **Why unresolved:** frequent concepts and rare concepts accumulate evidence at different rates; a fixed game count may be dishonest.
  - **Unblocking step:** calculate per-concept opportunity accumulation across production users and choose evidence-based sufficiency rules.

- **Question:** Which concept families should become player-facing plans first after piece safety?
  - **Why unresolved:** technical readiness, player distinctiveness, frequency and teachability may rank threat awareness, time management, tactics and conversion differently.
  - **Unblocking step:** run a cohort-distinctiveness and detector-readiness bake-off; Mohit reviews the sampled focus choices before the order is locked.

- **Question:** What is the intervention budget in Coach Mode for different time controls and player stages?
  - **Why unresolved:** too much help destroys play; too little help fails to teach, and the balance may vary by context.
  - **Unblocking step:** measure current interruption density and completion, then pilot candidate policies with replay/session review.

- **Question:** What baseline and comparison windows prove transfer for each concept?
  - **Why unresolved:** opportunities occur at different rates and event-time data is currently inconsistent in legacy focus records.
  - **Unblocking step:** build opportunity histograms and simulated chronic/learner cohorts, then data-lock per-concept or concept-family windows.

- **Question:** Which positional claims can be verified deterministically and which require human adjudication?
  - **Why unresolved:** plans often have several acceptable moves and engine preference alone does not identify the human lesson.
  - **Unblocking step:** Mohit adjudicates a stratified contrast-position packet; disagreements define the boundary between deterministic, human-reviewed and research-only claims.

- **Question:** How should existing attempts from overlapping training systems migrate into the canonical attempt record?
  - **Why unresolved:** legacy records use different identifiers, assistance fields, timestamps and success meanings.
  - **Unblocking step:** inventory each attempt source, map reproducible fields, preserve unknown provenance explicitly and dry-run the migration in validation.

- **Question:** Which legacy focus and progress claims can be preserved?
  - **Why unresolved:** production has focus history but no current metrics and several older progress definitions.
  - **Unblocking step:** define reproducibility rules, run a read-only migration report and present preserved/withdrawn counts before any production update.

- **Question:** What real-user activation and retention thresholds authorize paid beta and broader rollout?
  - **Why unresolved:** current training use is too low to provide a trustworthy baseline for the new journey.
  - **Unblocking step:** instrument the complete free value journey, observe the reviewer cohort, then preregister thresholds from the resulting distributions.

- **Question:** What subscription price and packaging match the demonstrated value?
  - **Why unresolved:** competitor pricing establishes a range but ChessGuru has no verified payment/renewal evidence.
  - **Unblocking step:** complete the free value event and subscription lifecycle, then run a controlled packaging test on activated users.

## 7. Pre-code requirements

- Mohit explicitly signs off this complete scope document after reviewing the literal new-player and existing-player experiences.
- The isolated `chessguru_validation` database is created on the production Mongo server with separate credentials or an equivalently enforced database boundary.
- Validation disables email, payment, external account sync and production analytics, and uses remapped anonymized IDs with no credentials, usernames, emails or provider/payment identifiers.
- A snapshot/restore procedure exists before copying production samples or testing migrations.
- The canonical-authority map is agreed: focus authority, sole focus reader, concept registry, detector authorization, lesson lifecycle, attempt record, progress projection and coaching context.
- Every existing focus reader, teaching engine, attempt source and learner-facing progress calculation is inventoried as keep, adapter, migrate or retire; no new authority is created while ownership is unresolved.
- The complete concept inventory is reconciled: duplicates are mapped to one canonical fact, each concept has a stable ID and role, and adding one concept does not require copying its definition into multiple sources.
- A concept evidence-contract template is approved covering opportunity, safe explanation, teaching methods, checkpoint, transfer fact, truth provenance and authorization grade.
- Event-time rules, assisted/unassisted rules and comparable-opportunity rules are defined before any outcome migration or improvement calculation.
- Production distributions are collected read-only for opportunity frequency, focus-set size, clock coverage, legacy migration coverage and player-stage coverage.
- Numeric choices—including focus-set limit, evidence windows, ranking formula, intervention budget, lesson length and rollout thresholds—are passed through `/lock-via-data`; none are selected from intuition.
- Mohit reviews initial gold packets across fundamentals, tactics, positional play, time, openings, traps and endgames; legal replay/tablebase checks are included where applicable.
- The existing test baseline is recorded honestly, including collection failures and routes not exercised by CI.
- A staging/validation end-to-end harness can run new-player and existing-player journeys with MongoDB, Stockfish and the frontend without pointing state-changing tests at real production users.
- Migration scripts are additive, idempotent, dry-run-first and restricted to explicitly selected test/validation users until a separate production rollout is approved.
- Player-facing claims and paid promises that depend on the new loop remain default-off until their acceptance evidence exists.
- After scope signoff and data locks, `/audit-pre-code` is run before the first implementation edit.
