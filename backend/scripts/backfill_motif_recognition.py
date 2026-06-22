"""backfill_motif_recognition.py — populate player_profiles.motif_recognition for
existing analyzed games (per-opportunity OFFENSE recognition, per-game tallies keyed
by game_id with date_played). Reuses the verified single-source compute. Idempotent.

  docker exec chess-coach-backend python /app/backend/scripts/backfill_motif_recognition.py [--apply] [--user USER_ID]

Dry-run by default (prints what it would write for a few users).
"""
import os, sys, time
sys.path.insert(0, "/app/backend")
from pymongo import MongoClient
from services.motif_profile_service import compute_game_recognition, merge_recognition, MOTIFS

APPLY = "--apply" in sys.argv
ONE_USER = None
if "--user" in sys.argv:
    ONE_USER = sys.argv[sys.argv.index("--user") + 1]

url = os.environ["MONGO_URL"]
db = MongoClient(url, serverSelectionTimeoutMS=20000)[os.environ.get("DB_NAME", "chess_coach")]

q = {"user_id": ONE_USER} if ONE_USER else {}
uids = [u["user_id"] for u in db.player_profiles.find(q, {"_id": 0, "user_id": 1}) if u.get("user_id")]
print(f"users to backfill: {len(uids)} | apply={APPLY}", flush=True)

t0 = time.time()
done = 0
for uid in uids:
    rec = {"by_game": {}}
    games = 0
    for g in db.games.find({"user_id": uid, "is_analyzed": True},
                           {"_id": 0, "game_id": 1, "date_played": 1}):
        a = db.game_analyses.find_one({"game_id": g["game_id"]}, {"_id": 0, "stockfish_analysis": 1})
        mevals = (a or {}).get("stockfish_analysis", {}).get("move_evaluations") or []
        if not mevals:
            continue
        games += 1
        rec = merge_recognition(rec, g["game_id"], g.get("date_played"),
                                compute_game_recognition(mevals))
    av = {m: sum(v["av"].get(m, 0) for v in rec["by_game"].values()) for m in MOTIFS}
    fo = {m: sum(v["fo"].get(m, 0) for v in rec["by_game"].values()) for m in MOTIFS}
    if APPLY:
        db.player_profiles.update_one({"user_id": uid}, {"$set": {"motif_recognition": rec}})
    done += 1
    if ONE_USER or done <= 3 or done % 10 == 0:
        print(f"  {uid[:16]} games={games} avail={av} found={fo} ({time.time()-t0:.0f}s)", flush=True)
print(f"[{'APPLIED' if APPLY else 'DRY-RUN'}] backfilled {done} users in {time.time()-t0:.0f}s")
