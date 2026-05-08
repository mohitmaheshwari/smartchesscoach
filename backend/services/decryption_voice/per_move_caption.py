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
    """Central pawn push in the opening. Coach voice rule: list a
    target only if there's an enemy piece on it. Otherwise lead with
    meaning ('claims the centre', 'fights for the middle') and skip
    the empty-square geometry."""
    if move_number > 8:
        return None
    if moving_piece.piece_type != chess.PAWN:
        return None
    to_sq = chess.square_name(move.to_square)
    if to_sq not in ("e4", "d4", "e5", "d5", "c4", "c5", "f4", "f5"):
        return None
    user_color = moving_piece.color
    direction = 1 if user_color == chess.WHITE else -1
    # Find an enemy piece this pawn now hits diagonally — otherwise
    # don't list anything; the pawn just claims central space.
    b = board_before.copy()
    b.push(move)
    target_pt = None
    target_sq_name = None
    for df in (-1, 1):
        nf = chess.square_file(move.to_square) + df
        nr = chess.square_rank(move.to_square) + direction
        if 0 <= nf <= 7 and 0 <= nr <= 7:
            sq = chess.square(nf, nr)
            p = b.piece_at(sq)
            if p and p.color != user_color and p.piece_type != chess.PAWN:
                target_pt = p.piece_type
                target_sq_name = chess.square_name(sq)
                break
    if target_pt is not None:
        target_name = _PIECE_NAME.get(target_pt, "piece")
        if is_user_move:
            return (
                f"Pushes to {to_sq} — claims the centre and hits "
                f"their {target_name} on {target_sq_name}."
            )
        return f"They push to {to_sq}, hitting your {target_name} on {target_sq_name}."
    if is_user_move:
        return f"Pushes to {to_sq} — fights for the centre. Now your pieces have room."
    return f"They push to {to_sq}, fighting for the centre."


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
                return (
                    f"Defends your {piece_name} on {sq_name}. "
                    f"Always cover what you can't replace."
                )
            return (
                f"They defend their {piece_name} on {sq_name} — "
                f"plugging a weak spot."
            )
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


# ── WHY-derivation helpers ───────────────────────────────────────────
# Each helper looks at one specific signal (attack diff, defense diff,
# evasion, PV payoff). Returns a substantive caption only when the
# signal is unambiguous — otherwise None, and the caller leaves the
# move uncaptioned (low confidence → admin review tab).

def _attacks_minor_or_higher(board: chess.Board, from_sq: int, attacker_color: bool) -> set:
    """Return set of squares occupied by enemy pieces of value >=3 (minor
    piece, rook, queen, king) attacked by the piece on from_sq."""
    out = set()
    for sq in board.attacks(from_sq):
        p = board.piece_at(sq)
        if not p or p.color == attacker_color:
            continue
        if p.piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING):
            out.add(sq)
    return out


def _is_safely_placed(board: chess.Board, sq: int, our_color: bool) -> bool:
    """A piece on sq is 'safely placed' if it has at least as many
    defenders as attackers (cheap proxy — ignores piece values)."""
    attackers = board.attackers(not our_color, sq)
    if not attackers:
        return True
    defenders = board.attackers(our_color, sq)
    return len(defenders) >= len(attackers)


def _why_attacks_more_material(
    board_before: chess.Board, played: chess.Move, best: chess.Move, is_user_move: bool,
) -> Optional[str]:
    """Engine's destination square attacks an enemy minor/rook/queen/
    king that the played destination doesn't attack. AND the attacker
    is safely placed there. → high-confidence 'attacks the X' caption."""
    user_color = board_before.piece_at(best.from_square).color
    # Apply best move and inspect attacks from new square
    b_best = board_before.copy()
    b_best.push(best)
    best_attacks = _attacks_minor_or_higher(b_best, best.to_square, user_color)
    if not best_attacks:
        return None
    # Apply played move and inspect attacks from played's destination
    b_played = board_before.copy()
    try:
        b_played.push(played)
    except Exception:
        return None
    played_attacks = _attacks_minor_or_higher(b_played, played.to_square, user_color)
    new_attacks = best_attacks - played_attacks
    if not new_attacks:
        return None
    # Engine's piece must be safely placed on best.to_square — otherwise
    # "attacks the bishop" is misleading if it's hanging there.
    if not _is_safely_placed(b_best, best.to_square, user_color):
        return None
    # Pick highest-value attacked piece for the caption
    target_sq = max(new_attacks, key=lambda s: _PIECE_VALUE.get(b_best.piece_at(s).piece_type, 0))
    target_piece = b_best.piece_at(target_sq)
    target_name = _PIECE_NAME.get(target_piece.piece_type, "piece")
    target_sq_name = chess.square_name(target_sq)
    if is_user_move:
        return f"attacks the {target_name} on {target_sq_name}"
    return f"attacks your {target_name} on {target_sq_name}"


