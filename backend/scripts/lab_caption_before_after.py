"""lab_caption_before_after.py — §2 before/after fixture for fact_templated_captions.

For real flagged Lab blunders (game_analyses.decryption_data), shows the EXISTING stored caption next
to a FRESH grounded caption from the verified no-hallucination prompt, with the engine PVs printed so
each fresh claim can be checked against the board (per [[feedback_keyword_caption_audit_unreliable]] —
engine-verify, don't keyword-scan). This is the scope's §2 product contract + a confabulation/why-rule
baseline on the actual review surface.

Findings on the first run (2026-06-10): the existing Lab captions for flagged blunders were bare
move-restatements ("knight to d4.") with NO why — the why-rule violated 6/6 — while the fresh captions
all carried a grounded, position-specific why. The problem is absence of coaching, not just confabulation.

Config via env (no secret committed):
    LLM_EXPOSER_URL, LLM_EXPOSER_KEY, MONGO_URL, DB_NAME, STOCKFISH_PATH(opt)
Usage:
    python backend/scripts/lab_caption_before_after.py --limit 6 --min-cp 150 --rating 1200
"""
import os
import json
import time
import argparse
import urllib.request
import chess
import chess.engine
from pymongo import MongoClient

SF = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")

PROMPT = """You are a chess coach writing a ONE or TWO sentence caption for a {rating}-rated player about the move below. RULES:
- The move was flagged by the engine as a {evaluation}. You MUST explain WHY in plain, simple English (coaching tone) — what the move allows, abandons, or misses, and what was better.
- Name concrete squares/pieces. No chess jargon (no zwischenzug/prophylaxis/fianchetto).
- NEVER state a capture, target square, or follow-up move unless it is actually true on the board.
- Do not pad with generic principles ("develop your pieces"). The why must fit THIS position.

Position (FEN): {fen}
Side to move: {side}
Move played: {move}  (engine says: {evaluation}, lost ~{cp}cp)
Engine's best instead: {best}
Engine line after best: {pv_best}
Engine line after the played move: {pv_played}

Write only the caption text, nothing else."""


def ask(prompt):
    url = os.environ["LLM_EXPOSER_URL"].rstrip("/")
    key = os.environ["LLM_EXPOSER_KEY"]
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    for _ in range(3):
        try:
            req = urllib.request.Request(
                url + "/ask",
                data=json.dumps({"provider": "claude", "question": prompt, "timeout_seconds": 150}).encode(),
                headers=h, method="POST",
            )
            with urllib.request.urlopen(req, timeout=40) as r:
                tid = json.loads(r.read().decode())["task_id"]
            for _ in range(50):
                time.sleep(4)
                try:
                    with urllib.request.urlopen(urllib.request.Request(url + f"/tasks/{tid}", headers=h), timeout=40) as r2:
                        rec = json.loads(r2.read().decode())
                except Exception:
                    continue
                if rec.get("status") in ("completed", "done", "finished", "succeeded"):
                    return (rec.get("answer") or "").strip()
                if rec.get("status") in ("error", "failed"):
                    break
        except Exception:
            time.sleep(3)
    return "[llm failed]"


def pvline(board, eng, n=6):
    info = eng.analyse(board, chess.engine.Limit(time=0.4))
    out, b = [], board.copy()
    for m in info["pv"][:n]:
        out.append(b.san(m))
        b.push(m)
    return " ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--min-cp", type=int, default=150)
    ap.add_argument("--rating", type=int, default=1200)
    ap.add_argument("--out", default="/tmp/lab_before_after.json")
    args = ap.parse_args()

    db = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000)[os.environ.get("DB_NAME", "chess_coach")]
    eng = chess.engine.SimpleEngine.popen_uci(SF)
    rows, n = [], 0
    for g in db.game_analyses.find({"decryption_data": {"$exists": True}}).limit(120):
        if n >= args.limit:
            break
        for ev in g.get("decryption_data", []):
            if n >= args.limit:
                break
            if not ev.get("is_user_move") or not ev.get("is_mistake"):
                continue
            cp = ev.get("cp_loss") or 0
            if cp < args.min_cp:
                continue
            fen, mv, best = ev.get("fen_before"), ev.get("move_san"), ev.get("best_move_san")
            if not (fen and mv and best):
                continue
            existing = ev.get("better_plan") or ev.get("mistake_analysis") or ev.get("narrative") or "(none)"
            try:
                b = chess.Board(fen)
                bb = b.copy(); bb.push_san(best); pv_best = best + " " + pvline(bb, eng, 5)
                bp = b.copy(); bp.push_san(mv); pv_played = pvline(bp, eng, 6)
            except Exception:
                continue
            side = "White" if b.turn == chess.WHITE else "Black"
            evl = "blunder" if cp >= 200 else "mistake"
            fresh = ask(PROMPT.format(rating=args.rating, evaluation=evl, fen=fen, side=side,
                                      move=mv, cp=cp, best=best, pv_best=pv_best, pv_played=pv_played))
            n += 1
            row = {"game_id": g.get("game_id"), "move_number": ev.get("move_number"), "move": mv,
                   "cp": cp, "best": best, "pv_best": pv_best, "pv_played": pv_played,
                   "existing": str(existing), "fresh": fresh}
            rows.append(row)
            print(f"\n=== {row['move_number']} {mv} ({evl}, {cp}cp), best {best} ===")
            print(f"  pv_best   : {pv_best}")
            print(f"  pv_played : {pv_played}")
            print(f"  EXISTING  : {row['existing'][:230]}")
            print(f"  FRESH     : {fresh}")
    eng.quit()
    with open(args.out, "w") as fh:
        json.dump(rows, fh, indent=2)
    print(f"\nwrote {len(rows)} before/after rows to {args.out}")


if __name__ == "__main__":
    main()
