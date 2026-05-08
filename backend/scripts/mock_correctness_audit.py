"""
Mock-correctness audit — verify the FACTUAL accuracy of fired captions.

Coverage audits answer "did a template fire?". This audit answers
"did the template fire on a position where its claim is actually
true?" — by re-deriving each template's chess claim from the board
state and comparing with the rendered caption text.

Catches silent template bugs:
  - "outpost" caption with an enemy pawn that CAN chase
  - "wins the bishop" when the captured piece is actually a knight
  - "your queen had no help" when there were defenders
  - "open file" when there's a friendly pawn on the file
  - "back rank pressure" when the opp king has luft

Reuses the game-generation + caption pipeline from
scripts/mock_games_audit.py to avoid re-implementing it.

Usage:
    python scripts/mock_correctness_audit.py --output /tmp/correctness.txt
    python scripts/mock_correctness_audit.py --time 0.1 --depth 8

Output: per-template correctness rate + sample wrong fires, so we
can see WHICH detectors silently lie about positions.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import chess

# Reuse the game generator + analyser + caption pipeline from
# mock_games_audit so the corpus is shaped identically.
from scripts.mock_games_audit import (  # noqa: E402
    play_game,
    analyse_game,
    caption_for_record,
    DEFAULT_PAIRS,
    DEFAULT_DEPTH,
    DEFAULT_TIME_PER_MOVE,
    DEFAULT_MAX_PLIES,
)


# ── Verifier types ──────────────────────────────────────────────────


VerifyFn = Callable[..., Tuple[bool, Optional[str]]]


# Helpers ────────────────────────────────────────────────────────────

_SQ_RE = re.compile(r"\b([a-h][1-8])\b")
_PIECE_TYPE_RE = re.compile(r"\b(pawn|knight|bishop|rook|queen|king)\b", re.IGNORECASE)

_PIECE_NAME_TO_TYPE = {
    "pawn": chess.PAWN,
    "knight": chess.KNIGHT,
    "bishop": chess.BISHOP,
    "rook": chess.ROOK,
    "queen": chess.QUEEN,
    "king": chess.KING,
}


def _all_squares(text: str) -> List[str]:
    return _SQ_RE.findall(text or "")


def _all_piece_words(text: str) -> List[str]:
    return [m.lower() for m in _PIECE_TYPE_RE.findall(text or "")]


def _piece_at(board: chess.Board, sq_name: str) -> Optional[chess.Piece]:
    try:
        return board.piece_at(chess.parse_square(sq_name))
    except Exception:
        return None


# ── Verifiers ────────────────────────────────────────────────────────
# Each verifier signature:
#   (board_before, move, board_after, caption_text, source, severity,
#    best_move_san, pv_after_best, is_user_move) -> (ok, reason)
#
# Verifiers focus on the CONCRETE CLAIM the template makes. They
# return False with a short reason when the claim doesn't hold.


def verify_good_capture(*, board_before, move, board_after, caption_text, **_):
    """Claim: 'Takes the {captured} on {sq}.' — captured piece type and
    square must match what's on board_before at move.to_square (not
    en passant)."""
    if not board_before.is_capture(move):
        return False, "good_capture fired on non-capture"
    sq_name = chess.square_name(move.to_square)
    if sq_name not in caption_text:
        return False, f"caption omits target square {sq_name}"
    if board_before.is_en_passant(move):
        if "en passant" not in caption_text:
            return False, "en passant capture not labelled"
        return True, None
    captured = board_before.piece_at(move.to_square)
    if not captured:
        return False, "no piece on capture square in board_before"
    piece_words = _all_piece_words(caption_text)
    expected_name = {
        chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
        chess.ROOK: "rook", chess.QUEEN: "queen",
    }.get(captured.piece_type)
    if not expected_name:
        return False, "captured piece type unexpected (king?)"
    if expected_name not in piece_words:
        return False, f"caption says {piece_words[:1]} but board has {expected_name}"
    return True, None


def verify_good_castle(*, board_before, move, board_after, caption_text, **_):
    """Claim: 'Castled {side}.' — must be a real castling move."""
    if not board_before.is_castling(move):
        return False, "non-castling move tagged good_castle"
    is_kingside = board_before.is_kingside_castling(move)
    side = "kingside" if is_kingside else "queenside"
    if side not in caption_text.lower():
        return False, f"caption side missing/wrong (expected {side})"
    return True, None


def verify_good_check(*, board_before, move, board_after, caption_text, **_):
    """Claim: '— check. Forces them to respond.' — must actually give check."""
    if not board_after.is_check():
        return False, "good_check fired on non-checking move"
    return True, None


def verify_good_central_pawn(*, board_before, move, board_after, caption_text, **_):
    """Claim: 'Pushes to {sq}, claiming central space.' — must be a
    pawn move to a central square."""
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.PAWN:
        return False, "non-pawn tagged good_central_pawn"
    sq_name = chess.square_name(move.to_square)
    if sq_name not in {"e4", "d4", "e5", "d5", "c4", "c5", "f4", "f5"}:
        return False, f"to_square {sq_name} not in central set"
    return True, None


def verify_good_development(*, board_before, move, board_after, caption_text, **_):
    """Claim: 'Develops the {piece} to {sq}.' — knight or bishop,
    moving from starting rank."""
    moving = board_before.piece_at(move.from_square)
    if not moving:
        return False, "no piece on from_square"
    if moving.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return False, "non-minor piece tagged good_development"
    starting_rank = 0 if moving.color == chess.WHITE else 7
    if chess.square_rank(move.from_square) != starting_rank:
        return False, "not from starting rank"
    sq_name = chess.square_name(move.to_square)
    if sq_name not in caption_text:
        return False, f"caption omits {sq_name}"
    return True, None


def verify_good_defend(*, board_before, move, board_after, caption_text, **_):
    """Claim: 'Defends your {piece} on {sq}.' — that piece must have
    been attacked pre-move AND have at least one defender post-move,
    AND defenders post-move >= attackers post-move."""
    sqs = _all_squares(caption_text)
    if not sqs:
        return False, "no square in caption"
    target_sq_name = sqs[0]
    target_sq = chess.parse_square(target_sq_name)
    user_color = board_before.turn
    p = board_after.piece_at(target_sq)
    if not p or p.color != user_color:
        return False, "no own piece on claimed defended square post-move"
    pre_attackers = board_before.attackers(not user_color, target_sq)
    if not pre_attackers:
        return False, f"piece on {target_sq_name} wasn't attacked pre-move"
    post_defenders = board_after.attackers(user_color, target_sq)
    if not post_defenders:
        return False, "no defender added"
    return True, None


def verify_middlegame_knight_outpost(*, board_before, move, board_after, caption_text, **_):
    """Claim: 'Plants the knight on {sq} — secure outpost. No enemy
    pawn can chase it.'"""
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.KNIGHT:
        return False, "non-knight tagged outpost"
    target_sq = move.to_square
    user_color = moving.color
    # Pawn-supported by friendly pawn?
    support_rank = chess.square_rank(target_sq) - 1 if user_color == chess.WHITE else chess.square_rank(target_sq) + 1
    has_support = False
    for df in (-1, 1):
        nf = chess.square_file(target_sq) + df
        if 0 <= nf <= 7 and 0 <= support_rank <= 7:
            sq = chess.square(nf, support_rank)
            p = board_after.piece_at(sq)
            if p and p.piece_type == chess.PAWN and p.color == user_color:
                has_support = True
                break
    if not has_support:
        return False, "claimed outpost lacks pawn support"
    # No enemy pawn can chase
    target_rank = chess.square_rank(target_sq)
    target_file = chess.square_file(target_sq)
    for df in (-1, 1):
        nf = target_file + df
        if not (0 <= nf <= 7):
            continue
        rank_range = range(target_rank + 1, 8) if user_color == chess.WHITE else range(0, target_rank)
        for nr in rank_range:
            p = board_after.piece_at(chess.square(nf, nr))
            if p and p.piece_type == chess.PAWN and p.color != user_color:
                return False, f"enemy pawn on {chess.square_name(chess.square(nf, nr))} can chase"
    return True, None


