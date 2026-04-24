"""
PV Tactical Analyzer
====================

Deterministic. No LLM. No fabrication.

Given Stockfish's best move + its principal variation, walks the board with
python-chess and extracts the concrete tactical reason the best move works:

  - material won over the sequence
  - immediate fork (two+ valuable attacks or check+attack)
  - defender deflection (a defended opponent piece becomes undefended because
    the defender has to move or is captured during the PV)

Returns a one-line tactical explanation grounded in the PV. If no clear
tactic is detected, returns None — caller falls back to the LLM narrator.

Why deterministic: every claim in the output traces to a step in the PV. The
LLM path (v5_llm_narrator) is kept as a fallback for positional mistakes
where the PV doesn't yield a clean tactical signal.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import chess

logger = logging.getLogger(__name__)

# Piece values in pawns. Used for material-delta calculations across the PV
# walk — so "you win a rook" is computed, not guessed.
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,  # king can't be captured; present for completeness
}

PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}


def _material_by_color(board: chess.Board) -> Tuple[int, int]:
    """Return (white_material, black_material) in pawn-equivalents."""
    white = black = 0
    for _, piece in board.piece_map().items():
        v = PIECE_VALUES.get(piece.piece_type, 0)
        if piece.color == chess.WHITE:
            white += v
        else:
            black += v
    return white, black


def _material_delta(board: chess.Board, user_is_white: bool) -> int:
    """Material balance from the user's POV."""
    white, black = _material_by_color(board)
    return (white - black) if user_is_white else (black - white)


def _describe_material_gain(delta: int) -> Optional[str]:
    """Turn a signed pawn-equivalent delta into a coach phrase (or None if trivial)."""
    if delta >= 8:
        return "wins the queen"
    if delta >= 5:
        return "wins a rook"
    if delta >= 3:
        return "wins a piece"
    if delta == 2:
        return "wins two pawns"
    if delta >= 1:
        return "wins a pawn"
    return None


def _immediate_fork(board_before: chess.Board, best_move: chess.Move) -> Optional[Dict]:
    """
    After playing the best move, does the moving piece attack 2+ valuable
    opponent targets — or attack 1 target with check?

    Returns None if no fork-like pattern, else a dict describing it.
    """
    board = board_before.copy()
    mover_color = board.turn
    board.push(best_move)

    piece_at_dest = board.piece_at(best_move.to_square)
    if piece_at_dest is None:
        return None

    # Valuable = knight or better (pawn attacks don't really fork)
    valuable_targets: List[Tuple[int, int]] = []  # list of (square, piece_type)
    for sq in board.attacks(best_move.to_square):
        target = board.piece_at(sq)
        if target is None:
            continue
        if target.color == mover_color:
            continue
        if target.piece_type == chess.KING:
            continue  # check handled separately
        if target.piece_type >= chess.KNIGHT:
            valuable_targets.append((sq, target.piece_type))

    gives_check = board.is_check()

    if gives_check and valuable_targets:
        return {
            "type": "check_and_attack",
            "targets": valuable_targets,
            "gives_check": True,
        }
    if len(valuable_targets) >= 2:
        return {
            "type": "fork",
            "targets": valuable_targets[:3],
            "gives_check": False,
        }
    return None


def _exposed_defender_loss(
    board_before: chess.Board,
    pv_moves: List[chess.Move],
    user_is_white: bool,
) -> Optional[Dict]:
    """
    Detect "defender deflection": a defended opponent piece that becomes
    undefended (or falls outright) later in the PV because its defender had
    to move or was captured.

    Strategy:
      1. Before playing anything, snapshot opponent pieces that currently
         have at least one defender (same-color attacker on their square).
      2. Walk the PV. After each move, check whether any of those
         previously-defended pieces is now attacked by the user AND has no
         same-color defender. If so — that piece is the exposed target.
    """
    if not pv_moves:
        return None
    opp_color = not (chess.WHITE if user_is_white else chess.BLACK)

    # Snapshot: which opponent pieces were defended before any PV move?
    initial_defended: Dict[int, int] = {}  # square → piece_type
    for sq, piece in board_before.piece_map().items():
        if piece.color != opp_color:
            continue
        if piece.piece_type < chess.KNIGHT:
            continue  # pawns "hanging" is noise
        defenders = board_before.attackers(opp_color, sq)
        if defenders:
            initial_defended[sq] = piece.piece_type

    if not initial_defended:
        return None

    # Walk the PV. At each board state, see if any originally-defended
    # piece is now attacked by the user and undefended.
    board = board_before.copy()
    for mv in pv_moves:
        try:
            board.push(mv)
        except Exception:
            break
        user_color = chess.WHITE if user_is_white else chess.BLACK
        for sq, piece_type in list(initial_defended.items()):
            current_piece = board.piece_at(sq)
            if current_piece is None:
                # Piece already captured — something else is going on, skip.
                continue
            if current_piece.color != opp_color:
                continue
            if current_piece.piece_type != piece_type:
                continue
            attackers = board.attackers(user_color, sq)
            defenders = board.attackers(opp_color, sq)
            if attackers and not defenders:
                return {"square": sq, "piece_type": piece_type}
    return None


