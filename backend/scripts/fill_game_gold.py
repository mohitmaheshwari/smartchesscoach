"""Fill Claude-GOLD tester captions for EVERY move of one game (both colors,
routine moves included), so the side-by-side tester panel has gold on every ply.

Reuses build_gold_set's every-move teaching prompt + narrator_claim_verifier.
Only verified captions are stored. Writes to db.gold_tester_captions keyed by
(game_id, move_number, move_san), with is_user_move recorded this time.

Env: PMONGO (prod), LLM_EXPOSER_URL (http://host.docker.internal:8000), LLM_EXPOSER_KEY
Usage: python scripts/fill_game_gold.py <game_id> [--apply]
"""
import os, sys, json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, "/app/backend")
import pymongo, chess
from services.narrator_claim_verifier import verify_caption

URL = os.environ["LLM_EXPOSER_URL"].rstrip("/")
KEY = os.environ["LLM_EXPOSER_KEY"]
RATING = 1200

PROMPT = """You are a chess coach writing a SHORT caption (max 2 sentences, ~30-40 words) for a {rating} student who plays {scol}. Coach who TEACHES, not rates. Every you/your = the student.
This move ({move}) was played by {mover}. STUDENT move: name opening/fundamental, or (mistake) the better move + a one-line why. OPPONENT move: what it means for you + what you do.
Land one short principle, stated directly. RULES: concrete squares; no jargon/markdown/CAPS; NEVER state a capture/tactic/follow-up unless true per the engine lines; never say "free" unless truly undefended.
FEN: {fen}  Side: {side}
Played: {move} (engine ~{cp}cp lost)  Best: {best}  Line-after-best: {pvb}  Line-after-played: {pvp}
Write ONLY the caption."""
CORRECT = """Your caption: "{cap}"
FACTUAL ERRORS vs the board (ground truth):
{errs}
Rewrite fixing ONLY these, max 2 sentences, same tone, student's seat, no new untrue claim. Write ONLY the caption."""


def call_llm(p, retries=2):
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    for _ in range(retries):
        try:
            d = json.dumps({"provider": "claude", "question": p, "timeout_seconds": 180}).encode()
            r = urllib.request.Request(URL + "/ask", data=d, headers=h, method="POST")
            with urllib.request.urlopen(r, timeout=40) as x:
                tid = json.loads(x.read().decode()).get("task_id")
            for _ in range(60):
                time.sleep(4)
                try:
                    pr = urllib.request.Request(URL + f"/tasks/{tid}", headers=h)
                    with urllib.request.urlopen(pr, timeout=40) as x2:
                        rec = json.loads(x2.read().decode())
                except Exception:
                    continue
                if rec.get("status") in ("completed", "done", "finished", "succeeded"):
                    return (rec.get("answer") or "").strip()
        except Exception:
            time.sleep(2)
    return ""


def side(f):
    return "White" if f.split(" ")[1] == "w" else "Black"


def facts_from(m):
    return {
        "move_san": m.get("move_san"),
        "fen_before": m.get("fen_before"),
        "fen_after": m.get("fen_after"),
        "is_user_move": bool(m.get("is_user_move")),
        "cp_loss": m.get("cp_loss"),
        "best_move_san": m.get("best_move_san"),
        "pv_after_best": m.get("pv_after_best") or [],
        "pv_after_played": m.get("pv_after_played") or [],
    }


def gold_for(f, scol):
    mover = "the student" if f["is_user_move"] else "the opponent"
    p = PROMPT.format(rating=RATING, scol=scol, move=f["move_san"], mover=mover,
                      fen=f["fen_before"], side=side(f["fen_before"]),
                      cp=f["cp_loss"], best=f.get("best_move_san") or "(n/a)",
                      pvb=" ".join((f.get("pv_after_best") or [])[:5]) or "(none)",
                      pvp=" ".join((f.get("pv_after_played") or [])[:5]) or "(none)")
    cap = call_llm(p)
    if not cap:
        return (None, "narrator_unavailable")
    v = verify_caption(cap, f)
    if not v:
        return (cap, "verified")
    cap2 = call_llm(CORRECT.format(cap=cap, errs="\n".join("- " + x["detail"] for x in v)))
    if cap2 and not verify_caption(cap2, f):
        return (cap2, "verified_after_correction")
    return (None, "HELD")


def main():
    gid = sys.argv[1]
    apply = "--apply" in sys.argv
    db = pymongo.MongoClient(os.environ["PMONGO"])["chess_coach"]
    ga = db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "decryption_v5_data": 1})
    dd = (ga or {}).get("decryption_v5_data") or []
    have = set(f"{r['move_number']}:{r['move_san']}" for r in
               db.gold_tester_captions.find({"game_id": gid}, {"move_number": 1, "move_san": 1}))
    scol = "white"  # user color for this game
    missing = [m for m in dd if f"{m.get('move_number')}:{m.get('move_san')}" not in have
               and m.get("move_san") and m.get("fen_before")]
    print(f"total={len(dd)} have_gold={len(have)} missing={len(missing)} apply={apply}", flush=True)

    def work(m):
        f = facts_from(m)
        cap, status = gold_for(f, scol)
        return (m, cap, status)

    done = held = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(work, m): m for m in missing}
        for fut in as_completed(futs):
            m, cap, status = fut.result()
            key = f"{m.get('move_number')}:{m.get('move_san')}"
            if cap:
                done += 1
                if apply:
                    db.gold_tester_captions.update_one(
                        {"game_id": gid, "move_number": m["move_number"], "move_san": m["move_san"]},
                        {"$set": {"caption": cap, "is_user_move": bool(m.get("is_user_move")),
                                  "status": status}}, upsert=True)
                print(f"  OK   {key:10} ({status}) {cap[:60]}", flush=True)
            else:
                held += 1
                print(f"  HELD {key:10} ({status})", flush=True)
    print(f"DONE generated={done} held={held}", flush=True)


if __name__ == "__main__":
    main()