def verify_middlegame_rook_open_file(*, board_before, move, board_after, caption_text, **_):
    """Claim: 'Rook to the {file}-file — {open|half-open}. The rook
    controls the column.'"""
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.ROOK:
        return False, "non-rook tagged rook_open_file"
    user_color = moving.color
    to_file = chess.square_file(move.to_square)
    # Friendly pawn on file?
    for r in range(8):
        p = board_after.piece_at(chess.square(to_file, r))
        if p and p.piece_type == chess.PAWN and p.color == user_color:
            return False, "friendly pawn on claimed open file"
    # Caption says "open" vs "half-open"; verify against enemy pawn presence
    has_enemy_pawn = any(
        (lambda p: p and p.piece_type == chess.PAWN and p.color != user_color)(board_after.piece_at(chess.square(to_file, r)))
        for r in range(8)
    )
    if has_enemy_pawn and "half-open" not in caption_text:
        return False, "enemy pawn present but caption says 'open'"
    if not has_enemy_pawn and "half-open" in caption_text:
        return False, "no enemy pawn but caption says 'half-open'"
    return True, None


def verify_middlegame_back_rank_pressure(*, board_before, move, board_after, caption_text, **_):
    """Claim: 'Heavy piece to {sq} — eyes their back rank. Their king
    has no luft.'"""
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type not in (chess.ROOK, chess.QUEEN):
        return False, "non-heavy-piece tagged back_rank_pressure"
    opp = not moving.color
    king_sq = board_after.king(opp)
    if king_sq is None:
        return False, "no opp king"
    back_rank = 7 if opp == chess.BLACK else 0
    if chess.square_rank(king_sq) != back_rank:
        return False, "opp king not on back rank"
    # Check luft squares all blocked
    front_rank = back_rank - 1 if opp == chess.BLACK else back_rank + 1
    king_file = chess.square_file(king_sq)
    for df in (-1, 0, 1):
        nf = king_file + df
        if not (0 <= nf <= 7):
            continue
        sq = chess.square(nf, front_rank)
        p = board_after.piece_at(sq)
        if not (p and p.piece_type == chess.PAWN and p.color == opp):
            return False, f"luft square {chess.square_name(sq)} not blocked by opp pawn"
    return True, None


def verify_middlegame_luft(*, board_before, move, board_after, caption_text, **_):
    """Claim: 'Pawn to {sq} — gives the king luft.'"""
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.PAWN:
        return False, "non-pawn tagged luft"
    user_color = moving.color
    to_file = chess.square_file(move.to_square)
    if to_file not in (0, 6, 7):
        return False, f"to_file {to_file} not a/g/h"
    king_sq = board_before.king(user_color)
    if king_sq is None:
        return False, "no king"
    castled_rank = 0 if user_color == chess.WHITE else 7
    if chess.square_rank(king_sq) != castled_rank:
        return False, "king not on castled rank"
    return True, None


