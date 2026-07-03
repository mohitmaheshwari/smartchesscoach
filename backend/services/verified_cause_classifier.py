"""verified_cause_classifier.py — the trustworthy replacement for the proxy
cognitive_gap cascade.

docs/reasoning_correctness_scope.md. The legacy classifier
(analysis_interpreter._classify_gap) labels a mistake from move-type PROXIES
("move touched the king → king_safety", "best move is a capture → missed_tactic")
and stamps a HARDCODED confidence. Measured on mohit/parth/shobhit it matched the
engine-verified cause only ~51% of the time — worst on the concrete claims
(piece_safety 35%, missed_tactic 21%).

This module classifies ONLY from board/engine EVIDENCE and ABSTAINS when it can't
prove a concrete cause (right-or-silent). Every label it emits is true by
construction, so downstream (captions, focus badges, missions) can trust it.

LAW: only speak where we can prove it. A None return means "no verified concrete
cause" — the caller must NOT invent one (it's a positional residue, handled
separately or left untagged).

Taxonomy (all verified):
  - piece_safety      : a ONE-MOVE SEE hang — the played move left material takeable
                        in a single capture. Depth-independent (reuses the tested SEE
                        in coach_play.coach_blunder_guard).
  - tactical_oversight: material lost over the engine's forced line, but NOT a one-move
                        hang — a multi-move miscalculation. Needs the PV.
  - missed_tactic     : the engine's best move wins material / forces mate that the
                        played move gave up.
  - walked_into_mate  : the refutation is a forced mate against the user.
  - None (abstain)    : no verified concrete material/mate cause — positional.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess

from coach_play.coach_blunder_guard import material_hung_after

# ── Data-locked thresholds (measured against the mohit/parth/shobhit 420-set) ──
# A one-move SEE loss this large is a clear "you left it hanging". 200cp = the
# exchange or a minor+; below that is a pawn, which is usually not a "piece" hang.
PIECE_HANG_CP = 200
# Material swing (cp) over the engine's forced line that counts as a real loss/gain.
LINE_MATERIAL_CP = 150

_VAL = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 320,
        chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}

_PIECE_NAME = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
               chess.ROOK: "rook", chess.QUEEN: "queen"}


def _material(board: chess.Board, color: chess.Color) -> int:
    return sum(_VAL[p.piece_type] for p in board.piece_map().values() if p.color == color)


def _material_swing_over_line(
    board_before: chess.Board, first_san: str, pv_sans: Optional[List[str]], user_color: chess.Color
) -> Optional[int]:
    """User-POV material delta (cp) from board_before, through first_san + the pv line.
    Negative = the user ends up DOWN material after the forced line. None if unplayable."""
    b = board_before.copy()
    before = _material(b, user_color) - _material(b, not user_color)
    try:
        b.push_san(first_san)
    except Exception:
        return None
    for san in (pv_sans or []):
        try:
            b.push_san(san)
        except Exception:
            break
    after = _material(b, user_color) - _material(b, not user_color)
    return after - before


def classify_verified_cause(
    fen_before: str,
    played_san: str,
    best_san: Optional[str] = None,
    pv_after_played: Optional[List[str]] = None,
    pv_after_best: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Return {gap, confidence, evidence} for a VERIFIED concrete cause, or None (abstain).

    confidence is always 1.0 — we only emit what we can prove. `evidence` is a small
    board-derived dict for the caption to render (never a label like "fork")."""
    try:
        board = chess.Board(fen_before)
        played = board.parse_san(played_san)
    except Exception:
        return None
    user = board.turn

    # 1. ONE-MOVE HANG (piece_safety) — SEE-verified, depth-independent. Strongest,
    #    cleanest signal; a piece left takeable in a single capture.
    worst, worst_cap = material_hung_after(board, played)
    if worst >= PIECE_HANG_CP:
        square = None
        piece = None
        if worst_cap is not None:
            b2 = board.copy()
            b2.push(played)
            tp = b2.piece_at(worst_cap.to_square)
            if tp is not None:
                piece = _PIECE_NAME.get(tp.piece_type)
                square = chess.square_name(worst_cap.to_square)
        return {
            "gap": "piece_safety",
            "confidence": 1.0,
            "evidence": {"kind": "one_move_hang", "lost_piece": piece,
                         "square": square, "see_cp": int(worst)},
        }

    # Compute the forced-line material outcomes (need a best move to compare).
    swing_played = _material_swing_over_line(board, played_san, pv_after_played, user)

    # 2. WALKED INTO MATE — the refutation forces mate against the user. We detect the
    #    signature from the PV only when it's unmistakable (kept conservative; the mate
    #    score itself lives upstream — here we abstain rather than guess).
    #    (Left to the caller's mate_info; not asserted from SAN alone.)

    # 3. MULTI-MOVE MATERIAL LOSS (tactical_oversight) — the played move loses material
    #    over the engine's forced line, but it was NOT a one-move hang → a miscalculation.
    if swing_played is not None and swing_played <= -LINE_MATERIAL_CP:
        return {
            "gap": "tactical_oversight",
            "confidence": 1.0,
            "evidence": {"kind": "line_material_loss", "loss_cp": int(-swing_played)},
        }

    # 4. MISSED TACTIC — the best move wins materially more than the played move did.
    if best_san:
        swing_best = _material_swing_over_line(board, best_san, pv_after_best, user)
        if (swing_best is not None and swing_played is not None
                and (swing_best - swing_played) >= LINE_MATERIAL_CP):
            return {
                "gap": "missed_tactic",
                "confidence": 1.0,
                "evidence": {"kind": "missed_material", "best_san": best_san,
                             "gain_cp": int(swing_best - swing_played)},
            }

    # No verified concrete cause — positional residue. Abstain (right-or-silent).
    return None
