# Personal Curriculum — Scope

**Status:** SIGNED OFF 2026-08-28 — Mohit: 'okay, go ahead.'

## 0. Existing surfaces audit

ChessGuru already contains most of the raw capabilities needed to teach new chess knowledge, but they are exposed as separate products rather than one relationship with a coach.

### What already exists

- **Home** presents a coach conversation, an active improvement focus, and one recommended action. It mainly speaks about what the coach has observed in the student's games.
- **Learn (`/lab`)** presents a rating-aware “Learn next” card, mastery panels, coaching patterns, game-review material, and session-review material. It currently carries too many jobs: syllabus, game laboratory, mastery tree, and review history.
- **Study (`/openings`)** presents the student's opening repertoire, opening performance, mastery labels, a weak-opening recommendation, interactive opening lessons, and an endgame catalogue.
- **Training** contains recurring-mistake puzzles, skill drills, diagnostic-driven practice, prescribed training, and community positions.
- **Play with Coach** can teach openings during play, warn about traps, launch inline trap and endgame lessons, ask teaching questions, and track whether an idea was used.
- **Diagnostics** estimate a player's level across a set of concepts and nominate a weakness.
- **Progress** reports recurring weaknesses, clean streaks, improvement proof, tracked patterns, and concepts the student has beaten.
- **The student model** already records several kinds of evidence: concepts seen, lessons attempted, opening practice, trap outcomes, endgame outcomes, mastery states, and application in games.
- **The curriculum tree** already selects a next skill using rating and prerequisites, but it exposes hard tiers and dependencies that do not always reflect an individual student's needs.

### Overlap

- Home, Learn, Study, Training, and Play with Coach can all recommend or deliver a learning action.
- Learn, Study, Progress, and Diagnostics all show some version of level, mastery, weakness, or what comes next.
- Opening knowledge is represented in opening lessons, opening walkthroughs, quizzes, coached play, opening progress, and skill drills.
- Traps and endgames exist both as browsable content and as lessons launched from coached play.
- Several mastery systems describe similar student states with different vocabulary.

### Genuine missing value

ChessGuru does not yet turn those capabilities into one coherent teaching relationship. The student still has to decide where to go, understand the difference between Learn, Study, Training, and Lab, interpret locked skills, and connect a lesson to later practice and real-game use.

The missing product is a coach-owned Personal Curriculum that decides what this one student should learn, explains why, delivers the right form of teaching, remembers the result, schedules review, and notices later application.

### Decision: REPLACE the player-facing learning journey

ChessGuru will replace the fragmented Learn/Study/Training curriculum experience with one coach-led learning journey. Existing lesson content, drills, detectors, game evidence, and teaching engines remain valuable and will be reused. The current skill-tree wall, hard player-facing locks, duplicated recommendations, and competing learning vocabularies will not remain as the primary experience.

Prerequisites and rating bands may guide the coach internally, but they will not behave like arbitrary locked doors. A student can browse any subject; the coach clearly distinguishes “what I recommend now” from “what you may explore.”

## 1. What it is

Personal Curriculum makes ChessGuru feel like one attentive chess coach working with one student. The coach remembers what the student understands, chooses one useful new idea at a time, teaches it in language appropriate for a 600–1500 player, gives help only when needed, revisits the idea before it is forgotten, and watches future games for evidence that the student can use it. It joins two forms of improvement into one relationship: repairing recurring mistakes and expanding the student's chess knowledge.

## 2. What the user sees

### Home: the coach sets today's direction

The student does not see a course dashboard or a wall of skills. They see a short conversation and one clear session assembled for them.

```text
Good evening, Mohit.

You remembered to check whether your pieces were attacked in
both of your last games. That is becoming a real habit.

Today, I want to add one new idea:

  WHY WE CASTLE EARLY
  You already bring your knights and bishops out, but your king
  often stays in the center while the position opens.

  I’ll show you the danger, let you fix it with help, and then
  give you one position to solve alone.

                    [ Learn with your coach · 8 min ]

Later today · one quick review
The rule of the square — learned 9 days ago            [ 1 position ]
```

There is never more than one primary new lesson. A short review may accompany it. Repair work may replace the new lesson when an urgent recurring problem deserves the full session, but the coach explains that choice.

