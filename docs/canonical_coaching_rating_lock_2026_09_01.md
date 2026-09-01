# Canonical coaching rating — data lock (2026-09-01)

Status: **LOCKED FROM PRODUCTION HISTORY**

## Decision

For coaching tone and rating-band difficulty, use the median rating from the
player's three most recent chronologically valid games on their explicitly
selected platform. If no platform is selected, use the platform of their most
recent valid game. Stored profile/user fields remain fallbacks only.

This rating is a presentation and difficulty signal. It does not choose the
player's improvement focus; verified behavior from their games does.

## Why three games

The read-only bake-off used 14,307 dated/rated games. Each candidate predicted
the next observed rating within the same player and platform.

| Window | Median absolute error | p90 error | Median estimator step |
|---:|---:|---:|---:|
| 3 | **8** | **18** | 2 |
| 5 | 8 | 25 | 0 |
| 10 | 12 | 41 | 1 |
| 20 | 16.5 | 66.5 | 0.5 |

Three games has the best next-game accuracy and a small median step. A one-game
value was rejected as needlessly volatile. Ten and twenty games are materially
staler.

## Production defect confirmed

`bhutramohit@gmail.com` explicitly selects Chess.com. The prior resolver showed
1199 from `player_profiles.current_rating`, while the latest Chess.com rating
was 887 and the last-three median was also 887. A newer Lichess game at 1334
must not silently override the user's selected platform because ratings are not
interchangeable across pools.

Aggregate evidence is versioned in
`backend/data/corpus_snapshots/canonical_rating_resolution_2026-09-01.json`.
The reproducible read-only audit is
`backend/scripts/audit_rating_resolution.py`.
