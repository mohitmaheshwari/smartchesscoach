# ChessGuru Product-Thesis Audit — 13 August 2026

> **Production-data correction (added 13 August 2026):** A subsequent production-data audit materially changed several conclusions below. The corrected verdict and scores are in [product_thesis_audit_production_data_addendum_2026_08_13.md](product_thesis_audit_production_data_addendum_2026_08_13.md). Where the original report says focus-outcome measurement is active or partially working, the production evidence supersedes it: **0 of 271 focuses have a real `current_metric`; improvement measurement is broken.**

## Executive verdict

**Decision: FIX, then GO — not KILL, and not yet GO as the main paid product.**

The thesis is **partially true** today:

> After enough games, ChessGuru can identify recurring, recent mistake categories; choose one evidence-backed focus; train the player on positions drawn from their games; and detect whether that category becomes less frequent.

The stronger public claim is not yet consistently true:

> ChessGuru does not yet reliably explain the player's underlying thinking process, route every eligible learner through the loop, or prove that ChessGuru caused improvement.

This distinction matters. The repository contains a credible coaching spine, not merely a Stockfish wrapper. But it also contains rival profile stores, dead memory paths, weakly validated heuristics, low feature reach, and user-facing claims that outrun delivered behavior. The right investment posture is to stop expanding breadth and make one longitudinal loop work for a meaningful cohort.

### Evidence boundary

- Active routes and code were traced in the current worktree at commit `b0105f21`, with an additional **uncommitted/staged Sprint 2 hardening pass**. Those hardening changes are not treated as shipped.
- The live public site and pricing page were inspected on 13 August 2026.
- The local MongoDB container was present but required authentication. I did not obtain credentials from container configuration. Fresh record-level querying is therefore **UNVERIFIED**.
- Existing aggregate audits in `docs/chessguru_evidence_board.md` are used where they record direct production queries. They are supporting evidence, not a substitute for code-path tracing.
- Focused tests: 39 passed; 13 endpoint tests failed before exercising product logic because `BASE_URL` was empty. This is a test-environment failure, not evidence that the endpoints are broken; it is also not passing end-to-end evidence.

## 1. Current user journey

| Stage | User sees | System learns/persists | What history changes |
|---|---|---|---|
| Landing | Premium positioning: recurring patterns, own-game puzzles, recovery detection, six-domain progress | Nothing until authentication | Nothing |
| Signup/onboarding | Google/email auth, then account connection or puzzle diagnostic path | User, rating/platform identifiers, onboarding state | Existing games determine whether diagnostic is offered |
| Cold-start diagnostic | A 20/25-puzzle adaptive diagnostic, consequence-graded result, headline gap and training CTA | `diagnostic_sessions`; a provisional weakness is also written into `player_profiles`/`coach_memory` | Superseded after 10 analyzed games; it is a cold-start bridge, not the durable learner model |
| Connect/import | Chess.com/Lichess username and sync status | `games`, `analysis_queue`; PGN, rating, result, opening, clocks where available | More analyzed games unlock focus assignment and richer Home copy |
| First analyzed game | Game review with turning points, deterministic captions, patterns and training links | `game_analyses`, per-move engine evaluations/cognitive gaps; puzzles may be extracted | Single-game coaching is strong, but recurrence confidence is necessarily low |
| Home return | Either honest “still learning,” or a coach conversation: stage, active focus, style-shaped theory and one action | Reads `user_active_focus`, `player_identities`, `user_pattern_decay`; writes small Home conversation continuity state | Relationship wording changes at 20/150/400 analyzed games; focus and decay state can change narrative |
| Lab/review | Coach’s Pick, recurring-pattern context, selected game and review | Refreshes/reads decay and review state | Recent mistakes weigh more; reviewed games are deprioritized |
| Training | User's own positions first, community fallback, difficulty metadata; completed solves excluded | `community_puzzles`, `puzzle_attempts` | Correct solves give capped recovery credit and refresh decay immediately |
| Play With Coach | Rating-aware live commentary, quizzes/guardian, session goal; for eligible users the active focus enters greeting/mission | `coach_sessions`, `coach_messages`, postgame data, mission scoreboard | The current active focus can affect in-game pedagogical opportunity and mission copy |
| 10+ games | One focus becomes eligible when there are at least 10 analyzed games and at least 3 occurrences | `move_observations` aggregated into `user_active_focus` with baseline and 14-day lock | The system distinguishes candidate weaknesses and locks one focus |
| Later return | Home can say a previous theory is declining/fading and move to another focus | `home_conversation_state`, focus outcomes, decay state | This is a real longitudinal “coach revised its theory” mechanism, but reach depends on focus assignment and sufficient data |
| Progress | Narrative profile, recurring weaknesses, patterns, improvement proof and, for trained prescriptions with enough data, before/after rates | Multiple stores: `player_identities`, `problem_lifecycle`, `thinking_scores`, `user_pattern_decay`, prescriptions | Can report association over time; cannot generally establish causation |

