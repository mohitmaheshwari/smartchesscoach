"""
Per-game trap scanner with teaching-gold classification.

Single source of truth for: given one PGN + the user's color, return the
list of trap fires from the data/traps.json library, each classified by
role (setter/victim) and by teaching value (gold/celebration/lucky/
warning) per [[surface-teaching-gold-proactively]].

Consumers:
  - backend/scripts/backfill_trap_fires.py — one-shot corpus pass that
    writes a `trap_fires` field to every game_analyses doc.
  - backend/analysis_worker.py — calls this for new games right after
    Stockfish analysis completes, persists results to the same field.
  - services/trap_intelligence.py (future refactor) — should read the
    pre-computed `trap_fires` field instead of re-running on every
    Lab page load.

The scanner is pure-Python (no Stockfish, no DB). It can run inline on a
PGN string. ~5-30ms per game depending on length.
"""

from __future__ import annotations

import io
import logging
from typing import Dict, List, Optional

import chess
import chess.pgn

from services.trap_library import get_all_traps, training_weakness_for_trap

logger = logging.getLogger(__name__)


# Module-level cache: flattened (opening_key, trap_dict) list, one pass at
# import time. Reload by calling _refresh_trap_index().
_TRAP_INDEX: Optional[List[Dict]] = None


def _refresh_trap_index() -> List[Dict]:
    global _TRAP_INDEX
    flat: List[Dict] = []
    for opening_key, traps in get_all_traps().items():
        for trap in traps:
            setup = trap.get("setup_moves") or []
            if not setup:
                continue
            flat.append({
                "opening_key": opening_key,
                "name": trap.get("name", "?"),
                "setup_moves": setup,
                "trap_line_moves": [
                    step["move"] for step in (trap.get("trap_line") or []) if step.get("move")
                ],
                "result_type": trap.get("result_type"),
                "difficulty": trap.get("difficulty"),
                "training_weakness": training_weakness_for_trap(trap),
                "description": trap.get("description", ""),
                # The side WHOSE TURN it is AFTER the setup_moves are played
                # — by convention in our data, this is the side that plays
                # the first move of the trap_line. Used to attribute setter
                # vs victim role to a user given their color.
                "side_to_move_after_setup": "white" if len(setup) % 2 == 0 else "black",
            })
    _TRAP_INDEX = flat
    return flat


def _trap_index() -> List[Dict]:
    if _TRAP_INDEX is None:
        return _refresh_trap_index()
    return _TRAP_INDEX


def _parse_pgn_sans(pgn: str) -> List[str]:
    if not pgn:
        return []
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None:
            return []
        sans: List[str] = []
        board = game.board()
        for move in game.mainline_moves():
            sans.append(board.san(move))
            board.push(move)
        return sans
    except Exception:
        return []


def _match_prefix(sans: List[str], needle: List[str]) -> bool:
    if len(sans) < len(needle):
        return False
    return all(sans[i] == m for i, m in enumerate(needle))


def _match_consecutive_after(sans: List[str], start_idx: int, needle: List[str]) -> int:
    matched = 0
    for i, m in enumerate(needle):
        j = start_idx + i
        if j >= len(sans):
            break
        if sans[j] != m:
            break
        matched += 1
    return matched


def _classify_role_and_gold(
    user_color: str,
    setter_color: str,
    setup_reached: bool,
    sprung_moves: int,
    full_sprung: bool,
) -> Dict[str, str]:
    """Map (setup-reached, sprung, full, who-is-setter, user-color) to:
      - role        : 'setter' / 'victim'
      - teaching_gold class: 'gold' / 'celebration' / 'lucky' / 'warning'

    Conventions (per [[surface-teaching-gold-proactively]]):
      user is SETTER:
        setup reached + sprung      → CELEBRATION (user landed the trap)
        setup reached + not sprung  → GOLD        (user missed the trap)
      user is VICTIM:
        setup reached + sprung      → WARNING     (opp landed the trap on user)
        setup reached + not sprung  → LUCKY       (opp missed the trap against user)
    """
    role = "setter" if user_color == setter_color else "victim"
    if not setup_reached:
        return {"role": role, "gold_class": "none"}
    sprung = sprung_moves >= 1
    if role == "setter":
        return {"role": "setter", "gold_class": "celebration" if sprung else "gold"}
    return {"role": "victim", "gold_class": "warning" if sprung else "lucky"}


def scan_pgn_for_traps(pgn: str, user_color: str) -> List[Dict]:
    """Scan a single PGN against the full 41-trap library. Returns a list
    of trap-fire records, one per trap whose setup_moves prefix matches.

    Each record:
      {
        "trap_name":         str,
        "opening_key":       str,
        "training_weakness": str,  # piece_safety / king_safety / tactical_oversight / ...
        "result_type":       str,  # checkmate / material / position
        "difficulty":        str,
        "description":       str,
        "setup_moves":       List[str],
        "trap_line":         List[str],
        "sprung_moves":      int,   # how many of trap_line played out (0..len(trap_line))
        "full_sprung":       bool,  # all of trap_line played out
        "setup_reached_ply": int,   # ply index where setup completed (0-based)
        "setter_color":      'white' | 'black',
        "user_color":        'white' | 'black',
        "role":              'setter' | 'victim',
        "gold_class":        'gold' | 'celebration' | 'lucky' | 'warning' | 'none',
      }
    """
    sans = _parse_pgn_sans(pgn)
    if not sans:
        return []

    user_color = (user_color or "white").lower()
    fires: List[Dict] = []

    for trap in _trap_index():
        setup = trap["setup_moves"]
        if not _match_prefix(sans, setup):
            continue

        setter_color = trap["side_to_move_after_setup"]
        trap_line = trap["trap_line_moves"]
        sprung_moves = _match_consecutive_after(sans, len(setup), trap_line) if trap_line else 0
        full_sprung = bool(trap_line) and sprung_moves == len(trap_line)

        roles = _classify_role_and_gold(
            user_color=user_color,
            setter_color=setter_color,
            setup_reached=True,
            sprung_moves=sprung_moves,
            full_sprung=full_sprung,
        )

        fires.append({
            "trap_name": trap["name"],
            "opening_key": trap["opening_key"],
            "training_weakness": trap["training_weakness"],
            "result_type": trap["result_type"],
            "difficulty": trap["difficulty"],
            "description": trap["description"],
            "setup_moves": setup,
            "trap_line": trap_line,
            "sprung_moves": sprung_moves,
            "full_sprung": full_sprung,
            "setup_reached_ply": len(setup) - 1,
            "setter_color": setter_color,
            "user_color": user_color,
            "role": roles["role"],
            "gold_class": roles["gold_class"],
        })

    return fires


# Version stamp persisted alongside trap_fires. Bump when the library
# changes (new traps added) or when classification logic changes so we
# can re-scan only stale rows during future backfills.
TRAP_SCANNER_VERSION = 1
