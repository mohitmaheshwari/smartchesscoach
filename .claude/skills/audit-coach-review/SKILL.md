---
name: audit-coach-review
description: Compare a human/LLM coach's review of a smartchesscoach game against Stockfish ground truth. Output a verdict table per move the coach called out, plus a false-positive rate and the worst blunders the coach missed. Trigger when the user pastes coach-style game commentary along with a game_id.
---

# Audit a coach review against engine truth

Compare any coach review (Indian persona, dry analyst, LLM-generated, whatever) against the Stockfish `move_evaluations` we already store for the game. The goal is to make every "this was a blunder" / "this was brilliant" claim defensible against the engine.

## When to invoke

- User pastes coach commentary along with a `game_id` from this codebase
- User explicitly types `/audit-coach-review`
- User asks "is this coach right?" / "did the coach get it?" about a game

Do NOT invoke for plain "review this game" requests with no external coach text — that's just the existing `/api/games/{id}/coach-review` endpoint.

## Required inputs

- `game_id` — the UUID from the user's URL (`/game/{game_id}?move=N`). MUST exist in `db.games`.
- `coach_text` — the full text of the coach's review

## Steps

1. **Pull engine truth** for the game. Use Docker exec on `chess-coach-backend` against the local Mongo. Honor the path-conversion gotcha on Windows + Git Bash: prefix bash commands with `MSYS_NO_PATHCONV=1`.

   ```python
   docker exec chess-coach-backend python -c "
   import os, asyncio
   from motor.motor_asyncio import AsyncIOMotorClient
   async def m():
       db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ.get('DB_NAME','chess_coach')]
       g = await db.games.find_one({'game_id':'<GAME_ID>'}, {'_id':0,'user_color':1,'result':1,'opening_name':1})
       a = await db.game_analyses.find_one({'game_id':'<GAME_ID>'}, {'_id':0,'stockfish_analysis':1})
       evals = ((a or {}).get('stockfish_analysis') or {}).get('move_evaluations') or []
       print('meta:', g)
       for x in sorted(evals, key=lambda x: -(x.get('cp_loss') or 0))[:12]:
           print(f'  m{x[\"move_number\"]:>3} {x.get(\"move\"):>6} cp_loss={x.get(\"cp_loss\"):>6} best={x.get(\"best_move\"):>6} class={x.get(\"classification\")}')
   asyncio.run(m())
   "
   ```

2. **Parse the coach review** for move references. Extract all move numbers + SAN the coach calls out. Catch patterns like "Move 22 — Qf6??", "8. Ne4?", "ate 50. Kf3 was the blunder", etc. Record what the coach SAID about each (mistake / brilliant / good / etc.).

3. **Cross-reference** every coach-flagged move against the engine's `cp_loss` for that move. Build a table:

   | Move | Coach's call | cp_loss | Verdict |
   |------|---|---|---|
   | 22 Qf6 | "the real blunder" | 599 | ✓ Real turning point |
   | 54 Kd7 | "ran king away" | 10 | ❌ False flag — engine doesn't care |

4. **Compute coverage**:
   - **False-positive rate**: coach-flagged moves where `cp_loss < 50` ÷ total flagged. Below 50cp the engine is essentially indifferent — calling these mistakes is confabulation.
   - **Missed blunders**: top 3 moves by `cp_loss` the coach never mentioned. List as "the coach skipped m{N} {SAN} ({cp_loss}cp)". If the BIGGEST cp_loss move isn't in the coach's review, surface this prominently.

5. **Note pattern observations** for the abstraction track (we're collecting these to feed product decisions):
   - Did the coach pick by *concept* (knight kicked, queen exposed) or by *severity*? Most LLM coaches are concept-first.
   - Did the coach narrate the actual result (won/lost)? Some review LLMs invent a winning arc on a loss.
   - Was there visible confabulation — coach reasoning aloud and getting confused mid-paragraph?

## Output

Keep it tight — under 400 words, structured. Use the table format above. End with:
- one-line **false-positive rate**
- one-line **biggest miss** (the blunder the coach skipped, if any)
- 2-3 line **pattern observation** for the audit log

Do NOT write a full essay. Audit, don't editorialize.

## Notes

- The Docker route assumes local-dev. For production audits, ask the user to run the read-only mongo query on the server and paste the result.
- The `cp_loss < 50` floor matches `PRINCIPLE_CP_FLOOR // 2` in `services/game_coach_review.py` (our actual review composer uses 100cp; for AUDIT we're more lenient about what counts as a fair flag, since coaches at 50cp aren't egregiously wrong).
- If the game isn't analyzed yet (`is_analyzed: False` or no `game_analyses` row), say so and stop. Don't fake it.
- See [memory/project_docker_no_source_mount.md] for the path-conversion gotcha and the `docker cp` trick when iterating.
