# Complete Chess Curriculum Scope

Status: **signed off by Mohit on 2026-08-30 (“go go go”)**

## 0. Existing surfaces audit

ChessGuru already has most of the parts needed for a complete learning system,
but they do not yet form one complete curriculum.

The Home page shows one current coaching focus and routes the player into the
next activity. The Lab shows a learning path and a mastery ledger. Opening,
trap, endgame, skill-drill, motif-drill, review, and Play with Coach surfaces
already provide different kinds of instruction and practice. Personal
Curriculum already names six honest player states: New, Learning, Can do with
help, Can do alone, Used in games, and Reliable.

The backend already records lesson attempts and, for a small set of skills,
evidence from real games. It can promote, refresh, and demote a skill. However,
coverage is narrow and the proof rules are inconsistent. The 39-node skill
tree is dominated by 24 openings; it contains only five general concepts, four
endgames, two mate patterns, three trap groups, and one coached-play habit.
The detailed endgame catalog now has 20 verified lessons, so even existing
content is not fully represented in the learning tree. The tactical profile
tracks fork, pin, skewer, discovered attack, and loose pieces, while the
interactive tactic path is narrower still. Positional detectors for ideas such
as weak squares, space, and open files exist, but do not yet provide complete
lessons with trustworthy mastery evidence.

ChessGuru also has real personalization ingredients, but not yet one teaching
personalization system. Coach memory stores weaknesses, strengths, studied
skills, and game history. Player profiles store decayed weaknesses and a basic
concise-or-detailed preference. Chess understanding adapts some language by
tactical strength and consistency. Reflection can capture intent and
confidence, and live coaching can reference a recurring pattern or active
focus. The 2026-08-30 production audit confirmed that these are not empty
ideas: 59 player profiles have analyzed-game evidence, 58 have ranked
weaknesses, 65 coach memories contain skill progress, 61 contain weaknesses,
and 3,723 concept-understanding records exist. But only three of 69 player
profiles have any stored learning-style value, only 15 users have a populated
chess-understanding record, and the lesson flow does not yet use a player's
specific misconceptions, vocabulary, prior explanations, or response to help
to choose how the next explanation is delivered. Today ChessGuru often
personalizes what to teach; it does not consistently personalize how this
student can understand it.

There is also source overlap. Opening facts, tactical patterns, endgame
principles, phase principles, caption principles, lesson-resolution keys, and
the skill tree are stored in several places. Some are legitimate derived views;
others repeat chess knowledge and can drift. A new stand-alone curriculum file
or a separate “academy” screen would increase that problem.

The overlap is real: the proposed system teaches lessons, selects a next focus,
records attempts, and shows mastery, all of which ChessGuru already does. The
genuine addition is breadth, a systematic teaching method, transfer tests,
real-game proof, retention proof, and one coherent progression across every
kind of chess knowledge.

**Decision: EXTEND existing.** The current Learn plan remains the front door.
The current skill tree becomes the progression index and references canonical
opening, trap, endgame, and concept content rather than copying it. Existing
Home, Lab, Training, Review, Progress, and Play with Coach surfaces deliver the
appropriate stage of the same lesson. Duplicate chess-fact sources are
consolidated or generated as derived views before new knowledge is added.

Research supports this direction. The Steps Method progresses from board
vision, defending, exchanges, and basic tactical awareness into planning,
weak pawns, passed pawns, mobility, defense, minor-piece decisions, and rook
endings. Lichess's public practice taxonomy covers a similarly broad set of
tactical, mating, and endgame patterns. Retrieval-practice research supports
testing instead of repeated reading; distributed-practice research supports
review after intervening experience; chess-expertise research supports
learning meaningful piece configurations rather than isolated move strings.

References:

- https://www.stappenmethode.nl/en/step1.php/certificates.php
- https://www.stappenmethode.nl/en/lp/en_lp_h4.pdf
- https://www.stappenmethode.nl/en/step6.php
- https://lichess.org/practice
- https://lichess.org/training/themes
- https://pubmed.ncbi.nlm.nih.gov/19439395/
- https://www.sciencedirect.com/science/article/pii/S0749596X06001367
- https://www.sciencedirect.com/science/article/pii/S0010028596900110

