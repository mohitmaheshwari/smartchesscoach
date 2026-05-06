"""
Per-move deterministic caption generator. Replaces V5 narrative as the
source of move-by-move analysis text on the game-analysis page.

Architecture:
  - For each move in a game, run a sequence of detectors.
  - The first detector that fires returns a caption + source label.
  - If nothing fires, return None (analysis page shows nothing for that
    move — honest "no comment" beats misleading text).

ZERO LLM at runtime. Every word in every caption comes from python-chess
geometry or template constants. Same principle as concept_dispatcher.

Detector order (high → low specificity):
  1. concept_dispatcher (existing tactical detectors — fork, mate,
     hanging piece, walked-into-attack, combination, etc.). Wins on
     critical moments.
  2. opening_book (named openings — Caro-Kann, Italian, etc.)
  3. good_move sub-detectors (castled, developed, captured, recaptured,
     pawn_push, prophylactic). Cover most "good"/"best" severity moves.
  4. endgame_technique (king activation, pawn promotion, holding).
  5. engine_fallback ("The engine prefers X here.") — last resort, only
     for mistake/blunder severity where nothing else matched.

Voice rule: Easy Indian English. Short SVO sentences. Names pieces and
squares from the position only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import chess

logger = logging.getLogger(__name__)


_PIECE_NAME = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

_PIECE_VALUE = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
}


@dataclass
class CaptionResult:
    """One caption for one move."""
    text: str
    source: str          # detector that fired (e.g., "good_castle", "opening:caro_kann")
    confidence: float    # 0-1, mostly diagnostic


# ── Good-move detectors ──────────────────────────────────────────────
# These produce captions for moves where severity is good/best/book and
# no specific tactical pattern fires. They describe what the move
# accomplishes structurally — castling to safety, developing a piece,
# pushing a central pawn, etc.

def _pronouns(is_user_move: bool):
    """Returns (subject, possessive, possessive_their_for_target) tuple.

    For user moves: ('You', 'your', 'their') — the user is the actor.
    For opp moves:  ('They', 'their', 'your') — opp is the actor.
    """
    if is_user_move:
        return ("You", "your", "their")
    return ("They", "their", "your")


def _castle_caption(move_san: str, is_user_move: bool) -> Optional[str]:
    if move_san not in ("O-O", "O-O-O", "O-O+", "O-O-O+", "O-O#", "O-O-O#"):
        return None
    side = "kingside" if move_san.startswith("O-O") and not move_san.startswith("O-O-O") else "queenside"
    if is_user_move:
        return f"Castled {side}. Your king is safer and your rook joins the game."
    return f"They castle {side}, tucking their king and connecting rooks."


def _development_caption(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[str]:
    """A piece moves from its starting rank for the first time, in the
    opening or early middlegame, to a square that's reasonable."""
    if move_number > 14:
        return None  # development phase mostly over
    if moving_piece.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return None
    starting_rank = 0 if moving_piece.color == chess.WHITE else 7
    if chess.square_rank(move.from_square) != starting_rank:
        return None
    to_sq = chess.square_name(move.to_square)
    subject, possessive, _ = _pronouns(is_user_move)
    verb = "Develops" if is_user_move else f"{subject} develop"
    if moving_piece.piece_type == chess.KNIGHT:
        good_squares = {"f3", "c3", "f6", "c6", "d2", "e2", "d7", "e7"}
        if to_sq in good_squares:
            tail = "Knights belong in the centre." if is_user_move else ""
            return (f"{verb} the knight to {to_sq}." + (f" {tail}" if tail else "")).strip()
        return f"{verb} the knight to {to_sq}."
    # Bishop
    tail = "Open diagonals are bishop territory." if is_user_move else ""
    return (f"{verb} the bishop to {to_sq}." + (f" {tail}" if tail else "")).strip()


