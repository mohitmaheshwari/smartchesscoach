"""
Debug game move evaluations — shows exactly what data the frontend receives.

Usage:
  docker cp debug_game_evals.py chess-coach-backend:/app/backend/ && docker exec -it chess-coach-backend python3 debug_game_evals.py ed042610-caf8-4e71-b81b-9fa7239fcb07
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://admin_user_mii_s_c:Mii123$44$@localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

from pymongo import MongoClient
import chess
import chess.pgn
import io

game_id = sys.argv[1] if len(sys.argv) > 1 else "ed042610-caf8-4e71-b81b-9fa7239fcb07"

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# Find game
game = db.games.find_one({"game_id": {"$regex": game_id[:12]}}, {"_id": 0})
if not game:
    print(f"Game not found: {game_id}")
    sys.exit(1)

full_id = game["game_id"]
print(f"=== GAME: {full_id} ===")
print(f"User color: {game.get('user_color')}")
print(f"Result: {game.get('result')}")
print()

# Parse PGN to get all moves
pgn_text = game.get("pgn", "")
pgn_game = chess.pgn.read_game(io.StringIO(pgn_text))
pgn_moves = []
if pgn_game:
    board = chess.Board()
    for move in pgn_game.mainline_moves():
        san = board.san(move)
        pgn_moves.append({
            "index": len(pgn_moves),
            "san": san,
            "from": chess.square_name(move.from_square),
            "to": chess.square_name(move.to_square),
            "is_white": board.turn == chess.WHITE,
            "move_number": board.fullmove_number,
        })
        board.push(move)

user_color = game.get("user_color", "white")

print(f"=== PGN MOVES ({len(pgn_moves)} total) ===")
for m in pgn_moves[:20]:
    is_user = (user_color == "white" and m["is_white"]) or (user_color == "black" and not m["is_white"])
    marker = "USER" if is_user else "OPP "
    print(f"  idx={m['index']:2d}  mn={m['move_number']:2d}  {m['san']:8s}  {'W' if m['is_white'] else 'B'}  {marker}  {m['from']}->{m['to']}")
print()

# Get analysis
analysis = db.game_analyses.find_one({"game_id": full_id}, {"_id": 0, "stockfish_analysis.move_evaluations": 1})
if not analysis:
    print("No analysis found!")
    sys.exit(1)

evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
print(f"=== MOVE EVALUATIONS ({len(evals)} entries) ===")
for i, e in enumerate(evals[:20]):
    mn = e.get("move_number", "?")
    move = e.get("move", "?")
    cp_loss = e.get("cp_loss", 0) or 0
    classification = e.get("classification", "")
    evaluation = e.get("evaluation", "")
    best = e.get("best_move", "")
    eb = e.get("eval_before", "?")
    ea = e.get("eval_after", "?")
    print(f"  evals[{i:2d}]  mn={mn:2}  {move:8s}  cp_loss={cp_loss:4}  class={classification:15s}  eval={evaluation:15s}  best={best:8s}  eb={eb}  ea={ea}")
print()

# Now simulate what the frontend does
print(f"=== FRONTEND MATCHING SIMULATION ===")
print(f"(What the frontend shows for each PGN move index)")
print()
for m in pgn_moves[:15]:
    idx = m["index"]
    san = m["san"]
    move_num = m["move_number"]
    to_sq = m["to"]
    is_user = (user_color == "white" and m["is_white"]) or (user_color == "black" and not m["is_white"])

    # Method 1: find by move_number + san
    match1 = next((e for e in evals if e.get("move_number") == move_num and e.get("move") == san), None)

    # Method 2: find by san only
    match2 = next((e for e in evals if e.get("move") == san), None)

    # Method 3: old broken method — evals[currentMoveIndex]
    match3 = evals[idx] if idx < len(evals) else None

    chosen = match1 or match2
    old_chosen = match1 or match3  # What the old code did

    marker = "USER" if is_user else "OPP "

    print(f"  PGN idx={idx:2d}  {san:8s}  {marker}  to={to_sq}")
    if match1:
        print(f"    match(mn+san): mn={match1.get('move_number')}  class={match1.get('classification', '')}  eval={match1.get('evaluation', '')}  cp_loss={match1.get('cp_loss', 0)}")
    else:
        print(f"    match(mn+san): NO MATCH")

    if match2 and match2 != match1:
        print(f"    match(san):    mn={match2.get('move_number')}  class={match2.get('classification', '')}  eval={match2.get('evaluation', '')}  cp_loss={match2.get('cp_loss', 0)}")

    if match3 and match3 != match1:
        print(f"    OLD evals[{idx}]: mn={match3.get('move_number')}  move={match3.get('move')}  class={match3.get('classification', '')}  eval={match3.get('evaluation', '')}  cp_loss={match3.get('cp_loss', 0)}")

    # What icon would show?
    if chosen:
        c = (chosen.get("classification", "") or chosen.get("evaluation", "")).lower()
    elif not is_user:
        # For opponent moves, derive from cp_loss
        cp = abs((match2 or {}).get("cp_loss", 0)) if match2 else 0
        c = "blunder" if cp >= 200 else "mistake" if cp >= 100 else "good"
    else:
        c = ""

    if old_chosen and old_chosen != chosen:
        old_c = (old_chosen.get("classification", "") or old_chosen.get("evaluation", "")).lower()
        if old_c != c:
            print(f"    ⚠️  OLD CODE would show: {old_c}  |  NEW CODE shows: {c}")

    print()

client.close()
print("Done.")
