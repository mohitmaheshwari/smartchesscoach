# A game as a sequence of decisions — worked example and the prior question

Read-only, 2026-10-15. Nothing written. Games are the **100 distinct** analysed
games (de-duplicated by platform game ID).

---

## 1. The prior question: does the whole-game frame actually fit him?

Before demonstrating a narrative, it is worth asking whether his losses are
single events. Over his **49 losses**, taking each eval curve from its peak to
its following trough:

| | Losses |
|---|---|
| **CLIFF** (one move ≥60% of the fall) | 11 (22%) |
| **MIXED** | 10 (20%) |
| **SLIDE** (worst move ≤40% of the fall) | 2 (4%) |
| **no decisive fall at all** (<200cp peak→trough) | **26 (53%)** |

Of the 23 losses with a decisive fall, the single worst move accounts for a
**median 58%** of it (p25 45%, p75 91%). And the median lost game contains
**6 moves costing 100cp or more**, up to 16.

**Three readings, and the third is the one I did not expect:**

1. **Pure cliffs are the minority.** Only 11 of 49. Naming one move as "the
   blunder" is defensible in about a fifth of his losses.
2. **But pure slides are rarer still** — 2 of 49. So "his advantage drains away
   gradually" is not the typical shape either. The typical shape is one move
   doing roughly half the damage and other moves doing the rest. **That is
   precisely the case for the whole-game frame**: a single label captures about
   half of what happened and silently discards the other half.
3. **Over half his losses never had a collapse to explain.** 26 of 49 never
   fell 200cp from their own peak — meaning he was never meaningfully better and
   then lost it. Those games need a different account entirely: not "where did
   it go wrong" but "it was never going right", which no amount of move-level
   labelling will produce.

So the frame fits, and the median lost game carries six significant errors —
which makes choosing one of them arbitrary.

---

## 2. The worked example

**lichess.org/LFLLI2MK** · 2026-09-18 · blitz **300+3** · he was White, 1290,
against 1329 · **lost by time forfeit** on move 25.

```
1. e4 d5 2. exd5 Qxd5 3. Nc3 Qd8 4. Nf3 Nf6 5. Bc4 Bg4 6. O-O Nc6 7. d3 e6
8. Bg5 Be7 9. h3 Bh5 10. Re1 O-O 11. Ne4 Nxe4 12. Bxe7 Qxe7 13. Rxe4 f5
14. Re1 a6 15. Rxe6 Qb4 16. Rh6+ Bf7 17. Bxf7+ Rxf7 18. Rh4 Qxb2 19. Ng5 Qf6
20. Nxf7 Qxh4 21. Qf3 Qe7 22. Nh6+ gxh6 23. Qxf5 Rf8 24. Qd5+ Kh8 25. Kf1 Qf6
0-1
```

His own evals, user-relative, with the engine's cost of each move:

| Move | Played | Eval after | cp lost | Stored gap |
|---|---|---|---|---|
| 6 | O-O | +38 | 195 | king_safety |
| 8 | Bg5 | −99 | 130 | opening_knowledge |
| 14 | Re1 | +87 | **399** | missed_tactic |
| **15** | **Rxe6** | **+492** | **0** | — |
| **16** | **Rh6+** | +138 | **432** | tactical_oversight |
| 17 | Bxf7+ | +120 | 0 | — |
| 18 | Rh4 | +121 | 1 | — |
| 19 | Ng5 | −33 | 180 | — |
| **20** | **Nxf7** | −240 | 180 | **piece_safety** |
| 21 | Qf3 | −368 | 119 | — |
| 25 | Kf1 | −713 | **406** | king_safety |

Peak **+492 at move 15**, trough **−713 at move 25**. Worst single move:
432cp — **29% of a 1,205cp fall**. By the classification above this is a SLIDE,
one of only two in the window.

### What was happening

He traded into a position where Black's king was exposed on the e-file and his
rook broke in with **15.Rxe6**, the engine's own choice, reaching +492 — a
winning advantage. Practical circumstances matter here and are recorded: five
minutes plus three seconds, against an opponent rated 39 points above him, and
the game ended on the clock rather than on the board.

### How the decisions connected

This is the part a per-move label cannot say. Every claim below is verified on
the board.

1. **Move 15, Rxe6.** The rook stands on e6 **attacked by nobody**. The
   advantage and the rook are both safe.
2. **Move 16, Rh6+.** A check. It costs 432cp, and it does something a label
   does not mention: the rook leaves a square where nothing attacked it for one
   where **the g7 pawn attacks it and nothing defends it**. The check created
   the weakness that decides the game, four moves before anything is lost.
