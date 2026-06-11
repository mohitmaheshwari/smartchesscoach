"""Build a stratified, ENGINE-VERIFIED gold caption set — the teaching STANDARD
for improving detectors (teach-detectors-from-gold). Sampled per pattern
(cognitive_gap), each caption written by Claude, verified against the board+engine
(narrator_claim_verifier), self-corrected once, HELD on double-fail. Only verified
golds are stored — you never teach a detector toward a hallucinated standard.

Stored to db.gold_captions + a JSONL backup, tagged by pattern.
Usage: python scripts/build_gold_set.py --per-gap 12 --apply
"""
import os, sys, json, time, argparse, urllib.request
sys.path.insert(0, "/app/backend")
import pymongo, chess
from services.narrator_claim_verifier import verify_caption
URL=os.environ["LLM_EXPOSER_URL"].rstrip("/"); KEY=os.environ["LLM_EXPOSER_KEY"]; RATING=1200
GAPS=["piece_safety","king_safety","missed_tactic","tactical_oversight","opening_knowledge","piece_activity"]

PROMPT="""You are a chess coach writing a SHORT caption (max 2 sentences, ~30-40 words) for a {rating} student who plays {scol}. Coach who TEACHES, not rates. Every you/your = the student.
This move ({move}) was played by {mover}. STUDENT move: name opening/fundamental, or (mistake) the better move + a one-line why. OPPONENT move: what it means for you + what you do.
Land one short principle, stated directly. RULES: concrete squares; no jargon/markdown/CAPS; NEVER state a capture/tactic/follow-up unless true per the engine lines; never say "free" unless truly undefended.
FEN: {fen}  Side: {side}
Played: {move} (engine ~{cp}cp lost)  Best: {best}  Line-after-best: {pvb}  Line-after-played: {pvp}
Write ONLY the caption."""
CORRECT="""Your caption: "{cap}"
FACTUAL ERRORS vs the board (ground truth):
{errs}
Rewrite fixing ONLY these, max 2 sentences, same tone, student's seat, no new untrue claim. Write ONLY the caption."""

def call_llm(p,retries=2):
    h={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"}
    for _ in range(retries):
        try:
            d=json.dumps({"provider":"claude","question":p,"timeout_seconds":180}).encode()
            r=urllib.request.Request(URL+"/ask",data=d,headers=h,method="POST")
            with urllib.request.urlopen(r,timeout=40) as x: tid=json.loads(x.read().decode()).get("task_id")
            for _ in range(60):
                time.sleep(4)
                try:
                    pr=urllib.request.Request(URL+f"/tasks/{tid}",headers=h)
                    with urllib.request.urlopen(pr,timeout=40) as x2: rec=json.loads(x2.read().decode())
                except Exception: continue
                if rec.get("status") in ("completed","done","finished","succeeded"): return (rec.get("answer") or "").strip()
        except Exception: time.sleep(2)
    return ""
def side(f): return "White" if f.split(" ")[1]=="w" else "Black"

def gold_for(facts, scol):
    mover="the student" if facts["is_user_move"] else "the opponent"
    p=PROMPT.format(rating=RATING,scol=scol,move=facts["move_san"],mover=mover,fen=facts["fen_before"],side=side(facts["fen_before"]),
        cp=facts["cp_loss"],best=facts.get("best_move_san") or "(n/a)",pvb=" ".join((facts.get("pv_after_best") or [])[:5]) or "(none)",
        pvp=" ".join((facts.get("pv_after_played") or [])[:5]) or "(none)")
    cap=call_llm(p)
    if not cap: return (None,"narrator_unavailable")
    v=verify_caption(cap,facts)
    if not v: return (cap,"verified")
    cap2=call_llm(CORRECT.format(cap=cap,errs="\n".join("- "+x["detail"] for x in v)))
    if cap2 and not verify_caption(cap2,facts): return (cap2,"verified_after_correction")
    return (None,"HELD")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--per-gap",type=int,default=12); ap.add_argument("--apply",action="store_true"); a=ap.parse_args()
    db=pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME","chess_coach")]
    ucol={g["game_id"]:g.get("user_color","white") for g in db.games.find({"is_analyzed":True},{"game_id":1,"user_color":1})}
    buckets={g:[] for g in GAPS}
    # stratified sample via aggregation: pull ONLY flagged user moves with a target
    # gap (small payload) instead of scanning full move arrays over the tunnel.
    pipeline=[
        {"$match":{"stockfish_analysis.move_evaluations":{"$exists":True}}},
        {"$project":{"game_id":1,"me":"$stockfish_analysis.move_evaluations"}},
        {"$unwind":"$me"},
        {"$match":{"me.is_opponent_move":{"$ne":True},"me.cp_loss":{"$gte":80},"me.cognitive_gap":{"$in":GAPS}}},
        {"$limit":4000},
    ]
    for r in db.game_analyses.aggregate(pipeline, allowDiskUse=True):
        gid=r.get("game_id"); m=r["me"]; g=m.get("cognitive_gap")
        if gid not in ucol or g not in buckets or len(buckets[g])>=a.per_gap: continue
        if any(b["game_id"]==gid for b in buckets[g]): continue  # one per game per gap for diversity
        buckets[g].append({"game_id":gid,"cognitive_gap":g,"move_number":m.get("move_number"),
            "fen_before":m["fen_before"],"move_san":m["move"],"is_user_move":True,"cp_loss":m.get("cp_loss"),
            "best_move_san":m.get("best_move"),"pv_after_best":m.get("pv_after_best") or [],"pv_after_played":m.get("pv_after_played") or []})
        if all(len(b)>=a.per_gap for b in buckets.values()): break
    targets=[x for b in buckets.values() for x in b]
    print("sampled per gap:", {g:len(b) for g,b in buckets.items()}, "| total", len(targets), "| mode", "APPLY" if a.apply else "DRY")
    out=[]; stats={"verified":0,"verified_after_correction":0,"HELD":0,"narrator_unavailable":0}
    for t in targets:
        scol=(ucol.get(t["game_id"]) or "black").capitalize()
        cap,status=gold_for(t,scol); stats[status]=stats.get(status,0)+1
        rec={**{k:t[k] for k in ("game_id","cognitive_gap","move_number","fen_before","move_san","cp_loss","best_move_san")},"gold_caption":cap,"verify_status":status}
        out.append(rec)
        print(f"  [{t['cognitive_gap']}] {t['move_san']} cpl={t['cp_loss']} ({status}): {(cap or '(HELD)')[:80]}")
    print("\nstats:",stats)
    json.dump(out,open("/app/backend/data/gold_set_v1.json","w"),indent=1)
    if a.apply:
        verified=[r for r in out if r["gold_caption"]]
        if verified:
            db.gold_captions.delete_many({"created_by":"gold_set_v1"})
            db.gold_captions.insert_many([{**r,"created_by":"gold_set_v1"} for r in verified])
        print(f"stored {len(verified)} verified golds to db.gold_captions")

main()
