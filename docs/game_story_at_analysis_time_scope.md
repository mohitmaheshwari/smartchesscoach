# Every game leaves something: a stored game story

**Status:** scope, 2026-10-20. No code written.
**Asked for:** *"each game leaves something, like trapped your queen, or miss
mate in 1 ... but also some other stories, like inactive pieces for long time,
bad bishop ... so good and bad parts of a game, can we build it while the game
gets analysed?"*

---

## 1. The answer is yes, and most of it is already built

The request contains two different shapes, and the product has both. What it
does not have is the assembly, the persistence, or a surface.

| shape | example | where it lives | state |
|---|---|---|---|
| **moment** — one move | trapped your queen, missed mate in one | `move_observations`, written at analysis time | **works** |
| **span** — many moves | pieces inactive for twelve moves, no pawn shelter for eight | `board_state_game_summary.compute_game_summary` | **works, reaches nobody** |

Measured for this scope:

**Moments**, over 400 analysed games — median **4** per game, max 22, and 73
games with none:

| polarity | total | top entries |
|---|---|---|
| negative | 1,063 | missed_generic_tactic 231, destination_safety 148, small_slip 132, simple_hang 81, ignored_king_attack 64 |
| **positive** | **548** | found_best_in_critical 133, responded_to_threat 108, punished_opponent_blunder 72, executed motifs |

**Spans**, over 250 games — median **3** per game, max 10, 51 games with none.
Ten of the eleven trends fire on a fifth to a half of games:

| trend | games |
|---|---|
| a piece with almost nowhere to go | 48% |
| pieces stayed on your side of the board | 44% |
| opponent owned an open file | 41% |
| opponent dominated the centre | 36% |
| king sat without its pawn shelter | 30% |
| pushed a piece alone into their territory | 28% |
| opponent had connected rooks, yours weren't | 26% |
| minor pieces stayed on the back rank | 24% |
| only your queen was doing anything | 23% |
| opponent aimed pieces at your king | 20% |
| behind in development | **0%** (effectively dead) |

A healthy, broadly-distributed layer — genuinely unusual in this codebase.

## 2. What is actually missing

1. **Spans are not persisted.** `compute_game_summary` is a pure function run
   at READ time from `decryption_v5_data`, which is itself lazily regenerated.
   A story should be derived once, when the game is analysed.
2. **Nothing is fetching them.** `GET /games/{game_id}/board-summary` exists
   and no frontend code calls it. Eleven working trends reach no player.
3. **Nothing assembles the two halves.** There is no per-game object that says
   "here is what this game left you", and a game with 22 moments and 10 trends
   needs selection, not a dump.
4. **No ranking.** Which two or three things should a player carry out of a
   game is the whole product question, and nothing answers it.
5. **"Bad bishop" specifically does not exist.** The nearest is
   `bs_worst_placed_piece` ("a piece with almost nowhere to go"). Bishop work
   is deferred by your own instruction, and the structural-versus-effect rule
   applies when it resumes.

**So this is an assembly job over two working layers. It needs no new
detection**, which is the opposite of where I would have guessed.

## 3. Design

At analysis time, after `move_observations` are derived, write one
`game_story` onto the analysis document:

```
game_story = {
    "schema_version": "game_story.v1",
    "derived_at": ...,
    "moments": [ {polarity, subtype, move_number, severity, detector_quality_id} ],
    "spans":   [ {fact_id, occurrence_count, move_numbers, total_severity} ],
    "headline": <the one thing to remember>,
}
```

Rules that follow from what was measured, not from taste:

- **Compose, never recompute.** Moments come from `move_observations`, spans
  from `compute_game_summary`. No new metric, no second vocabulary. If a
  detector is wrong, it is wrong in one place.
- **Only authorized moments may be named.** A moment whose
  `detector_quality_id` is SHADOW can be stored but must not be shown — the
  same rule that governs captions. Stored-but-unshown is deliberate: it makes
  the story auditable before it is published.
- **A span must earn its place by duration**, which `compute_game_summary`
  already enforces with a minimum-occurrence threshold.
- **Guarantee at least one positive when one exists.** This is the rule the
  measurement demands: negatives outnumber positives 1,063 to 548 *and* carry
  higher severity, so any naive top-N by severity produces an all-bad story.
  "Good and bad parts" will not happen by accident.
- **Say when a game left nothing.** 73 of 400 games have no sharp moment and
  51 of 250 no span. An honest empty story beats an invented one, and silence
  here is a fact about the game rather than missing coverage.

## 4. Decisions I need, because they are product judgements

1. **What ranks the headline?** Candidates, and they disagree:
   - **decisiveness** — did it change the result? Sharpest, and the stalemate
     and lost-mate work already computes it.
   - **severity** — biggest centipawn or win-probability swing. Available but
     skewed: it will almost always pick a blunder.
   - **recurrence** — the thing this player keeps doing, which ties the story
     to their focus rather than to this game alone.

   My recommendation: **decisiveness first, recurrence second**, severity only
   as a tiebreak. A player remembers the moment that decided the game and the
   habit they keep repeating; the largest eval swing is often neither.

2. **How many items?** I suggest one headline, up to two further moments, up to
   two spans. Five is already more than most people carry out of one game.

3. **Is one guaranteed positive right even in a badly played game?** I think
   yes and the vision says so too — a coach is not shy of the negative, but a
   game where the player defended well for twenty moves and then lost to one
   blunder has two true stories, and showing only the blunder is the dishonest
   one. Worth your word, since it is a tone decision.

## 5. How it gets verified

1. **Non-zero and non-trivial:** story present on a sample of games, with the
   measured medians (≈4 moments, ≈3 spans) surviving selection.
2. **Polarity:** no game with an available positive moment produces an
   all-negative story.
3. **Composition, not duplication:** assert the story's moments are a subset of
   that game's `move_observations`, and its spans a subset of
   `compute_game_summary` output. A story element with no source is a bug.
4. **Authorization:** no shown moment carries a SHADOW `detector_quality_id`.
5. **Honest emptiness:** a game with no moments and no spans yields an explicit
   empty story, not a fabricated one.
6. **Derived once:** re-analysing the same game produces the same story; the
   read path never recomputes it.
