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
