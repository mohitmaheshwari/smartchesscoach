# Describe both moves — Scope (plain English)

> Status: **DRAFT, awaiting Mohit's sign-off.** No code until he agrees §1.
> Written 2026-10-12 after he said: "there must be a very standard fundamental
> to support all this which is missing and I am also sure that we can do
> better, but we are really terrible right now."

## 0. The one idea

**A card is: what your move does, what the best move does, and the difference.**

That is the whole thing. Not "find what is wrong with this move".

We have been building a *defect catalogue* — a detector per kind of mistake,
added one at a time as Mohit flags positions. That design asks **"what is wrong
with this move?"**, and on 28% of his flagged moves nothing can answer it. So
every complaint spawns a new detector and the work never converges. This is the
thing he is feeling when he says we are still exploring positions one at a time.

**"What does this move do?" always has an answer**, because every legal move
does something. Coverage stops being earned detector-by-detector and becomes
structural.

## 1. THE DECISION Mohit is being asked to make

Replace "detect the defect" with "describe both moves and diff them" as the
*primary* frame for review captions. Detectors do not go away; they become one
source of verbs among several, instead of the thing the card is built on.

Everything below follows from that. If he disagrees with §1, nothing else here
matters.

## 2. Why this is not a hunch — it is already half-built

`caption_facts._recommended_move_why(board, move, mover_is_user, line)` is
**generic**. It takes any board and any move and returns what that move DOES as
a short verb phrase. We only ever call it on the engine's move and throw the
other half away.

On the position from the competitor screenshot (1.e4 e6 2.d4 Be7 3.Nc3 Nf6,
White to play; engine at depth 18 has e5 best at 92cp and Bg5 outside the top
four), the same function called twice returns:

```
Bg5   ->  'brings a new piece into the game'
e5    ->  'attacks the knight on f6'
```

Those two lines ARE the competitor's card — their "what you were thinking" and
their "the better idea". We compute both today and show one.

**Tempo is not a new detector in this frame; it falls out of the diff.** Both
moves attack the same knight on f6. `e5` attacks it with a PAWN — cheaper than
a knight, so the knight must move and White gains a free move. `Bg5` attacks it
with a BISHOP, and the knight is defended twice (Be7 and g7), so Black can
ignore it, and did. Same verb, different forcing-ness. The difference is the
lesson, and it is fully deterministic.

## 3. Where we actually are, measured

All 838 analysed games, every flagged move at 30cp+, both sides, no sampling.
Each move's PLAYED and BEST move passed to the same describer.

| | your moves (8,413) | their moves (4,381) |
|---|---|---|
| both describable | 4,946 (58.8%) | 2,604 (59.4%) |
| only the best move | 1,213 (14.4%) | 789 (18.0%) |
| only the played move | 1,456 (17.3%) | 622 (14.2%) |
| **neither** | **798 (9.5%)** | **366 (8.4%)** |

**At least one verb already exists on 90.5% of his moves.** Compare the
defect-catalogue frame on the same corpus: 28.3% of his moves have nothing that
can explain them at all.

The verbs in use are already a closed list of ten:

```
attacks 3,299 · wins 1,273 · moves 1,245 · puts 977 · brings 817
trades 734 · defends 500 · gives 395 · tucks 321 · costs 67
```

## 4. The work, and it is finite

Close the vocabulary until every legal move has a verb. When the describer
cannot speak for the played move, this is what the move was:

```
pawn 1,293 · king 669 · queen 376 · knight 333 · bishop 276 · rook 169
(captures are nearly all covered: 50 across all piece types)
```

**Quiet pawn moves and king moves are 55% of the gap.** They are quiet moves
that take a square, make luft, walk toward the centre in an endgame, block a
file, or prepare a break — real things with no verb yet.

This is a bounded list, not a hunt. Roughly: captures · attacks · defends ·
develops · castles · takes a square · creates a threat · opens a line · blocks
a line · advances · retreats · trades. Each is board-checkable.

## 5. What this does to work already done

- **The say-better backstop (`1fc9e108`) stays.** Naming the better move is
  half the frame.
- **The word-cap chokepoint (`ea3b444f`, `95a73c42`) stays.** Unrelated and
  correct.
- **The tier-3 families get demoted.** They are verbs, not concepts. They stop
  being the thing a card is built on and become one more way to describe a
  move. The preview showed why: on real cards they repeated what the card
  already said, fired on move 1 at 42cp, and once named a piece the move never
  touched.
- **`less_space` stays dead.** Mohit: "less_space itself is not a concept." It
  is a square count, and on the card checked, the 29-vs-36 gap was a bishop
  covering more squares than a knight from the same square — a true number
  attached to a false cause.

## 6. How we will know it worked

- **Coverage:** every flagged move, both sides, has a verb for the played move
  AND a verb for the best move. Target 100%; today 58.8%.
- **Truth:** every verb is board-checked on the FEN, same as now. A verb we
  cannot verify is not printed.
- **Teaching:** the only real test is Mohit reading cards. Twenty real rendered
  cards before anything ships, and the bar is his, not a score.

**Explicitly NOT claimed:** that this produces 100% *good* captions. It
produces 100% *coverage* — every card saying something true about both moves.
Whether the difference between two verbs reads as a lesson is a separate
question with one test, which is him reading it.

## 7. Open decisions for Mohit

1. **§1 itself** — is the comparison frame the right primary?
2. **Does the "what you were thinking" line appear on OPPONENT cards too?**
   "Your opponent was developing a piece" may be noise; for his own moves it
   reframes the card from correction to coaching.
3. **One surface or two?** The competitor ships one sentence and puts the
   breakdown behind a click. Our cards are one surface trying to carry
   everything, which is why they reach 81 words and four stages append to them.
   Two surfaces is a frontend change, so it is a separate decision.
4. **Where principles attach.** The competitor names a principle on the BETTER
   move ("tempo in the opening"), gated on what that move does. Mohit killed
   our principle bank as filler because it fired regardless of position. Gated
   on the verb, it is the memorable layer he keeps asking for — but it is his
   call whether to reopen it.

## 8. What is deliberately out of scope

Opponent-side analysis backfill (383 games, separate and already measured),
tier 2 openings (blocked on a known half-history bug in the opening detectors),
and anything on the PWC side until review is right.
