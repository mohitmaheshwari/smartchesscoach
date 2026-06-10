"""opening_namer.py — reliable, move-order-aware naming of the SPECIFIC opening.

Built 2026-06-10. The existing matchers were unusable for naming the specific opening on the live
coach-move panel:
  - coach_engine.opening_plans.get_opening_by_moves did LOOSE substring matching and MISLABELED
    (Four Knights -> "Petrov" — it saw the substring "nf6" regardless of move order).
  - opening_detection_service.detect_opening_from_moves returns only the broad FAMILY
    ("King's Pawn Game" for every 1.e4 line — too coarse to be useful).

This does a longest EXACT-PREFIX match of the played moves (SAN) against the curated `main_line`s in
data/coaching/opening_theory_tree.json (27 openings; verified 6/6 incl. Four Knights vs Petrov vs
Italian). It names the opening ONLY when the game's opening moves exactly equal a known main_line, so
it CANNOT mislabel — an unknown line simply returns None and no name is shown. Using existing data
with a correct matcher; not a new opening database.
"""
import json
import os
import logging
from functools import lru_cache
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

_TREE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "coaching", "opening_theory_tree.json"
)


@lru_cache(maxsize=1)
def _openings() -> List[Tuple[str, Tuple[str, ...], str]]:
    """(name, main_line tuple, plan) for every tree entry that has both name + main_line."""
    try:
        with open(_TREE_PATH, encoding="utf-8") as fh:
            tree = json.load(fh)
    except Exception as e:  # pragma: no cover
        logger.warning(f"[opening_namer] could not load opening_theory_tree.json: {e}")
        return []
    out = []
    for v in tree.values():
        if isinstance(v, dict) and v.get("main_line") and v.get("name"):
            plan = v.get("white_plan") or v.get("black_plan") or ""
            out.append((v["name"], tuple(v["main_line"]), plan))
    return out


def name_opening(moves: List[str]) -> Optional[Tuple[str, str]]:
    """Return (opening_name, plan) by the LONGEST main_line that is an exact prefix of `moves`,
    or None if no known main_line is a prefix. Never mislabels (exact prefix only)."""
    if not moves:
        return None
    best: Optional[Tuple[str, str]] = None
    best_len = 0
    for name, ml, plan in _openings():
        n = len(ml)
        if n > best_len and tuple(moves[:n]) == ml:
            best = (name, plan)
            best_len = n
    return best
