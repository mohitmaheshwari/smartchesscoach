"""What ChessGuru actually records per move, and on what share of rows.

Step 1 of the behavioural measurement proposal. The question is not which
fields exist -- it is what share of rows carry them, because a field present
on half the data cannot control for anything. Measured, not read off a schema.

Checked against the table in the proposal:
    FEN - engine evals/MultiPV - move played - clock before/after -
    best move + cp loss - rating + time control - outcome + move history
"""
import asyncio
import collections
import os
import re
import sys

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient

N_GAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 400
CLK = re.compile(r"%clk", re.I)


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]

    ids = []
    async for g in db.games.aggregate([
        {"$match": {"is_analyzed": True}},
        {"$sample": {"size": N_GAMES}},
        {"$project": {"_id": 0, "game_id": 1}},
    ]):
        ids.append(g["game_id"])

    # ---- per-move fields -------------------------------------------------
    present = collections.Counter()
    rows = 0
    opp_rows = 0
    opp_with_eval = 0
    for i in range(0, len(ids), 40):
        async for a in db.game_analyses.find(
            {"game_id": {"$in": ids[i:i + 40]}},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1},
        ):
            for m in ((a.get("stockfish_analysis") or {}).get("move_evaluations") or []):
                rows += 1
                if m.get("is_opponent_move"):
                    opp_rows += 1
                    if m.get("cp_loss") is not None:
                        opp_with_eval += 1
                for k, v in m.items():
                    if v is not None and v != "" and v != []:
                        present[k] += 1

    print("=" * 86)
    print("PER-MOVE FIELDS  (%d rows from %d analysed games)" % (rows, len(ids)))
    print("=" * 86)
    WANTED = {
        "fen_before": "position FEN (before)",
        "fen_after": "position FEN (after)",
        "move": "move played (SAN)",
        "move_uci": "move played (UCI)",
        "best_move": "engine best move",
        "cp_loss": "centipawn loss",
        "eval_before": "evaluation before",
        "eval_after": "evaluation after",
        "pv_after_best": "engine line after best",
        "pv_after_played": "engine line after played",
        "mate_info": "mate info",
        "is_opponent_move": "whose move",
        "move_number": "move number",
        "think_time": "CLOCK / thinking time",
        "clock": "CLOCK (raw)",
        "time_spent": "CLOCK (time spent)",
        "multipv": "MULTIPV alternatives",
        "alternatives": "MULTIPV alternatives (alt key)",
        "cognitive_gap": "gap label",
    }
    for key, label in WANTED.items():
        n = present.get(key, 0)
        pct = 100.0 * n / max(rows, 1)
        flag = "" if pct > 95 else ("   <-- PARTIAL" if pct > 0 else "   <-- ABSENT")
        print("  %-26s %-30s %6.1f%%%s" % (key, label, pct, flag))

    print()
    print("  opponent move rows: %d; of those with an engine cp_loss: %d (%.1f%%)" % (
        opp_rows, opp_with_eval, 100.0 * opp_with_eval / max(opp_rows, 1)))

    print()
    print("  every other field actually present, by share of rows:")
    for k, n in present.most_common():
        if k in WANTED:
            continue
        print("     %-28s %6.1f%%" % (k, 100.0 * n / max(rows, 1)))

    # ---- game-level context ---------------------------------------------
    print()
    print("=" * 86)
    print("GAME-LEVEL CONTEXT  (the controls the proposal asks for)")
    print("=" * 86)
    total = await db.games.count_documents({"is_analyzed": True})
    checks = {
        "user_rating": {"user_rating": {"$nin": [None, ""]}},
        "opponent_rating": {"opponent_rating": {"$nin": [None, ""]}},
        "time_control": {"time_control": {"$nin": [None, ""]}},
        "played_at_utc": {"played_at_utc": {"$ne": None}},
        "result": {"result": {"$nin": [None, ""]}},
        "termination": {"termination": {"$nin": [None, ""]}},
        "user_color": {"user_color": {"$nin": [None, ""]}},
        "pgn": {"pgn": {"$nin": [None, ""]}},
        "opening_name": {"opening_name": {"$nin": [None, ""]}},
    }
    for label, q in checks.items():
        q = dict(q)
        q["is_analyzed"] = True
        n = await db.games.count_documents(q)
        pct = 100.0 * n / max(total, 1)
        flag = "" if pct > 95 else ("   <-- PARTIAL" if pct > 0 else "   <-- ABSENT")
        print("  %-24s %6.1f%% of %d analysed games%s" % (label, pct, total, flag))

    # what time_control actually holds
    vals = collections.Counter()
    async for g in db.games.find({"is_analyzed": True, "time_control": {"$nin": [None, ""]}},
                                 {"_id": 0, "time_control": 1}).limit(3000):
        vals[str(g["time_control"])] += 1
    print("\n  what time_control actually contains:", dict(vals.most_common(6)))

    # clock in the PGN
    with_clk = 0
    seen = 0
    async for g in db.games.find({"is_analyzed": True, "pgn": {"$nin": [None, ""]}},
                                 {"_id": 0, "pgn": 1}).limit(500):
        seen += 1
        if CLK.search(g["pgn"] or ""):
            with_clk += 1
    print("  PGNs carrying a per-move clock (%%clk): %d of %d = %.0f%%" % (
        with_clk, seen, 100.0 * with_clk / max(seen, 1)))


asyncio.run(main())
