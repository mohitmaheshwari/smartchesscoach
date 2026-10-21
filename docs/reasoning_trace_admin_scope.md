# Reasoning Trace — admin page scope

Mohit, 2026-10-21:

> "i need a documentation from claude on the steps it took to find out why a
> move was a mistake on inaccuracy, and then tell the steps it took to get to
> those steps"
>
> "I would like to create a page on admin chessguru, where it will put all the
> samples thre, it used and the caption it generated and teh steps it took"

## What it is

A page that shows the reasoning engine thinking out loud. You pick a move the
engine faulted, and the page shows you the board, the sentence the player would
read, and every step the engine took to arrive at it — including the questions
it asked that came back empty and the answers it threw away, with the reason it
threw each one away.

A second tab answers the other half of the ask: for every question the engine
knows how to ask, where that question came from. The actual positions that
first showed the pattern, how many cards it reaches, and — where one was found
— the defect it shipped with and what fixed it.

The point of the two tabs together: the first shows the procedure running, the
second shows how the procedure was discovered. One is the engine's work, the
other is the record of the work that built the engine.

## Why it is built this way (the one design decision that matters)

The steps shown on this page are **emitted by the engine itself**, not written
by hand into the page.

This is the whole architectural choice. If the page renders prose describing
the steps, it is accurate the day it is written and wrong the first time a
question is added, a threshold moves, or a rule is promoted — and nobody finds
out, because a page cannot fail a test for being out of date. Three times this
month a check in this repo read from a source that had already drifted.

So `reason_about` records its own trace as it works, and the page renders that
trace. The page cannot describe a step the engine does not take, and it cannot
miss a step the engine does take. The documentation is the output, not a
parallel account of it.

## What the user sees

### Tab 1 — "A move, step by step"

```
┌─ Reasoning Trace ────────────────── [ random faulted move ] [ paste FEN ] ─┐
│                                                                            │
│  game 047a334a · move 13 · white · played Rae1 · engine wanted Rfd1 · 188cp│
│                                                                            │
│  ┌─────────────────┐  WHAT THE PLAYER WOULD READ                           │
│  │       board     │  ┌──────────────────────────────────────────────────┐  │
│  │   red  Rae1     │  │ Your d4 pawn was already hanging before this     │  │
│  │   green Rfd1    │  │ move. Rfd1 would have guarded it. After Rae1     │  │
│  │                 │  │ they take it with Bxd4 and keep it.              │  │
│  └─────────────────┘  └──────────────────────────────────────────────────┘  │
│                       left_it_loose · CAUSE · high confidence              │
│                                                                            │
│  THE EIGHT STEPS                                                           │
│   1  size expectation     188cp — a positional lesson is the right size  ok│
│   2  two futures          after Rae1 / after Rfd1, compared on d4        ok│
│   3  what we get to do    not reached — no plan question answered          -│
│   4  legal before, not    not reached                                     -│
│   5  is my move in the    not reached                                     -│
│   6  challenge the story  line costs 1 pawn, exactly the man named       ok│
│   7  claim vs the number  claims 100cp against 188cp                     ok│
│   8  one sentence         handed to the caption layer                    ok│
│                                                                            │
│  EVERY QUESTION ASKED, AND WHAT BECAME OF IT                               │
│   left_it_loose       CAUSE    d4 / pawp   KEPT      true after Rae1,      │
│                                            cured by Rfd1                  │
│   blocked_a_plan      CAUSE    —           no answer                      │
│   abandoned_defender  CAUSE    —           no answer                      │
│   pushed_past_support CAUSE    —           no answer                      │
│   engine_undoes_it    EVIDENCE Ra1→e1      DROPPED    nothing ever attacks │
│                                            e1, so the retreat is a choice │
│   returns_home        SYMPTOM  Ra1→e1      DROPPED    same premise fails   │
│                                                                            │
│  [ show the raw trace ]                                                    │
└────────────────────────────────────────────────────────────────────────────┘
```

Everything in the "what became of it" block is the part no existing surface
shows. A card today shows the one sentence that won. This shows the four
questions that had nothing to say and the two whose answers were thrown out,
with the board reason for each. That is what "the steps it took" means.

