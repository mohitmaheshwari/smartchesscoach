"""Verify each claim in the Shobhit email against actual data."""
import os, asyncio
from collections import Counter, defaultdict
from motor.motor_asyncio import AsyncIOMotorClient

UID = "user_e9acb79dfc26"  # Shobhit Maheshwari

async def main():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ.get("DB_NAME", "chess_coach")]

    print("="*70)
    print("CLAIM 1: '265 games, 45% accuracy'")
    print("="*70)
    total = await db.games.count_documents({"user_id": UID})
    analyzed = await db.games.count_documents({"user_id": UID, "is_analyzed": True})
    profile = await db.player_profiles.find_one({"user_id": UID}) or {}
    print(f"  Total games: {total}")
    print(f"  Analyzed:   {analyzed}")
    print(f"  Profile avg_accuracy: {profile.get('average_accuracy')}%")

    print()
    print("="*70)
    print("CLAIM 2: 'Endgame is one of the best in our system' (STRONG = top 20%)")
    print("="*70)
    # Rank Shobhit's per-game endgame mistake rate against all >20-game users
    pipeline = [
        {"$match": {"is_analyzed": True}},
        {"$group": {"_id": "$user_id", "n": {"$sum": 1}}},
        {"$match": {"n": {"$gte": 20}}},
    ]
    uids = [r["_id"] async for r in db.games.aggregate(pipeline)]
    rates = []
    for u in uids:
        p = await db.player_profiles.find_one({"user_id": u}, {"top_weaknesses": 1, "games_analyzed_count": 1}) or {}
        ws = {w["subcategory"]: w.get("occurrence_count", 0) for w in (p.get("top_weaknesses") or [])}
        g = p.get("games_analyzed_count", 0) or 1
        rate = ws.get("king_activity_neglect", 0) / g
        rates.append((rate, u))
    rates.sort()  # lower is better
    shobhit_rank = next((i for i, (_, u) in enumerate(rates) if u == UID), -1)
    print(f"  Endgame ranking (lower per-game rate = better): #{shobhit_rank+1} of {len(rates)}")
    print(f"  Shobhit endgame rate: {rates[shobhit_rank][0]:.3f} king_activity_neglect/game")
    print(f"  Top 9 (top 20%):")
    for i, (r, u) in enumerate(rates[:9]):
        nm = (await db.users.find_one({"user_id": u}, {"name": 1}) or {}).get("name", u)
        marker = " ← Shobhit" if u == UID else ""
        print(f"    #{i+1}: {nm[:30]:<30} rate={r:.3f}{marker}")

    print()
    print("="*70)
    print("CLAIM 3: 'When game reaches move 40+, he outplays people'")
    print("="*70)
    # Look at his outcomes in games that reach move 40+
    long_games_w = long_games_l = long_games_d = 0
    short_games_w = short_games_l = short_games_d = 0
    long_total = 0
    async for g in db.games.find({"user_id": UID, "is_analyzed": True}, {"game_id": 1, "result": 1, "user_color": 1, "pgn": 1}):
        pgn = g.get("pgn", "")
        # Crude: count moves by counting move numbers ("40." appears)
        is_long = " 40." in pgn or " 45." in pgn or " 50." in pgn
        res = (g.get("result") or "").strip()
        col = g.get("user_color")
        if res == "1-0":
            outcome = "win" if col == "white" else "loss"
        elif res == "0-1":
            outcome = "win" if col == "black" else "loss"
        elif res in ("1/2-1/2", "½-½"):
            outcome = "draw"
        else:
            outcome = "unknown"
        if is_long:
            long_total += 1
            if outcome == "win": long_games_w += 1
            elif outcome == "loss": long_games_l += 1
            elif outcome == "draw": long_games_d += 1
        else:
            if outcome == "win": short_games_w += 1
            elif outcome == "loss": short_games_l += 1
            elif outcome == "draw": short_games_d += 1
    sg_total = short_games_w + short_games_l + short_games_d
    print(f"  Games reaching move 40+: {long_total}")
    if long_total:
        print(f"    Record: {long_games_w}W / {long_games_l}L / {long_games_d}D  "
              f"({100*long_games_w/long_total:.0f}% wins)")
    print(f"  Games ending before move 40: {sg_total}")
    if sg_total:
        print(f"    Record: {short_games_w}W / {short_games_l}L / {short_games_d}D  "
              f"({100*short_games_w/sg_total:.0f}% wins)")

    print()
    print("="*70)
    print("CLAIM 4: 'Between moves 8-15, you lose pieces' (clustering of mistakes)")
    print("="*70)
    # Bucket Shobhit's blunder cp_loss by move number
    move_bucket_blunders = Counter()
    move_bucket_total = Counter()
    async for a in db.game_analyses.find({"user_id": UID}, {"stockfish_analysis.move_evaluations": 1}):
        moves = (a.get("stockfish_analysis") or {}).get("move_evaluations", []) or []
        for mv in moves:
            if mv.get("is_opponent_move"): continue
            mn = mv.get("move_number", 0)
            # Bucket: 1-7, 8-15, 16-25, 26-40, 41+
            if mn <= 7: bucket = "1-7 (opening)"
            elif mn <= 15: bucket = "8-15 (early MG)"
            elif mn <= 25: bucket = "16-25 (middlegame)"
            elif mn <= 40: bucket = "26-40 (late MG)"
            else: bucket = "41+ (endgame)"
            move_bucket_total[bucket] += 1
            ev = mv.get("evaluation")
            if ev in ("blunder", "mistake"):
                move_bucket_blunders[bucket] += 1
    print(f"  {'Move range':<25} {'Total moves':>12} {'Blunders+Mistakes':>20} {'Rate':>8}")
    for b in ["1-7 (opening)", "8-15 (early MG)", "16-25 (middlegame)", "26-40 (late MG)", "41+ (endgame)"]:
        t = move_bucket_total[b]
        bl = move_bucket_blunders[b]
        rate = (100*bl/t) if t else 0
        print(f"  {b:<25} {t:>12,} {bl:>20,} {rate:>7.1f}%")

asyncio.run(main())
