---
name: lichess-detector-loop
description: Measure and fix an EXISTING detector against Lichess's theme-labelled puzzles, which are the truth source. Run N puzzles of a theme through the detector; every puzzle it fails to fire on is a bug report. Cluster the misses by cause, fix the biggest cluster, re-run. Use whenever asked to improve, validate, check or "sharpen" a detector, or when asked whether a detector is good enough. Never build a new detector before running this on the existing one.
---

# The Lichess detector loop

Mohit, 2026-09-21: *"use existing detectors, run 1000 puzzles from lichess
on those detectors and detectors should fire on each one. If they don't
fire on any puzzle, that's the one for you to fix, because lichess is
truth."*

That is the whole method. This file exists because a session spent hours
going the other way and produced nothing shippable.

## Rule 0 — do not build a detector

Before writing any detector code, find the existing one. In one session
I built `simulate_missed_fork` while `services/fork_puzzle_proof.py`
already covered all five piece types with payoff verification, and I
built a Lichess validator while
`backend/scripts/validate_detectors_against_lichess.py` already existed.
Both were reverted. Grep first:

```bash
grep -rn "def .*<motif>\|<motif>_proof\|detect_<motif>" backend/services/ | head
ls backend/scripts/ | grep -iE "validate|bakeoff|promotion"
```

## Rule 1 — Lichess is the truth source

Tested, not assumed. Of 30 positions where our detector fired and Lichess
did **not** tag the theme, engine adjudication said Lichess was right in
at least 20, and about half the rest were other tactics (pin, skewer,
deflection) that we were mislabelling. Lichess even caught an error of
mine: I called `AQqK8` a queen fork; it is a queen *trade*, and Lichess's
tags said so.

So: **a miss is a bug in us, not a mislabel in Lichess.** Do not spend
time arguing that Lichess under-tagged. That instinct was wrong every
time it was checked.

Caveat worth stating once to the user, then not relitigating: Lichess
themes are computed by Lichess's own tagger, not hand-labelled. It is a
different team's implementation over millions of solver-tested positions,
which is far stronger than our own second copy — but it is not human
semantic gold, and the promotion lock still distinguishes the two.

## Rule 2 — play the line before you measure

Push the moves and look at the board. Ask what the move CREATES, not only
what already exists.

This rule exists because the same error appeared three times in one session:

  - `9OVqg`: I asked "is anything pinned?" of the position BEFORE the
    solution and reported that half of Lichess's `pin` puzzles contain no
    pin. `Rf5` is what creates the pin. Measured correctly it is 84.7%,
    not 50.2%. Mohit found it in seconds by playing the move.
  - fork: only `best_move` was tested; 130 of 300 misses had the fork two
    to four plies later in the same stored line.
  - a verifier measured 34.5% because it tested a stricter claim I had
    invented rather than the claim the caption makes to the player.

A measurement over a corpus only answers the question you already knew to
ask. It cannot tell you what a motif IS. Two positions examined properly
beat a thousand counted with the wrong probe — two of Mohit's rulings
overturned claims a 1000-puzzle run had "confirmed".

Concretely, before any measurement: push the solution and print the board;
check the position after the move as well as before; walk the whole stored
line, not just its first move.

## The loop

1. **Sample.** Pull N puzzles carrying the theme, rated 600-1500 (the
   product's band). Sample first and filter in Python —
   `$match` on `themes` over 4.1M rows times out; `$sample` then filter
   does not.
2. **Run the existing detector** on each.
3. **Every non-fire is a bug report.** Collect them.
4. **Cluster the misses by cause.** This is the valuable step and the one
   that gets skipped. Do not fix them one at a time; find the two or
   three reasons that explain most of them.
5. **Fix the biggest cluster. Re-run. Compare.**
6. **Also run the detector on OTHER themes.** Fires there are false
   positives. Recall that climbs while cross-fire climbs with it is not
   an improvement.

## The position convention that breaks everything silently

A Lichess row's `fen` is the position **before** the opponent's move.
`moves[0]` is that move, `moves[1]` is the solution, `moves[2:]` is the
continuation (which is exactly the `pv_after_best` our proof builders
take).

```python
board = chess.Board(p["fen"])
board.push(chess.Move.from_uci(p["moves"][0]))   # now it is the solver's turn
best_san = board.san(chess.Move.from_uci(p["moves"][1]))
```

Serve the stored FEN as-is and every position is wrong, with the user on
the wrong colour — and it fails silently, because the position is legal.

## Reporting

Give recall, cross-fire on at least two other themes, and the miss
clusters with counts. A single recall number without cross-fire is not an
answer: a detector that fires on everything scores 100%.

Numbers measured 2026-09-21, as the baseline to beat:

```
fork              66.0% recall   pin 13.6%  mate 2.4%  skewer 0.4%
discoveredAttack  41.2% recall   cross-fire 0.0%
backRankMate      99.5% recall   cross-fire 1.5%
```

## What "good enough" does not mean

A detector passing this loop still may not reach the user. The fork proof
scored 66% and coaching had never seen a single missed knight fork,
because `build_fork_proof` was wired to the admin review page and nothing
else — `user_pattern_events` held only `queen_fork`. **Always check the
last wire**: does the detector's output reach `user_pattern_events` and
therefore the coach?

```bash
# does it actually reach coaching?
grep -rn "<builder_name>" backend --include=*.py | grep -v scripts/ | grep -v admin_
```

## Related

`/verify-detectors-first` (do not build new ones),
`/detector-quality-scan` (precision sampling on our own games),
`backend/scripts/validate_detectors_against_lichess.py` (the runner).
