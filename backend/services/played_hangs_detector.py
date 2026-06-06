"""
played_hangs_detector.py — detect when a USER move leaves a piece hanging.

Built 2026-06-06 (overnight). Standalone + fully tested against real flagged
FENs BEFORE wiring into the central caption_facts layer (which has high blast
radius — every caption routes through it). The morning summary carries the
one-spot wiring diff for review.

Failure mode (from bare-caption forensics, ~16 flagged positions): the user
plays a move that leaves one of their own pieces attacked and winnable by the
opponent — either the moved piece itself, or another piece whose defender just
left / whose attacker line just opened.

`detect_played_hangs(board_before, played_move)` returns:
    {"square": "e5", "piece": "knight", "moved_piece": False} | None

Gating (conservative — these are the dials that control misfire):
  - The hung piece must be WINNABLE for the opponent (SEE-lite: attacked, and
    either undefended OR the cheapest attacker is worth less than the piece).
  - The hang must be NEWLY created by this move (not already hanging before) —
    so we don't blame a move for a pre-existing problem.
  - King excluded (that's check/mate logic, not hanging).
"""
from typing import Optional, Dict
import chess

_PIECE_VALUE = {
    chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 100000,
}
_PIECE_NAME = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen",
}


def _winnable(board: chess.Board, sq: int, color: bool) -> bool:
    """Is the `color` piece on `sq` winnable by the opponent? SEE-lite:
    attacked, and (undefended OR cheapest attacker cheaper than the piece)."""
    piece = board.piece_at(sq)
    if not piece or piece.color != color or piece.piece_type == chess.KING:
        return False
    attackers = board.attackers(not color, sq)
    if not attackers:
        return False
    defenders = board.attackers(color, sq)
    if not defenders:
        return True
    piece_val = _PIECE_VALUE[piece.piece_type]
    cheapest_attacker = min(
        _PIECE_VALUE[board.piece_at(a).piece_type] for a in attackers
    )
    # A lower-value attacker means even after recapture the opponent profits.
    return cheapest_attacker < piece_val


def _winnable_squares(board: chess.Board, color: bool) -> Dict[int, chess.Piece]:
    out = {}
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.color == color and p.piece_type != chess.KING and _winnable(board, sq, color):
            out[sq] = p
    return out


def detect_played_hangs(
    board_before: chess.Board,
    played_move: chess.Move,
    cp_loss: Optional[int] = None,
) -> Optional[Dict]:
    """Return the most valuable piece newly left hanging by `played_move`, or None.

    GATES (validated 2026-06-06 against 105 flagged FENs — without these the
    raw detector misfires on recapture pawns, 16 fires/3 low-cpl misfires;
    with them, 6 fires / 0 low-cpl misfires):
      - cp_loss >= 100 : the move must actually be bad (kills even-recapture
        pawns like exd4 cpl=2 that aren't real hangs).
      - hung-piece value >= 0.5 * min(cp_loss, 900) : the hung piece must
        plausibly EXPLAIN the loss (kills "names a minor a3 pawn on a 698-cp
        blunder" — O-O-O case).
    Pass cp_loss to apply the gates; omit it to get raw detection (testing).

    KNOWN LIMITATION (review before shipping): on positions where the loss is
    actually a discovered attack / zwischenzug (e.g. Be4 -> Qf4+), this reports
    "leaves your bishop hanging — no defender", which is simplistic, not the
    precise mechanism. ~2 of 6 gated fires. Consider suppressing when a
    discovered-attack is present (origin-ray-walk) before promoting to primary.
    """
    mover = board_before.turn
    board_after = board_before.copy()
    board_after.push(played_move)

    before = _winnable_squares(board_before, mover)
    after = _winnable_squares(board_after, mover)

    # Newly winnable squares (created by the move).
    newly = {sq: pc for sq, pc in after.items() if sq not in before}
    if not newly:
        return None

    # Pick the most valuable newly-hanging piece.
    best_sq = max(newly, key=lambda s: _PIECE_VALUE[newly[s].piece_type])
    pc = newly[best_sq]
    hung_value = _PIECE_VALUE[pc.piece_type]

    # Apply gates when cp_loss is known.
    if cp_loss is not None:
        if cp_loss < 100:
            return None
        if hung_value < 0.5 * min(cp_loss, 900):
            return None

    return {
        "square": chess.square_name(best_sq),
        "piece": _PIECE_NAME.get(pc.piece_type, "piece"),
        "moved_piece": best_sq == played_move.to_square,
    }


def clause_for(hang: Dict) -> str:
    """The R12 failure-mode clause text (1200-friendly, names the square)."""
    if hang["moved_piece"]:
        return f"it leaves your {hang['piece']} on {hang['square']} hanging — no defender after the move"
    return f"it leaves your {hang['piece']} on {hang['square']} hanging — its defender just moved away"
