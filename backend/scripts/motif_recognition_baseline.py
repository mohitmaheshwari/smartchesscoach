"""motif_recognition_baseline.py — population baseline for the NEW metric:
per-opportunity OFFENSE recognition rate (was the motif the engine's best move ->
did the player actually play it?), per motif, across all users. Lock-via-data for
the recognition-rate redesign. Read-only.
"""
import os, sys, time
sys.path.insert(0, "/app/backend")
from pymongo import MongoClient
from services.caption_facts import extract_facts
from services.motif_profile_service import _classify_aligned, MOTIFS

SOUND_CP = 40
SAMPLE = int(os.environ.get("SAMPLE", "120"))   # games per user
MIN_GAMES = int(os.environ.get("MIN_GAMES", "20"))
MIN_OPPS = int(os.environ.get("MIN_OPPS", "8"))  # need >= this many opportunities to trust a rate
ME = "user_8b599930d7ef"

url = os.environ["MONGO_URL"]
db = MongoClient(url, serverSelectionTimeoutMS=20000)[os.environ.get("DB_NAME", "chess_coach")]

def motifs_of(fen, move, pv, mover_user):
    """Which motifs does `move` create here (verified detectors)."""
    out = set()
    if not (fen and move):
        return out
    try:
        f = extract_facts(fen_before=fen, played_san=move, best_move_san=move,
                          cp_loss=0, pv_after_played=pv or [], mover_is_user=mover_user)
        if f.get("multi_target_attack_evidence"):
            out.add("fork")
        out |= _classify_aligned(f.get("aligned_pieces_evidence"))
    except Exception:
        pass
    return out

def user_rates(uid):
    avail = {m: 0 for m in MOTIFS}
    found = {m: 0 for m in MOTIFS}
    games = 0
    for g in db.games.find({"user_id": uid, "is_analyzed": True}, {"_id": 0, "game_id": 1}):
        if games >= SAMPLE:
            break
        a = db.game_analyses.find_one({"game_id": g["game_id"]}, {"_id": 0, "stockfish_analysis": 1})
        mevals = (a or {}).get("stockfish_analysis", {}).get("move_evaluations") or []
        if not mevals:
            continue
        games += 1
        for ev in mevals:
            if ev.get("is_opponent_move"):
                continue
            fen = ev.get("fen_before"); best = ev.get("best_move"); played = ev.get("move")
            cp = abs(int(ev.get("cp_loss") or 0))
            bm = motifs_of(fen, best, ev.get("pv_after_best") or [], True)
            if not bm:
                continue
            pm = motifs_of(fen, played, ev.get("pv_after_played") or [], True) if cp <= SOUND_CP else set()
            for m in bm:
                avail[m] += 1
                if m in pm:
                    found[m] += 1
    return games, avail, found

# collect users with enough games
uids = []
for u in db.player_profiles.find({}, {"_id": 0, "user_id": 1}):
    uid = u.get("user_id")
    if uid and db.games.count_documents({"user_id": uid, "is_analyzed": True}) >= MIN_GAMES:
        uids.append(uid)

print(f"users>= {MIN_GAMES} games: {len(uids)} | sample {SAMPLE} games/user", flush=True)
rows = {m: [] for m in MOTIFS}  # (rate, avail, uid)
me_row = {}
t0 = time.time()
for i, uid in enumerate(uids):
    games, avail, found = user_rates(uid)
    for m in MOTIFS:
        if avail[m] >= MIN_OPPS:
            rate = found[m] / avail[m]
            rows[m].append((rate, avail[m], uid))
            if uid == ME:
                me_row[m] = (rate, found[m], avail[m])
    if (i + 1) % 10 == 0:
        print(f"  ...{i+1}/{len(uids)} ({time.time()-t0:.0f}s)", flush=True)

def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    k = max(0, min(len(sorted_vals) - 1, int(round((p/100) * (len(sorted_vals)-1)))))
    return sorted_vals[k]

print(f"\n=== RECOGNITION-RATE POPULATION BASELINE ({time.time()-t0:.0f}s) ===")
for m in MOTIFS:
    vals = sorted(r[0] for r in rows[m])
    n = len(vals)
    print(f"\n{m.upper()}  (users with >= {MIN_OPPS} opportunities: {n})")
    if n:
        print("  median %.0f%% | p25 %.0f%% | p75 %.0f%% | min %.0f%% | max %.0f%%" % (
            100*pct(vals,50), 100*pct(vals,25), 100*pct(vals,75), 100*vals[0], 100*vals[-1]))
        avg_opps = sum(r[1] for r in rows[m]) / n
        print("  avg opportunities/user in sample: %.0f" % avg_opps)
    if m in me_row:
        rate, f_, a_ = me_row[m]
        below = sum(1 for v in vals if v < rate)
        print("  >>> YOU: %.0f%% (%d/%d) -> better than %.0f%% of users" % (100*rate, f_, a_, 100*below/max(1,n)))
    else:
        print("  >>> YOU: not enough %s opportunities in sample to rate" % m)