### During a lesson: one idea, shown on the board

```text
WHY WE CASTLE EARLY

Coach
“Your pieces are ready, but your king is still on e1. If the
center opens now, checks arrive with tempo. Castling moves the
king away and connects your rooks.”

                [ interactive board ]

What would you play before starting an attack?

  [ Move on the board ]        [ Give me a small hint ]
```

If the student chooses incorrectly, the coach does not merely mark it wrong:

```text
“You started the attack with h4. That idea can wait. Black can
open the center with ...d5 while your king is still on e1.
Make your king safe first, then attack.”

                         [ Try again ]
```

The lesson then changes support gradually:

```text
1. Watch me show it
2. Solve with a hint
3. Solve a different position alone
4. Use it in a short coached game
```

The student does not see those as an engineering sequence. They experience a natural coaching conversation.

### End of lesson: honest state, not instant mastery

```text
Good first step.

You understood why the king needed safety and found the move
without help in the final position.

I’m calling this “learning,” not mastered yet. I’ll bring it
back in a few days and watch for it in your games.

                  [ Play a short practice game ]
                  [ Finish for today ]
```

### A later visit: continuity

```text
Last week we learned to castle before attacking.

In yesterday’s game you did it on move 8 without a prompt,
then used the open rook on f1. That is exactly the connection
we practised.

You own this idea now. Next, I want to show you what to do
after both sides have castled.
```

### Learn: the student's plan, not a skill-tree wall

```text
YOUR COACHING PLAN

Learning now
  Why we castle early
  Understood with help · independent check is next
                                                    [ Continue ]

Keeping fresh
  Rule of the square              Review due now    [ 1 position ]
  Back-rank safety                Strong in games

Coming naturally next
  What to do after castling
  “I’ll introduce this after you use early castling reliably.”

Explore chess
  Openings · Tactics & traps · Endgames · Plans · Thinking habits
```

“Coming naturally next” is guidance, not a lock. The student can open it and read why the coach recommends waiting. They can still explore it if curious.

### Explore: simple subjects, not internal taxonomy

For a 600–900 student:

```text
KEEP YOUR ARMY SAFE
Don’t leave pieces where they can be taken.

FINISH A WINNING GAME
Simple checkmates with a queen or rook.

START THE GAME WELL
Bring pieces out, protect your king, and fight for the center.
```

For a 1000–1200 student:

```text
YOUR FIRST RELIABLE OPENINGS
Know where your pieces belong and what plan comes next.

TRICKS YOU SHOULD RECOGNIZE
Scholar’s Mate, Fried Liver ideas, and common opening traps.

KING AND PAWN ENDGAMES
Opposition, passed pawns, and the rule of the square.
```

For a 1300–1500 student:

```text
PLAY THE POSITION AFTER THE OPENING
Typical pawn structures, useful breaks, and best-placed pieces.

CALCULATE WITH A PURPOSE
Candidate moves, forcing replies, and when to stop calculating.

CONVERT YOUR ADVANTAGE
Improve the worst piece, trade at the right time, and simplify safely.
```

The rating changes examples, depth, vocabulary, and expected independence. It does not create a rigid ceiling around what the student is allowed to see.

### Progress: evidence the student can understand

Repair progress and knowledge progress appear as two parts of one story:

```text
WHAT IS CHANGING IN YOUR CHESS

Habit you are repairing
  Piece safety
  4 clean games · improving

Knowledge you are building
  Castle before attacking
  Learned → recalled → used correctly in 2 games

Knowledge that is now reliable
  Rule of the square
  Solved after 12 days without a hint
```

The player sees meaningful evidence, not competing percentages from different mastery systems.

## 3. In scope (V1)