Primary evidence: `frontend/src/App.js`, `frontend/src/pages/Onboarding.jsx`, `frontend/src/pages/DiagnosticPuzzles.jsx`, `backend/routes/diagnostic.py`, `backend/journey_service.py`, `backend/routes/home.py`, `backend/services/home_coach_conversation.py`, `backend/services/primary_weakness_picker.py`, `backend/services/pattern_decay_service.py`, `backend/routes/training.py`, `backend/routes/training_advanced.py`, `backend/routes/player.py`.

## 2. Learner-signal inventory

Reliability below means reliability of the *player conclusion*, not whether the code executes.

| Signal | Detection/source | Persistence | Meaningful sample | Future influence | Status / reliability |
|---|---|---|---|---|---|
| Move quality, cp loss, best move | Stockfish per move | `game_analyses.stockfish_analysis.move_evaluations` | 1 position/game | Captions, review, puzzle extraction | **REAL AND ACTIVE / high** for engine evaluation |
| Cognitive gap category | Deterministic/heuristic classifier over engine and board facts | move evaluations; derived into `move_observations.missed_pattern` | 1 event; recurrence needs 10+ games/3 fires | Focus ranking, review, training | **REAL AND ACTIVE / medium**; category accuracy varies |
| Piece-safety subtype | Board verification and response sequence: `simple_hang`, `threat_ignored`, `tactical_seq_loss`, `quiet_blunder`, `small_slip` | `move_observations.subtype/severity`, focus histogram | 3+ occurrences | Focus narrative, instruction selection | **REAL AND ACTIVE / medium-high** relative to broader labels |
| Threat awareness | Detect opponent threat; count response vs ignore | `move_observations`; aggregate response rate | Several actual threat opportunities | Can become primary focus | **REAL AND ACTIVE / medium**; opportunity detector quality is load-bearing |
| Punishing opponent blunders | Opponent-blunder event followed by response | `move_observations` aggregate rate | Several opportunities | Candidate focus | **REAL AND ACTIVE / medium** |
| Pins/forks/skewers/motifs | Concept detectors/caption facts and tactical-pattern fields | analyses, observations, motif profile/history | Event-level immediately; profile after repetition | Review and motif-specific drills in some paths | **IMPLEMENTED BUT UNEVEN / medium**; no single universal motif learner model |
| Repeated weakness | Aggregate all observations, minimum 10 games and 3 occurrences | `user_active_focus`, runners-up, baseline | 10 analyzed games | Home, PWC goal, mission, training route | **REAL AND ACTIVE / medium-high** |
| Recency and recovery | Last 20 games, exponential `0.85^n`; clean streak credit `0.3`; correct-puzzle credit `0.1`, capped at 1 | `user_pattern_decay` | Useful after several games | Lab prioritization, Home theory revision | **REAL AND ACTIVE / medium-high** |
| Focus outcome | Baseline occurrences/game vs post-focus occurrences/game; −20% improved, +10% regressed | `user_active_focus.current_metric/resolution` | 14-day cycle plus games after start | Close/celebrate/escalate/extend | **REAL AND ACTIVE / medium-low**; no variance/control adjustment |
| Style (aggressive/positional/developing) | Aggregate game tendencies | `player_identities.style_profile` | Multi-game; exact minimum varies | Changes Home theory wording | **REAL AND ACTIVE / medium**; narrow downstream impact |
| Tilt/collapse | Post-error/loss behavior heuristics | behavioral fields in identity/profile stores | High-volume users | Optional Home overlay; experiments | **IMPLEMENTED BUT WEAK / low-medium**; sparse coverage (11/63 in prior direct audit) |
| Post-blunder accuracy, recovery capability, worse after loss, overall improvement rate | Declared defaults, not populated by active writers | mostly missing/default in `player_identities` | N/A | No working user path | **PLACEHOLDER/ORPHANED** |
| Coach notes | Generated inconsistently | `player_identities.coach_notes` | Unknown | Potential memory | **IMPLEMENTED BUT WEAK**; prior audit found 11/63 populated |
| Cross-session teaching recall | Indexed teaching memories plus gated reader | `user_teaching_memory` | Historical backfill only | Intended PWC explanation depth | **COLLECTED BUT NOT USED**; prior audit found 29,974 stale docs and 0/755 served `v5_teaching` messages |
| Thinking/habit scores | Per-game composite heuristics | `thinking_scores` | Per game; trends need several | Feeds focus/progress | **REAL AND ACTIVE / low-medium**; 12,676 docs in prior audit but no outcome validation |
| Opening identity/name/result | PGN/opening lookup | `games`, opening profile/progress stores | 1 game, better over repetition | Opening pages/recommendations | **REAL AND ACTIVE / medium** |
| Opening familiarity from timing | First up-to-10 clean opening move times, increment-corrected | `games.move_time_stats.opening_recognition` | ≥4 timed opening moves in a clock-annotated game | None today | **EXPERIMENTAL / raw primitive** |
| Known vs unknown position / prep ending | Not inferred | None | N/A | None | **NOT IMPLEMENTED** |
| Move-time discipline | Clock deltas + increment; compare critical move with user's median | `games.move_time_stats` and observation time flags | ≥3 timed moves/game; history improves baseline | Mirror/PWC/focus candidates, though time-management focus is disabled | **IMPLEMENTED BUT WEAK / medium** |
| Time-management primary focus | Synthetic time flags and timeout rate | Candidate code exists | 10+ games | Intended focus | **DISABLED** because outcome measurement used the wrong field and wedged 18/38 active locks in a prior production audit |
| Puzzle performance | Correctness, time, attempts | `puzzle_attempts` | Per attempt | Exclusion, decay recovery; difficulty metadata | **REAL AND ACTIVE / medium** |
| Rating trend | Imported game/user ratings | games/profile | Multiple chronological games | Some progress/profile surfaces | **REAL AND ACTIVE / high as observation**, not proof of product effect |

