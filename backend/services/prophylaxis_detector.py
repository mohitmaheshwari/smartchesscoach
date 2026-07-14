"""prophylaxis_detector.py — Detect prophylaxis gaps (reactive vs proactive thinking).

Prophylaxis = preventing problems before they happen, not reacting to threats.

A prophylaxis gap is when the user makes a move that reacts to an opponent's threat
instead of preventing the threat from arising in the first place.

CONSERVATIVE DETECTOR: This is hard to detect reliably. We use 70% confidence gate
at launch, will refine in P2.

RATING-AWARE: 1300+ players should see prophylaxis feedback. 600-1000 are still
learning basic tactics.
"""

import chess
from typing import Dict, List, Optional, Tuple


def detect_prophylaxis_gap(move_eval: Dict, fen_before: str, fen_after: str) -> Optional[Tuple[float, str]]:
    """
    Detect prophylaxis gaps (reactive moves).

    Returns: (confidence: float [0-1], gap_type: str) or None

    Confidence gates:
    - 0.70+: Surface to user (launch threshold, conservative)
    - Below: Suppress
    """

    board_before = chess.Board(fen_before)
    board_after = chess.Board(fen_after)

    cp_loss = move_eval.get("cp_loss", 0)

    # Only look for prophylaxis gaps in moves with small losses (not blunders)
    if cp_loss >= 100:
        return None

    # Detect: Defensive move against a threat that could have been prevented earlier
    # This is hard without game history, so we use a conservative gate

    gap = _detect_reactive_defense(move_eval, board_after, board_before)
    if gap:
        return gap

    return None


def _detect_reactive_defense(move_eval: Dict, board_after: chess.Board, board_before: chess.Board) -> Optional[Tuple[float, str]]:
    """Detect when a move is reactive defense instead of proactive prevention."""

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

    # Check if this move is defensive (blocks a threat, moves a piece to safety)
    # These are reactive, not proactive

    # Check if opponent had a major threat that we just defended against
    opp_threats = list(board_before.attackers(not moved_piece.color, to_sq))

    # If piece was under attack and we just moved it to safety: reactive
    if len(opp_threats) > 0:
        cp_loss = move_eval.get("cp_loss", 0)
        if 10 < cp_loss < 100:  # Small inaccuracy, likely reactive
            # Confidence: 0.65 (below 0.70 threshold)
            confidence = 0.65
            return (confidence, "reactive_defense")

    return None


def is_prophylactic_move(board: chess.Board, move: chess.Move) -> bool:
    """Check if a move is proactive prophylaxis (hard to detect reliably)."""
    # Stub for now; will refine in testing
    return False
