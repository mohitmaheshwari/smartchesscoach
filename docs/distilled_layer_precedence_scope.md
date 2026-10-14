# A coverage net may not overwrite teaching

*2026-10-14. Written after the 880-game re-render stored generic text on
games whose cards, rendered directly, showed a named trap.*

## How this was found

Mohit asked for every game to be re-rendered at the current caption
version so he could read real cards. The batch finished clean (880 games,
0 errors). Spot-checking the Fried Liver games, the stored card said:

> Your opponent moved their knight with Ng5. Look at what it attacks now,
> and check whether any of your pieces just lost its guard.

while rendering the same game directly gave:

> Ng5 — watch out, you're now in Fried Liver Attack territory. White
> attacks f7 with the bishop and knight...

Four different call shapes were tried, plus `user_id`, `user_color`,
`game_id`, `opponent_move_evaluations`, LLM polish and the database name.
None of them explained it. The cause was none of the arguments:

    prod container   DISTILLED_CAPTIONS_ENABLED=1
    dev container    DISTILLED_CAPTIONS_ENABLED=0

The batch ran on prod. Every direct render ran locally.

## What the flag actually does

`DISTILLED_CAPTIONS_ENABLED` is described in code as a rollout flag for a
coverage net: when a distilled template is available, the caption text is
"replaced". It runs at the very END of `build_move_teaching_decision`,
after the rule cascade has already chosen a caption, and it overwrites
both the text and the `rule_name`.

Measured over 60 games / 3,303 cards, rendering each game twice with the
flag forced off and on (identical inputs, same process):

| | cards |
|---|---|
| overrides | 2,164 (65.5% of all cards) |
| filled a card the rules left SILENT | **0** |
| overwrote text the rules had written | 2,158 (99.7%) |

It never once did the job a coverage net is for. Across the 880
regenerated games it writes 41.9% of stored cards outright
(`distilled:*`), plus 17.9% more from its `facts:*` sibling — 59.8% of
everything a user reads.

## What the overwrites cost

Most rewording is harmless and some is better: the distilled text is
plainer, which suits a 600–1500 reader. The problem is the cases where
a fixed-sentence template has no slot for what the caption already said.

| thing lost | lost | gained |
|---|---|---|
| named motif (fork / pin / skewer / discovered) | 87 | 3 |
| opening name | 96 | 29 |
| why-clause on the better move | 40 | 3 |
| mate / winning-by-force verdict | 18 | 1 |
| every square reference | 318 | 173 |

Read examples, not just counts:

    R01_mate      Raxe3+. Opp is winning by force. Before moving,
                  calculate every enemy check to the end.
    became        Raxe3+ takes your knight, but your king can take back
                  — an even trade. Recapture to keep material level.

The student is being mated and the card tells them material is level.

    R12_blunder   Bb2 allows Qxb2 forking your rook on a1 and knight
                  on c3. Rb1 was better.
    became        Bb2 leaves your bishop on b2 undefended... you simply
                  lose it for nothing; better was Rb1.

A fork becomes "an undefended bishop".

    R05_check     Qh5+ — check, and attacks the pawn on h7 too. You
                  attack h7 more often than they defend it. That is how
                  a weak pawn falls.
    became        Qh5+ is the best move in this position.

`distilled:good_was_best` is the largest single rule in the stored
corpus — 4,422 cards — and that sentence is its whole content.

    R_PROMOTED    e4. King's Pawn Opening. White takes a share of the
    _opening     center. The most popular opening — it leads to open games.
    became        e4 is the best move in this position.

## The change

This is a precedence bug, not a quality bug. The net is allowed to speak;
it is not allowed to speak OVER a caption that carries something it
cannot carry. `_distilled_may_replace(existing, new)` abstains when:

1. `new` is empty and `existing` is not — never trade a card for silence.
2. `existing` names a motif, a mate verdict, a better-move why-clause or
   an opening name, and `new` does not.
3. `existing` names a square and `new` names none — unless `new` pays for
   it by gaining one of the markers in (2). That exemption keeps real
   upgrades: "Nf6 — controls d5, e4" → "Indian Defense setup. Black
   delays committing pawns to the centre" is better, and blocking it to
   save a square would cost teaching.

