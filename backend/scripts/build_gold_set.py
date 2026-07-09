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

PROMPT="""You are a kind chess coach talking to a {rating} student who plays {scol}. Write a SHORT caption (max 2 short sentences).
WRITE LIKE YOU ARE TALKING TO A CHILD, OR AN OLD BEGINNER WHO DOES NOT KNOW GOOD ENGLISH:
- Use only easy, everyday words. Short sentences. Talking style, warm and calm.
- NO chess jargon at all (no "fianchetto", "prophylaxis", "zwischenzug", "outpost", "zugzwang", "initiative", "tempo"). If you mean a square, just name the square.
- Do NOT show off notation. Lead with the IDEA or PATTERN in plain words (what is happening on the board), not the move letters. The move name can appear once, small.
- TEACH the WHY. The student must really understand. Every mistake caption must say WHY it is bad in simple words, and if you give a better move you MUST say in simple words WHY that move is good — never just "X was better".
- End with ONE tiny lesson they can reuse next game, said plainly.
- Calm, undramatic. Never say "you were already losing". Structure: what happened -> why -> what is better.

This move ({move}) was played by {mover}. STUDENT move that is fine/good: name the plan or idea in simple words. STUDENT mistake: say what went wrong and the better idea + why. OPPONENT move: say in simple words what they are trying to do to you, and what you should do about it.

HARD TRUTH RULES (never break): only say something is captured / attacked / a fork / "wins a piece" / "free" if it is TRUE in the engine lines below. Never invent a threat. Do not just repeat the square the move already lands on.
A move that stays winning is NOT a blunder — say "there was an even stronger move", not "blunder".

FEN: {fen}  Side to move: {side}
Played: {move} (engine ~{cp}cp lost)  Best move: {best}  Line after best: {pvb}  Line after played: {pvp}
Write ONLY the caption, in that simple talking voice."""
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
    ap=argparse.ArgumentParser(); ap.add_argument("--per-gap",type=int,default=12); ap.add_argument("--apply",action="store_true")
    ap.add_argument("--user",default=None,help="scope gold to ONE user_id's games (e.g. Shobhit)")
    ap.add_argument("--tag",default="gold_set_v1",help="created_by tag — keeps per-user gold sets separate so a run never wipes another's gold")
    a=ap.parse_args()
    db=pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME","chess_coach")]
    _gq={"is_analyzed":True}
    if a.user: _gq["user_id"]=a.user
    ucol={g["game_id"]:g.get("user_color","white") for g in db.games.find(_gq,{"game_id":1,"user_color":1})}
    buckets={g:[] for g in GAPS}
    # stratified sample via aggregation: pull ONLY flagged user moves with a target
    # gap (small payload) instead of scanning full move arrays over the tunnel.
    pipeline=[
        {"$match":{**({"game_id":{"$in":list(ucol.keys())}} if a.user else {}),"stockfish_analysis.move_evaluations":{"$exists":True}}},
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
    out=[]; stats={"verified":0,"verified_after_correction":0,"HELD":0,"narrator_unavailable":0,"skip_done":0}
    # RESUME: skip targets already gold-stored under this tag (crash-resilient on
    # an unstable env — a vanished container can't wipe finished work).
    done=set()
    if a.apply:
        for d in db.gold_captions.find({"created_by":a.tag},{"game_id":1,"move_number":1,"_id":0}):
            done.add((d.get("game_id"),d.get("move_number")))
        print(f"resume: {len(done)} already stored under tag {a.tag}; will skip those")
    pending=[t for t in targets if not (a.apply and (t["game_id"],t.get("move_number")) in done)]
    stats["skip_done"]=len(targets)-len(pending)
    # PARALLEL: the exposer now allows concurrency; fan out up to WORKERS at once.
    # gold_for = exposer call (urllib, per-call) + verify_caption (own chess.Board)
    # + a pymongo upsert (MongoClient is thread-safe). Each gold persists immediately.
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    WORKERS=6
    lock=threading.Lock()
    def work(t):
        scol=(ucol.get(t["game_id"]) or "black").capitalize()
        cap,status=gold_for(t,scol)
        rec={**{k:t[k] for k in ("game_id","cognitive_gap","move_number","fen_before","move_san","cp_loss","best_move_san")},"gold_caption":cap,"verify_status":status}
        if a.apply and cap:
            db.gold_captions.update_one(
                {"created_by":a.tag,"game_id":rec["game_id"],"move_number":rec["move_number"]},
                {"$set":{**rec,"created_by":a.tag}}, upsert=True)
        return t,status,cap,rec
    print(f"parallel gold gen: {len(pending)} targets x {WORKERS} workers (skipping {stats['skip_done']} done)", flush=True)
    done_ct=0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs=[ex.submit(work,t) for t in pending]
        for fut in as_completed(futs):
            try: t,status,cap,rec=fut.result()
            except Exception as e:
                with lock: stats["work_err"]=stats.get("work_err",0)+1
                print("  [work err]",str(e)[:70], flush=True); continue
            with lock:
                stats[status]=stats.get(status,0)+1; out.append(rec); done_ct+=1
            print(f"  [{done_ct}/{len(pending)}] [{t['cognitive_gap']}] {t['move_san']} ({status}): {(cap or '(HELD)')[:65]}", flush=True)
    print("\nstats:",stats)
    try: json.dump(out,open(f"/app/backend/data/gold_{a.tag}.json","w"),indent=1)
    except Exception: pass
    if a.apply:
        print(f"stored (incrementally) {sum(1 for r in out if r['gold_caption'])} new verified golds under tag {a.tag}; "
              f"total now: {db.gold_captions.count_documents({'created_by':a.tag})}")

main()
