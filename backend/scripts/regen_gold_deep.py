"""Regenerate gold captions on the DEEP PVs (2026-06-16), so gold + detector share engine depth.

For each existing gold position, feed Claude the deep best-line + deep post-played-line + mate length
(from db.gold_deep_pv), engine-verify (narrator_claim_verifier) + self-correct, store under
gold_<user>_deep. Preserves the originals. Fixes the depth-mismatch found when deepening the detector
alone (one_move_blunder 80->46 was a gold-built-on-shallow-PV artifact, not a real regression).

Env: MONGO_URL (direct ok), DB_NAME, LLM_API_BASE/_KEY (or LLM_EXPOSER_URL/_KEY).
"""
import os, sys, json, time, re, threading
sys.path.insert(0, "/app/backend")
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from pymongo import MongoClient
from services.narrator_claim_verifier import verify_caption
import services.narrator_fallback as nf

db = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000, socketTimeoutMS=30000)[os.environ["DB_NAME"]]
RATING = 1200

PROMPT = """You are a chess coach writing a SHORT caption (max 2 sentences, ~30-40 words) for a {rating} student who plays {scol}. Coach who TEACHES, not rates. Every you/your = the student.
This move ({move}) was played by the student. Name the better move + a one-line why (or, for a missed forced mate, name the mate). Land one short principle, stated directly.
RULES: concrete squares; no jargon/markdown/CAPS; NEVER state a capture/tactic/mate/follow-up unless true per the engine lines; never say "free" unless truly undefended.
FEN: {fen}  Side: {side}
Played: {move} (engine ~{cp}cp lost)  Best: {best}
Deep line after best: {pvb}{matenote}
Deep line after played: {pvp}
Write ONLY the caption."""
CORRECT = """Your caption: "{cap}"
FACTUAL ERRORS vs the board (ground truth):
{errs}
Rewrite fixing ONLY these, max 2 sentences, same tone, student's seat, no new untrue claim. Write ONLY the caption."""

BASE = os.environ.get("LLM_API_BASE") or os.environ.get("LLM_EXPOSER_URL")
KEY = os.environ.get("LLM_API_KEY") or os.environ.get("LLM_EXPOSER_KEY")
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def side(f):
    return "White" if f.split(" ")[1] == "w" else "Black"


def call_llm(p, retries=2):
    for _ in range(retries):
        try:
            r = requests.post(BASE.rstrip("/") + "/ask", headers=H, json={"question": p, "provider": "claude", "timeout_seconds": 160}, timeout=20)
            r.raise_for_status(); tid = r.json()["task_id"]; end = time.time() + 190
            while time.time() < end:
                time.sleep(4)
                t = requests.get(BASE.rstrip("/") + f"/tasks/{tid}", headers=H, timeout=20).json()
                if t.get("status") in ("completed", "done", "finished", "succeeded"): return (t.get("answer") or "").strip()
                if t.get("status") in ("error", "timeout", "failed"): break
        except Exception:
            time.sleep(2)
    return ""


def gold_for(facts, scol):
    matenote = ""
    if facts.get("deep_mate_n"):
        matenote = f"  (engine: FORCED MATE in {facts['deep_mate_n']} for the student)"
    p = PROMPT.format(rating=RATING, scol=scol, move=facts["move_san"], fen=facts["fen_before"], side=side(facts["fen_before"]),
                      cp=facts["cp_loss"], best=facts.get("best_move_san") or "(n/a)",
                      pvb=" ".join((facts.get("pv_after_best") or [])[:6]) or "(none)", matenote=matenote,
                      pvp=" ".join((facts.get("pv_after_played") or [])[:6]) or "(none)")
    cap = call_llm(p)
    if not cap:
        return None, "narrator_unavailable"
    v = verify_caption(cap, facts)
    if not v:
        return cap, "verified"
    cap2 = call_llm(CORRECT.format(cap=cap, errs="\n".join("- " + x["detail"] for x in v)))
    if cap2 and not verify_caption(cap2, facts):
        return cap2, "verified_after_correction"
    return None, "HELD"


def main():
    deep = {(d["game_id"], d.get("move_number")): d for d in db.gold_deep_pv.find({}, {"_id": 0})}
    golds = list(db.gold_captions.find({"created_by": {"$in": ["gold_shobhit", "gold_mohit", "gold_parth"]}, "gold_caption": {"$ne": None}}, {"_id": 0}))
    print(f"regenerating {len(golds)} gold on deep PVs; gateway={bool(BASE and KEY)}", flush=True)
    # resume: skip already-regenerated under _deep
    done = set()
    for d in db.gold_captions.find({"created_by": {"$in": ["gold_shobhit_deep", "gold_mohit_deep", "gold_parth_deep"]}}, {"_id": 0, "game_id": 1, "move_number": 1}):
        done.add((d.get("game_id"), d.get("move_number")))
    pending = [g for g in golds if (g["game_id"], g.get("move_number")) not in done]
    print(f"pending {len(pending)} (skip {len(golds)-len(pending)} done)", flush=True)

    def work(g):
        gm = db.games.find_one({"game_id": g["game_id"]}, {"_id": 0, "user_color": 1}); uc = (gm or {}).get("user_color", "white").lower()
        an = db.game_analyses.find_one({"game_id": g["game_id"]}, {"_id": 0, "stockfish_analysis.move_evaluations": 1}); ev = {}
        for m in (an or {}).get("stockfish_analysis", {}).get("move_evaluations") or []:
            if m.get("move_number") == g.get("move_number") and m.get("move") == g.get("move_san"): ev = m; break
        dp = deep.get((g["game_id"], g.get("move_number")), {})
        facts = {"fen_before": g["fen_before"], "move_san": g["move_san"], "is_user_move": True,
                 "cp_loss": g.get("cp_loss"), "best_move_san": g.get("best_move_san") or ev.get("best_move"),
                 "pv_after_best": dp.get("deep_pv_best") or ev.get("pv_after_best") or [],
                 "pv_after_played": dp.get("deep_pv_played") or ev.get("pv_after_played") or [],
                 "deep_mate_n": dp.get("deep_mate_n")}
        cap, status = gold_for(facts, uc.capitalize())
        newtag = g["created_by"] + "_deep"
        if cap:
            db.gold_captions.update_one({"created_by": newtag, "game_id": g["game_id"], "move_number": g.get("move_number")},
                                        {"$set": {**{k: g.get(k) for k in ("game_id", "cognitive_gap", "move_number", "fen_before", "move_san", "cp_loss", "best_move_san")},
                                                  "gold_caption": cap, "verify_status": status, "created_by": newtag}}, upsert=True)
        return status

    stats = Counter(); lock = threading.Lock(); n = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        for fut in as_completed([ex.submit(work, g) for g in pending]):
            try: st = fut.result()
            except Exception as e: st = "err:" + str(e)[:30]
            with lock:
                stats[st] += 1; n += 1
                if n % 25 == 0: print(f"  {n}/{len(pending)} {dict(stats)}", flush=True)
    print(f"\nDONE regen. stats: {dict(stats)}", flush=True)
    for t in ("gold_shobhit_deep", "gold_mohit_deep", "gold_parth_deep"):
        print(f"  {t}: {db.gold_captions.count_documents({'created_by': t})}", flush=True)


main()
