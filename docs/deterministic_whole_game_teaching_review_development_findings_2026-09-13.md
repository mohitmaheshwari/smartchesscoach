# Deterministic Whole-Game Teaching Review — Development Findings

**Date:** 2026-09-13
**Status:** 100-GAME BLIND REVIEW FROZEN; FIRST SHARED FACT IMPROVEMENT MEASURED
**Scope:** docs/deterministic_whole_game_teaching_review_scope.md

## Outcome first

The complete-game review found usable deterministic coaching material in **93 of 100** games without seeing ChessGuru's captions, selected events, detector labels or planner rank. It accepted **219 board-proved teaching moments** and refused to turn **546 other engine preferences** into lessons merely because their evaluation changed.

That split is the point of the architecture: ChessGuru already has enough chess truth to make most games memorable, but the unproved residue is dominated by the kinds of quiet moves that current reviews explain least well.

## Frozen evidence

- Development membership: 91f8aacdb0d121fce9258509c84cc2b4bd1a840c3d63224a182ed9e875044496
- Packet SHA-256: b0f44d273b9b597e9aaabcc0fa991a50083aa2909ec701cb625b6267303d4ac2
- Worksheet SHA-256: 6eb3014201940703420057bd72bb9cb6d7eee4f1327c6cc266238afe1968946c
- Games: 100, from 36 anonymous players, at most three per player
- Stored phase mix: 14 opening-only, 25 opening+middlegame, 10 opening+endgame and 51 all-three-phase games
- New Stockfish runs: 0
- Runtime or offline model calls: 0
- Production writes: 0
- Holdout games opened: 0 of 42

The packet includes complete legal traces and both actor streams wherever production had stored opponent evaluations. Fifty-two games contained both streams; 48 contained only the player's stored evaluation stream. Missing opponent evidence is reported as unavailable, never inferred.

## What the board proves today

The accepted lesson inventory is:

| Proof family | Moments |
|---|---:|
| Immediate material left available after accounting for what the move captured | 167 |
| Safe missed capture with no immediate recapture | 28 |
| Move allowing a legally replayed forced mate | 15 |
| Move missing a legally replayed forced mate | 4 |
| Fork geometry with a stored material payoff and no immediate capture of the forking piece | 5 |

The phase distribution is 84 opening, 65 middlegame and 70 endgame moments. The actor distribution is 190 player decisions and 29 opponent decisions; that imbalance is principally a stored-evidence availability limitation, not a ranking choice.

Seven games received an explicit **no provable central story**. Reading those seven rather than filling them with generic advice exposed the important gaps:

- a forcing capture available before a tempting check;
- opening moves whose value is development, central control or preserving castling;
- a quiet defensive queen move;
- purposeful endgame king or piece improvement;
- a pawn move whose value is a positional transformation rather than an immediate tactic.

## What is repeatedly missing

The 546 above-threshold but unsupported decisions group as follows:

| Repeated residue | Count |
|---|---:|
| Quiet endgame piece moves | 118 |
| Quiet opening or middlegame piece moves | 160 |
| Quiet pawn moves across phases | 124 |
| Captures with unsettled recapture/payoff | 91 |
| Quiet checks | 41 |
| Castling alternatives | 12 |

These counts do **not** authorize 546 captions. They identify where to test the existing fact system next.

The six shared investigation targets are:

1. exact or authorized endgame king/piece activity;
2. the concrete purpose of a quiet piece move;
3. pawn breaks and restraining moves as board transformations;
4. exchange and recapture settlement beyond the first capture;
5. forcing move order where a quiet check changes what can be saved;
6. the causal purpose of castling or preserving castling rights.

## First shared deterministic improvement

The initial system comparison found a recurring, safely expressible gap:
the stored played branch sometimes begins with an opponent capture that wins
material, yet the existing legal-board cause abstains because the loss becomes
clear only after the line is settled. A new typed
`immediate_material_loss` branch cause now requires all of the following:

- the opponent's first legal reply captures material;
- material taken by the player's own root move is netted first;
- bounded legal forcing settlement confirms that the loss survives;
- the stored alternative settles at least one pawn better;
- recapture-after-horizon and same-loss-in-both-branches cases abstain.

The canonical pure-fact comparison moved from **139 of 219 exact facts
(63.47%)** to **158 of 219 (72.15%)**: **19 additional exact causes** with no
sample-specific exception. The remaining result is 28 different verified facts
and 33 moments with no typed fact.

This new semantic family has its own quality ID and remains **Shadow**. It does
not inherit Caption authority from the older verified-line families. The
100-game worksheet is selection-censored at three moments per game and cannot
serve as a valid false-positive packet, so player-facing promotion would be an
unsupported shortcut.

The residual review also rejected easy-looking coverage changes. Several
unmatched “immediate loss” rows lose the same material in the stored best line,
end immediately before a recapture, or fall below the established consequence
floor. The five fork examples are too small a population and the present
offline predicate does not prove that the double attack itself causes the
payoff. Those families stay silent rather than receiving weaker rules.

## Safety incident and correction

An early attempt to compare freshly recomposed V5 output started a Stockfish
process even though the task was intended to use stored evidence only. It was
stopped immediately, its output was discarded and no production write
occurred. The frozen exporter no longer has any recomposition path. V5 now
accepts an explicit `allow_fresh_engine_verification` boundary and stored-only
reconciliation passes it as `False`; regression tests bind that call path.

The system baseline remains a last-wire finding: all 100 frozen development
games had zero stored whole-game plans and zero stored teachable events even
though the pure canonical fact builders can exactly represent 158 reviewed
moments. Historical reconciliation must therefore be a separate bounded,
dry-run-first operation after holdout, not an exporter side effect.

## Examples that change the product direction

One no-story game had a rook able to take a bishop before the player gave a queen check. The stored engine preference alone is not the lesson. The memorable lesson is move order: **before giving the check, ask whether a capture removes a defender or wins material first.**

Another no-story game repeatedly moved the king instead of developing the bishop. “Develop your pieces” is too generic. A safe deterministic explanation must name what the bishop move changes—whether it clears castling, covers an entry square or answers a concrete threat.

Several endgames prefer quiet king moves. Merely saying “activate your king” would be filler. The system must show the route or exact square relationship that makes the move work, and abstain where stored evidence cannot prove it.

## Next comparison

The independent inventory is now frozen. The next step may expose the current ChessGuru plan and caption output for these same anonymous games, join it to the gold, and give every accepted lesson one of the locked dispositions:

- exact match;
- causal equivalent;
- same move but wrong reason;
- verified fact not wired;
- detector miss;
- incomplete fact contract;
- missing concept candidate;
- unsupported residue;
- Codex interpretation rejected.

Only repeated verified gaps can change shared deterministic logic. The seven no-story games and 546 unsupported candidates remain silent unless that comparison produces a proof-backed implementation path. The implementation now also returns an explicit honest phase overview when no safe plan exists, so “no lesson” is a complete response rather than a missing UI.
