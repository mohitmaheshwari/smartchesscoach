# Caption-Template Authoring Runbook — Round 1

Workflow for Parth (and Mohit) to author caption templates against
real games. Started 2026-05-13.

## Step 1 — Pick the 10 games (Mohit runs once)

```bash
docker exec -it chess-coach-backend python scripts/pick_authoring_games.py
```

Output: 10 game_ids, 2 from each of 5 buckets:
- TACTICAL_BLUNDER (clean hangs / forks missed)
- POSITIONAL_MISTAKE (Ne7-style positional drops)
- ENDGAME (game reaches endgame phase)
- OPENING_DRIFT (subtle opening misses)
- WON_WITH_BLUNDER (won the game despite blunder)

Share the 10 game_ids with Parth.

## Step 2 — Parth opens each game (10 times)

For each game in the list:

```
https://YOUR_DOMAIN/game/{game_id}?show_facts=1
```

The `?show_facts=1` query param enables a per-move fact-dump panel
that shows the raw extractor output JSON for each move.

For every move Parth wants to author/correct, he fills one row in
the authoring sheet (Google Sheets or similar).

## Step 3 — The authoring sheet

Columns (left to right):

| Column | Required | Description |
|---|---|---|
| `game_id` | yes | The game's UUID. |
| `move_number` | yes | Full move number (e.g. 8). |
| `move_san` | yes | The move in SAN (e.g. "Ne7"). |
| `current_caption` | yes | What the caption currently says — copy verbatim from the review page. |
| `issue_with_current` | yes | One-sentence description of what's wrong. |
| `suggested_caption` | yes | What Parth thinks it should say — exact words. Can be position-specific for now. |
| `principle_id_or_new` | optional | If this caption maps to an existing principle (e.g. TAC_HANGING_PIECE), put the id. If it should be a NEW principle, put "NEW: " plus a name suggestion. |
| `generalizable_template` | optional | Same suggestion but with {placeholders} for facts. Skip if you can't generalize cleanly yet — we'll do this in Step 4. |
| `facts_needed` | optional | List of facts the template references. New facts (not in the extractor yet) start with `fact:` — e.g. `fact:piece_blocks_own_pieces`. |
| `author_notes` | optional | Free-text — what made this hard to caption, edge cases, etc. |

**Important:** Parth only authors `suggested_caption`. Generalizing
to templates is a Step 4 conversation. Position-specific is fine for
the first pass.

## Step 4 — Mohit + Parth review session (once Round 1 sheet is full)

After all 10 games are reviewed (estimated ~100-200 sheet rows):

1. Group sheet rows by similar pattern. E.g., 5 rows all flag "knight
   blocks own bishop" — those generalize to one template.
2. For each cluster, Parth writes the generic template with placeholders.
3. Claude imports the templates into
   `backend/services/authored_templates_parth.py`.
4. Each template's `required_facts` is checked against the extractor.
   Missing ones go on the EXTRACTOR_TODO list.
5. Claude adds the missing extractor facts one at a time, with
   per-fire audits per the audit-coverage-tracks-surface rule.

## Step 5 — Round 2

After Round 1 ships (templates wired + extractor extended), measure:
- How many user-flagged captions in subsequent games are addressed?
- Which pattern clusters are still under-served?

Decide whether Round 2 is another 10 games of authoring, or different
shape of work.

---

## Notes for the author

- **Don't worry about templating in Round 1.** Just write what you'd
  say for THAT exact position. The generalization happens in Step 4.

- **Honest silence > wrong caption.** If you don't have a good
  caption for a move, leave it blank in the sheet. Default of "" is
  better than guessing.

- **Reference the facts that exist.** The `?show_facts=1` panel shows
  exactly what the extractor produces. If you want to say
  "your knight is now hanging" — verify `is_exchange_losing` is True
  or `pieces_now_undefended` contains the knight. If neither, the
  fact doesn't exist yet and we add it.

- **Mark dual-meaning moves clearly.** If a move is both a tactical
  hang AND a positional mistake (rare), note both in `author_notes`.
