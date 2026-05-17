---
name: v5-lazy-generation-mechanic
description: "V5 decryption data is NOT written by the analysis worker — it's regenerated lazily by routes/coach.py keyed on V5_COACHING_VERSION. Re-queuing a game won't refresh the V5 fields; bumping the version constant is the right lever."
metadata: 
  node_type: memory
  type: reference
  originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---

The V5 decryption data flow surprised me on 2026-05-16 (Mohit
`fb_eb1d11ba227f`). It cost ~6 commits and several rebuild cycles
before I traced it.

**Data flow:**
- `backend/analysis_worker.py` runs Stockfish, writes
  `game_analyses.stockfish_analysis.move_evaluations` and other
  Stockfish-derived fields. **Does NOT write decryption_v5_data.**
- `backend/services/game_decryption_v5_service.py` defines
  `V5_COACHING_VERSION` (currently 6) and the function that builds
  `decryption_v5_data` per move.
- `backend/routes/coach.py:805` is the endpoint that returns
  per-move decryption data. Lines 815-822:
  ```python
  if analysis.get("decryption_v5_data") and stored_version < V5_COACHING_VERSION:
      # clear old data so it gets regenerated below
      await db.game_analyses.update_one(
          {"game_id": game_id},
          {"$unset": {"decryption_v5_data": "", ...}}
      )
  ```
- If `decryption_v5_data` is missing or version-stale, the next
  branch in coach.py regenerates it with the current code.

**Why this trips up bug-fix workflows:**
- Re-queuing a game forces Stockfish to re-run, but `decryption_v5_data`
  stays untouched in the DB. The new code in V5 service NEVER runs
  for that game unless you also bump `V5_COACHING_VERSION`.
- This is invisible if you only check the analysis worker — it
  completes successfully, the queue shows `completed`, but V5 fields
  are still from the old generation.

**How to force regeneration of V5 data for a single game:**
- Cheapest: `db.game_analyses.update_one({"game_id": gid}, {"$unset": {"decryption_v5_data": ""}})`
  then visit the lab page or hit the per-move endpoint.
- Global: bump `V5_COACHING_VERSION` in
  `game_decryption_v5_service.py`. Forces regen on EVERY game's
  next-read. Use this when shipping schema changes (new fields like
  `pv_after_played` or new shape patterns).

**How to apply going forward:**
- Any time you add a NEW field or NEW detector to the V5 pipeline,
  bump `V5_COACHING_VERSION` in the same commit. Otherwise the new
  code is dead for all existing analyzed games.
- When debugging "the V5 field isn't appearing": always check
  `decryption_v5_version` on the record first. If it's behind the
  current `V5_COACHING_VERSION`, the new code hasn't run yet for
  that game.

**Why this should have been a 30-min fix instead of 6 commits:**
- I shipped plumbing fixes (pv_after_played, post-move detection,
  key-name corrections) without ever asking "where does this field
  actually get written?" The answer is "lazily by coach.py keyed on
  V5_COACHING_VERSION" — and that's documented IN THE COMMENT next
  to the constant: "increment when coaching logic changes to trigger
  re-generation." I read past the comment multiple times. Audit
  discipline ([[design-clean-code-leaky]], [[check-existing-before-building]])
  would have caught this on the first iteration.
