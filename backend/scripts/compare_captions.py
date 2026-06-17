"""Unbiased, verifiable head-to-head: distilled SYSTEM caption vs CLAUDE GOLD, per move,
for a 1000-rated student. Two layers:
  1. OBJECTIVE: narrator_claim_verifier checks every claim in BOTH captions against the
     board (catches captures/tactics/free-pieces/mates that aren't real — lies, either side).
  2. UNBIASED QUALITY: a blind A/B LLM judge (doesn't know which is system vs gold; order
     randomized per move) picks which teaches a 1000 student better.

Env: PMONGO, LLM_EXPOSER_URL, LLM_EXPOSER_KEY
Usage: python scripts/compare_captions.py <game_id>
"""
import os, sys, json, time, urllib.request, random
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, "/app/backend")
import pymongo
from services.narrator_claim_verifier import verify_caption

URL = os.environ["LLM_EXPOSER_URL"].rstrip("/"); KEY = os.environ["LLM_EXPOSER_KEY"]

JUDGE = """You judge two chess coaching captions for a 1000-rated student at ONE position.
Position FEN (before the move): {fen}
Move played: {move} (by {who}).  Engine best move: {best}.  Eval swing: {cp}cp lost.
Engine line after the move: {pvp}

Caption A: "{A}"
Caption B: "{B}"

For a 1000-rated student, which caption is better — clearer, more useful, and FACTUALLY CORRECT (no claim that is false on the board: a capture/threat/fork/"free piece"/mate that does not actually exist, or a wrong square)? Factual correctness outweighs style.
Reply ONLY as JSON: {{"winner":"A"|"B"|"tie","reason":"<=12 words","A_false_claim":"<the false claim, or null>","B_false_claim":"<the false claim, or null>"}}"""


def call_llm(p):
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    for _ in range(2):
        try:
            d = json.dumps({"provider": "claude", "question": p, "timeout_seconds": 120}).encode()
            r = urllib.request.Request(URL + "/ask", data=d, headers=h, method="POST")
            with urllib.request.urlopen(r, timeout=40) as x:
                tid = json.loads(x.read().decode()).get("task_id")
            for _ in range(45):
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


def parse_json(s):
    try:
        i, j = s.index("{"), s.rindex("}")
        return json.loads(s[i:j + 1])
    except Exception:
        return None


