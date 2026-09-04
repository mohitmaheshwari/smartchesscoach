"""Read-only aggregate audit of the existing Stage 4 gold caption corpus.

No caption text, FEN, game id, move, user id, or reviewer note is exported.
Clean situations use legal board mutation and the canonical exchange-truth
helper.  Positions that cannot be classified from stored facts are deferred.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

import chess
from pymongo import MongoClient

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
DEPLOYED_BACKEND = Path("/app/backend")
if DEPLOYED_BACKEND.exists() and str(DEPLOYED_BACKEND) not in sys.path:
    sys.path.append(str(DEPLOYED_BACKEND))

from services.caption_facts import legal_exchange_gain


def _rank(row: dict) -> tuple:
    status = row.get("verify_status")
    return (
        2 if status == "verified_after_correction" else 1 if status == "verified" else 0,
        1 if str(row.get("created_by") or "").endswith("_deep") else 0,
    )


def _best_capture_gain(board: chess.Board) -> int:
    best = 0
    for move in list(board.legal_moves):
        if not board.is_capture(move):
            continue
        try:
            best = max(
                best,
                legal_exchange_gain(
                    board, move.to_square, board.turn, first_move=move
                ),
            )
        except Exception:
            continue
    return best


def _has_mate_in_one(board: chess.Board) -> bool:
    for move in list(board.legal_moves):
        after = board.copy(stack=False)
        after.push(move)
        if after.is_checkmate():
            return True
    return False


def classify(row: dict) -> str:
    try:
        board = chess.Board(row.get("fen_before") or "")
        played = board.parse_san(row.get("move_san") or "")
    except Exception:
        return "invalid_or_missing_position"

    after_played = board.copy(stack=False)
    after_played.push(played)
    if after_played.is_checkmate():
        return "delivered_mate"
    if _has_mate_in_one(after_played):
        return "allowed_mate_in_one"
    if _best_capture_gain(after_played) >= 100:
        return "allowed_profitable_capture"

    best_san = row.get("best_move_san") or ""
    try:
        best = board.parse_san(best_san) if best_san else None
    except Exception:
        best = None
    if best:
        after_best = board.copy(stack=False)
        after_best.push(best)
        if after_best.is_checkmate():
            return "missed_mate_in_one"
        if board.is_capture(best):
            try:
                if legal_exchange_gain(
                    board, best.to_square, board.turn, first_move=best
                ) >= 100:
                    return "missed_profitable_capture"
            except Exception:
                pass

    if (
        (row.get("move_number") or 99) <= 6
        and (row.get("move_san") or "").startswith("Q")
        and "x" not in (row.get("move_san") or "")
    ):
        return "early_queen_move"

    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(
        board.pieces(chess.QUEEN, chess.BLACK)
    )
    non_pawn_material = sum(
        len(board.pieces(piece_type, color))
        for piece_type in (chess.ROOK, chess.BISHOP, chess.KNIGHT)
        for color in (chess.WHITE, chess.BLACK)
    )
    if queens == 0 and non_pawn_material <= 6:
        return "endgame_position"
    return "deferred_requires_deeper_reason"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    args = parser.parse_args()

    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    rows = list(db.gold_captions.find({}, {"_id": 0}))
    verified = [
        row for row in rows
        if row.get("verify_status") in {"verified", "verified_after_correction"}
    ]

    selected = {}
    for row in verified:
        key = (row.get("game_id"), row.get("move_number"), row.get("move_san"))
        if key not in selected or _rank(row) > _rank(selected[key]):
            selected[key] = row

    situations = Counter(classify(row) for row in selected.values())
    gaps = Counter(str(row.get("cognitive_gap") or "unknown") for row in selected.values())
    status = Counter(str(row.get("verify_status") or "missing") for row in rows)

    result = {
        "schema_version": 1,
        "mode": "read_only_aggregate",
        "gold_rows": len(rows),
        "verified_rows": len(verified),
        "verified_unique_positions": len(selected),
        "duplicate_verified_rows_removed": len(verified) - len(selected),
        "verify_status": dict(sorted(status.items())),
        "legacy_gap_distribution_unique": dict(sorted(gaps.items())),
        "clean_situation_distribution_unique": dict(sorted(situations.items())),
        "clean_situation_covered": sum(
            value for key, value in situations.items()
            if key not in {"deferred_requires_deeper_reason", "invalid_or_missing_position"}
        ),
        "exports_private_rows": False,
        "database_writes": 0,
        "engine_runs": 0,
    }
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
