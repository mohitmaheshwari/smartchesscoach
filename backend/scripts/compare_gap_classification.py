#!/usr/bin/env python3
"""Where does our stored cognitive_gap disagree with the signed-off precedence?

The engine-hard half of §1 in docs/move_classification_from_gold_scope.md needs
no human judgement — every rule in it is a board or engine fact. So the
disagreement rate can be measured today, across every user with real games,
without waiting for anyone to adjudicate anything.

This deliberately classifies ONLY what the engine-hard tier can decide. A move
it cannot decide is reported as `undecided` rather than guessed at; the
positional tier is where the three-way comparison (this, Codex, the product)
earns its keep, and putting a guess here would poison that gold.

    python scripts/compare_gap_classification.py              # all users
    python scripts/compare_gap_classification.py --users 10
    python scripts/compare_gap_classification.py --json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chess  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

MATE_CP = 3000
EXPERT_FROM = 1600          # where the top two swap; see §1 amendment 1
OVERSIGHT_FLOOR_CP = 300    # a real oversight is a real loss
UNDECIDED = "undecided"



_PIECE_VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}
_SLIDERS = (chess.BISHOP, chess.ROOK, chess.QUEEN)


def _valuable_targets(board: chess.Board, square: int, mover: bool):
    out = []
    for target in board.attacks(square):
        piece = board.piece_at(target)
        if piece and piece.color != mover and _PIECE_VALUE[piece.piece_type] >= 3:
            out.append(target)
    return out


def _is_fork(before: chess.Board, move: chess.Move) -> bool:
    after = before.copy()
    after.push(move)
    hits = _valuable_targets(after, move.to_square, before.turn)
    if len(hits) < 2:
        return False
    was = set(_valuable_targets(before, move.from_square, before.turn))
    return bool(set(hits) - was)


def _is_discovered(before: chess.Board, move: chess.Move) -> bool:
    after = before.copy()
    after.push(move)
    mover = before.turn
    for square in chess.SQUARES:
        piece = after.piece_at(square)
        if (not piece or piece.color != mover
                or piece.piece_type not in _SLIDERS or square == move.to_square):
            continue
        gained = set(_valuable_targets(after, square, mover)) - set(
            _valuable_targets(before, square, mover))
        for target in gained:
            try:
                if move.from_square in chess.SquareSet.ray(square, target):
                    return True
            except Exception:
                continue
    return False


def _user_pov(value: Optional[float], user_color: str) -> Optional[float]:
    if value is None:
        return None
    return value if user_color == "white" else -value


def _phase(board: chess.Board) -> str:
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(
        board.pieces(chess.QUEEN, chess.BLACK))
    minors = sum(
        len(board.pieces(pt, colour))
        for pt in (chess.ROOK, chess.BISHOP, chess.KNIGHT)
        for colour in (chess.WHITE, chess.BLACK)
    )
    if queens == 0 and minors <= 6:
        return "endgame"
    return "middlegame"


def classify_engine_hard(
    move: Dict[str, Any], user_color: str, rating: Optional[int],
    deviation_move: Optional[int] = None,
) -> str:
    """§1 of the scope, engine-hard tier only. Returns UNDECIDED otherwise."""
    fen = move.get("fen_before")
    uci = move.get("move_uci") or move.get("move_uci_played")
    if not fen:
        return UNDECIDED
    try:
        board = chess.Board(fen)
    except Exception:
        return UNDECIDED

    before = _user_pov(move.get("eval_before"), user_color)
    after = _user_pov(move.get("eval_after"), user_color)

    # ---- mate gate, before the tier (amendment 2)
    if after is not None and after <= -MATE_CP:
        return "king_safety"          # they allowed mate
    if before is not None and before >= MATE_CP and (after is None or after < MATE_CP):
        return "missed_tactic"        # they had mate and lost it

    cp_loss = abs(move.get("cp_loss") or 0)

    # ---- does the played move leave something takeable?
    hangs = False
    if uci:
        try:
            from services.destination_safety_detector import (
                grade_destination_safety_candidate,
            )
            hangs = str(grade_destination_safety_candidate(
                fen, uci).get("status")) == "fail"
        except Exception:
            hangs = False

    # ---- did the engine's best move win something concrete they missed?
    #
    # Deliberately narrow. An earlier draft accepted "the best move is a
    # capture", which calls every recapture a missed tactic and inflated this
    # category enormously. A tactic means a NAMED mechanism: a fork, or a
    # discovered attack. Both checks were measured 2026-09-18 against 250
    # labelled fires each -- 99.2% and 100.0% true, firing on only 11.2% and
    # 4.0% of unrelated positions. Pin and skewer are excluded on purpose:
    # the same measurement put them at 10.4% and 6.0%.
    missed = False
    best = move.get("best_move")
    if best and cp_loss >= OVERSIGHT_FLOOR_CP:
        try:
            best_mv = board.parse_san(str(best))
            missed = _is_fork(board, best_mv) or _is_discovered(board, best_mv)
        except Exception:
            missed = False

    phase = _phase(board)
    move_number = move.get("move_number") or 0

    # ---- phase gates
    #
    # "endgame_technique requires endgame phase" is a REQUIREMENT for that
    # category, not a rule that the endgame overrides everything above it. An
    # earlier draft returned endgame_technique for any endgame mistake that was
    # not a hang, which swallowed 52.8% of stored missed_tactic -- a missed
    # fork in a rook ending is still a missed fork.
    if phase == "endgame":
        if hangs:
            return "piece_safety"
        if missed:
            return "missed_tactic"
        return "endgame_technique"

    order = (["missed_tactic", "piece_safety"]
             if (rating or 0) >= EXPERT_FROM
             else ["piece_safety", "missed_tactic"])
    for category in order:
        if category == "piece_safety" and hangs:
            return "piece_safety"
        if category == "missed_tactic" and missed:
            return "missed_tactic"

    # Book-checkable, as §1 requires -- not "it happened early". The stored
    # opening_deviation is present on 98.9% of analyses; move_number <= 8
    # was calling every early mistake an opening problem.
    if deviation_move is not None and move_number == deviation_move and cp_loss >= 100:
        return "opening_knowledge"
    # NOT a fallback. The agreed specification is "the opponent had a reply the
    # player did not see", which needs evidence of that reply. move_evaluations
    # stores user moves only, so nothing here can establish it -- an earlier
    # draft returned tactical_oversight for any unexplained middlegame loss and
    # it promptly swallowed 27-72% of every other category, which is the same
    # catch-all disease this whole exercise exists to remove.
    return UNDECIDED


async def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=0, help="0 = all")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]
    from services.rating_resolver import get_coaching_rating

    user_ids = await db.games.distinct("user_id", {"is_analyzed": True})
    if args.users:
        user_ids = user_ids[: args.users]

    agree = 0
    matrix: Dict[str, Counter] = defaultdict(Counter)
    undecided = 0
    no_stored = 0

    for user_id in user_ids:
        rating = await get_coaching_rating(db, user_id)
        async for analysis in db.game_analyses.find(
            {"user_id": user_id},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1, "game_id": 1,
             "opening_deviation": 1},
        ):
            game = await db.games.find_one(
                {"game_id": analysis.get("game_id")},
                {"_id": 0, "user_color": 1})
            colour = (game or {}).get("user_color") or "white"
            evals = (analysis.get("stockfish_analysis") or {}).get(
                "move_evaluations") or []
            deviation = ((analysis.get("opening_deviation") or {}).get(
                "deviation") or {}).get("user_move_number")
            for move in evals:
                if move.get("is_opponent_move"):
                    continue
                stored = move.get("cognitive_gap")
                if not stored:
                    continue
                if abs(move.get("cp_loss") or 0) < 100:
                    continue          # not a mistake; nothing to categorise
                mine = classify_engine_hard(move, colour, rating, deviation)
                if mine == UNDECIDED:
                    undecided += 1
                    continue
                matrix[stored][mine] += 1
                if stored == mine:
                    agree += 1

    decided = sum(sum(c.values()) for c in matrix.values())
    if args.json:
        print(json.dumps({
            "users": len(user_ids), "decided": decided, "agree": agree,
            "undecided": undecided,
            "matrix": {k: dict(v) for k, v in matrix.items()},
        }, indent=2))
        return 0

    print(f"users: {len(user_ids)}   mistakes the engine-hard tier decided: "
          f"{decided}   left to judgement: {undecided}")
    if not decided:
        return 0
    print(f"agreement with the stored cognitive_gap: {agree} "
          f"({100 * agree / decided:.1f}%)\n")
    print("where they disagree — stored label -> what the precedence says:\n")
    for stored in sorted(matrix, key=lambda k: -sum(matrix[k].values())):
        row = matrix[stored]
        total = sum(row.values())
        same = row.get(stored, 0)
        print(f"  {stored:22} {total:6} mistakes, "
              f"{100 * same / total:5.1f}% agree")
        for mine, n in row.most_common(4):
            if mine == stored:
                continue
            print(f"      -> {mine:22} {n:6}  ({100 * n / total:4.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
