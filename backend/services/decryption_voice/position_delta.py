"""
Position delta extractor — what just became true that wasn't true before.

The LLM hallucinates without grounded facts. Without delta, "they
attacked your king" is what comes out. With delta, "their bishop opened
the diagonal to your king" is what comes out. That's the wow gap.

Returns a structured dict the Decryption prompt can drop into the user
message. Computed deterministically from python-chess board state — no
LLM in this layer.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import logging

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


def _piece_label(piece: chess.Piece) -> str:
    return _PIECE_NAMES.get(piece.piece_type, "piece")


def _square_name(sq: int) -> str:
    return chess.square_name(sq)


def _attackers_of(board: chess.Board, square: int, color: chess.Color) -> List[Tuple[str, str]]:
    """Pieces of `color` that attack `square`. Returns [(piece_name, sq_name)]."""
    out = []
    for attacker_sq in board.attackers(color, square):
        p = board.piece_at(attacker_sq)
        if p:
            out.append((_piece_label(p), _square_name(attacker_sq)))
    return out


def _hanging_pieces(board: chess.Board, owner: chess.Color) -> List[Tuple[str, str]]:
    """Pieces of `owner` whose square has more enemy attackers than friendly defenders.
    Heuristic, not SEE — enough to flag "this piece is now in trouble."
    """
    enemy = not owner
    hanging = []
    for sq, piece in board.piece_map().items():
        if piece.color != owner:
            continue
        if piece.piece_type == chess.KING:
            continue
        attackers = len(board.attackers(enemy, sq))
        defenders = len(board.attackers(owner, sq))
        if attackers > defenders:
            hanging.append((_piece_label(piece), _square_name(sq)))
    return hanging


def _king_zone_attackers(board: chess.Board, king_color: chess.Color) -> int:
    """Count enemy pieces attacking any square in the king's 3x3 zone (inclusive)."""
    king_sq = board.king(king_color)
    if king_sq is None:
        return 0
    enemy = not king_color
    file_k = chess.square_file(king_sq)
    rank_k = chess.square_rank(king_sq)
    attackers = set()
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            f = file_k + df
            r = rank_k + dr
            if 0 <= f <= 7 and 0 <= r <= 7:
                sq = chess.square(f, r)
                for atk_sq in board.attackers(enemy, sq):
                    attackers.add(atk_sq)
    return len(attackers)


def _opened_lines(
    board_before: chess.Board,
    board_after: chess.Board,
    move: chess.Move,
) -> List[str]:
    """Files/ranks that became clear by the move (the moved piece's
    departed file/rank no longer has that piece blocking it).
    """
    lines = []
    from_sq = move.from_square
    file_letter = chess.FILE_NAMES[chess.square_file(from_sq)]
    # Did the move clear the file? Only meaningful if from_sq's file
    # was occupied by a sliding piece.
    moved_piece = board_before.piece_at(from_sq)
    if moved_piece and moved_piece.piece_type in (chess.QUEEN, chess.ROOK, chess.PAWN):
        # Only flag as "file opened" if the moved piece was on a file
        # otherwise contested (i.e., enemy pieces still on it after move).
        # Simple proxy: at least one enemy piece is also on this file.
        for r in range(8):
            sq = chess.square(chess.square_file(from_sq), r)
            piece = board_after.piece_at(sq)
            if piece and piece.color != moved_piece.color:
                lines.append(f"{file_letter}-file")
                break
    return lines


_PIECE_VALUE = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100,
}