def main():
    gid = sys.argv[1]
    db = pymongo.MongoClient(os.environ["PMONGO"])["chess_coach"]
    dd = (db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "decryption_v5_data": 1}) or {}).get("decryption_v5_data") or []
    gold = {f"{r['move_number']}:{r['move_san']}": r.get("caption") for r in db.gold_tester_captions.find({"game_id": gid})}

    rows = []
    for m in dd:
        key = f"{m.get('move_number')}:{m.get('move_san')}"
        sys_cap = (m.get("narrative") or "").strip()
        gold_cap = (gold.get(key) or "").strip()
        if not sys_cap and not gold_cap:
            continue
        rows.append((key, m, sys_cap, gold_cap))

    facts_of = lambda m: {"move_san": m.get("move_san"), "fen_before": m.get("fen_before"), "fen_after": m.get("fen_after"),
                          "is_user_move": bool(m.get("is_user_move")), "cp_loss": abs(int(m.get("cp_loss") or 0)),
                          "best_move_san": m.get("best_move_san"), "pv_after_best": m.get("pv_after_best") or [],
                          "pv_after_played": m.get("pv_after_played") or []}

    def work(item):
        key, m, sys_cap, gold_cap = item
        f = facts_of(m)
        v_sys = verify_caption(sys_cap, f) if sys_cap else []
        v_gold = verify_caption(gold_cap, f) if gold_cap else []
        winner = err_sys = err_gold = None
        reason = ""
        if sys_cap and gold_cap:
            # blind A/B: randomize which is shown as A, seeded by move number for reproducibility
            rnd = random.Random(m.get("move_number", 0) * 31 + len(m.get("move_san", "")))
            a_is_sys = rnd.random() < 0.5
            A, B = (sys_cap, gold_cap) if a_is_sys else (gold_cap, sys_cap)
            who = "the student" if m.get("is_user_move") else "the opponent"
            p = JUDGE.format(fen=f["fen_before"], move=m.get("move_san"), who=who, best=f["best_move_san"] or "(n/a)",
                             cp=f["cp_loss"], pvp=" ".join((f["pv_after_played"])[:5]) or "(none)", A=A, B=B)
            j = parse_json(call_llm(p)) or {}
            w = j.get("winner")
            if w == "A":
                winner = "system" if a_is_sys else "gold"
            elif w == "B":
                winner = "gold" if a_is_sys else "system"
            else:
                winner = "tie"
            reason = (j.get("reason") or "")[:60]
            # map A/B false-claim flags back to system/gold
            fa, fb = j.get("A_false_claim"), j.get("B_false_claim")
            err_sys = (fa if a_is_sys else fb)
            err_gold = (fb if a_is_sys else fa)
            err_sys = err_sys if err_sys and str(err_sys).lower() != "null" else None
            err_gold = err_gold if err_gold and str(err_gold).lower() != "null" else None
        return {"key": key, "move": m.get("move_san"), "is_user": bool(m.get("is_user_move")), "fen": f["fen_before"],
                "winner": winner, "reason": reason, "v_sys": v_sys, "v_gold": v_gold,
                "judge_err_sys": err_sys, "judge_err_gold": err_gold, "sys": sys_cap, "gold": gold_cap}

    out = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(work, it) for it in rows]
        for fut in as_completed(futs):
            out.append(fut.result())
    out.sort(key=lambda r: (int(r["key"].split(":")[0]), 0 if r["is_user"] else 1))

    win = {"system": 0, "gold": 0, "tie": 0, None: 0}
    vt_sys = vt_gold = 0
    verifier_lies = []   # objective: board-verified false claims
    judge_lies = []      # judge-flagged false claims (need eyeball)
    for r in out:
        win[r["winner"]] = win.get(r["winner"], 0) + 1
        vt_sys += len(r["v_sys"]); vt_gold += len(r["v_gold"])
        for side, vs in (("system", r["v_sys"]), ("gold", r["v_gold"])):
            for v in vs:
                verifier_lies.append((r["key"], side, v.get("check"), r["fen"]))
        if r["judge_err_sys"]: judge_lies.append((r["key"], "system", r["judge_err_sys"]))
        if r["judge_err_gold"]: judge_lies.append((r["key"], "gold", r["judge_err_gold"]))

    n = len([r for r in out if r["winner"]])
    print("=" * 70)
    print(f"COMPARISON — {gid}  ({n} moves with both captions; {len(out)} total)")
    print("=" * 70)
    print(f"QUALITY (blind A/B judge, 1000-rated student):")
    print(f"   system wins: {win['system']}   gold wins: {win['gold']}   tie: {win['tie']}")
    print(f"\nFACTUAL (board verifier — objective):")
    print(f"   system false claims: {vt_sys}    gold false claims: {vt_gold}")
    print(f"\n--- BOARD-VERIFIED FALSE CLAIMS (objective lies) ---")
    if not verifier_lies:
        print("   (none on either side)")
    for k, side, chk, fen in verifier_lies:
        print(f"   [{side:6}] {k:10} {chk}   fen={fen[:30]}")
    print(f"\n--- JUDGE-FLAGGED FALSE CLAIMS (eyeball; not board-confirmed) ---")
    if not judge_lies:
        print("   (none)")
    for k, side, claim in judge_lies[:40]:
        print(f"   [{side:6}] {k:10} {claim[:80]}")
    print(f"\n--- PER-MOVE (first 24) ---")
    for r in out[:24]:
        w = {"system": "SYS ", "gold": "GOLD", "tie": "tie ", None: "—   "}[r["winner"]]
        flags = ("S!" if r["v_sys"] else "  ") + ("G!" if r["v_gold"] else "  ")
        print(f"   {r['key']:10} {w} {flags} {r['reason']}")
    # persist full json for follow-up
    with open(f"/app/backend/scripts/_compare_{gid[:8]}.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n(full per-move detail written to _compare_{gid[:8]}.json)")


if __name__ == "__main__":
    main()
