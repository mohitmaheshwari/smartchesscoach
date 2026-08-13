# Scope: Pattern Learning System (V1 — Knight Forks)

Status: **DRAFT v4.2 — awaiting Mohit's signoff.**
v1–v3 2026-08-13 · v4 after review · v4.1 after product-direction approval · v4.2 after the
fork-architecture correction
Measurements: [pattern_learning_system_evidence.md](pattern_learning_system_evidence.md).

v4.1 → v4.2: **the fork model is piece-agnostic.** Royal-fork support moved OUT of a lesson-local
clause and INTO the canonical `multi_target_attack_evidence`, where it works for every attacker
type — measured on a 6k-move corpus, royal forks split queen 15 / knight 13 / rook 5 / bishop 2, so
a knight-specific fix would have missed 63% of them. `pattern_confidence/fork.py` retired. Gold
redefined as canonical evidence (normal **or** royal), re-run on the mate-corrected set: **97 gold,
not 64**. Entry copy re-worded for ambiguous provenance. Stage 6 closing lesson added. Q4 scoped as
a Stage-8-only blocker. Pre-commit optimisation discharged (`6e094a87`).

---

## 0. Existing surfaces audit

Five overlapping training mechanisms exist. Citations and detail: **E1**.

| Surface | Today | Decision |
|---|---|---|
| `PrescribedTraining.jsx` | Position → best move → grade. Almost no instruction before solving. | **Extend this. It is the host.** |
| `MotifDrill.jsx` | fork/pin/skewer, **non-interactive**, displays the answer. | Replace with the lesson. |
| `SkillDrill.jsx` | Detector-graded, one static hint, no progression. | Reuse the grading idea. |
| `EndgameLesson.jsx` | `INTRO → TRY → CORRECT/WRONG → COMPLETE`, arrows, phase gating. | **Generalise this component.** |
| Opening / trap / escape-square lessons | Real teaching, disjoint from tactics. | Out of scope. |

