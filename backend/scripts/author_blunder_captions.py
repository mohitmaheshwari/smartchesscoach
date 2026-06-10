"""author_blunder_captions.py — OFFLINE grounded-caption authoring for flagged blunders.

The verified approach (2026-06-10): an LLM, fed ONLY Stockfish truth (FEN, eval, the played move +
its refutation line, the best move + its line), writes a "why was this a mistake" caption. Verified to
(a) name real tactics correctly and (b) NEVER invent a tactic that isn't on the board — proven on both a
queen-hang (no tactic, it correctly said "no tactic justifies it") and a removed-defender case (a real
tactic, it correctly named Qxe3+ and the mechanism). Pairs with [[feedback_query_engine_before_authoring]]
and the no-hallucination rule in services/pwc_live_coach.py.

This is the OFFLINE authoring step in Mohit's intended flow: LLM drafts captions -> human approves
(/admin/captions) -> approved text is baked into templates. There is NO live LLM in production.

Config via env (NEVER hardcode the key):
    LLM_EXPOSER_URL   e.g. http://host.docker.internal:8000  (direct host; reliable)
    LLM_EXPOSER_KEY   the exposer bearer key
    MONGO_URL, DB_NAME (already set in the backend container)
    STOCKFISH_PATH    optional, default /usr/games/stockfish

Usage:
    python backend/scripts/author_blunder_captions.py --limit 6 --min-cp 200 --rating 1200
"""
import os
import sys
import json
import argparse
import asyncio
import urllib.request
import chess
import chess.engine
from motor.motor_asyncio import AsyncIOMotorClient

SF = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")

PROMPT_TEMPLATE = """You are a chess coach writing a ONE or TWO sentence caption for a {rating}-rated player about the move below. RULES:
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


def classify(cp: int) -> str:
    # Rating-aware thresholds live elsewhere; this offline tool uses a simple split for labelling.
    if cp >= 200:
        return "blunder"
    if cp >= 90:
        return "mistake"
    return "inaccuracy"


def _pv(board, eng, secs=0.3, n=6):
    info = eng.analyse(board, chess.engine.Limit(time=secs))
    sans, bb = [], board.copy()
    for m in info["pv"][:n]:
        sans.append(bb.san(m))
        bb.push(m)
    score = info["score"].pov(board.turn).score(mate_score=10000)
    first = info["pv"][0] if info["pv"] else None
    return score, first, sans


def call_llm(prompt: str, retries: int = 3) -> str:
    """Async /ask + poll — robust to the agentic CLI taking >2min and to transient tunnel drops.
    (sync /invoke holds the connection the whole time and times out.)"""
    import time
    url = os.environ["LLM_EXPOSER_URL"].rstrip("/")
    key = os.environ["LLM_EXPOSER_KEY"]
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    last = "no response"
    for _ in range(retries):
        try:
            data = json.dumps({"provider": "claude", "question": prompt, "timeout_seconds": 180}).encode()
            req = urllib.request.Request(url + "/ask", data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=40) as r:
                tid = json.loads(r.read().decode()).get("task_id")
            for _ in range(60):
                time.sleep(4)
                try:
                    pr = urllib.request.Request(url + f"/tasks/{tid}", headers=headers)
                    with urllib.request.urlopen(pr, timeout=40) as r2:
                        rec = json.loads(r2.read().decode())
                except Exception:
                    continue
                st = rec.get("status")
                if st in ("completed", "done", "finished", "succeeded"):
                    return (rec.get("answer") or "").strip()
                if st in ("error", "failed"):
                    last = rec.get("error") or "task failed"
                    break
        except Exception as e:
            last = str(e)
            time.sleep(3)
    return f"[llm failed: {last}]"


async def find_blunders(db, limit, min_cp, rating):
    eng = chess.engine.SimpleEngine.popen_uci(SF)
    found = []
    try:
        cur = db.coach_sessions.find(
            {"move_history.10": {"$exists": True}},
            {"_id": 0, "move_history": 1, "user_color": 1, "session_id": 1},
        ).sort("created_at", -1).limit(40)
        async for s in cur:
            uc = s.get("user_color", "white")
            for m in s["move_history"]:
                if len(found) >= limit:
                    break
                fb, mv = m.get("fen_before"), m.get("move")
                if not fb or not mv:
                    continue
                b = chess.Board(fb)
                if (b.turn == chess.WHITE) != (uc == "white"):
                    continue
                if not (6 <= b.fullmove_number <= 35):
                    continue
                best_ev, best_mv, pvb = _pv(b, eng)
                if best_mv is None:
                    continue
                best_san = b.san(best_mv)
                try:
                    actual = b.parse_san(mv)
                except Exception:
                    continue
                b2 = b.copy()
                b2.push(actual)
                # _pv scores from the side-to-move POV; after the played move it is the OPPONENT's
                # turn, so negate to get the mover's POV before comparing. Without this, a best move
                # scores as a huge "blunder" (the POV bug that flagged played==best as ~994cp).
                played_score, _, pvp = _pv(b2, eng)
                cp = best_ev - (-played_score)
                if cp < min_cp or abs(best_ev) > 700:  # real blunder, not already-decided
                    continue
                found.append({
                    "fen": fb, "side": "White" if b.turn == chess.WHITE else "Black",
                    "move": mv, "cp": cp, "best": best_san,
                    "pv_best": " ".join(pvb), "pv_played": " ".join(pvp),
                    "evaluation": classify(cp), "rating": rating,
                    "session": s["session_id"][:8], "move_number": b.fullmove_number,
                })
            if len(found) >= limit:
                break
    finally:
        eng.quit()
    return found


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--min-cp", type=int, default=200)
    ap.add_argument("--rating", type=int, default=1200)
    ap.add_argument("--out", default="/tmp/blunder_captions.json")
    args = ap.parse_args()

    db = AsyncIOMotorClient(
        os.environ["MONGO_URL"], serverSelectionTimeoutMS=12000
    )[os.environ.get("DB_NAME", "chess_coach")]
    await db.command("ping")

    blunders = await find_blunders(db, args.limit, args.min_cp, args.rating)
    out = []
    for f in blunders:
        try:
            f["caption"] = call_llm(PROMPT_TEMPLATE.format(**f))
        except Exception as e:
            f["caption"] = f"[llm failed: {e}]"
        out.append(f)
        print(f"\n--- {f['session']} m{f['move_number']} {f['move']} "
              f"({f['evaluation']}, {f['cp']}cp) ---")
        print(f"  best {f['best']} | pv_best {f['pv_best']} | pv_played {f['pv_played']}")
        print(f"  CAPTION: {f['caption']}")
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nwrote {len(out)} captions to {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
