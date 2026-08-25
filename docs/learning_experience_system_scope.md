# Scope: Learning Experience System

**Status:** QUEUED CONTENT v3.2 — PIC selected as the active product V1 on 2026-08-25; the signed subject-agnostic architecture remains canonical.  
**Product decision:** EXTEND the existing `/training` experience and generalised lesson authorities through PIC. Queue the knight-fork content experiment until the PIC evidence gate is resolved. Do not create a separate Academy or another open lesson library.

**Why the status changed:** the signed version treated four lesson families as V1, did not name a canonical mastery authority, and depended on an unsigned Pattern Learning scope. Those are product-contract changes, not editorial corrections, so the earlier signoff is not carried forward silently.

**v2 → v3:** baseline/post/delayed forms are now difficulty-matched and counterbalanced; admin is separated from calibration; calibration users are excluded from confirmation; the full distractor cost and the weaker self-review fallback are explicit; orphan-route findings have owners pending rather than disappearing.

**v3 → v3.1:** Pattern Learning now inherits this document's three-state learner projection and current-versus-highest checkpoint behavior. The active-recall audit found four newline-only duplicate modules; `backend/services/*` is canonical and the root copies are explicit deletion targets rather than competing logic to reconcile.

**v3.1 → v3.2:** Mohit resolved the competing-V1 conflict in favor of PIC. The knight-fork subject/content, authoring plan and fork cohorts are queued; the shared authorities, evidence tiers, learner projection with demotion, and cohort-separation rules are inherited by PIC and must not be re-derived there.

---

## 0. Existing surfaces audit

ChessGuru already has substantial teaching content and several interactive learning mechanisms. The gap is not the absence of lessons. The gap is that the mechanisms do not behave like one coach: they use different routes, different teaching sequences, different definitions of a correct answer, and different definitions of mastery.

### What already exists

| Existing surface | What the user sees today | What is worth keeping | Decision |
|---|---|---|---|
| `PrescribedTraining.jsx` at `/training`, `/training/prescribed`, and `/training/pattern/:pattern` | A personalized set of positions. The user moves a piece, receives correct/acceptable/incorrect feedback, may reveal the solution, and advances to the next puzzle. | Personal and community positions, difficulty selection, move evaluation, miss coaching, and the canonical `/training` route. | **Extend.** `/training` remains the host for guided learning sessions. |
| `SkillDrill.jsx` at `/training/skill/:skillId` | Detector-graded positions, one static hint, try again, next position, and a score at the end. | Detector-based grading that can accept more than one valid move. | Reuse the grading concept. Replace the page-specific delivery flow when a skill migrates. |
| `MotifDrill.jsx` at `/training/motif/:motif` | A non-interactive board that prints the engine's strongest move, reveals how the opponent created the motif, and tells the user to memorize the move. | Corrected personal-position contract, exact provenance, and personal fork/pin/skewer material. | Replace with the structured pattern lesson, then retire or redirect this route. |
| `EndgameLesson.jsx` | An introduction, interactive positions, correct/wrong phases, retry, arrows, completion, and a score. | The clearest reusable lesson phase machine currently in the product. | Generalise its interaction shell. Its exact-move pedagogy is not automatically inherited. |
| `OpeningLesson.jsx` and `GuidedOpeningLesson.jsx` | Learn, Practice, Traps, and Your Mistakes tabs; an autoplay walkthrough; move explanations; line rehearsal; AI practice; and opening statistics. | Authored opening ideas, main lines, opponent branches, traps, personal mistakes, and board interactions. | Preserve the content. Any migration is a separately scoped post-V1 decision. |
| `OpeningQuiz.jsx` | Concept questions, position questions, move-order entry, hints, a percentage, and an opening mastery label. | Multiple question formats and existing authored questions. | Reuse compatible questions as recall exercises. Do not keep a separate mastery model. Fix its independent correctness defect before sending more users to it: the local concept check currently treats every offered option as correct. |
| `OpeningWalkthrough.jsx` | A personal game narrated move by move, with occasional exact-best-move challenges and a Remember This ending. | Personal relevance and the idea of challenging the user at their own mistake. | Reuse personal moments inside the application stage. Do not preserve it as a disconnected learning journey. |
| Play With Coach lessons | Opening guidance, trap and endgame lesson selection, active recall, prediction, escape-square questions, pre-move checks, live feedback, and a postgame summary. | Real-game context, live application, prediction, active recall, and evidence of whether an instruction survived. | Keep Play With Coach as the application environment. Do not make its Lesson Library the primary learning front door. |
| `MissionRunner.jsx` | A briefing, a protocol, several positions, hints, a pass threshold, and completion rewards. | Short sessions, behavioral protocols, personal focus, and process-oriented language. | Keep missions for habit practice. Use the shared learning evidence when a mission rehearses a taught concept. |
| `DailyFixDrill.jsx` | A short timed set from the user's rushed mistakes, try again or skip, followed by a daily streak. | Brevity, personal relevance, and behavioral repetition. | Keep as a habit intervention, not as proof of concept mastery. |
| `DiagnosticPuzzles.jsx` | An assessment, concept-level result, headline weakness, and Start Training CTA. | Baseline evidence and a personalized starting point. | Keep diagnostic separate. It chooses where learning starts; it does not become the lesson. |
| Lab mastery panels | Separate progress displays for Engine 2 skills, tactical motifs, real-game application, openings, and active focus. | Existing evidence and the Learn navigation destination. | Keep Lab as the learning/progress home. For migrated skills, show one three-state projection plus concrete capabilities rather than several competing labels. |
| `docs/pattern_learning_system_scope.md` | A designed but not yet implemented journey for knight forks: understand, geometry, identify, counterexamples, create, trap recognition, mixed unseen positions, a personal position, honest result, and delayed recall. | The strongest pedagogy already designed in the repository and the proposed generalised lesson component. | Make it the first full lesson delivered by this system. Its signed version is authoritative for knight-fork content details. |
| `docs/one_surviving_instruction_scope.md` | One focus carried into the next Play With Coach session and evaluated after the game. | The transfer loop from learning to gameplay. | Connect completed lessons to this mechanism only where its experiment and evidence gates permit. |

