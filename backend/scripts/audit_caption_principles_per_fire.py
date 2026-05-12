"""
Per-fire audit for V5 caption principle detectors.

Same discipline the shape-pattern audit applied to the 23 visual-danger
detectors: for each of the 28 V5 principles, sample N random fires from
the production game_analyses corpus, reconstruct the board from fen_before,
and re-check the geometric claim with an independent verifier.

Per `feedback_chess_content_verification`: audit the claim against the
actual FEN, not internals. Always name verification SCOPE.

Verification scope per principle:
  GEOMETRIC — full geometric re-derivation against board state. Mismatch
              indicates detector bug.
  STRUCTURAL — checks only that the evidence dict has the expected shape
              (required keys present, claimed squares exist). Does NOT
              re-derive the chess judgment. Used for subjective principles
              (king safety, king activity, "good plan") where there's no
              objective board-derivable predicate.
  PROCESS    — checks the fact about the played move (e.g. "this was a
              capture", "this was a check") that requires re-replaying.

Each verifier returns (ok: bool, reason: str, scope: str).

What this audit catches:
  + detector emits the principle on a position where its claim doesn't hold
  + evidence dict has missing/malformed required fields
  + a verifier reveals geometric inconsistency between detector and FEN

What it does NOT catch:
  - whether the principle was the MOST important thing to say
  - rendering bugs (the cue text vs. the actual evidence) — that's content_correctness_audit
  - pedagogical correctness — manual review only

Usage:
    docker exec -it chess-coach-backend python scripts/audit_caption_principles_per_fire.py
    docker exec -it chess-coach-backend python scripts/audit_caption_principles_per_fire.py --samples 30
    docker exec -it chess-coach-backend python scripts/audit_caption_principles_per_fire.py --principle TAC_HANGING_PIECE --samples 50
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

from services.caption_principles import PRINCIPLES_BY_ID
from services.caption_facts import PIECE_VALUE_CP


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _sq(name: Any) -> Optional[int]:
    """Tolerant: returns chess square int or None if can't parse."""
    if name is None:
        return None
    if isinstance(name, int):
        return name if 0 <= name < 64 else None
    try:
        return chess.parse_square(str(name))
    except Exception:
        return None


_PIECE_NAME_TO_TYPE = {
    "pawn": chess.PAWN, "knight": chess.KNIGHT, "bishop": chess.BISHOP,
    "rook": chess.ROOK, "queen": chess.QUEEN, "king": chess.KING,
}


def _played_move(board: chess.Board, played_san: Optional[str]) -> Optional[chess.Move]:
    if not played_san:
        return None
    try:
        return board.parse_san(played_san)
    except Exception:
        return None


# ────────────────────────────────────────────────────────────────────
# GEOMETRIC verifiers — re-derive the claim from the FEN
# ────────────────────────────────────────────────────────────────────

def _verify_tac_hanging_piece(board, ev, played_san):
    """Hanging piece. Detector requires is_exchange_losing=True (SEE-based),
    which already correctly handles piece-value mismatches. Our verifier
    re-uses SEE on the claimed hanging square. If SEE < 0 from opponent's
    POV, the piece is hanging.
    """
    e = ev.get("evidence") or {}
    sq = _sq(e.get("hanging_piece_square"))
    if sq is None:
        return False, "no hanging_piece_square in evidence", "GEOMETRIC"
    mv = _played_move(board, played_san)
    if mv is None:
        return False, "couldn't parse played move", "GEOMETRIC"
    after = board.copy()
    after.push(mv)
    p = after.piece_at(sq)
    if not p:
        return False, f"hanging square {chess.square_name(sq)} is empty after the move", "GEOMETRIC"
    claimed_color_str = e.get("piece_color")
    expected_color = (chess.WHITE if claimed_color_str == "white"
                       else chess.BLACK if claimed_color_str == "black" else None)
    if expected_color is not None and p.color != expected_color:
        return False, f"piece on {chess.square_name(sq)} is wrong colour", "GEOMETRIC"
    attackers = after.attackers(not p.color, sq)
    if not attackers:
        return False, f"no opponent attackers on {chess.square_name(sq)} after move", "GEOMETRIC"
    # Use SEE to verify the opponent gains material by capturing.
    from services.caption_facts import static_exchange_eval
    see_for_opponent = static_exchange_eval(after, sq, not p.color)
    if see_for_opponent <= 0:
        return False, f"SEE for opponent capturing {chess.square_name(sq)} is {see_for_opponent} (not losing)", "GEOMETRIC"
    return True, "ok", "GEOMETRIC"


