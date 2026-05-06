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

def _castle_caption(move_san: str, user_color: chess.Color) -> Optional[str]:
    if move_san not in ("O-O", "O-O-O", "O-O+", "O-O-O+", "O-O#", "O-O-O#"):
        return None
    side = "kingside" if move_san.startswith("O-O") and not move_san.startswith("O-O-O") else "queenside"
    return f"Castled {side}. Your king is now safer and your rook joins the game."


def _development_caption(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
) -> Optional[str]:
    """A piece moves from its starting rank for the first time, in the
    opening or early middlegame, to a square that's reasonable."""
    if move_number > 14:
        return None  # development phase mostly over
    if moving_piece.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return None
    starting_rank = 0 if moving_piece.color == chess.WHITE else 7
    if chess.square_rank(move.from_square) != starting_rank:
        return None  # not from starting rank → not first development
    piece_name = _PIECE_NAME[moving_piece.piece_type]
    to_sq = chess.square_name(move.to_square)
    if moving_piece.piece_type == chess.KNIGHT:
        # Strongest knight squares: f3/c3 (white), f6/c6 (black)
        good_squares = {"f3", "c3", "f6", "c6", "d2", "e2", "d7", "e7"}
        if to_sq in good_squares:
            return f"Develops the knight to {to_sq}. Knights belong in the centre."
        return f"Develops the knight to {to_sq}."
    # Bishop
    return f"Develops the bishop to {to_sq}. Open diagonals are bishop territory."


def _central_pawn_caption(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
) -> Optional[str]:
    """Central pawn push (e4/d4/e5/d5) in the opening."""
    if move_number > 8:
        return None
    if moving_piece.piece_type != chess.PAWN:
        return None
    to_sq = chess.square_name(move.to_square)
    if to_sq not in ("e4", "d4", "e5", "d5", "c4", "c5", "f4", "f5"):
        return None
    return f"Pushes to {to_sq}, claiming central space."


def _capture_caption(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
) -> Optional[str]:
    """Move captures something. Describe the trade."""
    if not board_before.is_capture(move):
        return None
    if board_before.is_en_passant(move):
        return f"Takes the pawn en passant on {chess.square_name(move.to_square)}."
    captured = board_before.piece_at(move.to_square)
    if not captured:
        return None
    captured_name = _PIECE_NAME.get(captured.piece_type, "piece")
    moving_name = _PIECE_NAME.get(moving_piece.piece_type, "piece")
    moving_value = _PIECE_VALUE.get(moving_piece.piece_type, 0)
    captured_value = _PIECE_VALUE.get(captured.piece_type, 0)
    sq_name = chess.square_name(move.to_square)

    # Check if the recapture is good.
    board_after = board_before.copy()
    board_after.push(move)
    enemy_attackers = board_after.attackers(not moving_piece.color, move.to_square)

    if not enemy_attackers:
        return f"Takes the {captured_name} on {sq_name}. Nothing recaptures, so it's a free piece."
    if captured_value > moving_value:
        return f"Takes the {captured_name} on {sq_name}. You win material — {captured_name} for {moving_name}."
    if captured_value == moving_value:
        return f"Takes the {captured_name} on {sq_name}. Equal trade."
    # captured < moving — loses material
    return f"Takes the {captured_name} on {sq_name}, but you lose more than you win."


def _prophylactic_caption(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
) -> Optional[str]:
    """Quiet move that defends a square or piece against an enemy threat.
    Conservative: only fire when the moved piece NOW defends a friendly
    piece that was attacked before the move."""
    if board_before.is_capture(move):
        return None
    user_color = moving_piece.color

    # Find friendly pieces that were attacked before the move and
    # are now defended by the moved piece.
    board_after = board_before.copy()
    board_after.push(move)

    # We need to know what the moving piece NOW attacks (squares it
    # defends if our piece is there). For each square the moved piece
    # attacks on the new board, check if it's a friendly piece that was
    # also under attack.
    new_attacks_from = board_after.attacks(move.to_square)
    for sq in new_attacks_from:
        p = board_after.piece_at(sq)
        if not p or p.color != user_color:
            continue
        # Was this piece attacked before our move and is it still?
        was_attacked = bool(board_before.attackers(not user_color, sq))
        defenders_after = board_after.attackers(user_color, sq)
        if was_attacked and len(defenders_after) >= 1:
            piece_name = _PIECE_NAME.get(p.piece_type, "piece")
            return f"Defends your {piece_name} on {chess.square_name(sq)}."
    return None


def _generic_good_caption(
    moving_piece: chess.Piece,
    move: chess.Move,
) -> str:
    """Last-resort caption for severity = good/best when no specific
    pattern fires. Plain description of what moved where."""
    piece_name = _PIECE_NAME.get(moving_piece.piece_type, "piece")
    to_sq = chess.square_name(move.to_square)
    if moving_piece.piece_type == chess.PAWN:
        return f"Pawn to {to_sq}. Solid move."
    return f"{piece_name.capitalize()} moves to {to_sq}. A reasonable move."


def detect_good_move(
    board_before: chess.Board,
    move_san: str,
    move_number: int,
) -> Optional[CaptionResult]:
    """Run the good-move sub-detectors in order. Returns the first
    caption that fires, else a generic 'reasonable move' line."""
    try:
        move = board_before.parse_san(move_san)
        moving_piece = board_before.piece_at(move.from_square)
        if not moving_piece:
            return None
    except Exception:
        return None

    # Order matters: most specific first.
    cap = _castle_caption(move_san, moving_piece.color)
    if cap:
        return CaptionResult(cap, "good_castle", 0.95)

    cap = _capture_caption(board_before, move, moving_piece)
    if cap:
        return CaptionResult(cap, "good_capture", 0.95)

    cap = _central_pawn_caption(board_before, move, moving_piece, move_number)
    if cap:
        return CaptionResult(cap, "good_central_pawn", 0.9)

    cap = _development_caption(board_before, move, moving_piece, move_number)
    if cap:
        return CaptionResult(cap, "good_development", 0.9)

    cap = _prophylactic_caption(board_before, move, moving_piece)
    if cap:
        return CaptionResult(cap, "good_defend", 0.85)

    return CaptionResult(_generic_good_caption(moving_piece, move), "good_generic", 0.6)


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
        return detect_good_move(board_before, move_san, move_number)

    # 5. Engine fallback for mistake/blunder when nothing specific matched.
    if severity in ("mistake", "blunder", "inaccuracy") and best_move_san:
        return CaptionResult(
            f"The engine prefers {best_move_san} here.",
            "engine_fallback",
            0.5,
        )

    return None
