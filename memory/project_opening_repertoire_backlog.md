---
name: Opening Repertoire Feature (Backlog)
description: Show player's opening win rates in Progress page, recommend sticking to 2 best openings, pass opening to Play with Coach as input parameter
type: project
---

**Feature:** Opening repertoire tracking + focused practice

**Progress page addition:**
- Show all openings player has played (from imported games), split by White/Black
- Win/loss record per opening
- Highlight "your best" opening per color
- ~~Coach recommends sticking to top 1-2 openings per color~~
  **REVERSED by Mohit 2026-09-24: "we want people to coach up with more
  opening knowledge."** The goal is BREADTH, not consolidation. Narrowness
  is itself the weakness: accuracy inside one line you have played 200 times
  is circular and says nothing about strength. Coach should notice a narrow
  repertoire and offer the player something new, not reinforce the two they
  already know.

  **REFINED same day, and this is the actual model.** Neither "stick to 1-2"
  nor "broaden" alone is right. Narrow is a STAGE, not a fault:

      focus one opening -> player keeps playing it
      -> coach detects MASTERY of it -> switch focus to a new opening
      -> repeat

  So the coach rides the narrow phase deliberately, then GRADUATES the
  player. Mohit: "until coach finds out that you have mastered Italian and
  you keep playing Italian and then is the time to switch to other openings
  ... that's when people will come back to us."

  THE RETURN MECHANISM IS THE FOCUS CHANGING. That is the product's reason
  to be reopened, not any single lesson.

  Measured 2026-09-24 and this is the problem: of 193 focuses that ended,
  163 ended as `superseded_v6..v9` -- killed by OUR picker version bumps.
  Zero have ever ended because a player mastered the thing. Every resolution
  value that exists is a failure mode (measurement_pending 35, metric_gap
  18, detector_not_authorized_for_plan 11). So the graduation step Mohit is
  describing -- the one that brings people back -- has never once fired.

**Play with Coach integration:**
- Coach receives opening as input parameter
- Steers the game into that specific opening
- Uses opening_theory_tree.json data for coaching during the game
- Teaches the IDEAS behind the opening, not move memorization

**Why:** Real coaches focus students on 1-2 openings. Mastering two openings deeply > knowing ten superficially. This is how 1200s reach 1400.

**How to apply:** This is a backlog item, not current work. Build after the fundamentals coaching engine is done.


---

## Measurement, locked 2026-09-24

A repertoire is the player's OWN first moves, not the opening name and not
both sides' moves. Three wrong units were tried first:

- **opening name** -- 185 distinct "openings" in 732 games, because the
  names are variation-level ("Italian Game: Giuoco Pianissimo"). Makes every
  player look broad.
- **first move only** -- `e4` is not an opening (Mohit).
- **six plies, both sides** -- fragments to 4%, because the OPPONENT varies.

**Depth 3 of the user's own moves is the unit.** Measured across players
with 40+ White games:

```
depth   top line   lines for half   distinct
  2        23%           3             20      <- e4 Nf3, not an opening
  3        11%          10             35      <- USE THIS
  4         6%          20             45
  5         4%          23             52      <- shattered
```

The cliff is between 3 and 4: top line halves, lines-for-half doubles.

**Depth 3 gives breadth** ("half your White games are the same ten starts").
It CANNOT give within-opening narrowness ("inside the Italian you always
play d3") -- that needs depth 5, which is noise. For that, condition on the
POSITION instead of the sequence: of games reaching this exact position,
what did the player choose? That gate fires for 14 of 70 users, 26 spots,
almost all at move 4.

Example: `user_398eda90a  move 4  plays Nc6 26/29, also Bg4 x3`.

Open caveat: only ~7 users have enough parseable PGN for the depth-3
measure. PGN coverage is unverified and blocks putting this on a surface.