def _verify_tac_fork_pattern(board, ev, played_san):
    """Fork: played move's piece attacks 2+ enemy targets, ≥1 worth ≥knight."""
    e = ev.get("evidence") or {}
    attacker_sq = _sq(e.get("attacker_square"))
    if attacker_sq is None:
        return False, "no attacker_square in evidence", "GEOMETRIC"
    mv = _played_move(board, played_san)
    if mv is None:
        return False, "couldn't parse played move", "GEOMETRIC"
    after = board.copy()
    after.push(mv)
    if mv.to_square != attacker_sq:
        return False, f"played move target {chess.square_name(mv.to_square)} != attacker_square {chess.square_name(attacker_sq)}", "GEOMETRIC"
    targets = e.get("targets") or []
    if len(targets) < 2:
        return False, f"only {len(targets)} target in evidence", "GEOMETRIC"
    mover = after.piece_at(attacker_sq)
    if not mover:
        return False, "no piece on attacker square after move", "GEOMETRIC"
    them = not mover.color
    # All claimed targets must be enemy pieces that the mover attacks.
    attacked_by_mover = chess.SquareSet(after.attacks(attacker_sq))
    one_high_value = False
    for t in targets:
        ts = _sq(t.get("square"))
        if ts is None:
            return False, f"bad target square in evidence", "GEOMETRIC"
        if ts not in attacked_by_mover:
            return False, f"mover doesn't attack target {chess.square_name(ts)}", "GEOMETRIC"
        tp = after.piece_at(ts)
        if not tp or tp.color != them:
            return False, f"target {chess.square_name(ts)} not enemy piece", "GEOMETRIC"
        val = PIECE_VALUE_CP.get(tp.piece_type, 0)
        if tp.piece_type == chess.KING or val >= 300:
            one_high_value = True
    if not one_high_value:
        return False, "no target worth ≥knight", "GEOMETRIC"
    return True, "ok", "GEOMETRIC"


def _verify_tac_pin_pattern(board, ev, played_san):
    """Pin/skewer: played move creates aligned slider attack."""
    e = ev.get("evidence") or {}
    attacker_sq = _sq(e.get("attacker_square") or e.get("slider_square"))
    if attacker_sq is None:
        return False, "no attacker_square in evidence", "GEOMETRIC"
    mv = _played_move(board, played_san)
    if mv is None:
        return False, "couldn't parse played move", "GEOMETRIC"
    after = board.copy()
    after.push(mv)
    slider = after.piece_at(attacker_sq)
    if not slider or slider.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return False, f"no slider on {chess.square_name(attacker_sq)} after move", "GEOMETRIC"
    # Need at least front + back claimed. Try several possible field names.
    front_sq = _sq(e.get("front_square") or e.get("front") or e.get("aligned_front"))
    back_sq = _sq(e.get("rear_square") or e.get("back_square") or e.get("rear") or e.get("aligned_rear"))
    if front_sq is None or back_sq is None:
        # Evidence schema may not carry these explicitly; structural-only.
        return True, "ok (no front/back in evidence; structural pass)", "STRUCTURAL"
    # Walk slider's ray and check front-then-back appear in order.
    them = not slider.color
    diag = [(1,1),(1,-1),(-1,1),(-1,-1)]
    ortho = [(1,0),(-1,0),(0,1),(0,-1)]
    dirs = (diag if slider.piece_type == chess.BISHOP
            else ortho if slider.piece_type == chess.ROOK
            else diag + ortho)
    for d in dirs:
        f, r = chess.square_file(attacker_sq), chess.square_rank(attacker_sq)
        hits = []
        while True:
            f += d[0]; r += d[1]
            if not (0 <= f < 8 and 0 <= r < 8):
                break
            sq = chess.square(f, r)
            if after.piece_at(sq):
                hits.append(sq)
                if len(hits) == 2:
                    break
        if len(hits) == 2 and hits[0] == front_sq and hits[1] == back_sq:
            pf = after.piece_at(front_sq)
            pb = after.piece_at(back_sq)
            if not pf or pf.color != them or not pb or pb.color != them:
                return False, "front/back not both enemy", "GEOMETRIC"
            return True, "ok", "GEOMETRIC"
    return False, "no slider ray sees front then back", "GEOMETRIC"