def _central_pawn_caption(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[str]:
    if move_number > 8:
        return None
    if moving_piece.piece_type != chess.PAWN:
        return None
    to_sq = chess.square_name(move.to_square)
    if to_sq not in ("e4", "d4", "e5", "d5", "c4", "c5", "f4", "f5"):
        return None
    if is_user_move:
        return f"Pushes to {to_sq}, claiming central space."
    return f"They push to {to_sq}, grabbing central space."


def _capture_caption(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    is_user_move: bool,
) -> Optional[str]:
    if not board_before.is_capture(move):
        return None
    sq_name = chess.square_name(move.to_square)
    if board_before.is_en_passant(move):
        return (
            f"Takes the pawn en passant on {sq_name}."
            if is_user_move
            else f"They take the pawn en passant on {sq_name}."
        )
    captured = board_before.piece_at(move.to_square)
    if not captured:
        return None
    captured_name = _PIECE_NAME.get(captured.piece_type, "piece")
    moving_name = _PIECE_NAME.get(moving_piece.piece_type, "piece")
    moving_value = _PIECE_VALUE.get(moving_piece.piece_type, 0)
    captured_value = _PIECE_VALUE.get(captured.piece_type, 0)

    board_after = board_before.copy()
    board_after.push(move)
    enemy_attackers = board_after.attackers(not moving_piece.color, move.to_square)

    if is_user_move:
        if not enemy_attackers:
            return f"Takes the {captured_name} on {sq_name}. Nothing recaptures, so it's free."
        if captured_value > moving_value:
            return f"Takes the {captured_name} on {sq_name}. You win material — {captured_name} for {moving_name}."
        if captured_value == moving_value:
            return f"Takes the {captured_name} on {sq_name}. Equal trade."
        return f"Takes the {captured_name} on {sq_name}, but you lose more than you win."
    # opp's capture
    if not enemy_attackers:
        return f"They take the {captured_name} on {sq_name} for free."
    if captured_value > moving_value:
        return f"They take the {captured_name} on {sq_name} — wins material."
    if captured_value == moving_value:
        return f"They take the {captured_name} on {sq_name}. Equal trade."
    return f"They take the {captured_name} on {sq_name}, but lose more than they win."


def _prophylactic_caption(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    is_user_move: bool,
) -> Optional[str]:
    """Quiet move that defends a friendly piece that was previously attacked."""
    if board_before.is_capture(move):
        return None
    user_color = moving_piece.color
    board_after = board_before.copy()
    board_after.push(move)

    new_attacks_from = board_after.attacks(move.to_square)
    for sq in new_attacks_from:
        p = board_after.piece_at(sq)
        if not p or p.color != user_color:
            continue
        was_attacked = bool(board_before.attackers(not user_color, sq))
        defenders_after = board_after.attackers(user_color, sq)
        if was_attacked and len(defenders_after) >= 1:
            piece_name = _PIECE_NAME.get(p.piece_type, "piece")
            sq_name = chess.square_name(sq)
            if is_user_move:
                return f"Defends your {piece_name} on {sq_name}."
            return f"They defend their {piece_name} on {sq_name}."
    return None


def _generic_good_caption(
    moving_piece: chess.Piece,
    move: chess.Move,
    move_number: int,
    is_user_move: bool,
) -> str:
    piece_name = _PIECE_NAME.get(moving_piece.piece_type, "piece")
    to_sq = chess.square_name(move.to_square)
    # Phase-aware fallback
    in_opening = move_number <= 12
    in_endgame_phase = move_number >= 30
    if not is_user_move:
        if moving_piece.piece_type == chess.PAWN:
            return f"They push the pawn to {to_sq}."
        return f"They move the {piece_name} to {to_sq}."
    # User move
    if moving_piece.piece_type == chess.PAWN:
        if in_opening:
            return f"Pawn to {to_sq}. Holds the structure."
        if in_endgame_phase:
            return f"Pawn to {to_sq}. Pawn moves matter in the endgame."
        return f"Pawn to {to_sq}. Solid."
    if in_opening:
        return f"{piece_name.capitalize()} to {to_sq}. Reasonable opening move."
    if in_endgame_phase:
        return f"{piece_name.capitalize()} to {to_sq}. Keeps the position under control."
    return f"{piece_name.capitalize()} to {to_sq}. Reasonable."


def detect_good_move(
    board_before: chess.Board,
    move_san: str,
    move_number: int,
    is_user_move: bool = True,
) -> Optional[CaptionResult]:
    """Run the good-move sub-detectors in order. Returns the first
    caption that fires, else a generic 'reasonable move' line.
    Pronouns adjust automatically based on is_user_move."""
    try:
        move = board_before.parse_san(move_san)
        moving_piece = board_before.piece_at(move.from_square)
        if not moving_piece:
            return None
    except Exception:
        return None

    cap = _castle_caption(move_san, is_user_move)
    if cap:
        return CaptionResult(cap, "good_castle", 0.95)

    cap = _capture_caption(board_before, move, moving_piece, is_user_move)
    if cap:
        return CaptionResult(cap, "good_capture", 0.95)

    cap = _central_pawn_caption(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return CaptionResult(cap, "good_central_pawn", 0.9)

    cap = _development_caption(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return CaptionResult(cap, "good_development", 0.9)

    # Middlegame patterns — knight outpost, rook on open file, rook 7th,
    # pawn break, prophylactic king tuck. Tries each in order.
    try:
        from .middlegame_patterns import detect_middlegame_pattern
        mg = detect_middlegame_pattern(board_before, move, moving_piece, move_number, is_user_move)
        if mg:
            return CaptionResult(mg["caption"], f"middlegame:{mg['name']}", 0.9)
    except Exception as e:
        logger.warning(f"[per_move_caption] middlegame_patterns failed: {e}")

    cap = _prophylactic_caption(board_before, move, moving_piece, is_user_move)
    if cap:
        return CaptionResult(cap, "good_defend", 0.85)

    return CaptionResult(
        _generic_good_caption(moving_piece, move, move_number, is_user_move),
        "good_generic",
        0.6,
    )


# ── Public API ───────────────────────────────────────────────────────

def caption_for_move(
    *,
    fen_before: str,
    move_san: str,
    move_number: int,
    severity: Optional[str] = None,
    best_move_san: Optional[str] = None,
    pv_after_best: Optional[List[str]] = None,
    pv_after_played: Optional[List[str]] = None,
    user_color: Optional[str] = None,
    is_user_move: bool = True,
    move_history_san: Optional[List[str]] = None,
) -> Optional[CaptionResult]:
    """Return a deterministic caption for one move, or None.

    Pipeline:
      1. concept_dispatcher (tactical / strategic patterns) — wins for
         critical moments.
      2. opening_book — early in game, named opening recognition.
      3. endgame_technique — late in game.
      4. good_move sub-detectors — when severity is good/best.
      5. engine_fallback — last resort for mistake/blunder severity.

    severity values: 'good', 'best', 'inaccuracy', 'mistake', 'blunder',
    'context'. Used to gate which detectors fire.
    """
    if not fen_before or not move_san:
        return None
    try:
        board_before = chess.Board(fen_before)
    except Exception:
        return None

    # 1. Concept dispatcher — runs the existing tactical/strategic
    #    detectors. Wins for critical moments (the 4 turning-point
    #    moments per game and any other position with a clear pattern).
    if is_user_move and severity in ("mistake", "blunder", "inaccuracy") and best_move_san:
        try:
            from .concept_dispatcher import caption_for_moment
            cap, meta = caption_for_moment(
                fen_before=fen_before,
                user_move_san=move_san,
                best_move_san=best_move_san,
                pv_after_best=pv_after_best,
                pv_after_played=pv_after_played,
                user_color=user_color,
            )
            if cap and meta:
                pattern = (meta or {}).get("pattern_type") or "concept"
                return CaptionResult(cap, f"template:{pattern}", 0.95)
        except Exception as e:
            logger.warning(f"[per_move_caption] dispatcher failed: {e}")

    # 2. Opening book recognition (early in game). Needs the prior move
    # sequence — chess.Board(fen) loses the move_stack, so the caller
    # must pass move_history_san explicitly. If absent, opening
    # detection is skipped.
    if move_number <= 12 and move_history_san is not None:
        try:
            from .opening_book import recognize_opening_from_history
            full_history = list(move_history_san) + [move_san]
            ob = recognize_opening_from_history(full_history)
            if ob:
                return CaptionResult(ob["caption"], f"opening:{ob['name']}", 0.9)
        except Exception as e:
            logger.warning(f"[per_move_caption] opening_book failed: {e}")

    # 3. Endgame technique (low piece count)
    piece_count = sum(1 for sq in chess.SQUARES if board_before.piece_at(sq))
    if piece_count <= 14:
        try:
            from .endgame_technique import detect_endgame_technique
            eg = detect_endgame_technique(board_before, move_san, user_color or "white")
            if eg:
                return CaptionResult(eg["caption"], f"endgame:{eg['name']}", 0.85)
        except Exception as e:
            logger.warning(f"[per_move_caption] endgame_technique failed: {e}")

    # 4. Good-move sub-detectors (for positive severity)
    if severity in ("good", "best", "book") or severity is None:
        return detect_good_move(board_before, move_san, move_number, is_user_move)

    # 5. Engine fallback for mistake/blunder when nothing specific matched.
    if severity in ("mistake", "blunder", "inaccuracy") and best_move_san:
        return CaptionResult(
            f"The engine prefers {best_move_san} here.",
            "engine_fallback",
            0.5,
        )

    return None
