"""
Opponent Threat Detector — retro-fits the missing `threat` field on
existing opponent moves in stockfish_analysis.opponent_move_evaluations.

Why this exists:
  * The analyzer stores a `threat` field on opponent moves but rarely
    populates it — across the corpus it's null for ~all moves.
  * That means the Move Observations deriver's `opponent_previous.created_threat`
    is null for ~all moves, so `responded_to_threat` and
    `ignored_opponent_threat` sit at 0 across all 15,301 of Mohit's obs.
  * Fixing this in the analyzer is a longer job. This module gives us a
    fast retro-fit: compute threat squares from the FEN + move using
    python-chess, then store as `derived_threats: [<square>, ...]`.

Threat detection rules (v1):
  A move creates a threat if AFTER the move, the moving piece attacks
  a target piece that is:
    - a higher-value piece (weaker piece attacking stronger), OR
    - undefended (opponent could take it "for free"), OR
    - forkable — same move attacks 2+ pieces of value

Pieces valued (simple): P=1, N=3, B=3, R=5, Q=9, K=100.

Output: list of {square, attacked_piece, threat_type, is_free}.

Usage:
    from services.opponent_threat_detector import detect_threats
    threats = detect_threats(fen_before, opp_move_uci)
    # returns [] or [{'square': 'e5', 'piece': 'N', 'type': 'attack',
    #                 'is_free': True, 'defender_count': 0}, ...]
"""
from typing import List, Dict, Optional
try:
    import chess
    _CHESS_AVAILABLE = True
except ImportError:
    _CHESS_AVAILABLE = False

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
} if _CHESS_AVAILABLE else {}


def _piece_symbol(piece_type: int) -> str:
    return {1: "P", 2: "N", 3: "B", 4: "R", 5: "Q", 6: "K"}.get(piece_type, "?")


def detect_threats(fen_before: str, move_uci: str) -> List[Dict]:
    """Detect threats created by a move.

    Returns a list of threat dicts. Empty list = no threat detected.
    """
    if not _CHESS_AVAILABLE:
        return []
    if not fen_before or not move_uci:
        return []

    try:
        board = chess.Board(fen_before)
        move = chess.Move.from_uci(move_uci)
        if move not in board.legal_moves:
            return []
    except Exception:
        return []

    # Apply the move
    moving_side = board.turn
    moving_piece_type = None
    piece_at_from = board.piece_at(move.from_square)
    if piece_at_from:
        moving_piece_type = piece_at_from.piece_type

    board.push(move)
    # Now it's the OTHER side's turn. The threats we're detecting are
    # from `moving_side` (the side that just played) attacking `not moving_side`.
    # The moving piece is now on move.to_square.

    threats: List[Dict] = []
    moving_from_sq = move.to_square

    # Get all squares the moving piece now attacks
    attacked_squares = board.attacks(moving_from_sq)

    for target_sq in attacked_squares:
        target_piece = board.piece_at(target_sq)
        if not target_piece:
            continue
        if target_piece.color == moving_side:
            continue  # same color, not a threat

        target_value = PIECE_VALUES.get(target_piece.piece_type, 0)
        moving_value = PIECE_VALUES.get(moving_piece_type, 0) if moving_piece_type else 0

        # Count defenders of the target square (opposite color pieces that attack it)
        defenders = board.attackers(target_piece.color, target_sq)
        defender_count = len(defenders)

        # Threat classification
        is_free = defender_count == 0
        is_undervalue_attack = target_value > moving_value  # attacker cheaper than target
        is_check = target_piece.piece_type == chess.KING

        threat_type = None
        if is_check:
            threat_type = "check"
        elif is_free:
            threat_type = "free_piece"
        elif is_undervalue_attack:
            threat_type = "undervalue_attack"
        else:
            continue  # equal-value trade — not a "threat" that requires response

        threats.append({
            "square": chess.square_name(target_sq),
            "piece": _piece_symbol(target_piece.piece_type),
            "type": threat_type,
            "is_free": is_free,
            "defender_count": defender_count,
            "target_value": target_value,
            "attacker_value": moving_value,
        })

    # Fork detection — if 2+ threats on non-check pieces, it's a fork
    non_check_threats = [t for t in threats if t["type"] != "check"]
    if len(non_check_threats) >= 2:
        for t in non_check_threats:
            t["is_fork_component"] = True

    return threats
