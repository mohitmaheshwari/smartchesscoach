"""Regenerate ALL Claude-GOLD tester captions for one game in VERY EASY English
(Opus 4.8 via the exposer), engine-verified, overwriting gold_tester_captions.

Prompt rewritten for readers with basic English: simple everyday words, short
sentences, no chess jargon, one plain lesson at the end. Truth rules kept (verify
every claim on the board; abstain/correct on failure).

Env: PMONGO, LLM_EXPOSER_URL, LLM_EXPOSER_KEY
Usage: python scripts/regen_gold_easy.py <game_id> [--apply]
"""
import os, sys, json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, "/app/backend")
import pymongo
from services.narrator_claim_verifier import verify_caption

URL = os.environ["LLM_EXPOSER_URL"].rstrip("/"); KEY = os.environ["LLM_EXPOSER_KEY"]; RATING = 1000

PROMPT = """You are a kind chess coach. Write a SHORT caption (1 to 2 short sentences) for a {rating} student who plays {scol}.

WRITE IN VERY EASY ENGLISH — this is the most important rule:
- Use simple, everyday words. A 10-year-old, or someone still learning English, must understand it.
- Keep sentences short — about 8 to 10 words. One idea per sentence.
- NO chess jargon. Do not use words like develop, centralize, tempo, prophylaxis, fianchetto, initiative. Say it plainly: "bring your knight out", "put it in the middle", "make your king safe", "take the free piece".
- No hard words, no fancy grammar, no semicolons, no CAPITAL words, no markdown.

This move ({move}) was played by {mover}.
- If it is the STUDENT's move: say in plain words what it does. If it is a mistake, say the better move and why, simply.
- If it is the OPPONENT's move: say what it means for the student, and what the student should do.

End with ONE short, simple lesson (the principle), said in plain words.
Keep the WHOLE caption to one short paragraph — about 2 to 4 short sentences. No blank lines.

TRUTH RULES: only say a capture, threat, fork, or check if it is really true in the engine line. Never say "free" unless the piece is truly undefended. Use real square names.

FEN: {fen}  Side to move: {side}
Played: {move} (engine says about {cp} centipawns lost)  Best move: {best}  Line after best: {pvb}  Line after played: {pvp}
Write ONLY the caption, nothing else."""

CORRECT = """Your caption: "{cap}"
These claims are FALSE on the board:
{errs}
Rewrite it. Fix only these. Keep it 1 to 2 short sentences in VERY EASY English (simple words, short sentences), student's side, add no new untrue claim. Write ONLY the caption."""


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
    return {"move_san": m.get("move_san"), "fen_before": m.get("fen_before"), "fen_after": m.get("fen_after"),
            "is_user_move": bool(m.get("is_user_move")), "cp_loss": abs(int(m.get("cp_loss") or 0)),
            "best_move_san": m.get("best_move_san"), "pv_after_best": m.get("pv_after_best") or [],
            "pv_after_played": m.get("pv_after_played") or []}


def gold_for(f, scol):
    mover = "the student" if f["is_user_move"] else "the opponent"
    p = PROMPT.format(rating=RATING, scol=scol, move=f["move_san"], mover=mover, fen=f["fen_before"], side=side(f["fen_before"]),
                      cp=f["cp_loss"], best=f.get("best_move_san") or "(none)",
                      pvb=" ".join((f.get("pv_after_best") or [])[:5]) or "(none)",
                      pvp=" ".join((f.get("pv_after_played") or [])[:5]) or "(none)")
    cap = call_llm(p)
    if not cap:
        return (None, "narrator_unavailable")
    v = verify_caption(cap, f)
    if not v:
        return (cap, "verified")
    cap2 = call_llm(CORRECT.format(cap=cap, errs="\n".join("- " + x.get("check", str(x)) for x in v)))
    if cap2 and not verify_caption(cap2, f):
        return (cap2, "verified_after_correction")
    return (cap2 or cap, "kept_with_warning")  # keep best effort; comparison will re-verify


def main():
    gid = sys.argv[1]
    apply = "--apply" in sys.argv
    db = pymongo.MongoClient(os.environ["PMONGO"])["chess_coach"]
    dd = (db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "decryption_v5_data": 1}) or {}).get("decryption_v5_data") or []
    scol = "white"
    moves = [m for m in dd if m.get("move_san") and m.get("fen_before")]
    print(f"regenerating {len(moves)} gold captions (Opus 4.8, EASY English) apply={apply}", flush=True)

    def work(m):
        cap, status = gold_for(facts_from(m), scol)
        return (m, cap, status)

    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(work, m): m for m in moves}
        for fut in as_completed(futs):
            m, cap, status = fut.result()
            key = f"{m.get('move_number')}:{m.get('move_san')}"
            if cap:
                done += 1
                if apply:
                    db.gold_tester_captions.update_one(
                        {"game_id": gid, "move_number": m["move_number"], "move_san": m["move_san"]},
                        {"$set": {"caption": cap, "is_user_move": bool(m.get("is_user_move")), "status": status,
                                  "model": "claude-opus-4-8", "style": "easy_english"}}, upsert=True)
                print(f"  {key:10} ({status}) {cap[:62]}", flush=True)
            else:
                print(f"  {key:10} FAILED ({status})", flush=True)
    print(f"DONE regenerated={done}/{len(moves)}", flush=True)


if __name__ == "__main__":
    main()
