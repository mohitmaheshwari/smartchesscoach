"""
Pattern evidence — structured board geometry per pattern so the frontend
can render visual proof of "you exposed your king" / "you hung a piece"
on a mini board with highlights + arrows.

Called once per game alongside Truth + Player + Plan. The output drops
into game_analyses.pattern_evidence and is surfaced in the V5 endpoint.

Schema:
    {
        "pattern": "king_safety" | "piece_safety" | ...,
        "fen": "rnbq...",                  # position to render
        "move_number": int,
        "highlighted_squares": ["g8","g7","h7"],
        "arrows": [{"from":"g5","to":"g8"}, ...],
        "caption": "Their bishop on g5 was pointed at your king.",
    }
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

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


def _square(s: int) -> str:
    return chess.square_name(s)


# ── King-safety evidence ─────────────────────────────────────────────

def _king_safety_evidence(board: chess.Board, user_color: str) -> Optional[Dict]:
    """Find the user's king + exposed zone + enemy pieces attacking it."""
    user_cc = chess.WHITE if user_color == "white" else chess.BLACK
    enemy_cc = not user_cc
    king_sq = board.king(user_cc)
    if king_sq is None:
        return None

    file_k = chess.square_file(king_sq)
    rank_k = chess.square_rank(king_sq)

    exposed_squares: List[str] = []
    threats: List[Tuple[str, str, str]] = []  # (piece, from_sq, to_sq)

    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            f = file_k + df
            r = rank_k + dr
            if not (0 <= f <= 7 and 0 <= r <= 7):
                continue
            sq = chess.square(f, r)
            attackers = list(board.attackers(enemy_cc, sq))
            if attackers and (df, dr) != (0, 0):
                exposed_squares.append(_square(sq))
            for atk_sq in attackers:
                p = board.piece_at(atk_sq)
                if p:
                    threats.append((_piece_name(p), _square(atk_sq), _square(sq)))

    # Dedupe threats by (piece, from_square) — one arrow per attacker, drawn to the king.
    seen = set()
    arrows = []
    threat_descriptions = []
    for piece, from_sq, _to_sq in threats:
        key = (piece, from_sq)
        if key in seen:
            continue
        seen.add(key)
        arrows.append({"from": from_sq, "to": _square(king_sq)})
        threat_descriptions.append((piece, from_sq))

    if not threat_descriptions:
        return None

    # Caption — coach voice, name pieces and squares.
    if len(threat_descriptions) == 1:
        p, s = threat_descriptions[0]
        caption = f"Their {p} on {s} was pointed at your king."
    elif len(threat_descriptions) == 2:
        (p1, s1), (p2, s2) = threat_descriptions[:2]
        caption = f"Their {p1} on {s1} and {p2} on {s2} were both pointed at your king."
    else:
        caption = f"They had {len(threat_descriptions)} pieces aimed at your king."

    return {
        "pattern": "king_safety",
        "highlighted_squares": list(dict.fromkeys(exposed_squares + [_square(king_sq)])),
        "arrows": arrows,
        "caption": caption,
    }


# ── Piece-safety evidence ────────────────────────────────────────────

def _piece_safety_evidence(
    board: chess.Board, user_color: str
) -> Optional[Dict]:
    """Find the user's hanging piece (most valuable hanging non-king)."""
    user_cc = chess.WHITE if user_color == "white" else chess.BLACK
    enemy_cc = not user_cc

    value = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
             chess.ROOK: 5, chess.QUEEN: 9}

    candidates: List[Tuple[int, int, chess.Piece]] = []
    for sq, piece in board.piece_map().items():
        if piece.color != user_cc:
            continue
        if piece.piece_type == chess.KING:
            continue
        attackers = list(board.attackers(enemy_cc, sq))
        defenders = list(board.attackers(user_cc, sq))
        if attackers and len(attackers) > len(defenders):
            candidates.append((value.get(piece.piece_type, 0), sq, piece))

    if not candidates:
        return None
    candidates.sort(key=lambda c: -c[0])
    _v, hung_sq, hung_piece = candidates[0]
    attacker_sqs = list(board.attackers(enemy_cc, hung_sq))
    if not attacker_sqs:
        return None

    # Pick cheapest attacker for arrow.
    cheapest_sq = min(attacker_sqs, key=lambda s: value.get((board.piece_at(s) or chess.Piece(chess.PAWN, enemy_cc)).piece_type, 99))
    cheapest = board.piece_at(cheapest_sq)

    return {
        "pattern": "piece_safety",
        "highlighted_squares": [_square(hung_sq)],
        "arrows": [{"from": _square(cheapest_sq), "to": _square(hung_sq)}],
        "caption": (
            f"Your {_piece_name(hung_piece)} on {_square(hung_sq)} was hanging — "
            f"their {_piece_name(cheapest)} on {_square(cheapest_sq)} could take it for free."
        ),
    }


# ── Public API ───────────────────────────────────────────────────────

# Map cognitive_gap → evidence extractor. Patterns not in this map fall
# through to a generic "show the position" evidence with no overlay.
_PATTERN_TO_EXTRACTOR = {
    "king_safety": _king_safety_evidence,
    "ignore_threat": _king_safety_evidence,  # threat-awareness near king is similar
    "piece_safety": _piece_safety_evidence,
    "one_move_blunder": _piece_safety_evidence,
}


def extract_pattern_evidence(
    decryption_v5_data: List[Dict],
    user_color: str,
    critical_move_number: Optional[int] = None,
    critical_gap: Optional[str] = None,
) -> Optional[Dict]:
    """Extract structured evidence for the game's decisive pattern.

    Picks the FEN of the critical move (or largest-cp-loss user mistake
    as fallback), then applies the pattern-specific extractor. Returns
    None when the pattern doesn't have a registered extractor or the
    geometry is empty.
    """
    if not decryption_v5_data:
        return None

    # Locate the target move by number, falling back to biggest user mistake.
    target = None
    if critical_move_number is not None:
        for m in decryption_v5_data:
            if (m.get("is_user_move")
                    and m.get("move_number") == critical_move_number):
                target = m
                break
    if not target:
        candidates = [
            m for m in decryption_v5_data
            if m.get("is_user_move") and m.get("is_mistake")
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda m: -(m.get("cp_loss") or 0))
        target = candidates[0]

    fen = target.get("fen_before") or target.get("fen_after")
    if not fen:
        return None

    try:
        board = chess.Board(fen)
    except Exception as e:
        logger.warning(f"[pattern_evidence] FEN parse failed: {e}")
        return None

    pattern_key = ((critical_gap or "")
                   or (target.get("cognitive_gap") or "")
                   or "").strip().lower()

    extractor = _PATTERN_TO_EXTRACTOR.get(pattern_key)
    if not extractor:
        return None

    ev = extractor(board, user_color)
    if not ev:
        return None

    ev["fen"] = fen
    ev["move_number"] = target.get("move_number")
    return ev
