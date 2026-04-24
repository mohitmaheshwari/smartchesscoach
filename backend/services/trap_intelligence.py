"""
Trap Intelligence Service
=========================

Given a user's analyzed games, detect which opening traps they've
encountered and return a coach-voice summary for surfacing on the Lab page.

Key principle: ONLY factual claims. If the user hit the Fried Liver setup
3 times as black with 2 full line executions, we say that exactly. No
inventing "you're weak at the Italian" without data.

Output shape (returned from get_user_trap_intelligence):
    {
      "has_data": bool,
      "top_insight": {
          "trap_name": "Fried Liver Attack",
          "opening_key": "italian-game",
          "encounters": 3,
          "sprung": 1,
          "user_color": "black",        # the color the user played most often
          "role_hint": "defender",      # "defender" / "attacker" / "both"
          "training_weakness": "king_safety",
          "headline": "You've faced the Fried Liver Attack 3 times as black.",
          "cta": "Train the defense",
      },
      "all_insights": [ ... ],   # sorted by encounters desc
      "total_encounters": int,
    }

Caller plumbs this into the Lab page. When `has_data` is False, card is hidden.
"""

from __future__ import annotations

import io
import logging
from collections import Counter, defaultdict
from typing import Dict, List

import chess
import chess.pgn

from services.trap_library import get_all_traps, training_weakness_for_trap

logger = logging.getLogger(__name__)


def _parse_pgn_sans(pgn: str) -> List[str]:
    """Extract the move SAN list from a PGN string."""
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
    except Exception as e:
        logger.debug(f"pgn parse failed: {e}")
        return []


def _match_prefix(sans: List[str], needle: List[str]) -> bool:
    if len(sans) < len(needle):
        return False
    return all(sans[i] == m for i, m in enumerate(needle))


def _match_consecutive_after(sans: List[str], start_idx: int, needle: List[str]) -> int:
    """How many of `needle` match consecutively starting at sans[start_idx]."""
    matched = 0
    for i, m in enumerate(needle):
        j = start_idx + i
        if j >= len(sans):
            break
        if sans[j] != m:
            break
        matched += 1
    return matched


def _flatten_library() -> List[Dict]:
    """One flat list of trap entries with their parent opening_key attached."""
    out: List[Dict] = []
    for opening_key, traps in get_all_traps().items():
        for trap in traps:
            setup = trap.get("setup_moves") or []
            if not setup:
                continue
            out.append({
                "opening_key": opening_key,
                "name": trap.get("name", "?"),
                "setup_moves": setup,
                "trap_line_moves": [
                    step["move"] for step in (trap.get("trap_line") or []) if step.get("move")
                ],
                "result_type": trap.get("result_type"),
                "difficulty": trap.get("difficulty"),
                "training_weakness": training_weakness_for_trap(trap),
            })
    return out


def _build_headline(
    trap_name: str,
    encounters: int,
    sprung: int,
    dominant_color: str,
    role_hint: str,
) -> str:
    """Coach-voice headline. Names the move count and color — no hedging."""
    times_word = "time" if encounters == 1 else "times"
    if role_hint == "defender":
        return f"You've faced the {trap_name} {encounters} {times_word} as {dominant_color}."
    if role_hint == "attacker":
        return f"You've had the {trap_name} setup {encounters} {times_word} as {dominant_color}."
    # "both" — user played both sides of the same trap setup
    return f"You've seen the {trap_name} {encounters} {times_word} across both colors."


def _cta_for_role(role_hint: str) -> str:
    """Button label per role. Training weakness + routing URL is built elsewhere."""
    if role_hint == "defender":
        return "Train the defense"
    if role_hint == "attacker":
        return "Execute the tactic"
    return "Learn the pattern"


