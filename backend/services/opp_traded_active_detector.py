"""
opp_traded_active_detector.py — opp-failure V3: "traded an active piece for less".

Built 2026-06-07 (Mohit greenlit). The opponent initiates a CAPTURE/TRADE with
an active, developed minor/major piece, gets recaptured (so it's a trade, not a
free grab), and it's a mistake (the resulting position favors the user). The
coach-voice point: their good piece comes off the board and you're left better.

This is opp-failure V3 — the one piece of the framework with NO existing clause
(verified against opp_failure_* + why_opp_* before building, unlike the 4
redundant overnight detectors). Standalone + tested before any wiring.

LOCKED ON DATA (408-game corpus, 352 opp capture-mistakes by a minor/major):
  - 85% of the capturing pieces are developed (off home rank)
  - capturing-piece mobility: median 8 → "active" = mobility >= 6 (the <=5
    buckets are the inactive minority)
  - 40% (144) get recaptured next ply = the genuine trade subset
Thresholds below come from that distribution, not a guess.

detect_opp_traded_active(board_before, opp_move, pv_after_played, cp_loss)
  -> {"piece": "bishop", "move_san": "Bxf3", "recapture_san": "Nxf3+",
      "square": "f3"} | None
"""
from typing import Optional, Dict, List
import chess

_MINOR_MAJOR = {chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN}
_PIECE_NAME = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
               chess.ROOK: "rook", chess.QUEEN: "queen"}
_HOME = {
    chess.WHITE: {chess.A1, chess.B1, chess.C1, chess.D1, chess.E1, chess.F1, chess.G1, chess.H1},
    chess.BLACK: {chess.A8, chess.B8, chess.C8, chess.D8, chess.E8, chess.F8, chess.G8, chess.H8},
}

# Data-locked gates (see module docstring).
ACTIVE_MOBILITY_MIN = 6      # median was 8; 6 separates active from the inactive minority
CP_LOSS_MIN = 150            # real mistake, with margin


def detect_opp_traded_active(
    board_before: chess.Board,
    opp_move: chess.Move,
    pv_after_played: Optional[List[str]],
    cp_loss: Optional[int],
) -> Optional[Dict]:
    if cp_loss is None or cp_loss < CP_LOSS_MIN:
        return None
    if not board_before.is_capture(opp_move):
        return None
    attacker = board_before.piece_at(opp_move.from_square)
    if not attacker or attacker.piece_type not in _MINOR_MAJOR:
        return None
    # developed (off its home rank) AND active (mobility above the inactive band)
    if opp_move.from_square in _HOME[attacker.color]:
        return None
    if len(board_before.attacks(opp_move.from_square)) < ACTIVE_MOBILITY_MIN:
        return None
    # must be a TRADE: the opp's piece is recaptured on the same square next ply.
    if not pv_after_played:
        return None
    after = board_before.copy()
    after.push(opp_move)
    try:
        recap = after.parse_san(pv_after_played[0])
    except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
        return None
    if recap.to_square != opp_move.to_square:
        return None  # not a recapture of the opp's piece → free grab / different idea, not V3

    return {
        "piece": _PIECE_NAME.get(attacker.piece_type, "piece"),
        "move_san": board_before.san(opp_move),
        "recapture_san": pv_after_played[0],
        "square": chess.square_name(opp_move.to_square),
    }


def clause_for(v3: Dict) -> str:
    """1200-friendly opp-failure clause (the 'why'). Names the trade + the reply."""
    return (f"it trades off their active {v3['piece']} — take back with "
            f"{v3['recapture_san']} and you're left with the better pieces")
