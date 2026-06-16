"""Full-corpus validation (2026-06-16). Run the distilled caption system DETERMINISTICALLY
(classify -> template -> render -> independent verifier) over EVERY flagged user move in EVERY
analyzed game we have (~7800 games / ~38k moves). No Claude, no prod. Measures, at real scale:
  - COVERAGE: % of flagged moves that get a caption (vs abstain)
  - TRUTH:    % of those captions that verify TRUE on the board (the shippable bar)
  - per-situation breakdown.

This is the readiness test the 425-gold sample could not give. Env: MONGO_URL, DB_NAME.
Reuses classify / SITUATIONS / render / verify from distill_baseline_sweep.
"""
import os, sys, json, time
sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/scripts")
from collections import Counter, defaultdict
from pymongo import MongoClient
import distill_baseline_sweep as S

db = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000, socketTimeoutMS=40000)[os.environ["DB_NAME"]]

# distilled templates (fall back to seed template per situation)
try:
    TPL = json.load(open("/app/backend/data/distilled_templates.json")).get("templates", {})
except Exception:
    TPL = {}
SEED = {k: v[1] for k, v in S.SITUATIONS.items()}


def caption_for(g, ev, uc):
    lab = S.classify(ev, uc)
    if lab not in S.SITUATIONS:
        return lab, None, None  # abstain (positional/defer)
    builder = S.SITUATIONS[lab][0]
    f = builder(g, ev)
    errs = S.verify(g, ev, f, uc)
    tmpl = TPL.get(lab) or SEED.get(lab, "")
    cand = S.render(tmpl, f)
    if not cand.strip():
        return lab, None, None  # nothing rendered -> abstain
    return lab, cand, (not errs)


def main():
    t0 = time.time()
    gids = [d["game_id"] for d in db.game_analyses.find({"stockfish_analysis.move_evaluations": {"$exists": True}}, {"_id": 0, "game_id": 1})]
    print(f"corpus: {len(gids)} analyzed games", flush=True)
    ucache = {g["game_id"]: (g.get("user_color") or "white").lower() for g in db.games.find({}, {"_id": 0, "game_id": 1, "user_color": 1})}
    total_flagged = 0
    captioned = 0
    verified = 0
    by_sit = defaultdict(lambda: {"cap": 0, "ver": 0})
    abstain = 0
    processed = 0
    CH = 400
    for i in range(0, len(gids), CH):
        chunk = gids[i:i + CH]
        for attempt in range(4):
            try:
                docs = list(db.game_analyses.find({"game_id": {"$in": chunk}}, {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1}))
                break
            except Exception as e:
                print(f"  [retry chunk {i} #{attempt}] {str(e)[:50]}", flush=True); time.sleep(3); docs = []
        for an in docs:
            gid = an["game_id"]; uc = ucache.get(gid, "white")
            for m in (an.get("stockfish_analysis", {}) or {}).get("move_evaluations") or []:
                if (m.get("cp_loss") or 0) < 100 or not m.get("fen_before"):
                    continue
                total_flagged += 1
                g = {"fen_before": m["fen_before"], "move_san": m.get("move"), "best_move_san": m.get("best_move"), "move_number": m.get("move_number")}
                try:
                    lab, cand, ok = caption_for(g, m, uc)
                except Exception:
                    abstain += 1; continue
                if cand is None:
                    abstain += 1
                else:
                    captioned += 1; by_sit[lab]["cap"] += 1
                    if ok:
                        verified += 1; by_sit[lab]["ver"] += 1
            processed += 1
        if processed and processed % 1600 == 0:
            print(f"  {processed}/{len(gids)} games | {total_flagged} flagged | cap {captioned} | ver {verified} ({time.time()-t0:.0f}s)", flush=True)
    print("\n================= FULL-CORPUS VALIDATION =================", flush=True)
    print(f"analyzed games: {len(gids)} | flagged user moves (cp>=100): {total_flagged}", flush=True)
    cov = 100 * captioned // max(total_flagged, 1)
    tru = 100 * verified // max(captioned, 1)
    print(f"COVERAGE: {captioned}/{total_flagged} captioned = {cov}%  (abstained {abstain} = {100*abstain//max(total_flagged,1)}%)", flush=True)
    print(f"TRUTH:    {verified}/{captioned} of captions verify TRUE = {tru}%   <-- the shippable bar", flush=True)
    print("\nper-situation (captioned / verified-true):", flush=True)
    for sit, c in sorted(by_sit.items(), key=lambda kv: -kv[1]["cap"]):
        print(f"  {sit:22} cap {c['cap']:>6}  ver {c['ver']:>6}  ({100*c['ver']//max(c['cap'],1)}% true)", flush=True)


main()
