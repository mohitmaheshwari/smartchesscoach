"""coach_blunder_guard.py — the soundness FLOOR on the coach's own moves.

docs/coach_blunder_guard_scope.md. The coach opponent weakens via Stockfish Skill
Level / UCI_Elo, which makes it play WORSE but in an INHUMAN way — it occasionally
hangs a queen, which no 800–1500 player does in a quiet position, and which instantly
breaks the student's trust (Mohit 2026-06-27).

This guard is philosophy B: a HARD floor against FREE one-move material hangs at every
level, while ALLOWING the calibrated teaching-mistakes above it (pawn-drops, deeper
2+ move tactics the student must actually calculate). The one-move/multi-move boundary
IS philosophy B — we draw it with a static Static-Exchange-Evaluation, so there is no
extra engine call on the hot path: if the coach's move lets the opponent win >= a minor
piece with a single capture sequence, it's a free hang and we won't play it.

Pure functions + a guard entry point. No engine here except the optional resample,
which the caller supplies candidates for. Behind PWC_COACH_BLUNDER_GUARD (caller-gated).
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import chess

# Centipawn piece values for SEE. King is huge so it's never "won" in an exchange.
_PIECE_VAL = {
    chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000,
}

# Default floor: a minor piece. Below this is a pawn-drop (an allowed teaching mistake);
# at/above it is a free piece/rook/queen hang (blocked). Data-locked in the scope.
DEFAULT_FLOOR_CP = 300


def piece_value_cp(piece_type: int) -> int:
    """Canonical SEE material value for a python-chess piece type."""
    return _PIECE_VAL.get(piece_type, 0)


def _lva_capture(board: chess.Board, sq: int) -> Optional[chess.Move]:
    """The least-valuable LEGAL capture of `sq` by the side to move, or None."""
    best_mv: Optional[chess.Move] = None
    best_val = 10 ** 9
    for asq in board.attackers(board.turn, sq):
        pt = board.piece_at(asq).piece_type
        v = _PIECE_VAL[pt]
        if v >= best_val:
            continue
        mv = chess.Move(asq, sq)
        if pt == chess.PAWN and chess.square_rank(sq) in (0, 7):
            mv = chess.Move(asq, sq, promotion=chess.QUEEN)
        if board.is_legal(mv):
            best_val = v
            best_mv = mv
    return best_mv


def _see_on_square(board: chess.Board, sq: int) -> int:
    """Static exchange value for the side to move recapturing on `sq` (cp).

    Recursive swap-off with the least-valuable attacker; max(0, …) models the
    option to stop capturing when continuing would lose material. Operates on the
    real board (push/pop), so x-ray attackers behind the first one are handled."""
    mv = _lva_capture(board, sq)
    if mv is None:
        return 0
    captured = _PIECE_VAL[board.piece_at(sq).piece_type]
    board.push(mv)
    val = max(0, captured - _see_on_square(board, sq))
    board.pop()
    return val


def see_gain(board: chess.Board, move: chess.Move) -> int:
    """Net cp the side-to-move wins by playing this CAPTURE, under optimal exchange."""
    to_sq = move.to_square
    if board.is_en_passant(move):
        captured = _PIECE_VAL[chess.PAWN]
    else:
        tp = board.piece_at(to_sq)
        if tp is None:
            return 0
        captured = _PIECE_VAL[tp.piece_type]
    board.push(move)
    gain = captured - _see_on_square(board, to_sq)
    board.pop()
    return gain


def material_hung_after(board: chess.Board, coach_move: chess.Move) -> Tuple[int, Optional[chess.Move]]:
    """After the coach plays `coach_move`, the most material the OPPONENT can win
    with a single capture sequence (cp), and the capture that wins it.

    A return >= floor means `coach_move` is a free hang. 0 means nothing hangs."""
    board = board.copy()
    board.push(coach_move)
    worst = 0
    worst_cap: Optional[chess.Move] = None
    for mv in board.legal_moves:
        if board.is_capture(mv):
            g = see_gain(board, mv)
            if g > worst:
                worst = g
                worst_cap = mv
    return worst, worst_cap


def move_is_free_hang(board: chess.Board, move: chess.Move, floor_cp: int = DEFAULT_FLOOR_CP) -> bool:
    """True iff `move` hands the opponent >= floor_cp of material in one capture sequence."""
    worst, _ = material_hung_after(board, move)
    return worst >= floor_cp


# ── The hybrid floor (data-locked 2026-06-27) ──────────────────────────────
# SEE alone (one-move) caught only 2/6 real material hangs at Skill 0 — it misses
# MULTI-move catastrophes (a combination that wins the queen reads SEE=0). So the
# guard is two-pronged:
#   ONE_MOVE_FLOOR — a free piece+ hang to a SINGLE capture. Static SEE, no engine.
#   MULTI_MOVE_CATASTROPHE — a forced loss of a rook+ / walk into mate, seen by the
#       engine's eval drop. Set ABOVE a minor piece so the student is still ALLOWED
#       to win up to ~a piece via a tactic they must calculate (philosophy B's
#       teaching mistake) — we only veto the trust-breaking decisive losses.
ONE_MOVE_FLOOR_CP = 300
MULTI_MOVE_CATASTROPHE_CP = 500
# The replacement must be CLEARLY safe, not just barely under the catastrophe line —
# picking the most-losing "acceptable" move sat it right on the edge, where depth
# noise tipped it into a new catastrophe (Skill 5: 0 -> 2). Require a comfortable
# margin below the floor for the move we substitute in.
SAFE_REPLACE_MARGIN_CP = 120


def select_sound_coach_move(
    engine,
    board: chess.Board,
    proposed_move: chess.Move,
    *,
    one_move_floor: int = ONE_MOVE_FLOOR_CP,
    multi_move_floor: int = MULTI_MOVE_CATASTROPHE_CP,
    multipv: int = 12,
    depth: int = 14,
    time_limit: float = 0.4,
    human_policy_evidence=None,
) -> Tuple[chess.Move, bool]:
    """The coach soundness floor. Returns (move_to_play, was_guarded).

    Keeps the proposed (weakened-engine) move UNLESS it's a catastrophe:
      - a one-move free hang of a piece+ (SEE >= one_move_floor), OR
      - a forced eval drop of a rook+ / into mate (>= multi_move_floor).
    On a catastrophe, resamples to the WEAKEST engine candidate that is itself sound
    (preserving beatability — not the single best move). One multipv analyse on the
    coach's move path; the per-move eval reuses the multipv when present."""
    color = board.turn

    def _eval_of(info_cp_map, move):
        cp = info_cp_map.get(move)
        if cp is not None:
            return cp
        b2 = board.copy()
        b2.push(move)
        try:
            sc = engine.analyse(b2, chess.engine.Limit(depth=depth, time=time_limit))["score"]
            return -sc.pov(b2.turn).score(mate_score=100000)
        except Exception:
            return None

    def _is_catastrophe(move, move_cp, best_cp):
        worst, _ = material_hung_after(board, move)
        if worst >= one_move_floor:
            return True
        if move_cp is not None and best_cp is not None and (best_cp - move_cp) >= multi_move_floor:
            return True
        return False

    try:
        infos = engine.analyse(board, chess.engine.Limit(depth=depth, time=time_limit), multipv=multipv)
    except Exception:
        # No analysis available → fall back to the static one-move floor only.
        if move_is_free_hang(board, proposed_move, one_move_floor):
            for fallback in board.legal_moves:
                if not move_is_free_hang(board, fallback, one_move_floor):
                    return fallback, fallback != proposed_move
        return proposed_move, False

    cands: List[Tuple[chess.Move, int]] = []
    for info in infos:
        pv = info.get("pv")
        if pv:
            cands.append((pv[0], info["score"].pov(color).score(mate_score=100000)))
    if not cands:
        return proposed_move, False
    cp_map = {m: c for m, c in cands}
    best_cp = cands[0][1]

    prop_cp = _eval_of(cp_map, proposed_move)

    # Human likelihood may order only the candidates that this full-strength
    # analysis has already accepted. It cannot add a move to the safe set.
    if human_policy_evidence is not None:
        verified_safe = [
            (move, cp)
            for move, cp in cands
            if not _is_catastrophe(move, cp, best_cp)
        ]
        try:
            ranked = human_policy_evidence.rank_verified_candidates(
                tuple(move.uci() for move, _ in verified_safe)
            )
            if ranked:
                by_uci = {move.uci(): move for move, _ in verified_safe}
                selected = by_uci.get(ranked[0])
                if selected is not None:
                    return selected, selected != proposed_move
        except Exception:
            pass

    if not _is_catastrophe(proposed_move, prop_cp, best_cp):
        return proposed_move, False

    # Resample. Prefer the WEAKEST move that is CLEARLY safe (within the margin) so
    # the coach stays beatable without flirting with the catastrophe line. If no
    # candidate is clearly safe, fall back to the BEST sound move (definitely safe).
    clearly_safe = [
        (m, c) for m, c in cands
        if m != proposed_move and not _is_catastrophe(m, c, best_cp)
        and (best_cp - c) <= SAFE_REPLACE_MARGIN_CP
    ]
    if clearly_safe:
        return clearly_safe[-1][0], True  # weakest clearly-safe move
    sound = [(m, c) for m, c in cands if not _is_catastrophe(m, c, best_cp)]
    if sound:
        return sound[0][0], True  # best sound move (no weak-but-safe option existed)
    return proposed_move, False  # forced — nothing better