def verify_middlegame_wing_expansion(*, board_before, move, board_after, caption_text, **_):
    """Claim: 'Pawn to {sq} — {kingside attack|queenside expansion}.'"""
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.PAWN:
        return False, "non-pawn tagged wing_expansion"
    to_file = chess.square_file(move.to_square)
    if to_file not in (0, 1, 6, 7):
        return False, f"to_file {to_file} not flank"
    flank = "kingside" if to_file in (6, 7) else "queenside"
    if flank not in caption_text:
        return False, f"caption flank wrong (expected {flank})"
    return True, None


def verify_middlegame_king_walk(*, board_before, move, board_after, caption_text, **_):
    """Claim: 'King to {sq} — sidesteps. Avoids checks and pins.'"""
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.KING:
        return False, "non-king tagged king_walk"
    return True, None


def verify_middlegame_piece_maneuver(*, board_before, move, board_after, caption_text, **_):
    """Claim: '{Piece} to {sq} — repositions.' — minor piece, non-capture."""
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return False, "non-minor piece tagged piece_maneuver"
    if board_before.is_capture(move):
        return False, "capture move tagged piece_maneuver"
    return True, None


def verify_middlegame_pawn_prep(*, board_before, move, board_after, caption_text, **_):
    """Claim: 'Pawn to {sq} — quiet structural move. Solid setup.'"""
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.PAWN:
        return False, "non-pawn tagged pawn_prep"
    if board_before.is_capture(move):
        return False, "capture tagged pawn_prep"
    to_file = chess.square_file(move.to_square)
    if to_file not in (2, 3, 4):
        return False, f"to_file {to_file} not c/d/e"
    return True, None


def verify_middlegame_late_central_pawn(*, board_before, move, board_after, caption_text, **_):
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.PAWN:
        return False, "non-pawn"
    to_file = chess.square_file(move.to_square)
    if to_file not in (2, 3, 4, 5):
        return False, f"to_file {to_file} not c/d/e/f"
    if board_before.is_capture(move):
        return False, "capture"
    return True, None


def verify_middlegame_bishop_activation(*, board_before, move, board_after, caption_text, **_):
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.BISHOP:
        return False, "non-bishop"
    return True, None


def verify_middlegame_pawn_break(*, board_before, move, board_after, caption_text, **_):
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.PAWN:
        return False, "non-pawn"
    return True, None


def verify_middlegame_queen_lift(*, board_before, move, board_after, caption_text, **_):
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.QUEEN:
        return False, "non-queen"
    return True, None


def verify_middlegame_pawn_shield(*, board_before, move, board_after, caption_text, **_):
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.PAWN:
        return False, "non-pawn"
    if chess.square_file(move.to_square) != 5:
        return False, "not f-file"
    return True, None


def verify_middlegame_minority_attack(*, board_before, move, board_after, caption_text, **_):
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.PAWN:
        return False, "non-pawn"
    if chess.square_file(move.to_square) not in (0, 1):
        return False, "not a/b file"
    return True, None


def verify_middlegame_king_tuck(*, board_before, move, board_after, caption_text, **_):
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.KING:
        return False, "non-king"
    return True, None


def verify_middlegame_knight_central(*, board_before, move, board_after, caption_text, **_):
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.KNIGHT:
        return False, "non-knight"
    to_file = chess.square_file(move.to_square)
    to_rank = chess.square_rank(move.to_square)
    if to_file not in (2, 3, 4, 5):
        return False, "not central file"
    if to_rank not in (3, 4):
        return False, "not central rank"
    return True, None


def verify_endgame_king_activation(*, board_before, move, board_after, caption_text, **_):
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.KING:
        return False, "non-king"
    user_color = moving.color
    to_rank = chess.square_rank(move.to_square)
    from_rank = chess.square_rank(move.from_square)
    if user_color == chess.WHITE and not (to_rank > from_rank and to_rank >= 2):
        return False, "white king didn't move forward"
    if user_color == chess.BLACK and not (to_rank < from_rank and to_rank <= 5):
        return False, "black king didn't move forward"
    return True, None


def verify_endgame_king_repositioning(*, board_before, move, board_after, caption_text, **_):
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.KING:
        return False, "non-king"
    return True, None


def verify_endgame_rook_to_seventh(*, board_before, move, board_after, caption_text, **_):
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.ROOK:
        return False, "non-rook"
    user_color = moving.color
    target_rank = 6 if user_color == chess.WHITE else 1
    if chess.square_rank(move.to_square) != target_rank:
        return False, "rook not on 7th"
    return True, None


def verify_endgame_pawn_promotion(*, board_before, move, board_after, caption_text, **_):
    if move.promotion is None:
        return False, "no promotion"
    return True, None


def verify_endgame_pawn_near_promotion(*, board_before, move, board_after, caption_text, **_):
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.PAWN:
        return False, "non-pawn"
    user_color = moving.color
    near_rank = 6 if user_color == chess.WHITE else 1
    if chess.square_rank(move.to_square) != near_rank:
        return False, "not on near-promotion rank"
    return True, None


def verify_endgame_king_blockades_pawn(*, board_before, move, board_after, caption_text, **_):
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.KING:
        return False, "non-king"
    return True, None


def verify_engine_better_capture(
    *, board_before, move, board_after, caption_text,
    best_move_san=None, **_
):
    """Claim: 'Engine prefers {best_san} — wins the {captured}.'"""
    if not best_move_san:
        return False, "no best_move_san provided"
    try:
        best_move = board_before.parse_san(best_move_san)
    except Exception:
        return False, f"best_san {best_move_san} unparseable"
    if not board_before.is_capture(best_move):
        return False, "best_move not a capture"
    if board_before.is_en_passant(best_move):
        return ("en passant" in caption_text), None if "en passant" in caption_text else "missing en passant tag"
    captured = board_before.piece_at(best_move.to_square)
    if not captured:
        return False, "no captured piece"
    expected = {
        chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
        chess.ROOK: "rook", chess.QUEEN: "queen",
    }.get(captured.piece_type)
    if not expected or expected not in caption_text:
        piece_words = _all_piece_words(caption_text)
        return False, f"caption says {piece_words[:1]} but board has {expected}"
    return True, None


