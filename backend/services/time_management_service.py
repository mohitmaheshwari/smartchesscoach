"""
Time Management — what the player's own clock says
==================================================

A clock problem cannot be practised with puzzles. `/training/pattern/
time_collapse` used to render an empty puzzle board while Progress called time
discipline the player's number one focus, so a focus was promoted with nothing
behind it. This module supplies the thing that is actually true: the player's
own clock behaviour, read from the `[%clk]` stamps their games already carry.

Nothing here estimates or infers. Every number is a sum over stamps the
platform recorded, so the page can never make a claim the clock does not
support. See docs/time_management_practice_scope.md.

The design input is `long_thinks_per_game`. On the player this was built from
it is 1.2 — they are not slow, they play at a normal pace and then one or two
decisions balloon. That is what practice has to change; "play faster" would be
the wrong instruction.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CLK = re.compile(r"\[%clk\s+([0-9:.]+)\]")

# A think worth naming. Below this the move is ordinary play, not a decision
# that ate the clock.
LONG_THINK_SECONDS = 60

# Games needed before any of this is worth showing. Under this the numbers are
# noise and the surface should stay silent rather than coach from three games.
MIN_GAMES_FOR_PROFILE = 5


def _clock_to_seconds(stamp: str) -> Optional[float]:
    """'0:14:58.3' -> 898.3. None when the stamp is not parseable."""
    try:
        parts = [float(p) for p in str(stamp).split(":")]
    except (TypeError, ValueError):
        return None
    if not parts or len(parts) > 3:
        return None
    while len(parts) < 3:
        parts.insert(0, 0.0)
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


def _increment_seconds(time_control: Any) -> int:
    """'900+10' -> 10. Increment has to be added back or every move looks
    faster than it was."""
    text = str(time_control or "")
    if "+" not in text:
        return 0
    try:
        return int(text.split("+", 1)[1].strip())
    except (ValueError, IndexError):
        return 0


def _user_lost_on_time(game: Dict[str, Any]) -> bool:
    """Only a real flag-fall counts.

    Results are stored as '1-0'/'0-1', never as prose, so a substring search
    for "time" finds nothing -- a mistake made while building this. The result
    has to be read against the player's colour.
    """
    if str(game.get("termination") or "").lower() != "timeout":
        return False
    result = str(game.get("result") or "")
    is_white = str(game.get("user_color") or "").lower().startswith("w")
    if result == "1-0":
        return not is_white
    if result == "0-1":
        return is_white
    return False


def extract_own_move_times(
    pgn: str, user_is_white: bool, time_control: Any
) -> List[float]:
    """Seconds spent on each of the player's own moves, in order.

    The stamps alternate White, Black, so the player's own readings are every
    other one; time spent on a move is the drop between two consecutive
    readings plus the increment they got back.
    """
    stamps = [_clock_to_seconds(s) for s in _CLK.findall(pgn or "")]
    stamps = [s for s in stamps if s is not None]
    if len(stamps) < 4:
        return []
    mine = stamps[0::2] if user_is_white else stamps[1::2]
    if len(mine) < 2:
        return []
    increment = _increment_seconds(time_control)
    spent: List[float] = []
    for index in range(1, len(mine)):
        delta = mine[index - 1] - mine[index] + increment
        # A negative delta means the platform gave time back (or the stamps are
        # inconsistent); clamp rather than invent a negative think.
        spent.append(max(0.0, delta))
    return spent


def _phase(move_number: int) -> str:
    if move_number <= 10:
        return "moves_1_10"
    if move_number <= 20:
        return "moves_11_20"
    if move_number <= 30:
        return "moves_21_30"
    return "moves_31_plus"


def summarise_game(game: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One game's clock story, or None when it has no usable stamps."""
    user_is_white = str(game.get("user_color") or "").lower().startswith("w")
    spent = extract_own_move_times(
        game.get("pgn") or "", user_is_white, game.get("time_control")
    )
    if len(spent) < 8:
        return None
    total = sum(spent)
    if total <= 0:
        return None
    longest = max(spent)
    longest_at = spent.index(longest) + 2  # own-move numbering, first delta is move 2
    return {
        "game_id": game.get("game_id"),
        "lost_on_time": _user_lost_on_time(game),
        "seconds_used": round(total),
        "seconds_by_move_10": round(sum(spent[:10])),
        "seconds_by_move_20": round(sum(spent[:20])),
        "longest_think_seconds": round(longest),
        "longest_think_move": longest_at,
        "long_thinks": sum(1 for s in spent if s >= LONG_THINK_SECONDS),
        "moves_counted": len(spent),
    }


