"""Offline narrator pipeline: for moves the detector ABSTAINS on, write a coach
caption via the LLM gateway, VERIFY it against the board (narrator_claim_verifier),
SELF-CORRECT failures once, and BACKFILL only verified captions; HOLD double-fails.

This is the narrator safety-net + self-correction loop (2026-06-11). It complements
the detector verifier (caption_claim_verifier) — detectors grow from the abstention
log; until they cover a move, the narrator carries it, and NEVER ships an unverified
claim.

Usage (in the backend container, gateway env set):
    python scripts/narrate_verify_backfill.py --game game_xxx --moves 9,10,13          # dry-run
    python scripts/narrate_verify_backfill.py --game game_xxx --apply                  # backfill all flagged
"""
import os, sys, json, time, argparse, urllib.request
sys.path.insert(0, "/app/backend")
import pymongo, chess
from services.narrator_claim_verifier import verify_caption

URL = os.environ["LLM_EXPOSER_URL"].rstrip("/"); KEY = os.environ["LLM_EXPOSER_KEY"]; RATING = 1200

PROMPT = """You are a chess coach writing a SHORT caption (max 2 sentences, ~30-40 words) for a {rating} student who plays {scol}. Coach who TEACHES.
Every "you/your" = the student. This move ({move}) was played by {mover}.
- STUDENT's move: name the opening/fundamental, or for a mistake the better move + one-line why.
- OPPONENT's move: what it means FOR THE STUDENT + what you do next.
Land one short principle, stated directly.
RULES: concrete squares; no jargon/markdown/CAPS; NEVER state a capture/tactic/threat/follow-up unless true per the engine lines; never call a pawn "free" unless truly undefended.
Opening: {opening}
Move {mn} ({phase}) — by {mover}
FEN: {fen}  Side to move: {side}
Played: {move} (engine: {sev}, ~{cp}cp lost)
Best: {best}  Line after best: {pvb}  Line after played: {pvp}
Write ONLY the caption."""

CORRECT = """Your caption: "{cap}"
It has FACTUAL ERRORS verified against the board (ground truth):
{errs}
Rewrite fixing ONLY these, max 2 sentences, same coaching tone, student's seat. Do NOT add any new tactic/square unless true. Write ONLY the caption."""

def call_llm(prompt, retries=3):
    h={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"}; last="x"
    for _ in range(retries):
        try:
            d=json.dumps({"provider":"claude","question":prompt,"timeout_seconds":180}).encode()
            r=urllib.request.Request(URL+"/ask",data=d,headers=h,method="POST")
            with urllib.request.urlopen(r,timeout=40) as x: tid=json.loads(x.read().decode()).get("task_id")
            for _ in range(60):
                time.sleep(4)
                try:
                    pr=urllib.request.Request(URL+f"/tasks/{tid}",headers=h)
                    with urllib.request.urlopen(pr,timeout=40) as x2: rec=json.loads(x2.read().decode())
                except Exception: continue
                if rec.get("status") in ("completed","done","finished","succeeded"): return (rec.get("answer") or "").strip()
                if rec.get("status") in ("error","failed"): last=rec.get("error"); break
        except Exception as e: last=str(e); time.sleep(3)
    return ""

def side_of(fen): return "White" if fen.split(" ")[1]=="w" else "Black"

def narrate_verified(e, scol):
    """narrate -> verify -> self-correct once -> (caption|None, status)."""
    is_user=e.get("is_user_move")
    mover="the student (you)" if is_user else f"the opponent ({'White' if e.get('is_white') else 'Black'})"
    p=PROMPT.format(rating=RATING,scol=scol,move=e["move_san"],mover=mover,opening=e.get("opening_name") or "(unknown)",
        mn=e["move_number"],phase=e.get("phase") or "?",fen=e["fen_before"],side=side_of(e["fen_before"]),
        sev=e.get("severity"),cp=e.get("cp_loss"),best=e.get("best_move_san") or "(n/a)",
        pvb=" ".join(e.get("pv_after_best") or []) or "(none)",pvp=" ".join(e.get("pv_after_played") or []) or "(none)")
    cap=call_llm(p)
    if not cap: return (None,"narrator_unavailable")
    v=verify_caption(cap,e)
    if not v: return (cap,"verified_first_pass")
    # self-correct once
    fix=CORRECT.format(cap=cap,errs="\n".join("- "+x["detail"] for x in v))
    cap2=call_llm(fix)
    if cap2 and not verify_caption(cap2,e): return (cap2,"verified_after_correction")
    return (None,"HELD_double_fail")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--game",default="game_af4d58d0936a")
    ap.add_argument("--moves",default=""); ap.add_argument("--apply",action="store_true"); a=ap.parse_args()
    db=pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME","chess_coach")]
    g=db.games.find_one({"game_id":a.game},{"user_color":1}); scol=(g.get("user_color") or "black").capitalize()
    ga=db.game_analyses.find_one({"game_id":a.game},{"decryption_v5_data_detector_backup":1,"decryption_v5_data":1})
    facts=ga["decryption_v5_data_detector_backup"]
    want=set(int(x) for x in a.moves.split(",") if x.strip()) if a.moves else None
    targets=[e for e in facts if e.get("is_user_move") and (e.get("cp_loss") or 0)>=30 and (want is None or e["move_number"] in want)]
    print(f"game {a.game}: {len(targets)} target move(s) | mode {'APPLY' if a.apply else 'DRY-RUN'}\n")
    results={}
    for e in targets:
        cap,status=narrate_verified(e,scol)
        results[f"{e['move_number']}-1"]=(cap,status)
        print(f"m{e['move_number']} {e['move_san']} [{status}]:\n  {cap or '(HELD — nothing shipped)'}\n")
    if a.apply:
        live=ga["decryption_v5_data"]; n=0
        for d in live:
            k=f"{d.get('move_number')}-{1 if d.get('is_user_move') else 0}"
            if k in results and results[k][0]:
                d["caption"]=results[k][0]; d["caption_source"]="narrator_verified"; n+=1
        db.game_analyses.update_one({"game_id":a.game},{"$set":{"decryption_v5_data":live}})
        print(f"backfilled {n} verified narrator caption(s)")

main()