### Backend teaching and mastery audit

The frontend audit was not enough. The backend already contains a generic Play With Coach dispatcher and several overlapping progress systems:

| Existing backend authority | Meaning today | V1 decision |
|---|---|---|
| `backend/services/teaching_engine.py` | Dispatches opening, trap, and endgame lesson lifecycles inside coach sessions. | **Extend its lifecycle contract.** The `/training` runner may use a different session store, but it must not invent a second start/process/exit vocabulary or a parallel lesson dispatcher. |
| `backend/services/concept_mastery_service.py` | Produces the existing user-facing `unseen / learning / studied / stale` projection from coach memory. | **Canonical learner-facing projection.** Extend this projection for migrated skills; do not add another service that publishes mastery labels. |
| `backend/services/concept_mastery_tracker.py`, `backend/services/opening_mastery.py`, `backend/services/opening_mastery_tracker.py`, `backend/services/trap_mastery_tracker.py`, `backend/services/mastery_gate_service.py`, `backend/services/pattern_progress_aggregator.py`, `backend/focus_mastery_service.py`, and coach-memory pattern progress | Record different kinds of exposure, performance, focus, recall, or gameplay evidence in different stores. | They may remain evidence producers during migration. None may independently publish a competing learner-facing status for a migrated skill. |
| `backend/active_recall_service.py`, `backend/services/active_recall_service.py`, `backend/active_recall_integration.py`, and `backend/services/active_recall_integration.py` | Two service copies and two integration copies. Each pair is byte-identical after newline normalization. The only module-level data is the same `CONCEPT_EXPLANATIONS` dictionary, which is read but not mutated; there is no behavioral divergence today. The live services integration uses bare imports that can resolve the root service copy. | **Consolidate, do not arbitrate.** Keep `backend/services/active_recall_service.py` and `backend/services/active_recall_integration.py`; replace bare imports with the canonical `services.*` path; delete both root duplicates after a reference search; add an import/duplicate guard test. The risk is latent split behavior on the next one-sided edit. |
| `pattern_decay_service.py` | Ranks how active or recently recovered a real-game weakness is (`ACTIVE / DECLINING / FADING`). | Keep as **priority/urgency**, not knowledge mastery. Its output may choose what to teach next but cannot say what the learner knows. |

The active-recall files are true duplicates, not legitimate separate concerns. Current change cost is two files for a service edit and two files for an integration edit. Routes and tests already prefer the `services` integration, making that tree the canonical survivor; its two bare service imports are the bridge currently keeping the root service copy live.

This is the single-source rule for V1: domain systems may own their raw evidence, but `concept_mastery_service` owns the status and next-step projection the user sees. Home, Lab, Training, and Play With Coach consume that projection. An architecture note must define the adapters and ownership boundaries before implementation.

### Route and product overlap found

- The navigation label **Learn** opens `/lab`, while the main exercise experience lives at `/training`.
- `/training` renders `PrescribedTraining`, but `/coach` and `/focus` render the older `TrainingNew`, which contains another puzzle trainer and another opening trainer.
- Opening learning is split across a repertoire page, a lesson with four tabs, a quiz, a personal walkthrough, Play With Coach opening teaching, and multiple opening mastery services.
- Tactical learning is split across prescribed puzzles, skill drills, motif drills, active recall, tactical mastery panels, and the planned Pattern Learning System.
- `/challenge` has no static incoming product link.
- `/training/motif/:motif` has no static incoming product link.
- `/opening-walkthrough` has no static incoming product link.
- Plateau Breaker currently links to `/plateau-breaker/training` and `/plateau-breaker/play`, but neither route is registered. This is a separate navigation bug, not a reason to add another training destination.