## 1. What it is

The Complete Chess Curriculum turns ChessGuru into a personal coach that can
teach the full body of practical chess needed below 2000: board vision,
geometry, tactical patterns, mating patterns, calculation, defense, positional
weaknesses, pawn structures, piece play, openings, endgames, conversion, and
practical decision-making. It does not give every player the same course.
ChessGuru chooses one useful next lesson and teaches the same true chess idea
differently according to what this player already knows, the mistake or idea
that brought them here, the words and board relationships they understand,
the misconception they just revealed, and the amount of help that actually
works for them. It checks whether the player can recognize the idea in an
unfamiliar position, watches for a real opportunity in the player's games, and
revisits it until the knowledge is reliable rather than merely familiar.

**Personal Teaching Law:** no lesson may read like a generic chess article with
the player's name inserted. Every teaching interaction must begin from verified
evidence about this player: one of their positions or moves, their current
answer, a previously demonstrated strength or confusion, their current skill
state, repertoire, goal, or requested explanation preference. When evidence is
sparse, the coach says that honestly and learns through a short diagnostic
interaction before making a personal claim. Chess truth stays canonical; the
route into that truth, language, example, question, help, and pace adapt to the
student.

## 2. What the user sees

The player continues to see one focused coaching plan, not a wall of unlocked
and locked cards.

```text
YOUR COACHING PLAN

Make every defender count

You lost a rook because one knight was protecting two things.
Today I want you to see that shape before calculating moves.

Your path

  1  SEE THE SHAPE                         Complete
     The knight on f6 guards h7 and d5.
     If it is pulled away, one target falls.

  2  FIND IT WITHOUT HELP                 Ready now
     New position. No arrows and no theme name.
     [ Start the 3-position challenge ]

  3  USE IT IN A GAME                     Waiting for an opportunity
     I will watch both sides of your games:
     can you exploit an overloaded defender, and can you avoid one?

  4  PROVE IT STILL STICKS                Not due yet
     Review is scheduled after more games, not merely tomorrow.

Coach's evidence
  Lesson: solved independently
  Transfer position: not yet passed
  Your games: no clean opportunity measured yet

This is not "learned" yet. You understand it; now make it yours.
```

The lesson itself uses the smallest useful teaching sequence:

```text
DIAGNOSE  Infer the starting point from games; ask one small question if unsure.
NOTICE    Show the important squares, pieces, line, or pawn shape.
EXPLAIN   Connect the geometry to this player's move, idea, or prior knowledge.
CONTRAST  Change one detail and show when the rule stops working.
GUIDE     Let the player solve one position with limited help.
RECALL    Remove arrows, labels, candidate moves, answers, and the theme name.
MIX       Hide the lesson among unrelated positions so recognition is required.
TRANSFER  Test the same idea in a different-looking position.
APPLY     Create or observe a trustworthy opportunity and label its source.
RETAIN    Re-test after intervening games and refresh after a lapse.
```

The same lesson can therefore sound different without changing chess truth:

```text
Player A previously missed the defender:
  "Last game you counted the attackers but not the knight on f6. Before choosing
   a move here, point to every piece defending d5."

Player B knows the defenders but overgeneralizes the rule:
  "You already see that the knight guards two targets. Now the harder question:
   does removing it actually win either target, or can Black recapture?"

New player with insufficient evidence:
  "I do not know yet whether you missed the line or the defender. Show me what
   you think the knight on f6 is protecting, and I will start from there."
```

The mastery ledger uses evidence-based language:

```text
New → Learning → Can do with help → Can do alone
    → Used in games → Reliable

If evidence weakens:
Reliable / Used in games → Refresh needed → Learning
```

The player can open “Why?” at every state and see the actual lesson attempt,
unseen position, game, move, and detector evidence supporting the claim. If no
trustworthy real-game opportunity occurred, the product says “not measured”
instead of pretending the skill was applied or forgotten.

## 3. In scope (V1)

