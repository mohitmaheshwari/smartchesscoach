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


if __name__ == "__main__":
    sys.exit(main())
