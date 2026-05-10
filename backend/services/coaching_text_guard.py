"""
Coaching text guard — runtime validation that an emitted coaching string
does not hallucinate pieces or misattribute colors.

Per `feedback_chess_content_verification.md`: every coaching surface that
emits user-visible chess claims must verify those claims against the
actual FEN before render. This module is the production-time guard.
The same logic powers `scripts/content_correctness_audit.py` Phase 1 —
audit catches them post-hoc; this guard prevents them from ever
reaching a user.

Usage:
    from services.coaching_text_guard import verify_coaching_text

    issues = verify_coaching_text(text, fen, user_color="white")
    if issues:
        # text has hallucinated/wrong-color claims — fall back to a
        # safer template, regenerate, or suppress.
        text = safe_fallback()

Catches:
  - "your X on Y" / "the X on Y" with no piece on Y
  - "your X on Y" with wrong piece type on Y
  - "your X on Y" with X belonging to the wrong colour
  - Same checks for opponent ("their", "opponent's")

Doesn't catch (those are different verifiers):
  - Severity miscalibration (use forced-mate detection in classifier)
  - Calculation depth (use deeper engine for tactical claims)
  - Vacuous coaching (use vacuous-text detector)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

import chess


@dataclass
class GuardIssue:
    """One issue found in a coaching string."""
    kind: str          # "missing_piece" | "wrong_piece_type" | "wrong_color"
    text: str          # the substring that failed
    detail: str        # human-readable explanation


_PIECE_NAMES = {
    "king": chess.KING,
    "queen": chess.QUEEN,
    "rook": chess.ROOK,
    "bishop": chess.BISHOP,
    "knight": chess.KNIGHT,
    "pawn": chess.PAWN,
}


_PIECE_ON_SQUARE_RE = re.compile(
    r"\b(?:(your|their|my|opponent[’\']?s|the|a|an)\s+)?"
    r"(king|queen|rook|bishop|knight|pawn)"
    r"\s+on\s+"
    r"([a-h][1-8])\b",
    flags=re.IGNORECASE,
)


def verify_coaching_text(
    text: str,
    fen: str,
    user_color: str = "white",
) -> List[GuardIssue]:
    """Return a list of issues — each one a hallucination or wrong-color
    claim. Empty list = clean.

    fen is the position the coaching is about. user_color is "white" or
    "black" — used to interpret "your" / "their".
    """
    if not text or not fen:
        return []
    try:
        board = chess.Board(fen)
    except ValueError:
        return []

    color = chess.WHITE if user_color.lower() == "white" else chess.BLACK
    issues: List[GuardIssue] = []

    for match in _PIECE_ON_SQUARE_RE.finditer(text):
        side_word = match.group(1)
        piece_name = match.group(2).lower()
        square_name = match.group(3).lower()

        try:
            sq = chess.parse_square(square_name)
        except Exception:
            continue

        piece = board.piece_at(sq)
        if piece is None:
            issues.append(GuardIssue(
                kind="missing_piece",
                text=match.group(0),
                detail=f"no piece on {square_name} — claim is hallucinated",
            ))
            continue

        expected_type = _PIECE_NAMES[piece_name]
        if piece.piece_type != expected_type:
            actual = chess.piece_name(piece.piece_type)
            issues.append(GuardIssue(
                kind="wrong_piece_type",
                text=match.group(0),
                detail=f"square {square_name} has a {actual}, not a {piece_name}",
            ))
            continue

        if side_word:
            sw = side_word.lower().rstrip("'s").replace("'", "").replace("’", "")
            if sw in ("your", "my"):
                expected_color = color
            elif sw in ("their", "opponents", "opponent"):
                expected_color = not color
            else:
                expected_color = None
            if expected_color is not None and piece.color != expected_color:
                actual_side = "white" if piece.color == chess.WHITE else "black"
                issues.append(GuardIssue(
                    kind="wrong_color",
                    text=match.group(0),
                    detail=f"piece on {square_name} is {actual_side}, but text says '{side_word}'",
                ))

    return issues


def is_coaching_text_safe(
    text: str,
    fen: str,
    user_color: str = "white",
) -> bool:
    """Convenience boolean. True iff verify_coaching_text finds no issues."""
    return not verify_coaching_text(text, fen, user_color)
