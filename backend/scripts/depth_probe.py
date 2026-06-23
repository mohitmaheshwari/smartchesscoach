"""depth_probe.py — is shallow-depth Stockfish HARMFUL for our captions, or just
picking a different equally-fine move? For each real position, take depth-D's best
move and measure how much worse it truly is (its cp_loss judged at depth-18). A
near-tie (small loss) is harmless; a big loss means depth-D picked a genuinely
worse move and a "X was better" caption would mislead. docs/pwc_client_eval_scope.md #2."""
import sys; sys.path.insert(0, "/app/backend")
import chess, asyncio, os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO = os.environ.get("MONGO_URL", "mongodb://admin_user_mii_s_c:Mii123$44$@72.60.204.176:27017/?authSource=admin")
N = 150
TRUTH = 18


async def main():
    db = AsyncIOMotorClient(MONGO, serverSelectionTimeoutMS=12000)["chess_coach"]
    fens = []
    cur = db.game_analyses.find({}, {"_id": 0, "stockfish_analysis.move_evaluations.fen_before": 1}).limit(60)
    async for a in cur:
        for m in (a.get("stockfish_analysis") or {}).get("move_evaluations") or []:
            f = m.get("fen_before")
            if f: fens.append(f)
        if len(fens) >= N: break
    fens = fens[:N]
    print(f"sampled {len(fens)} positions; truth=depth{TRUTH}", flush=True)
    from stockfish_service import get_position_evaluation

    def best_san(fen, d):
        r = get_position_evaluation(fen, depth=d)
        return (r.get("best_move") or {}).get("san"), (r.get("evaluation") or {}).get("centipawns")

    for D in (12, 15):
        agree = harmful = tot = 0; harms = []
        for f in fens:
            try:
                bD, _ = best_san(f, D)
                b18, e18 = best_san(f, TRUTH)
                if not bD or not b18 or e18 is None:
                    continue
                tot += 1
                if bD == b18:
                    agree += 1; continue
                # depth-D chose a different move — how much worse is it really (at truth)?
                board = chess.Board(f); mv = board.parse_san(bD); board.push(mv)
                r_after = get_position_evaluation(board.fen(), depth=TRUTH)
                e_after = (r_after.get("evaluation") or {}).get("centipawns")
                if e_after is None: continue
                loss = max(0, e18 - (-e_after))  # cp the depth-D move loses vs truth-best
                if loss > 100:
                    harmful += 1
                    if len(harms) < 10: harms.append((f.split()[0][:20], bD, b18, loss))
            except Exception:
                pass
        ap = round(100*agree/tot) if tot else 0
        hp = round(100*harmful/tot) if tot else 0
        print(f"\ndepth{D}: agree={agree}/{tot} ({ap}%)  HARMFUL(>100cp worse)={harmful}/{tot} ({hp}%)", flush=True)
        for f, a, b, l in harms:
            print(f"    {f}  d{D}={a}  d18={b}  loss={l}cp", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
    sys.stdout.flush()
    import os as _os; _os._exit(0)