- Expand the existing skill tree into a complete under-2000 learning map
  covering board vision and geometry, piece safety, tactics, mating geometry,
  calculation, defense, positional play, pawn structures, openings, endgames,
  conversion, and practical play.
- Give every skill one stable identity, a player-facing name, prerequisites,
  intended rating range, canonical content reference, teachable board shape,
  common failure, and proof capabilities.
- Organize related skills into prerequisite families without forcing every
  player through a fixed course. Personal game evidence still chooses the
  current repair lesson; prerequisites and rating suitability prevent the
  coach from teaching an idea before its foundations.
- Place the player from existing game, lesson, and application evidence. Use a
  short adaptive diagnostic only when that evidence is sparse, stale, or
  contradictory; never make the player sit a full-course entrance exam.
- Maintain one evidence-based teaching profile that records known vocabulary,
  demonstrated prerequisites, recurring misconceptions, successful and
  unsuccessful explanation forms, assistance needed, transfer performance,
  repertoire, current goal, and player-requested preferences. Treat it as an
  evolving hypothesis, not a permanent label such as “visual learner.”
- Enforce the Personal Teaching Law on lesson introductions, hints,
  corrections, examples, reviews, and Play with Coach messages. Selecting a
  personal topic while rendering generic lesson text does not satisfy the law.
- Keep canonical chess truth separate from personal delivery. A lesson's legal
  position, geometry, principle, counterexample, and solution do not change by
  user; the starting example, wording, question depth, amount of help, pace,
  and connection to prior evidence can change.
- Teach geometry before jargon. Every new term is introduced through named
  squares, pieces, lines, pawn shapes, escape routes, or defenders and then
  connected to the conventional chess name.
- Teach every applicable pattern from both sides: how to use it and how to see
  or prevent it when the opponent can use it.
- Teach boundaries, not slogans. Every rule-based lesson includes a
  near-neighbor counterexample where one changed square, defender, tempo, pawn,
  or recapture makes the familiar rule fail or require modification.
- Require each complete lesson to contain an explanation, a board
  demonstration, guided practice, independent recall, and at least one unseen
  transfer position that is not a cosmetic copy of the demonstration.
- After initial learning, use mixed, unlabeled positions so the player must
  decide which idea matters before solving it. A themed exercise alone cannot
  prove recognition.
- At selected proof moments, collect a compact prediction or reason alongside
  the move so a lucky correct move cannot masquerade as understanding. The
  coach asks only what is needed to distinguish the likely misconceptions; it
  does not demand an essay after every move.
- Route a wrong answer to the diagnosed misconception: missed defender,
  ignored reply, faulty geometry, premature rule application, calculation
  cutoff, or another supported failure. Give a targeted correction and a
  different reassessment position rather than replaying the same answer.
- Separate instructional success from mastery evidence. Hints, corrections,
  revealed answers, and guided lines cannot count as independent proof.
- Use the existing six student states. A player can reach Can do alone through
  independent lesson and transfer evidence. Used in games requires a
  quality-authorized opportunity detector tied to an auditable game and move.
  Reliable additionally requires later independent recall and continued
  real-game performance after intervening games.
- Let skills without a trustworthy detector be taught and independently
  demonstrated, but never label them Used in games or Reliable. Their honest
  ceiling is Can do alone until measurement exists.
- Record opportunity separately from outcome. “The pattern did not occur” is
  not a success or failure. “Not measured” is a valid state.
- Credit correct real-game decisions as well as mistakes, using the number and
  quality of relevant opportunities as the denominator. Consistently applying
  a skill must be visible even when the player never makes the corresponding
  mistake.
- Give each graded position one primary tested skill. Secondary observations
  can update supporting evidence only under an explicit attribution rule; one
  multi-pattern move cannot silently graduate several skills.
- Record whether evidence came from a guided lesson, independent challenge,
  mixed drill, deliberately created Coach game, or organic player game, plus
  the relevant time control and time-pressure context. These sources remain
  visibly distinct in mastery decisions.
- Let Play with Coach steer naturally toward realistic opportunities for rare
  skills. A created opportunity can prove coached application but cannot be
  relabeled as organic application in the player's own games.