- One coach-owned learning plan per student containing one primary item and, when appropriate, one short review item.
- A single selection decision that can choose between repairing a demonstrated weakness, teaching a new idea, or refreshing prior knowledge.
- A student-facing state vocabulary that is understandable without explanation: **New**, **Learning**, **Can do with help**, **Can do alone**, **Used in games**, and **Reliable**.
- A canonical translation layer from existing mastery and evidence systems into that student-facing vocabulary; V1 must not invent another independent mastery score.
- A complete lesson arc for each supported V1 lesson: personal reason, explanation on a board, guided attempt, independent attempt, completion reflection, and a recorded next step.
- Rating-appropriate teaching for 600–1500 players through simpler language, smaller lesson chunks, different hints, and different expectations of independence.
- Personalization using real evidence when available: games, diagnostic results, previous lessons, practice attempts, coached games, and elapsed time since review.
- A safe cold-start path when little evidence exists: teach universal fundamentals, observe the response, and adapt rather than pretending to know the student.
- Home shows the coach's chosen session and why it matters to this student.
- Learn becomes the coaching-plan home: learning now, keeping fresh, naturally next, and Explore.
- Existing opening, trap, endgame, concept, quiz, drill, and coached-play experiences are entered through the same lesson contract, even when their underlying interactive components differ.
- Explore keeps all available subjects discoverable. Recommendations may be strong, but educational content is not hidden solely because of rating or an arbitrary prerequisite.
- Play with Coach can launch a short practice game focused on the current lesson and report application evidence back to the same plan.
- Future imported and coached games can produce one of four honest outcomes for a taught idea: **opportunity did not occur**, **used correctly**, **missed when relevant**, or **evidence unclear**.
- Review scheduling uses elapsed time and demonstrated recall, while avoiding fake precision in the player-facing copy.
- Progress presents repair and knowledge expansion as one improvement story without duplicating the Learn plan.
- Analytics distinguish recommendation shown, lesson started, explanation completed, guided success, independent success, review success, coached-game application, and real-game application.
- The experience works for a student who wants to follow the coach and for a curious student who wants to browse.

## 4. Explicitly out of scope (V1)

- Authoring every chess concept, opening, trap, and endgame before launch. V1 proves the complete teaching relationship with a deliberately small, verified curriculum.
- A giant linear course covering chess from 600 to 1500.
- Public grades, Elo promises, artificial XP, streak pressure, or “complete this to unlock your next rating tier” claims.
- Hard content locks based only on rating. Rating remains an internal adaptation signal.
- Claiming mastery after one correct answer or one completed lesson.
- Treating the absence of a concept in recent games as proof that the student mastered it.
- Generating unverified chess lessons dynamically with an LLM. Lesson chess truth and required moves must be board-verified.
- Replacing recurring-mistake detection, game review, the existing focus cycle, or puzzle extraction. The Personal Curriculum coordinates these systems.
- Teaching deep opening memorization as the default for this audience. Opening lessons emphasize purpose, placement, plans, common replies, and recovery outside known moves.
- Showing the complete internal skill graph, prerequisite graph, confidence formulas, or conflicting mastery percentages to the student.
- Social learning, leaderboards, coach marketplaces, classroom tools, or competition between students.
- Fully redesigning every chessboard interaction before the curriculum loop is validated.
- Automatic deletion of old routes or data during V1. Superseded routes require a measured migration and redirect plan.
- Premium packaging decisions. Educational sequencing and commercial entitlement are separate concerns.

## 5. Success criteria

V1 succeeds only if students move through the learning relationship and retain or apply what they learned. Final numeric thresholds will be locked from baseline data before code.

- A materially larger share of returning students begins the coach-recommended learning action than begins learning from the current fragmented Learn/Study/Training entry points.
- Most students who start a lesson reach the independent attempt; explanation views alone do not count as learning.
- Students who succeed with help are measurably less likely to require the same level of help on the next review.
- Students can recall a taught idea after a delay at a rate meaningfully above their first independent attempt baseline.
- When a taught idea genuinely occurs in later games, correct application increases relative to that student's pre-lesson baseline.
- The system records **opportunity did not occur** separately, so success is never manufactured from missing evidence.
- In qualitative sessions, 600–1500 players can answer all three questions without assistance: “What am I learning?”, “Why did my coach choose this?”, and “What should I do next?”
- In qualitative sessions, players describe the experience as guidance from one coach rather than a collection of lessons or chess tools.
- Browse-oriented students can find openings, traps, endgames, principles, and thinking lessons without encountering unexplained locks.
- No existing verified lesson or evidence capability becomes unreachable during migration.

