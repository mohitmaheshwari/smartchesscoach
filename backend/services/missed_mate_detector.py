"""
missed_mate_detector.py — the user had a forced mate and didn't play it.

Built 2026-06-07 (overnight). From the bare-caption forensics "missed_MATE"
+ "missed_check" buckets. This is the OBJECTIVE end of the why-gap: if the
engine's best move is checkmate (or its PV forces mate) and the user played
something else, the caption should say so — "you had mate". Zero misfire
risk: mate is mate.

detect_missed_mate(board_before, best_move_san, pv_after_best, cp_loss)
  -> {"kind": "mate_in_1" | "forced_mate", "best_san": "Qh7", "mate_in": 3|None} | None

Conservative gate: cp_loss >= 100 (the played move actually gave the mate up;
guards against eval noise where two near-equal moves both mate).
"""
from typing import Optional, Dict, List
import chess

_MATE_RE_PLIES = 8  # how deep into the PV to look for the mate marker


def _mate_distance(pv: List[str]) -> Optional[int]:
    """Plies until the '#' in the PV → moves-to-mate (rounded up)."""
    for i, mv in enumerate(pv[:_MATE_RE_PLIES]):
        if "#" in mv:
            return (i // 2) + 1
    return None


def detect_missed_mate(
    board_before: chess.Board,
    best_move_san: Optional[str],
    pv_after_best: Optional[List[str]],
    cp_loss: Optional[int],
) -> Optional[Dict]:
    if not best_move_san or (cp_loss or 0) < 100:
        return None
    try:
        bm = board_before.parse_san(best_move_san)
    except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
        return None

    bb = board_before.copy()
    bb.push(bm)
    if bb.is_checkmate():
        return {"kind": "mate_in_1", "best_san": best_move_san, "mate_in": 1}

    if pv_after_best:
        # best_move_san is usually the first PV entry; mate marker deeper in.
        md = _mate_distance(pv_after_best)
        if md is not None:
            return {"kind": "forced_mate", "best_san": best_move_san, "mate_in": md}
    return None


def clause_for(mm: Dict) -> str:
    """1200-friendly clause naming the mate."""
    if mm["kind"] == "mate_in_1":
        return f"you had checkmate — {mm['best_san']} ends the game"
    n = mm.get("mate_in")
    if n:
        return f"you had a forced mate — {mm['best_san']} leads to checkmate in {n}"
    return f"you had a forced mate starting with {mm['best_san']}"
