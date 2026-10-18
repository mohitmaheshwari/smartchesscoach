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

A raw threshold is too noisy (over 10s is 25% of all moves), and absolute
seconds are the wrong unit anyway — `move_time_analyzer` says so in its own
docstring: *"a 2-second move is normal in bullet, rushed in rapid."* Compare
each move against the SAME PLAYER'S median, which that service already
computes and stores as `median_user_move_s` on 12,047 games.

Measured over 2,500 games / 77,000 timed moves, by multiple of the player's
own pace:

    x own pace      moves   mistake >=100cp   median
     0-1  x        37,439       14.1%           2s
     1-2  x        20,195       22.1%           6s
     2-4  x        12,459       27.3%          12s
     4-8  x         5,203       29.6%          22s
     8-15 x         1,380       31.0%          37s   <- peak
    15-30 x           272       26.8%          62s   <- falls
    30+   x            52       26.9%         143s   <- falls
            base                19.7%

**The signal peaks at 8-15x and then DECLINES.** Past 15x the mistake rate
drops back toward baseline while the median time climbs to 62s and 143s.
That is the shape of people leaving the board, not calculating. An earlier
version of this scope said "the two longest thinks of the game", and on
Mohit's own games that picked a 131x moment and a 54x moment, both cp_loss 0
— it was selecting for absence.

So the trigger is a **band, not a maximum**: 4x to 15x the player's own
median, at most two a game.

    moments chosen   3,419   (1.37 per game)
    games with none    521   (21% -- the coach says nothing at all)
    mistake rate      32.8%  (base 19.7%)

## The moment, as the player sees it

Quiet position. 40 seconds gone. The player picks up the knight and puts it
back down.

Beside the board, not blocking, not a modal:

> **Taking your time. If you play that, what is their best answer?**
> `[ tap a square ]`   `[ not sure ]`   `[ show me ]`

The player taps the square they are worried about.

> **Yes — Nxe6 is the one. Everything else lets you keep the pawn.**

...or, when they tap something the opponent cannot play:

> **They cannot get there. The move to look at is Nxe6.**

Then it stops talking. Two beats. The player plays whatever they like.

### Why THIS question, and not "what is your knight looking at?"

The first draft asked what the moved piece attacks. Measured on the 3,419
moments the band selects, that question is unanswerable on a third of them:

    piece attacks something   66.1%   mistake 33.2%
    piece attacks nothing     32.4%   mistake 32.1%
    castling                   1.5%   mistake 29.4%

The "attacks nothing" moments carry the SAME mistake rate as the others, so
they are equally worth speaking on — the question simply did not fit them. On
Mohit's own games it produced *"What is the king looking at? (nothing yet)"*
on castling, which is worse than silence.

"What is their best answer?" fits every move type, including castling and
quiet developing moves. The truth is already stored as `pv_after_played[0]`,
so it is checkable without an engine call at speak-time. And it teaches the
one habit this rating band needs most: look at the reply before you commit.

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

1. ~~**Think-time as data.**~~ **DONE 2026-10-18.** The parse was never
   missing — `attach_move_times` had always run, but in PHASE 6, after the
   analysis document is written in PHASE 1, so the mutation fed the thinking
   score and died with the request. 0 of 19,896 analyses carried
   `time_spent_seconds`. Now persisted on write, and backfilled: **18,822 of
   19,896 (94.6%), 588,190 moves timed.** The 1,074 without are PGNs with no
   clock and stay "unknown", never "fast".
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
