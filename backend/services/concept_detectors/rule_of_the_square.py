"""Canonical rule-of-the-square truth and mastery adapter.

This module is the only runtime source for the chess fact. Caption, legacy
endgame and puzzle consumers derive their views from it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any, Dict, Optional, Set

import chess


@dataclass(frozen=True)
class RuleOfSquareFact:
    pawn_square: int
    pawn_color: chess.Color
    defender_color: chess.Color
    defending_king_square: int
    promotion_square: int
    pawn_pushes_to_promote: int
    catchable: bool

    def evidence(self) -> Dict[str, Any]:
        raw = asdict(self)
        raw.update({
            "pawn_square": chess.square_name(self.pawn_square),
            "pawn_color": "white" if self.pawn_color else "black",
            "defender_color": "white" if self.defender_color else "black",
            "defending_king_square": chess.square_name(
                self.defending_king_square
            ),
            "promotion_square": chess.square_name(self.promotion_square),
        })
        return raw


def promotion_square(pawn_square: int, pawn_color: chess.Color) -> int:
    return chess.square(
        chess.square_file(pawn_square),
        7 if pawn_color == chess.WHITE else 0,
    )


def pawn_pushes_to_promote(
    board: chess.Board,
    pawn_square: int,
    pawn_color: chess.Color,
) -> int:
    """Minimum unobstructed legal pushes, including a starting double push."""
    rank = chess.square_rank(pawn_square)
    distance = (7 - rank) if pawn_color == chess.WHITE else rank
    start_rank = 1 if pawn_color == chess.WHITE else 6
    if rank != start_rank:
        return distance
    direction = 8 if pawn_color == chess.WHITE else -8
    one = pawn_square + direction
    two = pawn_square + 2 * direction
    if (
        0 <= one < 64
        and 0 <= two < 64
        and board.piece_at(one) is None
        and board.piece_at(two) is None
    ):
        return distance - 1
    return distance


def square_of_the_pawn(
    pawn_square: chess.Square,
    pawn_color: chess.Color,
) -> Set[chess.Square]:
    """Textbook geometric square, retained as evidence rather than truth."""
    pawn_file = chess.square_file(pawn_square)
    pawn_rank = chess.square_rank(pawn_square)
    promotion_rank = 7 if pawn_color == chess.WHITE else 0
    distance = abs(promotion_rank - pawn_rank)
    return {
        chess.square(file_, rank)
        for file_ in range(
            max(0, pawn_file - distance),
            min(7, pawn_file + distance) + 1,
        )
        for rank in range(
            min(pawn_rank, promotion_rank),
            max(pawn_rank, promotion_rank) + 1,
        )
    }


def is_kp_vs_k(board: chess.Board) -> bool:
    pieces = list(board.piece_map().values())
    return (
        len(pieces) == 3
        and sum(p.piece_type == chess.KING for p in pieces) == 2
        and sum(p.piece_type == chess.PAWN for p in pieces) == 1
    )


def _critical_pawn(board: chess.Board) -> Optional[tuple[int, chess.Color]]:
    if not is_kp_vs_k(board):
        return None
    pawns = [
        (square, piece.color)
        for square, piece in board.piece_map().items()
        if piece.piece_type == chess.PAWN
    ]
    return pawns[0] if len(pawns) == 1 else None


def _defender_can_capture_promoted_piece(
    board_after_promotion: chess.Board,
    promotion_target: int,
    defender_color: chess.Color,
) -> bool:
    if board_after_promotion.turn != defender_color:
        return False
    king_square = board_after_promotion.king(defender_color)
    if king_square is None:
        return False
    return any(
        move.from_square == king_square
        and move.to_square == promotion_target
        and board_after_promotion.is_capture(move)
        for move in board_after_promotion.legal_moves
    )


def _race_is_catchable(
    board: chess.Board,
    pawn_square: int,
    pawn_color: chess.Color,
) -> bool:
    """Exact finite race: pawn pushes versus legal defending-king moves."""

    @lru_cache(maxsize=None)
    def solve(fen: str, tracked_pawn_square: int) -> bool:
        work = chess.Board(fen)
        pawn = work.piece_at(tracked_pawn_square)
        if (
            pawn is None
            or pawn.piece_type != chess.PAWN
            or pawn.color != pawn_color
        ):
            return True

        defender_color = not pawn_color
        if work.turn == pawn_color:
            pushes = [
                move
                for move in work.legal_moves
                if move.from_square == tracked_pawn_square
            ]
            if not pushes:
                return True

            results = []
            for move in pushes:
                after = work.copy(stack=False)
                after.push(move)
                if move.promotion:
                    results.append(
                        _defender_can_capture_promoted_piece(
                            after, move.to_square, defender_color
                        )
                    )
                else:
                    results.append(solve(after.fen(), move.to_square))
            # The pawn side chooses its best racing push.
            return all(results)

        king_square = work.king(defender_color)
        if king_square is None:
            return False
        king_moves = [
            move
            for move in work.legal_moves
            if move.from_square == king_square
        ]
        if not king_moves:
            return False

        for move in king_moves:
            if (
                move.to_square == tracked_pawn_square
                and work.is_capture(move)
            ):
                return True
            after = work.copy(stack=False)
            after.push(move)
            if solve(after.fen(), tracked_pawn_square):
                return True
        return False

    return solve(board.fen(), pawn_square)


def analyze_rule_of_square(
    board: chess.Board,
) -> Optional[RuleOfSquareFact]:
    """Return canonical K+P-vs-K race truth, or None outside V1 scope."""
    if not board.is_valid():
        return None
    critical = _critical_pawn(board)
    if critical is None:
        return None
    pawn_square, pawn_color = critical
    defender_color = not pawn_color
    defending_king = board.king(defender_color)
    if defending_king is None:
        return None
    return RuleOfSquareFact(
        pawn_square=pawn_square,
        pawn_color=pawn_color,
        defender_color=defender_color,
        defending_king_square=defending_king,
        promotion_square=promotion_square(pawn_square, pawn_color),
        pawn_pushes_to_promote=pawn_pushes_to_promote(
            board, pawn_square, pawn_color
        ),
        catchable=_race_is_catchable(board, pawn_square, pawn_color),
    )


def is_pure_king_pawn_race(
    board: chess.Board,
    pawn_sq: int,
    pawn_color: chess.Color,
) -> bool:
    fact = analyze_rule_of_square(board)
    return bool(
        fact
        and fact.pawn_square == pawn_sq
        and fact.pawn_color == pawn_color
    )


def detect_rule_of_the_square_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    """Grade one clean demonstration while unsafe output remains quarantined."""
    if board_before.turn != user_color or move not in board_before.legal_moves:
        return None
    fact_before = analyze_rule_of_square(board_before)
    if fact_before is None:
        return None
    moved_piece = board_before.piece_at(move.from_square)
    if moved_piece is None or moved_piece.color != user_color:
        return None

    if user_color == fact_before.pawn_color:
        if (
            moved_piece.piece_type == chess.PAWN
            and move.from_square == fact_before.pawn_square
        ):
            return "missed" if fact_before.catchable else "applied"
        return None

    if moved_piece.piece_type != chess.KING:
        return None
    if not fact_before.catchable:
        return None
    if move.to_square == fact_before.pawn_square and board_before.is_capture(move):
        return "applied"

    board_after = board_before.copy(stack=False)
    board_after.push(move)
    fact_after = analyze_rule_of_square(board_after)
    if fact_after is None:
        return "applied"
    return "applied" if fact_after.catchable else "missed"


def is_rule_of_square_relevant(fen: str, engine=None) -> bool:
    """Puzzle eligibility adapter; engine is retained for call compatibility."""
    try:
        return analyze_rule_of_square(chess.Board(fen)) is not None
    except (TypeError, ValueError):
        return False