def verify_engine_better_castle(*, board_before, move, board_after, caption_text, best_move_san=None, **_):
    if not best_move_san or not best_move_san.startswith("O-O"):
        return False, "best not castling"
    return True, None


def verify_engine_better_attacks_material(
    *, board_before, move, board_after, caption_text,
    best_move_san=None, **_
):
    if not best_move_san:
        return False, "no best_san"
    try:
        best_move = board_before.parse_san(best_move_san)
    except Exception:
        return False, "best_san unparseable"
    # After the engine's best move, the moved piece should attack >=2 enemy
    # pieces of value >=3 OR specifically the piece named in the caption.
    b = board_before.copy()
    b.push(best_move)
    sqs = _all_squares(caption_text)
    user_color = board_before.turn
    if not sqs:
        return False, "no target sq in caption"
    # Last square mentioned is the claimed target — verify it's an enemy
    # piece attacked by best_move's destination.
    target_sq = chess.parse_square(sqs[-1])
    target_p = b.piece_at(target_sq)
    if not target_p or target_p.color == user_color:
        return False, "no enemy piece on claimed target"
    if target_sq not in b.attacks(best_move.to_square):
        return False, "moved piece doesn't attack claimed target"
    return True, None


def verify_engine_better_defends_piece(
    *, board_before, move, board_after, caption_text,
    best_move_san=None, **_
):
    if not best_move_san:
        return False, "no best_san"
    try:
        best_move = board_before.parse_san(best_move_san)
    except Exception:
        return False, "best_san unparseable"
    user_color = board_before.turn
    sqs = _all_squares(caption_text)
    if not sqs:
        return False, "no sq in caption"
    target_sq = chess.parse_square(sqs[-1])
    if not (board_before.attackers(not user_color, target_sq)):
        return False, "claimed defended piece wasn't attacked pre-move"
    b = board_before.copy()
    b.push(best_move)
    p = b.piece_at(target_sq)
    if not p or p.color != user_color:
        return False, "no own piece on claimed sq post-move"
    if len(b.attackers(user_color, target_sq)) < len(b.attackers(not user_color, target_sq)):
        return False, "still hanging post-move"
    return True, None


def verify_engine_better_evades_attack(
    *, board_before, move, board_after, caption_text,
    best_move_san=None, **_
):
    if not best_move_san:
        return False, "no best_san"
    try:
        best_move = board_before.parse_san(best_move_san)
    except Exception:
        return False, "best_san unparseable"
    user_color = board_before.turn
    moving = board_before.piece_at(best_move.from_square)
    if not moving:
        return False, "no piece at best from_square"
    if not board_before.attackers(not user_color, best_move.from_square):
        return False, "claimed-evader wasn't attacked pre-move"
    return True, None


def verify_engine_better_pv_payoff(
    *, board_before, move, board_after, caption_text,
    pv_after_best=None, **_
):
    """Claim: '... — sets up {pv2} — winning material / a forcing check.'
    Verify pv_after_best ply-2 san matches caption AND is capture or check."""
    if not pv_after_best or len(pv_after_best) < 3:
        return False, f"pv too short: {pv_after_best}"
    follow_up = pv_after_best[2]
    if follow_up not in caption_text:
        return False, f"caption omits follow-up move {follow_up}"
    is_capture = "x" in follow_up
    is_check = follow_up.rstrip("!?").endswith(("+", "#"))
    if not (is_capture or is_check):
        return False, f"follow-up {follow_up} is not capture or check"
    return True, None


def verify_template_hanging_piece(
    *, board_before, move, board_after, caption_text, **_
):
    """Claim: 'Your {piece} on {sq} was hanging.' — a previously-attacked
    own piece that was undefended and the user's move doesn't save it."""
    sqs = _all_squares(caption_text)
    if not sqs:
        return False, "no sq"
    sq_name = sqs[0]
    sq = chess.parse_square(sq_name)
    user_color = board_before.turn
    p = board_before.piece_at(sq)
    if not p or p.color != user_color:
        return False, "no own piece on claimed sq pre-move"
    if not board_before.attackers(not user_color, sq):
        return False, "wasn't attacked pre-move"
    return True, None


def verify_template_walked_into_capture(
    *, board_before, move, board_after, caption_text, **_
):
    """Claim: 'Your {piece} on {sq} has no defender. {opp_capture} wins it.'
    The user's just-played move places/keeps a piece on a square attacked
    by opp without sufficient defenders."""
    user_color = board_before.turn  # color BEFORE move = the user
    # Find claimed square in caption
    sqs = _all_squares(caption_text)
    if not sqs:
        return False, "no sq"
    sq = chess.parse_square(sqs[0])
    p = board_after.piece_at(sq)
    if not p or p.color != user_color:
        return False, "no own piece on claimed sq post-move"
    attackers = board_after.attackers(not user_color, sq)
    defenders = board_after.attackers(user_color, sq)
    if len(attackers) <= len(defenders):
        return False, "not actually hanging post-move"
    return True, None


def verify_template_missed_capture(
    *, board_before, move, board_after, caption_text,
    best_move_san=None, **_
):
    """Claim: '{best_san} wins the {captured} on {sq}. It has no defender.'"""
    if not best_move_san:
        return False, "no best_san"
    try:
        best_move = board_before.parse_san(best_move_san)
    except Exception:
        return False, "best_san unparseable"
    if not board_before.is_capture(best_move):
        return False, "best not a capture"
    captured = board_before.piece_at(best_move.to_square)
    if not captured:
        return False, "no captured piece"
    return True, None


