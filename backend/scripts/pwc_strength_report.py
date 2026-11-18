"""Play with Coach results by player band and engine path. Read-only.

docs/coaching_intelligence_scope.md, 1b. The acceptance report for the
opponent: real games only (15+ moves), staff and development accounts left
out, the player's coaching rating from his player file when there is one.
The game is the unit; each band also reports how many players its games come
from, because games of one player are not independent.

Run in a throwaway container with MONGO_URL and DB_NAME set:
    python scripts/pwc_strength_report.py
"""
from __future__ import annotations

import collections
import math
import os
from typing import Any, Dict, Iterable, Mapping, Optional

REAL_GAME_PLIES = 30
BANDS = ("<1000", "1000-1399", "1400-1799", "1800+")


def band(rating: Optional[float]) -> str:
    if rating is None:
        return "no rating"
    return "<1000" if rating < 1000 else "1000-1399" if rating < 1400 else "1400-1799" if rating < 1800 else "1800+"


def plies(session: Mapping[str, Any]) -> int:
    if isinstance(session.get("plies_at_end"), int):
        return session["plies_at_end"]
    return len(session.get("move_history") or [])


def wilson(k: float, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - r) / d, 2), round((c + r) / d, 2))


def report(sessions: Iterable[Mapping[str, Any]], roles: Mapping[str, Any],
           ratings: Mapping[str, Optional[float]]) -> Dict[str, Any]:
    """Score (win 1, draw 0.5) per (band, engine path) on real games by players."""
    rows: Dict[tuple, Dict[str, Any]] = collections.defaultdict(lambda: {"games": 0, "points": 0.0, "players": set(),
                                                                          "endings": collections.Counter()})
    left_out = collections.Counter()
    for s in sessions:
        uid = s.get("user_id") or ""
        if s.get("result") not in ("win", "loss", "draw"):
            left_out["unfinished"] += 1
            continue
        if roles.get(uid) in ("admin", "super_admin") or uid.startswith("dev_"):
            left_out["staff or development account"] += 1
            continue
        if plies(s) < REAL_GAME_PLIES:
            left_out["under 15 moves"] += 1
            continue
        strength = s.get("opponent_strength") or {}
        path = strength.get("engine_path") or ("weakened_engine" if s.get("game_mode") == "play" else "teaching_selector")
        r = rows[(band(ratings.get(uid) or s.get("user_rating")), path)]
        r["games"] += 1
        r["points"] += {"win": 1.0, "draw": 0.5, "loss": 0.0}[s["result"]]
        r["players"].add(uid)
        r["endings"][s.get("termination_reason") or "not recorded"] += 1
    out = {}
    for (b, path), r in sorted(rows.items()):
        out[f"{b} / {path}"] = {"games": r["games"], "players": len(r["players"]),
                                "score": round(r["points"] / r["games"], 2), "interval": wilson(r["points"], r["games"]),
                                "endings": dict(r["endings"])}
    return {"rows": out, "left_out": dict(left_out)}


def main() -> None:
    from pymongo import MongoClient

    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    roles = {u["user_id"]: u.get("role") for u in db.users.find({}, {"_id": 0, "user_id": 1, "role": 1})}
    ratings = {f["user_id"]: f.get("rating") for f in db.player_coach_files.find({}, {"_id": 0, "user_id": 1, "rating": 1})}
    sessions = db.coach_sessions.find({}, {"_id": 0, "user_id": 1, "result": 1, "user_rating": 1, "game_mode": 1,
                                           "move_history": 1, "plies_at_end": 1, "termination_reason": 1,
                                           "opponent_strength": 1})
    import json

    print(json.dumps(report(sessions, roles, ratings), indent=1))


if __name__ == "__main__":
    main()
