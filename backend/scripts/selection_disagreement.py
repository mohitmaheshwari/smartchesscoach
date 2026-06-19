"""P2b data-first: where does the system pick the VISIBLE fact while gold teaches a
TRANSFERABLE principle? Fresh-render the corpus, tag both system + gold captions with
a light concept tagger, and report the disagreement matrix + top transferable-principle
misses with examples. Grounds the teaching-score weights (no blind thresholds).

Env: PMONGO. Usage: python scripts/selection_disagreement.py
"""
import os, sys, json, re, asyncio, collections
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient

# concept tagger — transferable PRINCIPLES vs VISIBLE facts
_PRINCIPLE = {
    "early_queen": r"queen out early|early queen|gets? chased|chase the queen|gain(s|ing)? time on (the|your|his) queen",
    "develop":     r"\bdevelop|bring(s|ing)? .*piece|knights before|new piece into",
    "center":      r"\b(center|centre|central)\b|fight for the cent",
    "king_safety": r"\bcastl|king('s)? saf|king to safety|tuck",
    "principle":   r"\balways\b|every move|good habit|the lesson|scan for|before .*(quiet|moving)",
    "open_file":   r"open file|open .-file|rook behind",
}
_VISIBLE = {
    "capture":  r"\btake|takes|capture|grab|recaptur|wins? the|winning material|free (pawn|piece)",
    "check":    r"\bcheck\b|\+",
    "threat":   r"threaten|attacks the|hits the|eyes the",
    "space":    r"claiming .*space|gain(s|ing)? space|push(es)? the .-pawn",
}


def tag(text):
    t = (text or "").lower()
    for k, rx in _PRINCIPLE.items():
        if re.search(rx, t):
            return ("principle", k)
    for k, rx in _VISIBLE.items():
        if re.search(rx, t):
            return ("visible", k)
    return ("other", "other")


async def main():
    from services import game_decryption_v5_service as v5_mod
    from services.game_decryption_v5_service import generate_game_decryption_v5
    async def _noop(*_a, **_kw): return []
    v5_mod._get_stockfish_candidates = _noop

    recs = [json.loads(l) for l in open("/app/backend/scripts/_gold_records_wg.jsonl", encoding="utf-8")]
    gold = {(r["game"], r.get("move_number"), r["move_san"]): r for r in recs}
    game_ids = list({r["game"] for r in recs})
    db = AsyncIOMotorClient(os.environ["PMONGO"])["chess_coach"]

    n = 0
    matrix = collections.Counter()           # (sys_kind, gold_kind)
    transfer_miss = collections.Counter()    # gold principle the system rendered as visible/other
    examples = collections.defaultdict(list)
    done = 0
    for gid in game_ids:
        game = await db.games.find_one({"game_id": gid}, {"_id": 0})
        analysis = await db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "stockfish_analysis": 1})
        if not game or not analysis:
            continue
        mevals = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
        if not (game.get("pgn") and mevals):
            continue
        fresh = await generate_game_decryption_v5(
            pgn=game.get("pgn"), user_color=(game.get("user_color") or "white").lower(),
            move_evaluations=mevals, user_id=game.get("user_id") or "unknown", db=db)
        for m in fresh:
            g = gold.get((gid, m.get("move_number"), m.get("move_san")))
            if not g:
                continue
            n += 1
            sk, sc = tag(m.get("caption"))
            gk, gc = tag(g["caption"])
            matrix[(sk, gk)] += 1
            # transferable miss: gold taught a principle, system did NOT (visible/other)
            if gk == "principle" and sk != "principle":
                transfer_miss[gc] += 1
                if len(examples[gc]) < 4:
                    examples[gc].append((m.get("move_san"), (m.get("caption") or "")[:60], g["caption"][:80]))
        done += 1
        if done % 25 == 0:
            print(f"  {done}/{len(game_ids)} games, {n} moves", flush=True)

    print(f"\n=== {n} moves ===")
    print("kind matrix (system_kind -> gold_kind):")
    for (sk, gk), c in matrix.most_common():
        print(f"  {c:5}  sys={sk:9} gold={gk}")
    tot_tm = sum(transfer_miss.values())
    print(f"\nTRANSFERABLE-PRINCIPLE MISSES (gold=principle, system!=principle): {tot_tm} ({tot_tm*100//max(1,n)}%)")
    for gc, c in transfer_miss.most_common():
        print(f"  {c:5}  {gc}")
    print("\nexamples:")
    for gc, exs in examples.items():
        print(f"### {gc}")
        for san, sysc, goldc in exs:
            print(f"   [{san}] SYS: {sysc}")
            print(f"           GOLD: {goldc}")
    import os as _os
    print("DONE", flush=True); _os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