## 3. Longitudinal intelligence

### Game 1

ChessGuru knows engine truth about that game, one or more classified mistakes, opening/result/rating metadata, and perhaps timing. It can extract own-game puzzles. It **does not know recurrence** and should not claim a durable bottleneck.

### Game 10

The durable focus pipeline becomes eligible: `MIN_ANALYZED_GAMES = 10`, and a candidate needs `MIN_EVIDENCE = 3`. Observations are aggregated across games, rating acts as a soft prior, evidence severity dominates, and one focus is locked. This is the first point where “what keeps happening” can be more than rhetoric.

### Game 30

The last-20-game decay window can distinguish active, declining and fading patterns. Clean games and puzzle solves change state. A 14-day focus may have a baseline/current outcome. Home can vary theory by style and say it has revised an earlier theory if the previous topic declined/faded.

### Game 100

The system has much more evidence for rates, subtypes, phase/style and repeat cycles, but not proportionally deeper cognition. Pattern decay still looks at 20 games; focus aggregation can use up to 25,000 observations. It can know that a category has recurred, disappeared, returned, or changed rank. It cannot reliably know the player's internal reason (“attention tunneled because attacking”) unless that reason is a hand-authored inference attached to category/style.

Direct answers:

- Aggregates across games: **YES**.
- Distinguishes occasional from recurring: **YES**, through minimum evidence, rates and decay.
- Weights recency: **YES**.
- Weakness strengthens/weakens: **YES**.
- Detects improvement: **PARTIALLY**; rate reduction and clean streak, without robust statistics.
- Previous coaching affects future coaching: **PARTIALLY**; active focus and puzzle credit do; teaching recall does not.
- Next game analysis knows prior games: **PARTIALLY**; PWC session setup and prioritization do, core Stockfish analysis remains game-local.
- One coherent learner model: **NO**. `user_active_focus` is becoming canonical for current focus, but identity, decay, problem lifecycle, coach memory, prescriptions and opening stores remain separate and sometimes conflicting.

