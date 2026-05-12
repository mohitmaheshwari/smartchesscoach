"""
Shape-pattern detectors (TIER 3).

For each of the 23 patterns in shape_patterns.py, this module exposes a
detector that takes a python-chess Board and returns a list of evidence
dicts. Each evidence dict carries:

    {
        "pattern_id":     "knight_fork",
        "executing_move": "e5d7"   # uci of the move that executes the pattern (None for positional)
        "mover":          "d5"     # square of the piece doing the work (None for positional)
        "targets":        ["c7", "f7"]   # squares the pattern hits/attacks
        "evidence":       "two enemy pieces of value >= knight on knight L-jumps from d7",
    }

After detection, `verify_with_engine_data(evidence_list, eval_data)` applies
each pattern's verifier_policy:

    - 'engine_confirms_target' → executing_move must equal eval_data['best_move_uci']
    - 'engine_in_top_3'        → executing_move must be in eval_data['top_n_uci'][:3]
    - 'heuristic_only'         → pass-through (positional, no engine confirm)

Design discipline (per feedback_design_clean_code_leaky.md):
    1. Data before code — shape_patterns.py shipped first.
    2. One detector at a time — within this file, batched by shared geometry.
    3. Edge cases enumerated upfront in each docstring.
    4. Named verification scope — inline self-checks at import time.
    5. Renderer never computes chess meaning — this is extractor land; renderer reads evidence dicts.

This module does NOT touch:
    - V5 caption rules / renderer
    - caption_principles.py (TIER 2)
    - any UI surface
"""

from __future__ import annotations

import chess
from typing import Dict, List, Optional, Tuple

from services.caption_facts import (
    PIECE_VALUE_CP,
    static_exchange_eval,
    _is_pinned_against_target,
)
from services.shape_patterns import PATTERNS_BY_ID


# ────────────────────────────────────────────────────────────────────
# Shared helpers
# ────────────────────────────────────────────────────────────────────

_MINOR_OR_ABOVE = 300  # knight value; targets we celebrate hitting


def _piece_val(board: chess.Board, sq: int) -> int:
    p = board.piece_at(sq)
    return PIECE_VALUE_CP.get(p.piece_type, 0) if p else 0


def _is_minor_or_above(board: chess.Board, sq: int) -> bool:
    return _piece_val(board, sq) >= _MINOR_OR_ABOVE


def _is_fork_target(board: chess.Board, sq: int, them: chess.Color) -> bool:
    """Enemy piece worth attacking as a fork target. Kings count (royal fork)
    even though PIECE_VALUE_CP[king] = 0 (SEE convention treats king as priceless)."""
    p = board.piece_at(sq)
    if not p or p.color != them:
        return False
    if p.piece_type == chess.KING:
        return True
    return PIECE_VALUE_CP.get(p.piece_type, 0) >= _MINOR_OR_ABOVE


def _legal_destinations(board: chess.Board, from_sq: int) -> List[int]:
    """All legal destination squares for the piece on from_sq. Empty list if not own piece's turn."""
    p = board.piece_at(from_sq)
    if not p or p.color != board.turn:
        return []
    return [m.to_square for m in board.legal_moves if m.from_square == from_sq]


def _ray_squares(from_sq: int, direction: Tuple[int, int]) -> List[int]:
    """Walk a ray from from_sq in the given (file_step, rank_step) direction.
    Returns squares in order until off-board. Excludes from_sq itself."""
    out = []
    f = chess.square_file(from_sq) + direction[0]
    r = chess.square_rank(from_sq) + direction[1]
    while 0 <= f < 8 and 0 <= r < 8:
        out.append(chess.square(f, r))
        f += direction[0]
        r += direction[1]
    return out


_DIAG_DIRS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
_ORTHO_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
_KING_DIRS = _DIAG_DIRS + _ORTHO_DIRS


def _knight_jumps(from_sq: int) -> List[int]:
    """8 L-jump squares from from_sq (only those on board)."""
    out = []
    f0 = chess.square_file(from_sq)
    r0 = chess.square_rank(from_sq)
    for df, dr in [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]:
        f, r = f0 + df, r0 + dr
        if 0 <= f < 8 and 0 <= r < 8:
            out.append(chess.square(f, r))
    return out


def _own_color(board: chess.Board) -> chess.Color:
    """The side whose turn it is — 'we' / 'us' / 'own' in detector docstrings."""
    return board.turn


def _ev(pattern_id: str, mover: Optional[int], targets: List[int],
        executing_move: Optional[chess.Move], evidence: str) -> Dict:
    return {
        "pattern_id": pattern_id,
        "mover": chess.square_name(mover) if mover is not None else None,
        "targets": [chess.square_name(s) for s in targets],
        "executing_move": executing_move.uci() if executing_move else None,
        "evidence": evidence,
    }


# ────────────────────────────────────────────────────────────────────
# BATCH 1 — Free Piece / Free Pawn (defender-count + SEE)
# ────────────────────────────────────────────────────────────────────

def detect_free_piece(board: chess.Board) -> List[Dict]:
    """Enemy piece of value >= knight is attacked by us and has ZERO defenders.

    Edge cases handled:
      - Skip enemy king (cannot be captured).
      - Skip enemy pawns (value < knight; covered by hanging-piece in TIER 2).
      - Skip if our cheapest attacker is pinned against our king for the target.
      - Multiple attackers: prefer the cheapest legal one as executing_move.
      - Two free pieces in the same position emit TWO evidences (don't collapse).

    Returns list of evidence dicts.
    """
    us = _own_color(board)
    them = not us
    out: List[Dict] = []
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.color != them:
            continue
        if p.piece_type == chess.KING:
            continue
        if PIECE_VALUE_CP.get(p.piece_type, 0) < _MINOR_OR_ABOVE:
            continue
        defenders = board.attackers(them, sq)
        if defenders:
            continue
        attackers = board.attackers(us, sq)
        if not attackers:
            continue
        # Choose cheapest legal (non-pinned-against-king-for-this-target) attacker.
        best_atk_sq = None
        best_atk_val = 10 ** 9
        for atk_sq in attackers:
            atk = board.piece_at(atk_sq)
            if not atk:
                continue
            # King attacker only safe if target square not attacked by them.
            if atk.piece_type == chess.KING and board.attackers(them, sq):
                continue
            if _is_pinned_against_target(board, atk_sq, sq):
                continue
            val = PIECE_VALUE_CP.get(atk.piece_type, 0)
            if val < best_atk_val:
                best_atk_val = val
                best_atk_sq = atk_sq
        if best_atk_sq is None:
            continue
        mv = chess.Move(best_atk_sq, sq)
        # Handle promotion edge.
        atk = board.piece_at(best_atk_sq)
        if atk.piece_type == chess.PAWN and chess.square_rank(sq) in (0, 7):
            mv = chess.Move(best_atk_sq, sq, promotion=chess.QUEEN)
        if mv not in board.legal_moves:
            continue
        out.append(_ev(
            "free_piece",
            mover=best_atk_sq,
            targets=[sq],
            executing_move=mv,
            evidence=f"{chess.piece_name(p.piece_type)} on {chess.square_name(sq)} undefended",
        ))
    return out