- Use game-count review scheduling with a calendar backstop. Daily players are
  reviewed after relevant play; inactive players are not given fake
  evidence-free reviews.
- Refresh and demote skills when later trustworthy evidence shows a lapse. The
  player keeps the history and sees why the refresher returned.
- Show one primary lesson at a time while preserving an optional Explore view
  of the complete curriculum, prerequisites, current evidence, and honest
  availability.
- Route teaching through existing Learn, Training, Opening, Endgame, Review,
  Progress, and Play with Coach surfaces. Do not create a parallel academy.
- Consolidate duplicated chess facts. The skill tree is a progression index;
  detailed chess content remains in its canonical subject source, and other
  views are derived by reference.
- Version skill definitions, canonical content, authored positions, graders,
  and detectors. When meaning or verification changes, define whether earlier
  evidence remains valid, needs migration, or triggers reassessment.
- Publish content through a visible lifecycle: draft, deterministic chess
  verification, coach review, pilot, publish, monitor, revise or roll back, and
  deprecate. A lesson teaches one transferable idea at a time and can be paused
  and resumed without losing evidence or context.
- Verify every authored position for legality and claimed outcome. Tactical and
  endgame claims use deterministic geometry, Stockfish, or tablebases as
  appropriate. Strategic lessons require a documented human-coach review plus
  engine checks that prevent false tactical claims.
- Preserve the existing personal-curriculum honesty constraints: no Reliable
  state before its delayed-recall and application rules are data-locked, and no
  application claim from a detector below the required quality grade.

## 4. Explicitly out of scope (V1)

- A separate Chess Academy, second Learn page, or second mastery ledger.
- A universal fixed course that ignores the player's own games and current
  weakness.
- Fixed “visual learner,” “verbal learner,” or similar personality labels that
  permanently decide instruction. Adaptation is based on observed performance,
  current concept, and explicit player preference, and can change.
- Fake personalization made from a first name, rating-band wording, an
  unsupported personality claim, or a generic paragraph preceded by “in your
  games.”
- Letting an LLM invent personal history, chess facts, lesson evidence, or a
  supposed misconception. Personal claims must resolve to stored evidence or
  an answer the player gave in the current interaction.
- Content aimed primarily above 2000, including deep theoretical novelties,
  exhaustive opening memorization, or rare specialist endings without measured
  relevance to the target audience.
- Calling a topic mastered because the player watched an explanation, copied a
  line, solved with hints, or passed the demonstration position from memory.
- LLM-only chess truth, automatically published lessons, or unreviewed
  generated positions.
- Giving every curriculum skill a detector by weakening detector quality.
  Unmeasured application remains honest until a detector passes its gate.
- Locking attempt counts, accuracy bars, review intervals, rating boundaries,
  skill priority weights, or detector thresholds from intuition.
- Calendar-only spaced repetition that can fire without new game evidence.
- Leaderboards, social comparison, certificates, streak pressure, or rewards
  for rushing through lessons.
- Replacing game review. The curriculum consumes evidence from review and sends
  the player back to real games; it does not become a separate puzzle-only app.

## 5. Success criteria

- A player can move from first explanation to Reliable only through four
  auditable proofs: independent understanding, transfer to a different
  position, real-game application, and later retention.
- No public “learned,” “mastered,” “used,” or “reliable” claim exists without
  the evidence required by that state. Missing opportunities render as Not
  measured.
- Every V1 skill visible in Learn has complete canonical content and a working
  route for all capabilities it claims. No card leads to an empty, generic, or
  unrelated activity.
- Every teaching interaction can answer “why this explanation for this player
  now?” with auditable evidence. If no personal evidence exists, it opens with
  an honest diagnostic instead of an unsupported claim or generic article.
- Two players working on the same canonical skill can receive different
  starting examples, language, questions, help, and reassessment paths when
  their evidence differs, while chess truth and grading remain identical.
- A wrong answer changes the next teaching action according to the supported
  misconception; repeatedly displaying the same generic hint fails the release
  gate.
- A correct answer that conflicts with the player's stated prediction or
  reason is not automatically promoted as independent understanding.
