# Show it before you ask for it — endgame lesson demonstrations

**Status: DRAFT, awaiting sign-off. No code written.**
Written 2026-09-19 against the 20 endgame lessons / 60 positions in
`backend/data/coaching/endgame_theory_tree.json`.

---

## The complaint, in one position

Lucena is the textbook example of a technique nobody works out by being asked.
You build a bridge with the rook; it takes four precise moves and the reason
only becomes visible once you have seen it happen.

Here is the whole lesson as it exists today:

```
prompt            "White to play. How does the king escape the checks?"
correct_move_san  "Rf4"
wrong_example_san "Kd7"
idea              "Build a bridge: the rook shields the king from checks."
on_correct        ...
on_wrong          ...
rule_reminder     ...
```

A board, a question, and a verdict. The player either already knows Lucena, or
they guess, get told they were wrong, read a sentence, and move on. That is a
quiz. Three lesson sessions have ever touched Lucena.

## What the player should get instead

**Step 1 — watch.** The coach plays the winning method out, one move at a time,
saying what each move is for. The player presses next, or lets it run.

```
   [board: Lucena position]

   ▸ Rf4      "First, the rook steps to the fourth rank. It is not
               attacking anything yet -- it is building a roof."
   ▸ Kd7      "Black checks from the side, which is all Black has."
   ▸ Rf5      ...
   ▸ ...      "...and there is the bridge. The rook blocks the check,
               the king walks out, the pawn promotes."

   [ Let me try it ]
```

**Step 2 — then the existing question**, unchanged. Same prompt, same grading,
same `on_correct` / `on_wrong`. Now it is a recall exercise after teaching,
instead of a cold guess.

That is the entire change in experience: **show, then ask**, instead of ask.

---

## What already exists, and what doesn't

Checked before proposing anything.

| Piece | State |
|---|---|
| A board that steps through a line of SAN moves, with prev/next/skip and autoplay | **Exists** — `frontend/src/components/InteractiveChessBoard.jsx`, used today by `OpeningRepertoire.jsx` only |
| Per-move narration on that board | **Missing.** It takes `showCoaching`, a single string for the whole line. It animates; it does not narrate. |
| Demonstration data on the lessons | **Missing.** 0 of 60 positions have a move sequence to show. |
| A replay mechanism in lessons | **Missing.** `auto_played_moves` sounds like one and is not: the backend returns SAN strings and `useTeachingMode.js` renders them as a **chat line** — *"Opponent played e4, e5. Your turn!"*. Nothing moves on the board. |

So the board component is most of the engineering, and it is already written.

### Field coverage across the 60 positions

```
60/60   fen, prompt, correct_move_san, wrong_example_san,
        idea, on_correct, on_wrong, rule_reminder
51/60   expected_result
 9/60   verification
 3/60   teaching_focus, help_squares, square_corners, reason_contract
 0/60   demonstration
```

Every lesson has the *ask* half fully authored and the *show* half absent.

---

## What gets built

**1. Data — a `demonstration` on each position.**

```json
"demonstration": {
  "moves": ["Rf4", "Kd7", "Rf5", "..."],
  "narration": [
    "The rook steps to the fourth rank. It is not attacking anything yet -- it is building a roof.",
    "Black checks from the side, which is all Black has.",
    "..."
  ]
}
```

`moves` starts from the position's own `fen`. `narration[i]` belongs to
`moves[i]`. Both lists must be the same length, and every move must be legal
from the position before it — checked, not assumed (see acceptance).

**2. Component — `showCoaching` becomes per-move.** Accept an array alongside
the existing string so `OpeningRepertoire` keeps working untouched.

**3. Wiring — the lesson surface renders the demo, then the question.** With a
skip for anyone who already knows it; nobody should be forced to sit through
Lucena twice.

**4. Silence when absent.** A position with no `demonstration` behaves exactly
as it does today. That way this can ship one lesson at a time rather than as a
60-position cliff.

---

## The real cost is authoring, not code

The engineering here is small. **60 positions × a legal line × a sentence per
move** is the work, and it is the part that decides whether this is worth
anything. A demonstration that says *"the rook moves to f4"* teaches less than
the `idea` line already there.

This is a genuine fork and I do not want to pick it alone:

**Option A — author all 60 by hand.** Highest quality, and endgame technique is
exactly the domain where a real explanation beats a generated one. Slow, and
it does not scale to openings or tactics later.

**Option B — distil them the way captions are distilled.** The house pattern:
generate offline, serve deterministic, verify every claim per-FEN. It scales,
and there is a verifier discipline to inherit. But the caption pipeline is
tuned to explain *mistakes*, and a demonstration is the opposite — explaining
why a correct move is correct, several moves deep.

**My recommendation: neither, at first.** Author **one lesson by hand**
(Lucena, since it is the clearest case for showing over asking), put it in
front of a real player, and find out whether watch-then-try actually changes
anything. If it does, that hand-authored lesson becomes the spec for whichever
of A or B we choose. If it does not, we have spent a day instead of three
weeks.

---

## Acceptance

Per lesson shipped:

1. Every move in `demonstration.moves` is legal from the preceding position,
   starting at the lesson's `fen`. Verified by replay, not by eye.
2. `narration` has exactly one entry per move, and none is empty — an empty
   string ships silently and looks authored.
3. Any factual claim in the narration is true of the board at that move. A
   narration line saying "the rook now blocks the check" must be a position
   where it does.
4. The existing question, grading and `on_correct` / `on_wrong` are byte
   unchanged. This adds a step before them; it changes nothing about them.
5. A position with no demonstration renders exactly as today.
6. The voice rules apply: no jargon a 900 would not follow, name the square,
   say the purpose rather than restating the move.

Point 6 rules out the obvious failure mode, which is narration that reads
*"Rf4. Now Kd7. Now Rf5."* — SAN already says that.

---

## Explicitly not in scope

Openings, traps, tactics or diagnostic positions. Generating demonstrations
from the user's own games. Changing which lesson gets recommended, or the
grading of any existing question. Hints or assisted retries. Everything here is
one field and one component prop.

---

## Open question for sign-off

Which lesson do we hand-author first? I have assumed **Lucena**, because it is
the strongest case for show-over-ask and because its current usage — 3 sessions
ever — gives a clean before/after. If you would rather see it on a lesson you
have actually hit while testing, name that one instead; the point of starting
with one is to aim it at a real complaint.