def explain_best_move_tactically(
    fen_before: str,
    best_move_uci: str,
    best_move_san: str,
    pv_after_best: List[str],
) -> Optional[str]:
    """
    Return a one-line tactical explanation for why the best move works,
    or None if the PV doesn't yield a clean tactical signal.

    Args:
      fen_before: position before best move
      best_move_uci: best move in UCI (e.g. "e2e4")
      best_move_san: best move SAN (for display)
      pv_after_best: list of SAN (or UCI) moves in the engine's line —
                     typically 4-8 moves deep

    Examples of what it returns:
      "Nxf2 forks queen and bishop — wins a piece."
      "Bxc4 wins a pawn."
      "Qh5+ attacks the king and the rook — wins a rook."
      "Rxd5 deflects the queen — the bishop on c4 falls next."
    """
    if not fen_before or not best_move_uci:
        return None

    try:
        board = chess.Board(fen_before)
    except Exception:
        return None

    user_is_white = board.turn == chess.WHITE

    try:
        best_move = chess.Move.from_uci(best_move_uci)
    except Exception:
        # Try SAN as a fallback (some records store SAN where we expect UCI)
        try:
            best_move = board.parse_san(best_move_san or best_move_uci)
        except Exception:
            return None

    if best_move not in board.legal_moves:
        return None

    # Parse the PV moves (accepting SAN or UCI per entry).
    pv_moves: List[chess.Move] = []
    pv_board = board.copy()
    # First PV move is typically the best move itself — include it.
    pv_input = list(pv_after_best or [])
    if not pv_input or pv_input[0] not in (best_move_san, best_move_uci):
        pv_input = [best_move_san or best_move_uci] + pv_input
    for entry in pv_input:
        if not entry:
            continue
        candidate = None
        for parser in (
            lambda e=entry: chess.Move.from_uci(e),
            lambda e=entry: pv_board.parse_san(e),
        ):
            try:
                mv = parser()
                if mv in pv_board.legal_moves:
                    candidate = mv
                    break
            except Exception:
                continue
        if candidate is None:
            break
        pv_moves.append(candidate)
        pv_board.push(candidate)

    if not pv_moves:
        return None

    # Facts:
    # 1. immediate fork after the best move
    fork_info = _immediate_fork(board, pv_moves[0])

    # 2. material delta at end of PV (user POV)
    start_delta = _material_delta(board, user_is_white)
    end_delta = _material_delta(pv_board, user_is_white)
    material_won = end_delta - start_delta

    # 3. defender deflection: a previously-defended opponent piece becomes
    #    undefended / captured in the PV
    deflection = _exposed_defender_loss(board, pv_moves, user_is_white)

    # ─── Compose the sentence ───
    parts: List[str] = []

    if fork_info:
        if fork_info["type"] == "check_and_attack":
            # first target only — keeps the sentence clean
            target_name = PIECE_NAMES.get(fork_info["targets"][0][1], "piece")
            parts.append(
                f"{best_move_san} attacks the king and the {target_name}"
            )
        else:
            names = [PIECE_NAMES.get(pt, "piece") for _, pt in fork_info["targets"][:2]]
            parts.append(f"{best_move_san} forks {names[0]} and {names[1]}")

    if deflection and not fork_info:
        # A pure defender-deflection tactic (not also a fork)
        piece_name = PIECE_NAMES.get(deflection["piece_type"], "piece")
        parts.append(
            f"{best_move_san} forces the defender to move — the {piece_name} falls next"
        )

    material_phrase = _describe_material_gain(material_won)
    if material_phrase:
        parts.append(material_phrase)

    if not parts:
        return None

    # Single sentence, deterministic, grounded.
    if len(parts) == 1:
        return parts[0] + "."
    return parts[0] + " — " + ", ".join(parts[1:]) + "."
