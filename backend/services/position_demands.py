"""
Position Demands — what principle does THIS position need right now?

The coaching pipeline used to compare move shapes (move_category of played vs
best) and declare PRINCIPLE_MISS based on that. That's position-blind — the
same move (e.g. a3) is genius prophylaxis in one position and lazy in another.

This module fixes that. Given a board, it scores each principle by urgency:
how much does THIS position demand this principle right now?

The principle with the highest urgency is the "dominant demand." The critique
layer then asks: did the played move serve the dominant demand?

Urgency scoring is DERIVED from board signals (piece counts, king safety,
hanging pieces), not hardcoded thresholds. That means the verdict emerges from
the position itself:

  After 1.e4 e5:
    DEVELOPMENT urgency = 4/4 minors on back rank → 0.9
    → a3 doesn't serve it → PRINCIPLE_MISS

  Ruy Lopez move 9 (both sides developed, castled):
    DEVELOPMENT urgency = 0/4 minors home → 0.0
    → a3/h3 doesn't get flagged on development grounds

Each demand returns a urgency in [0.0, 1.0] and a human-readable evidence string
the render layer can weave into the coaching message.
"""

import chess
from dataclasses import dataclass
from typing import List, Optional

from services.move_critique import Principle


@dataclass
class Demand:
    principle: Principle
    urgency: float       # 0.0 – 1.0; >= 0.4 is "worth teaching about"
    evidence: str        # natural-language reason the principle applies here


# ─────────────────────────────────────────────────────────────────────────────
# Per-principle scorers
# ─────────────────────────────────────────────────────────────────────────────

def _score_development(board: chess.Board) -> Demand:
    """Urgency of developing minor pieces.

    Scales with (a) how many minors are still on the back rank, (b) how early
    we still are in the game. Decays to 0 by move 15 — development stops being
    the dominant demand once pieces are out.
    """
    to_move = board.turn
    move_number = board.fullmove_number

    knight_home = {chess.B1, chess.G1} if to_move == chess.WHITE else {chess.B8, chess.G8}
    bishop_home = {chess.C1, chess.F1} if to_move == chess.WHITE else {chess.C8, chess.F8}

    undeveloped = 0
    for sq in knight_home:
        p = board.piece_at(sq)
        if p and p.color == to_move and p.piece_type == chess.KNIGHT:
            undeveloped += 1
    for sq in bishop_home:
        p = board.piece_at(sq)
        if p and p.color == to_move and p.piece_type == chess.BISHOP:
            undeveloped += 1

    # Base urgency: fraction of minors still home
    base = undeveloped / 4.0
    # Time decay: from 1.0 at move 1 down to 0 at move 15
    time_factor = max(0.0, 1.0 - move_number / 15.0)
    urgency = base * time_factor

    evidence = (
        f"{undeveloped}/4 minor pieces still on the back rank (move {move_number})"
        if undeveloped else f"all minors developed (move {move_number})"
    )
    return Demand(Principle.DEVELOPMENT, urgency, evidence)


def _score_king_safety(board: chess.Board) -> Demand:
    """Urgency of king safety (castling / defending).

    Ramps up with: (a) not castled past move 6, (b) attackers near the king.
    Stays low if king is castled AND nothing threatens it.
    """
    to_move = board.turn
    move_number = board.fullmove_number
    king_sq = board.king(to_move)
    if king_sq is None:
        return Demand(Principle.KING_SAFETY, 0.0, "no king on board")

    castled_squares = (
        {chess.G1, chess.C1} if to_move == chess.WHITE else {chess.G8, chess.C8}
    )
    is_castled = king_sq in castled_squares

    # Count enemy attackers on squares adjacent (one step) to the king
    kf, kr = chess.square_file(king_sq), chess.square_rank(king_sq)
    attacker_count = 0
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if df == 0 and dr == 0:
                continue
            nf, nr = kf + df, kr + dr
            if 0 <= nf <= 7 and 0 <= nr <= 7:
                if board.is_attacked_by(not to_move, chess.square(nf, nr)):
                    attacker_count += 1

    # Too early to castle — not urgent yet
    if move_number < 6:
        return Demand(
            Principle.KING_SAFETY, 0.15,
            f"king still fine (move {move_number}, castling prep later)"
        )

    if is_castled:
        # Castled king — only urgent if actively under attack
        urgency = min(attacker_count / 6.0, 0.6)
        evidence = (
            f"castled; {attacker_count} squares near king under attack"
            if attacker_count else "castled, king is safe"
        )
        return Demand(Principle.KING_SAFETY, urgency, evidence)

    # Uncastled middlegame — this is the meat of king-safety urgency
    move_pressure = min((move_number - 5) / 10.0, 1.0)
    attack_pressure = min(attacker_count / 4.0, 1.0)
    urgency = min(0.3 + move_pressure * 0.4 + attack_pressure * 0.3, 1.0)
    evidence = (
        f"uncastled on move {move_number}, {attacker_count} attackers near king"
    )
    return Demand(Principle.KING_SAFETY, urgency, evidence)


