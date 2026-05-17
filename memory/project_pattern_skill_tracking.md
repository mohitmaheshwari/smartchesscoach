---
name: pattern-skill-tracking
description: Track per-player pattern outcomes (applied / defended / missed / fell-for) for each of the 23 shape patterns. Data collected silently — not surfaced to user yet. Becomes player-profile skill signal for future personalisation.
metadata: 
  node_type: memory
  type: project
  originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---

For each of the 23 named shape patterns in [[shape-patterns]], record the player's actual interaction with that pattern in every game they play:

| Outcome | Meaning |
|---|---|
| **applied** | Pattern was available for THEM to play; they played the executing_move | 
| **missed_apply** | Pattern was available for them; they played something else |
| **defended** | Pattern was available for OPPONENT; player's response neutralised it (engine no longer prefers the pattern move) |
| **fell_for** | Pattern was available for opponent; opponent played it AND it gained advantage |
| **prevented** | Pattern geometry existed but player's prior move broke the setup |

Each game's per-move record already has enough data:
- `shape_pattern_id` (which pattern was on the board)
- `shape_pattern_executing_move` (the move that would execute it)
- `played_move_uci` / `move_san` (what was actually played)
- `is_user_move` (whose turn it was)
- `cp_loss` (whether the played move was good or bad relative to the pattern)

Aggregate by user_id × pattern_id over a rolling window (last 20 games). Outputs a skill profile per pattern:

```
free_piece:      apply 87% (47/54) | defend 92% (12/13) | strong
knight_fork:     apply 41% (7/17)  | defend 60% (3/5)   | weak
pin:             apply 78% (25/32) | defend 31% (4/13)  | mixed — DEFENDS POORLY
```

**Why:** The user explicitly asked for this 2026-05-12: "you register that, so you know about a player profile in much deeper sense, we might not show it to user, but we should have the data, so we can use it later." Memory anchors are principle names ([[sub1500-memory-anchors]]); skill ratings per principle let us pick which patterns to drill, which to prescribe, which to celebrate.

**How to apply:** Don't surface to user yet (per user direction). Just collect. The data table lives in a new `pattern_skill_profile` collection keyed by `(user_id, pattern_id)` with rolling counts. Update after every analysed game. Future surfaces that could consume this:
- Pattern of the Day → pick a WEAK pattern, not just frequent
- Play with Coach → coach plays positions where user is weak on a pattern
- Training prescriptions → drill the patterns the player consistently misses

**Sequencing:** Build after [[knowledgebase-to-review-wiring]] (traps + openings + Engine-2) ships, since it's an additive data layer not a user-facing feature. Don't block live coaching work on it.