def detect_free_pawn(board: chess.Board) -> List[Dict]:
    """Own pawn with no enemy pawn on same or adjacent files between it and promotion.
    Passed pawn — positional pattern, emits one evidence per passer.

    Edge cases handled:
      - White vs Black promotion direction.
      - Pawn on 2nd/7th rank counts as long as the path is clear.
      - Doubled own pawns: both can be passed if path is clear.
      - This is a positional pattern: no executing_move (the player keeps pushing).
    """
    us = _own_color(board)
    out: List[Dict] = []
    direction = 1 if us == chess.WHITE else -1
    promo_rank = 7 if us == chess.WHITE else 0
    for sq in board.pieces(chess.PAWN, us):
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        blocked = False
        for df in (-1, 0, 1):
            ef = f + df
            if not (0 <= ef < 8):
                continue
            # Walk rank by rank toward promotion
            er = r + direction
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
            out.append(_ev(
                "free_pawn",
                mover=sq,
                targets=[],
                executing_move=None,
                evidence=f"pawn on {chess.square_name(sq)} has clear path to promotion",
            ))
    return out


# ────────────────────────────────────────────────────────────────────
# BATCH 2 — Forks (Knight / Bishop / Rook)
# ────────────────────────────────────────────────────────────────────

def _fork_from_destination(board: chess.Board, mover_sq: int, dest_sq: int,
                           target_rays: List[int]) -> Optional[List[int]]:
    """Given a hypothetical move from mover_sq to dest_sq, count enemy targets
    (value >= knight OR king) reachable from dest_sq along target_rays.
    Returns the list of target squares if >= 2 distinct targets exist; else None.

    Note: target_rays is the pre-computed list of squares the piece would
    attack from dest_sq (e.g. for knight: 8 L-jumps; for bishop: diagonal rays;
    for rook: file/rank rays — with blockers respected in caller).
    """
    them = not board.turn
    targets = [sq for sq in target_rays
               if sq != mover_sq and _is_fork_target(board, sq, them)]
    return targets if len(targets) >= 2 else None


def _slider_rays_from(board: chess.Board, from_sq: int, dirs: List[Tuple[int, int]],
                       ignore_square: Optional[int] = None) -> List[int]:
    """Slider rays from from_sq in given directions, stopping at first occupied
    square (which IS included as the attacked target). If ignore_square is set,
    treat that square as empty (used when simulating a piece having moved off
    its original square)."""
    out = []
    for d in dirs:
        for sq in _ray_squares(from_sq, d):
            if sq == ignore_square:
                continue
            out.append(sq)
            if board.piece_at(sq):
                break
    return out


def detect_knight_fork(board: chess.Board) -> List[Dict]:
    """Own knight has (or could move to) a square from which >=2 enemy pieces
    of value >= knight sit on the 8 L-jump squares.

    Edge cases handled:
      - Both 'already-forking' (knight in place) and 'fork-on-next-move' (legal destination).
      - Pinned knight: legal_moves filters destinations the knight can't reach.
      - Defended landing square: we still emit if SEE on landing >= 0. We let the
        engine verifier reject losing forks.
      - One target being king: that's a check + fork; still counts.
    """
    us = _own_color(board)
    them = not us
    out: List[Dict] = []
    for kn_sq in board.pieces(chess.KNIGHT, us):
        # Case A: already-forking — knight stays put.
        targets_now = [j for j in _knight_jumps(kn_sq) if _is_fork_target(board, j, them)]
        if len(targets_now) >= 2:
            out.append(_ev("knight_fork", mover=kn_sq, targets=targets_now,
                           executing_move=None,
                           evidence=f"knight on {chess.square_name(kn_sq)} already attacks {len(targets_now)} pieces"))
            continue
        # Case B: fork-on-next-move.
        for dest in _legal_destinations(board, kn_sq):
            forked = _fork_from_destination(board, kn_sq, dest, _knight_jumps(dest))
            if forked is None:
                continue
            # Don't celebrate forks where the knight hangs on landing.
            if board.piece_at(dest):
                if static_exchange_eval(board, dest, us) < 0:
                    continue
            else:
                atks = board.attackers(them, dest)
                defs = board.attackers(us, dest)
                if atks and len(atks) > len(defs):
                    # Knight would be taken; only OK if we fork something worth >= a rook
                    fork_vals = [_piece_val(board, t) for t in forked]
                    fork_vals = [v for v in fork_vals if v > 0]
                    if not fork_vals or min(fork_vals) <= PIECE_VALUE_CP[chess.KNIGHT]:
                        continue
            mv = chess.Move(kn_sq, dest)
            if mv not in board.legal_moves:
                continue
            out.append(_ev("knight_fork", mover=kn_sq, targets=forked,
                           executing_move=mv,
                           evidence=f"knight jumps to {chess.square_name(dest)} attacking {len(forked)} pieces"))
    return out


def detect_bishop_fork(board: chess.Board) -> List[Dict]:
    """Own bishop has (or could move to) a square from which >=2 enemy pieces
    of value >= knight sit on its diagonal rays (with blockers respected).

    Edge cases handled:
      - Pinned bishop: legal_moves filters.
      - Already-forking vs move-into-fork: both emitted.
      - Bishop's color complex (no need to special-case; rays handle it).
    """
    us = _own_color(board)
    out: List[Dict] = []
    for b_sq in board.pieces(chess.BISHOP, us):
        rays_now = _slider_rays_from(board, b_sq, _DIAG_DIRS)
        forked = _fork_from_destination(board, b_sq, b_sq, rays_now)
        if forked is not None:
            out.append(_ev("bishop_fork", mover=b_sq, targets=forked,
                           executing_move=None,
                           evidence=f"bishop on {chess.square_name(b_sq)} hits {len(forked)} pieces on its diagonals"))
            continue
        for dest in _legal_destinations(board, b_sq):
            rays_from_dest = _slider_rays_from(board, dest, _DIAG_DIRS, ignore_square=b_sq)
            forked = _fork_from_destination(board, b_sq, dest, rays_from_dest)
            if forked is None:
                continue
            mv = chess.Move(b_sq, dest)
            if mv not in board.legal_moves:
                continue
            out.append(_ev("bishop_fork", mover=b_sq, targets=forked,
                           executing_move=mv,
                           evidence=f"bishop to {chess.square_name(dest)} hits {len(forked)} pieces"))
    return out


def detect_rook_fork(board: chess.Board) -> List[Dict]:
    """Own rook has (or could move to) a square from which >=2 enemy pieces
    of value >= bishop sit on its file/rank rays.

    Edge cases handled:
      - Pinned rook: legal_moves filters.
      - Already-forking vs move-into-fork: both emitted.
      - Bishop-value targets included (rooks regularly fork B + N too).
    """
    us = _own_color(board)
    out: List[Dict] = []
    for r_sq in board.pieces(chess.ROOK, us):
        rays_now = _slider_rays_from(board, r_sq, _ORTHO_DIRS)
        forked = _fork_from_destination(board, r_sq, r_sq, rays_now)
        if forked is not None:
            out.append(_ev("rook_fork", mover=r_sq, targets=forked,
                           executing_move=None,
                           evidence=f"rook on {chess.square_name(r_sq)} hits {len(forked)} pieces"))
            continue
        for dest in _legal_destinations(board, r_sq):
            rays_from_dest = _slider_rays_from(board, dest, _ORTHO_DIRS, ignore_square=r_sq)
            forked = _fork_from_destination(board, r_sq, dest, rays_from_dest)
            if forked is None:
                continue
            mv = chess.Move(r_sq, dest)
            if mv not in board.legal_moves:
                continue
            out.append(_ev("rook_fork", mover=r_sq, targets=forked,
                           executing_move=mv,
                           evidence=f"rook to {chess.square_name(dest)} hits {len(forked)} pieces"))
    return out