def _score_central_control(board: chess.Board) -> Demand:
    """Urgency of fighting for the center.

    Matters in the opening; drops off after move 15. Higher when the opponent
    has more central control than we do.
    """
    to_move = board.turn
    move_number = board.fullmove_number

    center = [chess.D4, chess.E4, chess.D5, chess.E5]
    ours = sum(1 for sq in center if board.is_attacked_by(to_move, sq))
    theirs = sum(1 for sq in center if board.is_attacked_by(not to_move, sq))

    if move_number > 15:
        return Demand(Principle.CENTRAL_CONTROL, 0.1, "past the opening")

    # Urgency from being behind in center, capped
    if theirs > ours:
        urgency = min((theirs - ours) / 3.0, 0.7)
        return Demand(
            Principle.CENTRAL_CONTROL, urgency,
            f"opponent controls more center ({theirs} vs {ours}) on move {move_number}"
        )
    return Demand(
        Principle.CENTRAL_CONTROL, 0.2,
        f"center contested ({ours} vs {theirs})"
    )


def _score_piece_safety(board: chess.Board) -> Demand:
    """Urgency: our non-pawn pieces are attacked with inadequate defense.

    Very high when something's hanging — this demand should dominate.
    """
    to_move = board.turn
    opponent = not to_move
    at_risk = 0
    hanging = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.color != to_move or p.piece_type in (chess.KING, chess.PAWN):
            continue
        atts = list(board.attackers(opponent, sq))
        defs = list(board.attackers(to_move, sq))
        if atts and not defs:
            hanging += 1
        elif len(atts) > len(defs):
            at_risk += 1

    if hanging:
        return Demand(Principle.PIECE_SAFETY, 1.0,
                      f"{hanging} of your pieces hanging (no defender)")
    if at_risk:
        return Demand(Principle.PIECE_SAFETY, 0.6,
                      f"{at_risk} of your pieces underdefended")
    return Demand(Principle.PIECE_SAFETY, 0.0, "all pieces adequately defended")


def _score_opponent_threats(board: chess.Board) -> Demand:
    """Urgency: respond to opponent's concrete threats (checks, captures
    available after opponent's next move)."""
    to_move = board.turn
    opponent = not to_move

    # Does the opponent threaten any of our non-pawn pieces with net-winning capture?
    threatened_value = 0
    piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                    chess.ROOK: 5, chess.QUEEN: 9}
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.color != to_move or p.piece_type == chess.KING:
            continue
        atts = list(board.attackers(opponent, sq))
        defs = list(board.attackers(to_move, sq))
        if not atts:
            continue
        # Simple SEE-like: cheapest attacker vs defenders
        cheapest_att_val = min(
            (piece_values.get(board.piece_at(a).piece_type, 9) for a in atts),
            default=9,
        )
        our_val = piece_values.get(p.piece_type, 0)
        if cheapest_att_val < our_val and len(atts) > len(defs):
            threatened_value += our_val - cheapest_att_val

    urgency = min(threatened_value / 9.0, 1.0)
    evidence = (
        f"opponent threatens to win ~{threatened_value} points of material"
        if threatened_value else "no immediate material threats"
    )
    return Demand(Principle.OPPONENT_THREATS, urgency, evidence)


# ─────────────────────────────────────────────────────────────────────────────
# Aggregator
# ─────────────────────────────────────────────────────────────────────────────

def analyze_demands(board: chess.Board) -> List[Demand]:
    """Rank all principles by how much THIS position demands them.

    Returns a list sorted by urgency descending. Top result is the
    "dominant demand" — the principle the position is most asking for.

    Implementation note: this is cheap (pure python-chess, no Stockfish).
    Safe to call on every move.
    """
    demands = [
        _score_piece_safety(board),       # hanging stuff overrides
        _score_opponent_threats(board),   # then threats
        _score_king_safety(board),
        _score_development(board),
        _score_central_control(board),
    ]
    return sorted(demands, key=lambda d: d.urgency, reverse=True)


def dominant_demand(board: chess.Board, min_urgency: float = 0.4) -> Optional[Demand]:
    """Return the top demand if it's urgent enough to teach about, else None."""
    demands = analyze_demands(board)
    if demands and demands[0].urgency >= min_urgency:
        return demands[0]
    return None
