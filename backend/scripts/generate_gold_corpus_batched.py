"""Batched easy-English Opus gold corpus for the consequence-detector teaching run.
Sends N positions per Opus call (amortizes the Claude-Code per-call overhead -> ~5-6x
cheaper than one-call-per-caption). Each caption is engine-VERIFIED; unverified ones
are dropped (the mining corpus needs clean examples, not 100% coverage).

Outputs:
  _gold_corpus_batched.json    {move_type: [captions]}  (for snippet mining)
  _gold_records.jsonl          per-move records (game, move, fen, pv, cp, caption) for consequence-mining

Env: PMONGO, LLM_EXPOSER_URL, LLM_EXPOSER_KEY
Usage: python scripts/generate_gold_corpus_batched.py <gid...>   [--batch N]
"""
import os, sys, json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, "/app/backend"); sys.path.insert(0, "/app/backend/scripts")
import pymongo
from services.narrator_claim_verifier import verify_caption
from group_gold_by_type import move_type

URL = os.environ["LLM_EXPOSER_URL"].rstrip("/"); KEY = os.environ["LLM_EXPOSER_KEY"]
RATING = 1000
BATCH = 8

HEAD = """You are a kind chess coach writing SHORT captions in VERY EASY English for a {rating}-rated student (basic English, short sentences, no chess jargon — say it plainly). For each position: a STUDENT move = say what it does, or if it is a mistake the better move + a one-line why; an OPPONENT move = what it means for the student and what the student should do. End each with one short simple lesson. TRUTH: only state a capture/threat/fork/check if it is really true in the engine line; never say "free" unless the piece is truly undefended.

Here are {n} chess positions. Write ONE caption for each number.

{items}

Return ONLY JSON, a caption for EVERY number: {{"1":"...","2":"...", ... ,"{n}":"..."}}"""


def side(f):
    return "White" if f.split(" ")[1] == "w" else "Black"


def call_llm(p):
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    for _ in range(2):
        try:
            d = json.dumps({"provider": "claude", "question": p, "timeout_seconds": 200}).encode()
            r = urllib.request.Request(URL + "/ask", data=d, headers=h, method="POST")
            with urllib.request.urlopen(r, timeout=40) as x:
                tid = json.loads(x.read().decode()).get("task_id")
            for _ in range(70):
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


def do_batch(items):
    """items: list of (record). Returns list of (record, caption, type) for VERIFIED ones."""
    lines = []
    for i, m in enumerate(items, 1):
        who = "STUDENT" if m.get("is_user_move") else "OPPONENT"
        pvp = " ".join((m.get("pv_after_played") or [])[:5]) or "(none)"
        lines.append(f"[{i}] {who} move {m.get('move_san')} ({side(m['fen_before'])} to move). FEN: {m['fen_before']}. "
                     f"Best: {m.get('best_move_san') or '(n/a)'}. Line after played: {pvp}. (engine ~{abs(int(m.get('cp_loss') or 0))}cp lost)")
    prompt = HEAD.format(rating=RATING, n=len(items), items="\n".join(lines))
    ans = parse(call_llm(prompt))
    out = []
    for i, m in enumerate(items, 1):
        cap = (ans.get(str(i)) or "").strip()
        if not cap:
            continue
        if verify_caption(cap, facts(m)):   # board-false claim -> drop
            continue
        out.append((m, cap, move_type(m)))
    return out


def main():
    gids = [a for a in sys.argv[1:] if not a.startswith("-")]
    global BATCH
    if "--batch" in sys.argv:
        BATCH = int(sys.argv[sys.argv.index("--batch") + 1])
    db = pymongo.MongoClient(os.environ["PMONGO"])["chess_coach"]
    moves = []
    for gid in gids:
        dd = (db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "decryption_v5_data": 1}) or {}).get("decryption_v5_data") or []
        for m in dd:
            if m.get("move_san") and m.get("fen_before"):
                m["_gid"] = gid
                moves.append(m)
    batches = [moves[i:i + BATCH] for i in range(0, len(moves), BATCH)]
    print(f"{len(gids)} games, {len(moves)} moves, {len(batches)} batches of {BATCH}", flush=True)

    corpus, records = {}, []
    done = kept = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(do_batch, b) for b in batches]
        for fut in as_completed(futs):
            done += 1
            for m, cap, t in fut.result():
                kept += 1
                corpus.setdefault(t, []).append(cap)
                records.append({"game": m["_gid"], "move_number": m.get("move_number"), "move_san": m.get("move_san"),
                                "fen_before": m.get("fen_before"), "fen_after": m.get("fen_after"),
                                "is_user_move": bool(m.get("is_user_move")), "cp_loss": abs(int(m.get("cp_loss") or 0)),
                                "pv_after_played": m.get("pv_after_played") or [], "type": t, "caption": cap})
            if done % 10 == 0:
                print(f"  {done}/{len(batches)} batches, {kept} verified captions", flush=True)
    with open("/app/backend/scripts/_gold_corpus_batched.json", "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1)
    with open("/app/backend/scripts/_gold_records.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"DONE kept={kept}/{len(moves)} verified  types={len(corpus)}", flush=True)
    for t in sorted(corpus, key=lambda x: -len(corpus[x]))[:12]:
        print(f"  {t:24} {len(corpus[t])}")


if __name__ == "__main__":
    main()
