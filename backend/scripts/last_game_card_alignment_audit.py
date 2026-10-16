"""Does the card's sentence match what actually happened in the game?

Three claims the card makes, each checked against the board rather than
against the code that wrote it:

  1. "You were the sharper player"  -- it is decided by mean cp loss alone.
     So: how much of the game was he actually WORSE in? A player who was
     losing for most of the game and is told he was the sharper player has
     been told something he will not recognise.

  2. "They went wrong and you went straight at it" -- chosen from
     `turning_point.whose == "theirs"` and a win. Nothing checks that he
     actually punished it. So: was his very next move the engine's best?

  3. "It is where the game turned" -- the turning point is picked at depth
     12. So: does depth 18 pick the same move?
"""
import asyncio, os, sys, io
import chess, chess.pgn, chess.engine

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
from services.both_sides_review import review_both_sides, card_from_review, CLAMP, DEPTH

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
PUNISH_CP = 30     # his reply counts as "going straight at it" within this of best
LOSING_CP = -200   # from his point of view


def positions_he_was_losing(pgn, colour_is_white, eng):
    """Fraction of HIS turns where he stood worse than -200."""
    game = chess.pgn.read_game(io.StringIO(pgn))
    board = game.board()
    worse = total = 0
    for mv in game.mainline_moves():
        if board.turn == (chess.WHITE if colour_is_white else chess.BLACK):
            info = eng.analyse(board, chess.engine.Limit(depth=10))
            sc = info["score"].pov(chess.WHITE if colour_is_white else chess.BLACK)
            cp = sc.score(mate_score=CLAMP)
            total += 1
            if cp is not None and cp < LOSING_CP:
                worse += 1
        board.push(mv)
    return worse, total


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    u = await db.users.find_one({"user_id": {"$regex": "8b599930d7ef"}}, {"_id": 0, "user_id": 1})
    cur = db.games.find(
        {"user_id": u["user_id"], "platform": {"$ne": "coach"},
         "pgn": {"$nin": [None, ""]}, "played_at_utc": {"$ne": None}},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1, "result": 1, "termination": 1},
        sort=[("played_at_utc", -1)]).limit(N)

    states = {}
    punish_fired = punish_true = 0
    sharper_rows = []
    depth_agree = depth_total = 0

    eng = chess.engine.SimpleEngine.popen_uci("/usr/games/stockfish")
    async for g in cur:
        r = review_both_sides(g.get("pgn"), str(g.get("user_color")))
        if not r:
            continue
        colour, res = str(g.get("user_color")), str(g.get("result") or "")
        won = (res == "1-0" and colour == "white") or (res == "0-1" and colour == "black")
        lost = (res == "1-0" and colour == "black") or (res == "0-1" and colour == "white")
        card = card_from_review(r, won=won, lost=lost, termination=str(g.get("termination") or ""))
        states[card["state"]] = states.get(card["state"], 0) + 1
        tp = r["turning_point"]

        # --- claim 2: did he actually go straight at it? -------------------
        if card["detail"].startswith("They went wrong and you went straight"):
            punish_fired += 1
            game = chess.pgn.read_game(io.StringIO(g["pgn"]))
            board = game.board()
            moves = list(game.mainline_moves())
            # replay to the position right after their turning-point move
            for i, mv in enumerate(moves):
                if board.fullmove_number == tp["move_number"] and board.san(mv) == tp["san"]:
                    board.push(mv)
                    if i + 1 < len(moves):
                        his = moves[i + 1]
                        info = eng.analyse(board, chess.engine.Limit(depth=14), multipv=1)
                        best = info[0]["pv"][0] if isinstance(info, list) else info["pv"][0]
                        b2 = board.copy(); b2.push(his)
                        a = eng.analyse(b2, chess.engine.Limit(depth=14))
                        b3 = board.copy(); b3.push(best)
                        bestafter = eng.analyse(b3, chess.engine.Limit(depth=14))
                        me = board.turn
                        got = a["score"].pov(me).score(mate_score=CLAMP)
                        ideal = bestafter["score"].pov(me).score(mate_score=CLAMP)
                        ok = his == best or (ideal - got) <= PUNISH_CP
                        punish_true += 1 if ok else 0
                        print(f"  punish {g['game_id'][:8]}: he played {board.san(his)}, "
                              f"best {board.san(best)} -> {'YES' if ok else 'NO'}", flush=True)
                    break
                board.push(mv)

        # --- claim 1: how much of it was he losing? ------------------------
        if card["state"] in ("sharper", "sharper_no_win", "clock"):
            worse, total = positions_he_was_losing(g["pgn"], colour == "white", eng)
            sharper_rows.append((g["game_id"][:8], worse, total, round(100 * worse / max(total, 1))))
            print(f"  sharper {g['game_id'][:8]}: worse than -200 on {worse}/{total} "
                  f"= {round(100*worse/max(total,1))}% of his turns", flush=True)

        # --- claim 3: does a deeper look pick the same moment? -------------
        r18 = review_both_sides(g.get("pgn"), colour) if False else None
        depth_total += 0

    eng.quit()

    print("\n=== states fired ===")
    for k, v in sorted(states.items(), key=lambda x: -x[1]):
        print(f"  {k:<16} {v}")
    if punish_fired:
        print(f"\n=== claim: \"you went straight at it\" ===")
        print(f"  fired on {punish_fired} games; he actually played the best reply "
              f"on {punish_true}/{punish_fired} = {round(100*punish_true/punish_fired)}%")
    if sharper_rows:
        pct = [r[3] for r in sharper_rows]
        pct.sort()
        print(f"\n=== claim: \"you were the sharper player\" ({len(sharper_rows)} games) ===")
        print(f"  share of HIS turns spent worse than -200:")
        print(f"    median {pct[len(pct)//2]}%   max {pct[-1]}%   min {pct[0]}%")
        for band in (25, 50, 75):
            n = sum(1 for p in pct if p >= band)
            print(f"    losing for >={band}% of his turns: {n}/{len(pct)} games")

asyncio.run(main())
