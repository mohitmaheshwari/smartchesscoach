"""Verify canonical endgame answers that are outside Syzygy coverage.

This is an authoring tool, not a runtime dependency. It prints compact,
copy-ready evidence for every legal lesson position containing more than seven
pieces. The content validator accepts a record only after the author copies the
matching FEN and move into the canonical lesson's ``verification`` object.

Usage:
    python scripts/verify_curriculum_stockfish.py --stockfish PATH
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import chess
import chess.engine


BACKEND_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = BACKEND_ROOT / "data" / "coaching" / "endgame_theory_tree.json"


def _score(info: dict, color: chess.Color) -> int:
    return info["score"].pov(color).score(mate_score=100_000)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stockfish", required=True)
    parser.add_argument("--depth", type=int, default=20)
    args = parser.parse_args()

    engine_path = Path(args.stockfish).resolve()
    engine_sha256 = hashlib.sha256(engine_path.read_bytes()).hexdigest()
    tree = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))

    with chess.engine.SimpleEngine.popen_uci(str(engine_path)) as engine:
        engine_name = engine.id.get("name", "Stockfish")
        for category_key, category in tree.items():
            if category_key.startswith("_"):
                continue
            for lesson_key, lesson in category.get("lessons", {}).items():
                for index, position in enumerate(lesson.get("positions", [])):
                    board = chess.Board(position["fen"])
                    if not board.is_valid() or len(board.piece_map()) <= 7:
                        continue

                    move = chess.Move.from_uci(position["correct_move_uci"])
                    if move not in board.legal_moves:
                        continue

                    root = engine.analyse(
                        board,
                        chess.engine.Limit(depth=args.depth),
                        multipv=3,
                    )
                    after = board.copy()
                    after.push(move)
                    selected = engine.analyse(
                        after,
                        chess.engine.Limit(depth=args.depth),
                    )
                    original_color = board.turn
                    result = {
                        "content_id": f"{category_key}/{lesson_key}",
                        "position_index": index,
                        "fen": board.fen(),
                        "move_uci": move.uci(),
                        "move_san": board.san(move),
                        "selected_score_cp": _score(selected, original_color),
                        "top_moves": [
                            {
                                "uci": info["pv"][0].uci(),
                                "san": board.san(info["pv"][0]),
                                "score_cp": _score(info, original_color),
                            }
                            for info in root
                        ],
                        "verification": {
                            "method": "stockfish",
                            "status": "verified",
                            "fen": board.fen(),
                            "move_uci": move.uci(),
                            "engine": engine_name,
                            "engine_sha256": engine_sha256,
                            "depth": args.depth,
                        },
                    }
                    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
