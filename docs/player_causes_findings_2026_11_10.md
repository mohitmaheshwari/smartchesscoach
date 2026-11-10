# What a player does not know vs does not see — measured 2026-11-10

Mohit, 2026-11-10: the coach must understand *why* for everything — not only
blindness and behaviour, but "the things he might just not know" — and build
the plan and the parent report from that.

This note records what the data says about each cause before anything is
built on it. All numbers are from production (`chess_coach`), 55 players with
20+ analysed games, their last 80 games each. Scripts are in `/root/research/`.

## Method: one test for every idea

For an idea X (a motif or a principle):

- **Opportunity**: the engine's best move is an X move.
- **Followed / found**: the player's move is also an X move (and lost ≤ 30 cp).
- **Missed / broke**: the player's move is not an X move and lost ≥ 80–100 cp.
- **Is it a trait?** Split each player's games into two halves; correlate the
  per-player rate across halves (split-half r). Noise gives r ≈ 0. A thing a
  player does not know shows as a stable rate.

The same check must decide both the hits and the misses. The first attempt
counted hits from `move_observations.tactical_pattern_executed`, which is the
shape the review caption chose on a good move — not a detector. It showed
pin 39 hits vs 1,156 misses and fake reliabilities of 0.47–0.77. Do not use
that field as a "found it" signal.

## Results

### Basic tactics: they know them, they miss them — blindness

Opportunity = the opponent's last move gave ≥ 150 cp and the engine's best
reply is the motif (miss classifier's geometry + pin prover; mate in one on the
board). Found = played the engine's move.

| Motif | Found | Missed | Find rate | Split-half r | Missed 2+ and never found |
|---|---|---|---|---|---|
| Fork | 470 | 411 | 0.53 | 0.21 | 0 of 54 |
| Pin | 549 | 464 | 0.54 | 0.24 | 1 of 52 |
| Skewer | 438 | 396 | 0.53 | −0.01 | 0 of 50 |
| Discovered attack | 256 | 228 | 0.53 | −0.07 | 0 of 44 |

Every player finds each basic motif about half the time; differences between
players are noise at ~15 opportunities per player. **A missed fork is a
looking problem, not a knowledge problem.** The plan should train the scan
(checks, captures, threats), not "learn the fork". This agrees with the coach
plan's reflection grid, where `found_when_asked` should mostly come back true
(cause `not_looking`).

### Principles: some are stable per-player traits — the knowledge axis

| Principle (engine's best move is…) | Followed | Broke | Split-half r | Player p10 / p50 / p90 |
|---|---|---|---|---|
| Develop a knight/bishop from the back rank (first 12 moves) | 5,344 | 933 | **0.89** | 0.69 / 0.88 / 0.95 |
| Rook to a file with no own pawn | 1,804 | 1,189 | 0.45 | 0.43 / 0.60 / 0.76 |
| Push a passed pawn | 1,430 | 406 | 0.34 | 0.59 / 0.78 / 0.89 |
| Castle | 631 | 246 | 0.30 | 0.42 / 0.75 / 0.91 |
| King move in an endgame (≤ 4 pieces, no queens) | 1,977 | 490 | 0.19 | 0.65 / 0.81 / 0.88 |

Development is a strong individual trait: the same players skip it game after
game. Part of that can be repertoire (the same line replayed), which is still a
thing the player does not know about their own opening. Endgame king activity
is common in lost endgames (best move a king move in 37 of 165 endgame-decided
losses) but is **not** a per-player trait yet — teach it when it happens; do
not diagnose a child with it.

### Endgame theory: rare, but provable

In the 1,000-loss study, 165 losses were decided in the endgame; 20 had ≤ 7
pieces, and in 19 of those the Lichess tablebase proves the played move turned
a **draw into a loss** (rook-and-pawn defence, king must attack the pawn, queen
against a pawn on the seventh). About 2% of all losses, each a textbook
position with a matching Lichess Practice lesson.

### Behaviour

Of 32,744 stored misses with clock data: 7% played with under 30 s left, 11%
played in under half the player's own median move time, 38% after thinking at
least twice their median. Hurry explains under a fifth of misses.

## What follows for the coach

1. Tactics motifs → cause "not looking" by default; train the scan habit.
2. Opening development → first candidate for a per-player knowledge diagnosis
   (needs a move-level detector with precedence under piece safety/tactics,
   graded in SHADOW first).
3. Endgame theory positions → a per-moment lesson ("this is a known position"),
   tablebase-proven, linked to the matching practice position.
4. Behaviour → only where the clock says so (low clock, fast vs own median).

## Data fix done the same day

`scripts/rederive_gap_labels.py` re-derives `missed_pattern / subtype /
severity` on stored `move_observations` where the current classifiers disagree.
It carries 5374d0f6 (Black evals) and three earlier precision fixes that never
reached stored rows (2a6b0c1b passed pawn, eee855f0 mate in two, b4ca0ade
fork vs deep mate) — the White negative control showed them as drift (83 label
changes in 300 White games). 4,580 rows changed in all (2,612 Black, 1,968
White).

**The undo files for that run were lost.** They were written inside the
backend container, which has no source mount, and the next deploys recreated
it. Every changed row carries `labels_rederived_at`; the old labels can only be
rebuilt by re-running the classifier code from before these fixes on the
stored analyses. Undo files for later runs are copied to the host
(`/root/backfill_undo/`).

## Opponent moves stored as the child's (found by the development backfill)

The development backfill changed 465 labels in Play-with-Coach games, all to
empty. Cause, older than this work: 257 coach analyses (April–September 2026)
list both sides' moves in `move_evaluations` with no `is_opponent_move` flag.
The deriver treated every unflagged move as the child's, and rows are keyed by
(game, move number), so each row held whichever side's move came last — for a
White child, the opponent's move. 3,003 stored rows across 21 players described
the opponent's move (dry run, 2026-11-10).

Fix: `is_users_move` reads the side to move from `fen_before`, which agrees with
the flag on all 505,097 flagged moves in production. `scripts/repair_two_sided_observations.py`
rebuilds only those games' rows; its undo (full old rows) is written to the host.
`rederive_gap_labels.py` compared both sides' derived moves with one stored row
in these games, so its label writes there were noise; the repair overwrites them.

## Built the same day (coach plan amendment A)

- `development_decision` stored per move (9dce9d29).
- Cut-off lock A1: rate below 0.75 with 20+ chances; flags 5 of 55 players
  (gated split-half r 0.79).
- Precision of the gated miss at depth 18, one per random game: **60 of 60**
  (Wilson lower bound 0.940); 41 further misses were owned by a piece-safety,
  king-safety or tactic label. Every moment shown is re-checked on the board
  when the plan is built (best developing move must beat the played move by
  50 cp).
- `knowledge:development` in the coach plan, the child's reflection flow, and
  one parent line once the coach approves.
