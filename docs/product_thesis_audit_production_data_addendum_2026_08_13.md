# ChessGuru Product-Thesis Audit — Production-Data Addendum

## Evidence status

This addendum reconciles the repository audit with the supplied report **“Does ChessGuru Know You?”**, dated 13 August 2026. That report states that it used read-only queries against production `chess_coach`, direct execution of production services, three anonymized case studies, and a 20-shuffle null test across 47 eligible users.

The supplied artifact is a derived audit report, not raw database access. I have verified that its described defects are consistent with the repository code paths, but I have **not independently rerun its database queries**. Production counts below should therefore be read as **production-audit evidence supplied by the user**, not independently reproduced results.

## Revised verdict

**FIX. Do not KILL. Do not GO as the primary paid product yet.**

The production evidence makes the current thesis weaker than the repository-only audit concluded:

- ChessGuru has unusually rich longitudinal raw material.
- It can produce excellent position-specific explanations.
- It usually does **not** convert that material into a diagnosis that distinguishes one player from another.
- It has **never successfully measured a focus outcome**.
- Training participation is far too low to claim a working learning loop.

The accurate product description today is:

> ChessGuru is a strong personalized-data and chess-explanation engine with an incomplete coaching product layered over it.

## Findings that supersede the original audit

### 1. Improvement measurement is broken, not merely statistically weak

Production result: **0 of 271 `user_active_focus` documents have a populated `current_metric`.**

The repository explains the failure in `primary_weakness_picker.check_focus_outcome()`:

- `focus.started_at` is stored as an ISO string.
- `games.analyzed_at` is a BSON Date.
- The `$gte` comparison crosses BSON type brackets and returns no games.
- Every scheduled check returns `no_data` and extends the lock.

There is a second independent correctness defect: observations are selected using `move_observations.derived_at`, while games are selected using `games.analyzed_at`. A backfill timestamp is not the date the chess was played or analyzed, so even after fixing the type mismatch the numerator and denominator describe different windows.

Revised answer to “Does ChessGuru determine whether training worked?”: **NO.**

### 2. The current diagnosis does not discriminate players

Production evidence across 50 profiled users:

- 47/50 receive `piece_safety` as the top diagnosis.
- 34/50 receive `king_safety` second.
- 43/50 users with a live focus see one of two hard-coded Home paragraphs.
- Piece safety accounts for `34.7% ± 7.5%` of mistakes across users—a relatively flat population signal.

Meanwhile, unused signals distinguish players much more strongly:

- Missing an opponent blunder: up to 19.5× spread.
- Ignoring threats: 16.1× spread.
- Critical-moment best-move rate: 1.7%–22.7%.
- Impulsive critical moves: 0%–4.8%.
- Opening-phase mistake rate: 3.9%–32.8%.

This changes the diagnosis assessment from “finds an evidence-backed personal bottleneck” to:

> **ChessGuru reliably finds a common beginner weakness, but usually fails to identify what is unusually bad—or unusually good—about this particular player.**

### 3. The best coaching surface is history-blind

The supplied production sample found `weakness_match = false` on **11,852/11,852** review cards. This matches the code boundary: `build_move_teaching_decision()` does not receive `user_id` or a cross-game learner context.

Thus the best per-move captions are ChessGuru intelligence, but mostly **single-game intelligence**. Cross-game history affects focus, Home copy and puzzle selection, not the main explanation at the moment the user studies their error.

### 4. Training exists structurally but has almost no behavioral adoption

Against 13,171 analyzed production games:

- 394 `puzzle_attempts`, across 17 users.
- 118 solve attempts, across 13 users.
- 464 Play With Coach sessions lifetime; 10 in August.
- 32 coaching prescriptions across six users, including test/prototype-like records.

Own-game puzzle generation is real. A functioning learning habit is not yet demonstrated.

Puzzle difficulty is also materially wrong for the audience: the training path falls back to `max(..., 1200)`, producing a 1200 rating for 57/69 inspected users, while the real median rating from game records was 849 and the lower quartile was below 516.

### 5. Existing progress claims should not be trusted as improvement

The supplied audit performed a null test on the “most improved pattern” calculation:

- Chronological split said “improving” for 66% of users.
- Shuffled, time-destroyed splits said “improving” 71% of the time.

Therefore the prominent improvement output contains no demonstrated time signal. It selects the maximum of several noisy ratios over small samples. This should be removed or relabeled until replaced by a valid measure.