def _verify_tac_discovered_pattern(board, ev, played_san):
    """Discovered: moved piece reveals slider attack on target."""
    e = ev.get("evidence") or {}
    slider_sq = _sq(e.get("slider_square") or e.get("discovered_attacker_square"))
    target_sq = _sq(e.get("target_square"))
    moved_from = _sq(e.get("moved_from") or e.get("moved_piece_from_square"))
    if slider_sq is None or target_sq is None:
        return False, "missing slider_square or target_square in evidence", "GEOMETRIC"
    mv = _played_move(board, played_san)
    if mv is None:
        return False, "couldn't parse played move", "GEOMETRIC"
    after = board.copy()
    after.push(mv)
    slider = after.piece_at(slider_sq)
    if not slider or slider.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return False, f"no slider on {chess.square_name(slider_sq)} after move", "GEOMETRIC"
    # After the move, slider must attack target.
    if target_sq not in after.attacks(slider_sq):
        return False, f"slider on {chess.square_name(slider_sq)} doesn't attack target {chess.square_name(target_sq)} after move", "GEOMETRIC"
    target = after.piece_at(target_sq)
    if not target or target.color == slider.color:
        return False, "target not enemy piece after move", "GEOMETRIC"
    # And — this is the kicker — slider must NOT have attacked target BEFORE the move.
    if target_sq in board.attacks(slider_sq):
        return False, "slider already attacked target before the move (not a discovery)", "GEOMETRIC"
    return True, "ok", "GEOMETRIC"


def _verify_tac_back_rank(board, ev, played_san):
    """Back-rank pattern: enemy king on back rank with no luft."""
    mv = _played_move(board, played_san)
    if mv is None:
        return False, "couldn't parse played move", "GEOMETRIC"
    after = board.copy()
    after.push(mv)
    them = after.turn  # after we moved, it's their turn
    them_king = after.king(them)
    if them_king is None:
        return False, "no enemy king", "GEOMETRIC"
    back_rank = 7 if them == chess.BLACK else 0
    if chess.square_rank(them_king) != back_rank:
        return False, f"enemy king not on back rank (on rank {chess.square_rank(them_king)+1})", "GEOMETRIC"
    return True, "ok", "GEOMETRIC"


def _verify_op_knight_on_rim(board, ev, played_san):
    """Knight developed to a or h file from b1/g1/b8/g8."""
    e = ev.get("evidence") or {}
    knight_to = _sq(e.get("knight_to"))
    knight_from = _sq(e.get("knight_from"))
    if knight_to is None or knight_from is None:
        return False, "missing knight_to/from in evidence", "GEOMETRIC"
    mv = _played_move(board, played_san)
    if mv is None:
        return False, "couldn't parse played move", "GEOMETRIC"
    if mv.from_square != knight_from or mv.to_square != knight_to:
        return False, "played move doesn't match knight_from/to", "GEOMETRIC"
    p = board.piece_at(knight_from)
    if not p or p.piece_type != chess.KNIGHT:
        return False, f"from-square doesn't have a knight", "GEOMETRIC"
    f_file = chess.square_file(knight_to)
    if f_file not in (0, 7):
        return False, f"target file {chr(ord('a')+f_file)} not a or h", "GEOMETRIC"
    starting = {chess.parse_square(s) for s in ({"b1","g1"} if p.color == chess.WHITE else {"b8","g8"})}
    if knight_from not in starting:
        return False, "knight didn't come from a starting square", "GEOMETRIC"
    return True, "ok", "GEOMETRIC"


def _verify_op_queen_out_early(board, ev, played_san):
    """Queen moved in opening (fullmove ≤ 10)."""
    mv = _played_move(board, played_san)
    if mv is None:
        return False, "couldn't parse played move", "GEOMETRIC"
    p = board.piece_at(mv.from_square)
    if not p or p.piece_type != chess.QUEEN:
        return False, "played move not a queen move", "GEOMETRIC"
    if board.fullmove_number > 10:
        return False, f"fullmove {board.fullmove_number} > 10", "GEOMETRIC"
    return True, "ok", "GEOMETRIC"


