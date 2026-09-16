# Personalized Opening Coach — Data Lock

Date: 2026-09-16

## Decision population

The read-only production measurement covered 15,418 analyzed games. Of those, 12,753 mapped to a teachable opening. The canonical curriculum contained 41 publishable opening families and 1,008 authored decision positions.

Across 181,814 opening-phase user moves, 29,930 occurred at an authored decision position: **16.46% authored-decision coverage**. That is sufficient to verify specific taught decisions, but not sufficient to infer whole-opening mastery from branch evidence alone.

## Locked decisions

### Sound alternatives

An authored move is accepted. A different legal move is accepted as a `sound_alternative` only when a server-side Stockfish comparison measures at most **20 centipawns of loss** from the mover's perspective.

This is not a new threshold. It is the existing engine-aware opening threshold already used by `opening_mastery_tracker.py`. In the production re-encounter sample it produced:

- 90.79% successful authored-position decisions;
- 25,513 repeated-decision transitions;
- 92.05% baseline next-decision success;
- 97.17% next-decision success after one success;
- 67.66% next-decision failure after a failure, across 2,016 failure transitions.

The 40cp and 60cp candidates classified 94.31% and 96.25% of decisions as successful. They were rejected for practice acceptance because they erase too much useful discrimination and no longer match the existing definition of an engine-sound book alternative.

### Mastery and staleness

V1 does **not** add an automatic branch `reliable` or `stale` promotion rule. The available historical corpus does not distinguish independent practice, assisted practice and real-game application consistently, and authored decisions cover only 16.46% of opening moves.

V1 records those evidence states separately. A later data lock will choose promotion and staleness rules from the new evidence stream. Lesson completion and assisted success never promote mastery.

### Existing opening-level bands

The active repertoire keeps its existing production-derived opening-phase bands:

- minimum four analyzed games before judging the opening;
- first twelve opening plies;
- under 23cp lost per move: `know`;
- 23cp through under 48cp: `drill`;
- 48cp or more: `learn`.

Those thresholds came from the p33 and p66 values of 13,909 analyzed games. They describe broad opening performance, not branch mastery.

### Canonical identity

- Canonical player-opening owner: `user_opening_mastery`.
- Repertoire portrait: `user_opening_profiles` remains derived and read-only from the mastery perspective.
- Opening theory: the existing unified opening source and verified curriculum remain authoritative.
- Decision identity: normalized FEN first four fields, canonical opening key, player color and role. A stable hash may be used as a storage key, but no new theory table may be introduced.

### Player perspective

Every new practice evidence item records `player_color` and `role`:

- `chosen_opening` when the player is studying the curriculum side;
- `answering_opponent` when the player is studying how to answer the opponent's system.

### Initial cohort evidence

The two strongest complementary families for a bounded later rollout are:

- Italian Game: 263 repeated decision keys, 2,629 observations, 693 games, 40 users.
- London System: 78 repeated decision keys, 661 observations, 457 games, 51 users.

This document does not authorize rollout. It only records why those two families are suitable candidates after source and staging validation.

## Legacy migration preview

The production census found:

- `user_opening_progress`: 6,952 rows / 57 users;
- `user_opening_mastery`: 727 rows / 67 users;
- mastery rows with analyzed-game IDs: 643;
- `opening_learning_progress`: zero rows;
- non-empty `branches_seen`: zero rows;
- `user_opening_profiles`: 78 rows, including 51 with recurring deviations and 29 with recurring engine-confirmed mistakes;
- `opening_practice_sessions`: 25 rows / 2 users, with 9 completed sessions; 6 of those 9 completed sessions contained mistakes.

Therefore the safe migration rule is locked as:

- analyzed-game IDs and their accuracy observations are evidence-backed;
- practice completion is exposure unless the server can reconstruct retries and hints;
- legacy `mastered` labels are not imported as proof;
- `opening_learning_progress` is removed from canonical read paths rather than backfilled;
- broad legacy progress remains available to old flows, but is an adapter input only and cannot overwrite canonical evidence.

No production write or migration is authorized by this data lock.

