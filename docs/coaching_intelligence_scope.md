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

### 1c. Strength correction

Chosen after 1b shows which engine path real players actually meet. Behind a
flag, enabled first for the pilot. Target from the investigation: players score
35–60% in every band over 20+ real games from 5+ players. The full Maia
opponent is Milestone 4.

### Pilot (not code)

10–20 real players, or one academy class, using the coach pages for four weeks.
Mohit recruits; engineering turns the flag on for them and reports the 1a
funnel weekly.

### Remaining limitations after Milestone 1

No diagnosis, no structured reasons, no practice-game opportunities yet. Browser
events can be lost if a player closes the tab within seconds; the server-side
visit record is the fallback.