### Existing live defects and orphan follow-ups found during the audit

| Defect | User impact | Disposition |
|---|---|---|
| Plateau Breaker sends users to two unregistered routes. | A user follows a coaching CTA and hits a dead destination. | Separate frontend fix. **Owner is currently unassigned; Mohit must assign one.** It is not bundled into the fork lesson. |
| `OpeningQuiz.jsx` accepts any offered concept option in its local correctness check. | A wrong answer can be celebrated as correct and corrupt an opening result. | Separate correctness fix. **Owner is currently unassigned; Mohit must assign one.** Opening expansion cannot begin until it is fixed, but it does not block the fork-only V1. |
| `/challenge` is registered but has no static incoming product link. | Discoverability and real usage are unknown; “orphaned” is not proven from a static search alone. | **Unassigned and not V1.** Instrument entries and search backend-provided links before deciding to retain, link, or redirect it. |
| `/opening-walkthrough` is registered but has no static incoming product link. | A potentially useful personal opening surface may be unreachable through normal navigation. | **Unassigned and not V1.** Instrument entries and audit dynamic links before any later opening migration decides its fate. |

### Measurement history and current observability

This repo has already built measurement infrastructure without completing the intended study twice:

- the 12-week behavior study has enrollment and outcome infrastructure, but the available records do not prove that the study progressed beyond enrollment;
- the Universal Habit Coach randomized holdout was designed but did not run at its intended scope;
- the documented study roster contains only 16 users across a wide rating range, so a cohort average cannot carry a reliable product claim;
- the existing training pages do not share lesson-start, stage, abandon, hint, reveal, resume, or delayed-recall events. Current training usage and comparable return behavior are therefore **unknown**, not zero and not assumed.

V1 avoids repeating that failure. The first measurement is a within-player design: a different unseen mixed set before teaching, immediately after teaching, and after a delay. Assessment items are first grouped into parallel difficulty-matched triplets. For each player, the three items in a triplet are assigned to baseline, post-test, and delayed recall through constrained random counterbalancing, so no item is permanently the easy “post” item and no player repeats a position. Each player is compared with their own baseline.

Admin use verifies plumbing and cannot estimate item difficulty. A separately named **calibration cohort** provides first-attempt item data **before receiving fork instruction** and is excluded from the confirmatory learning analysis. Initial matching uses available puzzle rating plus verified position features; empirical calibration then checks and refines the triplets. After the assessment pool, scoring rule, and stop/continue rule are frozen, a different **confirmatory cohort** measures learning. Group summaries are descriptive and include exact denominators; they are not presented as population-level proof. If the event chain or difficulty-equivalence check cannot be verified end to end, the lesson does not enter confirmatory beta.

### Content readiness found by the audit

The last verified evidence file reports 183 machine-eligible knight-fork candidates, but **zero human-reviewed Gold positions**. It also reports 3,395/3,395 corrected motif-drill solutions legal in their displayed positions, with 3,022 exact and 373 ambiguous provenance records across motifs. These are useful source facts, not teaching-ready inventory. The live database was unavailable during this review, so the 183 figure is the last verified snapshot, not a claim about today's production count.

For V1, “usable” means the position has passed legality, orientation, answerability, provenance, competing-idea, grading, and human teaching review. On that definition the current confirmed usable count is **0**. Content authoring and review, not component coding, is presently the first feasibility risk.

### Genuine differentiation worth preserving

The existing mechanisms are not all duplicates:

- Diagnostic is for discovering the starting point.
- Home chooses what matters today.
- Lab explains the learning path and shows evidence of progress.
- `/training` is where a focused lesson should happen.
- Missions and Daily Fix build behavioral consistency.
- Play With Coach and imported games show whether learning transfers to chess.

Those roles should remain distinct. What must become shared is the experience between starting a lesson and proving that the lesson survived.

### Decision

**EXTEND existing.** Build one canonical learning journey inside `/training`, based on the generalised lesson component already proposed in the Pattern Learning System. Home, Lab, diagnostics, game review, email moments, and Play With Coach may all start or resume the same lesson; they do not create their own lesson mechanics.

Within the queued LES content work, the first lesson remains **knight forks**, governed by the signed version of `docs/pattern_learning_system_scope.md`. It is not the active company V1. Its content implementation waits until PIC reaches its explicit evidence decision; piece safety does not copy fork content, grading or detector logic.

---

## 1. What it is

The Learning Experience System is the way ChessGuru turns a weakness into something the player can recognize, practice, remember, and use in a real game. The coach chooses one useful lesson, teaches it in short interactive sessions, reduces help as the player improves, brings it back later without announcing the answer, and then watches future games for proof that it stuck. It gives patterns, fundamentals, endgames, and openings one familiar learning rhythm without turning ChessGuru into a large course library the player must navigate alone.

---

## 2. What the user sees