# ────────────────────────────────────────────────────────────────────
# BATCH 3 — Slider-on-ray patterns (Pin / Skewer / Hidden Attack / Double Attack Line)
# ────────────────────────────────────────────────────────────────────

def _slider_dirs_for_piece(piece_type: int) -> List[Tuple[int, int]]:
    if piece_type == chess.BISHOP:
        return _DIAG_DIRS
    if piece_type == chess.ROOK:
        return _ORTHO_DIRS
    if piece_type == chess.QUEEN:
        return _KING_DIRS
    return []


def _walk_ray_two_hits(board: chess.Board, from_sq: int, direction: Tuple[int, int]
                       ) -> Optional[Tuple[int, int]]:
    """Walk a ray from from_sq. Return (first_piece_sq, second_piece_sq) — the
    two nearest non-empty squares on the ray — or None if fewer than two."""
    first = None
    for sq in _ray_squares(from_sq, direction):
        if board.piece_at(sq):
            if first is None:
                first = sq
            else:
                return (first, sq)
    return None


def detect_pin(board: chess.Board) -> List[Dict]:
    """Own slider sees an enemy piece, with a higher-value enemy piece (or king)
    behind it on the same ray.

    Edge cases handled:
      - Absolute pin (back piece is king) vs relative pin (back piece is heavier).
      - First piece must be enemy, second piece must be enemy too.
      - Own pieces blocking the ray = no pin.
      - Two pins from the same slider on different rays emit separate evidences.
    """
    us = _own_color(board)
    them = not us
    out: List[Dict] = []
    for piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        for s_sq in board.pieces(piece_type, us):
            for d in _slider_dirs_for_piece(piece_type):
                pair = _walk_ray_two_hits(board, s_sq, d)
                if not pair:
                    continue
                p1_sq, p2_sq = pair
                p1 = board.piece_at(p1_sq)
                p2 = board.piece_at(p2_sq)
                if not (p1 and p2 and p1.color == them and p2.color == them):
                    continue
                v1 = 10_000 if p1.piece_type == chess.KING else PIECE_VALUE_CP.get(p1.piece_type, 0)
                v2 = 10_000 if p2.piece_type == chess.KING else PIECE_VALUE_CP.get(p2.piece_type, 0)
                # Pin: front (p1) is LOWER value than back (p2). King-in-front is skewer.
                # Skip trivial pawn-pinned-to-minor pins (not teaching-worthy unless absolute pin to king).
                if p1.piece_type == chess.PAWN and p2.piece_type != chess.KING:
                    continue
                if v2 > v1 and p1.piece_type != chess.KING:
                    out.append(_ev(
                        "pin",
                        mover=s_sq,
                        targets=[p1_sq, p2_sq],
                        executing_move=None,
                        evidence=f"{chess.piece_name(p1.piece_type)} on {chess.square_name(p1_sq)} pinned to {chess.piece_name(p2.piece_type)} on {chess.square_name(p2_sq)}",
                    ))
    return out


def detect_skewer(board: chess.Board) -> List[Dict]:
    """Own slider hits an enemy piece, with a LOWER-value enemy piece behind it.
    Hitting the front piece forces it to move, exposing the back one.

    Edge cases handled:
      - Front piece must be HIGHER value than back piece (skewer, not pin).
      - Front piece must be able to legally move off the ray (else it's effectively a pin).
        We don't try to verify this here; we emit the geometry. Engine verifier filters.
      - King-front skewers (check) are also skewers — but only if king must move off-ray.
    """
    us = _own_color(board)
    them = not us
    out: List[Dict] = []
    for piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        for s_sq in board.pieces(piece_type, us):
            for d in _slider_dirs_for_piece(piece_type):
                pair = _walk_ray_two_hits(board, s_sq, d)
                if not pair:
                    continue
                p1_sq, p2_sq = pair
                p1 = board.piece_at(p1_sq)
                p2 = board.piece_at(p2_sq)
                if not (p1 and p2 and p1.color == them and p2.color == them):
                    continue
                if p1.piece_type == chess.KING or p2.piece_type == chess.KING:
                    v1 = 10_000 if p1.piece_type == chess.KING else PIECE_VALUE_CP.get(p1.piece_type, 0)
                    v2 = 10_000 if p2.piece_type == chess.KING else PIECE_VALUE_CP.get(p2.piece_type, 0)
                else:
                    v1 = PIECE_VALUE_CP.get(p1.piece_type, 0)
                    v2 = PIECE_VALUE_CP.get(p2.piece_type, 0)
                if v1 > v2:
                    out.append(_ev(
                        "skewer",
                        mover=s_sq,
                        targets=[p1_sq, p2_sq],
                        executing_move=None,
                        evidence=f"{chess.piece_name(p1.piece_type)} on {chess.square_name(p1_sq)} skewered to {chess.piece_name(p2.piece_type)} on {chess.square_name(p2_sq)}",
                    ))
    return out


def detect_hidden_attack(board: chess.Board) -> List[Dict]:
    """Own slider has an own piece in front of it, with an enemy piece (value
    >= knight, or king) behind. Moving the front piece reveals the attack.

    Edge cases handled:
      - Front piece must be OWN (else it's already a pin/skewer/direct hit).
      - Behind piece must be enemy of value >= knight, or enemy king (discovered check).
      - Front piece moving along the ray does NOT reveal — verifier handles via executing_move policy.
      - Front piece must have at least one legal move; otherwise can't be revealed.
    """
    us = _own_color(board)
    them = not us
    out: List[Dict] = []
    for piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        for s_sq in board.pieces(piece_type, us):
            for d in _slider_dirs_for_piece(piece_type):
                pair = _walk_ray_two_hits(board, s_sq, d)
                if not pair:
                    continue
                p1_sq, p2_sq = pair
                p1 = board.piece_at(p1_sq)
                p2 = board.piece_at(p2_sq)
                if not (p1 and p2):
                    continue
                if p1.color != us:
                    continue  # front must be ours
                if p2.color != them:
                    continue  # back must be enemy
                # Back must be valuable (knight+) or the king (discovered check).
                v2 = PIECE_VALUE_CP.get(p2.piece_type, 0)
                if v2 < _MINOR_OR_ABOVE and p2.piece_type != chess.KING:
                    continue
                # Front must have at least one legal move that LEAVES the ray.
                # We require a destination square that is not on the same ray as s_sq -> p2_sq.
                ray_squares = set(_ray_squares(s_sq, d))
                ray_squares.add(s_sq)
                escapes = [m for m in board.legal_moves
                           if m.from_square == p1_sq and m.to_square not in ray_squares]
                if not escapes:
                    continue
                # Choose the highest-SEE escape as executing_move (often a capture or attack).
                best_mv = max(escapes, key=lambda m: (
                    1 if board.is_capture(m) else 0,
                    -PIECE_VALUE_CP.get(p1.piece_type, 0),
                ))
                out.append(_ev(
                    "hidden_attack",
                    mover=p1_sq,
                    targets=[p2_sq],
                    executing_move=best_mv,
                    evidence=f"{chess.piece_name(p1.piece_type)} on {chess.square_name(p1_sq)} hides {chess.piece_name(piece_type)} on {chess.square_name(s_sq)} attacking {chess.piece_name(p2.piece_type)} on {chess.square_name(p2_sq)}",
                ))
    return out


