# Lesson question spec — make the printed question the question we grade

## The problem, measured

On the five piece-safety positions served to `user_206791ef6507` on 2026-09-17:

| legal moves | moves that keep every piece safe | moves the grader accepts |
|---|---|---|
| 22 | 9 | 1 (`Qe5`) |
| 28 | 8 | 1 (`exd4`) |
| 28 | 5 | 1 (`Qxg5`) |
| 37 | 19 | 1 (`Bf7+`) |
| 33 | 12 | 1 (`d4`) |

The card prints **"Which move keeps every piece safe?"**. The grader accepts
only the engine's single best move. So on position 4, eighteen moves correctly
answer the printed question and are marked wrong.

Three further faults on the same card:

1. `Of the 38 moves you can play here, 13 leave a piece where it can be taken.`
   Reads as "25 are fine". One is.
2. The follow-up offers the same three options on every board — and one of
   them ("It looks active, even if a piece can be taken") is transparently
   the wrong answer, so the question measures nothing.
3. `Ask me one question` highlights every unsafe destination and says
   "which of your moves stays off them?" — it restates the prompt and hands
   over the answer set, while still not reaching the one accepted move.

## What "all categories" means here

The 17 keys in `data/theory/tactical_patterns.json` (knight_fork, skewer,
deflection…) have **zero** stored positions between them. The categories that
actually carry supply are the cognitive-gap ones:

| category | community_puzzles | community_training_positions |
|---|---|---|
| calculation_depth | 19,460 | 31,504 |
| piece_safety | 2,252 | 7,313 |
| missed_tactic | 1,578 | 2,610 |
| king_safety | 139 | 296 |
| opening_knowledge | 103 | 307 |
| tactical_oversight | 17 | — |
| endgame_technique | 11 | — |

`learning_sessions` confirms it: 95 of 95 concept lessons ever served were
`piece_safety`. The other categories reach players through
`/training/pattern/:pattern`, which has its own hardcoded question map with
the same defect — it prints a diagnostic observation
("Which of your pieces has no defender?") while grading a single best move.

So the spec covers the seven real categories, on both surfaces.

## The rule

**The printed question must describe exactly what the grader accepts.**

That splits the categories in two, and the fix is different on each side:

- **`any_safe`** — the question is right, the grader is wrong. Piece safety is
  a *habit*, not a puzzle: many moves satisfy it. Accept any move whose
  destination survives a static exchange. `grade_destination_safety_candidate`
  already computes this and is already wired for the blind-diagnostic branch;
  it just never fires for community puzzles because those rows carry no
  `quality_id`.
- **`single_best`** — the grader is right, the question is wrong. There really
  is one tactic. Say "find it" instead of asking an observation question the
  board cannot be marked against.

Engine soundness is reported but does **not** gate correctness on `any_safe`:
a safe move that loses ground for an unrelated reason is a correct answer to
this lesson, and the feedback says so. Grading the concept we are teaching is
the point; `_destination_safety_feedback` already carries both verdicts.

## The categories

| category | accepts | printed question |
|---|---|---|
| piece_safety | any_safe | Play a move that leaves nothing of yours hanging. |
| calculation_depth | single_best | One line here runs further than it looks. Find the move that holds up two moves deep. |
| missed_tactic | single_best | There is a tactic in this position. Find it. |
| tactical_oversight | single_best | There is a tactic here that is easy to walk straight past. Find it. |
| king_safety | single_best | Your king is the problem in this position. Find the move that fixes it. |
| opening_knowledge | single_best | Find the move that keeps your opening on track. |
| endgame_technique | single_best | This endgame turns on one accurate move. Find it. |

Each carries a `task_line` that states how many moves count — "More than one
move works here" or "One move is right here" — replacing the counter sentence.

Each carries two reason options that are both real heuristics a 600–1500
player holds, so neither is guessable, plus "I am not sure yet."

## Scope

- NEW `backend/services/lesson_question_spec.py` — sole owner of question,
  task line, accepts-family and reason options per category. It replaces two
  hardcoded copies (`personalized_lesson_adapter.py:722`,
  `PrescribedTraining.jsx:736`), so it removes a duplication rather than
  adding one.
- `personalized_lesson_adapter._concept_descriptor` reads the spec.
- `personalized_lesson_adapter.grade_personalized_move` routes on
  `spec.accepts`, not on whether a row happens to carry `quality_id`.
- `teaching_engine` help text for `ask_one_question` asks a board question
  instead of restating the prompt.
- `PersonalizedLessonWorkspace.jsx` renders `task_line`.
- `PrescribedTraining.jsx` prefers the backend question.

## Not in scope

- Building detectors for the 17 empty tactical concepts. No supply exists.
- Changing what enters the puzzle pools.
- Puzzle difficulty ordering.

## Acceptance

1. For every served piece-safety position, the count of moves the grader
   accepts equals the count of destination-safe moves, and is > 1.
2. For every `single_best` category, the printed question contains no claim
   that more than one move works.
3. No category renders the "Of the N moves…" counter sentence.
4. No reason option is answerable without looking at the board.