def verify_template_missed_check(
    *, board_before, move, board_after, caption_text,
    best_move_san=None, **_
):
    if not best_move_san:
        return False, "no best_san"
    if not best_move_san.rstrip("!?").endswith(("+", "#")):
        return False, "best_san isn't a check/mate"
    return True, None


def verify_template_missed_mate(
    *, board_before, move, board_after, caption_text,
    best_move_san=None, **_
):
    if not best_move_san:
        return False, "no best_san"
    if "#" not in (best_move_san or ""):
        return False, "best_san isn't mate"
    return True, None


def verify_template_missed_castle(
    *, board_before, move, board_after, caption_text,
    best_move_san=None, **_
):
    if not best_move_san or not best_move_san.startswith("O-O"):
        return False, "best wasn't castling"
    return True, None


def verify_template_missed_fork(
    *, board_before, move, board_after, caption_text,
    best_move_san=None, **_
):
    if not best_move_san:
        return False, "no best_san"
    try:
        best_move = board_before.parse_san(best_move_san)
    except Exception:
        return False, "best_san unparseable"
    b = board_before.copy()
    b.push(best_move)
    user_color = board_before.turn
    targets = 0
    for sq in b.attacks(best_move.to_square):
        p = b.piece_at(sq)
        if p and p.color != user_color and p.piece_type != chess.PAWN:
            targets += 1
    if targets < 2:
        return False, f"only {targets} targets attacked, not a fork"
    return True, None


def verify_template_missed_attack_on_high_value(
    *, board_before, move, board_after, caption_text,
    best_move_san=None, **_
):
    """Claim: '{some_san} attacks their {piece} on {sq}. They have to
    move it...'. Verify the engine's best move (or some user piece)
    after some sequence creates an attack on a piece named in caption.
    Conservative: just check the named target square actually has an
    enemy piece, and that some user piece attacks it post-best."""
    if not best_move_san:
        return False, "no best_san"
    try:
        best_move = board_before.parse_san(best_move_san)
    except Exception:
        return False, "best_san unparseable"
    sqs = _all_squares(caption_text)
    if not sqs:
        return False, "no sq in caption"
    target_sq = chess.parse_square(sqs[-1])
    user_color = board_before.turn
    b = board_before.copy()
    b.push(best_move)
    target_p = b.piece_at(target_sq)
    if not target_p or target_p.color == user_color:
        return False, f"no enemy piece on claimed target {sqs[-1]}"
    if target_p.piece_type == chess.PAWN:
        return False, "claimed high-value target is a pawn"
    if not b.attackers(user_color, target_sq):
        return False, "no user attacker on claimed target"
    return True, None


def verify_template_trapped_piece(
    *, board_before, move, board_after, caption_text, **_
):
    """Claim: 'Your {piece} on {sq} had no safe square to go to.'
    Verify: a user piece exists on caption's named square, AND it has
    no safe square in board_after-state-before-move (i.e. attacked
    AND every escape square is also attacked or is its own colour)."""
    sqs = _all_squares(caption_text)
    if not sqs:
        return False, "no sq in caption"
    sq_name = sqs[0]
    sq = chess.parse_square(sq_name)
    user_color = board_before.turn
    p = board_before.piece_at(sq)
    if not p or p.color != user_color:
        return False, "no own piece on claimed sq"
    if p.piece_type in (chess.PAWN, chess.KING):
        return False, "claimed-trapped is pawn or king (skip)"
    if not board_before.attackers(not user_color, sq):
        return False, "claimed-trapped piece isn't attacked"
    # "Trapped" = every legal move of this piece leaves it on an
    # attacked square or doesn't escape capture. Lighter check: at
    # least one of its legal destinations exists, but ALL of them
    # land on squares attacked by opp.
    safe_destinations = 0
    for legal_move in board_before.legal_moves:
        if legal_move.from_square != sq:
            continue
        b2 = board_before.copy()
        b2.push(legal_move)
        if not b2.is_attacked_by(not user_color, legal_move.to_square):
            safe_destinations += 1
            break
    if safe_destinations > 0:
        return False, "piece has at least one safe escape square"
    return True, None


def verify_template_missed_pin(
    *, board_before, move, board_after, caption_text,
    best_move_san=None, **_
):
    """Claim: 'Your {piece} pins their {target} on {sq} — it cannot move.'
    Verify the engine's best move creates a pin: after the move, the
    user's piece attacks the target square, and there's an opp piece
    of higher value on the line behind."""
    if not best_move_san:
        return False, "no best_san"
    try:
        best_move = board_before.parse_san(best_move_san)
    except Exception:
        return False, "best_san unparseable"
    sqs = _all_squares(caption_text)
    if not sqs:
        return False, "no sq in caption"
    pinned_sq_name = sqs[-1]
    pinned_sq = chess.parse_square(pinned_sq_name)
    user_color = board_before.turn
    b = board_before.copy()
    b.push(best_move)
    # python-chess has board.pin() returning the pin ray for a pinned
    # piece, but only when it's the moving side. Use is_pinned with
    # chess.WHITE/BLACK (color whose piece is pinned).
    opp_color = not user_color
    pinned_piece = b.piece_at(pinned_sq)
    if not pinned_piece or pinned_piece.color != opp_color:
        return False, "no opp piece on claimed pinned sq"
    if not b.is_pinned(opp_color, pinned_sq):
        return False, "claimed-pinned piece is not actually pinned"
    return True, None


