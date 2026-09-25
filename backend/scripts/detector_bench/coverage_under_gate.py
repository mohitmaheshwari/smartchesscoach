"""What a production user actually feels, with the gate ENFORCED.

I measured 40% coverage earlier and reported it. That run was local, where
DETECTOR_QUALITY_GATE_ENFORCED defaults to "false", so can_influence() returns
True for every non-disabled detector. Production has it set to "true"
(checked on the box, 2026-09-25). So the 40% describes a machine that is not
the one users are on.

This runs the same production path twice - gate off, gate on - and reports
both. The difference is the coaching the registry is suppressing.

Read-only.
"""
import os, sys, asyncio, collections, json
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient


async def run(db, enforced):
    os.environ["DETECTOR_QUALITY_GATE_ENFORCED"] = "true" if enforced else "false"
    import importlib
    import services.detector_quality as dq
    importlib.reload(dq)
    from services.move_observation_deriver import derive_observations_for_game

    n_games = with_mistake = with_speaking = 0
    pairs = collections.Counter()
    speaking_ids = collections.Counter()
    cache = {}

    cur = db.game_analyses.find({}, {"_id": 0, "game_id": 1, "stockfish_analysis": 1}).limit(400)
    async for a in cur:
        sf = a.get("stockfish_analysis") or {}
        if not (sf.get("move_evaluations") or []):
            continue
        g = await db.games.find_one({"game_id": a["game_id"]},
                                    {"_id": 0, "user_color": 1, "user_id": 1, "pgn": 1})
        if not g:
            continue
        try:
            obs = derive_observations_for_game(
                sf, a["game_id"], g.get("user_id") or "u",
                (g.get("user_color") or "white").lower(), pgn=g.get("pgn"))
        except Exception:
            continue
        n_games += 1
        moments = 0
        saw = False
        for o in obs:
            mp = o.get("missed_pattern")
            if not mp:
                continue
            saw = True
            st = o.get("subtype")
            qid = "gap:%s:%s" % (mp, st) if st else "gap:%s" % mp
            pairs["%s / %s" % (mp, st or "(none)")] += 1
            if qid not in cache:
                try:
                    cache[qid] = dq.can_influence(qid, dq.QualitySurface.CAPTION)
                except Exception:
                    cache[qid] = False
            if cache[qid]:
                moments += 1
                speaking_ids[qid] += 1
        if saw:
            with_mistake += 1
        if moments:
            with_speaking += 1
    return {"games": n_games, "with_mistake": with_mistake, "with_speaking": with_speaking,
            "pairs": pairs, "speaking": speaking_ids, "cache": cache}


async def main():
    db = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://mongodb:27017"))[
        os.environ.get("DB_NAME", "test_database")]

    off = await run(db, False)
    on = await run(db, True)

    for label, r in (("GATE OFF (my earlier local run)", off),
                     ("GATE ON  (production today)", on)):
        g = max(r["games"], 1)
        print("=== %s ===" % label)
        print("  games analysed                        : %4d" % r["games"])
        print("  games with a flagged mistake          : %4d  %5.1f%%"
              % (r["with_mistake"], 100.0 * r["with_mistake"] / g))
        print("  games where a detector MAY explain one: %4d  %5.1f%%"
              % (r["with_speaking"], 100.0 * r["with_speaking"] / g))
        print("  ids allowed to speak: %s" % (dict(r["speaking"].most_common(8)) or "NONE"))
        print()

    print("=== what the registry suppresses in production ===")
    for k, n in on["pairs"].most_common(14):
        mp, st = k.split(" / ")
        qid = "gap:%s:%s" % (mp, st) if st != "(none)" else "gap:%s" % mp
        mark = "SPEAKS" if on["cache"].get(qid) else "silent"
        was = "SPEAKS" if off["cache"].get(qid) else "silent"
        flag = "   <- silenced by the gate" if (was == "SPEAKS" and mark == "silent") else ""
        print("  %-42s %6d   off:%-6s on:%-6s%s" % (k[:42], n, was, mark, flag))

asyncio.run(main())