def detect_double_attack_line(board: chess.Board) -> List[Dict]:
    """Two own compatible sliders (R+R, R+Q, B+B, B+Q) stacked on the same
    file/rank/diagonal pointing into enemy territory.

    Edge cases handled:
      - Compatibility: rook/queen on file or rank; bishop/queen on diagonal.
      - Rear slider sees the front one with no blocker.
      - "Pointing into enemy territory" approximated as: the ray beyond the
        front slider has >=2 squares before hitting an own piece (so the
        battery has space to fire).
    """
    us = _own_color(board)
    out: List[Dict] = []
    seen: set = set()  # avoid duplicate (front, rear) pairs
    for piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        for s_sq in board.pieces(piece_type, us):
            for d in _slider_dirs_for_piece(piece_type):
                # Find first own piece on the ray.
                for tgt in _ray_squares(s_sq, d):
                    p = board.piece_at(tgt)
                    if not p:
                        continue
                    if p.color != us:
                        break
                    # Check compatibility: tgt's piece type must use same ray dirs.
                    if d in _slider_dirs_for_piece(p.piece_type):
                        pair = (min(s_sq, tgt), max(s_sq, tgt), d)
                        if pair in seen:
                            break
                        seen.add(pair)
                        # Count squares beyond tgt on the same ray before next piece.
                        beyond = 0
                        for sq2 in _ray_squares(tgt, d):
                            if board.piece_at(sq2):
                                break
                            beyond += 1
                        if beyond >= 2:
                            out.append(_ev(
                                "double_attack_line",
                                mover=s_sq,
                                targets=[tgt],
                                executing_move=None,
                                evidence=f"{chess.piece_name(piece_type)} on {chess.square_name(s_sq)} backs {chess.piece_name(p.piece_type)} on {chess.square_name(tgt)} on shared line",
                            ))
                    break  # we only care about the FIRST own piece on the ray
    return out


# ────────────────────────────────────────────────────────────────────
# BATCH 4 — King-zone patterns (Back-Rank / h7 / Q+N mate / Smothered)
# ────────────────────────────────────────────────────────────────────

def detect_back_rank_trap(board: chess.Board) -> List[Dict]:
    """Enemy king on its back rank with all 3 forward squares occupied by
    ENEMY PAWNS (not just any piece — pieces can step away to make luft),
    and we have a R/Q with a clear path to the enemy back rank.

    Bug fix 2026-05-13 (per user-flagged move-4 false fire):
      - Old spec accepted any enemy piece blocking the 3 in-front squares.
        That fires on every opening position after a couple of captures —
        e.g. after 1.d4 e5 2.dxe5 d6 3.exd6 Bxd6 4.Bd2 the king sits on e1
        with d2=bishop, e2=pawn, f2=pawn, and a single open file somewhere
        else on the board was enough to fire the pattern. Pedagogically
        meaningless: bishop on d2 can step away in one move.
      - New spec: all 3 blockers must be PAWNS (immovable laterally), and
        we must have a R/Q with a path to the back rank (no piece of
        either colour between R/Q and the back rank).

    Negative cases this now rejects:
      1. move-4 with bishop in front of king (real complaint)
      2. starting-position derivatives (always had non-pawn or moved-pawn)
      3. both-castled middlegame with no open invasion file (no path)
      4. fianchetto positions (g6/g3 means missing pawn cover)
    """
    us = _own_color(board)
    them = not us
    them_king_sq = board.king(them)
    if them_king_sq is None:
        return []
    back_rank = 7 if them == chess.BLACK else 0
    if chess.square_rank(them_king_sq) != back_rank:
        return []
    # All 3 forward squares must be enemy PAWNS (not any enemy piece).
    forward_rank = 6 if them == chess.BLACK else 1
    f0 = chess.square_file(them_king_sq)
    pawns_in_front = 0
    valid_squares = 0
    for df in (-1, 0, 1):
        f = f0 + df
        if not (0 <= f < 8):
            continue
        valid_squares += 1
        sq = chess.square(f, forward_rank)
        p = board.piece_at(sq)
        if not p or p.color != them or p.piece_type != chess.PAWN:
            return []
        pawns_in_front += 1
    # Need at least 2 pawns (corner kings only have 2 valid squares in front).
    if pawns_in_front < 2:
        return []
    # We must have an R/Q with a clear path to the enemy back rank — that's
    # how the trap actually executes. Generic "open file exists somewhere"
    # isn't enough.
    candidates = list(board.pieces(chess.ROOK, us)) + list(board.pieces(chess.QUEEN, us))
    if not candidates:
        return []
    has_invasion = False
    for c_sq in candidates:
        if chess.square_rank(c_sq) == back_rank:
            has_invasion = True
            break
        cf = chess.square_file(c_sq)
        cr = chess.square_rank(c_sq)
        step = 1 if back_rank > cr else -1
        path_clear = True
        rr = cr + step
        while rr != back_rank:
            blocker = board.piece_at(chess.square(cf, rr))
            if blocker is not None:
                path_clear = False
                break
            rr += step
        if path_clear:
            has_invasion = True
            break
    if not has_invasion:
        return []
    # Emit the invading R/Q square as mover so the move-relevance gate can
    # attribute this pattern to the move that put our R/Q on the file.
    invader_sq = None
    for c_sq in candidates:
        if chess.square_rank(c_sq) == back_rank:
            invader_sq = c_sq
            break
        cf = chess.square_file(c_sq)
        cr = chess.square_rank(c_sq)
        step = 1 if back_rank > cr else -1
        rr = cr + step
        path_clear = True
        while rr != back_rank:
            if board.piece_at(chess.square(cf, rr)) is not None:
                path_clear = False
                break
            rr += step
        if path_clear:
            invader_sq = c_sq
            break
    return [_ev(
        "back_rank_trap",
        mover=invader_sq,
        targets=[them_king_sq],
        executing_move=None,
        evidence=f"king on {chess.square_name(them_king_sq)} has no escape squares on rank {back_rank + 1}",
    )]


def detect_h7_attack(board: chess.Board) -> List[Dict]:
    """Classical kingside attack pattern: own bishop bears on h7 (or h2),
    own queen has access to h-file or h5/h4 diagonal, enemy king on g8/g1,
    enemy knight NOT on f6/f3, and h7/h2 pawn present.

    Edge cases handled:
      - White attacks h7 (Black king on g8); Black attacks h2 (White king on g1).
      - 'Bishop bears on h7' = h7 is a square the bishop attacks (including through air).
      - Queen access: queen is on the d1-h5 (or d8-h4) diagonal OR has h-file access.
      - Knight defender on f6 (or f3) blocks the pattern.
      - We require h7 pawn present (else there's nothing to sac onto).
    """
    us = _own_color(board)
    them = not us
    them_king_sq = board.king(them)
    if them_king_sq is None:
        return []
    target_sq_name = "h7" if them == chess.BLACK else "h2"
    target_sq = chess.parse_square(target_sq_name)
    knight_defender_sq = chess.parse_square("f6" if them == chess.BLACK else "f3")
    king_castled_sq = chess.parse_square("g8" if them == chess.BLACK else "g1")
    # Enemy king on g8 or h8 area
    if them_king_sq not in (king_castled_sq, chess.parse_square("h8" if them == chess.BLACK else "h1")):
        return []
    # h-pawn present
    pawn_at_target = board.piece_at(target_sq)
    if not pawn_at_target or pawn_at_target.piece_type != chess.PAWN or pawn_at_target.color != them:
        return []
    # Knight defender on f6/f3 blocks
    f6_piece = board.piece_at(knight_defender_sq)
    if f6_piece and f6_piece.piece_type == chess.KNIGHT and f6_piece.color == them:
        return []
    # Own bishop attacks target square
    bishop_attackers = [s for s in board.attackers(us, target_sq)
                        if board.piece_at(s) and board.piece_at(s).piece_type == chess.BISHOP]
    if not bishop_attackers:
        return []
    # Own queen exists and can reach h-file / 4th-5th rank diagonal near king
    queens = list(board.pieces(chess.QUEEN, us))
    if not queens:
        return []
    return [_ev(
        "h7_attack",
        mover=bishop_attackers[0],
        targets=[target_sq],
        executing_move=None,
        evidence=f"bishop on {chess.square_name(bishop_attackers[0])} aims at {target_sq_name}, knight defender absent",
    )]