### A. The coach chooses the next lesson

The primary entry is a single recommendation, not a grid of subjects.

```text
TODAY WITH YOUR COACH

Learn to see knight forks

This pattern has appeared in your games.
First I'll show you the shape. Then you'll find it without help.

About 4 minutes · Session 1 of 3

                         [ Start lesson ]

Why this lesson?                         Browse lessons
```

If ChessGuru does not have enough personal evidence, the claim changes honestly without changing subjects:

```text
TODAY WITH YOUR COACH

Learn to see knight forks

This is a high-value tactical pattern at your level.
First I'll show you the shape. Then you'll find it without help.

About 4 minutes

                         [ Start lesson ]
```

`Browse lessons` is secondary. It never becomes the default task required to receive value.

### B. One consistent lesson screen

```text
Knight forks                                  Session 1 of 3
SEE IT                                            2 of 5

┌─────────────────────────────┐  Coach
│                             │
│         chessboard          │  A fork is one piece attacking
│                             │  two valuable pieces at once.
│        arrows / taps        │
│                             │  Tap both pieces this knight attacks.
└─────────────────────────────┘

Need a hint?                                      [ Continue ]
```

The board is the main teaching surface. Words explain what to look for; they do not replace seeing and doing it.

The interaction may be:

- tap a square;
- tap two targets;
- choose between a few board moves;
- move a knight;
- replay a move from the user's game.

SAN may appear as a secondary label after an action. A 700-rated player must be able to complete the lesson by looking at and using the board.

### C. Help fades rather than disappearing abruptly

The user always attempts before the answer is revealed.

```text
First attempt
  "Which two pieces can the knight attack?"

Hint 1
  "Trace the knight's L-shaped jumps."

Hint 2
  The knight is highlighted.

Hint 3
  One reachable square is shown.

Reveal
  The full geometry is animated.
  This position does not advance the user's independent checkpoint.
```

Assistance is recorded. A solved position with three hints is not presented as independent mastery.

### D. Wrong answers become coaching

Generic copy such as `Incorrect — Nf6 was best` is not sufficient.

Fork example:

```text
You found the queen. There is a second piece in the same knight's range.
Trace every L-shaped jump once more.
```

After two consecutive wrong attempts on the same measured idea, ChessGuru teaches the position, gives an easier example, and does not count the failed position as passed.

### E. The V1 lesson

#### Knight forks only

The exact stages, content confidence classes, wrong-answer diagnoses, personal-position rules, and delayed-recall contract come from `docs/pattern_learning_system_scope.md`.

The learner moves from seeing the knight's attack map to recognizing forks in mixed unseen positions, including positions where there is no fork. A personal game is an optional application stage, never fabricated when unavailable.

The first admin-only walking skeleton is deliberately thinner than the complete lesson: one recommendation opens one fork lesson; the learner attempts one unguided baseline item, receives one guided teaching interaction, answers one different unseen item, exits, resumes, and later receives one delayed recall item. The same saved state and evidence projection must survive that whole loop before the remaining fork stages are built.

Piece safety, endgames, and openings remain important product directions, but they are not V1 deliverables and their sample screens do not authorize code. Their future adapters must reuse the proven lifecycle and projection rather than expand this first experiment into a four-subject program.

### F. Honest progress, not a celebratory percentage

The lesson records eight internal evidence checkpoints:

| Internal checkpoint | Evidence meaning |
|---|---|
| 1. Introduced | The coach has shown the idea. |
| 2. Recognizes with help | The player can find it with highlights or hints. |
| 3. Recognizes independently | The player identifies the relevant geometry, rule, danger, or plan without help. |
| 4. Executes a clean example | The player can use the idea in a clear position. |
| 5. Handles variation | The player handles a counterexample, defensive reply, opponent deviation, or reversed orientation. |
| 6. Finds it in mixed unseen positions | The player recognizes when the idea is present and when it is not, without the lesson name in the prompt. |
| 7. Retains it after a delay | The player succeeds again after the configured delay, without advance warning. |
| 8. Applies it in a game | Verified game evidence shows the player used or respected the idea. |

The player does **not** see eight rungs. The learner-facing projection has three plain-language states:

| User-facing state | Meaning |
|---|---|
| **Learning** | The idea has been introduced and the player is building independent recognition. |
| **Remembered** | The player passed mixed unseen work and later recalled the idea without advance naming. |
| **Proven in games** | Verified game opportunities show the player used or respected the idea. |

`Refresh needed` is a modifier, not a fourth achievement level. It appears when new evidence shows that a previously demonstrated ability is not currently reliable.

The result screen names concrete demonstrated abilities rather than merely showing the state:

```text
Where you are with knight forks

✓ You see the knight's attack map without help
✓ You find both targets
~ You are still learning to reject fake forks
· Real-game application is not measured yet

Next: I'll mix one of these into a future session without naming it.

                     [ Done for today ]
                     [ Practise once more ]
```

