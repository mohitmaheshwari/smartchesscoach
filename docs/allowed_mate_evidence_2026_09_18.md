# `gap:king_safety:allowed_mate_exact` — evidence

Status: SHADOW. Says nothing to any player.

## Why it exists

`tactical_oversight` was measured on 2026-09-18 to be a mislabelled mate
bucket: of 500 `generic_oversight` fires, **81% are mate swings**. That is
also why the bucket averages 7,524cp. The signed-off precedence
(`docs/move_classification_from_gold_scope.md` §1, amendment 2) routes those
to `king_safety`, and this detector earns the right to make the claim.

## The measurement that shaped it

An evaluation sentinel is not a proof. Across **3,727** moves whose stored
evaluation was a mate score against the player:

| | share |
|---|---|
| already lost **before** the move — already in the net | **66.5%** |
| stored line too short to reach mate (PVs run 4–6 moves) | 24.3% |
| **mate proven by replaying the line to `board.is_checkmate()`** | **9.2%** |

A detector keyed on the evaluation alone would tell two thirds of those
players they walked into a mate they were already inside. That is the same
failure that has `king_safety` sitting in shadow at 75.4% precision: right
that something was wrong, wrong about what.

Of the 343 proven cases in that sample: **median 1 ply to mate, maximum 3.**

## The claim

Three conditions, all required:

1. the stored evaluation after the move is a mate score against the player;
2. it was **not** already a mate score before the move;
3. replaying the stored continuation from `fen_after` reaches an actual
   `board.is_checkmate()` within 7 plies.

Rendered from the evidence record only:

> Nf6 allows mate in one. The finish is Qxf7#.

## What it refuses to do

The 24.3% whose stored line runs out are returned as **unknown, never denied**.
Silence about a real mate costs recall; denying one costs trust.

## Limits

- Precise and partial by construction: caption-grade trade, not plan-grade.
- Recall is bounded by PV length, not by the detector. The upgrade is a fresh
  engine search on the truncated subset — roughly 5,600 positions corpus-wide
  at ~1.1s each, under two hours of one-off compute. That is Codex's
  CandidateFinder→Verifier pipeline applied surgically rather than to all
  39,000 mistakes.
- It says nothing about *why* the player missed it. Only that the position
  after their move is a forced mate.