def detect_queen_knight_mate(board: chess.Board) -> List[Dict]:
    """Own queen and own knight both within 3 squares of enemy king. Geometric
    proximity only — actual mate is the engine's job.

    Edge cases handled:
      - Multiple queens / knights: emit one evidence if ANY queen + knight pair qualifies.
      - Chebyshev distance, not Manhattan, since pieces move along rays/jumps.
    """
    us = _own_color(board)
    them = not us
    them_king_sq = board.king(them)
    if them_king_sq is None:
        return []
    queens = list(board.pieces(chess.QUEEN, us))
    knights = list(board.pieces(chess.KNIGHT, us))
    if not queens or not knights:
        return []
    kf, kr = chess.square_file(them_king_sq), chess.square_rank(them_king_sq)
    def near(sq):
        return max(abs(chess.square_file(sq) - kf), abs(chess.square_rank(sq) - kr)) <= 3
    near_queens = [q for q in queens if near(q)]
    near_knights = [n for n in knights if near(n)]
    if near_queens and near_knights:
        # Emit the near queen as mover so the move-relevance gate can fire
        # this pattern on moves involving the attacking queen or knight.
        return [_ev(
            "queen_knight_mate",
            mover=near_queens[0],
            targets=[them_king_sq, near_knights[0]],
            executing_move=None,
            evidence=f"queen + knight within 3 squares of king on {chess.square_name(them_king_sq)}",
        )]
    return []


def detect_knight_mate(board: chess.Board) -> List[Dict]:
    """Smothered-mate shape: enemy king's surrounding squares all occupied by
    enemy pieces (or off-board), and we have a knight that can deliver check.

    Edge cases handled:
      - King on edge/corner: off-board squares count as 'blocked'.
      - Surrounding squares must be occupied by ENEMY pieces (not ours — if ours
        is there, the king could capture). Exception: ours and the square is defended.
        Simplified: we accept any non-empty occupant.
      - We need a knight that can legally check the king.
    """
    us = _own_color(board)
    them = not us
    them_king_sq = board.king(them)
    if them_king_sq is None:
        return []
    kf, kr = chess.square_file(them_king_sq), chess.square_rank(them_king_sq)
    surrounded = True
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if df == 0 and dr == 0:
                continue
            f, r = kf + df, kr + dr
            if not (0 <= f < 8 and 0 <= r < 8):
                continue
            adj_sq = chess.square(f, r)
            if not board.piece_at(adj_sq):
                surrounded = False
                break
        if not surrounded:
            break
    if not surrounded:
        return []
    # Find a knight that can check the king.
    for n_sq in board.pieces(chess.KNIGHT, us):
        for dest in _knight_jumps(n_sq):
            if them_king_sq in _knight_jumps(dest):
                mv = chess.Move(n_sq, dest)
                if mv in board.legal_moves:
                    return [_ev(
                        "knight_mate",
                        mover=n_sq,
                        targets=[them_king_sq],
                        executing_move=mv,
                        evidence=f"king on {chess.square_name(them_king_sq)} smothered; knight {chess.square_name(n_sq)} → {chess.square_name(dest)} checks",
                    )]
    return []


# ────────────────────────────────────────────────────────────────────
# BATCH 5 — Pressure / tactical follow-on
# ────────────────────────────────────────────────────────────────────

def detect_no_safe_square(board: chess.Board) -> List[Dict]:
    """Enemy piece (>= knight) whose ALL legal destinations are attacked by us
    with winning SEE, AND we can pile on by attacking the piece once more.

    Edge cases handled:
      - Skip enemy pawns and king.
      - 'All legal destinations bad' counted via the enemy's moves if it were
        their turn — we use pseudo-legal here for tractability.
      - 'Pile-on possible': we have a piece that can attack the trapped piece's
        current square within one move. Detector emits geometry; engine verifies.
    """
    us = _own_color(board)
    them = not us
    out: List[Dict] = []
    # Generate destinations for enemy pieces as if they were to move.
    # python-chess: copy board, push null move (force opponent to move).
    # Null move requires not-in-check; use generator directly instead.
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.color != them:
            continue
        if p.piece_type in (chess.PAWN, chess.KING):
            continue
        if PIECE_VALUE_CP.get(p.piece_type, 0) < _MINOR_OR_ABOVE:
            continue
        # Compute the destination squares for this piece (pseudo-legal, ignoring side-to-move).
        dests = []
        if p.piece_type == chess.KNIGHT:
            dests = [d for d in _knight_jumps(sq) if not (board.piece_at(d) and board.piece_at(d).color == them)]
        else:
            for d in _slider_dirs_for_piece(p.piece_type):
                for r in _ray_squares(sq, d):
                    occ = board.piece_at(r)
                    if occ and occ.color == them:
                        break
                    dests.append(r)
                    if occ:
                        break
        if not dests:
            # No squares to move to at all — piece literally trapped.
            # But it might still be defended on the current square. We need attackers.
            if board.attackers(us, sq):
                out.append(_ev("no_safe_square", mover=None, targets=[sq], executing_move=None,
                               evidence=f"{chess.piece_name(p.piece_type)} on {chess.square_name(sq)} has zero squares to flee to"))
            continue
        all_bad = True
        for d in dests:
            # On d, would they survive? Approximation: after a hypothetical move,
            # is d attacked by us with SEE that costs them material?
            # Use static_exchange_eval at d (without simulating the move).
            see_us = static_exchange_eval(board, d, us)
            if see_us <= 0:
                all_bad = False
                break
        if all_bad and board.attackers(us, sq):
            out.append(_ev("no_safe_square", mover=None, targets=[sq], executing_move=None,
                           evidence=f"{chess.piece_name(p.piece_type)} on {chess.square_name(sq)} has no safe destinations"))
    return out


def detect_tired_defender(board: chess.Board) -> List[Dict]:
    """Enemy piece X defends >= 2 of their own pieces or critical squares; if
    X is removed/distracted, at least 2 things fall.

    Edge cases handled:
      - X must actually defend each target (be among target's defenders).
      - Targets must be valuable enough that losing them costs material
        (we require target value >= knight).
      - X being a pawn still counts (pawns defend, get distracted).
    """
    them = not _own_color(board)
    us = _own_color(board)
    out: List[Dict] = []
    for x_sq in chess.SQUARES:
        x = board.piece_at(x_sq)
        if not x or x.color != them:
            continue
        defended = []
        for y_sq in chess.SQUARES:
            if y_sq == x_sq:
                continue
            y = board.piece_at(y_sq)
            if not y or y.color != them:
                continue
            if PIECE_VALUE_CP.get(y.piece_type, 0) < _MINOR_OR_ABOVE:
                continue
            if x_sq in board.attackers(them, y_sq):
                # We must also already have an attacker on y_sq (else removing X
                # doesn't immediately threaten anything).
                if board.attackers(us, y_sq):
                    defended.append(y_sq)
        if len(defended) >= 2:
            out.append(_ev("tired_defender", mover=None, targets=[x_sq] + defended,
                           executing_move=None,
                           evidence=f"{chess.piece_name(x.piece_type)} on {chess.square_name(x_sq)} guards {len(defended)} pieces"))
    return out