## 4. Diagnostic depth

Deepest truthful conclusions currently possible:

1. “Across your games, piece safety is the highest-impact recurring category, with simple hangs dominating.” — historical observations + board-verified subtype + focus ranking.
2. “You often ignore a threat after the opponent's last move.” — opportunity/response heuristic across games.
3. “You see one tactical move but lose material in the forced sequence.” — engine/board-derived subtype.
4. “This pattern was active, but you have several clean recent games and it is declining.” — decay state.
5. “Since this focus started, events/game fell by X%.” — baseline/current rate.
6. “You tend to play aggressively, and when committed to an attack you stop scanning the rest of the board.” — first clause derived; second clause is hand-authored theory, not directly observed cognition.
7. “Your critical error was played much faster than your normal pace.” — personal timing baseline where clocks exist.
8. “A tough loss may carry into your next game.” — sparse behavioral heuristic, only shown above threshold.
9. “The real problem began several moves before the visible blunder.” — deterministic turning-point callback, still single-game causal chess reasoning.
10. “You have solved training positions for this weakness and earned recovery credit.” — actual training history.

The strongest “why” language is therefore a combination of Stockfish facts, deterministic board rules, history aggregation and hand-authored interpretation. It is not an LLM independently discovering a stable cognitive mechanism. The product is strongest at **WHAT repeatedly happens and under which visible chess context**; it is much weaker at **WHY this person thinks that way**.

## 5. Personalisation path

The best complete path is:

`game PGN → Stockfish move evaluation → cognitive gap/subtype → move_observations → aggregate_user_signals → primary_weakness_picker → user_active_focus → focus_bridge → Home/PWC session goal/mission → own-game pattern puzzles → puzzle_attempt → pattern-decay refresh → later focus outcome`.

Breaks and narrow points:

- Focus assignment is external-cron-dependent and starts only after 10 games. Prior direct audit found a real focus topic in only 21/460 all-time PWC sessions (5%) and 4% of recent first sessions.
- The core game analysis does not say “this exact geometry resembles Games 4, 8 and 11” as a universal behavior. Pattern-history/motif paths exist, but are not the single coaching spine.
- Style changes Home prose, but often through prewritten category/style variants.
- Rating changes thresholds, extraction and intensity. That is legitimate adaptation, but not deep personal memory.
- Sprint 2’s “one surviving instruction” is committed default-off and admin/super-admin gated. The worktree hardening adds a visible session-owned verdict and write-time gating, but is not committed/shipped in this audit boundary.

## 6. Training loop

The loop is technically closed for major cognitive-gap categories, but behaviorally incomplete:

1. Detection: engine + category/subtype classifier.
2. Prescription: current-focus route or pattern link.
3. Personalization: own-game puzzles first, then community; category and rating-informed difficulty metadata.
4. Completion: `puzzle_attempts` records correctness/time/moves.
5. Re-observation: later games generate the same observation types.
6. Improvement: decay and focus outcome can detect fewer events/game.
7. Next focus: completed/escalated focus can yield another candidate after cooldown.

Limitations:

- Correct puzzle solving is treated as small recovery evidence, not proof that transfer occurred in games. That is sensible, but the UI can overread it.
- Prescription tracking is partial and sparse (prior audit: two active real users).
- Category classifiers are not equally trustworthy. Piece safety is much stronger than calculation depth or positional diagnosis.
- The system can measure “after training” correlation for prescriptions with ≥3 baseline and ≥3 current games, but selection bias and concurrent learning remain.

## 7. Improvement measurement