No skill is called mastered because the user finished a lesson, watched an answer, or solved a repeated position.

The system stores both `highest_demonstrated_checkpoint` and `current_demonstrated_checkpoint`. Historical best never decreases and exists for audit only. Current capability can decrease:

- failing delayed recall moves the current state from **Remembered** to **Learning · Refresh needed**, at the last checkpoint the player re-demonstrated without help;
- a single real-game miss does not erase learning, because one opportunity is noisy; repeated verified misses can move **Proven in games** back to **Remembered · Refresh needed** only under a threshold locked from opportunity data;
- elapsed time alone schedules a recall check but does not demote the player;
- `pattern_decay_service` may raise the lesson's priority after recent misses, but it never rewrites mastery.

On first exposure, the unguided mixed baseline is also a test-out. A player who passes the pre-registered independent bar skips introduction and guided recognition, starts at the independent checkpoint, and receives no fake “lesson completed” celebration. They must still pass delayed recall and real-game application separately.

Every attempt stores a `content_version`. Copy-only edits may preserve evidence. Any edit that changes the FEN, orientation, accepted answer, detector meaning, hint that exposes the answer, or teaching claim is semantic: pending attempts on that asset are invalidated, historical evidence remains auditable under its old version, and the current capability is rechecked before the edited content can preserve or advance status. Historical puzzle attempts are never silently promoted into retention or application.

### G. Return, recall, and transfer

On a later visit, recall is mixed into the normal session:

```text
QUICK CHECK

Something may be available here. What do you notice?

[ There is a tactic ]    [ Nothing immediate ]
```

The lesson name is hidden until after the answer.

When an eligible concept becomes the user's active instruction, Play With Coach carries it into the game:

```text
Before this game
  One thing today: before each move, scan where every knight can jump next.

After the game
  You used the scan on 3 relevant positions.
  On move 21, you allowed Nc2+ to fork your king and rook.

Next game
  Same instruction — it has not survived consistently yet.
```

If the system cannot verify an application opportunity, it says `not measured in this game`; it does not call the lesson successful or failed.

---

## 3. In scope (V1)

- `/training` becomes the canonical place to start, resume, and complete a guided lesson.
- Home shows one primary coach-selected lesson or recall task, with one primary CTA.
- Lab shows the current lesson, learner-facing state, demonstrated capabilities, and what comes next; it does not create a second lesson runner.
- A secondary Browse option remains available for self-directed users without becoming the default experience.
- One consistent lesson shell supports board demonstration, square selection, target selection, candidate choice, legal piece movement, safe/unsafe classification, plan selection, opponent-response prediction, and replay.
- Every exercise requires an attempt before answer reveal.
- Hints progress from verbal guidance to visual help to reveal, and every hint level is recorded.
- Two consecutive failures on the same measured idea trigger a teaching exit or easier example; the failed position cannot advance a rung.
- Wrong-answer feedback identifies the missed geometry, defender, attacker, rule, plan, response, or calculation step whenever that distinction can be verified.
- Eight checkpoints remain internal evidence. The user sees only **Learning**, **Remembered**, or **Proven in games**, plus a `Refresh needed` modifier when justified.
- Completion, score, streak, lesson exposure, puzzle accuracy, retention, and real-game application remain visibly distinct concepts.
- Sessions can be safely interrupted and resume at the next unanswered interaction without losing attempt history.
- Delayed recall items can appear inside later normal sessions without naming the source lesson before the answer.
- Baseline, post-test, and delayed-recall items come from reviewed difficulty-matched triplets. Role assignment is constrained-random and counterbalanced across users; no player sees the same position twice, and no fixed form is always used after teaching.
- Admin sessions verify the journey only. A named calibration cohort estimates item difficulty from first attempts collected before fork instruction and is excluded from the later confirmatory analysis; confirmatory users receive only the frozen assessment pool and pre-registered scoring rule.
- The knight-fork lesson ships according to `docs/pattern_learning_system_scope.md`; this scope does not weaken or duplicate its content gates.
- Exact-move grading is permitted only when the chess idea genuinely has one required move. Detector-, rule-, or outcome-based grading is used when several answers are valid.
- Every authored teaching position has a declared confidence level. Unverified or ambiguous positions cannot teach or determine a rung.
- Personal-game copy names a game, date, move, or opponent only when provenance is exact.
- The user can see why a lesson was chosen. When evidence is insufficient, ChessGuru describes it as a rating-appropriate foundation rather than pretending it found a personal weakness.
- For concepts allowed by the experiment policy, the lesson's final instruction can enter the One Surviving Instruction loop and be evaluated in Play With Coach or later imported games.
- Existing route links for a migrated lesson resolve into the same lesson state. Users do not lose bookmarks or arrive at two versions of the same lesson.
- `concept_mastery_service` is the only user-facing status/next-step projection for the migrated fork skill. Other trackers may contribute named raw evidence but cannot publish a second label.
- The old page-specific progress display is removed or hidden for knight forks once the common projection is authoritative.
- Stage-level instrumentation records entry source, start, answer, answer meaning, hint use, reveal, retry, failure exit, completion, resume, delayed recall, and verified application.
- Rollout is default-off, then admin preview, then a named calibration cohort, then a separate confirmatory cohort, then measured expansion. A later lesson family cannot inherit rollout merely because the runtime is already enabled.
- V1 implementation order is: instrumented admin walking skeleton; reviewed fork content; complete knight-fork lesson; calibration and assessment freeze; confirmatory within-player test; optional verified personal application; measured expansion.
- V1 is complete only when the knight-fork lesson can be started from the recommendation surface, resumed safely, measured end to end, and produce one honest state and next step across the relevant surfaces.

