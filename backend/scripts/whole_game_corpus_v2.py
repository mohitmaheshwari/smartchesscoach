"""100-game whole-game gold corpus, v2 prompt (engine-grounded + length nudge +
concrete-punishment + clearly-better-only). 1 Opus call/game; Stockfish lines computed
per move (per-worker engine); each caption verified per-FEN. Writes the records the
aligned-corpus-table is built from.

Outputs: _gold_corpus_wg.json {type:[caps]} · _gold_records_wg.jsonl (per-move)
Env: PMONGO, LLM_EXPOSER_URL, LLM_EXPOSER_KEY
Usage: python scripts/whole_game_corpus_v2.py <gid...>
"""
import os, sys, json, time, urllib.request, shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, "/app/backend"); sys.path.insert(0, "/app/backend/scripts")
import pymongo, chess, chess.engine
from services.narrator_claim_verifier import verify_caption
from group_gold_by_type import move_type

URL = os.environ["LLM_EXPOSER_URL"].rstrip("/"); KEY = os.environ["LLM_EXPOSER_KEY"]; RATING = 1100
SF = shutil.which("stockfish") or "/usr/games/stockfish"

HEAD = """You are a kind chess coach reviewing a COMPLETE game for a {rating}-rated student who plays {color}. Write in VERY EASY English (simple words, short sentences, no chess jargon). You can see the WHOLE game, so USE THE CONTEXT — the opening, the plan so far, and what a piece set up on an earlier move.

LENGTH: keep ROUTINE moves to ONE short sentence. Save the fuller treatment (2 short sentences + a one-line lesson) for the IMPORTANT moves — the opening name, mistakes, tactics, captures, key plans. Do not pad quiet moves.

Here is the game move by move. For each move I give the engine's BEST move here and the engine LINE after the move actually played (ground truth — trust it over your own calc):
{moves}

For EACH move number write ONE caption:
- STUDENT move: what it does in the plan. If it is a MISTAKE, name the better move + a one-line WHY (use the engine best). Only mention a better move when it is CLEARLY better — do NOT nitpick near-equal moves.
- OPPONENT move: what it means for the student and what to do. If the opponent BLUNDERED, name the CONCRETE punishing move (the first move of the "line after" is the student's best reply) — not a vague "punish it".
Refer back to earlier moves when it helps. TRUTH: only state a capture/threat/fork/check if the engine line shows it; never say "free" unless truly undefended.

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


def facts(m):
    return {"move_san": m.get("move_san"), "fen_before": m.get("fen_before"), "fen_after": m.get("fen_after"),
            "is_user_move": bool(m.get("is_user_move")), "cp_loss": abs(int(m.get("cp_loss") or 0)),
            "best_move_san": m.get("best_move_san"), "pv_after_best": [], "pv_after_played": m.get("pv_after_played") or []}


def do_game(gid, dd):
    moves = [m for m in dd if m.get("move_san") and m.get("fen_before")]
    if not moves:
        return []
    uc = "white"
    for m in moves:
        if m.get("is_user_move"): uc = "white" if m.get("is_white") else "black"; break
    try:
        eng = chess.engine.SimpleEngine.popen_uci(SF)
    except Exception:
        return []
    lines = []
    try:
        for i, m in enumerate(moves, 1):
            try:
                bb = chess.Board(m["fen_before"])
                best_san = pv_san(bb, eng.analyse(bb, chess.engine.Limit(depth=14)).get("pv", []), 1) or "(n/a)"
            except Exception:
                best_san = "(n/a)"
            played_line = "(end)"
            fa = m.get("fen_after")
            if fa:
                try:
                    ba = chess.Board(fa)
                    if not ba.is_game_over():
                        played_line = pv_san(ba, eng.analyse(ba, chess.engine.Limit(depth=12)).get("pv", []), 4) or "(quiet)"
                except Exception:
                    played_line = "(quiet)"
            who = "STUDENT" if m.get("is_user_move") else "OPPONENT"
            lines.append(f"[{i}] {who}: {m['move_san']}  (~{abs(int(m.get('cp_loss') or 0))}cp lost; engine best: {best_san}; line after {m['move_san']}: {played_line})")
    finally:
        eng.quit()
    ans = parse(call_llm(HEAD.format(rating=RATING, color=uc, moves="\n".join(lines), n=len(moves))))
    out = []
    for i, m in enumerate(moves, 1):
        cap = (ans.get(str(i)) or "").strip()
        if not cap or verify_caption(cap, facts(m)):
            continue
        out.append((gid, m, cap, move_type(m)))
    return out


def main():
    gids = [a for a in sys.argv[1:] if not a.startswith("-")]
    db = pymongo.MongoClient(os.environ["PMONGO"])["chess_coach"]
    games = []
    for gid in gids:
        dd = (db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "decryption_v5_data": 1}) or {}).get("decryption_v5_data") or []
        if dd:
            games.append((gid, dd))
    print(f"{len(games)} games (v2: engine-grounded + length-nudged), 1 Opus call each", flush=True)
    corpus, records = {}, []
    done = kept = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(do_game, gid, dd) for gid, dd in games]
        for fut in as_completed(futs):
            done += 1
            try:
                res = fut.result()
            except Exception:
                res = []
            for gid, m, cap, t in res:
                kept += 1
                corpus.setdefault(t, []).append(cap)
                records.append({"game": gid, "move_number": m.get("move_number"), "move_san": m.get("move_san"),
                                "fen_before": m.get("fen_before"), "fen_after": m.get("fen_after"),
                                "is_user_move": bool(m.get("is_user_move")), "cp_loss": abs(int(m.get("cp_loss") or 0)),
                                "pv_after_played": m.get("pv_after_played") or [], "type": t, "caption": cap})
            if done % 10 == 0:
                print(f"  {done}/{len(games)} games, {kept} verified captions", flush=True)
    with open("/app/backend/scripts/_gold_corpus_wg.json", "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1)
    with open("/app/backend/scripts/_gold_records_wg.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"DONE games={done} verified_captions={kept} types={len(corpus)}", flush=True)


if __name__ == "__main__":
    main()
