# The Coached Experience — Design

**Status:** DRAFT v1 — design proposal, not a build contract. Requires Mohit's review.

**What this is.** PIC defines the machinery that proves a player improved.
This document defines what being coached actually *feels* like — what the player
sees each day, how the coach stays varied without becoming a store, and how the
existing content library (79 openings, 28 trap families, 6 endgame categories,
3,395 motif positions, 37k training positions) gets used by a guide rather than
browsed by a user.

**What it is not.** It does not change PIC v1's build. It names what PIC v1 is
*part of*, so that shipping the reactive engine is not mistaken for shipping the
coach.

---

## 1. Two axes, one voice

A real coach runs two curricula at once.

| | **Reactive** | **Proactive** |
|---|---|---|
| Source | The player's own games | The syllabus for their level |
| Trigger | They made the mistake | They're ready for it |
| Example | "You hung the bishop again" | "You're 1200 — time you knew the Lucena" |
| Today in ChessGuru | PIC (being built) | Skill tree + content library (exists, unguided) |

Nobody learns the Lucena from their mistakes. Nobody learns "check the square
before you let go" from a syllabus. **A coach needs both, and the player must
never be asked which one they want.**

The measured thread stays singular — one active focus, one instruction, one
proof loop. The *teaching* does not.

---

## 2. The daily decision

The player never chooses. The coach picks, in this order:

1. **New game since last visit?** → the moment from that game. Freshest and most
   personal; always wins.
2. **Checkpoint due?** → an unannounced mixed set. Never labelled as a test.
3. **Delayed recall due?** → one item folded into the session, pattern unnamed.
4. **Active focus needs practice?** → their own positions first, community
   positions second.
5. **Nothing pending?** → the next syllabus item from the skill tree.

Rule 5 is what stops the product going quiet, and it is where the library earns
its keep. Rule 1 is what stops it feeling generic.

**One action per day, drawn from two pools.** The pool is invisible to the player.

---

## 3. The variety engine

Grinding one format kills return rate faster than difficulty does. The same
thread gets taught through different material on different days:

| Day | Thread | Material | Source |
|---|---|---|---|
| 1 | piece safety | your game, move 19 | the player's game |
| 2 | piece safety | the same shape, someone else's position | community positions |
| 3 | piece safety | Légal's Mate — a trap built on it | `traps.json` |
| 4 | piece safety | silent checkpoint, unannounced | mixed |
| 5 | — | rook endgame: the Lucena | `endgames.json` |
| 6 | piece safety | your new game | the player's game |

Most of the library is not a separate subject — it is **vocabulary for the
active thread**. A trap is a piece-safety story with a name. A fork is two
pieces unsafe at once. An opening disaster is usually a queen chased into the
open. Opposition, Lucena, Philidor and structure are the genuinely separate axis.

**What this requires:** every content item carries concept tags, so the coach can
ask *"material for `piece_safety`, unseen by this player, in a format not used in
the last two days."* That query is the variety engine. It reuses existing content
and adds no new store.

---

## 4. The fix is the product

A coach who talks without demonstrating on the board does not get paid.

Players do not pay to learn *that* they hang pieces — they know they lose
pieces. They pay for a way to **keep fixing it**. Diagnosis and proof are ours,
not theirs: diagnosis picks the thread, proof tells us whether to move on.
Neither is the value.

The fix for piece safety is not knowledge, it is a **habit**: before you let go
of the piece, check who attacks the square. Habits are built by repetition of the
action under feedback — not by reading about them, and not by solving five
puzzles labelled "piece safety."

So the unit of the product is a **rep**, not a lesson.

### The rep

One rep is a live decision on a board, answered in seconds, corrected instantly:

```text
┌───────────────────────────────┐
│                               │
│                               │
│           BOARD               │
│   Bg5 drawn as a ghost piece  │
│                               │
│                               │
└───────────────────────────────┘
  You want to play Bg5.

  [   Safe   ]      [  Not safe  ]
```

Answered — the board does the teaching:

```text
┌───────────────────────────────┐
│                               │
│           BOARD               │
│   h6 flashes · arrow h6 → g5  │
│                               │
└───────────────────────────────┘
  The h-pawn takes it.

                    3 / 8   [ Next ]
```

Roughly 20 seconds per rep. **Eight reps is under three minutes.** That is the
session. The player leaves having made eight real decisions, not having read
eight sentences.

### Drill the scan, not the answer

The wrong drill asks *"what is the best move?"* — that trains puzzle-solving.
The right drill asks *"is this square safe, and who takes it?"* — that trains the
scan the player must run in every real game. Same position, different skill.

Escalate only when the scan is reliable: safe/unsafe → name the attacker →
is it defended enough → now find a safe alternative yourself.

### Three surfaces, one habit

The fix does not live in the drill alone. It exists across three moments, and all
three already exist in the codebase as separate features:

