#!/usr/bin/env python3
"""Find endgame mistakes across every analysed game, and say what kind they are.

The question this exists to answer is whether endgame errors are really
positional, and the stored labels cannot answer it: `pawn_structure` and
`piece_activity` have never once been assigned, and `endgame_technique`
just means "a mistake in an endgame", so counting it as positional answers
its own question.

So the classification is taken from the board instead:

  tactical   after the move, the opponent has a capture that wins material
             by static exchange. Something hung.
  positional the evaluation collapses and yet nothing can be taken. The
             move was wrong for a reason you cannot see by counting.

That distinction is deterministic, needs no engine at scan time, and is the
one that decides whether "what your move prevents" style coaching would
have helped.

Usage:
    python backend/scripts/find_endgame_mistakes.py
    ENDGAME_MEN=12 MISTAKE_CP=100 python backend/scripts/find_endgame_mistakes.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess
from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
ENDGAME_MEN = int(os.environ.get("ENDGAME_MEN", "12"))
MISTAKE_CP = int(os.environ.get("MISTAKE_CP", "100"))
BLUNDER_CP = int(os.environ.get("BLUNDER_CP", "300"))
# A capture worth roughly a pawn or more is material actually being won,
# rather than an even trade the engine happens to prefer.
MATERIAL_CP = 100
OUT = os.environ.get("OUT", "/tmp/endgame_mistakes.json")


def played_move(board: chess.Board, evaluation: dict):
    """The move the user actually played, however this row stored it."""
    for key in ("move_uci", "played_move_uci", "user_move_uci"):
        raw = evaluation.get(key)
        if raw:
            try:
                move = chess.Move.from_uci(str(raw))
                if move in board.legal_moves:
                    return move
            except ValueError:
                pass
    for key in ("move", "move_san", "played_move", "user_move_san"):
        raw = evaluation.get(key)
        if raw:
            try:
                return board.parse_san(str(raw))
            except ValueError:
                pass
    return None


def wins_material(board: chess.Board) -> bool:
    """Can the side to move take something and come out ahead?

    Uses the project's own static exchange evaluation. python-chess 1.11.2
    has no see_ge, and an earlier version of this script called it inside a
    bare except, so every position silently came back "nothing hangs" and
    the scan reported endgame mistakes as 100% positional. A classifier
    that cannot fail is not a classifier.
    """
    from coach_play.coach_blunder_guard import see_gain

    for move in board.legal_moves:
        if not board.is_capture(move):
            continue
        if see_gain(board, move) >= MATERIAL_CP:
            return True
    return False


def main() -> int:
    db = MongoClient(MONGO_URL)[DB_NAME]

    kinds = Counter()
    severity = Counter()
    by_men = Counter()
    tablebase = Counter()
    unreadable = Counter()
    examples = defaultdict(list)
    scanned = games = 0

    cursor = db.game_analyses.find(
        {}, {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1}
    )
    for doc in cursor:
        games += 1
        for evaluation in (doc.get("stockfish_analysis") or {}).get("move_evaluations") or []:
            if evaluation.get("is_opponent_move"):
                continue
            cp = evaluation.get("cp_loss")
            fen = evaluation.get("fen_before")
            if not isinstance(cp, (int, float)) or cp < MISTAKE_CP or not fen:
                continue
            try:
                board = chess.Board(fen)
            except Exception:
                unreadable["bad fen"] += 1
                continue
            men = len(board.piece_map())
            if men > ENDGAME_MEN:
                continue
            scanned += 1
            by_men[men] += 1
            tablebase["<=7 men" if men <= 7 else ">7 men"] += 1
            severity["blunder" if cp >= BLUNDER_CP else "mistake"] += 1

            move = played_move(board, evaluation)
            if move is None:
                unreadable["move not recoverable"] += 1
                kinds["unknown"] += 1
                continue
            after = board.copy()
            after.push(move)
            kind = "tactical" if wins_material(after) else "positional"
            kinds[kind] += 1
            if len(examples[kind]) < 12:
                examples[kind].append({
                    "game_id": doc.get("game_id"),
                    "fen": fen,
                    "played": board.san(move),
                    "best": evaluation.get("best_move_san") or evaluation.get("best_move"),
                    "cp_loss": cp,
                    "men": men,
                    "move_number": evaluation.get("move_number"),
                })

    total = sum(kinds.values()) or 1
    print(f"  games with analysis          : {games}")
    print(f"  endgame mistakes (<= {ENDGAME_MEN} men, >= {MISTAKE_CP}cp): {scanned}")
    print()
    print("  what kind, judged from the board:")
    for kind in ("tactical", "positional", "unknown"):
        n = kinds[kind]
        print(f"     {kind:12} {n:6}  {100*n//total:3}%")
    print()
    print("  severity:")
    for k, v in severity.most_common():
        print(f"     {k:12} {v}")
    print()
    print("  tablebase reach:")
    for k, v in tablebase.most_common():
        print(f"     {k:12} {v}")
    if unreadable:
        print()
        print("  rows that could not be judged:")
        for k, v in unreadable.most_common():
            print(f"     {k:22} {v}")

    print()
    print("  positional examples (nothing hangs, yet the position collapses):")
    for ex in examples["positional"][:6]:
        print(f"     move {ex['move_number']} {ex['played']} (best {ex['best']}) "
              f"-{ex['cp_loss']}cp  {ex['men']} men")
        print(f"        {ex['fen']}")

    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump({"kinds": dict(kinds), "examples": {k: v for k, v in examples.items()}}, handle)
    print(f"\n  written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
