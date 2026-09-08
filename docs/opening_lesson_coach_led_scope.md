# Opening lesson: one coach-led lesson, not a menu

Status: **draft, awaiting Mohit's signoff.** No code until then.

## The problem, in one sentence

Before the Vienna page teaches anything, it asks the student to make seven
choices — three variation chips and four tabs — and the student has no way
to know the right answer to any of them.

That is the wrong shape for a coach. Deciding what you should study next is
the coaching. A page that lays out `Vienna, Bishop's Line (9)`,
`Vienna Gambit (11)` and `Frankenstein-Dracula Variation (11)` and waits is a
table of contents, and a student who already knew which of those they needed
would not need us. Mohit's words: *if the user could select it, he can read it
anywhere.*

It also buries the one thing nothing else on the internet can give them.
`user_mistakes` — this student's own errors in this exact opening — is
already in the lesson payload today, and it is behind tab four.

## Where I disagree with the brief

The reference point given was YouTube. I want to take one thing from it and
explicitly leave another.

**Take:** no menu, the coach picks the order, one continuous thread, the
board moves while somebody explains why.

**Leave:** passivity. A video cannot ask you anything and does not know you.
We can do both, and the tree already carries the material for it — every node
now has a `hint` to ask with, a `right_feedback` for when they find it, and a
`wrong_feedback` for when they do not. Turning the lesson into something you
watch would throw away the only real advantage we have over the video they
would otherwise be watching.

So: **coach-led, not menu-led. Continuous, not fragmented. Asked, not
watched.**

## What the screen becomes

```
  ┌──────────────────────────────────────────────────────────────────┐
  │  ← Repertoire            VIENNA GAME · lesson 1 of 4             │
  │  ●━━━━━━━━━━●━━━━━━━━━━○━━━━━━━━━━○                              │
  │  your game  main line   the trap   the sharp one                 │
  ├─────────────────────────────┬────────────────────────────────────┤
  │                             │  COACH                             │
  │       [ board ]             │                                    │
  │                             │  You have played the Vienna 12     │
  │   arrows + highlights       │  times. Four of those you lost     │
  │   drawn by the coach        │  the e4 pawn the same way, so      │
  │                             │  that is where we start.           │
  │                             │                                    │
  │                             │  ── it plays out on the board ──   │
  │                             │                                    │
  │                             │  Their knight is out on its own    │
  │                             │  and f7 is thin. One move hits     │
  │                             │  both.                             │
  │                             │                                    │
  │                             │      [ your move on the board ]    │
  │                             │      ─────────────────────────     │
  │                             │      Show me   ·   I'm not sure    │
  └─────────────────────────────┴────────────────────────────────────┘
```

No chips. No tabs. One thread with a visible spine so the student knows how
far they are and what is coming — the spine is a *progress bar, not a
chooser*. Chapters become clickable only once reached, so revisiting is
possible and choosing-before-you-know is not.

## The sequence the coach follows

Ordered by what this student needs, not by chess taxonomy.

1. **Your game.** The mistake they actually made in this opening, from
   `user_mistakes`, replayed on the board. If they have never played it, this
   chapter is skipped silently and the lesson opens at 2.
2. **The main line**, move by move, using the authored `right_feedback`, and
   *stopping to ask* at each node that has a `hint`.
3. **The trap**, entered as a branch off the main line rather than a separate
   destination: "now — what if they take your pawn?" For the Vienna this is
   Qh5 and the verified fact that 24 of Black's 32 replies are mate in one.
4. **The sharp alternative** — the Gambit — framed as a choice of temperament,
   not a different page: "same position, different mood."
5. **Close.** Three things to remember, then straight into practice on the
   moves they got wrong, not a tab they have to find.

## What already exists

| piece | state |
| --- | --- |
| tree with hint / right / wrong on every node | done, 216/216 |
| variations composing into legal lines | done |
| traps with `trap_type` and a stated punishment | done, 21 verified |
| this user's mistakes per opening (`user_mistakes`) | already in the payload |
| board playback component (`GuidedOpeningLesson`) | exists, 556 lines |

## What has to be built

- **A lesson plan builder** (backend). Given opening + user, return an ordered
  list of chapters with the coach's line for each transition. This is the only
  real new logic, and it is where the "coach decides" lives.
- **One page instead of tabs** (frontend). `OpeningLesson.jsx` is 705 lines of
  tab plumbing; most of it goes.
- **Chapter transitions.** The coach has to say why we are moving on, or it is
  still four things stapled together.

## Out of scope

Board visuals, the engine, the caption pipeline, and the content itself. This
is sequencing and presentation only. No opening data changes.

## How we will know it worked

Not "time on page" — a menu can beat a lesson on that by making people hunt.
The check is **completion of the whole thread** versus today's tab-hopping,
and whether the mistake taught in chapter 1 falls faster than the student's
untaught mistakes afterwards, which
`backend/scripts/measure_coaching_contribution.py` already measures.

## Chapter 1: measured, and it changed the design

I had this backwards. The draft treated the personal opener as the normal case
and a generic one as the edge case. Counting how our 125 users would actually
land on the Vienna:

| case | users | share |
| --- | --- | --- |
| played the Vienna -> open with their own mistake in it | 33 | 26% |
| played chess but not the Vienna -> tie it to their weakness | 36 | 29% |
| no games at all -> generic opener | 56 | 45% |

The generic case is the **plurality**, not the exception. Designing the page
around the personal opener would have tuned it for a quarter of users.

Worse, the middle tier is a mirage. Of the 53 users with a weakness topic on
file, **49 are `piece_safety`** — so "your weakness is piece safety" is the same
sentence for 92% of them. It reads as personal and carries no information,
which is the failure mode we already have a name for: it looks like coaching
and is not.

**Decision:**

- The **generic opener is the default path** and gets the real writing effort.
  Every user gets a lesson that stands up on its own.
- The **personal opener is an upgrade that has to earn its place.** It fires
  only when we can name a specific position and move — "you lost the e4 pawn
  this way four times" — not a category. 33 users clear that bar today for the
  Vienna, and that number grows on its own as people play.
- **Tier 2 as drafted is dropped.** A weakness category shared by 92% of users
  is not personalisation. If it ever becomes specific enough to name a pattern
  rather than a bucket, it can come back.

This also means the lesson is never blocked on personal data, which matters
because [[ChessGuru is not live]] and most accounts have no games yet.
