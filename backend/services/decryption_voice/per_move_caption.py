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


def _is_check_san(move_san: str) -> bool:
    """SAN ends in '+' (check) or '#' (mate), ignoring annotation marks."""
    s = move_san.rstrip("!?")
    return s.endswith("+") or s.endswith("#")


def _is_mate_san(move_san: str) -> bool:
    return move_san.rstrip("!?").endswith("#")


def _check_tail(move_san: str, is_user_move: bool) -> str:
    """Returns ' Check!' / ' Checkmate!' / '' to append to a base caption."""
    if _is_mate_san(move_san):
        return " Checkmate!"
    if _is_check_san(move_san):
        return " Check!" if is_user_move else " Check."
    return ""


def _castle_caption(move_san: str, is_user_move: bool) -> Optional[str]:
    if move_san not in ("O-O", "O-O-O", "O-O+", "O-O-O+", "O-O#", "O-O-O#"):
        return None
    side = "kingside" if move_san.startswith("O-O") and not move_san.startswith("O-O-O") else "queenside"
    if is_user_move:
        base = f"Castled {side}. Your king is safer and your rook joins the game."
    else:
        base = f"They castle {side}, tucking their king and connecting rooks."
    return base + _check_tail(move_san, is_user_move)


def _check_caption(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_san: str,
    is_user_move: bool,
) -> Optional[str]:
    """Caption for a non-capture, non-castling move that gives check or
    delivers mate. Captures are handled by _capture_caption with a check
    tail; castle by _castle_caption. Catches the queen/rook check moves
    that flooded good_generic in the audit (~1,560 hits)."""
    if not _is_check_san(move_san):
        return None
    if board_before.is_capture(move):
        return None
    if move_san.startswith("O-O"):
        return None
    piece_name = _PIECE_NAME.get(moving_piece.piece_type, "piece")
    sq_name = chess.square_name(move.to_square)
    if _is_mate_san(move_san):
        if is_user_move:
            return f"Checkmate! {piece_name.capitalize()} to {sq_name} — game over."
        return f"They mate with the {piece_name} on {sq_name}."
    # Plain check
    if is_user_move:
        return f"{piece_name.capitalize()} to {sq_name} — check. Forces them to respond."
    return f"Check from the {piece_name} on {sq_name}. You must address it first."


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
    move_san: str = "",
) -> Optional[str]:
    if not board_before.is_capture(move):
        return None
    sq_name = chess.square_name(move.to_square)
    tail = _check_tail(move_san, is_user_move)
    # Mate trumps material talk — a mating sacrifice is good regardless
    # of piece value. Short-circuit to a clean caption.
    if _is_mate_san(move_san):
        captured = board_before.piece_at(move.to_square)
        captured_name = _PIECE_NAME.get(captured.piece_type, "piece") if captured else "piece"
        if is_user_move:
            return f"Takes the {captured_name} on {sq_name}. Checkmate!"
        return f"They take the {captured_name} on {sq_name}. Checkmate."
    if board_before.is_en_passant(move):
        base = (
            f"Takes the pawn en passant on {sq_name}."
            if is_user_move
            else f"They take the pawn en passant on {sq_name}."
        )
        return base + tail
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
            base = f"Takes the {captured_name} on {sq_name}. Nothing recaptures, so it's free."
        elif captured_value > moving_value:
            base = f"Takes the {captured_name} on {sq_name}. You win material — {captured_name} for {moving_name}."
        elif captured_value == moving_value:
            base = f"Takes the {captured_name} on {sq_name}. Equal trade."
        else:
            base = f"Takes the {captured_name} on {sq_name}, but you lose more than you win."
        return base + tail
    # opp's capture
    if not enemy_attackers:
        return f"They take the {captured_name} on {sq_name} for free." + tail
    if captured_value > moving_value:
        return f"They take the {captured_name} on {sq_name} — wins material." + tail
    if captured_value == moving_value:
        return f"They take the {captured_name} on {sq_name}. Equal trade." + tail
    return f"They take the {captured_name} on {sq_name}, but lose more than they win." + tail


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

    # Capture handles its own check tail; check_caption handles all other
    # check moves (queen / rook / minor giving check without capturing).
    cap = _capture_caption(board_before, move, moving_piece, is_user_move, move_san)
    if cap:
        return CaptionResult(cap, "good_capture", 0.95)

    cap = _check_caption(board_before, move, moving_piece, move_san, is_user_move)
    if cap:
        return CaptionResult(cap, "good_check", 0.95)

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


