"""Opening names from Lichess's own list, with no network call.

data/lichess/lichess_openings.json holds every named opening and variation
(lichess-org/chess-openings, CC0, 3,865 lines, pulled 2026-11-09). A position
is looked up by its EPD, so a transposed move order still finds its name.

The Lichess opening explorer, which code used for names, has answered 401
without an API token since at least 2026-11-09; this needs no token at all.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

DATA = Path(__file__).resolve().parent.parent / "data" / "lichess" / "lichess_openings.json"


def _key(fen_or_epd: str) -> str:
    return " ".join(fen_or_epd.split(" ")[:4])


@lru_cache(maxsize=1)
def _by_position() -> Dict[str, Tuple[str, str, int]]:
    rows = json.loads(DATA.read_text(encoding="utf-8"))["openings"]
    out: Dict[str, Tuple[str, str, int]] = {}
    for o in rows:
        k = _key(o["epd"])
        # Several lines can reach one position; keep the most specific name
        # (the longest line), which is the one Lichess shows for it.
        if k not in out or o["plies"] > out[k][2]:
            out[k] = (o["name"], o["eco"], o["plies"])
    return out


def name_for_fen(fen: str) -> Optional[Tuple[str, str]]:
    """(name, eco) for this exact position, or None when Lichess names none."""
    hit = _by_position().get(_key(fen))
    return (hit[0], hit[1]) if hit else None


def explorer_headers() -> Dict[str, str]:
    """Headers for explorer.lichess.ovh. It refuses anonymous requests (401);
    a personal token without scopes (lichess.org/account/oauth/token) is
    enough, read from LICHESS_API_TOKEN. Never a player's stored token."""
    headers = {"Accept": "application/json", "User-Agent": "ChessCoachAI/1.0"}
    token = os.environ.get("LICHESS_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
