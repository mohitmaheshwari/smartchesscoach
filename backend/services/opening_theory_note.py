"""
Opening Theory Note — adds opening-specific theory alongside per-move coaching.

Purpose: when a Play-with-Coach session is in a known opening, attach a
brief 1200-friendly note to the move feedback. The note pairs with the
universal teaching rule from the move-level coach (e.g. "Rule: pieces
before pawns") to give the user *why this rule matters in this opening*.

Voice rules (per project_coach_voice memo):
  - Concrete pieces / squares / consequences only
  - No banned jargon — opening_curriculum.json was cleaned 2026-05-09
  - 1200 must be able to verify by looking at the board

Returns None when no opening is detected or no curriculum data exists —
honest silence beats fluffy filler (per feedback_no_hollow_coverage memo).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


_CURRICULUM_PATH = Path(__file__).resolve().parent.parent / "data" / "opening_curriculum.json"
_CURRICULUM_CACHE: Optional[Dict] = None


# detect_opening_from_moves returns its own keyspace (qgd, qga, slav, etc.)
# but opening_curriculum.json uses family-level keys (queens_gambit). When
# the detector key doesn't directly match, try this alias map to find the
# closest curriculum entry. Family-level theory still teaches the right
# ideas for any sub-variation.
_DETECTOR_TO_CURRICULUM_KEY = {
    # Queen's Gambit family — all variations map to the family entry
    "qgd": "queens_gambit",
    "qga": "queens_gambit",
    "slav": "queens_gambit",
    "semi_slav": "queens_gambit",
    "queens_gambit_declined": "queens_gambit",
    "queens_gambit_accepted": "queens_gambit",
    # Italian family
    "italian_game": "italian_game",
    "two_knights_defense": "italian_game",
    # Sicilian family
    "sicilian_defense": "sicilian_defense",
    # Direct matches (no alias needed but listed for clarity)
    "ruy_lopez": "ruy_lopez",
    "caro_kann": "caro_kann",
    "french_defense": "french_defense",
    "scandinavian_defense": "scandinavian_defense",
    "london_system": "london_system",
}


def _load_curriculum() -> Dict:
    """Lazy-load the opening curriculum data file once per process."""
    global _CURRICULUM_CACHE
    if _CURRICULUM_CACHE is not None:
        return _CURRICULUM_CACHE
    try:
        with _CURRICULUM_PATH.open("r", encoding="utf-8") as f:
            _CURRICULUM_CACHE = json.load(f)
    except Exception as exc:
        logger.warning(f"opening_theory_note: failed to load curriculum: {exc}")
        _CURRICULUM_CACHE = {}
    return _CURRICULUM_CACHE


def get_opening_theory_note(
    move_history: List[str],
    move_number: int,
    opening_phase_max: int = 12,
) -> Optional[Dict]:
    """
    Build an opening-theory note for the current PwC move feedback.

    Args:
        move_history: SAN moves played so far in the game (alternating colors).
        move_number: The current full-move number — used to gate the note to
            the opening phase only.
        opening_phase_max: Stop firing notes after this full-move number.
            Default 12 — beyond that we're in middlegame and the note adds
            noise.

    Returns:
        None when no opening is detected or no theory data exists. Otherwise:
            {
                "opening_name": "Queen's Gambit",
                "summary": "Offer a pawn with c4 to control the center...",
                "key_rule": "c4 fights for d5 control."
            }
        Frontend can render summary + key_rule as a single callout, or
        either alone.
    """
    if not move_history or move_number <= 0 or move_number > opening_phase_max:
        return None

    try:
        from services.opening_mastery import detect_opening_from_moves
    except Exception as exc:
        logger.warning(f"opening_theory_note: detector import failed: {exc}")
        return None

    info = detect_opening_from_moves(move_history)
    if not info:
        return None

    opening_key = info.get("opening_key")
    if not opening_key:
        return None

    curriculum = _load_curriculum()
    # Try direct match first; fall back to detector→curriculum alias.
    data = curriculum.get(opening_key) or curriculum.get(
        _DETECTOR_TO_CURRICULUM_KEY.get(opening_key, "")
    )
    if not data:
        # Detector recognised the opening but we don't have curriculum
        # data for it yet — silent fall-through (no fluffy filler).
        return None

    summary = (data.get("summary") or "").strip()
    golden_rules = data.get("golden_rules") or []
    key_rule = (golden_rules[0].strip() if golden_rules else "")

    if not summary and not key_rule:
        return None

    return {
        "opening_name": data.get("name") or info.get("opening_name"),
        "summary": summary,
        "key_rule": key_rule,
    }
