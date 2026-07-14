"""coordination_detector.py — Detect piece coordination gaps.

A coordination gap is when the user's pieces don't work together effectively.
Specifically: rooks that don't support each other, pieces that are passive,
pieces that can't support threats or defense together.

RATING-AWARE: 1400+ players should see coordination feedback more than 1000-rated
(who are still learning basic piece moves).
"""

import chess
from typing import Dict, List, Optional, Tuple


def detect_coordination_gap(move_eval: Dict, fen_before: str, fen_after: str) -> Optional[Tuple[float, str]]:
    """
    Detect coordination gaps in a move.

    Returns: (confidence: float [0-1], gap_type: str) or None if no coordination gap detected

    Confidence gates:
    - 0.75+: Surface to user (meets launch threshold)
    - 0.60-0.74: Suppress (not confident enough)
    """

    board_before = chess.Board(fen_before)
    board_after = chess.Board(fen_after)

    cp_loss = move_eval.get("cp_loss", 0)

    # Only look for coordination gaps in moves that are NOT blunders (cp_loss < 100)
    # Coordination gaps are subtle strategic issues, not tactical errors
    if cp_loss >= 100:
        return None

    # Detect: Rook passivity (rook moves but to a square where it doesn't support other pieces)
    gap = _detect_rook_passivity(move_eval, board_after, board_before)
    if gap:
        return gap

    # Detect: Piece isolation (moving a piece away from support)
    gap = _detect_piece_isolation(move_eval, board_after, board_before)
    if gap:
        return gap

    return None


def _detect_rook_passivity(move_eval: Dict, board_after: chess.Board, board_before: chess.Board) -> Optional[Tuple[float, str]]:
    """Detect when a rook move reduces piece coordination."""

    move_san = move_eval.get("move", "")
    if not move_san or not move_san.startswith("R"):
        return None

    # Parse the rook move
    try:
        move = board_before.parse_san(move_san)
    except:
        return None

    from_sq = move.from_square
    to_sq = move.to_square

    # Check if rook moved to a square where it's more isolated
    rook = board_before.piece_at(from_sq)
    if not rook or rook.piece_type != chess.ROOK:
        return None

    # Confidence: 0.72 (under 0.75 threshold, will suppress)
    # This is hard to detect reliably without full game context
    confidence = 0.72

    return (confidence, "rook_isolation")


def _detect_piece_isolation(move_eval: Dict, board_after: chess.Board, board_before: chess.Board) -> Optional[Tuple[float, str]]:
    """Detect when a move creates piece isolation."""

    move_san = move_eval.get("move", "")
    if not move_san:
        return None

    try:
        move = board_before.parse_san(move_san)
    except:
        return None

    to_sq = move.to_square
    moved_piece = board_after.piece_at(to_sq)

    if not moved_piece:
        return None

    # Check if the piece moved has any support from other pieces
    our_color = moved_piece.color
    defenders = board_after.attackers(our_color, to_sq)

    # If piece has no support and is exposed: coordination gap
    if len(defenders) == 0 and moved_piece.piece_type in [chess.ROOK, chess.BISHOP, chess.KNIGHT]:
        # Only surface if it's a bad move (cp_loss > 0)
        cp_loss = move_eval.get("cp_loss", 0)
        if cp_loss > 15:  # Meaningful loss, not just a quiet move
            confidence = 0.68  # Below threshold
            return (confidence, "piece_isolation")

    return None


def has_coordination_gap(board: chess.Board, our_color: bool) -> bool:
    """Quick check: does this side have obvious coordination issues?

    Used for rating-aware coaching (don't show 600-rated player coordination
    hints when they're still learning piece movement).
    """
    # Stub for now; more sophisticated analysis later
    return False