def _why_defends_attacked_piece(
    board_before: chess.Board, played: chess.Move, best: chess.Move, is_user_move: bool,
) -> Optional[str]:
    """Best move adds a defender to an own piece that's currently
    attacked AND undefended (or under-defended). Played move doesn't
    add this defense."""
    user_color = board_before.piece_at(best.from_square).color
    # Find own pieces (≥minor) that are attacked-and-hanging in fen_before
    hanging = []
    for sq in chess.SQUARES:
        p = board_before.piece_at(sq)
        if not p or p.color != user_color:
            continue
        if p.piece_type in (chess.PAWN, chess.KING):
            continue
        attackers = board_before.attackers(not user_color, sq)
        if not attackers:
            continue
        defenders = board_before.attackers(user_color, sq)
        if len(defenders) < len(attackers):
            hanging.append(sq)
    if not hanging:
        return None
    # Apply best move; check if any hanging piece is now adequately defended
    b_best = board_before.copy()
    b_best.push(best)
    b_played = board_before.copy()
    try:
        b_played.push(played)
    except Exception:
        return None
    for sq in hanging:
        # Piece may have moved (e.g., it WAS the played/best piece).
        p_best = b_best.piece_at(sq)
        if not p_best or p_best.color != user_color:
            continue
        defenders_best = b_best.attackers(user_color, sq)
        attackers_best = b_best.attackers(not user_color, sq)
        if len(defenders_best) < len(attackers_best):
            continue
        # Best fixes the hang. Did played also fix it?
        p_played = b_played.piece_at(sq)
        if p_played and p_played.color == user_color:
            defenders_played = b_played.attackers(user_color, sq)
            attackers_played = b_played.attackers(not user_color, sq)
            if len(defenders_played) >= len(attackers_played):
                continue  # played also fixed; not a differentiator
        piece_name = _PIECE_NAME.get(p_best.piece_type, "piece")
        sq_name = chess.square_name(sq)
        if is_user_move:
            return f"defends your {piece_name} on {sq_name} which was hanging"
        return f"defends their {piece_name} on {sq_name} which was hanging"
    return None


def _why_evades_attack(
    board_before: chess.Board, played: chess.Move, best: chess.Move, is_user_move: bool,
) -> Optional[str]:
    """The piece that engine moves was attacked at its origin square,
    AND the played move didn't move that piece (or moved it to a
    worse-attacked square). Engine's move evades a hanging-piece situation."""
    user_color = board_before.piece_at(best.from_square).color
    # The piece engine moves
    moving_piece = board_before.piece_at(best.from_square)
    if not moving_piece or moving_piece.piece_type in (chess.PAWN, chess.KING):
        return None
    from_sq = best.from_square
    attackers = board_before.attackers(not user_color, from_sq)
    if not attackers:
        return None
    defenders = board_before.attackers(user_color, from_sq)
    if len(defenders) >= len(attackers):
        return None  # not actually hanging
    # Engine's destination must be safe
    b_best = board_before.copy()
    b_best.push(best)
    if not _is_safely_placed(b_best, best.to_square, user_color):
        return None
    # Played didn't fix the hang? Either played was a different piece or
    # the original piece is still hanging after played.
    if played.from_square == from_sq:
        return None  # both moves move the same piece — handled by other helper
    piece_name = _PIECE_NAME.get(moving_piece.piece_type, "piece")
    from_sq_name = chess.square_name(from_sq)
    if is_user_move:
        return f"saves your {piece_name} on {from_sq_name} which was hanging"
    return f"saves their {piece_name} on {from_sq_name} which was hanging"


def _why_pv_tactical_payoff(
    board_before: chess.Board, best: chess.Move, best_san: str,
    pv_after_best: Optional[list], is_user_move: bool,
) -> Optional[str]:
    """Look 2-3 plies into pv_after_best. If user's follow-up (ply 2)
    is a clean capture or check, that's the engine's tactical payoff."""
    if not pv_after_best or len(pv_after_best) < 3:
        return None
    # pv_after_best[0] is the engine's best move (might already include).
    # We want the user's follow-up, which is at index 2 (after opp response
    # at index 1).
    follow_up_san = pv_after_best[2] if len(pv_after_best) > 2 else None
    if not follow_up_san:
        return None
    # Concrete payoffs we can name:
    is_capture = "x" in follow_up_san
    is_check = follow_up_san.rstrip("!?").endswith("+") or follow_up_san.rstrip("!?").endswith("#")
    is_mate = follow_up_san.rstrip("!?").endswith("#")
    if not (is_capture or is_check):
        return None
    if is_mate:
        if is_user_move:
            return f"sets up {follow_up_san} — checkmate"
        return f"threatens {follow_up_san} — checkmate"
    if is_capture and is_check:
        if is_user_move:
            return f"sets up {follow_up_san} — capture with check"
        return f"threatens {follow_up_san} — capture with check"
    if is_capture:
        if is_user_move:
            return f"sets up {follow_up_san} — winning material"
        return f"threatens {follow_up_san} — winning material"
    # is_check
    if is_user_move:
        return f"sets up {follow_up_san} — a forcing check"
    return f"threatens {follow_up_san} — a forcing check"