---

## 4. Explicitly out of scope (V1)

- A new Academy, Courses, Explore, or Pattern Library top-level product.
- Migrating every opening, trap, endgame, motif, Engine 2 skill, mission, or puzzle category.
- Building the piece-safety, endgame, or opening adapters. They are separate post-V1 decisions after knight-fork evidence is reviewed.
- Teaching pins or skewers before their attribution gates and lesson-specific scopes pass.
- User-authored courses, custom lesson playlists, or public study plans.
- An unbounded AI lesson generator. V1 lessons use reviewed content and verified variable slots.
- AI-generated chess positions presented as teaching-grade without independent verification.
- Voice narration, animated avatars, video lessons, or live human-coach chat.
- Social leaderboards, public rankings, leagues, coins, XP redesign, or competitive streak pressure.
- Using streaks as proof of learning. Streaks may reward returning; they do not advance a rung.
- Calling a user addicted or deliberately using anxiety, loss aversion, or misleading urgency to force daily return.
- A full redesign of Home, Lab, Progress, Play With Coach, or game review beyond the entry, resume, evidence, and transfer surfaces required here.
- Replacing Play With Coach with a lesson simulator.
- Replacing Diagnostic with teaching content.
- Exact numeric success thresholds chosen from intuition. They are locked from the eligible corpus, design simulation, and calibration distribution, then frozen before the confirmatory cohort begins.
- A user-facing claim that ChessGuru improved real-game performance until the transfer measurement has enough eligible opportunities and passes its correctness gates.
- Automatic conversion of historical puzzle attempts into retained or applied rungs.
- A new mastery tracker or a new user-facing mastery vocabulary alongside `concept_mastery_service`.
- Deleting legacy routes or data before traffic, reference, and history-preservation checks are complete.
- Pricing, subscription packaging, paywall placement, or marketing claims for the ₹199 plan.

---

## 5. Success criteria

V1 succeeds only if it changes what the player can do. Session completion by itself is not success.

### Trust and correctness gates

- Every user-facing knight-fork position is legal, answerable, correctly oriented, and independently reviewed under its content confidence contract.
- No personal claim is shown from ambiguous provenance.
- No revealed, skipped, or failed exercise is credited as independent, retained, or applied.
- When several moves satisfy the taught idea, the grader does not reject a valid alternative merely because it differs from the stored move.
- Knight forks have one user-facing state and one next step across Home, Lab, Training, and Play With Coach.
- The teaching-ready content count is derived from reviewed assets, never the 183-candidate machine pool.

Any violation of these gates blocks rollout regardless of engagement.

### Learning behavior

- The fork lesson includes an unguided baseline and a different set of mixed unseen positions after instruction.
- Baseline, post-test, and delayed forms are built from difficulty-matched item triplets and counterbalanced across users. The calibration cohort's first attempts establish the matching; those users are excluded from confirmatory results.
- Each user's immediate result is compared with that same user's baseline. Delayed recall is compared with both baseline and immediate performance.
- A user-level benefit means the pre-registered post-test rule is met without reveal and the delayed rule is later met on different content. A cohort average cannot turn an individual failure into success.
- Group summaries report the number eligible, started, completed, recalled, benefited, did not benefit, and had missing follow-up. With the known small cohort they are directional evidence, not a population claim.
- The result screen's state must be reproducible from recorded attempts, hint use, reveals, delays, verified application evidence, and content version.
- A user who struggles is routed to a simpler exercise or a smaller prerequisite rather than being advanced through repeated reveal-and-next behavior.
- A user who passes the initial mixed test can test out of guided stages; recall and application remain unearned.

### Usability and return behavior

- A recommended user can start today's lesson from Home with one primary action and without choosing a category.
- An interrupted lesson resumes at the correct unanswered interaction on another visit.
- The fork lesson uses consistent navigation, help placement, result language, and resume behavior on supported mobile and desktop layouts.
- Start-to-first-action, stage abandonment, hint use, reveal use, session completion, voluntary extra practice, and delayed-recall return are measurable by stage.
- Current puzzle/drill repeat and return behavior is **unknown** because comparable events do not exist. V1 establishes a trustworthy denominator first; it does not claim to beat a fabricated baseline.
- Return and completion are diagnostic guardrails. They can reveal an unusable lesson, but they cannot substitute for within-player learning and recall.

