# Caption-Template Authoring Runbook — Round 1

Workflow for Parth (and Mohit) to author caption templates against
real games. Started 2026-05-13.

**No sheet. No external tooling. Inline-on-site authoring.**

## Step 1 — Pick the 10 games (Mohit runs once)

```bash
docker exec -it chess-coach-backend python scripts/pick_authoring_games.py --output /tmp/parth_games.txt
docker exec -it chess-coach-backend cat /tmp/parth_games.txt
```

Output: 10 game_ids, 2 from each of 5 buckets:
- TACTICAL_BLUNDER (clean hangs / forks missed)
- POSITIONAL_MISTAKE (Ne7-style positional drops)
- ENDGAME (game reaches endgame phase)
- OPENING_DRIFT (subtle opening misses)
- WON_WITH_BLUNDER (won despite blunder)

Share the 10 game_ids with Parth.

## Step 2 — Parth opens each game with the fact-dump on

For each game:

```
https://YOUR_DOMAIN/game/{game_id}?show_facts=1
```

The `?show_facts=1` query param toggles a per-move JSON panel that
shows the raw extractor output for each move. Parth can see what
facts exist for the caption he's about to author.

## Step 3 — Parth flags + authors INLINE

The existing flag icon next to every caption now has an extra field:
**"Authoring (optional) — If you can author the replacement text, paste it here."**

For each caption Parth wants to fix:

1. Click the flag icon next to the caption.
2. **"What's wrong?"** — describe the issue (as today).
3. **"Authoring (optional)"** — paste the replacement text he'd
   want the player to see.
4. Submit. Button reads **"Submit Authored Replacement"** when the
   authoring field is filled.

Storage:
- The flag lands in `move_feedback` collection with new fields:
  - `suggested_caption` — Parth's replacement text
  - `is_authoring_submission: true` — flag indicating authoring mode
- All position context auto-captured (game_id, fen, move_san, severity, cp_loss, etc.)

## Step 4 — Review session (Mohit + Parth + Claude)

After ~10 games of authoring submissions:

```bash
# Query all authoring submissions
db.move_feedback.find({"is_authoring_submission": true})
```

Mohit + Parth review the suggestions:
1. **Cluster** by similar position pattern. E.g., five "knight blocks
   bishop+queen" submissions → one template.
2. **Generalize** the suggested text with {placeholders}.
3. **Identify missing facts** — if a template needs
   `fact:piece_blocks_own_pieces` and the extractor doesn't produce
   it, that's added to the extractor TODO list.
4. **Claude imports** the templates into
   `backend/services/authored_templates_parth.py` and adds the
   needed extractor facts (one at a time, per-fire audit each).

## Step 5 — Round 2

After Round 1 ships, measure:
- How many user-flagged captions in NEW games are addressed by the
  templates Parth authored?
- Which pattern clusters are still under-served?

Decide whether Round 2 is more games, more facts, or different shape.

---

## Notes for Parth

- **Don't worry about templating.** Just write what you'd say for
  THIS exact position. Mohit + Claude will cluster and generalize
  in Step 4.
- **Honest silence > wrong caption.** If you don't have a good
  replacement, leave the authoring field blank — that just submits
  a regular bug flag (issue without suggested text).
- **Reference facts that exist.** The `?show_facts=1` panel shows
  exactly what the extractor produces. Your suggested text should
  reference squares, pieces, and concepts the facts confirm. If
  you want to say something the facts don't support yet, mention
  it in the "What's wrong?" note — that drives the extractor work.
- **Pace.** No deadline. The more games, the better Round 1 sample.

---

## Notes for Mohit

- **Bug flags vs authoring submissions are different.** Both go to
  `move_feedback`. Filter by `is_authoring_submission` to see Parth's
  authored set. Regular flags don't carry suggested_caption.
- **Round 1 doesn't need any new tooling.** Use the existing admin
  feedback view; the new field renders the same way.
- **Stop the round when patterns stabilize.** If after 10 games the
  same 5-7 clusters keep showing up, that's the working set. No need
  to grind through 50 games.