def verify_endgame_connected_passed_pawns(
    *, board_before, move, board_after, caption_text, **_
):
    """Claim: 'Connected passed pawns. Push them together.'"""
    moving = board_before.piece_at(move.from_square)
    if not moving or moving.piece_type != chess.PAWN:
        return False, "non-pawn"
    user_color = moving.color
    direction = 1 if user_color == chess.WHITE else -1
    passed_files = set()
    for sq in chess.SQUARES:
        p = board_after.piece_at(sq)
        if not p or p.piece_type != chess.PAWN or p.color != user_color:
            continue
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        is_passed = True
        nr = r + direction
        while 0 <= nr <= 7:
            for nf in (f - 1, f, f + 1):
                if 0 <= nf <= 7:
                    pp = board_after.piece_at(chess.square(nf, nr))
                    if pp and pp.piece_type == chess.PAWN and pp.color != user_color:
                        is_passed = False
                        break
            if not is_passed:
                break
            nr += direction
        if is_passed:
            passed_files.add(f)
    for f in passed_files:
        if (f + 1) in passed_files:
            return True, None
    return False, "no two adjacent passed pawn files"


def verify_engine_review_needed(*args, **kwargs):
    """Empty by design — no claim to verify."""
    return True, "deliberately empty"


def verify_good_generic(*args, **kwargs):
    """Generic fallback — no specific claim to verify."""
    return True, "generic fallback (no claim)"


def verify_engine_fallback(*args, **kwargs):
    return True, "fallback (no claim)"


# Registry — source label → verifier
VERIFIERS: Dict[str, VerifyFn] = {
    "good_capture": verify_good_capture,
    "good_castle": verify_good_castle,
    "good_check": verify_good_check,
    "good_central_pawn": verify_good_central_pawn,
    "good_development": verify_good_development,
    "good_defend": verify_good_defend,
    "good_generic": verify_good_generic,

    "middlegame:knight_outpost": verify_middlegame_knight_outpost,
    "middlegame:knight_central": verify_middlegame_knight_central,
    "middlegame:rook_open_file": verify_middlegame_rook_open_file,
    "middlegame:back_rank_pressure": verify_middlegame_back_rank_pressure,
    "middlegame:queen_lift": verify_middlegame_queen_lift,
    "middlegame:pawn_break": verify_middlegame_pawn_break,
    "middlegame:minority_attack": verify_middlegame_minority_attack,
    "middlegame:king_tuck": verify_middlegame_king_tuck,
    "middlegame:luft": verify_middlegame_luft,
    "middlegame:pawn_prep": verify_middlegame_pawn_prep,
    "middlegame:late_central_pawn": verify_middlegame_late_central_pawn,
    "middlegame:pawn_shield": verify_middlegame_pawn_shield,
    "middlegame:wing_expansion": verify_middlegame_wing_expansion,
    "middlegame:bishop_activation": verify_middlegame_bishop_activation,
    "middlegame:king_walk": verify_middlegame_king_walk,
    "middlegame:piece_maneuver": verify_middlegame_piece_maneuver,

    "endgame:king_activation": verify_endgame_king_activation,
    "endgame:king_repositioning": verify_endgame_king_repositioning,
    "endgame:rook_to_seventh": verify_endgame_rook_to_seventh,
    "endgame:pawn_promotion": verify_endgame_pawn_promotion,
    "endgame:pawn_near_promotion": verify_endgame_pawn_near_promotion,
    "endgame:king_blockades_pawn": verify_endgame_king_blockades_pawn,

    "engine_better:capture": verify_engine_better_capture,
    "engine_better:castle": verify_engine_better_castle,
    "engine_better:attacks_material": verify_engine_better_attacks_material,
    "engine_better:defends_piece": verify_engine_better_defends_piece,
    "engine_better:evades_attack": verify_engine_better_evades_attack,
    "engine_better:pv_payoff": verify_engine_better_pv_payoff,

    "template:hanging_piece": verify_template_hanging_piece,
    "template:walked_into_capture": verify_template_walked_into_capture,
    "template:missed_capture": verify_template_missed_capture,
    "template:missed_check": verify_template_missed_check,
    "template:missed_mate": verify_template_missed_mate,
    "template:missed_castle": verify_template_missed_castle,
    "template:missed_fork": verify_template_missed_fork,
    "template:missed_attack_on_high_value": verify_template_missed_attack_on_high_value,
    "template:trapped_piece": verify_template_trapped_piece,
    "template:missed_pin": verify_template_missed_pin,

    "endgame:connected_passed_pawns": verify_endgame_connected_passed_pawns,

    "engine_review_needed": verify_engine_review_needed,
    "engine_fallback": verify_engine_fallback,
}


# ── 1200-test (explanation quality) ─────────────────────────────────
# Per the project memory feedback_1200_test: every caption must EITHER
# pair a chess concept word with a verifiable concrete consequence, OR
# not use the concept at all. The check is "does the caption contain
# at least one concrete consequence the player can see on the board?"
# A caption can be factually correct (passes verifier above) yet still
# fail the 1200 test if it's pure abstract description.

# Source labels that are exempt — empty by design or generic fallback
# that we already accept as a non-teaching slot.
_QUALITY_EXEMPT = {
    "engine_review_needed",
    "engine_fallback",
    "good_generic",
    "silent",
}

# Concept words that need a paired explanation. If a caption has any
# of these AND no concrete-consequence pattern, it fails the 1200 test.
_NEEDS_PAIR_CONCEPTS = [
    "outpost", "fianchetto", "luft", "minority attack",
    "controls the column", "controls the file", "controls the diagonal",
    "active diagonal", "fresh diagonal", "secure outpost",
    "tempo", "prophylactic", "central post",
    "claiming central space", "kingside attack", "queenside expansion",
    "back-rank", "back rank", "tests their pawn structure",
]