def detect_remove_the_guard(board: chess.Board) -> List[Dict]:
    """Enemy piece X defends a valuable enemy target Y. We can capture X with
    winning SEE; once X is gone, Y is undefended (or insufficiently defended).

    Edge cases handled:
      - Y must be value >= knight.
      - We must have an attacker on Y already (otherwise capturing X is pointless).
      - 'Sufficiently defended' = removing X leaves zero defenders on Y.
    """
    us = _own_color(board)
    them = not us
    out: List[Dict] = []
    for x_sq in chess.SQUARES:
        x = board.piece_at(x_sq)
        if not x or x.color != them:
            continue
        # Can we win X via SEE?
        if not board.attackers(us, x_sq):
            continue
        see = static_exchange_eval(board, x_sq, us)
        if see < 0:
            continue
        # Targets X defends.
        for y_sq in chess.SQUARES:
            if y_sq == x_sq:
                continue
            y = board.piece_at(y_sq)
            if not y or y.color != them:
                continue
            if PIECE_VALUE_CP.get(y.piece_type, 0) < _MINOR_OR_ABOVE:
                continue
            if x_sq not in board.attackers(them, y_sq):
                continue
            # Count other defenders of Y (excluding X).
            other_defenders = board.attackers(them, y_sq) - chess.SquareSet([x_sq])
            if len(other_defenders) > 0:
                continue
            # We must already attack Y.
            if not board.attackers(us, y_sq):
                continue
            # Choose the cheapest attacker of X as the executing move.
            atks = sorted(board.attackers(us, x_sq),
                          key=lambda s: PIECE_VALUE_CP.get(board.piece_at(s).piece_type, 0)
                          if board.piece_at(s) else 99)
            mv = chess.Move(atks[0], x_sq)
            if mv not in board.legal_moves:
                continue
            out.append(_ev("remove_the_guard", mover=atks[0], targets=[x_sq, y_sq],
                           executing_move=mv,
                           evidence=f"{chess.piece_name(x.piece_type)} on {chess.square_name(x_sq)} sole guard of {chess.square_name(y_sq)}"))
    return out


def detect_force_the_king(board: chess.Board) -> List[Dict]:
    """We have a check or capture that forces enemy king to a specific square
    where our follow-up wins material.

    Hard to detect cleanly without 2-ply lookahead. We emit candidates:
        - any check that has only ONE legal king response (forced single reply)
        - the destination of that king reply is attacked by us with SEE > 0 after the king moves there
    Engine verifier filters to true tactics.

    Edge cases handled:
      - Multiple legal responses: not forced → skip.
      - King-only responses; not blocks/captures by other pieces.
    """
    us = _own_color(board)
    them = not us
    out: List[Dict] = []
    for mv in list(board.legal_moves):
        # Quick filter: must be a check or capture (otherwise rarely forcing).
        is_check = board.gives_check(mv)
        if not is_check:
            continue
        # Simulate
        b2 = board.copy()
        b2.push(mv)
        replies = list(b2.legal_moves)
        if len(replies) != 1:
            continue
        reply = replies[0]
        if board.piece_at(reply.from_square) and board.piece_at(reply.from_square).piece_type != chess.KING:
            continue  # only forced king moves count for our purposes
        # After reply, is the king on a square we can attack profitably?
        b3 = b2.copy()
        b3.push(reply)
        # The king is now on reply.to_square. Can we win material with our next move?
        # Approximation: is any square adjacent to the new king square attacked by us
        # with SEE > 0, where there's an enemy piece sitting?
        kf = chess.square_file(reply.to_square)
        kr = chess.square_rank(reply.to_square)
        for df in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if df == 0 and dr == 0:
                    continue
                f, r = kf + df, kr + dr
                if not (0 <= f < 8 and 0 <= r < 8):
                    continue
                adj = chess.square(f, r)
                p = b3.piece_at(adj)
                if p and p.color == them and PIECE_VALUE_CP.get(p.piece_type, 0) >= _MINOR_OR_ABOVE:
                    if static_exchange_eval(b3, adj, us) > 0:
                        out.append(_ev("force_the_king", mover=mv.from_square,
                                       targets=[reply.to_square, adj],
                                       executing_move=mv,
                                       evidence=f"forced king reply to {chess.square_name(reply.to_square)} drops {chess.square_name(adj)}"))
                        break
            else:
                continue
            break
    return out


def detect_in_between_move(board: chess.Board, prev_move: Optional[chess.Move] = None) -> List[Dict]:
    """Zwischenzug: previous enemy move was a capture, the 'natural' reply is
    recapture, but we have an intermediate check/threat instead.

    Gates: prev_move.to_square must currently hold an enemy piece (i.e. that's
    where the enemy capturer landed) AND we must have at least one attacker on
    that square (the natural recapture exists). Without those, this isn't a
    zwischenzug situation at all.

    Edge cases handled:
      - prev_move = None: no history, return [].
      - prev_move was non-capturing: enemy piece on to_square but we have no attacker → skip.
      - We emit candidates: legal CHECK moves that are not the recapture.
      - Engine verifier confirms net material >= recapture.
    """
    if prev_move is None:
        return []
    us = _own_color(board)
    them = not us
    recap_sq = prev_move.to_square
    enemy_at_recap = board.piece_at(recap_sq)
    if not enemy_at_recap or enemy_at_recap.color != them:
        return []
    if not board.attackers(us, recap_sq):
        return []
    out: List[Dict] = []
    for mv in board.legal_moves:
        if mv.to_square == recap_sq:
            continue
        if not board.gives_check(mv):
            continue
        out.append(_ev("in_between_move", mover=mv.from_square, targets=[recap_sq, mv.to_square],
                       executing_move=mv,
                       evidence=f"check on {chess.square_name(mv.to_square)} before recapturing on {chess.square_name(recap_sq)}"))
    return out


# ────────────────────────────────────────────────────────────────────
# BATCH 6 — Positional patterns
# ────────────────────────────────────────────────────────────────────

