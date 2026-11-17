"""Result records for the games the import does not coach on.

The import skips bullet, casual Lichess games and very short games
(journey_service.should_analyze_game). Until 2026-11-17 they were dropped
entirely, so the coach could never say "your 2+1 games go badly, mostly on the
clock": Mohit has 27 Lichess bullet games (rated 816 against 1354 in blitz)
and the database held none of them.

These records carry only what that advice needs: the clock, the result, how
the game ended, both ratings and the length. They live in their own
collection, never in `games`, so Home, the plan, habits and analysis are
untouched by them.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

COLLECTION = "skipped_game_records"
SCHEMA_VERSION = 1

_CC_LOSS = {"checkmated", "timeout", "resigned", "abandoned", "lose", "bughousepartnerlose", "kingofthehill", "threecheck"}
_CC_DRAW = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}


def _reason(game: Dict[str, Any], platform: str) -> str:
    speed = str(game.get("time_class") if platform == "chess.com" else game.get("speed") or "").lower()
    if speed in ("bullet", "ultrabullet"):
        return "bullet"
    if platform == "lichess" and not game.get("rated", False):
        return "casual"
    return "short"


def _cc_ending(white: Dict, black: Dict) -> str:
    codes = {str(white.get("result") or ""), str(black.get("result") or "")}
    if codes & {"timeout", "timevsinsufficient"}:
        return "time"
    if "checkmated" in codes:
        return "mate"
    if "resigned" in codes:
        return "resign"
    if "abandoned" in codes:
        return "abandon"
    if codes & _CC_DRAW:
        return "draw"
    return "other"


_LI_ENDING = {"outoftime": "time", "mate": "mate", "resign": "resign", "timeout": "abandon",
              "draw": "draw", "stalemate": "draw"}


def skipped_game_record(game: Dict[str, Any], platform: str, username: str,
                        user_id: str) -> Optional[Dict[str, Any]]:
    """One platform game -> a result record, or None when it cannot be read."""
    name = str(username or "").lower()
    if platform == "chess.com":
        white, black = game.get("white") or {}, game.get("black") or {}
        if str(white.get("username") or "").lower() == name:
            me, opp, color = white, black, "white"
        elif str(black.get("username") or "").lower() == name:
            me, opp, color = black, white, "black"
        else:
            return None
        code = str(me.get("result") or "")
        result = "win" if code == "win" else "draw" if code in _CC_DRAW else "loss" if code in _CC_LOSS else None
        tc = str(game.get("time_control") or "")
        base, _, inc = tc.partition("+")
        moves = len(set(re.findall(r"(?<![.\d])(\d+)\.(?!\.)", str(game.get("pgn") or ""))))
        ended = game.get("end_time")
        record = {
            "platform_game_id": str(game.get("url") or "").rstrip("/").rsplit("/", 1)[-1] or None,
            "url": game.get("url"),
            "speed": str(game.get("time_class") or "").lower(),
            "base_seconds": int(base) if base.isdigit() else None,
            "increment_seconds": int(inc) if inc.isdigit() else (0 if base.isdigit() else None),
            "rated": bool(game.get("rated")),
            "result": result,
            "ending": _cc_ending(white, black),
            "user_rating": me.get("rating"),
            "opponent_rating": opp.get("rating"),
            "full_moves": moves,
            "played_at_utc": datetime.fromtimestamp(ended, timezone.utc) if ended else None,
        }
    else:
        players = game.get("players") or {}
        ids = {c: str(((players.get(c) or {}).get("user") or {}).get("id") or "").lower() for c in ("white", "black")}
        color = "white" if ids["white"] == name else "black" if ids["black"] == name else None
        if color is None:
            return None
        other = "black" if color == "white" else "white"
        winner = game.get("winner")
        clock = game.get("clock") or {}
        created = game.get("createdAt")
        record = {
            "platform_game_id": game.get("id"),
            "url": f"https://lichess.org/{game.get('id')}",
            "speed": str(game.get("speed") or "").lower(),
            "base_seconds": clock.get("initial"),
            "increment_seconds": clock.get("increment"),
            "rated": bool(game.get("rated")),
            "result": "draw" if not winner else ("win" if winner == color else "loss"),
            "ending": _LI_ENDING.get(str(game.get("status") or ""), "other"),
            "user_rating": (players.get(color) or {}).get("rating"),
            "opponent_rating": (players.get(other) or {}).get("rating"),
            "full_moves": (len(str(game.get("moves") or "").split()) + 1) // 2,
            "played_at_utc": datetime.fromtimestamp(created / 1000, timezone.utc) if created else None,
        }
    if not record["platform_game_id"]:
        return None
    record.update(user_id=user_id, platform=platform, color=color,
                  reason=_reason(game, platform), schema_version=SCHEMA_VERSION)
    return record


async def store_skipped_games(db, user_id: str, games: Iterable[Dict[str, Any]],
                              platform: str, username: str, should_import) -> int:
    """Upsert a record for every fetched game the import skips. Returns how many."""
    stored = 0
    for game in games:
        if should_import(game, platform):
            continue
        record = skipped_game_record(game, platform, username, user_id)
        if not record:
            continue
        await db[COLLECTION].update_one(
            {"user_id": user_id, "platform": platform, "platform_game_id": record["platform_game_id"]},
            {"$set": {**record, "recorded_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        stored += 1
    return stored


__all__ = ["COLLECTION", "skipped_game_record", "store_skipped_games"]