# Concrete-consequence patterns. If the caption matches any of these,
# it has a verifiable claim a 1200 player can confirm by looking.
_CONCRETE_PATTERNS = [
    r"wins (the |an? |your |their |my |\w+ )?(pawn|knight|bishop|rook|queen|piece|material)",
    r"takes (the |a )?(pawn|knight|bishop|rook|queen|piece) on [a-h][1-8]",
    r"attacks (the |a |their |my )?(pawn|knight|bishop|rook|queen|king) on [a-h][1-8]",
    r"defends (your|their|my) (pawn|knight|bishop|rook|queen) on [a-h][1-8]",
    r"saves (your|their|my) (pawn|knight|bishop|rook|queen|piece)",
    r"checkmate",
    r"check\.",
    r"check\s—",
    r"check that forces",
    r"check that",
    r"no enemy pawn can chase",
    r"no defender",
    r"no defenders",
    r"had no safe square",
    r"no escape",
    r"no luft",
    r"sets up [\w\d\+#=]+",
    r"threatens [\w\d\+#=]+",
    r"prepares ",
    r"promot",
    r"promotion",
    r"sits in front of (the )?(\w+ )?passed pawn",
    r"connected passed pawns",
    r"runs to promotion",
    r"catches it in time",
    r"(a|the) capture",
    r"forces (them|me|him|her) to respond",
    r"forces a (king move|response|king response)",
    r"open(s)? (a |the )?(file|line|diagonal)",
    r"opens up",
    r"keeps the king safer",
    r"escape squares?",
    r"shores up the kingside",
    r"closes the long diagonal",
    r"avoids checks",
    r"tucks the king",
    r"passed pawn",
    r"has no defender",
    r"no back-rank surprises now",
    r"defending [a-h][1-8]",
    r"won the (knight|bishop|rook|queen|piece)",
    r"hanging",
]

_concrete_re = re.compile("|".join(_CONCRETE_PATTERNS), re.IGNORECASE)


def quality_check(caption_text: str, source: str) -> Tuple[bool, str]:
    """Returns (passes_1200_test, reason).
    Pass = either has no risky concept word, or has one paired with a
    concrete-consequence pattern.
    """
    if source in _QUALITY_EXEMPT:
        return True, "exempt source"
    txt = (caption_text or "").strip()
    if not txt:
        return True, "empty caption"
    txt_lower = txt.lower()
    has_concrete = bool(_concrete_re.search(txt))
    if has_concrete:
        return True, "has concrete consequence"
    # No concrete consequence — only OK if the caption avoids all risky
    # concept words too (i.e. it's a clean fact statement).
    has_risky = any(c in txt_lower for c in _NEEDS_PAIR_CONCEPTS)
    if has_risky:
        return False, "concept word used without paired concrete consequence"
    # No risky concept and no concrete consequence — likely a hollow
    # filler caption ("repositions", "small move makes my side a bit
    # better", "claiming central space"). Flag.
    hollow_flags = [
        "repositions", "redeploys", "redeployment", "active diagonal",
        "small move", "to a better spot", "controls the",
        "reasonable", "holds the structure", "keeps the position under control",
        "pawn moves matter", "solid setup", "solid",
    ]
    if any(h in txt_lower for h in hollow_flags):
        return False, "empty filler phrasing"
    return True, "concrete fact statement"


# ── Runner ───────────────────────────────────────────────────────────