- Every independent challenge hides the answer and removes assistance. A
  guided solve never silently upgrades into independent proof.
- Every real-game application claim identifies a specific game, position,
  move, opportunity, outcome, detector version, and detector quality status.
- A later lapse returns the skill to Refresh needed and changes the active plan
  when appropriate; the system never protects a stale mastery badge.
- The same skill identity and state appear consistently on Home, Learn, Lab,
  Progress, Review, and Play with Coach.
- Adding a skill changes one canonical content source plus one progression
  reference; it does not require copying the same chess facts into multiple
  services or frontend tables.
- Published lessons and mastery evidence identify their content, grader, and
  detector versions. A rollback or material lesson change cannot leave stale
  evidence silently supporting a stronger public state.
- In coach/player validation, an evaluator can answer what was taught, what the
  player proved, what remains unmeasured, and why the next activity was chosen
  without inspecting internal data.
- Pilot thresholds for completion, application, retention, and refresh are
  accepted only after the offline bake-off and coach review defined in the
  pre-code requirements. The chosen numeric pass bars become part of the
  release gate, not an after-launch guess.

## 6. Open questions

- **Question:** Which exact skills and prerequisite order belong in the first
  complete under-2000 map?
  **Why unresolved:** External curricula provide a broad taxonomy, but the
  shipped order must reflect ChessGuru's 600–1500 game corpus and existing
  content quality.
  **Unblocking step:** Build a coverage matrix comparing Steps Method, Lichess
  themes, current ChessGuru skills, named production mistakes, and invited
  coach review. Group aliases and remove topics that do not represent a
  distinct player need.
- **Question:** Which observed signals should change explanation form for a
  particular concept, and which signals are too weak to support a personal
  claim?
  **Why unresolved:** The repository has game-derived weaknesses, skill
  evidence, a coarse concise/detailed field, and small understanding coverage,
  but no validated model connecting an explanation choice to better transfer
  for this player.
  **Unblocking step:** Define candidate signals and delivery choices, then run
  a coach-reviewed pilot comparing immediate correction, unseen transfer, help
  reduction, and later retention. Keep only adaptations that improve learning
  or player-reported clarity without weakening chess truth.
- **Question:** What is the honest cold-start interaction before ChessGuru has
  enough evidence to personalize teaching?
  **Why unresolved:** Pretending to know a new player violates the Personal
  Teaching Law, while a long questionnaire creates generic onboarding friction.
  **Unblocking step:** Prototype short board-based diagnostic choices and test
  whether they identify prerequisite knowledge or misconception with minimal
  interruption.
- **Question:** When does a changed lesson, skill definition, grader, or
  detector invalidate earlier mastery evidence?
  **Why unresolved:** Some revisions improve wording only; others change what
  was tested or whether the proof was trustworthy.
  **Unblocking step:** Classify change types and approve retain, migrate,
  reassess, and invalidate rules before content versions begin supporting
  public mastery states.
- **Question:** How many independent and delayed successes constitute Can do
  alone and Reliable for each skill kind?
  **Why unresolved:** One threshold will not fit a one-move mating pattern, a
  positional plan, an opening structure, and a thinking habit.
  **Unblocking step:** Bake off candidate graduation rules against existing
  lesson, puzzle, and game evidence; compare false mastery, activation, time to
  graduate, and later relapse by skill kind.
- **Question:** How many games should pass before review, and when should the
  calendar backstop fire?
  **Why unresolved:** The existing corpus proves review must be game-based, but
  the exact interval must balance opportunity frequency and forgetting.
  **Unblocking step:** Measure opportunity recurrence and lapse by skill family;
  lock per-family game intervals with the already-established calendar
  backstop principle.
- **Question:** Which skills can honestly support real-game application in V1?
  **Why unresolved:** Only a small detector set currently has sufficient
  semantic and attribution evidence.
  **Unblocking step:** Inventory detector reach and quality, then publish an
  application-capability matrix. Skills below the gate remain independently
  demonstrable but application-unmeasured.
