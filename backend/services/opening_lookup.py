"""
Opening recognition layer for V5 captions.

Loads backend/data/opening_curriculum.json and matches the played-move
sequence's color-side moves against each opening's `setup_order`.
Returns the deepest-matching opening entry, carrying:

  - name           : "Italian Game"
  - color          : "white" | "black"
  - summary        : one-sentence pitch (authored)
  - golden_rules   : list of authored short principles
  - matched_steps  : how many setup moves matched (0 = no setup played yet)
  - next_expected  : next setup move the side "should" play, or None

Per locked rule renderer_never_computes_chess_meaning: this module
returns FACTS only. Caption authoring decisions live in the renderer
or LLM prompt — not here.

Match policy:
  - For each opening, compare its `setup_order` (the side's own moves
    in canonical order) to the actual moves played by that side so
    far in the game (white moves if color == "white", else black).
  - Longest matching prefix wins. Ties: deterministic by dict order.
  - +/# markers tolerated when comparing.

Multiple openings in opening_curriculum.json describe the same game
from different perspectives (e.g. italian_game / italian_game_black).
match_opening_for_mover() accepts the moving side's colour and returns
that side's opening — the relevant teaching frame for THAT move.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CURRICULUM_PATH = Path(__file__).resolve().parent.parent / "data" / "opening_curriculum.json"

_CACHE: Optional[List[Dict[str, Any]]] = None


def _strip_san(san: str) -> str:
    return (san or "").replace("+", "").replace("#", "")


def _load() -> List[Dict[str, Any]]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        data = json.loads(CURRICULUM_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning(f"[opening] curriculum not found at {CURRICULUM_PATH}")
        _CACHE = []
        return _CACHE
    except Exception as e:
        logger.warning(f"[opening] failed to load curriculum: {e}")
        _CACHE = []
        return _CACHE

    flat: List[Dict[str, Any]] = []
    for key, entry in (data or {}).items():
        if not isinstance(entry, dict):
            continue
        setup = [str(m) for m in (entry.get("setup_order") or [])]
        flat.append({
            "key": key,
            "name": entry.get("name") or key.replace("_", " ").title(),
            "color": (entry.get("color") or "").lower(),
            "summary": (entry.get("summary") or "").strip(),
            "golden_rules": list(entry.get("golden_rules") or []),
            "setup_order": setup,
            "setup_order_norm": [_strip_san(m) for m in setup],
        })
    _CACHE = flat
    logger.info(f"[opening] loaded {len(flat)} curriculum entries")
    return _CACHE


def _moves_for_color(played_moves_san: List[str], color: str) -> List[str]:
    """Return ONLY the moves played by `color`. Played sequence
    alternates white, black, white, black starting at index 0 = white.
    """
    if color == "white":
        return played_moves_san[0::2]
    return played_moves_san[1::2]


def match_opening_for_mover(
    played_moves_san: List[str],
    mover_color: str,
) -> Optional[Dict[str, Any]]:
    """Return the deepest-matching opening for the side that just moved.

    Args:
        played_moves_san: full played-move SAN sequence so far (both sides).
        mover_color: "white" or "black" — the side whose move just landed.

    Returns:
        Dict with the matched opening's authored content, or None if no
        match. The returned dict's `matched_steps` reflects how many of
        the side's own setup moves have been played in order, and
        `next_expected` is the next setup move (or None at end of setup).
    """
    if not played_moves_san:
        return None
    side_moves_norm = [_strip_san(m) for m in _moves_for_color(played_moves_san, mover_color)]
    if not side_moves_norm:
        return None

    best: Optional[Dict[str, Any]] = None
    best_steps = 0

    for entry in _load():
        if entry["color"] != mover_color:
            continue
        setup_norm = entry["setup_order_norm"]
        if not setup_norm:
            continue
        match_len = 0
        for i in range(min(len(side_moves_norm), len(setup_norm))):
            if side_moves_norm[i] == setup_norm[i]:
                match_len += 1
            else:
                break
        if match_len > best_steps:
            best = entry
            best_steps = match_len

    if best is None or best_steps == 0:
        return None

    next_expected = (
        best["setup_order"][best_steps]
        if best_steps < len(best["setup_order"])
        else None
    )
    return {
        "name": best["name"],
        "color": best["color"],
        "summary": best["summary"],
        "golden_rules": list(best["golden_rules"]),
        "matched_steps": best_steps,
        "next_expected": next_expected,
    }