def build_time_profile(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate clock behaviour. Pure function so it is testable without a DB.

    `eligible` is False when there is not enough clock data to say anything,
    and the surface must stay silent in that case rather than coach from noise.
    """
    summaries = [s for s in (summarise_game(g) for g in games) if s]
    if len(summaries) < MIN_GAMES_FOR_PROFILE:
        return {
            "eligible": False,
            "reason": "not_enough_clock_data",
            "games_with_clock_data": len(summaries),
            "games_needed": MIN_GAMES_FOR_PROFILE,
        }

    timeout_losses = [s for s in summaries if s["lost_on_time"]]
    # The timeout losses are the interesting population; fall back to all games
    # when the sample has none, so the numbers still describe something real.
    focus = timeout_losses or summaries

    def _mean(values: List[float]) -> float:
        return (sum(values) / len(values)) if values else 0.0

    pct_by_10 = _mean([
        s["seconds_by_move_10"] / s["seconds_used"] * 100
        for s in focus if s["seconds_used"] > 0
    ])
    pct_by_20 = _mean([
        s["seconds_by_move_20"] / s["seconds_used"] * 100
        for s in focus if s["seconds_used"] > 0
    ])

    phases: Dict[str, int] = {
        "moves_1_10": 0, "moves_11_20": 0, "moves_21_30": 0, "moves_31_plus": 0,
    }
    for s in focus:
        phases[_phase(s["longest_think_move"])] += 1

    burn_moments = sorted(
        (
            {
                "game_id": s["game_id"],
                "move_number": s["longest_think_move"],
                "seconds": s["longest_think_seconds"],
                "lost_on_time": s["lost_on_time"],
            }
            for s in focus
            if s["longest_think_seconds"] >= LONG_THINK_SECONDS
        ),
        key=lambda m: -m["seconds"],
    )

    return {
        "eligible": True,
        "games_with_clock_data": len(summaries),
        "timeout_losses": len(timeout_losses),
        "timeout_loss_rate_pct": round(len(timeout_losses) / len(summaries) * 100, 1),
        "sample": "timeout_losses" if timeout_losses else "all_games",
        "sample_size": len(focus),
        "pct_clock_by_move_10": round(pct_by_10, 1),
        "pct_clock_by_move_20": round(pct_by_20, 1),
        "avg_longest_think_seconds": round(_mean([s["longest_think_seconds"] for s in focus])),
        "worst_think_seconds": max(s["longest_think_seconds"] for s in focus),
        "long_thinks_per_game": round(_mean([s["long_thinks"] for s in focus]), 1),
        "longest_think_phase": phases,
        "burn_moments": burn_moments[:10],
    }


async def get_time_profile(db, user_id: str, limit: int = 60) -> Dict[str, Any]:
    """Read the player's recent games and summarise their clock use."""
    try:
        games = await db.games.find(
            {"user_id": user_id, "pgn": {"$regex": r"%clk"}},
            {
                "_id": 0, "game_id": 1, "pgn": 1, "user_color": 1,
                "result": 1, "termination": 1, "time_control": 1,
            },
        ).sort("date_played_iso", -1).limit(limit).to_list(limit)
    except Exception as err:
        logger.warning(f"time profile query failed for {user_id}: {err}")
        return {"eligible": False, "reason": "query_failed"}
    return build_time_profile(games)
