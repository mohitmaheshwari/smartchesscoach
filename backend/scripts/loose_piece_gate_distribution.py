"""Choose the loose-piece gate from the distribution, not from taste.

Every loose-piece card the current code renders, cross-tabbed by
  (a) how much the move actually cost   -- cp_loss
  (b) whether the game was already decided after it -- |eval_after|
with eval units normalised (3.9% of analyses store pawns, not centipawns).
"""
import asyncio
import importlib.util
import os
import sys
from collections import Counter

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, "/app/backend")
from services.rating_resolver import get_coaching_rating, move_classification_thresholds


def _load(alias, path):
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


pre = _load("cf_pre", "/tmp/caption_facts_pre.py").build_legal_material_loss_cause
FLOOR = 150
GAMES = 500


def norm_eval(doc_is_pawns, v):
    if not isinstance(v, (int, float)):
        return None
    return float(v) * 100.0 if doc_is_pawns else float(v)


def cp_bucket(cp):
    for hi in (30, 50, 75, 100, 150, 300):
        if cp < hi:
            return f"<{hi}"
    return ">=300"


def state_bucket(ev):
    if ev is None:
        return "unknown"
    a = abs(ev)
    if a >= 1500:
        return "over (>=1500)"
    if a >= 600:
        return "decided (600-1499)"
    if a >= 200:
        return "one side better"
    return "close"


async def main():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ.get("DB_NAME", "chess_coach")]
    ratings = {}
    cards = []

    cur = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations": {"$exists": True}},
        {"_id": 0, "game_id": 1, "user_id": 1,
         "stockfish_analysis.move_evaluations": 1},
    ).limit(GAMES)

    async for doc in cur:
        moves = doc.get("stockfish_analysis", {}).get("move_evaluations") or []
        vals = [float(m[k]) for m in moves for k in ("eval_before", "eval_after")
                if isinstance(m.get(k), (int, float))]
        is_pawns = bool(vals) and any(abs(v - round(v)) > 1e-9 for v in vals)

        uid = doc.get("user_id")
        if uid not in ratings:
            try:
                ratings[uid] = int(await get_coaching_rating(db, uid))
            except Exception:
                ratings[uid] = 1200
        band_floor = abs(move_classification_thresholds(ratings[uid])["inaccuracy"])

        for ev in moves:
            if ev.get("is_opponent_move"):
                continue
            fb, pl, bm = ev.get("fen_before"), ev.get("move"), ev.get("best_move")
            if not fb or not pl or not bm or pl == bm:
                continue
            try:
                cause = pre(fen_before=fb, played_san=pl, best_move_san=bm,
                            minimum_gain_cp=FLOOR)
            except Exception:
                continue
            if cause is None:
                continue
            cards.append({
                "cp": int(ev.get("cp_loss") or 0),
                "eval_after": norm_eval(is_pawns, ev.get("eval_after")),
                "mate": ev.get("mate_info") is not None,
                "band_floor": band_floor,
                "rating": ratings[uid],
            })

    n = len(cards)
    print(f"loose-piece cards rendered over {GAMES} games: {n}\n")

    print("=== cross-tab: cost of the move x how decided the game already was ===")
    states = ["close", "one side better", "decided (600-1499)", "over (>=1500)", "unknown"]
    cps = ["<30", "<50", "<75", "<100", "<150", "<300", ">=300"]
    grid = Counter()
    for c_ in cards:
        grid[(cp_bucket(c_["cp"]), state_bucket(c_["eval_after"]))] += 1
    print(f"{'cp_loss':>9} " + "".join(f"{s:>20}" for s in states) + f"{'row':>7}")
    for cb in cps:
        row = [grid[(cb, s)] for s in states]
        print(f"{cb:>9} " + "".join(f"{v:>20}" for v in row) + f"{sum(row):>7}")
    col = [sum(grid[(cb, s)] for cb in cps) for s in states]
    print(f"{'total':>9} " + "".join(f"{v:>20}" for v in col) + f"{n:>7}")

    print("\n=== candidate gates: cards kept / removed ===")
    def report(name, keep):
        k = sum(1 for c_ in cards if keep(c_))
        print(f"  {name:52} keep {k:4} ({k/max(n,1)*100:5.1f}%)  "
              f"remove {n-k:4}")

    report("today (no gate)", lambda c_: True)
    report("A rating-band inaccuracy floor", lambda c_: c_["cp"] >= c_["band_floor"])
    for f in (30, 50, 75, 100):
        report(f"B flat {f}cp floor", lambda c_, f=f: c_["cp"] >= f)
    for f in (30, 50, 75):
        for d in (600, 1500):
            report(f"C flat {f}cp floor + skip once |eval| >= {d}",
                   lambda c_, f=f, d=d: c_["cp"] >= f and (
                       c_["eval_after"] is None or abs(c_["eval_after"]) < d))
    report("D flat 50cp floor + skip mate-scored positions",
           lambda c_: c_["cp"] >= 50 and not c_["mate"])


asyncio.run(main())
