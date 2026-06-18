"""Whole-game easy-English Opus gold: send the COMPLETE game in one call so Opus has
the full arc (opening, plan-so-far, what a piece set up earlier) -> more contextual,
coherent captions. 1 call/game (cheaper: less Claude-Code per-call overhead). Each
caption is engine-VERIFIED per-FEN; unverified ones dropped.

Outputs:  _gold_corpus_wg.json   {move_type: [captions]}
          _gold_records_wg.jsonl per-move records (for consequence-mining)
Env: PMONGO, LLM_EXPOSER_URL, LLM_EXPOSER_KEY
Usage: python scripts/whole_game_gold.py <gid...>
"""
import os, sys, json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, "/app/backend"); sys.path.insert(0, "/app/backend/scripts")
import pymongo
from services.narrator_claim_verifier import verify_caption
from group_gold_by_type import move_type

URL = os.environ["LLM_EXPOSER_URL"].rstrip("/"); KEY = os.environ["LLM_EXPOSER_KEY"]; RATING = 1000

HEAD = """You are a kind chess coach reviewing a COMPLETE game for a {rating}-rated student who plays {color}. Write in VERY EASY English (simple words, short sentences, no chess jargon). You can see the WHOLE game, so USE THE CONTEXT — the opening, the plan so far, what each side is trying to do, and what a piece set up on an earlier move.

Here is the game move by move, with the engine's read on each move:
{moves}

For EACH move number, write ONE short caption (1 to 2 short sentences, then one simple lesson):
- STUDENT move: say what it does in the plan; if it is a mistake, give the better move + a one-line why.
- OPPONENT move: say what it means for the student and what the student should do.
Refer back to earlier moves/plans when it helps the student understand. TRUTH: only state a capture, threat, fork, or check if it is really true in the engine line; never say "free" unless the piece is truly undefended.

Return ONLY JSON — a caption for EVERY move number: {{"1":"...","2":"...", ... ,"{n}":"..."}}"""


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
    try:
        return json.loads(s[s.index("{"): s.rindex("}") + 1])
    except Exception:
        return {}


def facts(m):
    return {"move_san": m.get("move_san"), "fen_before": m.get("fen_before"), "fen_after": m.get("fen_after"),
            "is_user_move": bool(m.get("is_user_move")), "cp_loss": abs(int(m.get("cp_loss") or 0)),
            "best_move_san": m.get("best_move_san"), "pv_after_best": m.get("pv_after_best") or [],
            "pv_after_played": m.get("pv_after_played") or []}


def do_game(gid, dd):
    moves = [m for m in dd if m.get("move_san") and m.get("fen_before")]
    if not moves:
        return []
    uc = "white"
    for m in moves:
        if m.get("is_user_move"):
            uc = "white" if m.get("is_white") else "black"; break
    lines = []
    for i, m in enumerate(moves, 1):
        who = "STUDENT" if m.get("is_user_move") else "OPPONENT"
        pvp = " ".join((m.get("pv_after_played") or [])[:4]) or "(none)"
        lines.append(f"[{i}] {who}: {m.get('move_san')}  (engine ~{abs(int(m.get('cp_loss') or 0))}cp lost; best {m.get('best_move_san') or '(n/a)'}; then {pvp})")
    prompt = HEAD.format(rating=RATING, color=uc, moves="\n".join(lines), n=len(moves))
    ans = parse(call_llm(prompt))
    out = []
    for i, m in enumerate(moves, 1):
        cap = (ans.get(str(i)) or "").strip()
        if not cap or verify_caption(cap, facts(m)):   # missing or board-false -> drop
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
    print(f"{len(games)} games, 1 Opus call each (whole-game context)", flush=True)
    corpus, records = {}, []
    done = kept = total = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(do_game, gid, dd) for gid, dd in games]
        for fut in as_completed(futs):
            done += 1
            res = fut.result()
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
    print(f"DONE games={done} verified_captions={kept}  types={len(corpus)}", flush=True)


if __name__ == "__main__":
    main()
