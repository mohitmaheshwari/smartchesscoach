"""
Moment Context — pull the FULL context the LLM needs to write coaching
prose at the depth a 1200 player actually wants.

Until now, the Plan Decryption prompt only saw the user's blunder
consequence (their piece will be captured, etc.). That produced
"your move was bad because X is now attacked" — chess.com-flavored,
shallow.

Real coaching names:
  1. The opponent's just-played move (what they did to you)
  2. The opponent's MISSED move (what they SHOULD have done)
  3. The user's missed move (the saving / winning line)
  4. The user's missed LINE (next 3-4 ply showing the rescue)
  5. Both kings' squares, key piece geometry

This module extracts all of that from the existing V5 + stockfish data
and serves it as plain facts the prompt can drop in. No LLM.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import chess

logger = logging.getLogger(__name__)


_PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}


def _piece_name(piece: chess.Piece) -> str:
    return _PIECE_NAMES.get(piece.piece_type, "piece")


def _uci_to_san(fen: str, uci: str) -> Optional[str]:
    """Convert a UCI move to SAN given the FEN. None if illegal."""
    if not fen or not uci:
        return None
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            return None
        return board.san(move)
    except Exception:
        return None


def _describe_move(fen: str, uci: str) -> Optional[Dict]:
    """Return {san, piece, from_square, to_square} for a UCI move."""
    if not fen or not uci or len(uci) < 4:
        return None
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci)
        moving_piece = board.piece_at(move.from_square)
        if moving_piece is None:
            return None
        san = None
        try:
            if move in board.legal_moves:
                san = board.san(move)
        except Exception:
            pass
        return {
            "san": san or uci,
            "piece": _piece_name(moving_piece),
            "from_square": chess.square_name(move.from_square),
            "to_square": chess.square_name(move.to_square),
        }
    except Exception:
        return None


def _pv_to_san_sequence(fen: str, pv: List[str], max_ply: int = 4) -> List[Dict]:
    """Convert a PV (list of UCIs) into a list of SAN moves with side
    annotation, capped at max_ply. Each entry: {san, side, ply}.
    """
    if not fen or not pv:
        return []
    try:
        board = chess.Board(fen)
    except Exception:
        return []

    out = []
    for i, uci in enumerate(pv[:max_ply]):
        try:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                break
            san = board.san(move)
            out.append({
                "san": san,
                "side": "white" if board.turn == chess.WHITE else "black",
                "ply": i + 1,
            })
            board.push(move)
        except Exception:
            break
    return out


def _piece_locations(fen: str) -> Dict[str, List[Dict]]:
    """Where every piece is on the board. Used for the LLM to write
    'their rook on g2' or 'your king on c6' specifically."""
    try:
        board = chess.Board(fen)
    except Exception:
        return {}
    result = {"white": [], "black": []}
    for sq, piece in board.piece_map().items():
        result["white" if piece.color == chess.WHITE else "black"].append({
            "piece": _piece_name(piece),
            "square": chess.square_name(sq),
        })
    return result


# ── Public API ───────────────────────────────────────────────────────

def build_moment_context(
    decryption_v5_data: List[Dict],
    move_evaluations: List[Dict],
    critical_move_number: int,
    user_color: str,
) -> Optional[Dict]:
    """Gather the full coaching context for one moment.

    Args:
        decryption_v5_data: V5 per-move records.
        move_evaluations:   raw stockfish move data (for best_move /
                            pv from the opponent's preceding ply).
        critical_move_number: the user's move number under analysis.
        user_color:         "white" | "black"

    Returns:
        Dict with all the facts the prompt needs, or None if data is
        missing.
    """
    if not decryption_v5_data:
        return None

    # 1. Locate the user's critical move record in V5.
    target = None
    target_idx = None
    for i, m in enumerate(decryption_v5_data):
        if (m.get("is_user_move")
                and m.get("move_number") == critical_move_number):
            target = m
            target_idx = i
            break
    if not target or target_idx is None:
        return None

    fen_before = target.get("fen_before")
    if not fen_before:
        return None

    # 2. The user's actual move.
    user_move_uci = None
    if target.get("move_san") and fen_before:
        try:
            board = chess.Board(fen_before)
            for mv in board.legal_moves:
                if board.san(mv) == target.get("move_san"):
                    user_move_uci = mv.uci()
                    break
        except Exception:
            pass

    user_move = _describe_move(fen_before, user_move_uci) if user_move_uci else {
        "san": target.get("move_san"),
        "piece": None,
        "from_square": None,
        "to_square": None,
    }

    # 3. The user's missed move (engine's recommended alternative).
    best_uci = target.get("best_move_uci") or ""
    user_missed_move = _describe_move(fen_before, best_uci) if best_uci else None

    # 4. The PV from the user's missed move — shows the saving line.
    user_missed_line = []
    pv = target.get("pv_after_best") or []
    if best_uci and pv and fen_before:
        try:
            board = chess.Board(fen_before)
            best = chess.Move.from_uci(best_uci)
            if best in board.legal_moves:
                board.push(best)
                # The PV stored in V5 is the line AFTER the best move.
                user_missed_line = _pv_to_san_sequence(board.fen(), pv, max_ply=4)
        except Exception:
            pass

    # 5. The opponent's just-played move (the V5 entry right before target).
    opp_just_played = None
    if target_idx > 0:
        prev = decryption_v5_data[target_idx - 1]
        if not prev.get("is_user_move") and prev.get("move_san"):
            opp_fen_before = prev.get("fen_before")
            opp_uci = None
            if opp_fen_before:
                try:
                    bb = chess.Board(opp_fen_before)
                    for mv in bb.legal_moves:
                        if bb.san(mv) == prev.get("move_san"):
                            opp_uci = mv.uci()
                            break
                except Exception:
                    pass
            if opp_fen_before and opp_uci:
                opp_just_played = _describe_move(opp_fen_before, opp_uci)
                opp_just_played["fen_before"] = opp_fen_before
                # Did the opponent ALSO have a better move?
                opp_best_uci = prev.get("best_move_uci") or ""
                if opp_best_uci and opp_best_uci != opp_uci:
                    opp_missed = _describe_move(opp_fen_before, opp_best_uci)
                    if opp_missed:
                        opp_just_played["opp_missed_move"] = opp_missed
                # Was the opponent's move actually a slip?
                opp_just_played["was_mistake"] = prev.get("severity") in (
                    "opp_blunder", "opp_mistake", "blunder", "mistake"
                )

    # 6. Piece locations (full board snapshot for the LLM).
    pieces = _piece_locations(fen_before)

    return {
        "fen_before": fen_before,
        "user_color": user_color,
        "move_number": critical_move_number,
        "user_move": user_move,                # what they played
        "user_missed_move": user_missed_move,  # what they should have played
        "user_missed_line": user_missed_line,  # 3-4 ply of the saving line
        "opp_just_played": opp_just_played,    # what they did right before
        "pieces": pieces,                       # piece locations both sides
    }


def format_moment_context_for_prompt(ctx: Dict) -> str:
    """Render the moment context as plain bullet facts the LLM consumes.
    No editorial language — just the facts."""
    if not ctx:
        return ""
    lines = []
    user_color = ctx.get("user_color", "white")

    # Pieces snapshot — let the LLM name "their rook on g2" specifically.
    pieces = ctx.get("pieces") or {}
    user_pieces = pieces.get(user_color, [])
    opp_pieces = pieces.get("black" if user_color == "white" else "white", [])
    if user_pieces:
        lines.append("- USER pieces on the board: " + ", ".join(
            f"{p['piece']} on {p['square']}" for p in user_pieces
        ))
    if opp_pieces:
        lines.append("- OPPONENT pieces on the board: " + ", ".join(
            f"{p['piece']} on {p['square']}" for p in opp_pieces
        ))

    opp = ctx.get("opp_just_played")
    if opp:
        descriptor = (
            f"OPPONENT just played: {opp['piece']} from {opp['from_square']} to {opp['to_square']} "
            f"({opp.get('san', '?')})"
        )
        lines.append("- " + descriptor)
        if opp.get("opp_missed_move"):
            m = opp["opp_missed_move"]
            verdict = "actually a slip" if opp.get("was_mistake") else "the move worked, but a sharper plan was"
            lines.append(
                f"- Opponent's better alternative ({verdict}): "
                f"{m['san']} ({m['piece']} → {m['to_square']})"
            )

    user_played = ctx.get("user_move") or {}
    if user_played.get("from_square") and user_played.get("to_square"):
        lines.append(
            f"- USER played: {user_played.get('piece')} from {user_played['from_square']} to {user_played['to_square']} "
            f"({user_played.get('san', '?')})"
        )

    miss = ctx.get("user_missed_move")
    if miss and miss.get("from_square"):
        lines.append(
            f"- USER's MISSED MOVE (the saving / winning move): "
            f"{miss['piece']} from {miss['from_square']} to {miss['to_square']} "
            f"({miss.get('san', '?')})"
        )

    line = ctx.get("user_missed_line") or []
    if line:
        line_str = " ".join(f"{x['san']}" for x in line)
        lines.append(
            f"- The line that would have followed the missed move: {line_str}"
        )
        lines.append(
            "- USE this line in your output — name the next move or two so "
            "the player sees the rescue plan."
        )

    return "\n".join(lines)