| Metric | Definition/storage | Exposure/use | Limitation |
|---|---|---|---|
| Accuracy, mistakes, blunders | Engine-derived per game/profile | Review/progress | Opponent/position/time-control mix confounds trend |
| Rating | Imported platform rating over games | Profile/progress | Strong outcome, but influenced by play volume and platform |
| Pattern rate | Occurrences ÷ analyzed games | Focus outcome/progress | Events/game ignores opportunity count and variance |
| Pattern decay | Recency-weighted presence minus recovery | Lab/Home decisions | Hand-set constants; not statistically calibrated |
| Threat-response rate | responses ÷ detected threats | Focus candidate | Detector opportunity quality limits validity |
| Blunder-punish rate | punished ÷ opponent blunder opportunities | Focus candidate | Sparse for some users |
| Thinking scores | heuristic per-game habit composite | focus/progress | Not outcome-validated |
| Puzzle solve rate/time | attempts | training/decay | Puzzle improvement may not transfer to games |
| Training before/after | pattern rate before vs after started prescription | `/progress/improvement-proof` | Honest association, still labeled `training_causal` too strongly |
| Opening timing primitive | average/min/max early move time | not user-facing/unused | Timing is only a proxy; no known-position ground truth |

**Can ChessGuru prove it helped? NO.** It can show credible within-user correlation: training happened, and the measured error rate later declined. Only the small randomized Universal Habit Coach holdout attempts causal inference: 4 treated vs 4 control, 68% vs 48% clean rate. That is promising and underpowered, not proof.

## 8. Opening recognition and timing

- Timing stored: **YES**, when PGN clock annotations exist.
- Increment handled: **YES**, parsed from time control and added back.
- Opening timing calculated: **YES**, raw first-window average/min/max/count after enough clean samples.
- Familiarity inferred: **NO**; deliberately not labeled.
- Persisted: **YES**, per game at `games.move_time_stats.opening_recognition`.
- Consumed by coaching: **NO verified active consumer for the recognition primitive**.
- Known vs unknown position: **NO**.
- Preparation end: **NO**.
- Training generated from it: **NO**.
- Status: **EXPERIMENTAL/VALIDATION PRIMITIVE**, not shipped product intelligence.

## 9. WOW moments

| Moment | Reality/frequency |
|---|---|
| “This is the same recent piece-safety issue, especially simple hangs” | Real after 10+ games and focus assignment; potentially strong, but current reach is low |
| “I thought X; now I think Y” when an old pattern fades | Real data gate in Home; likely rare and dependent on focus/decay transitions |
| Own blunder returned as a puzzle | Real and broadly understandable; common once analysis/extraction completes |
| Critical mistake was rushed relative to personal pace | Real only with valid clock annotations; occasional |
| Earlier turning point caused the later collapse | Real deterministic single-game insight; can feel coach-like, frequency depends on pipeline fire |
| Style-specific theory | Partly personal, partly templated; may feel personal but is not a discovered psychological truth |
| Relationship language (“I know what usually causes your losses”) | Game-count templating; looks personal, not itself evidence |
| Landing-page examples such as “5th game in a row” | Marketing illustration; do not treat as verified live output |

## 10. Retention loop

- Immediately after a game: **YES** — analysis, turning points, pattern verdict, own-game puzzle extraction.
- Tomorrow: **WEAK** — Home one-action/PWC and diagnostic continuation. Daily emails reach only a pilot address; Daily Fix entry is orphaned.
- After 7 days: **PARTIAL** — updated decay/focus, new imported games and practice; little guaranteed new value without more play.
- After 30 days: **YES, if active** — focus outcome, pattern transition, progress narrative and new recommendation.
- After 6 months: **PARTIAL** — richer history/style/focus cycles and rating trend, but no robust long-term curriculum or causal proof. For an inactive user: **NONE**.

## 11. Alternative comparison

### Commodity

Stockfish evaluation, best moves, accuracy, generic captions, basic opening naming, standard puzzles, LLM-written encouragement and rating bands can all be reproduced by Chess.com/Lichess plus a general LLM.

### Differentiated today

