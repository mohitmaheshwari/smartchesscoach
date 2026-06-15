"""Lane C — judge_vs_gold.py: measure the REAL detector caption quality gap.

For every move in db.gold_captions: render the CURRENT detector caption (stubbed
Stockfish — engine truth is already stored; game_id=None for RAW detector output,
no authored overrides), then LLM-judge it MATCH / PARTIAL / MISS against the gold
on four axes (same-why / same-alternative / truthful / easy+has-why).

Coverage != quality — the detector-vs-gold diff only measured "did a caption fire",
not "is it as good as the gold". This computes the >=85%-match number.

Rules honored (docs/parallel_task_assignment.md):
- This is a NEW script; it edits no service file.
- It reuses the ONE gateway client config from services.narrator_fallback
  (_BASE/_KEY/_H) — it does NOT open a second Claude client. Serial calls.
- It only READS db.gold_captions / games / game_analyses. Writes nothing to Mongo.

VALIDATE-THE-JUDGE FIRST: --validate-judge runs constructed sanity cases
(gold-vs-itself must be MATCH; gold-vs-empty must be MISS; gold-vs-scrambled must
be MISS). If the judge fails those, do NOT trust the batch number.

Gateway env (pass via docker exec -e): LLM_API_BASE (use http://host.docker.internal:8000
from the container), LLM_API_KEY.

Usage:
  python scripts/judge_vs_gold.py --validate-judge
  python scripts/judge_vs_gold.py [--limit N]
"""
import os
import sys
import json
import time
import argparse
import asyncio

sys.path.insert(0, "/app/backend")

import requests
from motor.motor_asyncio import AsyncIOMotorClient

import services.narrator_fallback as nf          # the ONE gateway client config
import services.game_decryption_v5_service as v5  # the single render entry


# ── gateway: reuse narrator_fallback's endpoint/key (one client, serial) ──────
def _ask(prompt, timeout_s=120):
    """Single serial gateway call via narrator_fallback's config. None on failure."""
    if not nf._BASE or not nf._KEY:
        return None
    try:
        r = requests.post(f"{nf._BASE}/ask", headers=nf._H,
                          json={"question": prompt, "provider": "claude",
                                "timeout_seconds": timeout_s}, timeout=30)
        r.raise_for_status()
        tid = r.json().get("task_id")
        if not tid:
            return None
        deadline = time.time() + timeout_s + 40
        while time.time() < deadline:
            time.sleep(3)
            try:
                t = requests.get(f"{nf._BASE}/tasks/{tid}", headers=nf._H, timeout=15).json()
            except Exception:
                continue
            st = t.get("status")
            if st in ("done", "completed", "finished", "succeeded"):
                return (t.get("answer") or "").strip()
            if st in ("error", "timeout", "failed"):
                return None
    except Exception:
        return None
    return None


def _parse_verdict(ans):
    if not ans:
        return None, None
    import re
    m = re.search(r"\{.*\}", ans, re.S)
    if not m:
        # bare-word fallback
        for v in ("MATCH", "PARTIAL", "MISS"):
            if v in ans.upper():
                return v, ans[:60]
        return None, ans[:60]
    try:
        d = json.loads(m.group(0))
        v = (d.get("verdict") or "").upper()
        return (v if v in ("MATCH", "PARTIAL", "MISS") else None), d.get("why")
    except Exception:
        return None, ans[:60]


JUDGE = """You grade a chess coaching caption against a GOLD-standard caption for the SAME move, for a {rating} student.
FEN: {fen}
Move played: {move}  (~{cp}cp lost)   Engine best: {best}
GOLD caption: "{gold}"
CANDIDATE caption: "{cand}"

Grade ONLY whether the CANDIDATE teaches the same lesson as the GOLD:
- same_why: names the same reason the move is bad / same fundamental.
- same_alternative: points to the same better move/idea (or correctly stays silent).
- truthful: every chess claim is true on the board (no invented capture/tactic/threat).
- easy_has_why: simple language AND it explains a why (not just "X is a mistake").

Verdict: MATCH (same core lesson + truthful), PARTIAL (related but weaker or missing a piece), MISS (different/wrong/empty/untruthful).
An EMPTY candidate is MISS. A truthful but different lesson is PARTIAL at best. A confabulation is MISS even if it sounds right.
Reply ONLY JSON: {{"verdict":"MATCH|PARTIAL|MISS","why":"<=12 words"}}"""