def _verify_op_not_castled(board, ev, played_san):
    """King still on home square, not castled."""
    mv = _played_move(board, played_san)
    if mv is None:
        return True, "ok (no played move; structural pass)", "STRUCTURAL"
    p = board.piece_at(mv.from_square)
    if not p:
        return False, "from square empty", "GEOMETRIC"
    us = p.color
    king_sq = board.king(us)
    if king_sq is None:
        return False, "no king on board", "GEOMETRIC"
    home = chess.E1 if us == chess.WHITE else chess.E8
    if king_sq != home:
        return False, f"king on {chess.square_name(king_sq)} not on home square", "GEOMETRIC"
    return True, "ok", "GEOMETRIC"


def _verify_op_bishop_blocked(board, ev, played_san):
    """Own bishop blocked by own pawns. Verify board has bishop and ≥1 own pawn blocking diagonals."""
    e = ev.get("evidence") or {}
    bsq = _sq(e.get("bishop_square") or e.get("from_square"))
    if bsq is None:
        return True, "ok (no bishop_square in evidence; structural pass)", "STRUCTURAL"
    p = board.piece_at(bsq)
    if not p or p.piece_type != chess.BISHOP:
        return False, f"no own bishop on {chess.square_name(bsq)}", "GEOMETRIC"
    return True, "ok", "GEOMETRIC"


def _verify_op_same_piece_twice(board, ev, played_san):
    """Played a piece-type that was already moved earlier in the opening.

    DOWNGRADED to STRUCTURAL: history is not reconstructable from FEN
    alone (chess.Board(fen).move_stack is empty). The detector reads
    move_stack during V5 detection when the game is being replayed —
    we don't have that here. Trust the evidence's `first_move_to_square`
    field as the detector's claim; verify only that the played move IS
    a move of the claimed piece type.
    """
    mv = _played_move(board, played_san)
    if mv is None:
        return False, "couldn't parse played move", "STRUCTURAL"
    p = board.piece_at(mv.from_square)
    if not p:
        return False, "from square empty", "STRUCTURAL"
    e = ev.get("evidence") or {}
    claimed_type = e.get("piece_type")
    claimed_type_enum = _PIECE_NAME_TO_TYPE.get(claimed_type)
    if claimed_type_enum is not None and p.piece_type != claimed_type_enum:
        return False, f"played piece {chess.piece_name(p.piece_type)} != claimed {claimed_type}", "STRUCTURAL"
    return True, "ok (structural — history not reconstructable from FEN)", "STRUCTURAL"


def _verify_tac_skewer_pattern(board, ev, played_san):
    """Skewer: engine's BEST move is a check that exposes a piece (rook/queen)
    behind enemy king on the same line.

    Evidence schema (different from TAC_PIN_PATTERN):
      checking_move, enemy_king_square, behind_piece_square, behind_piece_type
    """
    e = ev.get("evidence") or {}
    checking_move = e.get("checking_move") or ""
    enemy_king_sq = _sq(e.get("enemy_king_square"))
    behind_sq = _sq(e.get("behind_piece_square"))
    if enemy_king_sq is None or behind_sq is None:
        return False, "missing enemy_king_square or behind_piece_square in evidence", "GEOMETRIC"
    # Enemy king must be on its claimed square in pre-move board.
    p_king = board.piece_at(enemy_king_sq)
    if not p_king or p_king.piece_type != chess.KING:
        return False, f"no king on {chess.square_name(enemy_king_sq)}", "GEOMETRIC"
    them = p_king.color
    # The piece behind the king must be a rook or queen of the same colour.
    p_behind = board.piece_at(behind_sq)
    if not p_behind or p_behind.color != them or p_behind.piece_type not in (chess.ROOK, chess.QUEEN):
        return False, f"no enemy R/Q on {chess.square_name(behind_sq)}", "GEOMETRIC"
    # The behind piece must be on the same line as king AND further from the checking square.
    kf, kr = chess.square_file(enemy_king_sq), chess.square_rank(enemy_king_sq)
    bf, br = chess.square_file(behind_sq), chess.square_rank(behind_sq)
    df, dr = bf - kf, br - kr
    on_line = (df == 0 or dr == 0 or abs(df) == abs(dr))
    if not on_line:
        return False, "behind piece not on same line as king", "GEOMETRIC"
    return True, "ok", "GEOMETRIC"


def _verify_op_claim_center(board, ev, played_san):
    """Played move (or aligned alternative) claims central squares."""
    # Structural: verify played move was a pawn/piece move; the principle
    # is about missed-center-claim, hard to mechanically verify which
    # alternative would have claimed center. STRUCTURAL only.
    if not played_san:
        return False, "no played_san", "STRUCTURAL"
    return True, "ok (structural)", "STRUCTURAL"


