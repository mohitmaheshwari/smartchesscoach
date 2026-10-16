"""Does the free in-pass measure agree with the expensive one?

The audit judged "did he go straight at it" with a fresh depth-14 analysis of
the position after their mistake. The fix uses `reply_cost` -- the cost of his
reply, already computed in the one pass the review makes. Cheap is only worth
having if it agrees.
"""
import asyncio, os, sys, io
import chess, chess.pgn, chess.engine
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
from services.both_sides_review import review_both_sides, PUNISHED_CP, CLAMP

async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    u = await db.users.find_one({"user_id": {"$regex": "8b599930d7ef"}}, {"_id": 0, "user_id": 1})
    cur = db.games.find(
        {"user_id": u["user_id"], "platform": {"$ne": "coach"},
         "pgn": {"$nin": [None, ""]}, "played_at_utc": {"$ne": None}},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1},
        sort=[("played_at_utc", -1)]).limit(30)

    eng = chess.engine.SimpleEngine.popen_uci("/usr/games/stockfish")
    agree = total = 0
    async for g in cur:
        r = review_both_sides(g.get("pgn"), str(g.get("user_color")))
        if not r or r["turning_point"]["whose"] != "theirs" or r.get("reply_cost") is None:
            continue
        cheap = r["reply_cost"] <= PUNISHED_CP
        tp = r["turning_point"]
        game = chess.pgn.read_game(io.StringIO(g["pgn"]))
        board = game.board(); moves = list(game.mainline_moves()); dear = None
        for i, mv in enumerate(moves):
            if board.fullmove_number == tp["move_number"] and board.san(mv) == tp["san"]:
                board.push(mv)
                if i + 1 < len(moves):
                    his = moves[i + 1]
                    info = eng.analyse(board, chess.engine.Limit(depth=14), multipv=1)
                    best = info[0]["pv"][0] if isinstance(info, list) else info["pv"][0]
                    me = board.turn
                    b2 = board.copy(); b2.push(his)
                    b3 = board.copy(); b3.push(best)
                    got = eng.analyse(b2, chess.engine.Limit(depth=14))["score"].pov(me).score(mate_score=CLAMP)
                    ideal = eng.analyse(b3, chess.engine.Limit(depth=14))["score"].pov(me).score(mate_score=CLAMP)
                    dear = (his == best) or (ideal - got) <= 30
                break
            board.push(mv)
        if dear is None:
            continue
        total += 1
        agree += 1 if dear == cheap else 0
        print(f"  {g['game_id'][:8]} reply_cost={r['reply_cost']:>4} cheap={'Y' if cheap else 'N'} "
              f"depth14={'Y' if dear else 'N'} {'' if dear == cheap else '   <-- DISAGREE'}", flush=True)
    eng.quit()
    print(f"\nagreement: {agree}/{total} = {round(100*agree/max(total,1))}%")
asyncio.run(main())
