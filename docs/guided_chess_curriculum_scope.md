# Guided Chess Curriculum — Scope

**Status:** DRAFT — direction approved 2026-09-04; awaiting Mohit's sign-off on the complete scope.

## 0. Existing surfaces audit

ChessGuru already has enough pieces to teach openings, traps, and endgames, but those pieces do not currently behave like one coach.

### What already exists

- **Personal Curriculum** can choose a recommended subject for a student, explain why it matters, track lesson evidence, and bring knowledge back for review. This remains the player-facing home for learning.
- **Opening Study** (`/openings` and `/openings/:openingKey`) shows repertoire performance, a main-line walkthrough, practice, traps, and mistakes from the student's games.
- **Public opening guides** (`/learn/openings/:slug`) show setup order, golden rules, traps, middlegame plans, and endgame tips.
- **Play with Coach** can recognize an opening, offer opening guidance, warn about traps, and launch trap or endgame lessons during a game.
- **Game Review** can name openings, recognize known traps, and explain some opening deviations.
- **Endgame Study** (`/endgames/:categoryKey/:lessonKey`) provides an interactive board with a rule, three positions, move checking, and feedback.
- **Curriculum evidence** already records lesson starts, assisted attempts, independent attempts, completion, mastery state, and some later game-application evidence.

### What the audit found

- The opening catalogue contains **79 entries**, but only **25** have a teaching tree and **42** are game-derived placeholders with little more than a name, colour, difficulty, and usage count.
- The current authenticated opening lesson constructs **124 move steps with zero authored explanations**. The player therefore sees the fallback “A key move in this opening” instead of being taught the reason for the move.
- Opening Study is primarily an autoplayed line. Reaching the end produces “Now you know the main line,” even though the player may not have made an independent decision.
- Personal mistakes are fetched for the page but placed in a separate tab. They do not change the lesson sequence, examples, hints, or checkpoint.
- Bishop's Opening has a useful basic setup tree, but no linked traps, variations, critical positions, or move-idea records. The current experience cannot teach its real decisions or common tactical dangers.
- Trap content has three competing representations:
  - 54 traps in `backend/data/traps.json`;
  - 18 traps in a hardcoded in-game database, only 11 of which overlap by name;
  - 13 embedded trap summaries across eight opening-curriculum entries.
- The running backend and checked-out branch have drifted: the running backend
  loads 55 trap records while this workspace contains 54, and their trap-data
  and recognizer hashes differ. The running targeted trap suite passes 16/16;
  the workspace suite passes 12/16. A release cannot be called accurate while
  the tested artifact and source artifact are different.
- The production-like local corpus contains 518 stored trap encounters across
  430 of 13,927 analyses with a `trap_fires` field. The scanner infers the
  setter from move parity instead of canonical `trap_color`; 335/518 stored
  encounters (64.7%) therefore assign the wrong setter/victim role.
- Exact named-trap execution is the strongest existing behavior: all 95/95
  executions with usable engine data were within 50cp of the engine choice.
  Hidden-opportunity recall is incomplete: the guarded review path found
  10/16 engine-confirmed opportunities and missed six second-step
  punishments. The guard's ten surfaced candidates were all engine-confirmed.
- Setup occurrence alone is not opportunity truth. Of 208 reconstructed
  “player did not play the stored trap move” candidates with engine data,
  only 16 were confirmed costly misses of that move; 123 alternatives were
  engine-fine and 69 were ambiguous. Every missed-trap claim must therefore
  be decided at the actual player decision point and engine-verified.
- The legacy game analyser returns a `trap_opportunities_missed` array but
  never populates it, and its dedicated Lab component is commented out.
  Meanwhile the live PWC suggestion path matches a move-string prefix and
  cannot by itself prove that the player, rather than the opponent, should
  move next or that the advertised continuation is sound in the exact
  position.
- The canonical V5 caption state machine is the correct integration
  chokepoint: it already serves imported review and live coaching, preserves
  cross-move state, and can carry a verified trap event without introducing a
  second coaching renderer.