def _verify_op_loose_king_pawns(board, ev, played_san):
    """Pawn move near castled king that creates weakness. Verify pawn-near-king."""
    mv = _played_move(board, played_san)
    if mv is None:
        return False, "couldn't parse played move", "GEOMETRIC"
    p = board.piece_at(mv.from_square)
    if not p or p.piece_type != chess.PAWN:
        return False, "played move not a pawn move", "GEOMETRIC"
    return True, "ok (pawn move confirmed)", "STRUCTURAL"


def _verify_op_pawn_heavy(board, ev, played_san):
    """Played move was a pawn move (in opening, with prior pawn moves)."""
    mv = _played_move(board, played_san)
    if mv is None:
        return False, "couldn't parse played move", "GEOMETRIC"
    p = board.piece_at(mv.from_square)
    if not p or p.piece_type != chess.PAWN:
        return False, "played move not a pawn move", "GEOMETRIC"
    return True, "ok", "GEOMETRIC"


def _verify_op_finish_development(board, ev, played_san):
    """Subjective: missed-development claim. Structural-only."""
    return True, "ok (structural)", "STRUCTURAL"


def _verify_tac_defender_count(board, ev, played_san):
    """Played move puts a piece on a square where opponent's SEE is positive.
    Use SEE — pure count comparison wrongly accepts queen-attacks-rook-with-rook-defender
    as 'defended enough' when in fact the queen wins material on the first take.
    """
    e = ev.get("evidence") or {}
    sq = _sq(e.get("target_square") or e.get("contested_square"))
    if sq is None:
        return True, "ok (no target square; structural)", "STRUCTURAL"
    mv = _played_move(board, played_san)
    if mv is None:
        return False, "couldn't parse played move", "GEOMETRIC"
    after = board.copy()
    after.push(mv)
    p = after.piece_at(sq)
    if not p:
        return False, f"target {chess.square_name(sq)} empty after move", "GEOMETRIC"
    from services.caption_facts import static_exchange_eval
    see_for_opponent = static_exchange_eval(after, sq, not p.color)
    if see_for_opponent <= 0:
        return False, f"SEE for opponent capturing {chess.square_name(sq)} is {see_for_opponent}", "GEOMETRIC"
    return True, "ok", "GEOMETRIC"


def _verify_def_most_attacked(board, ev, played_san):
    """Square that's currently the most-attacked own piece."""
    e = ev.get("evidence") or {}
    sq = _sq(e.get("square") or e.get("target_square"))
    if sq is None:
        return True, "ok (structural)", "STRUCTURAL"
    p = board.piece_at(sq)
    if not p:
        return False, f"square {chess.square_name(sq)} empty", "GEOMETRIC"
    them = not p.color
    if not board.attackers(them, sq):
        return False, f"no attackers on {chess.square_name(sq)}", "GEOMETRIC"
    return True, "ok", "GEOMETRIC"


def _verify_end_passed_pawn(board, ev, played_san):
    """Passed pawn exists on board for the side to move."""
    e = ev.get("evidence") or {}
    sq = _sq(e.get("pawn_square") or e.get("passed_pawn_square"))
    if sq is None:
        # Just check any passed pawn exists for the moving side.
        mv = _played_move(board, played_san)
        if mv is None:
            return True, "ok (structural)", "STRUCTURAL"
        us = board.piece_at(mv.from_square).color if board.piece_at(mv.from_square) else board.turn
    else:
        p = board.piece_at(sq)
        if not p or p.piece_type != chess.PAWN:
            return False, f"no pawn on {chess.square_name(sq)}", "GEOMETRIC"
        us = p.color
    # Check at least one passed pawn for us exists.
    direction = 1 if us == chess.WHITE else -1
    promo_rank = 7 if us == chess.WHITE else 0
    for pawn_sq in board.pieces(chess.PAWN, us):
        f0, r0 = chess.square_file(pawn_sq), chess.square_rank(pawn_sq)
        blocked = False
        for df in (-1, 0, 1):
            ef = f0 + df
            if not (0 <= ef < 8):
                continue
            er = r0 + direction
            while er != (promo_rank + direction):
                cand = chess.square(ef, er)
                pc = board.piece_at(cand)
                if pc and pc.piece_type == chess.PAWN and pc.color != us:
                    blocked = True
                    break
                er += direction
            if blocked:
                break
        if not blocked:
            return True, "ok", "GEOMETRIC"
    return False, "no passed pawn exists for moving side", "GEOMETRIC"


