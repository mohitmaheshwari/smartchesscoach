---
name: detector-quality-scan
description: Audit a concept_detector for false positives and false negatives by sampling fires across many games and cross-checking against Stockfish evaluations. Trigger when a detector is newly shipped, after a detector is tightened or widened, or when a user reports a bad fire.
---

# Detector quality scan

Spot-check a `concept_detector` against engine ground truth. Surfaces:

- **False positives**: detector fires "missed" on a move the engine considers fine (low cp_loss)
- **False negatives**: detector returns "none" on a move where the engine sees a big mistake AND the position superficially fits the skill
- **Drift**: detector picks change in surprising ways after a code change

This is the audit that would have caught the original rule-of-the-square narrowness (zero fires across 50 games — detector too strict) AND the post-widening false positive (defender had a queen, but detector accepted because the queen was momentarily blocked).

## When to invoke

- Right after merging a new concept_detector (`first-time fire rates sane?`)
- Right after tightening or widening an existing detector (regression check)
- User reports a suspicious fire ("this position isn't a rule-of-the-square moment")
- User asks "is this detector good enough to wire to the drill?"

## Required input

- `skill_id` — must be in `backend/services/concept_detectors/registry.py:DETECTORS`

## Optional input

- `--n-games N` — sample size. Default 50. Smaller for fast iteration; 200+ for serious audits.

## Steps

1. **Sample N analyzed games** at random. Pull `pgn` + `user_color`. Walk each game's user moves, run the detector, collect fires:

   ```python
   docker exec chess-coach-backend python -c "
   import os, sys, asyncio, io, chess, chess.pgn
   sys.path.insert(0,'/app/backend')
   from motor.motor_asyncio import AsyncIOMotorClient
   from services.concept_detectors.registry import DETECTORS
   det = DETECTORS['<skill_id>']
   async def m():
       db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ.get('DB_NAME','chess_coach')]
       games = []
       async for g in db.games.aggregate([
           {'\$match': {'is_analyzed': True}},
           {'\$sample': {'size': <N>}},
           {'\$project': {'_id':0,'game_id':1,'pgn':1,'user_color':1}}
       ]):
           games.append(g)
       fires = {'applied': [], 'missed': []}
       for g in games:
           uc = chess.WHITE if (g.get('user_color') or 'white').lower() == 'white' else chess.BLACK
           try:
               game = chess.pgn.read_game(io.StringIO(g.get('pgn') or ''))
               if game is None: continue
               board = game.board()
               for ply, mv in enumerate(game.mainline_moves()):
                   if board.turn == uc:
                       try: v = det(board, mv, uc)
                       except: v = None
                       if v in ('applied','missed'):
                           mn = ply // 2 + 1
                           try: san = board.san(mv)
                           except: san = mv.uci()
                           fires[v].append({'game_id': g['game_id'], 'move_number': mn, 'san': san, 'fen': board.fen()})
                   board.push(mv)
           except: continue
       print(f'applied: {len(fires[\"applied\"])}, missed: {len(fires[\"missed\"])}')
       # show 5 of each
       for outcome in ('applied','missed'):
           print(f'\\n--- sample of 5 {outcome} ---')
           for f in fires[outcome][:5]:
               print(f'  {f[\"game_id\"][:18]} m{f[\"move_number\"]} {f[\"san\"]} | {f[\"fen\"]}')
   asyncio.run(m())
   "
   ```

2. **Cross-check each sample against engine truth.** For each of the 10 sampled fires (5 applied + 5 missed), pull `cp_loss` for that move from `game_analyses.stockfish_analysis.move_evaluations` (match on `move_number` + `move` SAN).

3. **Categorize each sample**:

   - **Applied + cp_loss ≤ 50**: detector says user did the right thing AND engine agrees → ✓ true positive
   - **Applied + cp_loss > 100**: detector says user did the right thing BUT engine says they made a mistake → ⚠️ possible false positive (detector accepting moves the engine punishes)
   - **Missed + cp_loss > 100**: detector says user did the wrong thing AND engine agrees → ✓ true negative
   - **Missed + cp_loss ≤ 50**: detector says wrong, engine says fine → ⚠️ probable false flag (the rule-of-the-square Kd7 case)

4. **Report findings tight**:

   ```
   Detector: endgame_rule_of_square
   Sample: 50 games, X applied + Y missed = Z fires per game
   Cross-checked 10 samples (5 each):
     applied:  5/5 cp_loss ≤ 50  ✓
     missed:   3/5 cp_loss > 100 ✓
               2/5 cp_loss < 50  ⚠️ false flag (game X m48, game Y m22)
   FP rate (sampled): 20%
   Suggest: review the 2 false-flag positions; tighten guard.
   ```

5. **If FP rate > 15% in either direction**, surface the suspicious FENs for manual review. Don't try to auto-fix the detector — that's a separate review pass.

## What NOT to do

- Don't run on 5000+ games unless the user asks. Sample first, deep-scan only when the FP signal warrants it.
- Don't compare against `cognitive_gap` classifications — those are themselves derived; cp_loss is the more grounded check.
- Don't auto-edit the detector code. This skill DIAGNOSES; tightening is a separate decision the user makes.
- Don't sample only "applied" fires. False *positives* on missed are how detectors silently demote users (the rule-of-the-square Kd7 false flag was exactly this).

## Cross-skill notes

- After a tightening, run this scan again and compare. Both runs in a row should ideally show drop in FP rate.
- For detectors that fire too rarely (< 0.1 fires per game over 50 games), the issue is breadth not precision. Different skill — widen, don't audit.
- See [memory/feedback_fix_framing_not_detection.md] for the rule about NEVER deleting detection to fix bad captions. Same here: if the audit shows a framing problem (caption is wrong about what the rule means), fix the caption, not the detector.