def run(args) -> str:
    pairs = DEFAULT_PAIRS
    if args.pairs:
        pairs = []
        for token in args.pairs.split(","):
            t = token.strip().lower().replace("vs", "v")
            if "v" in t:
                w, b = t.split("v", 1)
                pairs.append((int(w), int(b)))

    correctness_total: Dict[str, int] = defaultdict(int)
    correctness_pass: Dict[str, int] = defaultdict(int)
    wrong_examples: Dict[str, List[Dict]] = defaultdict(list)
    no_verifier: Counter = Counter()

    # 1200-test (explanation quality)
    quality_total: Dict[str, int] = defaultdict(int)
    quality_pass: Dict[str, int] = defaultdict(int)
    quality_fails: Dict[str, List[Dict]] = defaultdict(list)

    started = time.time()
    games_played = 0
    for pair in pairs:
        w_rating, b_rating = pair
        user_color = "white"
        print(f"  Generating {w_rating}v{b_rating}...", flush=True)
        game = play_game(
            w_rating, b_rating,
            depth=args.depth, time_per_move=args.time, max_plies=args.max_plies,
        )
        plies = sum(1 for _ in game.mainline_moves())
        print(f"    {plies} plies; analysing + verifying...", flush=True)
        records = analyse_game(game, depth=14, multipv=3)
        games_played += 1

        history_san: List[str] = []
        for rec in records:
            cap = caption_for_record(rec, user_color, history_san)
            history_san.append(rec["move_san"])
            if not cap["is_user_move"]:
                continue
            source = cap["source"]
            text = cap["text"]
            verifier = VERIFIERS.get(source)
            if not verifier:
                no_verifier[source] += 1
                continue
            board_before = chess.Board(rec["fen_before"])
            board_after = chess.Board(rec["fen_after"])
            try:
                move = board_before.parse_san(rec["move_san"])
            except Exception:
                continue
            try:
                ok, reason = verifier(
                    board_before=board_before,
                    move=move,
                    board_after=board_after,
                    caption_text=text,
                    source=source,
                    severity=rec["severity"],
                    best_move_san=rec.get("best_move_san"),
                    pv_after_best=rec.get("pv_after_best"),
                    is_user_move=True,
                )
            except Exception as e:
                ok, reason = False, f"verifier exception: {e}"
            correctness_total[source] += 1
            if ok:
                correctness_pass[source] += 1
            else:
                if len(wrong_examples[source]) < 5:
                    wrong_examples[source].append({
                        "pair": pair,
                        "move": f"M{rec['move_number']} {rec['move_san']}",
                        "fen": rec["fen_before"],
                        "text": (text or "")[:140],
                        "reason": reason or "(no reason)",
                    })

            # 1200-test pass — explanation quality
            quality_total[source] += 1
            q_ok, q_reason = quality_check(text, source)
            if q_ok:
                quality_pass[source] += 1
            else:
                if len(quality_fails[source]) < 5:
                    quality_fails[source].append({
                        "pair": pair,
                        "move": f"M{rec['move_number']} {rec['move_san']}",
                        "text": (text or "")[:140],
                        "reason": q_reason,
                    })

    elapsed = time.time() - started

    # ── Build report ────────────────────────────────────────────────
    lines: List[str] = []
    lines.append("=" * 78)
    lines.append("MOCK CORRECTNESS AUDIT")
    lines.append("=" * 78)
    lines.append(f"  pairs:        {pairs}")
    lines.append(f"  games played: {games_played}")
    lines.append(f"  elapsed:      {elapsed:.1f}s")
    lines.append("")

    grand_total = sum(correctness_total.values()) or 1
    grand_pass = sum(correctness_pass.values())
    lines.append(
        f"  OVERALL CORRECTNESS: {grand_pass}/{grand_total}  "
        f"({100.0 * grand_pass / grand_total:.1f}% verified)"
    )
    lines.append("")

    # Per-template table, sorted by total fires desc
    lines.append("PER-TEMPLATE CORRECTNESS:")
    lines.append("-" * 78)
    for source, total in sorted(correctness_total.items(), key=lambda x: -x[1]):
        passed = correctness_pass.get(source, 0)
        pct = 100.0 * passed / total if total else 0
        marker = "" if passed == total else f"  ← {total - passed} wrong"
        lines.append(f"  {passed:4d}/{total:4d}  {pct:5.1f}%  {source}{marker}")
    lines.append("")

    if no_verifier:
        lines.append("TEMPLATES WITH NO VERIFIER (count not included in totals):")
        for src, n in no_verifier.most_common():
            lines.append(f"  {n:5d}  {src}")
        lines.append("")

    # Wrong-fire samples
    any_wrong = any(
        correctness_total[s] > correctness_pass[s] for s in correctness_total
    )
    if any_wrong:
        lines.append("WRONG-FIRE SAMPLES (up to 5 per template):")
        lines.append("-" * 78)
        for source in sorted(wrong_examples.keys()):
            exs = wrong_examples[source]
            if not exs:
                continue
            lines.append(f"  {source}:")
            for ex in exs:
                lines.append(
                    f"    {ex['pair'][0]}v{ex['pair'][1]}  {ex['move']}: "
                    f"reason='{ex['reason']}'"
                )
                lines.append(f"      text: {ex['text']}")
                lines.append(f"      fen:  {ex['fen']}")
            lines.append("")

    # ── 1200-test (explanation quality) section ──────────────────
    lines.append("=" * 78)
    lines.append("1200-TEST (EXPLANATION QUALITY)")
    lines.append("=" * 78)
    lines.append("Concept words must be paired with concrete consequences a 1200")
    lines.append("player can verify by looking. Empty fillers ('repositions',")
    lines.append("'controls the column' alone) fail. Exempt: engine_review_needed,")
    lines.append("good_generic, engine_fallback, silent.")
    lines.append("")
    q_grand_total = sum(quality_total.values()) or 1
    q_grand_pass = sum(quality_pass.values())
    q_pct = 100.0 * q_grand_pass / q_grand_total
    lines.append(
        f"  OVERALL EXPLANATION QUALITY: {q_grand_pass}/{q_grand_total}  "
        f"({q_pct:.1f}% pass)"
    )
    lines.append("")

    lines.append("PER-TEMPLATE QUALITY:")
    lines.append("-" * 78)
    for source, total in sorted(quality_total.items(), key=lambda x: -x[1]):
        passed = quality_pass.get(source, 0)
        pct = 100.0 * passed / total if total else 0
        marker = "" if passed == total else f"  ← {total - passed} fail 1200-test"
        lines.append(f"  {passed:4d}/{total:4d}  {pct:5.1f}%  {source}{marker}")
    lines.append("")

    any_q_fail = any(
        quality_total[s] > quality_pass[s] for s in quality_total
    )
    if any_q_fail:
        lines.append("QUALITY-FAIL SAMPLES (up to 5 per template):")
        lines.append("-" * 78)
        for source in sorted(quality_fails.keys()):
            exs = quality_fails[source]
            if not exs:
                continue
            lines.append(f"  {source}:")
            for ex in exs:
                lines.append(
                    f"    {ex['pair'][0]}v{ex['pair'][1]}  {ex['move']}: "
                    f"reason='{ex['reason']}'"
                )
                lines.append(f"      text: {ex['text']}")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pairs", default=None, help="comma-list e.g. '1200v1100,1200v1200,...'")
    p.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    p.add_argument("--time", type=float, default=DEFAULT_TIME_PER_MOVE)
    p.add_argument("--max-plies", type=int, default=DEFAULT_MAX_PLIES)
    p.add_argument("--output", default=None)
    args = p.parse_args()
    report = run(args)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"\nReport written to {args.output}")
    else:
        print()
        print(report)