### Transfer behavior

- Eligible completed lessons create a single short instruction that can be carried into a later game without creating a second competing focus.
- The product records eligible real-game opportunities separately from correct applications and violations.
- When no eligible opportunity occurs, the user sees `not measured`, not a fabricated success.
- Real-game transfer is reported as exploratory during V1 unless its opportunity count and correctness bar satisfy the separately locked launch gate.

### Product simplicity

- The fork lesson does not require the user to understand the difference between prescribed training, skill drill, motif drill, active recall, mission, or mastery service.
- Migrated entry points open the same lesson and the same saved state.
- The primary Home experience offers one recommended learning action; browsing remains optional.
- No new top-level navigation item is added for this system.

### Launch and kill rules

The fork lesson does not advance because users finished it or liked the visuals. It advances only after the trust gates pass and the pre-registered within-player learning and retention rule passes.

The following are explicit stop conditions:

1. **No reviewed content, no build-out.** The admin walking skeleton may use a tiny reviewed set, but calibration cannot open while the teaching-ready Gold count is zero. The timed batch includes 5 Gold positions, 2 counterexamples, and all 15 hand-picked distractors required by those five Gold positions. Time and rejection rates are recorded separately for Gold positions, counterexamples, and distractor moves; 120 of the planned 172 review units are distractors, but equal effort per unit is not assumed. If that batch plus the assessment-review sample shows the full contract cannot be produced within the named owner's approved capacity, stop the full lesson build and re-scope before adding stages.
2. **Broken event chain, no beta.** If a start cannot be followed through answer, help, completion, resume, and delayed recall with stable user/session/content identifiers, stop rollout. Measurement is part of the feature, not a later analytics task.
3. **Trust failure pauses exposure.** Any illegal position, false teaching claim, leaked ambiguous provenance, or rejection of a verified valid answer disables the affected content version until corrected and re-verified. Engagement never overrules this.
4. **No calibrated comparison, no confirmatory claim.** Admin data cannot calibrate content. If a separate calibration cohort cannot be recruited, or if the frozen triplets fail the pre-registered difficulty-equivalence check, stop before confirmatory beta rather than selecting convenient items after seeing outcomes.
5. **No within-player benefit, no expansion.** After calibration and before the confirmatory cohort starts, the assessment pool and sequential stop/continue rule are frozen. If the confirmatory rule reaches its no-benefit or harm boundary, the lesson is stopped or redesigned; it does not expand as “inconclusive” indefinitely.
6. **No usable return path, no retention claim.** If the pilot window cannot produce the pre-registered minimum delayed-recall denominator, diagnose and correct the entry/return mechanism once. If the repeated window still cannot reach the denominator, stop expansion and treat the delivery model as unproven.
7. **Failed generalisation stays narrow.** If the walking skeleton requires fork-specific branches in the shared lifecycle or a new competing mastery authority, stop the generalised-runtime work. A narrow fork lesson may proceed only after architecture review; the code must not pretend the abstraction succeeded.

---

## 6. Open questions

### Q1. What is the pre-registered within-player stop/continue rule?

- **Question:** What item-equivalence, immediate post-test, delayed-recall, missing-follow-up, and sequential stopping rule decides whether the fork lesson continues, changes, or dies?
- **Why unresolved:** The current surfaces lack comparable events, the cohort is small, and admin use cannot estimate item difficulty.
- **Unblocking step:** Before calibration, use `/lock-via-data` on the eligible pool and a design simulation to lock the calibration precision/coverage rule without seeing confirmatory outcomes. Recruit a named calibration cohort, collect first-attempt data, form difficulty-matched triplets, and freeze the pool. Then preregister the confirmatory within-player rule and run it on a different cohort. Report individual transitions and exact denominators; do not use a group mean as the launch decision.

### Q2. Is the reviewed content plan feasible?

- **Question:** Can the required Gold, counterexample, and distractor set be authored and independently reviewed at an acceptable rate?
- **Why unresolved:** There are 183 last-verified machine-eligible candidates but zero reviewed Gold assets. Candidate count is not lesson inventory, and the current Pattern scope's 40 Gold + 12 counterexamples + distractors is the dominant cost.
- **Unblocking step:** Name the author and independent reviewer; time 5 Gold positions, 2 counterexamples, and their required 15 distractor moves, plus a representative assessment-review sample. Record acceptance rate, review time by asset type, rejected reasons, and reusable distractors; then keep, reduce, or kill the content plan explicitly. By count, the planned contract is 40 Gold + 12 counterexamples + 120 distractor moves = 172 review units, but the estimate must not assume those units cost the same.

### Q3. How does rollout coexist with the one-experiment-at-a-time policy?