- Recency-weighted personal pattern states with clean-game and puzzle recovery.
- One focus ranked from the player’s cross-game subtype evidence.
- Own-game-first pattern training connected to that focus.
- Personal-pace comparison for rushed critical moves.
- Cross-game Home narrative that can revise a theory when the old topic fades.

### Potential moat

The event-level longitudinal dataset (`move_observations` + outcomes + training attempts + focus cycles) could become a moat because it links chess situations to repeated behavior and intervention response. Today it is **not yet a moat**: coverage is low, taxonomies are partly heuristic, experiments are tiny, and similar histories could be rebuilt from imported PGNs.

## 12. Real-user cases

Fresh low/medium/high anonymized reconstruction is **UNVERIFIED** because authenticated database access was unavailable. I will not fabricate it.

Previously verified aggregate production evidence establishes:

- 114 users in focus eligibility audits; 52 had at least 10 analyzed games.
- 63 users had player-identity documents; style had full coverage in that subset.
- Active focus population was approximately 62 in the Experiment #1 documentation.
- Coach notes were populated for 11/63.
- The diagnostic completed for about 8% of users and 42% abandoned before puzzle 1.
- Teaching-memory index held 29,974 stale documents but had never produced a recorded V5 teaching message.

Those facts support population-level conclusions, not individual case studies.

## 13. Maximum truthful dashboard for the best-understood user

> **YOUR CHESS**
>
> Games analyzed: *available from `game_analyses`*
>
> Current rating and recent movement: *available from imported games*
>
> **#1 thing holding you back**  
> Piece safety, selected from your cross-game evidence. The strongest repeated subtype is simple hangs/threats ignored. Evidence count, severity and games at baseline can be shown.
>
> **Recurring pattern**  
> Active/declining/fading state across the latest 20 games, recent count, clean-game streak and supporting game links.
>
> **Tactical profile**  
> Threat-response rate, opponent-blunder punish rate, tactical/motif events where detectors have evidence. Do not claim mental cause.
>
> **Playing style**  
> Aggressive/positional/developing, with the exact observable tendencies used to derive it.
>
> **Opening knowledge**  
> Openings played/results and progress. Early move timing may be shown as raw timing only; do not label positions known/unknown.
>
> **Time management**  
> Median move time and whether the worst move was unusually rushed for games with clocks. Do not assign a time-management focus until its outcome metric is fixed.
>
> **What improved**  
> Pattern rate before focus/training versus after, sample sizes, clean streak and puzzle solves. Wording: “associated with improvement,” not “ChessGuru caused.”
>
> **What got worse**  
> Categories whose recent rate/state rose, with game examples.
>
> **Next focus**  
> One active focus, one concrete instruction and direct links to own-game puzzles/PWC.
>
> **Evidence**  
> Every conclusion links to game IDs, move numbers, board positions and observation counts.

This report is more valuable than the current fragmented surfaces, but almost all underlying fields already exist.

## 14. Product gaps

### P0 — thesis-breaking

1. **Insufficient loop reach.** A real focus reached only ~5% of all-time PWC sessions in the prior audit. Product: make every eligible learner see one evidence-backed focus across Home, review, training and next game. Technical: move assignment from external daily cron into an idempotent analysis-complete/read-through path; instrument each hop. Reuse picker/focus bridge/mission scoreboard. Difficulty: medium. No new data.
2. **No trustworthy intervention-to-transfer proof.** Product: show that the trained error becomes less frequent in later games with adequate samples and honest language. Technical: opportunity-normalized outcomes where possible, intervention timestamp/cohort, minimum samples, comparison/holdout. Reuse focus outcomes, observations, attempts and Experiment #1. Difficulty: medium-high. Needs more prospective data.
3. **Fragmented learner model.** Product: one current explanation of “what holds me back,” with evidence and status. Technical: establish `user_active_focus` + observations/decay as canonical; retire or demote rival current-focus and dead memory fields; freshness contracts. Difficulty: medium. No new user data.
4. **Public value/monetization mismatch.** Live pricing shows `—/month` and disabled Subscribe while landing promises a full loop. Product: do not market ₹199 paid coaching until purchase and promised loop are available. Technical: production configuration and end-to-end payment/entitlement verification. Difficulty: low-medium. No new data.

