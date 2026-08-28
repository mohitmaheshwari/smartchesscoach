"""backfill_motif_profile_and_anticipation.py — *** SUPERSEDED 2026-08-13 ***

DO NOT RUN. Use scripts/migrate_fork_promotion_recompute.py instead.

Kept for history only. Four defects make it unsafe against current production:

  1. LOSES PROVENANCE. It calls compute_game_motifs(mevals, user_color) without
     `game_id` (line ~53), so every drill row it writes gets game_id=None and no
     provenance stamp. get_drills() then refuses to name the game, and the Stage 8
     "this is you, 6 days ago" copy silently has nothing to show. The replacement
     passes game_id, which is what lets the service stamp provenance "exact".
  2. SKIPS DUPLICATE PROFILES. It writes with update_one({"user_id": uid}).
     player_profiles is NOT unique on user_id — 69 docs for 67 user_ids in
     production — so the second copy of a duplicated profile is never written.
     This exact bug silently lost 68 rows during the Gate 3 backfill.
  3. NEVER RECOMPUTES motif_recognition. It rebuilds motif_profile and
     motif_anticipation only, so the offense-recognition store (which drives the
     mastery ladder) is left calibrated to the old fork definition.
  4. NON-DETERMINISTIC TRUNCATION. It relies on natural find() order. Because
     merge_motifs keeps only the last 30 got_positions, WHICH positions survive
     depends on that order, so two runs can disagree.

Original docstring follows.
--------------------------------------------------------------------

populate player_profiles.motif_profile (two-sided verdict) and
.motif_anticipation (defense-side "did you see it coming") for existing
analyzed games.

Reuses the verified single-source computes. Idempotent: rebuilds each
user's totals from scratch so re-runs produce the same result. Safe to
re-run any number of times; also safe to re-run after extending MOTIFS
(the recompute picks up new motif entries from the source of truth).

  docker exec chess-coach-backend python3 /app/backend/scripts/backfill_motif_profile_and_anticipation.py [--apply] [--user USER_ID]

Dry-run by default — prints what it would write for a small sample.

Companion to `backfill_motif_recognition.py`. Together the two scripts
refresh all three player_profiles.motif_* fields the analysis worker
maintains going forward at analysis_worker.py:629.
"""
import os, sys, time
sys.path.insert(0, "/app/backend")
from pymongo import MongoClient
from services.motif_profile_service import (
    compute_game_motifs, merge_motifs,
    compute_game_anticipation, merge_anticipation,
    MOTIFS,
)

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
sample_count = 0
for uid in uids:
    mp = None  # start-from-scratch each user (idempotent)
    ant = {"by_game": {}}
    n_games = 0
    for g in db.games.find({"user_id": uid, "is_analyzed": True},
                           {"_id": 0, "game_id": 1, "date_played": 1, "user_color": 1}):
        a = db.game_analyses.find_one({"game_id": g["game_id"]}, {"_id": 0, "stockfish_analysis": 1})
        mevals = (a or {}).get("stockfish_analysis", {}).get("move_evaluations") or []
        if not mevals:
            continue
        n_games += 1
        mp = merge_motifs(mp, compute_game_motifs(mevals, (g.get("user_color") or "white").lower()))
        ant = merge_anticipation(ant, g["game_id"], g.get("date_played"),
                                 compute_game_anticipation(mevals))

    if n_games == 0:
        continue

    if sample_count < 3:
        # Compact summary — per-motif made_sound/got + faced/allowed
        mp_summary = {m: (mp[m].get("made_sound", 0), mp[m].get("got", 0)) for m in MOTIFS}
        # Aggregate anticipation across games
        faced_agg = {m: sum(v["faced"].get(m, 0) for v in ant["by_game"].values()) for m in MOTIFS}
        allowed_agg = {m: sum(v["allowed"].get(m, 0) for v in ant["by_game"].values()) for m in MOTIFS}
        print(f"  {uid[:20]} games={n_games} motif_profile ms/got={mp_summary}  ant faced/allowed=({faced_agg}, {allowed_agg})")
        sample_count += 1

    if APPLY:
        db.player_profiles.update_one(
            {"user_id": uid},
            {"$set": {"motif_profile": mp, "motif_anticipation": ant}},
        )
    done += 1

print(f"[{'APPLY' if APPLY else 'DRY-RUN'}] backfilled {done} users in {int(time.time()-t0)}s")
