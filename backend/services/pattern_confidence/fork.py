"""
Fork Confidence Scorer (simple, SEE-based)
==========================================

3-signal formula instead of the full 6-component spec:
  • forced SEE on the best target square  → "is there material to win?"
  • standard SEE on the forker square     → "is the forker safe?"
  • target value floor                    → "are these targets worth fighting for?"

Tier mapping (per implementation proposal, not the authored spec):
  HIGH    target gain ≥ 300cp AND (forker safe OR check), at least one
          minor/major target
  MEDIUM  target gain ≥ 100cp AND forker safe, OR check + valuable
          target with no clear material yet
  LOW     forker would hang, OR no material to win, OR no valid
          fork shape — `reason` explains why so the voice layer can
          still teach (e.g., "the forking knight hangs to a pawn")

The "LOW with reason" departure from the authored spec is deliberate:
silent LOW discards a teaching moment. Naming the failure mode is
more valuable for a 1200 player than withholding it.

We use `forced_exchange_eval` (no step-0 clamp) for target gain so
the score distinguishes "no profitable capture" from "bad capture
forced." Standard `static_exchange_eval` is correct for forker safety —
the opponent only captures if it's actually profitable.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import chess

from .see import static_exchange_eval, forced_exchange_eval


_PIECE_VALUE_PAWNS = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 1000,
}

_PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}


def evaluate_fork(
    board_before: chess.Board,
    fork_move: chess.Move,
) -> Dict:
    """Score `fork_move` as a fork. Returns:

        {
          "detected": bool,
          "confidence": float (0..1),
          "tier": "HIGH" | "MEDIUM" | "LOW",
          "targets": [(square_name, piece_name, gain_cp), ...],
          "evidence": {
            "target_count": int,
            "high_value_targets": int,
            "forker_safe": bool,
            "forker_value_pawns": int,
            "forker_safety_loss_cp": int,    # >0 = opp profits by capturing
            "best_target_gain_cp": int,
            "gives_check": bool,
          },
          "reason": str   # populated when not detected or LOW tier
        }
    """
    board = board_before.copy()
    mover_color = board.turn

    if fork_move not in board.legal_moves:
        return _result(False, 0.0, "LOW", [], {}, "fork move is not legal here")

    board.push(fork_move)
    forker_sq = fork_move.to_square
    forker = board.piece_at(forker_sq)
    if not forker:
        return _result(False, 0.0, "LOW", [], {}, "no piece on fork square after move")

    # ── Find valuable targets ──
    valuable_targets: List[Tuple[int, int]] = []
    for sq in board.attacks(forker_sq):
        target = board.piece_at(sq)
        if not target or target.color == mover_color:
            continue
        if target.piece_type == chess.KING:
            continue  # check is tracked separately
        if target.piece_type >= chess.KNIGHT:
            valuable_targets.append((sq, target.piece_type))

    gives_check = board.is_check()

    # Need at least 2 targets, OR 1 target + check
    if len(valuable_targets) < 2 and not gives_check:
        return _result(
            False, 0.0, "LOW", [], {},
            "no fork shape — needs 2+ valuable targets or check+target"
        )
    if len(valuable_targets) < 1 and gives_check:
        return _result(
            False, 0.0, "LOW", [], {},
            "check alone isn't a fork — no valuable second target"
        )

    # ── Forker safety ──
    opp_color = not mover_color
    forker_safety_loss = static_exchange_eval(board, forker_sq, opp_color)
    forker_safe = forker_safety_loss <= 0 or gives_check

    # ── Best target gain (forced exchange, attacker committed to capture) ──
    target_gains: List[Tuple[int, int, int]] = []
    best_target_gain = 0
    for tsq, ttype in valuable_targets:
        gain_cp = forced_exchange_eval(board, tsq, mover_color)
        target_gains.append((tsq, ttype, gain_cp))
        if gain_cp > best_target_gain:
            best_target_gain = gain_cp

    # ── Evidence dict ──
    evidence = {
        "target_count": len(valuable_targets),
        "high_value_targets": sum(
            1 for _, t, _ in target_gains
            if _PIECE_VALUE_PAWNS.get(t, 0) >= 5
        ),
        "forker_safe": forker_safe,
        "forker_value_pawns": _PIECE_VALUE_PAWNS.get(forker.piece_type, 0),
        "forker_safety_loss_cp": forker_safety_loss,
        "best_target_gain_cp": best_target_gain,
        "gives_check": gives_check,
    }

    # ── Tier mapping ──
    if not forker_safe:
        # The forker hangs — the strongest negative signal.
        return _result(
            False, 0.15, "LOW", target_gains, evidence,
            f"the forking {_PIECE_NAMES.get(forker.piece_type, 'piece')} would be "
            f"captured for material gain ({forker_safety_loss}cp) — fork is fake"
        )

    # Forker is safe. Now classify by best target gain.
    if best_target_gain >= 300:
        # Winning at least a minor — clean.
        # Confidence scales with size of gain, capped at 1.0.
        confidence = min(1.0, 0.6 + best_target_gain / 1000.0)
        return _result(True, confidence, "HIGH", target_gains, evidence, "")

    if best_target_gain >= 100:
        # Pawn-level gain or partial material — real but smaller.
        confidence = 0.5 + best_target_gain / 1500.0
        return _result(True, confidence, "MEDIUM", target_gains, evidence, "")

    if gives_check and len(valuable_targets) >= 1:
        # Check + attack with no clear SEE gain — still has tempo value
        # because the king move loses control of the target.
        return _result(True, 0.45, "MEDIUM", target_gains, evidence, "")

    # No material to win and no check — fork shape exists but doesn't bite.
    return _result(
        False, 0.2, "LOW", target_gains, evidence,
        "fork shape exists, but every target is defended evenly — "
        "no material to win"
    )


def _result(
    detected: bool,
    confidence: float,
    tier: str,
    target_gains: List[Tuple[int, int, int]],
    evidence: Dict,
    reason: str,
) -> Dict:
    return {
        "detected": detected,
        "confidence": round(confidence, 3),
        "tier": tier,
        "targets": [
            (chess.square_name(sq), _PIECE_NAMES.get(t, "piece"), gain)
            for sq, t, gain in target_gains
        ],
        "evidence": evidence,
        "reason": reason,
    }


# Voice mapping per the authored spec, with the LOW-with-reason
# adjustment. Use this from coaching surfaces to render output.
def voice_for(result: Dict) -> Optional[str]:
    """Return the coach-voice line for a fork evaluation, or None when
    we should stay silent. None case: not detected AND no informative
    reason (e.g., "fork move is not legal here" — operational error,
    not coaching).
    """
    tier = result.get("tier")
    detected = result.get("detected")
    reason = result.get("reason") or ""

    if detected and tier == "HIGH":
        return "This is a clean fork."
    if detected and tier == "MEDIUM":
        return "This looks like a fork — check if it's safe."
    # LOW or not detected — show the reason if it's a teaching moment
    if reason and "fork" in reason.lower():
        return f"This isn't a clean fork — {reason}."
    return None
