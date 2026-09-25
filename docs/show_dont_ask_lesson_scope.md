# Show, don't ask — the concept lesson rebuilt

**Status: DRAFT, awaiting Mohit's signoff. No code until then.**
Written 2026-09-25 after Mohit: *"if a user really has to learn his mistakes
and keep not doing that again, how do you really want this fixed?"*

---

## The one thing wrong today

The lesson asks you to report your own thinking:

> **What did you check before choosing the move?** You played Nxg4.
> - I checked what could capture the piece once it landed.
> - I moved the piece that was already under attack.
> - I am not sure yet.

Nobody can answer that honestly. People do not remember what they checked;
they reconstruct a reason afterwards that fits the outcome. So the answer is
noise, and we grade it and store it and build a "belief" from it.

A coach never asks this. A coach **shows you what happened** and then **makes
you do it again properly**. The behaviour is the test. What you say you were
thinking is not evidence of anything.

That is the whole change. Everything below follows from it.

## What a player sees

Five screens. No multiple choice anywhere.

### 1. The moment — shown, not described

```
  FROM YOUR GAME · 14 SEPTEMBER

  [ board at the position before his move ]
  [ it plays Bxf2+ by itself, pauses, then plays Rxf2 ]
  [ a red arrow f1 -> f2 stays on the board ]

  You played Bxf2+.
  Their rook on f1 took it straight back.
```

No question. No verdict word. He watches his own mistake happen once.

### 2. The cause — one sentence he can carry

```
  The square you moved to was already being watched.
```

Transferable, no jargon, true of every position in this family. This is the
sentence he should still have in his head next week — not "Bxf2+ was a
blunder", which is about one move he will never see again.

### 3. Do it right — same position, no options

```
  [ board back to just before his move ]

  Same position. Play a move that nothing can take.
  27 moves work here.
```

- Any safe move is accepted. `accepts=any_safe` already exists and does this.
- A wrong try does **not** get a verdict. The board draws the arrow of the
  piece that would take it, the move snaps back, and it says:
  `Their rook on f1 is watching that square.` Then he tries again.
- He cannot fail this screen. He leaves it having played a safe move with his
  own hand, which is the behaviour we want, performed rather than described.

### 4. Somewhere else — the actual test

```
  DIFFERENT GAME · SAME IDEA

  [ board: another of HIS positions with the same cause ]

  Play a move that nothing can take.
```

Step 3 is practice in a position he has just been told the answer to, so it
proves nothing on its own. Step 4 is the transfer: same cause, unfamiliar
board, no warning about which piece matters. This is the screen that says
whether he learned the idea or memorised one position.

He has 203 of these moments stored, so there is always another.

### 5. The habit — identical every time

```
  Before you let go of a piece: look at the square, ask what watches it.
```

Same words every lesson in this family, deliberately. A habit is one sentence
repeated, not a new phrasing each visit.

### Later, not in the lesson — the proof

On the progress page, from real games rather than puzzle scores:

```
  You have not dropped a piece this way in your last nine games.
```

and when it recurs, which the improvement-cycle card already says well:

```
  It happened again in a real game, so we're not done yet.
```

## Why this should actually stop the mistake

The current lesson does one thing: it shows a position and marks an answer.
This does five, and each is a step the last one cannot replace.

1. **See it happen.** Most players never see the refutation, because in the
   real game they had already moved on. Showing the recapture is the moment
   the mistake becomes real.
2. **Name the cause once, plainly.** Not the move — the reason. Moves do not
   repeat; causes do.
3. **Perform the correction.** Reading that a square was watched teaches
   nothing. Playing a safe move with his own hand is the behaviour.
4. **Transfer.** Doing it in the position he was just taught proves only that
   he was listening. Doing it in a different game is the evidence.
5. **Prove it from real games.** Puzzle scores measure puzzle-solving. The
   only proof that matters is that it stopped happening when he plays.

## What we already have

Nothing here needs new detection, and nothing needs Stockfish at click time.

| Piece | Where it is |
|---|---|
| His own moments | `move_observations.subtype = destination_safety_exact` — **203** for him |
| Position + his move | stored on each observation |
| Who punishes it | board geometry, one line: attackers of the landing square |
| Grading any safe move | `accepts=any_safe`, already live |
| Arrow rendering | `PrescribedTraining` already draws an `arrows` array |
| A second position | the other 202 |
| Recurrence, for the proof | the improvement-cycle card already detects it |

The only thing missing is that `teaching_engine` returns `arrows: []` on a
wrong move — the information is computed to grade him and then discarded.

## In scope

- Replace the reason question with screens 1–5 for `piece_safety`.
- Return the punishing arrow on a wrong attempt instead of an empty list.
- Pick screen 4's position from a **different game** with the same subtype.
- One habit sentence per category, authored once.

## Out of scope for v1

- The other five categories. Same five screens, different sentence — but only
  after this one is seen to work.
- Spaced repetition / scheduling when a lesson returns.
- The proof line on progress (the recurrence half already exists).
- Removing the reason question anywhere it is not `piece_safety`.

## Decisions I need from Mohit

1. **Does the lesson ever show the answer?** My view: no. Unlimited tries, the
   arrow tells him what is wrong each time, so a player can always get there
   himself. Showing the move ends the thinking.
2. **"Safe" means nothing can take it on that square.** A move can be safe
   there and still lose to something else entirely. Do we accept it, and let
   the next lesson handle the other cause? My view: yes — one lesson, one
   idea.
3. **Is screen 1 animated, or two static boards?** My view: animated once,
   with a replay control. It is the difference between watching your mistake
   and reading about it.

## What would say this failed

`destination_safety_exact` keeps firing at the same rate in his real games
after he completes the lesson. That number already exists per user, so this
is measurable without building anything new — and it is the only success
criterion that counts.