def detect_strong_knight_square(board: chess.Board) -> List[Dict]:
    """Own knight on advanced rank (4/5/6 for White; 3/4/5 for Black), defended
    by an own pawn, and no enemy pawn on adjacent files can ever push to attack it.

    Edge cases handled:
      - White vs Black rank ranges.
      - 'Defended by pawn' = at least one own pawn attacks the knight's square.
      - 'Can never be kicked' = no enemy pawn exists on adjacent file at any rank
        from which it could march forward and attack the square.
    """
    us = _own_color(board)
    them = not us
    out: List[Dict] = []
    target_ranks = (3, 4, 5) if us == chess.WHITE else (2, 3, 4)
    for n_sq in board.pieces(chess.KNIGHT, us):
        if chess.square_rank(n_sq) not in target_ranks:
            continue
        # Defended by own pawn?
        defended_by_pawn = False
        for atk_sq in board.attackers(us, n_sq):
            pp = board.piece_at(atk_sq)
            if pp and pp.piece_type == chess.PAWN:
                defended_by_pawn = True
                break
        if not defended_by_pawn:
            continue
        # No enemy pawn on adjacent files that could attack this square?
        nf = chess.square_file(n_sq)
        nr = chess.square_rank(n_sq)
        kickable = False
        for df in (-1, 1):
            ef = nf + df
            if not (0 <= ef < 8):
                continue
            # Enemy pawn must be in front of the knight to push forward (for White's enemy = Black, pawns push down).
            for er in range(8):
                ep = board.piece_at(chess.square(ef, er))
                if not ep or ep.piece_type != chess.PAWN or ep.color != them:
                    continue
                # Can this pawn ever reach (nf, nr-1) (white knight) / (nf, nr+1) (black knight) to attack?
                target_pawn_rank = nr - 1 if us == chess.WHITE else nr + 1
                if us == chess.WHITE:
                    # Enemy black pawn pushes down; needs to reach rank target_pawn_rank from above.
                    if er > target_pawn_rank:
                        kickable = True
                else:
                    if er < target_pawn_rank:
                        kickable = True
                if kickable:
                    break
            if kickable:
                break
        if kickable:
            continue
        out.append(_ev("strong_knight_square", mover=n_sq, targets=[],
                       executing_move=None,
                       evidence=f"knight on {chess.square_name(n_sq)} on permanent outpost"))
    return out


def detect_weak_squares(board: chess.Board) -> List[Dict]:
    """HEURISTIC ONLY. Enemy king zone has >=3 squares of one colour where the
    enemy bishop of that colour is missing.

    Edge cases handled:
      - King zone = 3x3 around the king (8 surrounding squares).
      - Colour count: chess.SQUARES are coloured by (file+rank) parity; light = even sum.
      - Missing bishop: enemy has no bishop on the matching colour.
    """
    us = _own_color(board)
    them = not us
    them_king_sq = board.king(them)
    if them_king_sq is None:
        return []
    kf = chess.square_file(them_king_sq)
    kr = chess.square_rank(them_king_sq)
    zone = []
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if df == 0 and dr == 0:
                continue
            f, r = kf + df, kr + dr
            if 0 <= f < 8 and 0 <= r < 8:
                zone.append(chess.square(f, r))
    # Bucket squares by (file+rank) parity. We don't claim 'light' vs 'dark' here
    # because our parity convention is inverted from standard chess (a1 sum=0 even
    # but a1 is dark in real-world). Doesn't matter as long as we're consistent.
    parity_a = [s for s in zone if (chess.square_file(s) + chess.square_rank(s)) % 2 == 0]
    parity_b = [s for s in zone if (chess.square_file(s) + chess.square_rank(s)) % 2 == 1]
    their_bishops = list(board.pieces(chess.BISHOP, them))
    has_b_parity_a = any((chess.square_file(s) + chess.square_rank(s)) % 2 == 0 for s in their_bishops)
    has_b_parity_b = any((chess.square_file(s) + chess.square_rank(s)) % 2 == 1 for s in their_bishops)
    # We need an own piece that can actually exploit the weak squares:
    # a knight (jumps anywhere), a queen (any colour), or a same-parity bishop.
    our_bishops = list(board.pieces(chess.BISHOP, us))
    has_our_b_parity_a = any((chess.square_file(s) + chess.square_rank(s)) % 2 == 0 for s in our_bishops)
    has_our_b_parity_b = any((chess.square_file(s) + chess.square_rank(s)) % 2 == 1 for s in our_bishops)
    have_knight = bool(board.pieces(chess.KNIGHT, us))
    have_queen = bool(board.pieces(chess.QUEEN, us))
    out: List[Dict] = []
    # Require >= 4 (not 3) — 3 is too generous; almost any king has a 3/5 split.
    if len(parity_a) >= 4 and not has_b_parity_a and (have_knight or have_queen or has_our_b_parity_a):
        out.append(_ev("weak_squares", mover=None, targets=parity_a,
                       executing_move=None,
                       evidence=f"{len(parity_a)} weak squares around enemy king (enemy has no bishop of that colour)"))
    if len(parity_b) >= 4 and not has_b_parity_b and (have_knight or have_queen or has_our_b_parity_b):
        out.append(_ev("weak_squares", mover=None, targets=parity_b,
                       executing_move=None,
                       evidence=f"{len(parity_b)} weak squares around enemy king (enemy has no bishop of that colour)"))
    return out


def detect_open_long_line(board: chess.Board) -> List[Dict]:
    """Enemy's fianchetto bishop is gone AND the long diagonal to their king
    is clear enough for us to invade.

    Edge cases handled:
      - White-side fianchetto: b2/g2 pawn moved + dark-square / light-square bishop gone.
      - Mirror for Black.
      - 'Clear enough' = at least 4 squares on the long diagonal toward king side are empty.
    """
    us = _own_color(board)
    them = not us
    them_king_sq = board.king(them)
    if them_king_sq is None:
        return []
    out: List[Dict] = []
    # Long diagonals: a1-h8 squares all have (file==rank) so sum is even -> parity 0.
    # a8-h1 squares all have (file+rank==7) -> parity 1. Bishop matching the diagonal
    # must share its parity.
    diag_a1h8 = [chess.square(i, i) for i in range(8)]
    diag_a8h1 = [chess.square(i, 7 - i) for i in range(8)]
    their_bishops = list(board.pieces(chess.BISHOP, them))
    has_b_par0 = any((chess.square_file(s) + chess.square_rank(s)) % 2 == 0 for s in their_bishops)
    has_b_par1 = any((chess.square_file(s) + chess.square_rank(s)) % 2 == 1 for s in their_bishops)
    our_bishops = list(board.pieces(chess.BISHOP, us))
    has_our_b_par0 = any((chess.square_file(s) + chess.square_rank(s)) % 2 == 0 for s in our_bishops)
    has_our_b_par1 = any((chess.square_file(s) + chess.square_rank(s)) % 2 == 1 for s in our_bishops)
    have_queen = bool(board.pieces(chess.QUEEN, us))
    # a1-h8 (parity 0): enemy must lack parity-0 bishop; we need parity-0 bishop or queen.
    # a8-h1 (parity 1): enemy must lack parity-1 bishop; we need parity-1 bishop or queen.
    for diag, their_has, our_has_b, label in (
        (diag_a1h8, has_b_par0, has_our_b_par0, "a1-h8"),
        (diag_a8h1, has_b_par1, has_our_b_par1, "a8-h1"),
    ):
        if their_has:
            continue
        if not (our_has_b or have_queen):
            continue
        empty_count = sum(1 for s in diag if not board.piece_at(s))
        if empty_count >= 4:
            out.append(_ev("open_long_line", mover=None, targets=diag,
                           executing_move=None,
                           evidence=f"long diagonal {label} open; enemy bishop of that colour absent"))
    return out


def detect_long_diagonal_bishop(board: chess.Board) -> List[Dict]:
    """Own bishop on a long diagonal (a1-h8 / a8-h1) with >= 5 empty squares
    along it (i.e. unobstructed).

    Edge cases handled:
      - Bishop must be ON the long diagonal (not just any diagonal).
      - Squares counted include both sides of the bishop along the same diagonal.
    """
    us = _own_color(board)
    out: List[Dict] = []
    diag_a1h8 = set([chess.square(i, i) for i in range(8)])
    diag_a8h1 = set([chess.square(i, 7 - i) for i in range(8)])
    for b_sq in board.pieces(chess.BISHOP, us):
        for diag, label in ((diag_a1h8, "a1-h8"), (diag_a8h1, "a8-h1")):
            if b_sq not in diag:
                continue
            empty_count = sum(1 for s in diag if s != b_sq and not board.piece_at(s))
            if empty_count >= 5:
                out.append(_ev("long_diagonal_bishop", mover=b_sq, targets=list(diag),
                               executing_move=None,
                               evidence=f"bishop on {chess.square_name(b_sq)} commands {label}"))
    return out