A square is the cheapest proof a sentence is about THIS board rather than
any board. The decided-position gate in the same file already judges a
stripped caption that way; this reuses the standard rather than inventing
one.

## Result

Same 60 games, same process, flag forced off then on, guard in place:

| | before | after |
|---|---|---|
| overrides | 2,164 (65.5% of cards) | 1,567 (47.4%) |
| named motif lost | 87 | **0** |
| mate / winning-by-force verdict lost | 18 | **0** |
| opening name lost | 96 | **0** |
| every square reference lost | 318 | **27** |
| why-clause lost | 40 | 11 |

The 27 remaining square-losses are the paid-for exemption in (3): the
replacement gained an opening name or a motif. 597 overwrites were
blocked; the other 1,567 still land, including the 1,173 where neither
side names a square and the plainer wording genuinely reads better.

`tests/test_distilled_may_not_overwrite_teaching.py` locks all twelve
cases, each a real pair from this run.
`tests/test_caption_pipeline_boundary.py`: 85 passed on both trees.

### The 11 why-losses are a different layer

They are not the distilled layer overwriting; they come from a verifier
downstream of it:

    was   exf4 lets Bxf6 win your queen on f6. Bxh1 was better — it
          captures the rook on h1.
    now   You played exf4 — it runs into Bxf6, taking your queen.
          Bxh1 was stronger: it wins material.
          [distilled:one_move_blunder→FINAL_VERIFY_SOFTENED]

The distilled text makes a specific claim, FINAL_VERIFY cannot verify it,
and the softener replaces it with a generic one. With the flag off the
softener never fires, so the chain starts with the distilled layer but
the damage is done one stage later, where this guard cannot see it. 11 of
1,561 overwrites (0.7%), and the direction is generic-instead-of-specific
rather than false. Named here, not fixed here: closing it means
re-checking marker preservation on the FINAL caption after every
downstream stage, which reorders stages this change does not touch.

## Not changed, and why

Six cards go from text to an empty caption. That is the
decided-position gate, not this layer: in an already-decided position it
strips the better-move clause and silences what is left if no square
survives. Mohit's own ruling — "silence is NOT always worse. silence is
better than fake explanation." The distilled text happens to contain the
best-move SAN where the rule caption did not, so it reaches a gate the
rule caption walked past. Left alone deliberately.

Separately: `tests/test_opponent_reply_ties.py` called `sys.exit` at
module level, which aborted pytest COLLECTION for the whole suite with
INTERNALERROR — no test anywhere could run. Guarded under
`__name__ == "__main__"` and given a real assertion.

## Still open

The 880-game re-render stored the pre-guard text. It has to run again
once this ships, and the six authored captions the earlier regen
overwrote still need restoring from `authored_caption_overrides`.

---

## Correction: a marker is only worth protecting if it is teaching

*Same day, after reading the cards the guard saved on live data.*

The guard shipped, then I rendered 120 freshly re-rendered games twice --
as deployed, and with the guard forced to always allow -- so every card
it saved could be read beside what the student would have got instead.
1,348 cards were saved. Two of the clauses were protecting filler.

**The mate clause was wrong, including on the case I built it from.** Of
the 78 cards it saved, **76** named no square other than the played
move's own, because the text was always the same sentence:

> b6. Opp is winning by force. Before moving, calculate every enemy check
> to the end.

That card repeats on every move of a lost game -- ten consecutive moves
in game `0134bb00`. The replacements it was blocking were frequently the
more useful card ("Bxd3+ takes your pawn, but your bishop can take back").
The original example in this doc, `Raxe3+ ... Opp is winning by force`,
is one of those 76. A mate VERDICT is not teaching; a mate claim that
names a square is, and that is still protected.

**The never-silence rule was keeping repeats.** 156 of the cards it kept
were verbatim duplicates within one game, worst case *"Your opponent
tidys up the king, keeping it safe."* **25 times** in game `00aedb7f`.
That is exactly what the decided-position gate exists to silence, so the
rule was fighting a ruling already made.

Both now require the protected text to be **about this board**: to name a
square the played move's own SAN does not. A pawn move's SAN *is* a
square, which is why the naive test passed on "b6. Opp is winning by
force." The motif and opening markers need no such test -- the named fork
and the named opening ARE the transferable lesson, and all 160 motif
cards named a real square anyway.