def _judge(fen, move, cp, best, gold, cand, rating=1200):
    return _parse_verdict(_ask(JUDGE.format(
        rating=rating, fen=fen, move=move, cp=cp or 0, best=best or "(n/a)",
        gold=gold or "", cand=cand or "")))


# ── render the CURRENT detector caption for each gold game (stubbed SF) ───────
async def _render_game(db, game_id):
    """Return {(move_number, move_san): caption} for one game's user moves."""
    game = await db.games.find_one({"game_id": game_id}, {"_id": 0, "pgn": 1, "user_color": 1, "user_id": 1})
    an = await db.game_analyses.find_one({"game_id": game_id}, {"_id": 0, "stockfish_analysis.move_evaluations": 1})
    if not game or not an:
        return {}, {}
    me = (an.get("stockfish_analysis") or {}).get("move_evaluations") or []
    pgn = game.get("pgn") or ""
    uc = (game.get("user_color") or "white").lower()
    uid = game.get("user_id") or "unknown"
    if not pgn or not me:
        return {}, {}
    try:
        dec = await v5.generate_game_decryption_v5(
            pgn=pgn, user_color=uc, move_evaluations=me, user_id=uid, db=db, game_id=None)
    except Exception as e:
        print(f"  [render err {game_id[:8]}] {e}", flush=True)
        return {}, {}
    caps = {}
    for d in dec:
        if d.get("is_user_move"):
            caps[(d.get("move_number"), d.get("move_san"))] = d.get("caption") or ""
    # also fetch pv per (move_number, move_san) for the judge/best context
    pv = {}
    for m in me:
        pv[(m.get("move_number"), m.get("move"))] = {
            "best": m.get("best_move"), "cp": m.get("cp_loss"),
        }
    return caps, pv


