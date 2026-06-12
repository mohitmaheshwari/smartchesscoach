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
            # Authored move tree (named sub-variations live here). Kept so the
            # sub-variation matcher can walk it; setup_order alone is the
            # LEARNER's own moves and cannot distinguish anti-lines that the
            # OPPONENT chooses (Alapin 2.c3, Smith-Morra 2.d4, Caro Advance 3.e5).
            "tree": entry.get("tree") if isinstance(entry.get("tree"), dict) else None,
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


DEFAULT_MIN_MATCHED_STEPS = 3
"""How many setup moves of an opening must be played in order before
we declare the opening matched. Three lines up with the 'commitment'
move of every opening in opening_curriculum.json:

  - Italian Game (white): e4, Nf3, **Bc4** — Bc4 is the signature move
    that distinguishes Italian from Ruy Lopez (Bb5), Scotch (d4), etc.
  - Italian Game (black): e5, Nc6, **Bc5** — Bc5 distinguishes from
    Two Knights (Nf6), Petroff, Philidor, etc.
  - London System: d4, Nf3, **Bf4** — Bf4 distinguishes London from
    Colle, Torre, Queen's Gambit lines, etc.

Below 3 matched setup moves we deliberately return None so the LLM
doesn't claim a specific opening prematurely — moves 1 and 2 fall
back to primary_reason category teaching ("claims the centre",
"develops a knight").
"""


def _walk_sub_variation(
    tree: Dict[str, Any], moves_norm: List[str]
) -> tuple:
    """Walk one opening's authored move `tree` against the actual game moves
    and return ``(name, depth)`` of the DEEPEST node carrying a ``name`` — the
    most specific named sub-variation the game reached — or ``(None, 0)`` if
    the game left book before any named node.

    Tree model (uniform across colours — verified against the curriculum):
      node = {"name"?, "next"?, "responses"?}
        next      : the LEARNER's single expected reply (one ply, not branched)
        responses : {opponent_move: child_node} — the BRANCHING plies. The
                    named sub-variations live here because they are created by
                    the OPPONENT's choice (White's 2.c3 = Alapin, 3.e5 = Caro
                    Advance), which is exactly what setup_order can't see.

    `moves_norm` is the full alternating SAN sequence (White first), already
    +/#-stripped. At each step exactly one of {the node's ``next``, a
    ``responses`` key} matches the next game move — ``next`` is the learner's
    move and ``responses`` are the opponent's, so only one side is to move.
    """
    if not isinstance(tree, dict) or not tree:
        return (None, 0)
    deepest_name: Optional[str] = None
    deepest_depth = 0
    level: Any = tree            # {move: node} at the current branching ply
    i = 0
    while i < len(moves_norm) and isinstance(level, dict) and level:
        node = level.get(moves_norm[i])
        if not isinstance(node, dict):
            break
        name = node.get("name")
        if name:
            deepest_name = name
            deepest_depth = i + 1
        nxt = node.get("next")
        nxt = _strip_san(str(nxt)) if (nxt and str(nxt) != "None") else None
        resp = node.get("responses") or {}
        if nxt and i + 1 < len(moves_norm) and moves_norm[i + 1] == nxt:
            # learner played the expected reply; the branch sits one ply later
            i += 2
        else:
            # the next ply is itself the branch (opponent to move)
            i += 1
        level = resp
    return (deepest_name, deepest_depth)


