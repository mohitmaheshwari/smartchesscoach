# The coach that speaks when you hesitate

Status: DRAFT for sign-off. Written 2026-10-18.
Grew out of Mohit: *"I want to have a conversation with player while playing
game, how do we do this really better and very very interactive."*

## The problem with the obvious version

The first idea was to ask the player what they were thinking, after the game.
Mohit killed it in one line: *"not all people really remember what they were
doing."* He is right, and it generalises — asking someone to recall their
reasoning gets you confabulation, not data.

In-game there is no recall problem. The thought is live.

## What exists today, and why it cannot carry a conversation

`PreMoveGuardian` already intercepts moves before they are played. It is
wired: `useGuardian.js` -> `CoachPlay.jsx` -> the coach-play route ->
`PreMoveGuardian`. It is also, by design, almost silent:

    coach sessions                     499
    sessions where it NEVER spoke      477   (95.6%)
    interventions, all sessions         33
    user moves played                8,849
    the guardian speaks on          0.373% of moves   (1 in 270)

That is deliberate. Stockfish is the arbiter (`eval_drop < 0.5` -> never
intervene, "Stockfish knows better"), only CRITICAL fires (a 4+ pawn drop),
HIGH and MEDIUM are deliberately silent, it is capped at 3 per game, and with
no engine eval it goes blind rather than noisy. `_decide_intervention` says
why: *"let the student make the mistake and learn from the Socratic question
that follows."*

So the guardian answers one question — **"are you about to throw the game
away?"** — and the answer is nearly always no.

**A conversation needs a different question: "what are you looking at right
now?"** That fires on the player's uncertainty, not on catastrophe. Two
different triggers, so two different voices.

## The trigger: the player's own clock

Measured over 900 games / 21,186 user moves with clocks parsed from the PGN
(`%clk`, present on 739 of 900 games = 82%):

    think time     moves   mistake >=100cp   flagged critical
     0-2 s         4,923        12.4%            14.7%
     2-5 s         6,518        17.7%            19.4%
     5-10 s        4,451        22.7%            23.9%
    10-20 s        3,010        26.7%            27.5%
    20-45 s        1,772        30.8%            31.0%
    45+  s           512        28.9%            29.1%
      all moves                 20.2%

A move thought about for 20+ seconds is **2.5x** more likely to be a mistake
than one played in under two. The independently computed `is_critical` flag
tracks it almost exactly, so long thinks land on genuinely sharp positions
rather than merely slow ones.

A raw threshold is too noisy (over 10s is 25% of all moves). The cadence comes
from picking the longest few thinks **of that game**:

    pick              moments   mistake   critical   median think
    top-1 per game        739     33.8%     34.8%        31s
    top-2 per game      1,478     34.1%     34.8%        26s
    top-3 per game      2,214     32.7%     33.2%        23s

**top-2 is the design**: ~7% of moves, 34% hit rate, about two moments in a
55-move game.

### What this trigger will NOT do, stated up front

top-2 catches **11.8% of all mistakes**. Hesitation finds the moments the
player *knows* are hard. It will never catch the blunder played instantly and
confidently — that is a different trigger, and the existing "you usually rush
here" pattern line is what it was always for. This is a companion, not a
safety net. **The guardian keeps catastrophe and does not change.**

## The moment, as the player sees it

Quiet position. 40 seconds gone. The player picks up the knight and puts it
back down.

Beside the board, not blocking, not a modal:

> **Taking your time. What is the knight looking at?**
> `[ tap a square ]`   `[ nothing ]`   `[ show me ]`

The player taps **f7**.

> **Yes — f7. And what is defending it?**

...or, if they tapped a square the knight does not attack:

> **It does not reach there yet. From where it stands it hits e5 and g5.**

Then it stops talking. Two beats. The player plays whatever they like.

### Rules the moment obeys

1. **Never judges the move.** It asks what the player SEES. It cannot be
   wrong about the position because it makes no claim about the position's
   value. This matters: in the week this was written, the same codebase
   badged a forced best move as a Blunder on 4,465 cards and explained a
   4.3-pawn blunder as "they missed a pawn". Any design that requires us to
   be right about chess before speaking is not ready. This one does not.
2. **Two beats, never three.** Question, one tap, one reply. Three beats is a
   lesson and a lesson is not a game.
3. **Ignorable.** The move is never blocked. No acknowledgement required.
4. **Never repeats** the same question twice in a game.
5. **Board-answerable only.** Never "what were you thinking?" Always a
   question whose answer is visible on the board.
6. Voice: simple English, short sentences, no jargon — `/check-voice` and
   `/rewrite-for-1200` as usual.

## What it records, and why that fixes the review too

The tap is stored: the move, the square the player looked at, and whether it
is one the piece actually attacks.

That gives the post-game review the thing it has never had — evidence of what
the player **saw**, not what they would later claim. The review can then say
*"on move 15 you were looking at the knight; the thing that mattered was f7"*
as a recorded fact rather than a reconstruction. **One mechanism answers both
of Mohit's questions.**

## Build order

1. **Think-time as data.** `%clk` is in the PGN and the analysis pipeline
   drops it (0 of 23,735 rows keep it). Parse it into `move_evaluations` as
   `think_seconds`. Nothing else can be built until this exists, and it is
   independently useful for the behavioural focus work.
2. **The trigger, offline.** The top-2-longest-thinks selection over a
   finished game, so it can be measured on the corpus before anything is live.
3. **The question.** One board-answerable question per moment, derived from
   the piece the player is holding. Deterministic, no LLM.
4. **The live hook.** PWC reads the clock live rather than from a PGN. NOT
   yet verified to exist on the session — check before promising it.
5. **The tap, recorded**, and the review sentence that uses it.

## What is explicitly not in scope

- A chat box with an LLM behind it. Our error rate is too high to invite open
  questions; conversation multiplies the cost of being wrong.
- Making the guardian chattier. Its restraint is why it is credible.
- The candidate-move multiple choice, already rejected in
  `coaching_presence_scope.md` for turning the coach into a tutor.

## Open question for Mohit

Does the companion speak in the REVIEW as well, on the same two moments, for
games already played? The clock data is there for 82% of imported games, so it
is buildable without PWC — but the player is no longer in the position, and
"what are you looking at" becomes a recall question again, which is the thing
we started by rejecting.
