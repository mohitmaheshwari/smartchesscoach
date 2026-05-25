"""
Trap recognition layer for V5 captions.

Reads backend/data/traps.json and detects when a played-move sequence
matches a known opening trap's `setup_moves`. Fires ONLY on the move
that COMPLETES the setup (the move that defines the trap's intent).

Returns a structured trap fact for the LLM prompt or renderer:

    {
        "name": "Blackburne Shilling Gambit",
        "family": "italian-game",
        "description": "Black plays Nd4 inviting Nxe5, then wins with Qg5! ...",
        "completed_by_move": "Nd4",
        "trap_line": ["Nxe5", "Qg5", "Nxf7", "Qxg2", ...],
        "result_type": "wins_material" | "mate" | ...
    }

Match policy:
  - Exact length + exact-prefix match on `setup_moves`.
  - Notation matching is tolerant of check/mate markers (Nd4+ matches Nd4).
  - Otherwise SAN must be identical (case-sensitive piece letters, 'x' marker
    preserved, disambiguation preserved). The traps.json author writes the
    canonical SAN — we don't transpose or normalize beyond +/#.

Per locked rule renderer_never_computes_chess_meaning: this module
returns FACTS only. Caption authoring decisions live in the renderer
or LLM prompt — not here.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TRAPS_PATH = Path(__file__).resolve().parent.parent / "data" / "traps.json"

_TRAPS_CACHE: Optional[List[Dict[str, Any]]] = None


def _strip_san(san: str) -> str:
    """Normalize SAN for matching: drop check/mate markers."""
    return (san or "").replace("+", "").replace("#", "")


def _load_traps() -> List[Dict[str, Any]]:
    """Flatten traps.json into a single list; cached after first call.

    Each entry carries both the move-only line (`trap_line`) for fast
    matching AND the full step list (`trap_line_steps`) with explanations
    so callers walking continuations can surface the authored prose.
    """
    global _TRAPS_CACHE
    if _TRAPS_CACHE is not None:
        return _TRAPS_CACHE

    try:
        data = json.loads(TRAPS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning(f"[trap] traps.json not found at {TRAPS_PATH}")
        _TRAPS_CACHE = []
        return _TRAPS_CACHE
    except Exception as e:
        logger.warning(f"[trap] failed to load traps.json: {e}")
        _TRAPS_CACHE = []
        return _TRAPS_CACHE

    flat: List[Dict[str, Any]] = []
    for family, trap_list in (data or {}).items():
        for trap in trap_list or []:
            setup_raw = trap.get("setup_moves") or []
            line_moves: List[str] = []
            line_steps: List[Dict[str, str]] = []
            for step in trap.get("trap_line") or []:
                if isinstance(step, dict):
                    mv = step.get("move", "") or ""
                    explanation = (step.get("explanation") or "").strip()
                else:
                    mv = step
                    explanation = ""
                if mv:
                    line_moves.append(mv)
                    line_steps.append({"move": mv, "explanation": explanation})
            flat.append({
                "family": family,
                "name": trap.get("name", "?"),
                "description": (trap.get("description") or "").strip(),
                "setup_moves": list(setup_raw),
                "setup_moves_norm": [_strip_san(m) for m in setup_raw],
                "trap_line": line_moves,
                "trap_line_steps": line_steps,
                "success_message": (trap.get("success_message") or "").strip(),
                "result_type": trap.get("result_type"),
                # v89: SETTER's color ('white' or 'black') — the side
                # that punishes / wins material / mates. Backfilled
                # across all 43 traps in 2026-05-25. Consumed by V5
                # to compute user_is_victim for the trap-warning caption.
                "trap_color": trap.get("trap_color"),
            })
    _TRAPS_CACHE = flat
    logger.info(f"[trap] loaded {len(flat)} traps from {TRAPS_PATH.name}")
    return _TRAPS_CACHE


def detect_trap_setup(played_moves_san: List[str]) -> Optional[Dict[str, Any]]:
    """Return a trap fact if `played_moves_san` exactly matches some
    trap's `setup_moves` (with +/# tolerance). Else None.

    Fires only on the move that COMPLETES the setup. If played sequence
    is shorter or longer than every trap's setup, no match.

    The returned dict's `trap_line_steps` is the authored continuation
    (move + explanation per step) used by the line-walker to annotate
    subsequent moves as in_line / deviation.
    """
    if not played_moves_san:
        return None
    normalized = [_strip_san(m) for m in played_moves_san]
    n = len(normalized)
    for trap in _load_traps():
        if len(trap["setup_moves_norm"]) != n:
            continue
        if trap["setup_moves_norm"] == normalized:
            return {
                "name": trap["name"],
                "family": trap["family"],
                "description": trap["description"],
                "completed_by_move": played_moves_san[-1],
                "trap_line": list(trap["trap_line"]),
                "trap_line_steps": list(trap["trap_line_steps"]),
                "result_type": trap.get("result_type"),
                "trap_color": trap.get("trap_color"),
                "success_message": trap.get("success_message"),
            }
    return None


def match_trap_line_step(trap: Dict[str, Any], played_san: str, step_index: int) -> bool:
    """True if `played_san` is the expected move at `step_index` in trap_line.
    +/# markers are tolerated; otherwise SAN must be identical.
    """
    line = trap.get("trap_line") or []
    if step_index < 0 or step_index >= len(line):
        return False
    return _strip_san(played_san) == _strip_san(line[step_index])