| Moment | Surface | Status |
|---|---|---|
| Rehearse the scan, no consequence | Drill (`/training`) | Positions exist; the rep format does not |
| Run the scan for real, live | **Pre-Move Guardian** in Play With Coach | **Built** — `HANGING_PIECE` is its category 1 |
| See where the scan failed | Game review | Built |

Wiring those three to one instruction is the fix mechanism. The Guardian is the
strongest asset here and PIC currently does not centre it: it is the only place
in the product that intervenes *at the moment of the real decision*, which is
exactly where a habit is formed.

### What the words are for

Text is a caption, never a paragraph. One line above the board to frame the
decision, one line after to name what happened. Continuity and the coach's voice
live in **one sentence at the top of the session**, not in a screen of their own:

```text
Yesterday, move 19 — the bishop again.
Eight quick ones.
                                [ Start ]
```

Then the board, immediately.

The coach speaks at three moments only: **why we're here** (one line, at the
start), **what just happened** (one line, per rep), and **what changed** (one
short verdict, at the end). Everywhere else, the board talks.

### The end of a session

```text
┌───────────────────────────────┐
│           BOARD               │
│   the one you got wrong,      │
│   attacker highlighted        │
└───────────────────────────────┘
  7 of 8. This one — the knight was
  already covering g5.

  Tomorrow: same check, harder positions.

                              [ Done ]
```

Not a percentage, not a state label. One board, one correction, one next step.

### The metric that matters

**Reps per session, not sessions per week.** A design that delivers 8 decisions
in 3 minutes beats one that delivers 2 decisions in 6. When judging any screen in
this product, count how many real decisions the player makes on a board, and how
many seconds of reading stand between them.

---

## 5. Internal states must never surface

PIC §3 defines nine lifecycle states. **Every one of them is engineering
vocabulary.** If any renders as a label, the product reads as a machine. LES
already solved this pattern by collapsing 8 internal checkpoints into 3
learner-facing states; PIC needs the same translation layer.

| Internal state | What the player is told |
|---|---|
| `not_eligible` | *(nothing — normal experience, no cycle language)* |
| `diagnosed` | "One thing keeps happening." |
| `practice_assisted` | "Let's work on it." |
| `checkpoint_insufficient_evidence` | "It didn't come up. We'll try again." |
| `checkpoint_unresolved` | "Still happening. Same thing today." |
| `checkpoint_promising` | "Better. Let's see it in a real game." |
| `external_insufficient_evidence` | "That game didn't test it. Next one." |
| `external_unresolved` | "It showed up again. Not done yet." |
| `resolved` | "You've stopped. Here's what's next." |

---

## 6. Principles

1. **The board is the screen.** If a mockup can be read as prose with the board
   behind a button, it is wrong. Text is a caption; the demonstration is the
   teaching. A coach who only talks does not get paid.
2. **Count the reps.** The unit is a decision made on a board, not a lesson
   delivered. Eight in three minutes beats two in six.
3. **Fixing beats knowing.** The player already knows they lose pieces.
   Diagnosis picks the thread and proof tells *us* when to move on — neither is
   what they are paying for.
4. **Never a grid.** One action. Browsing exists but is never the path to value.
5. **Continuity every time.** Each session opens by referencing the last one — in
   one line, above the board. A coach who forgets is not a coach.
6. **The content may be generic; the reason must be personal.** A stock Lucena
   lesson is fine. "Because you reached this in 6 games and lost 4" is what makes
   it coaching.
5. **"Why this?" is always one tap away.** It is the difference between a guide
   and an algorithm.
6. **Vary the format, hold the thread.** Breadth belongs to the arc, not the session.
7. **Never announce a test**, and never lie about one either.
8. **Silence is a failure mode.** If the coach has nothing personal to say, it
   teaches from the syllabus — it does not show an empty state.

---

## 7. What this needs that does not exist yet

| Need | Status |
|---|---|
| Concept tags on traps, motifs, endgames, opening lessons | **Missing** — the variety engine depends on it |
| A daily-decision service implementing the §2 cascade | **Missing** |
| State→language translation layer | **Missing** — PIC has the states, not the words |
| Proactive syllabus selection with a personal reason | **Partly** — skill tree exists, no coach voice drives it |
| Repertoire curation (79 openings → the player's two) | **Missing** — a catalog is not a curriculum |
| Reactive engine | **PIC v1, in build** |
| Content library | **Exists** |

---

## 8. Open questions

1. **How often should the proactive axis interrupt?** Every third day, or only
   when the reactive queue is empty? Affects whether the coach feels attentive
   or nagging. Lock from post-launch return data.
2. **Who curates 79 openings down to two?** Player choice, rating-based default,
   or derived from what they already play most?
3. **Does the proactive axis get a proof loop of its own,** or is "learned the
   Lucena" allowed to rest on lesson completion?
4. **What does day 1 look like with no games connected?** Provisional diagnostic,
   or a syllabus opener until games arrive?