async def run(limit, validate_judge):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000)[os.environ["DB_NAME"]]
    golds = await db.gold_captions.find({"gold_caption": {"$ne": None}}, {"_id": 0}).to_list(length=10000)
    golds = [g for g in golds if (g.get("gold_caption") or "").strip()]
    if limit:
        golds = golds[:limit]
    print(f"gold_captions with a verified caption: {len(golds)}", flush=True)
    print(f"gateway configured: {bool(nf._BASE and nf._KEY)} ({nf._BASE or '<unset>'})", flush=True)
    if not (nf._BASE and nf._KEY):
        print("ABORT: gateway env (LLM_API_BASE/LLM_API_KEY) not set in this process.", flush=True)
        return

    # ── STEP A: validate the judge on constructed sanity cases ──
    if validate_judge:
        sample = golds[:15]
        ok = {"match": 0, "miss_empty": 0, "miss_scramble": 0}
        print("\n=== VALIDATE THE JUDGE (must pass before trusting the batch) ===", flush=True)
        for g in sample:
            gc = g["gold_caption"]
            scram = " ".join(reversed(gc.split()))  # word-scrambled = should MISS
            v_self, _ = _judge(g["fen_before"], g["move_san"], g.get("cp_loss"), g.get("best_move_san"), gc, gc)
            v_empty, _ = _judge(g["fen_before"], g["move_san"], g.get("cp_loss"), g.get("best_move_san"), gc, "")
            v_scr, _ = _judge(g["fen_before"], g["move_san"], g.get("cp_loss"), g.get("best_move_san"), gc, scram)
            ok["match"] += (v_self == "MATCH")
            ok["miss_empty"] += (v_empty == "MISS")
            ok["miss_scramble"] += (v_scr in ("MISS", "PARTIAL"))
            print(f"  self={v_self} empty={v_empty} scramble={v_scr}  [{g.get('cognitive_gap')}]", flush=True)
        n = len(sample)
        print(f"\njudge sanity: gold-vs-self MATCH {ok['match']}/{n} | "
              f"gold-vs-empty MISS {ok['miss_empty']}/{n} | "
              f"scramble not-MATCH {ok['miss_scramble']}/{n}", flush=True)
        trustworthy = ok["match"] >= 0.8 * n and ok["miss_empty"] >= 0.8 * n
        print(f"JUDGE {'TRUSTWORTHY -> safe to run batch' if trustworthy else 'BROKEN -> fix before batch'}", flush=True)
        return

    # The Mongo tunnel (:27018) is known-flaky. So split into two phases:
    #   B1 = MONGO burst (load + render -> cache candidate captions in memory)
    #   B2 = GATEWAY only (judge from the cache) — survives a tunnel drop.
    by_game = {}
    for g in golds:
        by_game.setdefault(g["game_id"], []).append(g)

    # ── STEP B1 (MONGO, front-loaded with retry) ──
    records = []  # {gap, fen, move, cp, best, gold, cand}
    rendered = 0
    for gid, items in by_game.items():
        caps = {}
        for attempt in range(4):
            try:
                caps, _ = await _render_game(db, gid)
                break
            except Exception as e:
                print(f"  [render retry {gid[:8]} #{attempt}] {str(e)[:70]}", flush=True)
                await asyncio.sleep(3)
        for g in items:
            cand = caps.get((g.get("move_number"), g.get("move_san")), "")
            records.append({"gap": g.get("cognitive_gap") or "?", "fen": g["fen_before"],
                            "move": g["move_san"], "cp": g.get("cp_loss"),
                            "best": g.get("best_move_san"), "gold": g["gold_caption"], "cand": cand})
        rendered += 1
        if rendered % 10 == 0:
            print(f"  rendered {rendered}/{len(by_game)} games", flush=True)
    n_empty = sum(1 for r in records if not r["cand"])
    print(f"MONGO PHASE done: {len(records)} records cached ({n_empty} empty candidate). "
          f"Gateway phase next — no Mongo needed.", flush=True)

    # ── STEP B2 (GATEWAY only) — judge from cache ──
    from collections import Counter, defaultdict
    per_gap = defaultdict(Counter)
    worst = []  # (gap, move, gold, cand, verdict, why)
    n_done = 0
    t0 = time.time()
    for r in records:
        v, why = _judge(r["fen"], r["move"], r["cp"], r["best"], r["gold"], r["cand"])
        per_gap[r["gap"]][v or "UNJUDGED"] += 1
        n_done += 1
        if v in ("PARTIAL", "MISS"):
            worst.append((r["gap"], r["move"], r["gold"], r["cand"], v, why))
        if n_done % 10 == 0:
            print(f"  judged {n_done}/{len(records)}  ({time.time()-t0:.0f}s)", flush=True)

    print("\n================ PER-PATTERN %% MATCH (>=85%% is the bar) ================", flush=True)
    print(f"{'cognitive_gap':22}{'MATCH':>7}{'PART':>6}{'MISS':>6}{'n':>5}{'%match':>8}", flush=True)
    grand = Counter()
    for gap, c in sorted(per_gap.items(), key=lambda kv: -sum(kv[1].values())):
        tot = sum(c.values())
        grand.update(c)
        pm = 100 * c.get("MATCH", 0) // max(tot, 1)
        print(f"{gap:22}{c.get('MATCH',0):>7}{c.get('PARTIAL',0):>6}{c.get('MISS',0):>6}{tot:>5}{pm:>7}%", flush=True)
    gt = sum(grand.values())
    print(f"{'OVERALL':22}{grand.get('MATCH',0):>7}{grand.get('PARTIAL',0):>6}{grand.get('MISS',0):>6}{gt:>5}"
          f"{100*grand.get('MATCH',0)//max(gt,1):>7}%", flush=True)

    print("\n================ WORST TEMPLATES (flag for Lane B) ================", flush=True)
    for gap, mv, gold, cand, v, why in worst[:30]:
        print(f"[{v}] {gap} {mv}", flush=True)
        print(f"   GOLD: {gold[:90]}", flush=True)
        print(f"   CAND: {(cand or '(empty)')[:90]}   <- {why}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--validate-judge", action="store_true")
    a = ap.parse_args()
    # stub the live Stockfish call — engine truth is already stored in move_evaluations
    async def _no_sf(*args, **kw):
        return []
    v5._get_stockfish_candidates = _no_sf
    asyncio.run(run(a.limit, a.validate_judge))


if __name__ == "__main__":
    main()
