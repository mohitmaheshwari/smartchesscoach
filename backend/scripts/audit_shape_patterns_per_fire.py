"""
Per-fire shape-pattern audit.

For each pattern_id that has fired in the corpus, sample N records and
run a POST-HOC GEOMETRIC VERIFIER against the fen_before. The verifier
is independent of the detector — it re-checks the geometry the
detector CLAIMED to find. Mismatches indicate detector bugs or
backfill corruption.

What this audits:
  - Detector-side geometry: does the fired pattern actually hold on the board?
  - Backfill-side write: do persisted fields match what re-detection produces?
  - Schema: are the required fields populated?

What this does NOT audit:
  - Whether the pattern is the most-teaching-worthy thing about the position.
  - Whether the engine actually plays the fork / exploits the pattern.
  - The rendered caption string vs the position (that's a separate layer).

Output:
  - Per-pattern: ok / mismatch / sample-FENs
  - Mismatches listed with reason and side-by-side claimed vs. observed

Usage:
    docker exec chess-coach-backend python scripts/audit_shape_patterns_per_fire.py
    docker exec chess-coach-backend python scripts/audit_shape_patterns_per_fire.py --samples 20
    docker exec chess-coach-backend python scripts/audit_shape_patterns_per_fire.py --pattern free_piece --samples 50
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import chess
from motor.motor_asyncio import AsyncIOMotorClient

from services.shape_patterns import PATTERNS_BY_ID
from services.caption_facts import PIECE_VALUE_CP

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


# ────────────────────────────────────────────────────────────────────
# Post-hoc verifiers — re-check geometry independent of detector code.
# Each returns (ok: bool, reason: str). Reason explains WHY a mismatch
# occurred so we can fix the detector.
# ────────────────────────────────────────────────────────────────────

def _sq(name: str) -> int:
    return chess.parse_square(name)


def _verify_free_piece(board: chess.Board, mover: str, targets: List[str],
                       executing_move: Optional[str]) -> Tuple[bool, str]:
    """Free piece: target is enemy ≥knight, zero defenders, attacker exists."""
    if not targets:
        return False, "no targets"
    tgt = _sq(targets[0])
    p = board.piece_at(tgt)
    them = not board.turn
    if not p or p.color != them:
        return False, f"target {targets[0]} not enemy piece"
    if p.piece_type == chess.KING:
        return False, "target is king"
    if PIECE_VALUE_CP.get(p.piece_type, 0) < 300:
        return False, f"target value {PIECE_VALUE_CP.get(p.piece_type, 0)} < knight"
    if board.attackers(them, tgt):
        return False, "target has defenders (not free)"
    if not board.attackers(board.turn, tgt):
        return False, "no own attacker on target"
    return True, "ok"


def _verify_knight_fork(board: chess.Board, mover: str, targets: List[str],
                        executing_move: Optional[str]) -> Tuple[bool, str]:
    """Knight fork: ≥2 enemy targets (≥knight or king) on knight L-jumps from landing."""
    if len(targets) < 2:
        return False, "<2 targets"
    them = not board.turn
    # Resolve the landing square: if executing_move, use its to_square; else mover stays put.
    if executing_move:
        try:
            landing = chess.Move.from_uci(executing_move).to_square
        except Exception:
            return False, "bad executing_move uci"
    elif mover:
        landing = _sq(mover)
    else:
        return False, "no mover or executing_move"
    # 8 knight jumps from landing
    f0, r0 = chess.square_file(landing), chess.square_rank(landing)
    jumps = []
    for df, dr in [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]:
        f, r = f0+df, r0+dr
        if 0 <= f < 8 and 0 <= r < 8:
            jumps.append(chess.square(f, r))
    fork_targets = []
    for t_name in targets:
        t = _sq(t_name)
        if t not in jumps:
            return False, f"target {t_name} not on knight L-jump from {chess.square_name(landing)}"
        p = board.piece_at(t)
        if not p:
            return False, f"target {t_name} empty"
        if p.color != them:
            return False, f"target {t_name} is own piece"
        is_valuable = p.piece_type == chess.KING or PIECE_VALUE_CP.get(p.piece_type, 0) >= 300
        if not is_valuable:
            return False, f"target {t_name} value < knight and not king"
        fork_targets.append(t)
    if len(fork_targets) < 2:
        return False, "<2 valid fork targets"
    return True, "ok"


def _verify_slider_fork(board: chess.Board, mover: str, targets: List[str],
                        executing_move: Optional[str], piece_type: int,
                        dirs: List[Tuple[int, int]]) -> Tuple[bool, str]:
    """Bishop/rook fork: ≥2 enemy targets reachable on slider rays from landing.

    For case-B (move-into-fork) fires, the verifier must walk rays on the
    POST-MOVE board, otherwise the slider's original square blocks the ray.
    """
    if len(targets) < 2:
        return False, "<2 targets"
    them = not board.turn
    # Decide: pre-move board for case A (already-forking), post-move board for case B.
    work_board = board
    if executing_move:
        try:
            mv = chess.Move.from_uci(executing_move)
        except Exception:
            return False, "bad executing_move uci"
        landing = mv.to_square
        work_board = board.copy()
        try:
            work_board.push(mv)
        except Exception:
            return False, "executing_move not legal in pre-move board"
    elif mover:
        landing = _sq(mover)
    else:
        return False, "no mover or executing_move"
    # Reach: rays from landing on the work_board, stop at first piece (which IS attacked).
    reach = set()
    for d in dirs:
        f, r = chess.square_file(landing), chess.square_rank(landing)
        while True:
            f += d[0]; r += d[1]
            if not (0 <= f < 8 and 0 <= r < 8):
                break
            sq = chess.square(f, r)
            reach.add(sq)
            if work_board.piece_at(sq):
                break
    for t_name in targets:
        t = _sq(t_name)
        if t not in reach:
            return False, f"target {t_name} not reachable from {chess.square_name(landing)} along given rays"
        p = work_board.piece_at(t)
        if not p or p.color != them:
            return False, f"target {t_name} not enemy piece"
    return True, "ok"


def _verify_bishop_fork(board, mover, targets, ex):
    return _verify_slider_fork(board, mover, targets, ex, chess.BISHOP,
                                [(1,1),(1,-1),(-1,1),(-1,-1)])


def _verify_rook_fork(board, mover, targets, ex):
    return _verify_slider_fork(board, mover, targets, ex, chess.ROOK,
                                [(1,0),(-1,0),(0,1),(0,-1)])


def _verify_pin_or_skewer(board: chess.Board, mover: str, targets: List[str],
                          executing_move: Optional[str], pattern: str) -> Tuple[bool, str]:
    """Pin/skewer: own slider sees enemy_front then enemy_back on same ray."""
    if len(targets) != 2 or not mover:
        return False, "need exactly 2 targets and mover"
    them = not board.turn
    slider_sq = _sq(mover)
    p_slider = board.piece_at(slider_sq)
    if not p_slider or p_slider.color != board.turn:
        return False, f"slider on {mover} not own piece"
    if p_slider.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return False, f"slider on {mover} is {p_slider.piece_type}"
    front, back = _sq(targets[0]), _sq(targets[1])
    # Walk every direction from slider; find one where the first hit is `front` and second is `back`.
    diag = [(1,1),(1,-1),(-1,1),(-1,-1)]
    ortho = [(1,0),(-1,0),(0,1),(0,-1)]
    if p_slider.piece_type == chess.BISHOP:
        dirs = diag
    elif p_slider.piece_type == chess.ROOK:
        dirs = ortho
    else:
        dirs = diag + ortho
    found = False
    for d in dirs:
        f, r = chess.square_file(slider_sq), chess.square_rank(slider_sq)
        hits = []
        while True:
            f += d[0]; r += d[1]
            if not (0 <= f < 8 and 0 <= r < 8):
                break
            sq = chess.square(f, r)
            if board.piece_at(sq):
                hits.append(sq)
                if len(hits) == 2:
                    break
        if len(hits) == 2 and hits[0] == front and hits[1] == back:
            found = True
            break
    if not found:
        return False, f"slider {mover} does not see {targets[0]} then {targets[1]} on any ray"
    p_front = board.piece_at(front)
    p_back = board.piece_at(back)
    if not p_front or p_front.color != them or not p_back or p_back.color != them:
        return False, "front/back not both enemy"
    v_front = 10_000 if p_front.piece_type == chess.KING else PIECE_VALUE_CP.get(p_front.piece_type, 0)
    v_back = 10_000 if p_back.piece_type == chess.KING else PIECE_VALUE_CP.get(p_back.piece_type, 0)
    if pattern == "pin":
        if p_front.piece_type == chess.KING:
            return False, "pin: front is king (skewer)"
        if v_back <= v_front:
            return False, f"pin: back value {v_back} not > front {v_front}"
    elif pattern == "skewer":
        if v_front <= v_back:
            return False, f"skewer: front value {v_front} not > back {v_back}"
    return True, "ok"


def _verify_back_rank_trap(board, mover, targets, ex):
    """King on back rank, all 3 forward squares blocked by own pieces, open file exists, we have R/Q."""
    if not targets:
        return False, "no targets"
    them = not board.turn
    them_king = board.king(them)
    if them_king is None:
        return False, "no enemy king"
    back = 7 if them == chess.BLACK else 0
    if chess.square_rank(them_king) != back:
        return False, "enemy king not on back rank"
    forward = 6 if them == chess.BLACK else 1
    f0 = chess.square_file(them_king)
    for df in (-1, 0, 1):
        f = f0 + df
        if not (0 <= f < 8):
            continue
        sq = chess.square(f, forward)
        p = board.piece_at(sq)
        if not p or p.color != them:
            return False, f"escape square {chess.square_name(sq)} not blocked by own"
    if not (board.pieces(chess.ROOK, board.turn) or board.pieces(chess.QUEEN, board.turn)):
        return False, "no R or Q to deliver"
    return True, "ok"


def _verify_hidden_attack(board, mover, targets, ex):
    """Own piece in front, enemy ≥knight or king behind, on same slider ray."""
    if not mover or not targets:
        return False, "missing mover or targets"
    them = not board.turn
    front = _sq(mover)
    back = _sq(targets[0])
    p_front = board.piece_at(front)
    p_back = board.piece_at(back)
    if not p_front or p_front.color != board.turn:
        return False, "front not own piece"
    if not p_back or p_back.color != them:
        return False, "back not enemy piece"
    is_valuable = p_back.piece_type == chess.KING or PIECE_VALUE_CP.get(p_back.piece_type, 0) >= 300
    if not is_valuable:
        return False, "back not valuable"
    # Walk rays from any own slider through front to back.
    diag = [(1,1),(1,-1),(-1,1),(-1,-1)]
    ortho = [(1,0),(-1,0),(0,1),(0,-1)]
    for piece_type, dirs in ((chess.BISHOP, diag), (chess.ROOK, ortho), (chess.QUEEN, diag + ortho)):
        for s_sq in board.pieces(piece_type, board.turn):
            for d in dirs:
                f, r = chess.square_file(s_sq), chess.square_rank(s_sq)
                hits = []
                while True:
                    f += d[0]; r += d[1]
                    if not (0 <= f < 8 and 0 <= r < 8):
                        break
                    sq = chess.square(f, r)
                    if board.piece_at(sq):
                        hits.append(sq)
                        if len(hits) == 2:
                            break
                if len(hits) == 2 and hits[0] == front and hits[1] == back:
                    return True, "ok"
    return False, "no slider sees front-then-back ray"


def _verify_free_pawn(board, mover, targets, ex):
    """Own pawn with no enemy pawn on same or adjacent files between it and promotion."""
    if not mover:
        return False, "no mover"
    sq = _sq(mover)
    p = board.piece_at(sq)
    us = board.turn
    if not p or p.color != us or p.piece_type != chess.PAWN:
        return False, "mover not own pawn"
    direction = 1 if us == chess.WHITE else -1
    promo = 7 if us == chess.WHITE else 0
    f0, r0 = chess.square_file(sq), chess.square_rank(sq)
    for df in (-1, 0, 1):
        ef = f0 + df
        if not (0 <= ef < 8):
            continue
        er = r0 + direction
        while er != (promo + direction):
            cand = chess.square(ef, er)
            pc = board.piece_at(cand)
            if pc and pc.piece_type == chess.PAWN and pc.color != us:
                return False, f"enemy pawn on {chess.square_name(cand)} blocks promotion path"
            er += direction
    return True, "ok"


def _verify_double_attack_line(board, mover, targets, ex):
    """Two own compatible sliders stacked on same line."""
    if not mover or not targets:
        return False, "need mover + target"
    a = _sq(mover); b = _sq(targets[0])
    pa = board.piece_at(a); pb = board.piece_at(b)
    if not pa or not pb or pa.color != board.turn or pb.color != board.turn:
        return False, "not both own pieces"
    # They must be on same file, rank, or diagonal.
    fa, ra = chess.square_file(a), chess.square_rank(a)
    fb, rb = chess.square_file(b), chess.square_rank(b)
    df = fb - fa; dr = rb - ra
    if df == 0 and dr == 0:
        return False, "same square"
    if not (df == 0 or dr == 0 or abs(df) == abs(dr)):
        return False, "not on same line"
    return True, "ok"


def _verify_no_safe_square(board, mover, targets, ex):
    """Enemy piece exists on target with at least one own attacker."""
    if not targets:
        return False, "no targets"
    them = not board.turn
    tgt = _sq(targets[0])
    p = board.piece_at(tgt)
    if not p or p.color != them:
        return False, "target not enemy piece"
    if not board.attackers(board.turn, tgt):
        return False, "no own attacker on target"
    return True, "ok"


def _verify_tired_defender(board, mover, targets, ex):
    """First target is enemy piece that defends each subsequent enemy target."""
    if len(targets) < 3:
        return False, "<3 targets (defender + 2 defended)"
    them = not board.turn
    x_sq = _sq(targets[0])
    x = board.piece_at(x_sq)
    if not x or x.color != them:
        return False, "defender not enemy piece"
    for t_name in targets[1:]:
        y = _sq(t_name)
        if x_sq not in board.attackers(them, y):
            return False, f"defender {targets[0]} doesn't defend {t_name}"
    return True, "ok"


def _verify_remove_the_guard(board, mover, targets, ex):
    """First target X is guard; second target Y depends only on X."""
    if len(targets) != 2 or not mover:
        return False, "need 2 targets + mover"
    them = not board.turn
    x_sq = _sq(targets[0]); y_sq = _sq(targets[1])
    x = board.piece_at(x_sq); y = board.piece_at(y_sq)
    if not x or x.color != them or not y or y.color != them:
        return False, "x or y not enemy"
    if x_sq not in board.attackers(them, y_sq):
        return False, "x not defending y"
    other_defenders = [s for s in board.attackers(them, y_sq) if s != x_sq]
    if other_defenders:
        return False, f"y has other defenders besides x: {[chess.square_name(s) for s in other_defenders]}"
    if not board.attackers(board.turn, x_sq):
        return False, "we have no attacker on x"
    if not board.attackers(board.turn, y_sq):
        return False, "we have no attacker on y"
    return True, "ok"


def _verify_knight_mate(board, mover, targets, ex):
    """Enemy king with all surrounding squares occupied; own knight delivers check."""
    them = not board.turn
    them_king = board.king(them)
    if them_king is None:
        return False, "no enemy king"
    kf, kr = chess.square_file(them_king), chess.square_rank(them_king)
    for df in (-1,0,1):
        for dr in (-1,0,1):
            if df == 0 and dr == 0:
                continue
            f, r = kf+df, kr+dr
            if not (0 <= f < 8 and 0 <= r < 8):
                continue
            sq = chess.square(f, r)
            if not board.piece_at(sq):
                return False, f"escape square {chess.square_name(sq)} not occupied"
    return True, "ok"


def _verify_queen_knight_mate(board, mover, targets, ex):
    """Own queen + knight both within 3 squares of enemy king."""
    them = not board.turn
    them_king = board.king(them)
    if them_king is None:
        return False, "no enemy king"
    queens = list(board.pieces(chess.QUEEN, board.turn))
    knights = list(board.pieces(chess.KNIGHT, board.turn))
    if not queens or not knights:
        return False, "missing queen or knight"
    kf, kr = chess.square_file(them_king), chess.square_rank(them_king)
    def near(sq):
        return max(abs(chess.square_file(sq)-kf), abs(chess.square_rank(sq)-kr)) <= 3
    if any(near(q) for q in queens) and any(near(n) for n in knights):
        return True, "ok"
    return False, "queen and knight not both within 3 of king"


def _verify_strong_knight_square(board, mover, targets, ex):
    """Own knight on advanced rank, defended by pawn, no enemy pawn can attack."""
    if not mover:
        return False, "no mover"
    sq = _sq(mover)
    p = board.piece_at(sq)
    us = board.turn
    if not p or p.color != us or p.piece_type != chess.KNIGHT:
        return False, "mover not own knight"
    target_ranks = (3,4,5) if us == chess.WHITE else (2,3,4)
    if chess.square_rank(sq) not in target_ranks:
        return False, f"knight on rank {chess.square_rank(sq)+1} not advanced"
    defended_by_pawn = any(
        board.piece_at(atk_sq) and board.piece_at(atk_sq).piece_type == chess.PAWN
        for atk_sq in board.attackers(us, sq)
    )
    if not defended_by_pawn:
        return False, "knight not defended by pawn"
    return True, "ok"


def _verify_weak_squares(board, mover, targets, ex):
    """≥4 same-parity squares around enemy king + enemy has no bishop of that parity."""
    them = not board.turn
    them_king = board.king(them)
    if them_king is None:
        return False, "no enemy king"
    if len(targets) < 4:
        return False, f"only {len(targets)} target squares"
    parities = [(chess.square_file(_sq(t)) + chess.square_rank(_sq(t))) % 2 for t in targets]
    if len(set(parities)) != 1:
        return False, "targets are mixed parity"
    p = parities[0]
    their_bishops = list(board.pieces(chess.BISHOP, them))
    has_matching = any((chess.square_file(b) + chess.square_rank(b)) % 2 == p for b in their_bishops)
    if has_matching:
        return False, "enemy has a bishop of that parity"
    return True, "ok"


def _verify_open_long_line(board, mover, targets, ex):
    """Long diagonal: enemy bishop of that color absent, we have B/Q to exploit."""
    them = not board.turn
    if not targets:
        return False, "no targets"
    # Determine which diagonal by inspecting first target
    t = _sq(targets[0])
    on_a1h8 = chess.square_file(t) == chess.square_rank(t)
    on_a8h1 = chess.square_file(t) + chess.square_rank(t) == 7
    if not (on_a1h8 or on_a8h1):
        return False, "target not on a long diagonal"
    # Enemy bishop parity required absent
    parity = 0 if on_a1h8 else 1  # a1=(0,0) sum 0 (parity 0); a8=(0,7) sum 7 (parity 1)
    their_b = list(board.pieces(chess.BISHOP, them))
    has = any((chess.square_file(b) + chess.square_rank(b)) % 2 == parity for b in their_b)
    if has:
        return False, "enemy bishop of that parity still on board"
    # We must have own B (same parity) or Q
    our_b = list(board.pieces(chess.BISHOP, board.turn))
    has_our = any((chess.square_file(b) + chess.square_rank(b)) % 2 == parity for b in our_b)
    if not has_our and not board.pieces(chess.QUEEN, board.turn):
        return False, "no own B (matching) or Q to exploit"
    return True, "ok"


def _verify_long_diagonal_bishop(board, mover, targets, ex):
    """Own bishop on a long diagonal with ≥5 empty squares along it."""
    if not mover:
        return False, "no mover"
    sq = _sq(mover)
    p = board.piece_at(sq)
    if not p or p.color != board.turn or p.piece_type != chess.BISHOP:
        return False, "mover not own bishop"
    on_a1h8 = chess.square_file(sq) == chess.square_rank(sq)
    on_a8h1 = chess.square_file(sq) + chess.square_rank(sq) == 7
    if not (on_a1h8 or on_a8h1):
        return False, "bishop not on a long diagonal"
    diag = ([(i,i) for i in range(8)] if on_a1h8 else [(i,7-i) for i in range(8)])
    diag_sqs = [chess.square(f,r) for f,r in diag]
    empty = sum(1 for s in diag_sqs if s != sq and not board.piece_at(s))
    if empty < 5:
        return False, f"only {empty} empty squares on diagonal"
    return True, "ok"


def _verify_pawn_hole_fianchetto(board, mover, targets, ex):
    """Enemy played g6/g3/b6/b3 AND matching-color bishop entirely gone."""
    them = not board.turn
    if not targets:
        return False, "no targets"
    hole_sq = _sq(targets[0])
    hole_name = chess.square_name(hole_sq)
    if hole_name not in ("g6","g3","b6","b3"):
        return False, f"hole {hole_name} not a fianchetto square"
    p = board.piece_at(hole_sq)
    if not p or p.piece_type != chess.PAWN or p.color != them:
        return False, "fianchetto pawn missing from hole"
    parity_needed = {"g6":0, "b6":1, "g3":1, "b3":0}[hole_name]
    their_b = list(board.pieces(chess.BISHOP, them))
    has = any((chess.square_file(b) + chess.square_rank(b)) % 2 == parity_needed for b in their_b)
    if has:
        return False, "matching-color bishop still on board"
    return True, "ok"


def _verify_h7_attack(board, mover, targets, ex):
    """Bishop bears on h7/h2, enemy king on g8/g1 area, no f6/f3 knight defender, h-pawn present."""
    if not targets:
        return False, "no targets"
    them = not board.turn
    target_sq = _sq(targets[0])
    if chess.square_name(target_sq) not in ("h7","h2"):
        return False, "target not h7/h2"
    # h-pawn must be there
    p_h = board.piece_at(target_sq)
    if not p_h or p_h.piece_type != chess.PAWN or p_h.color != them:
        return False, "h-pawn missing"
    # Our bishop must attack target
    bishop_atks = [s for s in board.attackers(board.turn, target_sq)
                   if board.piece_at(s) and board.piece_at(s).piece_type == chess.BISHOP]
    if not bishop_atks:
        return False, "no own bishop attacks h-target"
    # Defender knight on f6/f3 must NOT be there
    f_sq = _sq("f6" if them == chess.BLACK else "f3")
    p_f = board.piece_at(f_sq)
    if p_f and p_f.piece_type == chess.KNIGHT and p_f.color == them:
        return False, "knight defender still present"
    return True, "ok"


def _verify_force_the_king(board, mover, targets, ex):
    """Permissive: just check that executing_move is legal AND gives check."""
    if not ex:
        return False, "no executing_move"
    try:
        mv = chess.Move.from_uci(ex)
    except Exception:
        return False, "bad uci"
    if mv not in board.legal_moves:
        return False, "executing_move not legal"
    if not board.gives_check(mv):
        return False, "executing_move doesn't check"
    return True, "ok"


def _verify_in_between_move(board, mover, targets, ex):
    """Permissive: executing_move is legal AND gives check."""
    if not ex:
        return False, "no executing_move"
    try:
        mv = chess.Move.from_uci(ex)
    except Exception:
        return False, "bad uci"
    if mv not in board.legal_moves:
        return False, "not legal"
    if not board.gives_check(mv):
        return False, "doesn't check"
    return True, "ok"


_VERIFIERS = {
    "free_piece":              _verify_free_piece,
    "free_pawn":               _verify_free_pawn,
    "knight_fork":             _verify_knight_fork,
    "bishop_fork":             _verify_bishop_fork,
    "rook_fork":               _verify_rook_fork,
    "pin":                     lambda b,m,t,e: _verify_pin_or_skewer(b,m,t,e,"pin"),
    "skewer":                  lambda b,m,t,e: _verify_pin_or_skewer(b,m,t,e,"skewer"),
    "hidden_attack":           _verify_hidden_attack,
    "double_attack_line":      _verify_double_attack_line,
    "back_rank_trap":          _verify_back_rank_trap,
    "h7_attack":               _verify_h7_attack,
    "queen_knight_mate":       _verify_queen_knight_mate,
    "knight_mate":             _verify_knight_mate,
    "no_safe_square":          _verify_no_safe_square,
    "tired_defender":          _verify_tired_defender,
    "remove_the_guard":        _verify_remove_the_guard,
    "force_the_king":          _verify_force_the_king,
    "in_between_move":         _verify_in_between_move,
    "strong_knight_square":    _verify_strong_knight_square,
    "weak_squares":            _verify_weak_squares,
    "open_long_line":          _verify_open_long_line,
    "long_diagonal_bishop":    _verify_long_diagonal_bishop,
    "pawn_hole_fianchetto":    _verify_pawn_hole_fianchetto,
}


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--samples", type=int, default=10,
                    help="Random samples per pattern (default 10)")
    ap.add_argument("--pattern", type=str, default=None,
                    help="Audit only one pattern_id")
    ap.add_argument("--show-fens", action="store_true",
                    help="Print FEN for every sample (good for visual check)")
    args = ap.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    if args.pattern:
        pattern_ids = [args.pattern]
    else:
        pattern_ids = sorted(PATTERNS_BY_ID.keys())

    print(f"\n── Per-fire shape-pattern audit ─────────────────────")
    print(f"  Samples per pattern: {args.samples}")
    print(f"  Patterns: {len(pattern_ids)}")
    print()

    grand_total_ok = 0
    grand_total_fail = 0
    grand_mismatch_examples: List[Dict] = []

    for pid in pattern_ids:
        verifier = _VERIFIERS.get(pid)
        if not verifier:
            print(f"  [{pid}] no verifier — skipping")
            continue
        # Mongo aggregation: sample N random move records with shape_pattern_id == pid
        pipeline = [
            {"$match": {"decryption_v5_data.shape_pattern_id": pid}},
            {"$project": {"decryption_v5_data": 1, "game_id": 1}},
            {"$unwind": "$decryption_v5_data"},
            {"$match": {"decryption_v5_data.shape_pattern_id": pid}},
            {"$sample": {"size": args.samples}},
        ]
        records = await db.game_analyses.aggregate(pipeline).to_list(args.samples)
        if not records:
            print(f"  [{pid}] no fires in corpus — skipping")
            continue
        ok = 0
        fail = 0
        fail_reasons = {}
        for r in records:
            rec = r["decryption_v5_data"]
            fen = rec.get("fen_before")
            mover = rec.get("shape_pattern_mover")
            targets = rec.get("shape_pattern_targets") or []
            ex = rec.get("shape_pattern_executing_move")
            if not fen:
                fail += 1
                fail_reasons["no_fen"] = fail_reasons.get("no_fen", 0) + 1
                continue
            try:
                board = chess.Board(fen)
            except Exception as exc:
                fail += 1
                fail_reasons[f"bad_fen:{exc}"] = fail_reasons.get(f"bad_fen:{exc}", 0) + 1
                continue
            try:
                passed, reason = verifier(board, mover, targets, ex)
            except Exception as exc:
                fail += 1
                fail_reasons[f"verifier_crash:{exc}"] = fail_reasons.get(f"verifier_crash:{exc}", 0) + 1
                continue
            if passed:
                ok += 1
                if args.show_fens:
                    print(f"    OK [{pid}] {fen}")
            else:
                fail += 1
                fail_reasons[reason] = fail_reasons.get(reason, 0) + 1
                if len(grand_mismatch_examples) < 25:
                    grand_mismatch_examples.append({
                        "pattern": pid,
                        "reason": reason,
                        "fen": fen,
                        "mover": mover,
                        "targets": targets,
                        "executing_move": ex,
                        "game_id": r.get("game_id"),
                    })
        grand_total_ok += ok
        grand_total_fail += fail
        status = "OK " if fail == 0 else "FP "
        print(f"  [{status}] {pid:25s}  ok={ok:3d}  fail={fail:3d}  rate={ok}/{ok+fail}")
        if fail_reasons:
            for reason, cnt in sorted(fail_reasons.items(), key=lambda x: -x[1])[:3]:
                print(f"        - {cnt}x  {reason}")

    total = grand_total_ok + grand_total_fail
    if total == 0:
        print("\nNo records audited.")
        return
    pct = 100.0 * grand_total_ok / total
    print(f"\n── Summary ──────────────────────────────────────────")
    print(f"  ok:    {grand_total_ok}")
    print(f"  fail:  {grand_total_fail}")
    print(f"  pct:   {pct:.1f}%")
    if grand_mismatch_examples and grand_total_fail > 0:
        print(f"\n── First {min(len(grand_mismatch_examples), 10)} mismatches (paste FEN into chess.com/lichess analysis) ──")
        for ex in grand_mismatch_examples[:10]:
            print(f"  [{ex['pattern']}] {ex['reason']}")
            print(f"    FEN: {ex['fen']}")
            print(f"    mover={ex['mover']} targets={ex['targets']} executing={ex['executing_move']}")


if __name__ == "__main__":
    asyncio.run(main())
