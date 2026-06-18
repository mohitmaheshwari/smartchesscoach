"""Whole-game gold v2: GROUND Opus with real Stockfish lines per move (computed at gen
time, since stored PVs are empty) + a LENGTH nudge (brief on routine moves, full on key
ones). One Opus call per game. Verifies each caption per-FEN. Prints all captions.

Env: PMONGO, LLM_EXPOSER_URL, LLM_EXPOSER_KEY
Usage: python scripts/whole_game_gold_v2.py <game_id>
"""
import os, sys, json, time, urllib.request, shutil
sys.path.insert(0, "/app/backend"); sys.path.insert(0, "/app/backend/scripts")
import pymongo, chess, chess.engine
from services.narrator_claim_verifier import verify_caption

URL = os.environ["LLM_EXPOSER_URL"].rstrip("/"); KEY = os.environ["LLM_EXPOSER_KEY"]; RATING = 1100
SF = shutil.which("stockfish") or "/usr/games/stockfish"

HEAD = """You are a kind chess coach reviewing a COMPLETE game for a {rating}-rated student who plays {color}. Write in VERY EASY English (simple words, short sentences, no chess jargon). You can see the WHOLE game, so USE THE CONTEXT — the opening, the plan so far, and what a piece set up on an earlier move.

LENGTH: keep ROUTINE moves to ONE short sentence. Save the fuller treatment (2 short sentences + a one-line lesson) for the IMPORTANT moves — the opening name, mistakes, tactics, captures, and key plans. Do not pad quiet moves.

Here is the game move by move. For each move I give the engine's BEST move here and the engine LINE after the move actually played (this is ground truth — trust it over your own calc):
{moves}

For EACH move number write ONE caption:
- STUDENT move: what it does in the plan. If it is a MISTAKE, name the better move + a one-line WHY (use the engine's best move/line). Only mention a better move when it is CLEARLY better — do NOT nitpick near-equal moves.
- OPPONENT move: what it means for the student and what to do. If the opponent BLUNDERED, name the CONCRETE punishing move (the first move of the "line after" is the student's best reply) — not a vague "punish it".
Refer back to earlier moves when it helps. TRUTH: only state a capture/threat/fork/check if the engine line shows it; never say "free" unless the piece is truly undefended.

Return ONLY JSON — a caption for EVERY move number: {{"1":"...", ... ,"{n}":"..."}}"""


def pv_san(board, pv, k=5):
    b = board.copy(); out = []
    for mv in pv[:k]:
        try: out.append(b.san(mv))
        except Exception: break
        b.push(mv)
    return " ".join(out)


def call_llm(p):
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    for _ in range(2):
        try:
            d = json.dumps({"provider": "claude", "question": p, "timeout_seconds": 240}).encode()
            r = urllib.request.Request(URL + "/ask", data=d, headers=h, method="POST")
            with urllib.request.urlopen(r, timeout=40) as x:
                tid = json.loads(x.read().decode()).get("task_id")
            for _ in range(90):
                time.sleep(4)
                try:
                    rec = json.loads(urllib.request.urlopen(urllib.request.Request(URL + f"/tasks/{tid}", headers=h), timeout=40).read().decode())
                except Exception:
                    continue
                if rec.get("status") in ("completed", "done", "finished", "succeeded"):
                    return (rec.get("answer") or "").strip()
        except Exception:
            time.sleep(2)
    return ""


def parse(s):
    try: return json.loads(s[s.index("{"): s.rindex("}") + 1])
    except Exception: return {}


def main():
    gid = sys.argv[1]
    db = pymongo.MongoClient(os.environ["PMONGO"])["chess_coach"]
    dd = (db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "decryption_v5_data": 1}) or {}).get("decryption_v5_data") or []
    moves = [m for m in dd if m.get("move_san") and m.get("fen_before")]
    uc = "white"
    for m in moves:
        if m.get("is_user_move"): uc = "white" if m.get("is_white") else "black"; break
    eng = chess.engine.SimpleEngine.popen_uci(SF)
    lines = []
    print("computing engine lines per move...", flush=True)
    for i, m in enumerate(moves, 1):
        fb = m["fen_before"]; fa = m.get("fen_after")
        try:
            bb = chess.Board(fb)
            best = eng.analyse(bb, chess.engine.Limit(depth=16))
            best_san = pv_san(bb, best.get("pv", []), 1) or "(n/a)"
        except Exception:
            best_san = "(n/a)"
        played_line = "(end)"
        if fa:
            try:
                ba = chess.Board(fa)
                if not ba.is_game_over():
                    pl = eng.analyse(ba, chess.engine.Limit(depth=14))
                    played_line = pv_san(ba, pl.get("pv", []), 4) or "(quiet)"
            except Exception:
                played_line = "(quiet)"
        who = "STUDENT" if m.get("is_user_move") else "OPPONENT"
        lines.append(f"[{i}] {who}: {m['move_san']}  (~{abs(int(m.get('cp_loss') or 0))}cp lost; engine best here: {best_san}; line after {m['move_san']}: {played_line})")
    eng.quit()
    prompt = HEAD.format(rating=RATING, color=uc, moves="\n".join(lines), n=len(moves))
    print("calling Opus (1 call)...", flush=True)
    ans = parse(call_llm(prompt))
    print(f"\n=== {gid[:13]} (student {uc}) — v2 captions (engine-grounded + length-nudged) ===")
    kept = drop = 0
    for i, m in enumerate(moves, 1):
        cap = (ans.get(str(i)) or "").strip()
        f = {"move_san": m["move_san"], "fen_before": m["fen_before"], "fen_after": m.get("fen_after"),
             "is_user_move": bool(m.get("is_user_move")), "cp_loss": abs(int(m.get("cp_loss") or 0)),
             "best_move_san": m.get("best_move_san"), "pv_after_best": [], "pv_after_played": m.get("pv_after_played") or []}
        v = verify_caption(cap, f) if cap else ["missing"]
        who = "YOU " if m.get("is_user_move") else "OPP "
        if v:
            drop += 1
            print(f"{who}{m['move_number']:>2}:{m['move_san']:6} [DROP {v[0].get('check') if isinstance(v[0],dict) else v[0]}] {cap[:80]}")
        else:
            kept += 1
            print(f"{who}{m['move_number']:>2}:{m['move_san']:6} {cap}")
    print(f"\nkept {kept}, dropped {drop}")


if __name__ == "__main__":
    main()
