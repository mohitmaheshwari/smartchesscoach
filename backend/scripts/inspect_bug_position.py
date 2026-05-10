"""
Quick diagnostic: dump everything we know about a single bug —
FEN, board ASCII, what each piece attacks, what attacks each piece.

Usage:
    python scripts/inspect_bug_position.py --bug-file /tmp/parth_full_with_fen.json --feedback-id fb_1dbdb06502eb
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import chess


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bug-file", required=True)
    p.add_argument("--feedback-id", required=True)
    args = p.parse_args()

    data = json.loads(Path(args.bug_file).read_text(encoding="utf-8"))
    bugs = data.get("feedback") or []
    bug = next((b for b in bugs if b.get("feedback_id") == args.feedback_id), None)
    if not bug:
        print(f"feedback_id {args.feedback_id} not found")
        return 1

    pos = bug.get("position") or {}
    fen = pos.get("fen") or ""
    move_san = pos.get("move_san") or ""
    move_number = pos.get("move_number") or 0

    print(f"feedback_id: {args.feedback_id}")
    print(f"page       : {bug.get('page')}")
    print(f"severity   : {bug.get('severity')}")
    print(f"move       : {move_number}.{move_san}")
    print(f"fen        : {fen}")
    print(f"flagged    : {bug.get('coaching_text_flagged', '')[:200]}")
    print(f"issue      : {bug.get('issue', '')[:300]}")
    print()

    if not fen:
        print("(no FEN — can't render board)")
        return 0

    board = chess.Board(fen)
    print("Board (this is the position WHERE the move was about to be played):")
    print(board)
    print(f"\nside to move: {'WHITE' if board.turn == chess.WHITE else 'BLACK'}")
    print()

    # Try to play the flagged move and see what happens
    try:
        move = board.parse_san(move_san)
    except Exception as e:
        print(f"Couldn't parse move {move_san}: {e}")
        return 0

    board_after = board.copy()
    board_after.push(move)

    print(f"After {move_san}, position is:")
    print(board_after)
    print()

    # Whose move was it
    moving_color = chess.WHITE if board.turn == chess.WHITE else chess.BLACK
    moving_color_name = "WHITE" if moving_color == chess.WHITE else "BLACK"
    opp_color_name = "BLACK" if moving_color == chess.WHITE else "WHITE"

    # What piece moved
    moved_piece = board_after.piece_at(move.to_square)
    if moved_piece:
        sq_name = chess.square_name(move.to_square)
        piece_name = chess.piece_name(moved_piece.piece_type)
        print(f"{moving_color_name} {piece_name} on {sq_name} now attacks:")
        for sq in board_after.attacks(move.to_square):
            target = board_after.piece_at(sq)
            sq_n = chess.square_name(sq)
            if target:
                color = "WHITE" if target.color == chess.WHITE else "BLACK"
                print(f"  {sq_n}: {color} {chess.piece_name(target.piece_type)}")
            else:
                print(f"  {sq_n}: empty")
    print()

    # Who attacks the moved piece
    attackers = list(board_after.attackers(not moving_color, move.to_square))
    if attackers:
        print(f"{opp_color_name} pieces attacking the {piece_name} on {sq_name}:")
        for sq in attackers:
            piece = board_after.piece_at(sq)
            print(f"  {chess.square_name(sq)}: {chess.piece_name(piece.piece_type)}")
    else:
        print(f"No {opp_color_name} pieces attack the {piece_name} on {sq_name}.")

    # Now run V5 decryption against the actual game and print the move's
    # produced narrative + plan.current_problem so we can see what V5 emits.
    print()
    print("=" * 70)
    print("Running V5 decryption pipeline to see what it outputs for this move…")
    print("=" * 70)

    import asyncio
    import os
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.game_decryption_v5_service import generate_game_decryption_v5

    async def run_v5():
        ctx = bug.get("context") or {}
        game_id = ctx.get("game_id")
        if not game_id:
            print(f"  No game_id in bug context — can't run V5.")
            return
        client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = client[os.environ.get("DB_NAME", "chess_coach")]
        game = await db.games.find_one({"game_id": game_id}, {"_id": 0})
        analysis = await db.game_analyses.find_one({"game_id": game_id}, {"_id": 0})
        if not game or not analysis:
            print(f"  Missing game or analysis for game_id={game_id}")
            client.close()
            return
        pgn = game.get("pgn") or ""
        user_color = (game.get("user_color") or "white").lower()
        sf = analysis.get("stockfish_analysis") or {}
        move_evaluations = sf.get("move_evaluations") or []
        decryption = await generate_game_decryption_v5(
            pgn=pgn, user_color=user_color, move_evaluations=move_evaluations,
            user_id=game.get("user_id") or "unknown", db=db,
        )
        client.close()
        print(f"  game_id={game_id}  user_color={user_color}  total moves={len(decryption)}")
        # Find the move record matching (move_number, move_san)
        hits = [m for m in decryption
                if m.get("move_number") == move_number
                and (m.get("move_san") or "").rstrip("!?+#") == move_san.rstrip("!?+#")]
        if not hits:
            print(f"  No match for move {move_number} {move_san} in regenerated output.")
            return
        rec = hits[0]
        print()
        print(f"  is_user_move    : {rec.get('is_user_move')}")
        print(f"  severity        : {rec.get('severity')}")
        print(f"  cp_loss         : {rec.get('cp_loss')}")
        print(f"  concept_id      : {rec.get('concept_id')}")
        print(f"  concept_type    : {rec.get('concept_type')}")
        print()
        print(f"  narrative       : {rec.get('narrative')!r}")
        plan = rec.get("plan") or {}
        print(f"  plan.current_problem : {plan.get('current_problem')!r}")
        print(f"  plan.consequence     : {plan.get('consequence')!r}")
        print(f"  plan.better_approach : {plan.get('better_approach')!r}")

    asyncio.run(run_v5())


if __name__ == "__main__":
    sys.exit(main())