### Tab 2 — "Where each question came from"

```
┌─ Where each question came from ────────────────────────────────────────────┐
│                                                                           │
│  left_it_loose                               CAUSE · shipped 21 Oct 2026  │
│  "Something of yours was already hanging and you did not hold it"         │
│                                                                           │
│  HOW IT WAS FOUND                                                         │
│    Read 11 cards the engine could not explain and worked out by hand why  │
│    each move was worse. Two of the eleven were the same story, and         │
│    nothing in the system could see it.                                    │
│                                                                           │
│  THE POSITIONS THAT SHOWED IT        [board] [board]                      │
│    Rae1  best Rfd1  188cp   d4 loose before and after; Rfd1 defends d4    │
│    Rf1   best Rc1   313cp   c3 loose before and after; Rc1 defends c3     │
│                                                                           │
│  HOW FAR IT REACHES   measured on 18,920 games                            │
│    1,874 cards carry a loose man                                          │
│      520 of those the better move holds and the played move does not      │
│      493 of those said nothing at all before this question existed        │
│                                                                           │
│  WHAT IT GOT WRONG                                                        │
│    962 of its claims named a man worth less than a third of the loss.     │
│    It was the only question in the engine that did this.                  │
│    Fixed by: the man you name has to be the man who falls.                │
│    58% of those claims turned out to be SOUND, so the obvious fix — a     │
│    ratio — would have deleted 560 good cards to repair 400 bad ones.      │
└───────────────────────────────────────────────────────────────────────────┘
```

## In scope for V1

- `reason_about` emits a trace: the eight steps with their verdicts, and every
  question asked with what became of its answer.
- `GET /api/admin/reasoning-trace` — one faulted move with its full trace and
  its caption. Takes a random pick, a specific game and move, or a pasted FEN
  with a played move.
- `GET /api/admin/reasoning-provenance` — the discovery record per question.
- The page at `/admin/reasoning-trace`, both tabs, boards with arrows.
- Provenance is **data** (`backend/data/question_provenance.json`), with a test
  asserting every question in the registry has an entry — so a new question
  cannot ship without saying where it came from.
- A written document, `docs/how_claude_finds_the_mistake.md`: the procedure,
  and how the procedure was arrived at.

## Explicitly out of scope for V1

- No judging, voting or approving. `/admin/detector-review` and
  `/admin/reason-judge` already do that and this is not another one — it is
  read-only. Nothing on this page changes what a player sees.
- No editing a question or a threshold from the page.
- No LLM. The trace is the engine's own record; `caption_polish` is not wired
  here.
- Not a measurement dashboard. Counts shown are the ones recorded with each
  question's provenance, not live aggregates recomputed per page load.
- No pagination through the whole corpus. One move at a time, plus a random
  pick, is the working loop this is for.

## Success criteria

The test is whether it answers a question faster than a script does.

1. Mohit flags a bad card. The page shows, without anyone writing a probe,
   which question produced it and which rule let it through.
2. A question that fires but is always thrown away becomes visible as such —
   `engine_undoes_it` has 4,650 findings and 30% survive, and nothing on any
   screen says so today.
3. A step that never runs shows up as never running. If steps 3, 4 and 5 read
   "not reached" on every sample, the engine has fewer working steps than the
   documentation claims, and that should be obvious rather than discoverable.
4. Adding a question without recording where it came from fails a test.

## Open questions

- **Which samples does tab 2 show?** Decided: the real positions recorded in
  each question's provenance entry, because those are the ones that produced
  it. A live re-scan would show current firings, which is a different and less
  useful fact.
- **Does the caption on tab 1 come from the real caption layer?** It must, or
  the page shows a sentence no player would see. V1 renders through
  `build_move_teaching_decision` where the move has a card, and says plainly
  "no card on this surface yet" where the framework is not wired — which is
  the truth for `left_it_loose` today and should not be hidden.
- **Where do the eight steps' names live?** In the trace the engine emits, one
  entry per step, so the page never holds a list that can fall out of sync.