### P1 — major

1. Calibrate detector reliability per category; limit strong claims to validated categories. Reuse detector audits/gold sets. Medium-high; needs human-labeled samples.
2. Replace hand-authored psychological certainty with evidence-bearing hypotheses and counterexamples. Reuse Home conversation and game links. Medium; no new collection required.
3. Fix time-management outcome semantics before re-enabling it. Reuse time flags/timeout losses. Medium; needs retrospective validation.
4. Make progress evidence one coherent surface, with sample sizes and game links. Reuse existing improvement proof, focus and decay. Medium.
5. Resolve onboarding failure: diagnostic has 8% completion and large pre-puzzle abandonment. Reuse play-first/import-first routes. Medium; needs funnel measurement.

### P2 — enhancement

- Expand motif-specific transfer once detector quality is proven.
- Improve longitudinal opening familiarity only after validating timing against known/unknown ground truth.
- Add richer coach-note memory only if an active consumer is first defined.

## 15. Scores and final answers

| Dimension | Today | Possible in 60 days with current architecture/data |
|---|---:|---:|
| Diagnostic intelligence | 6.5 | 8.0 |
| Longitudinal understanding | 6.0 | 8.0 |
| Personalisation | 5.5 | 7.5 |
| Training quality | 6.5 | 8.0 |
| Improvement measurement | 4.0 | 7.0 |
| Retention | 4.0 | 6.5 |
| User WOW | 5.5 | 8.0 |
| Differentiation | 6.0 | 8.0 |
| Defensibility | 4.5 | 6.5 |

**Overall thesis readiness: 5.4/10 today; 7.7/10 achievable in 60 focused days.**

### A. Better understanding after 30 games than after 1?

**YES, meaningfully—but not comprehensively.** At 30 games it can rank recurring weaknesses, subtype them, weight recency, track clean games/training, select one focus and revise that focus. At Game 1 it cannot. The “why you think this way” layer remains partly templated.

### B. Identify what holds a particular rating back?

**PARTIALLY.** It can identify the most frequent/high-severity measured behavior, especially piece safety and threat response. It cannot prove that this is the causal bottleneck on rating, and weaker categories may be classifier artifacts.

### C. Prescribe training from diagnosis?

**YES, partially delivered.** Own-game-first pattern puzzles and a focus-driven route exist. Reach and continuity are the problem.

### D. Determine whether training worked?

**PARTIALLY.** It can compare later pattern rates and decay states and credit practice; it cannot generally establish causal transfer.

### E. Would a user pay monthly today?

**A minority of highly engaged 600–1500 players might pay after experiencing a strong own-game insight, but the product is not ready to reliably earn ₹199/month across the funnel.** The public Pro purchase is currently disabled/no-price, diagnostic activation is weak, and the best longitudinal loop reaches too few sessions. The coaching engine has payment-worthy moments; the product does not deliver them predictably enough.

### F. Evidence it can beat generic Stockfish + LLM?

**YES.** The clearest evidence is the cross-game observation→focus→own-position training→later-game measurement path, plus recency/recovery and the small randomized habit-reminder result. That is structurally beyond a one-shot LLM review. It is promising evidence, not validated superiority.

### G. One 60-day outcome for two developers

> **Among users who reach 30 analyzed games, at least 60% must complete one full evidence loop in-product: receive one recurring-weakness diagnosis supported by at least three linked game moments, complete targeted training, play at least five subsequent games, and receive an honest outcome verdict; at least 50% of interviewed completers must say the diagnosis revealed a recurring problem they had not clearly recognized themselves.**

This is one product outcome: prove that ChessGuru can know, train and re-measure one real weakness. Do not spend the 60 days adding more lesson types, dashboards or personality layers.

## Final investment call

**FIX with a strict 60-day gate.** The architecture and stored event history justify continued investment. The product has crossed the line from generic analysis into early longitudinal coaching. It has not crossed the line into a reliably delivered, causally credible subscription product. If the single 60-day loop outcome is met, GO. If reach and user recognition remain weak despite making the existing spine universal, reconsider the thesis rather than adding more systems.
