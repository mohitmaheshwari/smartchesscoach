"""Pattern catalog loader + caption_facts → pattern_ids resolver.

The catalog itself lives in `backend/data/pattern_catalog.json` (one JSON
entry per pattern with human_name/short_description/family). Voice is
Mohit's domain; this module only owns the LOOKUP path: given the
caption_facts dict produced for a move, which pattern_ids fired?

Used by:
  - services/pattern_event_logger.py — when a user move triggers a
    detector, log a miss event keyed on the resolved pattern_id(s).
  - future P2 phase 2 — when detectors run on user GOOD moves too,
    same resolver decides whether to log a hit event.

Design notes:
  * Resolver is pure: in → caption_facts (dict), out → list of pattern
    IDs that are present in the facts. Order matches the catalog's
    priority intuition (mate > piece capture > tactical > positional)
    but a position can fire multiple at once and we return all of them.
  * Catalog read once at import time and cached. Reload via
    `_refresh_catalog()` if you edit pattern_catalog.json in dev.
  * pattern_ids are STABLE — once a pattern ships and event docs use
    its ID, the ID must never change. Only the displayed name/text
    can be tuned.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


_CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "pattern_catalog.json",
)

_catalog_cache: Optional[Dict] = None


def _refresh_catalog() -> Dict:
    global _catalog_cache
    try:
        with open(_CATALOG_PATH, "r", encoding="utf-8") as f:
            _catalog_cache = json.load(f)
    except Exception as e:
        logger.warning(f"[pattern_catalog] failed to load: {e}")
        _catalog_cache = {"patterns": {}}
    return _catalog_cache


def get_catalog() -> Dict:
    if _catalog_cache is None:
        return _refresh_catalog()
    return _catalog_cache


def get_pattern(pattern_id: str) -> Optional[Dict]:
    """Return the catalog entry for a pattern_id, or None if unknown."""
    return get_catalog().get("patterns", {}).get(pattern_id)


def resolve_pattern_ids(caption_facts: Dict) -> List[str]:
    """Given a caption_facts dict from V5 generation, return the list of
    pattern_ids that fired in that position. Empty list when no
    catalog-tracked pattern was present.

    The mapping reflects which detector populated which fact key. When
    a fact key is set with a non-empty value, the corresponding
    pattern fired.
    """
    if not caption_facts:
        return []
    ids: List[str] = []

    # Tactic detector (missed_tactic in caption_rules.py) — highest-
    # priority why-clauses, so log these first.
    kind = caption_facts.get("missed_tactic_kind")
    if kind == "mate":
        ids.append("missed_mate")
    elif kind == "piece_capture":
        ids.append("missed_piece")

    # Shape detector (clearance_for_attack)
    if caption_facts.get("missed_clearance_attack_square"):
        ids.append("clearance_for_attack")

    # Shape detector (clearance_then_check / Légal's family)
    if caption_facts.get("missed_clearance_then_check_follow_up_san"):
        ids.append("clearance_then_check")

    # Queen fork sub-kinds
    qfk = caption_facts.get("queen_fork_sub_kind")
    if qfk == "capture_with_check":
        ids.append("queen_fork_capture_with_check")
    elif qfk == "fork":
        ids.append("queen_fork")

    # Attack with tempo
    if caption_facts.get("attack_with_tempo_piece"):
        ids.append("attack_with_tempo")

    # Endgame loose pawn sub-kinds
    elk = caption_facts.get("endgame_loose_pawn_sub_kind")
    if elk == "direct_capture":
        ids.append("endgame_loose_pawn_capture")
    elif elk == "attack":
        ids.append("endgame_loose_pawn_attack")

    # Opening-principle detectors
    if caption_facts.get("un_developing_piece"):
        ids.append("un_developing")
    if caption_facts.get("defensive_pawn_user_san"):
        ids.append("defensive_pawn_push")
    if caption_facts.get("knight_outpost_destination"):
        ids.append("knight_outpost")
    if caption_facts.get("stop_opp_pawn_blocking_san"):
        ids.append("stop_opp_pawn")
    if caption_facts.get("knight_on_rim_square"):
        ids.append("knight_on_rim")
    if caption_facts.get("pawn_kicks_piece_square"):
        ids.append("pawn_kicks_piece")

    # Tactical/positional helpers
    if caption_facts.get("active_defense_defended_square"):
        ids.append("active_defense")
    if caption_facts.get("same_piece_better_extra_square"):
        ids.append("same_piece_better_square")
    if caption_facts.get("discovered_vac_exposed_square"):
        ids.append("discovered_vacating_check")

    # Principle detector — blocked own pawn
    if caption_facts.get("blocked_pawn_file"):
        ids.append("blocked_own_pawn")

    # Shape: king_pawn_lifted (kingside attack geometry)
    if caption_facts.get("shape_pattern_id") == "king_pawn_lifted":
        ids.append("king_pawn_lifted")

    # Trap context (v69) — the user missed punishing a known trap
    if caption_facts.get("trap_context_name"):
        ids.append("trap_punishment")

    return ids
