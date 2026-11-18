"""What a player knows, idea by idea (docs/daily_coach_plan_scope.md, section 9).

Two kinds of evidence, both already stored:
  - his games: `move_observations.tactic_tags` (services/tactic_tags.py) says,
    per proved idea, whether he FOUND it, MISSED his own chance, or ALLOWED it
    to the opponent;
  - puzzles: his answers on the day card's ideas (`puzzle_attempts` with a
    "theme-<idea>" topic).

States (provisional, scope open question 2):
  misses       - more of his own chances missed than found
  puzzles_only - solves the idea's puzzles but still misses it in games
  knows        - found at least as often as missed, at least twice
  unseen       - no evidence yet
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

GAMES_READ = 60
KNOWS_MIN_FOUND = 2
PUZZLE_MIN_ATTEMPTS = 3
PUZZLE_SOLVED_SHARE = 0.6

# tactic_tags motif / concept -> the day card's idea key (data/daily_themes.json).
_CONCEPT_KEY = {"tactic.mate_in_one": "mate_in_one", "tactic.back_rank_mate": "back_rank_mate"}
_MOTIF_KEY = {
    "free_piece": "hanging_piece", "fork": "fork", "pin": "pin", "skewer": "skewer",
    "discovered_attack": "discovered_attack", "back_rank_mate": "back_rank_mate", "forced_mate": "mate_in_two",
}


def idea_key(tag: Mapping[str, Any]) -> Optional[str]:
    return _CONCEPT_KEY.get(str(tag.get("concept_id") or "")) or _MOTIF_KEY.get(str(tag.get("motif") or ""))


def record(observations: Iterable[Mapping[str, Any]], attempts: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """key -> {found, missed, allowed, puzzles, solved, state}."""
    out: Dict[str, Dict[str, Any]] = {}

    def row(key: str) -> Dict[str, Any]:
        return out.setdefault(key, {"found": 0, "missed": 0, "allowed": 0, "puzzles": 0, "solved": 0})

    for o in observations:
        for t in o.get("tactic_tags") or ():
            key = idea_key(t)
            if key and t.get("kind") in ("found", "missed", "allowed"):
                row(key)[t["kind"]] += 1
    for a in attempts:
        topic = str(a.get("topic") or "")
        if topic.startswith("theme-"):
            r = row(topic[len("theme-"):])
            r["puzzles"] += 1
            r["solved"] += 1 if a.get("correct") else 0
    for r in out.values():
        r["state"] = state(r)
    return out


def state(r: Mapping[str, Any]) -> str:
    found, missed = r.get("found", 0), r.get("missed", 0)
    solves = r.get("puzzles", 0) >= PUZZLE_MIN_ATTEMPTS and r.get("solved", 0) >= PUZZLE_SOLVED_SHARE * r["puzzles"]
    if missed > found:
        return "puzzles_only" if solves else "misses"
    if found >= KNOWS_MIN_FOUND:
        return "knows"
    return "unseen"


def to_teach(rec: Mapping[str, Mapping[str, Any]]) -> List[str]:
    """Ideas he misses in his games, most missed first."""
    weak = [(k, r) for k, r in rec.items() if r["state"] in ("misses", "puzzles_only")]
    return [k for k, _ in sorted(weak, key=lambda kr: -kr[1]["missed"])]


async def load(db, user_id: str, analysed_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    ids = analysed_ids[:GAMES_READ]
    obs = await db.move_observations.find(
        {"user_id": user_id, "game_id": {"$in": ids}, "tactic_tags.0": {"$exists": True}},
        {"_id": 0, "tactic_tags": 1}).to_list(None) if ids else []
    attempts = await db.puzzle_attempts.find(
        {"user_id": user_id, "topic": {"$regex": "^theme-"}}, {"_id": 0, "topic": 1, "correct": 1}).to_list(None)
    return record(obs, attempts)