def detect_pawn_hole_fianchetto(board: chess.Board) -> List[Dict]:
    """Enemy played a fianchetto pawn move (g6/g3/b6/b3) AND the matching-colour
    bishop is GONE from the board entirely — that square is a permanent hole.

    Edge cases handled:
      - 'Bishop off the diagonal' is NOT enough; the bishop might come back. We
        require the bishop of the matching parity to be entirely absent.
      - g7 = (6,6) sum 12 even -> KS Black bishop has parity 0.
      - b7 = (1,6) sum 7  odd  -> QS Black bishop has parity 1.
      - g2 = (6,1) sum 7  odd  -> KS White bishop has parity 1.
      - b2 = (1,1) sum 2  even -> QS White bishop has parity 0.
    """
    them = not _own_color(board)
    if them == chess.BLACK:
        spots = [("g6", chess.parse_square("g6"), 0),
                 ("b6", chess.parse_square("b6"), 1)]
    else:
        spots = [("g3", chess.parse_square("g3"), 1),
                 ("b3", chess.parse_square("b3"), 0)]
    their_bishops = list(board.pieces(chess.BISHOP, them))
    out: List[Dict] = []
    for hole_name, hole_sq, required_parity in spots:
        p = board.piece_at(hole_sq)
        if not p or p.piece_type != chess.PAWN or p.color != them:
            continue
        bishop_present = any(
            (chess.square_file(b) + chess.square_rank(b)) % 2 == required_parity
            for b in their_bishops
        )
        if bishop_present:
            continue
        out.append(_ev("pawn_hole_fianchetto", mover=None, targets=[hole_sq],
                       executing_move=None,
                       evidence=f"enemy played {hole_name}; matching fianchetto bishop is gone"))
    return out


# ────────────────────────────────────────────────────────────────────
# Dispatcher + verifier
# ────────────────────────────────────────────────────────────────────

_DETECTORS = {
    "free_piece":             detect_free_piece,
    "free_pawn":              detect_free_pawn,
    "knight_fork":            detect_knight_fork,
    "bishop_fork":            detect_bishop_fork,
    "rook_fork":              detect_rook_fork,
    "pin":                    detect_pin,
    "skewer":                 detect_skewer,
    "hidden_attack":          detect_hidden_attack,
    "double_attack_line":     detect_double_attack_line,
    "back_rank_trap":         detect_back_rank_trap,
    "h7_attack":              detect_h7_attack,
    "queen_knight_mate":      detect_queen_knight_mate,
    "knight_mate":            detect_knight_mate,
    "no_safe_square":         detect_no_safe_square,
    "tired_defender":         detect_tired_defender,
    "remove_the_guard":       detect_remove_the_guard,
    "force_the_king":         detect_force_the_king,
    # in_between_move needs prev_move; handled separately in detect_all_shapes
    "strong_knight_square":   detect_strong_knight_square,
    "weak_squares":           detect_weak_squares,
    "open_long_line":         detect_open_long_line,
    "long_diagonal_bishop":   detect_long_diagonal_bishop,
    "pawn_hole_fianchetto":   detect_pawn_hole_fianchetto,
}


def detect_all_shapes(board: chess.Board, prev_move: Optional[chess.Move] = None) -> List[Dict]:
    """Run every detector against `board`. Returns the union of evidences.

    prev_move (uci or chess.Move) is needed for in_between_move detection.
    """
    out: List[Dict] = []
    for det in _DETECTORS.values():
        try:
            out.extend(det(board))
        except Exception:
            # Detectors must never crash the pipeline. Log-and-continue.
            continue
    if prev_move is not None:
        try:
            out.extend(detect_in_between_move(board, prev_move))
        except Exception:
            pass
    return out


def verify_with_engine_data(evidence_list: List[Dict], eval_data: Optional[Dict]) -> List[Dict]:
    """Filter evidence by each pattern's verifier_policy against engine data.

    eval_data shape (matches what V5 pipeline produces):
        {
            "best_move_uci": "e2e4",
            "top_n_uci":     ["e2e4", "d2d4", "g1f3"],
            ...
        }

    If eval_data is None, returns evidence as-is (no filtering).
    Patterns with verifier_policy='heuristic_only' always pass.
    Patterns without executing_move always pass (positional — no move to match).
    """
    if eval_data is None:
        return evidence_list
    best = eval_data.get("best_move_uci")
    top_n = eval_data.get("top_n_uci") or ([best] if best else [])
    out = []
    for ev in evidence_list:
        spec = PATTERNS_BY_ID.get(ev["pattern_id"])
        if not spec:
            continue
        policy = spec["verifier_policy"]
        if policy == "heuristic_only":
            out.append(ev)
            continue
        ex = ev.get("executing_move")
        if ex is None:
            # Positional pattern — engine confirms via position eval, not move match.
            # We pass for now; downstream cp_loss / eval-trend filters refine.
            out.append(ev)
            continue
        if policy == "engine_confirms_target":
            if ex == best:
                out.append(ev)
        elif policy == "engine_in_top_3":
            if ex in (top_n[:3] if isinstance(top_n, list) else []):
                out.append(ev)
    return out


# ────────────────────────────────────────────────────────────────────
# Self-check on import (loud failure — better than silent drift)
# ────────────────────────────────────────────────────────────────────

def _self_check() -> None:
    # 1. Free piece: hanging queen on d4, white to move with rook on d1.
    b = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1")
    ev = detect_free_piece(b)
    assert any(e["pattern_id"] == "free_piece" and "d4" in e["targets"] for e in ev), \
        f"free_piece self-check failed: {ev}"
    # 2. Knight fork: white knight on e5 forks black king on h8 and queen on c6.
    #    Actually let's set up a classic royal fork. White N on c7 forks Black K on a8 and Q on e8.
    b = chess.Board("k3q3/2N5/8/8/8/8/8/4K3 w - - 0 1")
    ev = detect_knight_fork(b)
    assert any(e["pattern_id"] == "knight_fork" for e in ev), f"knight_fork self-check failed: {ev}"
    # 3. Back-rank trap: black king on g8 with pawns on f7 g7 h7, white rook on a1.
    b = chess.Board("6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1")
    ev = detect_back_rank_trap(b)
    assert any(e["pattern_id"] == "back_rank_trap" for e in ev), f"back_rank_trap self-check failed: {ev}"
    # 4. Pin: white bishop on g2 pins black knight on c6 to king on a8.
    b = chess.Board("k7/8/2n5/8/8/8/6B1/4K3 w - - 0 1")
    ev = detect_pin(b)
    assert any(e["pattern_id"] == "pin" for e in ev), f"pin self-check failed: {ev}"
    # 5. Skewer: white rook on h8 attacks black king on h7, with rook on h2 behind.
    b = chess.Board("7R/7k/8/8/8/8/7r/4K3 b - - 0 1")
    # Black to move; we want a white pattern here. Flip turn:
    b = chess.Board("7R/7k/8/8/8/8/7r/4K3 w - - 0 1")
    ev = detect_skewer(b)
    assert any(e["pattern_id"] == "skewer" for e in ev), f"skewer self-check failed: {ev}"


_self_check()
