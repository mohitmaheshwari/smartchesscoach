# Game tags: finding games by what happened in them

Status: signed off by Mohit 2026-10-22 ("go"). Builds on
`docs/game_story_by_phase_scope.md`.

## What it is

Every analysed game carries tags that say what happened in it, so we can pick
games from one player or from the whole community. Examples: the player's
queen could have been trapped and the opponent missed it; the player shut in
the opponent's knight; the player came out of the Caro-Kann worse.

## What the user sees

The Review Queue (`/review`, reviewers only) gains a "Game tags" picker,
rarest tags first, each with how many games carry it. Choosing tags shows the
games that carry all of them. Each game row shows its player tags; clicking a
tag opens the game at the move behind it.

```
Game tags  [ Add a tag (52)                    v ]
           [ queen trapped, opponent missed x ]

W  Mohit   Queen's Pawn Opening                     EddieDawg1971
           [queen trapped, opponent missed · Ng5] [let off · Nxg5]
```

## In scope

- Tags derived from the game ledger and nothing else (`services/game_tags.py`).
- Each tag keeps the moves behind it.
- Stored as `game_analyses.game_tags`, indexed, written by the analysis
  worker, by the story loader when it rebuilds, and by
  `scripts/backfill_game_stories.py` for older games.
- Search and counts on the reviewer endpoints, and the Review Queue picker.
- The ledger proves trapped rooks the same way as trapped queens.

## Out of scope

- Executed tactics such as a fork. They are recorded only once a game's
  review captions exist, so new games would never carry them.
- Automatic use by the coach's game pick or the lesson builder. Tags are
  checked by eye on the reviewer page first.
- Player-facing tag search.

## Measured, 2,000 games, 2026-10-22

Four to eight tags per game. Rare tags: queen trapped and missed 14 games,
rook trapped and missed 30, opponent's knight shut in 51. Common tags,
useful only in combination: punished a blunder 1,505, lost a winning
position 1,487. "Tactically active" is three or more tactical successes,
about the top third of games.
