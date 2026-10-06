"""Does the chooser choose? docs/home_session_scope.md

The failure to watch for is not a wrong answer, it is the same answer for
everybody. A chooser that says IMPROVE to all seventy players has not chosen.
"""
import asyncio, collections, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from motor.motor_asyncio import AsyncIOMotorClient
from services.pattern_decay_service import refresh_user_pattern_decay
from services.session_chooser import build_blocks, choose, total_minutes
from services.area_practice_links import practice_link


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
    modes, whys, lens = collections.Counter(), collections.Counter(), collections.Counter()
    modes2 = collections.Counter()
    for user_id in await db.games.distinct("user_id"):
        try:
            patterns = await refresh_user_pattern_decay(db, user_id)
        except Exception:
            patterns = {}
        focus = await db.user_active_focus.find_one(
            {"user_id": user_id, "status": "active", "type": {"$ne": "strength"}},
            {"_id": 0})
        has_practice = False
        if focus:
            link = await practice_link(db, user_id, str(focus.get("topic_key") or ""))
            has_practice = bool(link)
        # A recent sound sacrifice, if any.
        # games_ago must be REAL. An earlier version hardcoded 1 for any
        # brilliant move in the last twelve games, which faked recency and made
        # the chooser look like it was appreciating everybody.
        good = None
        recent = await db.games.find(
            {"user_id": user_id, "is_analyzed": True},
            {"_id": 0, "game_id": 1, "played_at_utc": 1, "date_played": 1}
        ).sort("played_at_utc", -1).limit(12).to_list(12)
        order = {g["game_id"]: i for i, g in enumerate(recent)}
        async for a in db.game_analyses.find(
                {"game_id": {"$in": list(order)}},
                {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1}):
            for m in ((a.get("stockfish_analysis") or {}).get("move_evaluations") or []):
                if not m.get("is_opponent_move") and m.get("is_brilliant"):
                    ago = order[a["game_id"]]
                    if good is None or ago < good["games_ago"]:
                        good = {"fen": m.get("fen_before"),
                                "move_san": m.get("move_san"), "games_ago": ago}
                    break
        out = choose(patterns, good, focus, has_practice)
        # Second run: what the SAME player sees tomorrow, once today's
        # appreciation has been shown and retired. This is the steady state and
        # it is the number that matters.
        from services.session_chooser import appreciation_key, APPRECIATE as _A
        shown = [appreciation_key(out["evidence"])] if out["mode"] == _A else []
        tomorrow = choose(patterns, good, focus, has_practice, already_shown=shown)
        modes2[tomorrow["mode"]] += 1
        modes[out["mode"]] += 1
        whys[out["why"]] += 1
        lens[len(build_blocks(out["mode"], out["evidence"], focus, has_practice))] += 1
    total = sum(modes.values())
    print("players: %d" % total)
    print("\nMODE")
    for k, v in modes.most_common():
        print("   %-12s %3d  (%.0f%%)" % (k, v, 100.0 * v / max(total, 1)))
    print("\nWHY")
    for k, v in whys.most_common():
        print("   %-26s %d" % (k, v))
    print("")
    print("TOMORROW -- today's appreciation retired; the steady state")
    for k, v in modes2.most_common():
        print("   %-12s %3d  (%.0f%%)" % (k, v, 100.0 * v / max(total, 1)))
    print("\nBLOCKS PER SESSION")
    for k, v in sorted(lens.items()):
        print("   %d blocks  %d players" % (k, v))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
