"""Detects the tactical idea behind the engine's best move by walking
`pv_after_best` with python-chess.

Closes Mohit-flagged gap (2026-05-20): captions said
"{best_move} was better" without explaining WHY. The user is left
guessing what tactic the engine saw. The detector walks the PV from
the position after best_move and identifies the climax:

  - mate_in_N — PV contains a `#` mate move by the user side
  - piece_capture — PV contains a user-side capture of a piece worth
    >= knight value (the actionable "you'd win the queen/rook/etc.")
  - material — PV contains user-side pawn captures only (no piece)
  - None — nothing significant, PV is positional / quiet

The result feeds R12_blunder.json `why_clauses_user` predicates so the
phrasing lives in JSON. Python only extracts chess data here.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    import chess
except Exception:  # pragma: no cover — defensive
    chess = None  # type: ignore

logger = logging.getLogger(__name__)


_PIECE_NAME = {
    1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen", 6: "king",
}
_PIECE_VALUE = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9, 6: 100}


def detect_missed_tactic(
    fen_before: Optional[str],
    best_move_san: Optional[str],
    pv_after_best: List[str],
    user_color: str,
) -> Optional[Dict[str, Any]]:
    """Walk the principal variation after engine's recommended move,
    return a structured payload describing the tactical climax.

    Args:
      fen_before: FEN of the position BEFORE the user's actual move
        (the position where best_move was the engine's choice).
      best_move_san: Engine's recommended move (SAN).
      pv_after_best: List of SAN moves played AFTER best_move was made,
        alternating opp, user, opp, user, ...
      user_color: "white" or "black"

    Returns one of (highest-priority match wins):
      {"kind": "mate", "ply": N, "mating_move": "Qxf7#"}
      {"kind": "piece_capture", "piece_type": "queen",
       "square": "d8", "capturing_move": "Nxd8", "ply": N}
      {"kind": "material", "captures": N}
      None — no actionable tactic in the PV

    Returns None on any error (missing FEN, malformed PV, etc.).
    Caller treats None as "no missed_tactic_kind fact" and falls back
    to existing why-clauses.
    """
    if not chess or not fen_before or not best_move_san or not pv_after_best:
        return None

    try:
        board = chess.Board(fen_before)
        # Apply best_move first so the board is at the position the PV
        # starts from. Detector walks the PV from there.
        best_move_obj = board.parse_san(best_move_san)
        board.push(best_move_obj)
    except Exception as exc:
        logger.warning(f"[tactic_detector] bad fen or best_move: {exc}")
        return None

    user_color_white = (user_color or "").lower() == "white"
    user_piece_captures: List[Dict[str, Any]] = []
    user_pawn_captures = 0
    mate_payload: Optional[Dict[str, Any]] = None

    # Side-to-move in fen_after_best is OPPONENT. So pv[0] is played
    # by opponent, pv[1] by user, alternating.
    for ply_index, san in enumerate(pv_after_best):
        is_user_move = (ply_index % 2 == 1)  # second mover in PV = user
        try:
            move = board.parse_san(san)
        except Exception:
            # PV may contain garbage past depth; stop walking.
            break

        is_capture = board.is_capture(move)
        captured_piece_type = None
        captured_square = None
        if is_capture:
            captured_square = chess.square_name(move.to_square)
            if board.is_en_passant(move):
                captured_piece_type = 1  # pawn
            else:
                cap_piece = board.piece_at(move.to_square)
                captured_piece_type = cap_piece.piece_type if cap_piece else None

        # Apply the move so SAN annotations (#, +) reflect resulting state.
        board.push(move)
        # python-chess uses `is_checkmate` on the resulting board.
        if board.is_checkmate() and is_user_move:
            mate_payload = {
                "kind": "mate",
                "ply": ply_index + 1,
                "mating_move": san,
            }
            break  # mate is the strongest possible — stop walking

        if is_user_move and is_capture and captured_piece_type:
            if captured_piece_type >= 2:  # knight or higher
                user_piece_captures.append({
                    "kind": "piece_capture",
                    "piece_type": _PIECE_NAME.get(captured_piece_type, "piece"),
                    "piece_value": _PIECE_VALUE.get(captured_piece_type, 0),
                    "square": captured_square,
                    "capturing_move": san,
                    "ply": ply_index + 1,
                })
            else:
                user_pawn_captures += 1

    if mate_payload:
        return mate_payload

    if user_piece_captures:
        # Pick the highest-value piece won.
        best_capture = max(user_piece_captures, key=lambda c: c["piece_value"])
        # Strip the internal piece_value field — JSON templates don't need it.
        return {
            "kind": "piece_capture",
            "piece_type": best_capture["piece_type"],
            "square": best_capture["square"],
            "capturing_move": best_capture["capturing_move"],
            "ply": best_capture["ply"],
        }

    if user_pawn_captures >= 1:
        return {"kind": "material", "captures": user_pawn_captures}

    return None
