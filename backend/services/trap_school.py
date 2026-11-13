"""The trap school: opening traps that really happen at our players' levels,
each with real games where it happened.

Content lives in data/trap_school.json, built once (2026-11-13) from:
  - traps.json (the authored line and its explanations);
  - trap_roles_verified.json (Stockfish decides which side the trap wins for);
  - the Lichess opening explorer at 1000-1800, blitz and rapid (how often
    players reach the setup and walk all the way in);
  - real Lichess games, each downloaded and replayed to confirm the line.
Nothing calls Lichess when a page opens. Figures stay in `measured` and never
reach the page; `how_common` says it in words.

A player's own traps (caught / waiting / could set / sprang) come from his
player file (services/player_coach_file.trap_record), so the school and his
opening file never disagree.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

logger = logging.getLogger(__name__)

PATH = Path(__file__).resolve().parent.parent / "data" / "trap_school.json"
CASE_ORDER = ("caught", "waiting", "could_set", "sprang")
CASE_TITLES = {
    "caught": "Traps that caught you",
    "waiting": "Traps that were waiting for you",
    "could_set": "Traps you can set",
    "sprang": "Traps you sprang",
}
_CACHE: Optional[List[Dict[str, Any]]] = None


def traps() -> List[Dict[str, Any]]:
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.loads(PATH.read_text(encoding="utf-8")).get("traps") or []
        except (OSError, ValueError):
            logger.warning("trap school file missing: %s", PATH)
            _CACHE = []
    return _CACHE


def slug(key: str) -> str:
    return key.replace("#", "-")


def _practice_url(practice_key: Optional[str]) -> Optional[str]:
    from services.player_coach_file import _practice_link
    return _practice_link(practice_key)


def card(t: Mapping[str, Any]) -> Dict[str, Any]:
    """What the list shows for one trap."""
    return {"slug": slug(t["key"]), "name": t["name"], "setter": t["setter"], "victim": t["victim"],
            "setup_fen": t["setup_fen"], "how_common": t["how_common"], "ends_in_mate": t.get("ends_in_mate"),
            "games": len(t.get("examples") or [])}


def detail(t: Mapping[str, Any]) -> Dict[str, Any]:
    """Everything one trap's page shows. No figures."""
    return {**card(t), "description": t.get("description"), "how_to_avoid": t.get("how_to_avoid"),
            "success_message": t.get("success_message"), "setup_san": t["setup_san"], "steps": t["steps"],
            "tempting_move": t.get("tempting_move"), "practice_url": _practice_url(t.get("practice_key")),
            "examples": [{k: ex.get(k) for k in ("id", "url", "white", "black", "winner", "speed", "year",
                                                  "moves", "result", "line_plies")}
                         for ex in t.get("examples") or []]}


def school(player_traps: Optional[Mapping[str, List[Mapping[str, Any]]]] = None) -> Dict[str, Any]:
    """The school's front page: his own traps first, by case, then every trap."""
    by_key = {t["key"]: t for t in traps()}
    mine: List[Dict[str, Any]] = []
    shown = set()
    for case in CASE_ORDER:
        rows = []
        for item in (player_traps or {}).get(case) or []:
            t = by_key.get(item.get("key"))
            if t is None:
                continue
            rows.append({**card(t), "game_id": item.get("game_id")})
            shown.add(t["key"])
        if rows:
            mine.append({"case": case, "title": CASE_TITLES[case], "traps": rows})
    return {"mine": mine, "all": [card(t) for t in traps()]}


def by_slug(value: str) -> Optional[Dict[str, Any]]:
    for t in traps():
        if slug(t["key"]) == value:
            return detail(t)
    return None