# ── Engine-preference interpreter ────────────────────────────────────
# Replaces the "The engine prefers X here." fallback with a richer
# descriptive caption. We compare the played move and the engine's best
# along several axes (capture / check / castle / same-piece-different-
# square / different-piece) and produce the most specific honest
# comparison. Doesn't claim to know WHY — just describes the difference.

def _strip_san_ann(san: str) -> str:
    """Drop annotation marks (!?+#) for shape comparisons."""
    return san.rstrip("!?").rstrip("+#")


def _interpret_engine_preference(
    *,
    fen_before: str,
    played_san: str,
    best_san: str,
    is_user_move: bool,
) -> Optional[str]:
    """Produce a richer caption when engine_fallback would fire.
    Returns None if no comparative interpretation applies (caller
    falls back to the generic 'engine prefers X' line)."""
    if not best_san or not played_san:
        return None
    try:
        board = chess.Board(fen_before)
        played_move = board.parse_san(played_san)
        best_move = board.parse_san(best_san)
    except Exception:
        return None

    played_piece = board.piece_at(played_move.from_square)
    best_piece = board.piece_at(best_move.from_square)
    if not played_piece or not best_piece:
        return None

    played_is_capture = board.is_capture(played_move)
    best_is_capture = board.is_capture(best_move)
    played_is_check = _is_check_san(played_san)
    best_is_check = _is_check_san(best_san)
    played_is_castle = played_san.startswith("O-O")
    best_is_castle = best_san.startswith("O-O")

    pron = "you" if is_user_move else "they"

    # 1. Engine wanted a CAPTURE the user didn't play
    if best_is_capture and not played_is_capture:
        captured = board.piece_at(best_move.to_square)
        # En passant: piece_at(to) is empty
        if not captured and board.is_en_passant(best_move):
            return f"Engine prefers {best_san} — an en passant capture."
        if captured:
            captured_name = _PIECE_NAME.get(captured.piece_type, "piece")
            return f"Engine prefers {best_san} — wins the {captured_name}."
        return f"Engine prefers {best_san} — a capture."

    # 2. Engine wanted a CHECK the user didn't play
    if best_is_check and not played_is_check:
        return f"Engine prefers {best_san} — a check that forces a response."

    # 3. Engine wanted to CASTLE
    if best_is_castle and not played_is_castle:
        side = "kingside" if "O-O-O" not in best_san else "queenside"
        return f"Engine prefers castling {side} — keeps the king safer."

    # 4. SAME PIECE, different destination square (positional preference)
    if played_piece.piece_type == best_piece.piece_type:
        played_to = chess.square_name(played_move.to_square)
        best_to = chess.square_name(best_move.to_square)
        if played_to != best_to:
            piece_name = _PIECE_NAME.get(played_piece.piece_type, "piece")
            return (
                f"{piece_name.capitalize()} to {played_to} — engine prefers "
                f"{best_san}, a stronger square for the same {piece_name}."
            )

    # 5. DIFFERENT piece type — different idea entirely
    played_name = _PIECE_NAME.get(played_piece.piece_type, "piece")
    best_name = _PIECE_NAME.get(best_piece.piece_type, "piece")
    if played_name == best_name:
        # Fallback when piece types match but our same-square branch missed
        return f"Engine prefers {best_san} over {played_san}."
    return (
        f"Engine prefers {best_san} — switches to a {best_name} move "
        f"instead of the {played_name}."
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
    #    Try the shape-aware interpreter first (capture / check / castle /
    #    same-piece-different-square / different-piece-type) before
    #    falling back to the generic "engine prefers X" line.
    if severity in ("mistake", "blunder", "inaccuracy") and best_move_san:
        interp = _interpret_engine_preference(
            fen_before=fen_before,
            played_san=move_san,
            best_san=best_move_san,
            is_user_move=is_user_move,
        )
        if interp:
            # Distinct source labels make the audit see what's working
            label = "engine_better:capture" if " wins the " in interp or "en passant" in interp else (
                "engine_better:check" if "check" in interp.lower() else (
                "engine_better:castle" if "castling" in interp else (
                "engine_better:same_piece" if "stronger square" in interp else
                "engine_better:different_piece"
            )))
            return CaptionResult(interp, label, 0.6)
        return CaptionResult(
            f"The engine prefers {best_move_san} here.",
            "engine_fallback",
            0.5,
        )

    return None