async def get_user_trap_intelligence(db, user_id: str) -> Dict:
    """
    Scan the user's games and return trap encounter insights.

    Runs deterministically off the user's stored PGNs + the static trap
    library. Cheap enough to run on every Lab load (or cache for 5 min).
    """
    empty = {"has_data": False, "top_insight": None, "all_insights": [], "total_encounters": 0}

    traps = _flatten_library()
    if not traps:
        return empty

    # Pull the user's analyzed games
    games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "user_color": 1, "result": 1, "pgn": 1},
    ).to_list(500)

    if not games:
        return empty

    # user_id → trap_name → {encounters, sprung, full, colors, opening_key, training_weakness}
    bucket = defaultdict(lambda: {
        "encounters": 0,
        "sprung": 0,
        "full": 0,
        "colors": Counter(),
        "opening_key": "",
        "training_weakness": "",
        "result_type": "",
    })

    for g in games:
        sans = _parse_pgn_sans(g.get("pgn", ""))
        if not sans:
            continue
        user_color = (g.get("user_color") or "white").lower()

        for trap in traps:
            setup = trap["setup_moves"]
            if not _match_prefix(sans, setup):
                continue

            entry = bucket[trap["name"]]
            entry["encounters"] += 1
            entry["colors"][user_color] += 1
            entry["opening_key"] = trap["opening_key"]
            entry["training_weakness"] = trap["training_weakness"]
            entry["result_type"] = trap.get("result_type") or ""

            trap_line = trap["trap_line_moves"]
            if trap_line:
                matched = _match_consecutive_after(sans, len(setup), trap_line)
                if matched >= 1:
                    entry["sprung"] += 1
                if matched == len(trap_line):
                    entry["full"] += 1

    if not bucket:
        return empty

    # Build the insight list, sorted by encounters descending
    insights: List[Dict] = []
    for trap_name, data in bucket.items():
        if data["colors"]:
            dominant_color, _ = data["colors"].most_common(1)[0]
        else:
            dominant_color = "white"
        colors_seen = set(data["colors"].keys())
        if len(colors_seen) >= 2:
            role_hint = "both"
        elif data["result_type"] == "checkmate":
            # Checkmate traps — defender role is the one trying to avoid mate.
            role_hint = "defender" if dominant_color != _trap_setter_color(data) else "attacker"
        else:
            # Heuristic by dominant color + trap's typical setter side.
            setter_color = _trap_setter_color(data)
            role_hint = "attacker" if dominant_color == setter_color else "defender"

        insight = {
            "trap_name": trap_name,
            "opening_key": data["opening_key"],
            "encounters": data["encounters"],
            "sprung": data["sprung"],
            "full": data["full"],
            "user_color": dominant_color,
            "role_hint": role_hint,
            "training_weakness": data["training_weakness"],
            "headline": _build_headline(
                trap_name, data["encounters"], data["sprung"], dominant_color, role_hint
            ),
            "cta": _cta_for_role(role_hint),
        }
        insights.append(insight)

    insights.sort(key=lambda i: (-i["encounters"], -i["sprung"]))
    total = sum(i["encounters"] for i in insights)
    return {
        "has_data": True,
        "top_insight": insights[0] if insights else None,
        "all_insights": insights,
        "total_encounters": total,
    }


# ── Helpers ───────────────────────────────────────────────────────────

# A rough lookup: openings where white is typically the trap setter.
# The trap library doesn't label this explicitly; we infer by opening.
_WHITE_SETTER_OPENINGS = {
    "italian-game", "ruy-lopez", "scholars-mate-defense-trap",
    "vienna-game", "london-system", "queens-gambit", "slav-defense",
    "caro-kann", "french-defense", "philidor-defense", "opera-game",
}


def _trap_setter_color(entry: Dict) -> str:
    """Which color typically SETS this trap? Heuristic by opening_key."""
    key = entry.get("opening_key", "")
    if key in _WHITE_SETTER_OPENINGS:
        return "white"
    # Defenses and counter-openings — black is often the trap setter
    # (Albin counter-gambit's Lasker trap, Sicilian traps from black, etc.)
    if "defense" in key or "gambit" in key or "indian" in key:
        return "black"
    return "white"  # default