## 6. Open questions

- **Question:** Which small set of lessons should form the V1 curriculum?
  **Why unresolved:** The code contains many lesson types, but content existence does not prove teaching quality, board correctness, appropriate voice, or enough evidence volume for later verification.
  **Unblocking step:** Audit candidate lessons across fundamentals, one opening idea, one trap-defense idea, and one endgame idea; select the set with complete teach-practise-review-apply coverage.

- **Question:** What should win when urgent repair work and a due new-knowledge lesson compete?
  **Why unresolved:** The correct balance depends on student behavior and current recommendation volume, not intuition.
  **Unblocking step:** Run a data bake-off on recent users to compare candidate selection policies and inspect the sessions each would produce.

- **Question:** How many simultaneous learning items can a student retain without the experience feeling empty or overwhelming?
  **Why unresolved:** “One primary plus one review” is the product hypothesis, but current usage data must test it.
  **Unblocking step:** Measure current starts, completions, and cross-surface switching; validate with moderated sessions across rating bands.

- **Question:** Which existing mastery store is authoritative for each lesson type?
  **Why unresolved:** Concepts, openings, traps, endgames, and focus improvement currently use different stores and definitions.
  **Unblocking step:** Complete a field-level single-source-of-truth audit and define read/write ownership before designing the canonical translation layer.

- **Question:** Which current page becomes the canonical Learn route, and which routes redirect or become secondary detail pages?
  **Why unresolved:** `/lab` currently mixes learning and review, while `/openings`, `/training`, and several lesson routes own valid interactions.
  **Unblocking step:** Produce a route and content-ownership map, then visually test the proposed information architecture.

- **Question:** Should a student be allowed to override the coach's primary lesson?
  **Why unresolved:** Total rigidity weakens autonomy, but constant switching prevents continuity.
  **Unblocking step:** Test two player-facing choices: “Choose something else” versus browse-only exploration that does not replace the coach plan.

- **Question:** What elapsed-time and performance rules schedule review?
  **Why unresolved:** No numeric cadence should be selected from convention or gut feel.
  **Unblocking step:** Analyze existing attempt intervals and recall outcomes, then run the lock-via-data process.

- **Question:** What is the minimum evidence required to say an idea was “used in games” or “reliable”?
  **Why unresolved:** Opportunities differ sharply across openings, endgames, tactics, and principles.
  **Unblocking step:** Define per-lesson observable opportunities and validate detectors against reviewed games before setting thresholds.

- **Question:** How should premium entitlement affect Explore without confusing it with pedagogical prerequisites?
  **Why unresolved:** The current request concerns teaching UX, while commercial packaging has separate constraints.
  **Unblocking step:** Define entitlement language and UI only after the educational route map is approved.

## 7. Pre-code requirements

- Mohit explicitly signs off on this complete scope document.
- The route and content-ownership map identifies the future role of Home, Learn/Lab, Study/Openings, Training, Progress, and every V1 lesson route.
- A live visual audit is completed on desktop and mobile for the current Home, Learn, Study, Training, Progress, opening lesson, skill drill, endgame lesson, and Play-with-Coach teaching flows.
- The V1 lesson set is selected through a content-quality audit, and every selected lesson has verified board truth, 600–1500 voice, guided practice, independent practice, and a valid application signal.
- A single-source-of-truth audit assigns ownership for concept, opening, trap, endgame, focus, review, and real-game evidence; no new independent mastery store is permitted without explicit approval.
- The player-facing state vocabulary is mapped to existing evidence with concrete examples and contradiction handling.
- Numeric choices—including review intervals, readiness gates, evidence counts, and success thresholds—complete the lock-via-data process.
- Cold-start, sparse-data, conflicting-evidence, stale-evidence, and no-opportunity behaviors are specified.
- The replacement and migration plan guarantees that no verified existing capability becomes inaccessible and that old deep links have a destination.
- Analytics baselines for current Learn, Study, Training, and lesson flows are captured before replacement.
- The V1 mockups are tested with representative 600–900, 1000–1200, and 1300–1500 players, including at least one player who prefers browsing over recommendations.
- The pre-code audit is run immediately before the first implementation change.