def match_sub_variation(
    played_moves_san: List[str],
    opening_key: Optional[str] = None,
    min_depth: int = DEFAULT_MIN_MATCHED_STEPS,
) -> Optional[Dict[str, Any]]:
    """Return the most specific named sub-variation the game reached.

    Sub-variations (Alapin, Smith-Morra, Bowdler, Caro-Kann Advance, …) are
    defined by the OPPONENT's choice, which `match_opening_for_mover` (keyed
    off the learner's own setup_order) cannot distinguish — and in anti-lines
    the learner's moves often deviate from the main-line setup, so the family
    may not even match. This walks the full alternating move sequence against
    the authored `tree`, so it labels the sub-line directly from the moves.

    Args:
        played_moves_san: full SAN sequence so far (both sides, White first).
        opening_key: restrict to one curriculum opening's tree; if None, scan
            every opening and keep the deepest hit (cross-opening false matches
            are avoided by the exact move-tree walk + the min_depth gate).
        min_depth: plies that must match before we name a sub-variation
            (default 3 — same confidence gate as DEFAULT_MIN_MATCHED_STEPS; a
            2-ply line like 1.e4 c5 is just "Sicilian", not yet a sub-line).

    Returns {name, depth, opening_key} of the deepest named line, or None.
    """
    if not played_moves_san:
        return None
    moves_norm = [_strip_san(m) for m in played_moves_san]
    best_name: Optional[str] = None
    best_depth = 0
    best_key: Optional[str] = None
    for entry in _load():
        if opening_key is not None and entry["key"] != opening_key:
            continue
        tree = entry.get("tree")
        if not tree:
            continue
        name, depth = _walk_sub_variation(tree, moves_norm)
        if name and depth > best_depth:
            best_name, best_depth, best_key = name, depth, entry["key"]
    if not best_name or best_depth < min_depth:
        return None
    return {"name": best_name, "depth": best_depth, "opening_key": best_key}


def match_opening_for_mover(
    played_moves_san: List[str],
    mover_color: str,
    min_matched_steps: int = DEFAULT_MIN_MATCHED_STEPS,
) -> Optional[Dict[str, Any]]:
    """Return the deepest-matching opening for the side that just moved.

    Args:
        played_moves_san: full played-move SAN sequence so far (both sides).
        mover_color: "white" or "black" — the side whose move just landed.
        min_matched_steps: don't declare until this many of the side's
            setup moves have been played in order. Default 3 — see the
            DEFAULT_MIN_MATCHED_STEPS docstring for why.

    Returns:
        Dict with the matched opening's authored content, or None if
        no opening's setup has been played at least `min_matched_steps`
        moves into.
    """
    if not played_moves_san:
        return None
    side_moves_norm = [_strip_san(m) for m in _moves_for_color(played_moves_san, mover_color)]
    if not side_moves_norm:
        return None

    best: Optional[Dict[str, Any]] = None
    best_steps = 0

    # Opening fires ONLY while the side is still on-book within the
    # setup phase. The moment any move deviates from setup_order — or
    # the side plays past setup_order's length — no opening match.
    # (Previously this used longest-prefix match, which kept reporting
    # "Italian @ step 3" forever even after the side deviated at move 4.)
    n_played = len(side_moves_norm)
    for entry in _load():
        if entry["color"] != mover_color:
            continue
        setup_norm = entry["setup_order_norm"]
        if not setup_norm:
            continue
        if n_played > len(setup_norm):
            continue  # past the end of authored setup
        if side_moves_norm != setup_norm[:n_played]:
            continue  # any deviation kills the match
        match_len = n_played
        if match_len > best_steps:
            best = entry
            best_steps = match_len

    if best is None or best_steps < min_matched_steps:
        return None

    next_expected = (
        best["setup_order"][best_steps]
        if best_steps < len(best["setup_order"])
        else None
    )
    # Sub-variation tag (additive): the specific named line the game reached
    # (e.g. "Alapin (2.c3)") so progress can label the sub-line, not just the
    # family. Scoped to the matched opening's tree. None when still on the
    # generic main line. Existing consumers ignore the extra keys.
    sub = match_sub_variation(played_moves_san, opening_key=best["key"])
    return {
        "name": best["name"],
        "color": best["color"],
        "summary": best["summary"],
        "golden_rules": list(best["golden_rules"]),
        "matched_steps": best_steps,
        "next_expected": next_expected,
        "sub_variation": sub["name"] if sub else None,
        "sub_variation_depth": sub["depth"] if sub else 0,
    }