| on 120 live games | before | after |
|---|---|---|
| cards the guard saves | 1,348 | 1,033 |
| mate-clause saves | 78 (76 filler) | **0** |
| kept text repeats in-game | 162 | **2** |
| fails both filler tests | 158 | **0** |
| motif saves (all board-specific) | 185 | 160 |

The 189 opening saves that name no other square are the design: the
opening name carries the lesson.

> "Rh1+. Skewers the king on f1 -- when it moves, the rook on a1 is
> exposed." *(kept)* vs "Rh1+ is the best move in this position."

### A harness bug worth recording

The first re-measurement reported 3,700 saved cards with motif collapsing
to 4 -- the opposite of the intent. The guard had gained a third
parameter and the harness's always-allow stub still took two, so every
call raised TypeError inside the `except Exception` around the distilled
block and the comparison silently inverted. The harness now asserts its
stub matches the real signature. Same failure mode as the `opp_cp_loss`
regression: a swallowed TypeError reads as a behaviour change.

---

## The mate claim was checked against the wrong move

*2026-10-14, after Mohit approved fixing the mate binding only.*

Wrapping `verify_caption` during a real render over 150 games / 8,494
cards recorded every rejection with the caption it threw away. Of 1,164
rejections, **1,029 stand** -- the verifier is mostly right, and its
best catches are real:

> "Bxf7+ ... you simply **lose it for nothing**"
> -- the stored line also removes 100cp of opponent material.

Of the 160 mate rejections, **113 blamed a move that was not played**,
from two causes.

**1. "force mate" was not "forced win".** `_MATE_ALLOWED_RX` listed
`lets ... forced win`, but the only template that claims mate --
`data/distilled_templates.json` `allowed_mate` -- says *"lets your
opponent force mate"*. Every caption from it fell past the
opponent-mates branch into a block asking *is the RECOMMENDED move
mate?*, which it never is:

> "Qd2 lets your opponent force mate, so play Qxf5+ instead"
> rejected as "claims checkmate but Qxf5+ is not mate"

**2. "missed a checkmate" read as "delivered checkmate".**
`_MATE_MISSED_RX` covered "missed mate" but not "missed **a**
checkmate", so a bare `\bcheckmate\b` in `_MATE_DELIVERED_RX` caught
48 captions and classified them as the mover DELIVERING mate when they
say the opposite. That block then tested only the FIRST move, while the
caption says it *"starts a line that forces mate"* -- the mate lands at
the end.

The block now walks the line the claim belongs to, exactly as the
opponent-mates branch already walked `pv_after_played`:
`pv_after_best` for the user's own missed mate, `pv_after_played` for
the opponent's. **The proof requirement is unchanged and still fails
closed** -- the line must reach a checkmate delivered by the side the
caption credits, or the claim is rejected. Five of the twelve tests are
negative controls for exactly that.

### The honest result: the fix is correct and buys little today

| | before | after |
|---|---|---|
| mate rejections blaming a move not played | 113 | **0** |
| mate rejections total | 160 | 153 |
| all rejections | 1,164 | 1,131 |

Seven cards per 150 games. The reason is the interesting part -- the
length of the line each remaining claim depends on:

| plies | cases |
|---|---|
| 0 (nothing stored) | 38 |
| 1 | 1 |
| 2 | 1 |
| 4 | 111 |
| 12 | 2 |

**151 of 153 (99%) have 4 plies or fewer.** A 4-ply line proves
mate-in-2 at best, and the stored mate distribution runs to mate-in-7
(`{1:171, 2:74, 3:29, 4:24, 6:25, 7:21}`). These claims cannot be proven
at the depth we stored, so no verifier change can ship them. The real
unlock is re-analysis depth -- the same 4-ply staleness behind the 47
unprovable missed mates and the short punishment lines.

What this change buys: the rejection reason is now truthful and
diagnosable instead of blaming an unrelated move, and the wrong gate is
gone, so the cards ship the moment the lines are long enough.

### Not pursued, with the number

Negation ("that needs White's pawn on c4, **not** e4" flagged for
claiming a pawn on c4) is real but **6 cases** of 1,164. Not worth
relaxing a check whose other 1,029 rejections are correct.