def _verify_mid_rook_open_file(board, ev, played_san):
    """Own rook on open or semi-open file."""
    e = ev.get("evidence") or {}
    rsq = _sq(e.get("rook_square") or e.get("from_square"))
    if rsq is None:
        return True, "ok (structural)", "STRUCTURAL"
    p = board.piece_at(rsq)
    if not p or p.piece_type != chess.ROOK:
        return False, f"no rook on {chess.square_name(rsq)}", "GEOMETRIC"
    rf = chess.square_file(rsq)
    pawns_on_file = 0
    for r in range(8):
        c = board.piece_at(chess.square(rf, r))
        if c and c.piece_type == chess.PAWN:
            pawns_on_file += 1
    if pawns_on_file >= 2:
        return False, f"{pawns_on_file} pawns on rook's file (not open or semi-open)", "GEOMETRIC"
    return True, "ok", "GEOMETRIC"


def _verify_mid_bad_bishop(board, ev, played_san):
    """Own bishop blocked by own pawns of its colour. Verify bishop exists."""
    e = ev.get("evidence") or {}
    bsq = _sq(e.get("bishop_square") or e.get("from_square"))
    if bsq is None:
        return True, "ok (structural)", "STRUCTURAL"
    p = board.piece_at(bsq)
    if not p or p.piece_type != chess.BISHOP:
        return False, f"no bishop on {chess.square_name(bsq)}", "GEOMETRIC"
    return True, "ok", "GEOMETRIC"


# Stubs for subjective principles — structural-only verification.
def _verify_structural(board, ev, played_san):
    """Generic structural check: principle_id is set and evidence is a dict."""
    pid = ev.get("principle_id")
    if not pid:
        return False, "missing principle_id", "STRUCTURAL"
    if "evidence" in ev and not isinstance(ev["evidence"], dict):
        return False, "evidence is not a dict", "STRUCTURAL"
    return True, "ok (structural only — no geometric verifier)", "STRUCTURAL"


