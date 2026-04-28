"""
Static Exchange Evaluation (SEE)
================================

Authored design (see docstring of static_exchange_eval). One job:

    "If pieces trade on this square, does the tactic actually win
     material?"

Not engine search. No PV, no checkmate logic, no sacrifice depth,
no positional compensation. Just the deterministic exchange swap-list
with optimal back-prop. That is enough for fork confidence.

PUBLIC API:
    static_exchange_eval(board, target_square, attacker_color) -> int

Returns centipawn-like material gain for `attacker_color` if exchanges
happen on `target_square`. Positive = good for attacker. Negative =
bad. Zero when target is empty or no attacker exists.
"""

from __future__ import annotations

from typing import Optional, Tuple

import chess


PIECE_VALUE = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}


def _least_valuable_attacker(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
) -> Optional[Tuple[int, chess.Square, chess.Piece]]:
    """Return (value, from_sq, piece) for color's cheapest attacker of
    `square`. King is excluded — including the king as an exchange
    participant breaks SEE because the king can't legally be captured.
    """
    candidates = []
    for from_sq in board.attackers(color, square):
        piece = board.piece_at(from_sq)
        if not piece or piece.piece_type == chess.KING:
            continue
        candidates.append((PIECE_VALUE[piece.piece_type], from_sq, piece))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0]


def _build_swap_list(
    board: chess.Board,
    target_square: chess.Square,
    attacker_color: chess.Color,
) -> list:
    """Walk the exchange sequence on `target_square` and return the
    raw swap-list of captured-piece values, in capture order. Empty
    list when the target is empty or the attacker has no piece on it.
    """
    target_piece = board.piece_at(target_square)
    if not target_piece:
        return []

    work = board.copy(stack=False)

    gains = []
    side = attacker_color
    current_captured_value = PIECE_VALUE[target_piece.piece_type]

    while True:
        attacker = _least_valuable_attacker(work, target_square, side)
        if attacker is None:
            break

        attacker_value, from_sq, attacker_piece = attacker
        gains.append(current_captured_value)

        work.remove_piece_at(from_sq)
        work.remove_piece_at(target_square)
        work.set_piece_at(target_square, attacker_piece)

        current_captured_value = attacker_value
        side = not side

    return gains


def static_exchange_eval(
    board: chess.Board,
    target_square: chess.Square,
    attacker_color: chess.Color,
) -> int:
    """Standard SEE — optimal-play exchange evaluation.

    Each side chooses to stop the exchange if continuing would lose
    material (back-prop clamps at every step including step 0). So
    when the initiator has no profitable capture, returns 0 — meaning
    "the attacker shouldn't take."

    Use this for: "is this exchange profitable for the attacker?"
    Returns 0 for both "no exchange exists" and "attacker rationally
    refuses." The two are indistinguishable; use forced_exchange_eval
    when you need to separate them.
    """
    gains = _build_swap_list(board, target_square, attacker_color)
    if not gains:
        return 0
    for i in range(len(gains) - 2, -1, -1):
        gains[i] = max(0, gains[i] - gains[i + 1])
    return gains[0]


def forced_exchange_eval(
    board: chess.Board,
    target_square: chess.Square,
    attacker_color: chess.Color,
) -> int:
    """Forced-exchange variant — attacker is committed to start the
    exchange (no step-0 refusal). Subsequent moves still play
    optimally, but step 0's clamp is removed.

    Returns negative values when the initiator's "forced" capture
    nets material loss. Useful for fork-confidence NMGS where we
    want the position quality of the capture itself, distinguishing
    "neutral / no exchange" from "bad capture available."

    Examples:
      • Free pawn (no defender): +100  (same as standard SEE)
      • Even minor trade with defender: 0  (same)
      • Q-takes-P defended by N: -800  (standard SEE = 0 here)
    """
    gains = _build_swap_list(board, target_square, attacker_color)
    if not gains:
        return 0
    # Back-prop subsequent decisions only — step 0 stays unclamped
    # because the initiator is committed.
    for i in range(len(gains) - 2, 0, -1):
        gains[i] = max(0, gains[i] - gains[i + 1])
    if len(gains) >= 2:
        return gains[0] - gains[1]
    return gains[0]