- Public opening guides use embedded traps while authenticated opening lessons use the 54-trap source. Two ChessGuru pages can therefore disagree about whether an opening has traps.
- In-game trap lessons use the separate 18-trap database. They stop after the trap move, mostly rehearse execution, and do not consistently teach recognition, defence, refusal, or the normal continuation when the opponent avoids the trap.
- Endgame content is split between an 18-lesson, 54-position theory tree and a separate six-lesson move-sequence file. Standalone Study and Play with Coach can therefore teach different material.
- The data is not ready for an accuracy claim: three canonical trap lines are illegal, one hardcoded trap line is illegal, and three endgame answers have incorrect SAN check notation. All 78 opening main lines and variations tested legal.
- There are several overlapping route and component implementations for opening walkthroughs, quizzes, trap practice, endgame practice, and in-game teaching. Their language, evidence, and completion rules are inconsistent.

### Overlap and genuine differentiation

- Opening recognition, ECO naming, teaching content, and player mastery are different jobs and may keep purpose-specific indexes or derived views.
- Opening plans and explanations must not be copied into recognizers, components, or fallback tables.
- A trap is one chess fact regardless of whether it appears in Study, Review, or Play with Coach. Its moves and teaching meaning require one authoritative record.
- An endgame technique is one lesson regardless of entry point. Study and Play with Coach should adapt the same lesson, not maintain separate versions.
- Personal Curriculum already owns recommendation and continuity. The new work should improve what happens inside a selected lesson, not create another learning home.

### Decision: EXTEND the Personal Curriculum and central V5 decision pipeline; REPLACE fragmented lesson and trap-detection internals

The player-facing learning journey remains Personal Curriculum, and the V5
decision pipeline remains the shared path for Review and Play with Coach.
Existing URLs and useful board components remain available, but opening,
trap, and endgame lessons will read one shared teaching contract and one
authoritative source per type. A trap encounter will be derived once as a
position-and-decision event—offered, available, executed, missed, avoided, or
refused—and every surface will consume that result. Legacy parity inference,
prefix-only claims, hardcoded or embedded copies, and stale `trap_fires`
will become compatibility views and then be removed after verified rollout.

## 1. What it is

Guided Chess Curriculum is the teaching ability inside ChessGuru's Personal Curriculum. It turns an opening, trap, or endgame from a line to watch into a short coaching conversation built for one player: why the coach chose it, what the position is asking, what choices matter, what common mistake changes the position, how to respond when the opponent varies, and whether the student can use the idea without help. The coach adapts the depth and examples from observed chess behaviour, not from questionnaires or free-form typing, and never invents chess truth with an LLM.

## 2. What the user sees

### An opening lesson selected from the player's games

```text
COACH

You already reach the Bishop's Opening in your games. The part that
costs you time is what happens after Black attacks e4 with ...Nf6.

Today we are learning one decision:
protect e4 without giving up the reason you played Bc4 first.

                         [ Show me on the board ]
```

```text
After 1.e4 e5 2.Bc4 Nf6

Black's knight attacks your pawn on e4.

3.d3 protects it with a pawn. Your knight can still develop to f3,
and your f-pawn remains free if the position later calls for f4.

What would you play here?

                         [ Move on the board ]
                         [ Give me a small hint ]
```

If the player chooses another sound move, ChessGuru does not pretend that chess has only one legal idea:

```text
3.Nc3 is playable and develops a piece. For the plan we are practising,
3.d3 is cleaner because it protects e4 immediately and keeps the next
two jobs simple: Nf3 and castling.
```

The lesson then shows a real danger rather than advertising a cheap trick:

```text
TRAP TO RECOGNISE

An early Qh5 can threaten f7, but it is not automatically a winning
attack. If Black meets the threat calmly, the queen may simply lose time.

First defend the threat. Then continue developing.

                         [ Practise defending it ]
                         [ See when White can punish a mistake ]
```

It finishes with a different position and no visible answer:

```text
NOW WITHOUT HELP

Black chose ...Bc5 instead of ...Nf6. Place your next piece and tell me
through the move what plan you are choosing.

                         [ Move on the board ]
```

### A trap lesson

```text
FRIED LIVER IDEA — DEFEND IT FIRST

Recognition: White's bishop attacks f7 and the knight has jumped to g5.
The danger begins if Black reacts with the tempting but inaccurate ...Nxd5.

1. Spot the threat.
2. Choose a sound defence.
3. See why the losing reply fails.
4. Practise the punishment only after understanding the defence.
5. Continue normally when the opponent refuses the trap.
```

The coach distinguishes a sound attacking idea from a hope-chess trap that works only after an opponent's mistake.

### An endgame lesson

