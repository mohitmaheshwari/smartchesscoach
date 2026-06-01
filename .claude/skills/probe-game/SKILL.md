---
name: probe-game
description: Pull engine ground truth for a game from local Mongo in one command. Returns game meta, top cp_loss user moves, and optional move-N detail (FEN, eval, gap, classification). Trigger when the user asks "what does the engine say about game X" or "show me move N of game X" or any debug question that needs the stockfish data we already have.
---

# Probe a game's engine data

Replaces the manual `docker exec chess-coach-backend python -c "..."` ritual we did 8+ times in one session. Run this when the question is "what does the engine actually say" about a specific game or move.

## When to invoke

- User pastes a `game_id` and asks anything that needs cp_loss / best_move / classification
- User asks "what happened at move N" / "is m{N} actually a blunder"
- User reports a UI bug at `/game/{id}?move=N` and we need the underlying data
- ANY time before answering a chess-analysis question about a specific game — verify first, don't guess from move SAN

Do NOT invoke for questions about game *lists*, statistics across games, or aggregate behavior — those need different queries.

## Required input

- `game_id` — UUID matching `db.games.game_id`

## Optional input

- `--move N` — 1-indexed full move number. If given, also dump the FEN before, played SAN, engine best, cp_loss, classification, cognitive_gap for that specific user move.

## Steps

1. **Bash command** (use `MSYS_NO_PATHCONV=1` prefix on Windows + Git Bash — see [memory/project_docker_no_source_mount.md]):

   ```bash
   MSYS_NO_PATHCONV=1 docker exec chess-coach-backend python -c "
   import os, asyncio, json
   from motor.motor_asyncio import AsyncIOMotorClient
   async def m():
       db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ.get('DB_NAME','chess_coach')]
       g = await db.games.find_one(
           {'game_id': '<GAME_ID>'},
           {'_id':0,'user_color':1,'result':1,'opening_name':1,'opponent_name':1,'is_analyzed':1,'date_played':1}
       )
       if g is None:
           print('NOT FOUND'); return
       print(f'meta: {json.dumps(g, default=str)}')
       a = await db.game_analyses.find_one(
           {'game_id': '<GAME_ID>'}, {'_id':0,'stockfish_analysis':1}
       )
       me = ((a or {}).get('stockfish_analysis') or {}).get('move_evaluations') or []
       if not me:
           print('no stockfish analysis yet'); return
       print(f'\\n-- top 10 user moves by cp_loss --')
       for x in sorted(me, key=lambda e: -(e.get('cp_loss') or 0))[:10]:
           print(f'  m{x[\"move_number\"]:>3} {x.get(\"move\"):>7} cp_loss={x.get(\"cp_loss\"):>6} best={x.get(\"best_move\"):>7} class={x.get(\"classification\")} gap={x.get(\"cognitive_gap\")}')
       # Optional: --move N detail
       target = <MOVE_N or 'None'>
       if target:
           print(f'\\n-- move {target} detail --')
           for x in me:
               if x.get('move_number') == target:
                   print(json.dumps({
                       k: x.get(k) for k in [
                           'move_number','move','best_move','cp_loss','classification',
                           'cognitive_gap','fen_before','fen_after','eval_before','eval_after'
                       ]
                   }, default=str, indent=2))
   asyncio.run(m())
   "
   ```

2. **Format the output** for the user. If it's a debug question, surface what's relevant:
   - For "did the coach get it right" questions → emphasize the cp_loss column
   - For "where did the game decide itself" → show the row with max cp_loss
   - For "what's the engine want at move N" → show `best_move` + diagnosis

3. **Cross-reference** when relevant:
   - If user mentions a coach review, this is a setup for `/audit-coach-review`
   - If user mentions a detector firing, this is a setup for `/detector-quality-scan`

## What NOT to do

- Don't paraphrase the engine's opinion. Quote the cp_loss number directly. The whole point is to ground in numbers, not vibes.
- Don't run this for unanalyzed games (`is_analyzed: False`) — say so and stop.
- Don't fall back to PGN-parsing for chess facts if `move_evaluations` is empty. If we don't have engine data, the answer is "we don't have engine data."
- Don't run on the server-side production DB unless the user explicitly says so. Local dev only by default.

## Output format

Keep tight. Two-section default:

```
Game 4346513e — Mohit black, vs Sumopork12, Scandinavian, 1-0 (you lost)
Top 10 user moves by cp_loss:
  m50  Kf3   -8640cp  best=e4    class=blunder       gap=piece_safety
  m56  Kh2   -8407cp  best=Kf2   class=blunder       gap=king_safety
  ...
```

If `--move N` was passed, add a third section with the detail dict.

## Notes

- On Windows + Git Bash the `/app/...` path inside docker gets mangled to `C:/Program Files/Git/app/...` without `MSYS_NO_PATHCONV=1`. Always prefix.
- See [memory/project_docker_no_source_mount.md] for the `docker cp` trick when iterating on changed backend code.