**Decision: EXTEND `/training`. Do not build a parallel Pattern Academy.** The codebase's dominant
failure mode is building a mechanism and not landing it — 262 services, ~30 write-only or
never-fired collections, and three fully-built systems found dead during this audit (`mistake_cards`
at 0 documents, cross-game recall never fired, MotifDrill's trap panel unreachable). A sixth
parallel training product would repeat it.

**Prerequisite found by this audit and already shipped** (commits `25e0114c`, `2b331aa1`): the
personal-position contract was broken in production — 92% of stored drill solutions were illegal in
their own displayed position and `PrescribedTraining` graded users against them. Fixed, backfilled
and verified at 3,395/3,395 (**E1.2–E1.4**). V1 depends on it; it did not wait for this signoff.

---

## 1. What it is

A structured learning journey for one tactical pattern, replacing random-puzzle mechanics inside
`/training`, keeping own-game positions for the application stage rather than the teaching stage.

**Understand → See → Identify → Create/Avoid → Practise → Recall → Apply.** Puzzles are one part of
that, not the whole. A player can currently solve a fork puzzle without learning what geometry
creates a fork, how to spot one unprompted, how to avoid the opponent's, or whether they still
recognise it tomorrow.

**V1 teaches the knight-fork subtype. ChessGuru's underlying fork model is piece-agnostic and
recognises any move that attacks two valuable targets at once.**

A fork is a multi-target attack — one piece attacking two or more enemy pieces simultaneously.
Knights, bishops, rooks, queens, pawns and kings can all fork; a knight checking the king while
hitting a rook is a royal fork. (A pin or skewer is a different shape: the pieces sit behind one
another on a line rather than being attacked at once.) The canonical model is therefore:

```
Multi-target attack (fork)          <- canonical, piece-agnostic
  ├── knight fork   <- V1 teaches this subtype only
  ├── bishop fork
  ├── pawn fork
  ├── rook fork
  ├── queen fork
  └── king fork
```

V1 narrows the **lesson**, never the **model**. The lesson filters the generic evidence with
`attacker_piece_type == "knight"`. No `knight_fork_detector` is built, and bishop- or pawn-fork
lessons later reuse the same evidence with no new detector.

Knight forks are the right first lesson because the geometry is clear and, uniquely among the
motifs, attribution is clean (**E2**).

**V1 may truthfully say:**
> "You can recognise knight forks without highlights, including in positions where I did not tell
> you a fork existed."

**V1 must not say:**
> "You have stopped missing forks in your games."

That is a real-game transfer claim, legal only after Track A's measurement passes its correctness
gate. Until then the rung-8 slot reads *"Not measured yet."* — plain text, not a spinner or a lock.

---

## 2. What the user sees

The card is the product. One instruction, one board, one interaction per screen. No side panel.
**No notation required before the geometry is understood** — moves are chosen by tapping squares or
arrows; SAN is a secondary label only.

### Entry — never a catalog

Reachable from Home, game review and `/training`; the same lesson in all three.

The draft opener said *"You walked into 3 knight forks in your last 20 games."* **That is not
provable.** Measured: of the 24 users with any gold knight-fork position, **16 have zero in their
last 20 games and exactly 1 has three** (**E3.1**). A 20-game query would therefore silence the
personal opener for almost everyone and still be wrong for one. Corrected copy, which needs no count
and holds for every user who has any gold position:

```
  I found a knight fork in one of your games — and saved the position.
  Let me teach you to see the fork square before it appears.

  [ Start — about 4 minutes ]
```

This wording stays true when provenance is ambiguous — it claims a saved position, not a date or an
opponent, and 11% of stored rows cannot name their game (**E1.4**).

Gate: **≥1 reviewed Gold knight-fork position.** At most 32 users have a Gold-*eligible* candidate;
how many have a reviewed one is unknown until authoring runs, so this gate must read reviewed
positions, never the candidate pool — otherwise the copy promises a saved personal lesson backed by
unaudited material. The specifics move to Stage 8, where the position is on screen and the claim is
self-evidencing. Fallback for everyone else:

```
  Knight forks are the first tactic most players learn to fear.
  Let's make them yours.
```

**We never state a count we have not verified.**

### Session shape

Ten stages is too long for one sitting for a median-849 mobile player. Three ~4-minute sessions,
each independently completable, each ending on a real result.

| Session | Stages | Rung |
|---|---|---|
| **A — See it** | 1 Understand · 2 Geometry · 3 Identify | 1–3 |
| **B — Use it** | 4 Real-vs-fake · 5 Create · 6 Spot the trap | 4–5 |
| **C — Own it** | 7 Mixed unseen · 8 Your game *(optional)* · 9 Result | 6 |
| **Recall** — ≥24h later, unannounced | 10 Delayed unseen | 7 |

### The stages

**1 · Understand.** Static board, knight d5, king b6, rook f6, arrows to both targets. Reuses
`EndgameLesson`'s `INTRO` phase verbatim.

```
  A fork is one piece attacking two valuable pieces at once.
  This knight attacks the king AND the rook. The king must move —
  then the rook falls.                                  [ Got it → ]
```

**2 · See the geometry.** Tap-the-square, not move-the-piece — the layer ordinary puzzles skip.

```
  Tap every square this knight attacks.      ● ● ● ○ ○ ○ ○ ○   3/8
```

Wrong tap flashes and clears with **no text** — silence is the correction. After three wrong taps
the L-shape to one unfound square animates once. Then the board flips and the question repeats for
a **black** knight: orientation transfer is a known failure mode no current surface tests.

**3 · Identify.** Three positions. *"Which two pieces could this knight attack at the same time?"*
(tap two).

**4 · Real vs fake.** Five positions, **two counterexamples**. *"Is there a fork here?"*
On a counterexample answered "Yes":

> *"The knight does attack both. But look at what happens next — they just take the knight, and
> you've traded a knight for a pawn. A fork works when they can't save both pieces, or when the
> trade that follows leaves you ahead."*

The test is **net material after the sequence**, never "is the square defended."

**5 · Create.** Three positions, scaffolding fading within the stage: necessary pieces only, fork
square highlighted → distractors added, knight highlighted → full position, nothing highlighted.

**6 · Spot the trap.** A median of 23.5 of ~34 legal moves "prevent the fork" (**E3.2**), so asking
the user to prevent it is not an exercise. The discriminating question is which single move walks
into it.

```
  Their knight is on f3. One of these moves loses material.
  Which one would you avoid?

  [board; four candidate destination squares highlighted — tap a square
   or its arrow. SAN appears as a small secondary label.]
```

Then *"Right — after Qd7, Nc5 hits your queen and your rook."* → `[ Show me ]` animates it.

After the animation, close with the reusable lesson — the same sentence Stage 8 ends on, so the
habit is stated identically in both the general and the personal case:

```
  Before moving your queen or rook, scan every square their knight
  can jump to.
```

We do **not** then ask for the preventing move; there is no single right answer.

**7 · Mixed unseen.** Six positions. **The word "fork" never appears.** Two contain no tactic.
*"Something may be available here. What do you notice?"* → `[ There's a tactic ] [ Nothing here ]`
→ *"Show me."* This is the rung-6 test.

**8 · Your game — optional bonus, role-reversed.**

```
  1. Board at fen_before:   "You played Qd7."
  2. Qd7 replays automatically.
  3. At fen_after:          "If you were your opponent, where would you
                             move the knight?"
  4. User plays the fork — against their own former self.
  5. "Before moving your queen or rook, scan every square their knight
     can jump to."
```

Discriminating, legal (3,395/3,395 verified post-hotfix), personal, and it teaches the scan rather
than a move. Candidate pool: **≤32 users, median 4 positions, max 18** — but these are
Gold-*eligible*, not reviewed. Real coverage is determined after authoring (**E3.4**), and Stage 8
stays optional regardless. **Skipped silently when unavailable, never
faked, excluded from every rung, and never gates completion.**

Only rows with `provenance == "exact"` may print a game or date; 11% of stored rows match several
games and have their attribution cleared (**E1.4**).

**9 · Honest result.**

```
  Where you are with knight forks

  ✓  You see the knight's attack map              8/8 squares, no help
  ✓  You find both targets                        3/3
  ✓  You spot a fake fork                         2/2
  ~  You find them in a full position             4/6 unprompted
  ·  You still miss them in your own games        not measured yet

  Next: I'll show you one of these again in a couple of days,
  without telling you what it is.
```

Not "Lesson complete." Not a percentage. Not a trophy.

**10 · Delayed recall.** ≥24h later, inside the normal `/training` session, interleaved, no pattern
name. Three positions, one a counterexample. Rung 7 — **measurable entirely inside training,
independent of Track A.**

### Wrong-answer coaching

*"Incorrect — Nf6 was best"* teaches nothing. Every wrong answer names what the player failed to see.

| Failure | Detected by | Response |
|---|---|---|
| Didn't see the attack map | Tapped an unreachable square | *"A knight moves in an L. From d5 it can't reach d7."* |
| Found one target, missed the second | One correct, then stopped or wrong | *"The queen, yes. There's a second piece in that same knight's range."* |
| Saw the fork, missed the follow-up | Chose a fork whose sequence loses material | *"Play it out — they take the knight. Count what you're left with."* |
| Found a tactic, not the fork | Different sound move | *"Not a bad move. But there was something bigger — one piece hitting two."* |
| Assumed a tactic existed | "There's a tactic" on a clean position | *"Nothing here. Part of seeing tactics is knowing when there isn't one."* |
| Right idea, wrong order | Second move of the sequence first | *"Right idea, wrong order. Fork first, then take."* |

**Failure exit — mandatory.** After **two consecutive wrong answers on one position**, stop. Show
the answer with the geometry drawn, mark the stage `shown`, move on. A `shown` stage **cannot count
toward rung progression**. Endless retry is how people quit.

---

## 3. In scope (V1)

1. **One pattern, learner-facing: knight forks.** The engine is designed so pin and skewer can
   follow; no pin or skewer content ships.
2. **Sessions A–C plus delayed recall**, per §2.
3. **A generalised lesson component** derived from `EndgameLesson.jsx`'s phase machine.
4. **Tap-the-square / tap-the-arrow interaction.** Never a SAN-only choice.
5. **The mastery ladder** — rungs 1–7 live, rung 8 shown as *"not measured yet"*:

   | Rung | Meaning | Measured by |
   |---|---|---|
   | 1 | Introduced | Stage 1 complete |
   | 2 | Recognises with visual help | Stage 2 with hints |
   | 3 | Identifies geometry independently | Stages 2–3, zero hints |
   | 4 | Solves clean examples | Stage 5, positions 1–2 |
   | 5 | Handles both directions | Stage 5 pos. 3 + Stage 6 |
   | 6 | Recognises in mixed unseen positions | Stage 7, unprompted, incl. negatives |
   | 7 | Retains after a delay | Stage 10, ≥24h, unannounced |
   | 8 | Applies it in real games | *gated on Track A* |

6. **Move grading reads the canonical evidence through the shared promotion predicate.**
   A Stage 8 answer is **correct** if the move is legal and either it is the stored
   `opp_creates_motif`, or `caption_facts.multi_target_attack_evidence` reports a shape with
   `attacker_piece_type == "knight"` and `via_moving_piece` that passes `is_named_fork()`.
   Exact-move grading is banned: it reintroduces false negatives the moment two moves both fork.

   **Two layers, deliberately separate.** The evidence records chess truth: a piece that checks the
   king while attacking a pawn *is* a fork, and the canonical detector says so — the enemy king is
   folded in as a **forced target** (`value_cp = 0`, `is_forced = true`) so it can never enter
   material arithmetic. Product policy lives in one shared predicate:

   > **`is_named_fork(shape)` — at least one WINNABLE target worth a minor piece or more.**
   > The king never counts toward it. `FORK_MIN_NAMED_TARGET_CP = 300`.

   **Enforced by a derived view, not by convention.** `extract_facts` emits
   `named_fork_evidence` — the promoted subset, produced solely by `is_named_fork()`. Every
   user-facing surface reads that view: the R02 caption rule, the `_p_tac_fork_pattern` principle,
   `motif_profile_service` fork claims and drill positions, and `player_identity`. Raw
   `multi_target_attack_evidence` is retained for geometry audits and detector research only. The
   one deliberate exception is `caption_facts_verified`'s "does this move have any coaching reason"
   check, which correctly stays on raw — a pawn-only royal fork does give the move content.

   Without this, one surface could say *"check, and it attacks a pawn"* while another says
   *"you keep getting forked"* and serves the same move as a fork drill. A pawn-only royal fork is
   not silenced — it routes to the existing check explanation.

   Three gates protect the evidence itself: the other target already passed SEE, the check comes
   from the piece that just moved, and the checking piece survives SEE on its own square. That last
   one is where `pattern_confidence/fork.py:120` was too lenient (**E3.3**).

   **Piece-agnostic**: it keys off "the checking piece", never off knights. The lesson filters to
   knights; the detector and the predicate do not.

7. **Position confidence classes.** No position teaches without one.

   | Class | Bar | Used for |
   |---|---|---|
   | **Gold-eligible** | Canonical `multi_target_attack_evidence` passes `is_named_fork()` with `attacker_piece_type = knight` and `via_moving_piece = True` · not a mate line by explicit `mate_info`. **183 candidates today** | the pool review draws from |
   | **Gold** | A Gold-eligible candidate **that a human has reviewed and accepted** | Stages 1, 3, 4, 5, 6, 8 |
   | **Verified** | Detector + engine agree, no human pass | Stages 7, 10 |
   | **Inferred** | Broad tag only (`missed_tactic`, `tactical`) | Never used here |
   | **Rejected** | Ambiguous, competing ideas, tag mismatch, unclear solution | Discarded, reason recorded |

   **Gold-eligible is not Gold.** Eligibility is machine-decidable; Gold requires human review.
   The 183 figure is the size of the *pool*, not the amount of teaching content we have — the
   entry-copy gate and Stage 8 coverage must be recomputed from reviewed positions only, never from
   the candidate count (**E3.4**).

   The v4 bar was also self-contradictory: it required "detector fires" while admitting 16 positions
   where the detector did not. Eligibility is now defined **as** the shared predicate, so the two
   cannot diverge.

   `via_moving_piece` is asserted **per asset during authoring**, not via a blocking global sample.

8. **Counterexamples: 12, hand-authored**, each passing four gates — detector must not fire (or
   fires but the sequence loses material), engine confirms no winning tactic by **net material after
   the sequence**, independent chess review, and `/check-voice`.

9. **Stage 6 distractors: hand-picked.** Per Gold position, exactly one move that allows the fork
   plus three legal, plausible, positionally sound alternatives — no obviously silly answer — each
   engine- and detector-verified and human-reviewed. No generation rule is built.

10. **Sourcing.** Teaching positions from `lichess_puzzles` (`themes: fork`, knight-filtered on the
    solving move, 62% hit rate at 400–1000, rating-banded). Personal positions from the post-hotfix
    reconstructed records, deduped by `(game_id, opp_creates_motif)`, `provenance == "exact"` for
    anything that names a game or date. Counterexamples hand-authored.

11. **Stage-level instrumentation from the first commit** — every tap, hint, wrong answer and
    failure exit, keyed to stage and position ID.

12. **Single source of truth.** `caption_facts.multi_target_attack_evidence` is the ONE fork
    signal, for every attacker type and for royal forks alike. The lesson filters it with
    `attacker_piece_type == "knight"`. `motif_profile.fork` and
    `move_observations.tactical_pattern_executed` are read-only consumers.
    `services/pattern_confidence/fork.py` — the only other recognizer that handled check-plus-piece
    forks — is **retired**: marked do-not-use, never had a production caller, kept only as an
    independent cross-check for four detector scripts. No lesson-local, frontend, or
    knight-specific recognizer may be created.

13. **Delivery — two parallel tracks, 60 days, two developers.**

    **Track A — measurement foundation** (unblocks rung 8 and the retention loop): fix the BSON
    string/datetime comparison in `check_focus_outcome`; use one canonical event time for numerator
    and denominator; backtest historical focuses; add minimum-sample and uncertainty handling;
    remove the improvement claim that fails the shuffle test; give `time_management` a measurable
    outcome; produce real results instead of perpetual `no_data`.

    **Track B — the Knight Forks pilot**: §7 item 5 (rating resolution) first, then item 6, then
    Sessions A–C, then delayed recall, instrumented throughout.

    The tracks touch in exactly one place: rung 8. Track B ships without it.

---

## 4. Explicitly out of scope (V1)

- Pin, skewer, discovered attack, loose piece as learner-facing content. Discovered (669 positions)
  and loose (919) have ample material (**E5.2**); they are excluded on **detector-attribution**
  grounds (**E2**), not content grounds.
- Automatic counterexample generation by FEN perturbation.
- Reviving `mistake_card_service`. Reuse its scheduling concepts and endpoint shapes only.
- A Stage 6 distractor-generation rule.
- The wider curriculum families: board vision, opponent awareness, chess theory.
- Any real-game transfer claim.
- Streaks, XP, completion animations, trophies.
- Numeric thresholds. Every cut point — how many of six mixed positions counts as rung 6, how long a
  delay counts for rung 7, how fast scaffolding fades — is locked against the pilot's own
  distribution via `/lock-via-data`. Picking a number before seeing the histogram is the mistake
  this project has made three times.

---

## 5. Success criteria

**Primary — pilot hypotheses, not targets.** These are what we test. At n≈15 they are not powered,
and they are revised against the pilot's own distribution via `/lock-via-data` before any is
reported as a result.

> *Hypothesis:* of beta users who complete Sessions A–C, **≥60% reach rung 6** — identifying knight
> forks in mixed unseen positions where the pattern was not named, including correctly rejecting at
> least one position with no tactic — and **≥40% reach rung 7** on delayed recall ≥24h later.

**Secondary — the readable result.** The stage at which each user *first fails* is recorded. If
failures cluster on one stage across the cohort, that stage is mis-designed and we will know which.
At this cohort size this is the finding V1 is actually for.

**Deferred to Track A (rung 8).** Among users reaching rung 7, the knight-fork `got` rate per game
after the lesson versus their pre-lesson baseline. **Not shown to any user** until Track A's
measurement passes its correctness gate: a fixed comparison window, a minimum sample, and a
shuffle-control the claim survives. The current improvement claim fails that control (66% real vs
71% shuffled) and must be removed before any new one ships.

**Cohort.** 20–25 recruited players rated 600–1200, targeting ≥15 completers. Present traffic — 4
logins in the last 7 days, 512 lifetime training attempts — cannot support a conventional
experiment (**E6**).

---

## 6. Open questions

| # | Question | Owner | Unblocking step |
|---|---|---|---|
| 1 | **Content authoring capacity.** 40 Gold positions + 12 counterexamples + 3 distractors per Gold is the largest cost in V1 and it scales with the Gold count. Is it one person or split? | **Mohit to assign** | Author 5 Gold + 2 counterexamples as a timed pilot batch, measure minutes-per-asset, then size the rest from the real rate rather than an estimate |
| 2 | **Independent chess reviewer.** §3.8 and §3.9 both require a human who is not the author. Who? | **Mohit to assign** | Name the reviewer before authoring starts, so review is not retrofitted; Parth is the obvious candidate given prior caption-review history |
| 3 | **Recruitment channel.** 20–25 players rated 600–1200, ≥15 completers. | **Mohit to assign** | Decide channel (existing 64-user base has only ~26 in band and 4 weekly actives, so this likely needs outside recruitment); draft the invite and the consent line before Track B ships |
| 4 | ~~Royal-fork floor~~ — **CLOSED.** 300 cp confirmed by Mohit 2026-08-13 as the minimum for a *named/teaching-grade* fork, not as the definition of whether a fork exists. Moved out of the detector into the shared `is_named_fork()` promotion predicate. | — | Closed |
| 5 | ~~Uniform vs royal-only naming floor~~ — **CLOSED.** Ratified by Mohit 2026-08-13: 300 cp applies uniformly to normal and royal shapes. Royal-only rejected (leaves pawn+pawn named while equivalent royal shapes are suppressed); 500 rejected (loses valid minor-piece forks); no floor rejected (demonstrated caption noise). | — | Closed |
| 6 | **Recompute scope.** The fork recompute (§7 item 14) shifts the `got` distribution, so the p70-locked `_verdict` mastery boundaries need refitting. Refit against the post-recompute distribution, or hold the old boundaries and accept drift? | **Claude to measure, Mohit to decide** | Blocking for fork drills only. Run the recompute on a sample first, then `/lock-via-data` on the new distribution |

*Resolved and removed: whether Stage 8 stays in V1 (yes — Mohit, §7).*

---

## 7. Pre-code requirements

| # | Requirement | Status |
|---|---|---|
| 1 | Semantic audit of `made_sound` for fork/pin/skewer | ✅ **Discharged** — E2 |
| 2 | Gate 4 expanded: knight share, reconstructability, coverage, multi-answer, manual sample | ✅ **Discharged** — E3 |
| 3 | Fix the `got_positions` contract; backfill; fix both consumers | ✅ **Shipped** — `25e0114c`, verified 3,395/3,395 |
| 4 | Mate gate on explicit `mate_info`, not a cp proxy; reclassify | ✅ **Discharged** — E4, 64 gold |
| 5 | Detect ambiguous provenance joins; quarantine game/date attribution | ✅ **Discharged** — E1.4, 373/3,395 quarantined, 0 leaks |
| 6 | Fix `/training/prescribed` difficulty to use `rating_resolver.get_current_rating` | ⬜ **Open — blocking.** Two days. **Track B starts here** |
| 7 | Correct the stale audit comment at `motif_profile_service.py:15` | ⬜ Open — one line |
| 8 | Author 40 Gold + 12 counterexamples + 3 distractors per Gold, through the §3.7–3.9 gates | ⬜ Open — the main content cost; see §6 Q1 |
| 9 | Recruit 20–25 players rated 600–1200 | ⬜ Open — see §6 Q3 |
| 10 | Optimise the pre-commit hook (one `grep` per file, not per line) | ✅ **Discharged** — `6e094a87`. 469,113 ms → 85 ms on `coach_play.py` |
| 11 | Royal-fork support in the canonical detector; retire `pattern_confidence/fork.py` | ✅ **Discharged** — `de9f6d11` |
| 12 | Move the 300 floor out of the detector into a shared promotion predicate; behavioural tests | ✅ **Discharged** — `is_named_fork()`, 10 behavioural tests, no new regression |
| 13 | Wire every user-facing fork consumer to the derived `named_fork_evidence` view; de-duplicate `_p_tac_fork_pattern`'s threshold | ✅ **Discharged** — R02, principle path, motif profile (4 sites), player identity |
| 14 | **Recompute stored `motif_profile` fork rows, then refit the `_verdict` mastery boundaries** | ⬜ **Open — blocking for any fork drill or Stage 8 content.** 35% of drill positions change credit even though totals barely move (**E3.4a**) |
| 15 | Correct the stale audit-status block at `motif_profile_service.py:15` | ✅ **Discharged** — replaced with the per-motif geometry/attribution table |

**Decisions recorded (Mohit, 2026-08-13):**

1. **Cohort** — 20–25 real players rated 600–1200, ≥15 completers.
2. **Stage 8** — stays in V1. It is the screen that turns a good tactics course into a coach who
   remembers your games. Optional, never affects rungs or completion; a median of 2 positions is
   enough because it is a reflection moment, not a repetition pool.
3. **Stage 8 grading** — accept any legal move that creates the verified fork, not only the
   historical move (§3.6).
4. **Track B sequencing** — starts with the rating-resolution fix.
5. **Counterexamples** — engine verification, detector verification, independent chess review,
   `/check-voice`.
6. **Stage 6 distractors** — hand-picked for V1; no generation rule.
7. **Gate 3** — approved, shipped and pushed ahead of this signoff.
8. **Product direction** — approved. Formal signoff pending the corrections in this revision.

No code beyond items 6–7 starts until this document is signed.
