# Promoting detectors can no longer change what a user sees

2026-09-26. Written because "which detector do we promote next" turns out to
have the answer "none of them, and that is fine". Measured, so nobody spends
another week on the question.

## The test, run before the work instead of after

A detector can be repaired to perfect precision and still move nobody. The
picker takes the top-scoring topic per user, so a new subtype only changes
what a player sees if its **pattern** is not already their top topic AND its
evidence outweighs their current best.

That test is cheap. It was run last for `opening_knowledge` — after hours of
repair — and the answer was 0 of 33. So it is run first here, for every
candidate at once.

## Every candidate, ranked by whether it would change anyone's topic

```
  candidate                                    rows  users  grade    changes topic for
  missed_tactic:missed_generic_tactic          4539     55  unreg.   16 of 55
  piece_safety:small_slip                      5939     56  unreg.   12 of 56
  tactical_oversight:generic_oversight         3419     55  unreg.    6 of 55
  endgame_technique:generic_endgame_slip       2955     49  unreg.    6 of 49
  piece_safety:tactical_seq_loss               3771     55  unreg.    5 of 55
  opening_knowledge:unverified_hint            3146     55  unreg.    3 of 55
  piece_safety:simple_hang                     2382     54  caption   1 of 54
  missed_tactic:missed_pin                     1299     50  shadow    nobody
  king_safety:weakened_shelter                  848     50  unreg.    nobody
  endgame_technique:passed_pawn_ignored         667     42  unreg.    nobody
  piece_safety:quiet_blunder                    637     47  unreg.    nobody
  piece_safety:threat_ignored                   591     53  unreg.    nobody
  missed_tactic:missed_discovered_attack        404     43  shadow    nobody
  king_safety:king_in_center                    345     35  unreg.    nobody
  opening_knowledge:retreated_a_developed_piece 154     33  shadow    nobody
```

**The split is total.** Every candidate with a provable claim moves nobody.
Every candidate that would move somebody is a generic bucket whose own name
says it is unclassified — `generic`, `slip`, `oversight`, `unverified_hint`.
There is no third group.

An earlier cut of this table looked more promising because it compared a
candidate against the user's best authorized count and called anything larger
a win. That overstates: `piece_safety:small_slip` outscoring
`piece_safety:destination_safety_exact` leaves the user on piece_safety
either way. More evidence for the topic they already have is not a different
focus.

## Classifying the biggest bucket does not rescue it

`missed_generic_tactic` is the residual: the engine's best move is not a fork,
pin, skewer or discovered attack, and the player lost 200cp or more. It
decomposes cleanly — what the best move does, against a negative control of
engine-approved moves:

```
                              bucket    control    enrichment
  capture, not winning         28.4%       4.1%         6.9x
  takes material, small        25.5%       3.3%         7.7x
  gives check                  23.1%       4.9%         4.7x
  takes free material 200+     23.0%       3.2%         7.2x
  quiet move                    0.0%      84.2%            -
```

Not one of the 4,000 sampled is a quiet move, against 84.2% of ordinary
moves. So the bucket is real and fully decomposable, and
`takes_free_material_200+` is provable by SEE alone with no engine.

And it still does not matter. That slice is 1,039 rows across 53 users, a
median of **7 per user**, against incumbents in the hundreds:

```
  would change the topic for: 1 of 53 users
```

## Why this is the right outcome, not a failure

Current focus distribution across 57 users with evidence:

```
  piece_safety   40
  king_safety    16
  missed_tactic   1
```

For 600-1500 players, hanging pieces genuinely is the first problem. The
picker saying so for two users in three is not a bug to engineer around — it
is the correct answer, arrived at from their own games.

**So the lever is not which topic we name. It is the quality of the coaching
inside the topic** — the lesson a player is handed once we have said
"piece safety", the caption on the move, whether the puzzle is answerable.
That is where the remaining work is.

## Two things found on the way

**`missed_free_piece` is a dead field.** It is set only when the v5 shape id
is `free_piece`, and it is True on 155 of 4,539 rows while SEE proves free
material in 1,039 — it misses 85% of them. It is also **written and never
read**: the deriver is the only file that mentions it. So the miss costs
nothing today, and fixing it would buy nothing until something consumes it.

**The precise detectors are small by nature.** `missed_pin` at 1,299 rows and
81.1% precision, `missed_discovered_attack` at 404 — these are good detectors.
They are simply rare next to "you left a piece where it could be taken", which
fires constantly. Rarity is not a defect to fix; it is what a specific motif
looks like in a 600-1500 corpus. See
[[project_rare_concepts_teach_by_puzzle_not_detector]] — the same conclusion
reached from the other direction, that rare concepts are taught by puzzle
rather than by detector.