- **Question:** Can the admin and named beta users remain non-overlapping with Universal Habit Coach or One Surviving Instruction, or must public beta wait?
- **Why unresolved:** Shared Home, Training, and Play With Coach surfaces can change the same user's behavior and make both experiments uninterpretable.
- **Unblocking step:** Produce a cohort-and-surface overlap table for active experiments. Mohit decides whether orthogonal cohorts are sufficient or public rollout waits for the active verdict.

### Q4. When is the legacy fork route retired?

- **Question:** At what point does `/training/motif/:motif` redirect into the canonical saved fork lesson?
- **Why unresolved:** Static references are sparse, but backend action URLs, bookmarks, and history may still reach it.
- **Unblocking step:** Instrument route entry source, search static and backend-provided links, preserve historical URLs, and redirect only after the new fork lesson has parity and rollback coverage. Other lesson routes are not part of V1 retirement.

---

## 7. Pre-code requirements

No Learning Experience System product code starts until items 1–7 are discharged. Items 8–10 are required before non-admin beta. This ordering allows one instrumented walking skeleton without pretending the whole program is ready.

1. **Both scopes are signed and reconciled.** Mohit re-signs this v2 document and signs the final `docs/pattern_learning_system_scope.md`. The fork-content document is stricter on chess truth; this document is stricter on shared UX, authority, measurement, and rollout. Any conflict is resolved in writing.

2. **The fork data work is closed.** The recompute, threshold-refit decision, backup, apply-by-`_id`, and zero-change verification required by the Pattern scope are complete before personal fork content is served.

3. **The canonical authority note is approved.** It names `teaching_engine.py`'s lifecycle contract and `concept_mastery_service`'s learner-facing projection as the existing authorities to extend; defines lesson-session ownership, content adapters, grading, event schema, content versioning, evidence adapters, and route migration; and proves no duplicate detector, lesson dispatcher, or mastery label is introduced. It also consolidates active recall onto `backend/services/active_recall_service.py` and `backend/services/active_recall_integration.py`, replaces their bare imports with canonical package imports, deletes the two root duplicates after reference verification, and adds a guard test so the copy pair cannot return.

4. **The fork evidence dictionary and migration rule are executable.** Each internal checkpoint states accepted and rejected evidence, hint/reveal effects, demotion/freshness behavior, test-out behavior, content-version invalidation, and why historical puzzle attempts do or do not count. Unsupported history begins as Not measured and can test out.

5. **Content feasibility and review independence are demonstrated.** A fork author and a different qualified human reviewer are named. The timed batch contains 5 Gold positions, 2 counterexamples, and the 15 distractor moves required by those five Gold positions, plus a representative assessment-review sample. Acceptance and minutes per accepted asset are recorded separately by type before sizing the complete set. Legality, orientation, answerability, duplicate, provenance, competing-idea, multiple-answer grading, and voice checks run on all content that enters the walking skeleton. If no independent reviewer is available, engine/detector verification plus a delayed, blinded second-pass self-review may produce only `Provisional` admin content; it is explicitly weaker, cannot become Gold, and cannot enter calibration or confirmatory cohorts.

6. **The walking-skeleton contract is approved.** One recommendation, baseline item, guided interaction, different unseen item, exit/resume, result projection, and delayed recall run through one saved session. Mobile and desktop prototypes keep the board usable, do not rely on color alone, and do not force the learner to scroll away from the position while answering.

7. **Instrumentation is verified before exposure.** Stable identifiers connect entry source, lesson/content version, start, answer meaning, help, reveal, retry, failure exit, completion, resume, post-test, delayed recall, and application. A seeded admin journey is queried end to end and matches the UI state exactly.

8. **Calibration and the numeric decision rule pass `/lock-via-data`.** Admin dry runs verify plumbing only. Before calibration, the assessment-pool coverage and required item-estimate precision are locked from the eligible corpus plus design simulation. A named calibration cohort is then run and excluded from confirmatory analysis. Difficulty-matched triplets, role counterbalancing, scoring, immediate within-player lift, delayed retention, missing follow-up, minimum recall denominator, sequential stop/continue boundary, session guardrails, and any non-chess grading tolerance are frozen before the separate confirmatory cohort begins. Current usage remains `unknown`; no invented legacy baseline is used.

9. **Rollout and operational ownership are recorded.** The feature is default-off, then admin-only, then a named calibration cohort, then a non-overlapping confirmatory cohort, each with a rollback condition. Experiment overlap is resolved. Owners are assigned separately for the Plateau Breaker dead routes, Opening Quiz correctness defect, `/challenge` discoverability audit, and `/opening-walkthrough` discoverability audit; those tasks are not bundled as evidence for this V1.

10. **Implementation hygiene is complete.** Existing staged and dirty changes are inventoried and preserved; `/audit-pre-code` runs immediately before the first product file changes; no later lesson family or catalog migration is authorized by this signoff.