def _likely_opponent_capture(
    board_after: chess.Board,
    to_square: int,
    user_chess_color: chess.Color,
) -> Optional[Dict]:
    """If the user's moved piece is hanging on `to_square`, compute the
    cheapest legal capture by the opponent. Returns SAN + attacker info,
    or None if not hanging or no legal capture exists."""
    opp_color = not user_chess_color
    attackers = list(board_after.attackers(opp_color, to_square))
    if not attackers:
        return None
    defenders = list(board_after.attackers(user_chess_color, to_square))
    # If equally or better defended, opponent won't capture for free.
    if len(attackers) <= len(defenders):
        return None
    # Cheapest attacker takes the piece.
    attackers.sort(key=lambda sq: _PIECE_VALUE.get(board_after.piece_at(sq).piece_type, 99))
    cheapest_sq = attackers[0]
    cheapest_piece = board_after.piece_at(cheapest_sq)
    capture_move = chess.Move(cheapest_sq, to_square)
    # board_after has the wrong side-to-move (it's opp's turn). Use as-is.
    if capture_move in board_after.legal_moves:
        try:
            san = board_after.san(capture_move)
        except Exception:
            san = None
        return {
            "san": san,
            "attacker_piece": _piece_label(cheapest_piece),
            "attacker_square": _square_name(cheapest_sq),
            "target_square": _square_name(to_square),
        }
    return None


def _user_remaining_majors(board: chess.Board, user_color: chess.Color) -> List[Tuple[str, str]]:
    """List user's queens/rooks/bishops/knights still on the board.
    Lets the Decryption sentence 3 name a specific other piece instead
    of saying "your pieces were too far away" (the previous failure mode)."""
    out = []
    for sq, piece in board.piece_map().items():
        if piece.color != user_color:
            continue
        if piece.piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT):
            out.append((_piece_label(piece), _square_name(sq)))
    return out


def compute_position_delta(
    fen_before: str,
    fen_after: str,
    move_uci: str,
    user_color: str,
) -> Optional[Dict]:
    """Build the delta facts the Decryption LLM uses to ground its prose.

    user_color: "white" | "black" — which side is the player.
    """
    try:
        board_before = chess.Board(fen_before)
        board_after = chess.Board(fen_after)
        move = chess.Move.from_uci(move_uci) if move_uci else None
    except Exception as e:
        logger.warning(f"[position_delta] FEN/move parse failed: {e}")
        return None

    user_chess_color = chess.WHITE if user_color == "white" else chess.BLACK
    opp_color = not user_chess_color

    moved_piece = board_before.piece_at(move.from_square) if move else None
    captured_piece = None
    if move:
        # If after-board has a piece-of-mover-color on to_square AND
        # before-board had an enemy piece on to_square → capture.
        before_target = board_before.piece_at(move.to_square)
        if before_target and moved_piece and before_target.color != moved_piece.color:
            captured_piece = before_target

    # Pieces that BECAME hanging after the move (relevant to user's pain).
    hanging_after = _hanging_pieces(board_after, user_chess_color)
    hanging_before = _hanging_pieces(board_before, user_chess_color)
    newly_hanging = [h for h in hanging_after if h not in hanging_before]

    # Same for opponent — used when the user's move was actually winning.
    opp_hanging_after = _hanging_pieces(board_after, opp_color)
    opp_hanging_before = _hanging_pieces(board_before, opp_color)
    opp_newly_hanging = [h for h in opp_hanging_after if h not in opp_hanging_before]

    # King zone pressure delta
    user_king_attackers_before = _king_zone_attackers(board_before, user_chess_color)
    user_king_attackers_after = _king_zone_attackers(board_after, user_chess_color)
    king_pressure_delta = user_king_attackers_after - user_king_attackers_before

    # Opened lines
    opened = _opened_lines(board_before, board_after, move) if move else []

    # The user's move described in plain terms
    move_described = None
    if moved_piece and move:
        move_described = {
            "piece": _piece_label(moved_piece),
            "from_square": _square_name(move.from_square),
            "to_square": _square_name(move.to_square),
            "was_capture": captured_piece is not None,
            "captured_piece": _piece_label(captured_piece) if captured_piece else None,
        }

    # The user's move's destination — is the moved piece now itself
    # under attack (will it be captured next move)? This is the
    # "you walked into a recapture" signal.
    moved_piece_now_attacked = False
    moved_piece_attackers: List[Tuple[str, str]] = []
    likely_capture = None
    if move:
        attackers = _attackers_of(board_after, move.to_square, opp_color)
        defenders = _attackers_of(board_after, move.to_square, user_chess_color)
        if attackers and len(attackers) > len(defenders):
            moved_piece_now_attacked = True
            moved_piece_attackers = attackers
            # If hanging, predict the opponent's actual capture move so
            # the LLM can write "they took it" with concrete grounding.
            likely_capture = _likely_opponent_capture(
                board_after, move.to_square, user_chess_color
            )

    # User's other major pieces still on the board — lets sentence 3
    # name a specific piece instead of vague "your other pieces".
    remaining_majors = _user_remaining_majors(board_after, user_chess_color)
    # Filter out the moved piece itself if it's still on the board.
    if move and move.to_square is not None:
        moved_to_label = (
            _piece_label(board_after.piece_at(move.to_square))
            if board_after.piece_at(move.to_square) else None
        )
        moved_to_sq_name = _square_name(move.to_square)
        if moved_to_label:
            remaining_majors = [
                (p, s) for (p, s) in remaining_majors
                if not (p == moved_to_label and s == moved_to_sq_name)
            ]

    return {
        "move_described": move_described,
        "moved_piece_now_attacked": moved_piece_now_attacked,
        "moved_piece_attackers": moved_piece_attackers,
        "likely_opponent_capture": likely_capture,
        "user_pieces_newly_hanging": newly_hanging,
        "opp_pieces_newly_hanging": opp_newly_hanging,
        "user_king_attackers_count": user_king_attackers_after,
        "user_king_attackers_added": max(0, king_pressure_delta),
        "opened_lines": opened,
        "user_remaining_majors": remaining_majors,
    }