- **Question:** What verifies a strategic or positional lesson when there is no
  single forced engine move?
  **Why unresolved:** Engine evaluation can reject tactical falsehoods but does
  not by itself prove that a pedagogical explanation is the right transferable
  lesson.
  **Unblocking step:** Define a positional evidence protocol combining legal
  geometry, evaluation stability across candidate moves, and counterexample
  tests before implementation. Require two independent coach reviews before
  the completed positional lessons are published.
- **Question:** Which existing knowledge files are canonical, derived, or true
  duplicates?
  **Why unresolved:** The repository contains multiple pattern, principle,
  opening, endgame, lesson, and caption sources created for different paths.
  **Unblocking step:** Complete a reader-by-reader source audit and approve a
  migration map before extending any schema.
- **Question:** What pilot behavior proves that the teaching method transfers
  beyond puzzle familiarity?
  **Why unresolved:** Pre-launch behavior cannot establish a new learning
  baseline, and lesson completion alone is not transfer.
  **Unblocking step:** Define the pilot around unseen-position success,
  opportunity-normalized real-game application, and delayed retention; lock
  sample and pass criteria before recruitment begins.

## 7. Pre-code requirements

- Mohit explicitly signs off this complete scope document. **Complete:
  2026-08-30 (“go go go”).**
- The curriculum coverage matrix is versioned before implementation. Per
  Mohit's instruction that he and the invited coaches manually verify the
  completed product at the end, their two-coach review is a publication gate,
  not a development pause. It distinguishes essential skills, aliases,
  advanced deferrals, and current ChessGuru coverage.
- The single-source audit names the canonical source and every reader for
  skills, tactical patterns, positional concepts, openings, traps, endgames,
  lesson descriptions, and progression metadata. A consolidation sequence is
  approved; no new duplicate taxonomy is created.
- The existing six-state personal-curriculum contract is confirmed as the one
  public learning-state model. Parallel mastery labels are mapped to it or
  retired from public use.
- The Personal Teaching Law is converted into an auditable rendering contract
  for every teaching surface. It names allowed evidence anchors, the honest
  cold-start fallback, prohibited fake-personalization patterns, and the
  required “why this explanation now?” trace.
- Existing player-profile, coach-memory, chess-understanding, reflection,
  curriculum-evidence, and focus signals are mapped into one canonical
  teaching-profile view. Duplicate learning-style and understanding fields are
  consolidated or made derived; a new parallel profile is not created.
- A personalization evaluation set contains paired student histories for the
  same lesson and verifies that delivery changes when evidence changes, stays
  stable when evidence does not, never invents history, and preserves identical
  chess truth and grading.
- Candidate graduation and refresh rules are stated per skill kind and run
  through the lock-via-data bake-off. The winning rules cite activation,
  evidence availability, false-mastery risk, relapse, and opportunity
  frequency.
- Review cadence candidates are measured in games and relevant opportunities,
  with the calendar backstop retained only as a safety net.
- Every skill proposed for Used in games or Reliable has an opportunity
  detector and application detector that pass the required quality surface.
  Skills without them are explicitly capped at Can do alone.
- The positional evidence protocol is written and applied to a representative
  sample of pawn-structure, weak-square, piece-placement, and planning lessons
  before implementation. Those lessons remain unpublished until the invited
  coaches complete the final human review.
- The content-authoring contract requires legal positions, answer-hidden
  independent attempts, non-duplicate transfer positions, player-level voice,
  boundary counterexamples, misconception-specific corrections, one primary
  tested skill, and cited engine/tablebase/coach evidence.
- The content lifecycle defines draft, verification, coach review, pilot,
  publish, monitoring, revision, rollback, deprecation, versioning, and
  evidence-migration ownership before new curriculum content is published.
- Existing routes are selected for each teaching capability, and every CTA is
  mapped to the exact promised activity before implementation.
- Baseline instrumentation exists for lesson start, assistance used,
  independent attempt, transfer attempt, application opportunity, application
  outcome, delayed review, refresh, promotion, and demotion.
- Focused unit, integration, and browser test plans cover the evidence state
  machine and every existing surface that displays skill state.
- The audit-pre-code checklist is completed after all numeric locks and before
  the first curriculum schema, data, backend, or frontend implementation edit.