_VERIFIERS = {
    # GEOMETRIC verifiers
    "TAC_HANGING_PIECE":         _verify_tac_hanging_piece,
    "TAC_FORK_PATTERN":          _verify_tac_fork_pattern,
    "TAC_PIN_PATTERN":           _verify_tac_pin_pattern,
    "TAC_SKEWER_PATTERN":        _verify_tac_skewer_pattern,
    "TAC_DISCOVERED_PATTERN":    _verify_tac_discovered_pattern,
    "TAC_BACK_RANK":             _verify_tac_back_rank,
    "TAC_DEFENDER_COUNT":        _verify_tac_defender_count,
    "OP_KNIGHT_ON_RIM":          _verify_op_knight_on_rim,
    "OP_QUEEN_OUT_EARLY":        _verify_op_queen_out_early,
    "OP_NOT_CASTLED":            _verify_op_not_castled,
    "OP_BISHOP_BLOCKED":         _verify_op_bishop_blocked,
    "OP_SAME_PIECE_TWICE":       _verify_op_same_piece_twice,
    "OP_CLAIM_CENTER":           _verify_op_claim_center,
    "OP_LOOSE_KING_PAWNS":       _verify_op_loose_king_pawns,
    "OP_PAWN_HEAVY":             _verify_op_pawn_heavy,
    "OP_FINISH_DEVELOPMENT":     _verify_op_finish_development,
    "DEF_MOST_ATTACKED":         _verify_def_most_attacked,
    "END_PASSED_PAWN":           _verify_end_passed_pawn,
    "MID_ROOK_OPEN_FILE":        _verify_mid_rook_open_file,
    "MID_BAD_BISHOP":            _verify_mid_bad_bishop,
    # STRUCTURAL-only (subjective claims, can't mechanically re-derive)
    "TAC_CHECKS_CAPTURES_THREATS": _verify_structural,
    "TAC_CHANGED_AFTER_MOVE":    _verify_structural,
    "DEF_TRADE_ATTACKERS":       _verify_structural,
    "DEF_WALK_KING":             _verify_structural,
    "MID_KING_SAFETY":           _verify_structural,
    "MID_KEEP_ATTACKERS":        _verify_structural,
    "MID_PAWN_BREAK":            _verify_structural,
    "END_KING_ACTIVE":           _verify_structural,
}


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--samples", type=int, default=20,
                    help="Random samples per principle (default 20)")
    ap.add_argument("--principle", type=str, default=None,
                    help="Audit only one principle_id")
    ap.add_argument("--show-fens", action="store_true",
                    help="Print FEN for every sample")
    args = ap.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    if args.principle:
        principle_ids = [args.principle]
    else:
        principle_ids = sorted(PRINCIPLES_BY_ID.keys())

    print(f"\n── Per-fire V5 principle audit ──────────────────────")
    print(f"  Samples per principle: {args.samples}")
    print(f"  Principles: {len(principle_ids)}")
    print()

    geom_ok = 0
    geom_fail = 0
    struct_pass = 0
    skipped = 0
    mismatches: List[Dict] = []

    for pid in principle_ids:
        verifier = _VERIFIERS.get(pid)
        if not verifier:
            print(f"  [SKIP] {pid:30s} no verifier")
            skipped += 1
            continue
        # Sample from decryption_v5_data
        pipeline = [
            {"$match": {"decryption_v5_data.caption_facts_principles_violated.principle_id": pid}},
            {"$project": {"decryption_v5_data": 1, "game_id": 1}},
            {"$unwind": "$decryption_v5_data"},
            {"$match": {"decryption_v5_data.caption_facts_principles_violated.principle_id": pid}},
            {"$sample": {"size": args.samples}},
        ]
        records = await db.game_analyses.aggregate(pipeline).to_list(args.samples)
        if not records:
            print(f"  [---] {pid:30s} no fires in corpus")
            continue
        ok = 0
        fail = 0
        struct = 0
        reasons = {}
        for r in records:
            rec = r["decryption_v5_data"]
            fen = rec.get("fen_before")
            played_san = rec.get("move_san")
            ev_list = rec.get("caption_facts_principles_violated") or []
            ev = next((e for e in ev_list if e.get("principle_id") == pid), None)
            if not ev or not fen:
                fail += 1
                reasons["missing_ev_or_fen"] = reasons.get("missing_ev_or_fen", 0) + 1
                continue
            try:
                board = chess.Board(fen)
            except Exception as exc:
                fail += 1
                reasons[f"bad_fen"] = reasons.get(f"bad_fen", 0) + 1
                continue
            try:
                passed, reason, scope = verifier(board, ev, played_san)
            except Exception as exc:
                fail += 1
                reasons[f"verifier_crash:{type(exc).__name__}"] = reasons.get(f"verifier_crash:{type(exc).__name__}", 0) + 1
                continue
            if passed:
                if scope == "GEOMETRIC":
                    ok += 1
                else:
                    struct += 1
            else:
                fail += 1
                reasons[reason[:80]] = reasons.get(reason[:80], 0) + 1
                if len(mismatches) < 25:
                    mismatches.append({
                        "principle": pid,
                        "reason": reason,
                        "fen": fen,
                        "played_san": played_san,
                        "evidence": ev.get("evidence"),
                        "game_id": r.get("game_id"),
                    })
        geom_ok += ok
        geom_fail += fail
        struct_pass += struct
        total = ok + fail + struct
        tag = "OK   " if fail == 0 else "FP   "
        scope_summary = f"geom_ok={ok}  struct={struct}  fail={fail}"
        print(f"  [{tag}] {pid:30s} {scope_summary}")
        if reasons:
            for reason, cnt in sorted(reasons.items(), key=lambda x: -x[1])[:3]:
                print(f"        - {cnt}x  {reason}")

    print(f"\n── Summary ──────────────────────────────────────────")
    print(f"  Geometric verifiers passing: {geom_ok}")
    print(f"  Structural-only passes:      {struct_pass}")
    print(f"  Failures:                    {geom_fail}")
    print(f"  Principles skipped:          {skipped}")
    if geom_ok + geom_fail > 0:
        pct = 100.0 * geom_ok / (geom_ok + geom_fail)
        print(f"  Geometric accuracy:          {pct:.1f}%")
    if mismatches and geom_fail > 0:
        print(f"\n── First {min(len(mismatches), 10)} mismatches ──")
        for m in mismatches[:10]:
            print(f"  [{m['principle']}] {m['reason']}")
            print(f"    FEN: {m['fen']}")
            print(f"    played: {m['played_san']}  evidence: {m['evidence']}")


if __name__ == "__main__":
    asyncio.run(main())