def _derive_engine_preference_why(
    *, fen_before: str, played_san: str, best_san: str,
    pv_after_best: Optional[list], is_user_move: bool,
) -> Optional[str]:
    """Try each WHY-derivation in priority order. Returns a half-sentence
    fragment ('attacks the bishop on c5') that the caller stitches into
    a full caption. Returns None when no high-confidence signal exists."""
    try:
        board = chess.Board(fen_before)
        played = board.parse_san(played_san)
        best = board.parse_san(best_san)
    except Exception:
        return None
    return (
        _why_evades_attack(board, played, best, is_user_move)
        or _why_attacks_more_material(board, played, best, is_user_move)
        or _why_defends_attacked_piece(board, played, best, is_user_move)
        or _why_pv_tactical_payoff(board, best, best_san, pv_after_best, is_user_move)
    )


def _interpret_engine_preference(
    *,
    fen_before: str,
    played_san: str,
    best_san: str,
    pv_after_best: Optional[list],
    is_user_move: bool,
) -> Optional[str]:
    """Produce a substantive caption explaining WHY engine prefers its
    move. Concrete 'why' is required — capture/castle (material/king
    safety) OR a derived signal from attack/defense/PV lookahead.

    Returns None when no high-confidence signal exists. Caller leaves
    the move uncaptioned so the human coach can address it via the
    review tab — better than padding with hollow descriptions like
    'different pawn, different idea'.
    """
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

    # ── Concrete cases (intrinsic WHY: material / king safety) ──
    # Voice rule (per project_coach_voice): use "X was sharper" /
    # "X was the move" framing — the coach is the player's voice,
    # not a third-party narrator quoting an engine.

    # 1. Engine wanted a CAPTURE the user didn't play
    if best_is_capture and not played_is_capture:
        captured = board.piece_at(best_move.to_square)
        if not captured and board.is_en_passant(best_move):
            return f"{best_san} was the move — en passant snags the pawn."
        if captured:
            captured_name = _PIECE_NAME.get(captured.piece_type, "piece")
            return f"{best_san} was the move. Wins the {captured_name} — free."
        return None  # promotion-capture edge case; let coach review

    # 2. Engine wanted to CASTLE — coach voice on king safety
    if best_is_castle and not played_is_castle:
        side = "kingside" if "O-O-O" not in best_san else "queenside"
        return f"{best_san} was the move. Castle {side} first — your king's exposed otherwise."

    # ── Derived cases — require a concrete signal ──
    why = _derive_engine_preference_why(
        fen_before=fen_before,
        played_san=played_san,
        best_san=best_san,
        pv_after_best=pv_after_best,
        is_user_move=is_user_move,
    )
    if not why:
        return None

    # Coach voice: lead with the move, name the lesson plainly.
    if best_is_check:
        return f"{best_san} was sharper — a check that {why}."
    return f"{best_san} was sharper here — {why}."


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

    # 5. Engine prefers a different move. Two paths:
    #    a) A concrete WHY derivable from position/PV → ship a substantive
    #       caption with high confidence.
    #    b) No concrete WHY → return None. The move shows uncaptioned
    #       and the human coach can write proper text via the review tab.
    #       Better than padding with "different idea" / "stronger square"
    #       which sounds informative but teaches nothing.
    if severity in ("mistake", "blunder", "inaccuracy") and best_move_san:
        interp = _interpret_engine_preference(
            fen_before=fen_before,
            played_san=move_san,
            best_san=best_move_san,
            pv_after_best=pv_after_best,
            is_user_move=is_user_move,
        )
        if interp:
            if " wins the " in interp or "en passant" in interp:
                label = "engine_better:capture"
            elif "castling" in interp:
                label = "engine_better:castle"
            elif "saves your" in interp or "saves their" in interp:
                label = "engine_better:evades_attack"
            elif "attacks the" in interp or "attacks your" in interp:
                label = "engine_better:attacks_material"
            elif "defends your" in interp or "defends their" in interp:
                label = "engine_better:defends_piece"
            elif "sets up" in interp or "threatens" in interp:
                label = "engine_better:pv_payoff"
            else:
                label = "engine_better:other"
            return CaptionResult(interp, label, 0.85)
        # No high-confidence WHY available — leave uncaptioned for review.
        # Tag with a low-confidence source label so the audit can count
        # how many flagged-for-review moves we have.
        return CaptionResult("", "engine_review_needed", 0.2)

    return None