3. **Move 18, Rh4.** With the rook on h6 now genuinely hanging, this rescues
   it, at a cost of 1cp. A good move — and it leaves the rook on h4, still
   unprotected.
4. **Move 19, Ng5.** Costs 180cp. It also, incidentally, places his knight on
   the f6–h4 diagonal.
5. **Black's 19…Qf6.** The queen now bears on h4 **through** the knight, and
   defends f7 at the same time. Nothing of his is yet attacked: before move 20
   the h4 rook is **attacked by nobody**, because his own knight blocks the
   line.
6. **Move 20, Nxf7.** He takes the material. Moving the knight **unblocks the
   diagonal he did not know he was relying on**, and after 20…Qxh4 the rook
   falls: attacked from f6, defended by nothing.

So the rook was not left hanging and overlooked. **He removed his own shield.**
It is a discovered attack that he supplied both halves of — the loose piece at
move 16, and the screen at move 19 — and then dismantled at move 20.

**34 of his 38 legal moves at move 20 would have kept the rook safe.** It was
not a difficult escape; it needed only noticing what was holding the position
together.

### Where the game changed

Not at one move. **Move 16 created the vulnerability, move 20 cashed it, and
moves 19 and 21 paid 300cp between them.** The eval curve shows the advantage
leaving in four instalments: 432, 180, 180, 119. If we had labelled this game,
we would have labelled move 16 (the largest) and said "tactical oversight" —
true, and it would have skipped the fact that his rook spent five moves
undefended and that he was the one who exposed it.

### What to learn from this game

**When you give a check, ask what square your piece lands on.** 15.Rxe6 was
winning. 16.Rh6+ was a check that moved the rook from safety to a square the
g7 pawn covered, and everything after followed from that. The second lesson is
its twin: **before moving a piece, check what it is currently blocking.** At
move 20 his knight was the only thing standing between Black's queen and his
rook.

Both are the same habit seen from two sides — *what does this square do?* — and
that habit is the one his own lesson records say he rarely applies: he chose
`looks_active` as his reason **34 times** and `checked_landing_square` **4
times**, while `piece_left_unsafe` is his most-recorded misconception at **51**.

The game also supplies evidence for a reading I have kept labelling a
hypothesis: **Rh6+ is a check played from a winning position that cost 432cp.**
That is the same shape as the five mate positions where he played a different
check. Still a hypothesis — but this is now a fourth independent instance.

---

## 3. What this analysis cannot claim

Four limits, stated because the narrative above is persuasive and persuasive is
not the same as established.

- **His intention is unknown.** 16.Rh6+ may have been a planned attack on h7, a
  mis-seen mating idea, or a reflex check. The moves are evidence of what
  happened, not of what he was trying to do. A sensible intention would not
  make Rh6+ sound, and an unsound move does not prove he had no plan. **The
  only way to settle it is to ask him at move 16** — which is exactly the
  critical-moment question the threat assessment is built around.
- **Opponent moves have no engine truth.** `move_evaluations` stores only his
  moves, so "Black threatened this" is my board computation, not Stockfish's
  judgement. The attacker and defender counts above are exact; the *assessment*
  of Black's intentions is not available at all.
- **The eval numbers are his side only**, and clamped to ±1500 so mate
  sentinels do not masquerade as centipawn magnitudes.
- **One game is one game.** The population figures in §1 are the general claim;
  this game is a demonstration of what a narrative looks like, not proof that
  it generalises.

---

## 4. What this implies for which positions become training

The point of the narrative is to choose the training, so: from this game the
position worth drilling is **not** move 20, where the rook is lost. It is
**move 16**, where he is winning and about to give a check:

```
r4rk1/1pp3pp/p1n1R3/5p1b/1qB5/3P1N1P/PPP2PP1/R2Q2K1 w - - 1 16
he played Rh6+, costing 432cp from a +492 position
```

Drilling move 20 teaches him to spot a discovered attack. Drilling move 16
teaches him the decision that made the discovered attack possible, while he
still has a winning position and a free choice. The second is the one that
transfers.

That is the general rule this example suggests: **train the move that created
the weakness, not the move that lost the material.** Finding it requires the
whole-game pass — the move that created the weakness carries no label, often
costs little or nothing on its own, and in this game the move that *rescued*
the rook (18.Rh4, 1cp) sits between them looking blameless.

A caution on scale, measured: 26 of his 49 losses have no collapse to narrate.
For those, this method has nothing to offer and should say so rather than
manufacture a turning point.