```text
RULE OF THE SQUARE

You reached two pawn races this week and calculated each move separately.
This rule lets you answer the same question quickly.

I will show one race. You will solve one with a hint. Then you will solve
a different race without the rule displayed.

Finishing this lesson means “can try alone.” I will call it reliable only
after you remember it later or use it correctly in a game.
```

### A new player

With no game history, the coach says that it is still learning about the player. It starts with a universal, short lesson chosen from rating and onboarding choices, observes where help was needed, and uses that evidence for the next recommendation. It never claims the lesson was personally diagnosed when no evidence exists.

### A returning player

The coach uses recent games, repeated opening positions, active focuses, previous lesson attempts, hints used, independent answers, and later game opportunities. A requested subject remains available through Explore even when the coach recommends something else first.

## 3. In scope (V1)

- One shared lesson journey for published openings, traps, and endgames: personal reason, explain, demonstrate, guided decision, feedback with consequence, independent checkpoint, honest completion state, and return to the Personal Curriculum.
- Personal lesson introductions based on observable evidence: relevant games, repeated positions, active focuses, rating, prior attempts, and review due state. Cold-start wording must admit when the coach has little evidence.
- Rating-aware depth and language for the 600–1500 audience without hard-locking requested subjects.
- `opening_curriculum.json` becomes the authoritative source for opening teaching facts: purpose, setup, important decisions, opponent replies, acceptable alternatives, common mistakes, recovery when off-book, typical middlegame plan, and linked trap IDs.
- `traps.json` becomes the only authoritative trap-content source. Each published trap records its opening family, both sides, trigger position or sequence, the opponent mistake required, punishment proof, safe defence, refusal/normal continuation, per-step explanations, difficulty, and whether the underlying move is sound or merely practical.
- `endgame_theory_tree.json` becomes the only authoritative endgame-lesson source. Each published lesson contains a plain-language rule, recognition cue, demonstration, guided position, distinct independent position, accepted sound alternatives where relevant, common error, and transferable reminder.
- Existing recognition/ECO indexes may remain when they store recognition identity rather than copied teaching prose. They reference canonical curriculum IDs.
- Public guides, Opening Study, Personal Curriculum, Game Review, and Play with Coach receive projections from the same authoritative teaching records.
- Every published lesson passes automated JSON-schema, legal-move, FEN, side-to-move, exact-SAN, duplicate-ID, route-reachability, and required-teaching-field validation.
- Engine verification is required for tactical claims, trap punishments, losing replies, and claims that only one move works. Multiple sound moves must be accepted or explained honestly.
- LLM use is limited to optional tone adjustment from approved facts. Required moves, evaluations, names, plans, and consequences remain deterministic and verified.
- Trap learning includes recognition and defence before or alongside execution. It cannot award independent understanding for replaying a revealed line.
- Opening learning emphasizes piece placement, pawn breaks, decisions, replies, and the position after the known moves. Memorising a sequence alone cannot advance the student to “Can do alone.”
- Endgame learning hides the answer during an independent checkpoint and uses a different position from the demonstration.
- Assistance, retries, answer reveals, completion, delayed recall, and later application evidence feed the existing Personal Curriculum evidence model.
- All currently visible curriculum entries are audited. Incomplete placeholders are not presented as complete lessons; they remain searchable reference entries until they pass the publishing contract.
- Bishop's Opening is the first full opening reference implementation, including its calm main plan, common Black replies, safe aggressive options, misleading early-queen ideas, and verified linked traps or tactical warnings.
- Known illegal trap records and incorrect endgame notation are corrected before any new lesson path is enabled.
- Legacy lesson paths stay available behind a default-off migration flag until the shared path passes comparison and rollout gates.

## 4. Explicitly out of scope (V1)

- Claiming complete instructional coverage of all ECO opening variations. V1 improves every lesson ChessGuru publishes and stops presenting placeholders as finished teaching.
- Deep theoretical memorisation intended for expert or master-level preparation.
- Generating new chess lines or tactical claims dynamically with an LLM.
- Treating every aggressive opening sequence as a trap. A trap requires a specific opponent error and a verified consequence.
- Promising that a lesson completion equals mastery, rating gain, or future game success.
- Replacing the Personal Curriculum recommendation system, active-focus system, game-review pipeline, or concept detectors.
- Building another catalogue, mastery score, opening recognizer, trap database, or endgame database.
- Requiring players to write subjective essays about their style or goals.
- Hiding requested educational content solely because of rating or prerequisites.
- Completing all future content authoring in one release. New lessons will enter through the same validation and publishing contract in measured batches.