### 6. Production contains high-value intelligence that the UI ignores

The production audit found:

- 413,186 move observations across 56 users.
- 40,189 subtype-classified mistake observations.
- 278,322 moves with think time.
- 11,993 games with move-time statistics.
- 10,039 community puzzles and 36,597 training positions.
- 13,624 successfully executed tactical patterns.
- 71 users with opening profiles and 65 with opening mastery data.

The moat candidate is the dataset connecting position, behavior, timing, recurrence and eventual intervention—not the current Home paragraph.

## Real-user evidence

### High activity

- 1,442 analyzed games and 50,807 observed moves.
- Rating roughly 1385→1358; peak 1507, trough 1271.
- Current coaching emphasizes piece safety.
- Yet the user is better than the cohort on hanging pieces, ignored threats and missed opponent blunders.
- 249 timeout losses, 3.5-second median move and 821 impulsive-critical events indicate time management may be the more distinctive constraint.
- Only three puzzle attempts, no measured focus outcome.

This is the decisive false-positive product case: the database knows something individual, but the focus ranking tells the user the generic answer.

### Medium activity

- 114 analyzed games; genuine rating around 196.
- No active focus despite exceeding the 10-game gate.
- Strength profile claims positional sense 100 and overall strength 1300.
- Impulsive-critical rate is 4.69%, above the 90th percentile.
- That highly distinctive signal is not surfaced.

This proves both a focus-coverage hole and severe strength-model miscalibration.

### Low activity

- 34 analyzed games; rating around 1326.
- Generic threat-awareness fallback, no subtype evidence.
- Opening recognizer returned Unknown for all 33 classified games.
- No training attempts and no measured outcome.

The system is honest here, but delivers little recurring value.

## Revised scores

| Dimension | Original repo-only | Production-corrected | 60-day potential |
|---|---:|---:|---:|
| Diagnostic intelligence | 6.5 | **6.0** | 8.0 |
| Longitudinal understanding | 6.0 | **4.0** | 7.0 |
| Personalisation | 5.5 | **3.0** | 7.0 |
| Training quality | 6.5 | **2.0** | 5.0 |
| Improvement measurement | 4.0 | **1.0** | 7.0 |
| Retention | 4.0 | **2.0** | 4.5 |
| User WOW | 5.5 | **5.0** | 8.0 |
| Differentiation | 6.0 | **5.0** | 7.0 |
| Defensibility | 4.5 | **3.0** | 5.0 |

**Production-corrected overall thesis readiness: approximately 3.4/10.**

The underlying technical asset is stronger than 3.4/10. The score is for the product thesis as experienced by a real user, not code quality or data richness.

## Revised direct answers

- **A. Better understanding after 30 games than one? PARTIALLY.** Internally yes; user-facing discrimination barely improves.
- **B. Identifies the actual rating bottleneck? PARTIALLY, leaning NO individually.** It mostly identifies the population’s dominant weakness.
- **C. Prescribes training? PARTIALLY.** The structural route exists; difficulty and adoption are poor.
- **D. Determines whether training worked? NO.** Zero measured focus outcomes.
- **E. Reasonably worth monthly payment today? NO for the broad target cohort.** A few users may value the review engine, but production behavior does not support a recurring subscription thesis.
- **F. Can it become better than Stockfish + LLM? YES.** The structured observation corpus, verified caption system, cohort comparisons and multi-game Mirror are real assets.

## One 60-day outcome

> **For every active user with at least 30 analyzed games, ChessGuru states one weakness that is genuinely specific to that player—at least 25 percentile points from their rating-band cohort median—and 14 days later reports a valid before/after measurement for that exact signal. At least 80% of eligible active focuses must end with a real measured result rather than `no_data`.**

This is stronger than the original audit’s completion objective because production evidence shows the two thesis-breaking failures are diagnosis specificity and outcome measurement. It prevents the team from satisfying the sprint by adding new surfaces.

## Recommended engineering order

1. Fix measurement window types and event-time semantics; backtest before displaying anything.
2. Remove or suppress the current “most improved” claim because it fails the null test.
3. Rank weaknesses by cohort deviation and likely rating impact, not raw population-common counts.
4. Restore time management as a measurable focus using impulsive-critical rate/timeouts.
5. Make the current focus additive context in game review without allowing it to alter engine-verified chess claims.
6. Correct rating resolution for puzzle difficulty.

No new major feature should begin until the 60-day outcome is met.