def format_delta_for_prompt(delta: Dict) -> str:
    """Render the delta dict as plain bullet facts for the LLM prompt.
    Keep it tight — no editorial language, just facts."""
    if not delta:
        return ""
    lines = []

    md = delta.get("move_described") or {}
    if md:
        action = "captured" if md.get("was_capture") else "moved"
        line = f"- The user's {md.get('piece')} {action} from {md.get('from_square')} to {md.get('to_square')}"
        if md.get("was_capture") and md.get("captured_piece"):
            line += f" (taking a {md.get('captured_piece')})"
        lines.append(line + ".")

    if delta.get("moved_piece_now_attacked"):
        atk = delta.get("moved_piece_attackers") or []
        if atk:
            atk_desc = ", ".join(f"{p} on {s}" for p, s in atk)
            lines.append(f"- The user's piece is now attacked by: {atk_desc}.")

    cap = delta.get("likely_opponent_capture")
    if cap:
        san = cap.get("san") or "the capture"
        atk_p = cap.get("attacker_piece", "piece")
        atk_sq = cap.get("attacker_square", "?")
        tgt_sq = cap.get("target_square", "?")
        lines.append(
            f"- The opponent's next move will capture the user's piece for free: "
            f"{san} ({atk_p} on {atk_sq} takes on {tgt_sq}). "
            f"Treat this piece as gone — not just attacked."
        )

    nh = delta.get("user_pieces_newly_hanging") or []
    if nh:
        nh_desc = ", ".join(f"{p} on {s}" for p, s in nh)
        lines.append(f"- User pieces that became loose after the move: {nh_desc}.")

    onh = delta.get("opp_pieces_newly_hanging") or []
    if onh:
        onh_desc = ", ".join(f"{p} on {s}" for p, s in onh)
        lines.append(f"- Opponent pieces that became loose: {onh_desc}.")

    if delta.get("user_king_attackers_added", 0) > 0:
        lines.append(
            f"- Pressure near the user's king increased by "
            f"{delta['user_king_attackers_added']} attacker(s)."
        )

    opened = delta.get("opened_lines") or []
    if opened:
        lines.append(f"- Lines opened by the move: {', '.join(opened)}.")

    majors = delta.get("user_remaining_majors") or []
    if majors:
        majors_desc = ", ".join(f"{p} on {s}" for p, s in majors)
        lines.append(
            f"- User's other major pieces still on the board: {majors_desc}. "
            f"Use these to be specific in sentence 3 — name a piece, "
            f"not 'your other pieces'."
        )

    return "\n".join(lines)