## 5. Success criteria

- A player cannot finish a published lesson seeing generic fallback copy such as “A key move in this opening.” Every decision shown has an authored, position-specific reason.
- A player cannot earn “Can do alone” through autoplay, answer reveal, or repeating the demonstrated position. The state requires a distinct unassisted checkpoint.
- The same opening, trap, or endgame presents the same chess truth in Public Guide, Study, Personal Curriculum, Review, and Play with Coach.
- Every player-visible move sequence is legal; every stored FEN and side to move is valid; every displayed SAN is exact; every tactical or forced-move claim passes the agreed verification gate.
- Bishop's Opening demonstrates the full contract end to end: personal reason, plans, replies, alternatives, traps/dangers, independent transfer, evidence recording, and coached-play continuation.
- At least one opening, one trap-defence lesson, and one endgame lesson complete the full learn → independent recall → later application evidence loop before broad rollout.
- The lesson funnel records recommendation, start, explanation, guided attempt, hint/reveal, independent attempt, completion, return to plan, delayed recall, and game application without creating a second mastery system.
- A returning player's lesson visibly changes when their evidence changes; a new player's lesson does not pretend to be based on games that do not exist.
- No published lesson links to an empty, placeholder, contradictory, or unreachable destination.
- After the measurement run-in, the new journey must improve independent-checkpoint completion and return-to-plan behaviour over the legacy lesson experience. Numeric launch thresholds are locked from observed baselines rather than chosen from intuition.

## 6. Open questions

- **Question:** Which opening, trap, and endgame subjects follow Bishop's Opening in the first migration batch?
  **Why unresolved:** The answer should reflect actual player-game coverage, lesson visits, active focuses, and observed failure frequency rather than personal preference.
  **Unblocking step:** Run read-only production aggregates, rank subjects by affected players and learning value, then lock the batch using the data-decision process.

- **Question:** What engine margin makes a move an accepted alternative rather than a wrong answer in an opening or endgame checkpoint?
  **Why unresolved:** One fixed centipawn rule will behave differently across quiet openings, forced tactics, and tablebase endgames.
  **Unblocking step:** Sample authored positions, compare candidate moves at the configured engine depth, and lock rules by lesson type from the observed distributions.

- **Question:** What minimum funnel improvement justifies replacing the legacy journey at 100%?
  **Why unresolved:** Current opening/trap lesson funnel baselines are incomplete, so a percentage chosen now would be invented.
  **Unblocking step:** Instrument the legacy and new paths during the default-off/A-B period, then set the rollout gate from measured behaviour and correctness.

- **Question:** Which of the 42 placeholder opening entries should remain public reference pages and which should be hidden until authored?
  **Why unresolved:** Some may have meaningful search or player-history value despite not qualifying as lessons.
  **Unblocking step:** Combine traffic, player-game frequency, content completeness, and route-use data into a publishing audit before migration.

## 7. Pre-code requirements

- Mohit explicitly signs off on this complete scope document.
- A feature specification defines the shared lesson response, canonical IDs, adapters, affected routes/components, rollout flag, rollback, and phased deletion of legacy sources.
- The opening/trap/endgame field matrix is written before UI work so mockups cannot invent facts the backend does not provide.
- Read-only production aggregates answer migration-order and baseline questions; numeric thresholds and ranking choices pass the data-lock process.
- The exact authoritative sources are locked: `opening_curriculum.json`, `traps.json`, and `coaching/endgame_theory_tree.json`; no fourth teaching source may be introduced.
- A source-consumer map identifies every reader of embedded opening traps, the hardcoded trap database, `endgames.json`, and legacy opening lesson data before any source is retired.
- Known illegal trap lines and endgame SAN mismatches have explicit regression cases.
- The lesson contract supports multiple accepted moves and clearly separates chess correctness, lesson preference, and stylistic choice.
- Existing curriculum evidence fields are mapped to the lesson journey; no new mastery scale is created.
- The legacy baseline and a small set of gold lesson transcripts are captured for automated comparison and human review.
- Mohit and the implementation reviewer can run the relevant backend tests and a browser-level opening/trap/endgame journey locally.
- The pre-code audit is completed after the spec and data locks, before the first implementation edit.
