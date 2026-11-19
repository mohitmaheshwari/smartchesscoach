# Coaching intelligence: approved direction and milestones

Status: direction APPROVED (the coach-investor's final direction, forwarded by
Mohit, 2026-11-18). Milestone 1 is detailed below and approved by that
direction ("Begin with instrumentation, pilot recruitment, coach-opponent
logging and strength corrections"). Later milestones each get their own scope
section and sign-off before code.

Evidence base: the investigation of 2026-11-18 (published as "ChessGuru
Diagnosis Investigation") and its corrections.

## Product objective

Understand what an individual player needs, teach it through the most fitting
intervention, and establish with reliable evidence whether he learned it.
ChessGuru aims to be the most effective personal chess teacher, not the best
analysis engine.

## Architectural constraints (from the direction)

1. **Hierarchical competency model.** A tactical theme is not one skill.
   Distinguish piece type, pattern, complexity, preparatory moves,
   recognition, calculation, execution and defensive awareness. Keep the
   evidence needed for these distinctions without fragmenting needlessly.
2. **Diagnostic Engine V0.** Testable hypotheses from existing observations,
   detectors, clocks, Maia and history. Each has supporting and contradictory
   evidence, uncertainty and a diagnostic exercise. In V0 the plan decides what
   to fix and the diagnosis decides how to train it. The data model must let a
   confirmed underlying deficit link several symptoms and later change the
   plan. An inferred psychological cause is never presented as fact.
   Confidence belongs to the evidence for a claim, not to the player.
3. **Play with Coach as teaching and assessment.** Four assistance levels:
   Teach, Guide, Test, Compete. Human-plausible moves, adaptive strength,
   lesson-specific opportunities, with recognition and execution recorded.
   Deliberate instructional opportunities are kept apart from natural play.
   No blanket veto of low-probability Maia moves; the move policy is validated
   against real human move distributions.
4. **Learning verification from four sources:** themed exercises, unlabelled
   positions, controlled practice games, competitive games. Practice games give
   fast application evidence; competitive games give slow transfer evidence.
   Improvement after training is reported as "observed after training", never
   as caused by it. Ten opportunities is a minimum to begin assessing, not proof.
5. **Structured chess reasoning.** Versioned, machine-readable claims (pieces,
   squares, moves, relationships, continuation evidence, verification
   results). Explanations are rendered from verified claims:
   board facts → chess relationships → verified reasoning → words.
6. **Competency research** off production. Four cohorts: improvers, stagnant,
   declining, recovering. Comprehensive analysis of a 1,000-game pilot before
   any faulted-position-only strategy, so denominators include successes.
   Control platform, time control, difficulty, opponent strength, volume and
   player-level clustering. No mastery thresholds from exploratory findings.
7. **Validation standards.** Supported and plausible are reported separately.
   Intervals and sample sizes always shown. Moves are correlated within games,
   players and sessions, so intervals use the game or player as the unit.
   Player-facing explanations need a stronger bar than internal hypotheses.
   Benchmarks account for difficulty, time control and their own uncertainty.
8. **No duplicate engines, databases or sources of truth.** Extend what exists.
   Nothing unvalidated is shown to players.

## Milestones (order approved)

| | Milestone | Priority |
|---|---|---|
| 1 | Instrumentation and real users; Play with Coach logging and strength | P0 |
| 2 | Structured reasoning claims and coach validation set | P0 |
| 3 | Diagnostic Engine V0 (coach-facing, behind a flag) | P1 |
| 4 | Pedagogical practice games (Teach / Guide / Test / Compete) | P1 |
| 5 | Learning lifecycle (introduced → practised → retained → applied → mastered) | P1 |
| 6 | Competency research, separate infrastructure, in parallel | P2 |
| 7 | Positional intelligence, narrow validated scope | P2 |

## Milestone 1 in detail

### 1a. Exposure, completion and adoption measurement

What the investigation found missing, and what this milestone adds:

- **Eligibility and visits, recorded on the server.** Whenever a player with the
  coach pages loads them (not during view-as), the visit is recorded:
  first seen, last seen, and the days seen. This does not depend on browser
  analytics.
- **Plan weeks only for players who can see the plan.** Today a week is locked
  for everyone with a player file (78 of 92 weeks belong to players who cannot
  see the plan). Weeks become exposure-only. Existing rows stay as they are;
  analyses filter them.
- **Impression and action events** through the existing privacy allowlist:
  - plan card viewed; day card viewed; day task opened
  - day size changed; plan work opened (learn / find / play)
  - study game viewed and answered; theme set completed
  - coach Learn page viewed

  No game ids, positions or text are sent.
- **Opened is not completed.** Day tasks already record completion from proof
  (puzzles solved, games played). Plan-card clicks stay "opened".
- **Writes that fail stop looking done.** The plan card no longer turns a tick
  green when the server rejected the write.
- **One timestamp on every puzzle attempt.** The writers that store a text date
  or nothing also store a real timestamp, so attempts can be joined in time.

Acceptance for 1a: for any player and week we can state, from stored data alone,
whether he was eligible, whether he visited, whether he saw the plan and the
day card, which tasks he opened, which he completed, and the week's verdict.

### 1b. Play with Coach logging (before any strength change)

- Store the opponent's real strength per session: rating used after the floor,
  skill level, engine path (weakened engine or teaching selector), and whether
  the floor applied. The stored skill level today ignores the floor.
- Record a termination reason for every finished game: checkmate, stalemate,
  insufficient material, resignation, abandonment.
- Mark staff and development accounts. Mark a real game (15+ moves) at the end.

Acceptance for 1b: from stored sessions we can report score by band and by
engine path on real games by non-staff players, with the opponent's actual
strength.

### 1c. Strength correction (approved by Mohit 2026-11-19: "go ahead")

**What 1b showed.** On the pre-change data, 64 of 65 real games by non-staff
players ran on the coach-mode teaching selector, which ranks full-strength
depth-10 lines. The 1500 floor applies only to play mode. Players under 1000
scored 0 of 45 there (interval 0–8%, from 4 players). Lowering the floor alone
would change almost nothing.

**Built: a human-move opponent for coach mode** (`coach_play/human_opponent.py`):
- Each coach move is sampled from Maia-2's distribution at the player's own
  rating (no floor), facing his rating.
- No engine veto and no "punish" rule. A person at that rating does not
  always take a free piece.
- The opening-lesson line still takes priority. Play mode is unchanged.
- If Maia fails, the existing selector plays, so a game never stalls.
- Behind `PWC_HUMAN_OPPONENT_USERS` (user ids or "*"); empty, so off for
  everyone until the pilot.
- The session's `opponent_strength` records `engine_path: human_policy` and
  the target rating. In the older coach path each coach move's snapshot keeps
  Maia's probability and rank. The unified path stores only the session record.

**The move policy, validated against real human play** (the coach's challenge
to a 1% veto). 1,200 real moves from our players:
- Maia is well calibrated: moves it gives 1–10% were played 3.6% of the time
  against 3.5% predicted. Every bin is close.
- Real players make moves Maia gives under 1% between 0.7% and 5% of the
  time, by band. A 1% veto would delete real play.
- Under 0.2% holds 0–1.3% of real moves. The cut-off is therefore 0.2%, and
  the opponent otherwise samples Maia as-is.

**Measured on prod after deploy (2026-11-19):**
- Real positions at 700, 1200 and 1700 gave human-looking moves (Maia ranks 1 to 13).
- The first version took a median 5.2 s and up to 25 s per move: the
  container has no CPU quota, so torch used every core of the shared box.
  Pinned to one thread: median 0.10 s, 95th percentile 0.21 s, max 0.29 s
  over 36 moves.
- Loading the model takes about 25 s, so it now loads in the background at
  startup whenever the flag names anyone.
- When the player takes Black, the coach's first move still comes from the
  older engine (a separate code path); only that one move.

**Not in 1c:** adaptive strength from results (the target is fixed at the
player's rating until pilot data shows where scores land), and lesson
opportunities (Milestone 4). Maia-2 treats ratings below about 1100 as one
group, so it is least precise for beginners.

**Acceptance:** with the flag on for pilot players, score 35–60% in every band
over 20+ real games from 5+ players (`scripts/pwc_strength_report.py`); coach
move time under 1.5 s at the 95th percentile; no stalled games.

### Pilot (not code)

10–20 real players, or one academy class, using the coach pages for four weeks.
Mohit recruits; engineering turns the flag on for them and reports the 1a
funnel weekly.

### Remaining limitations after Milestone 1

No diagnosis, no structured reasons, no practice-game opportunities yet. Browser
events can be lost if a player closes the tab within seconds; the server-side
visit record is the fallback.
