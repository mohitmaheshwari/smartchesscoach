"""Fresh-render the CURRENT V5 pipeline on the corpus games (no DB writes) and
compare the system's served caption vs the Opus gold, tiered by the locked
caption_classifier. Avoids the stale-stored-data trap (feedback_fast_testing_strategy).

Env: PMONGO. Usage: python scripts/fresh_render_compare.py [--skip-stockfish-candidates]
"""
import os, sys, json, asyncio, collections
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
from services.caption_classifier import classifier as C

TEACH = {"HIGH", "MID"}
REC = "/app/backend/scripts/_gold_records_wg.jsonl"


async def main():
    skip_cand = "--skip-stockfish-candidates" in sys.argv
    from services import game_decryption_v5_service as v5_mod
    from services.game_decryption_v5_service import generate_game_decryption_v5
    if skip_cand:
        async def _noop(*_a, **_kw): return []
        v5_mod._get_stockfish_candidates = _noop
        print("[skip-candidates ON]", flush=True)

    recs = [json.loads(l) for l in open(REC, encoding="utf-8")]
    gold = {(r["game"], r.get("move_number"), r["move_san"]): r for r in recs}
    game_ids = list({r["game"] for r in recs})
    db = AsyncIOMotorClient(os.environ["PMONGO"])["chess_coach"]

    n = miss = sys_teach = gold_teach = matched = fallback_sil = 0
    miss_by = collections.Counter(); miss_opp = collections.Counter(); miss_user = collections.Counter()
    miss_rule = collections.Counter()
    detail = []  # per-miss rows for analysis
    done = 0
    for gid in game_ids:
        game = await db.games.find_one({"game_id": gid}, {"_id": 0})
        analysis = await db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "stockfish_analysis": 1})
        if not game or not analysis:
            continue
        pgn = game.get("pgn") or ""
        mevals = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
        if not pgn or not mevals:
            continue
        try:
            fresh = await generate_game_decryption_v5(
                pgn=pgn, user_color=(game.get("user_color") or "white").lower(),
                move_evaluations=mevals, user_id=game.get("user_id") or "unknown", db=db,
            )
        except Exception as exc:
            print(f"  {gid[:12]} FAIL {exc}", flush=True); continue
        for m in fresh:
            key = (gid, m.get("move_number"), m.get("move_san"))
            g = gold.get(key)
            if not g:
                continue
            n += 1
            cap = (m.get("caption") or "").strip()
            tier = m.get("caption_tier") or C.classify_freetext(cap)["tier"]
            sys_t = (tier in TEACH) or bool(m.get("has_teaching_content"))
            gold_t = C.classify_freetext(g["caption"])["tier"] in TEACH
            sys_teach += sys_t; gold_teach += gold_t
            if sys_t and gold_t: matched += 1
            if "R_FALLBACK_no_primary" in (m.get("rule_name") or "") and not cap:
                fallback_sil += 1
            if (not sys_t) and gold_t:
                miss += 1
                side = "opp" if not g["is_user_move"] else "user"
                miss_by[side] += 1
                (miss_opp if side == "opp" else miss_user)[g["type"]] += 1
                rn = (m.get("rule_name") or "").split("→")[-1].strip() or "?"
                miss_rule[rn] += 1
                detail.append({
                    "game": gid, "move_number": m.get("move_number"), "move_san": m.get("move_san"),
                    "is_user_move": g["is_user_move"], "cp_loss": g.get("cp_loss"), "gold_type": g["type"],
                    "rule_name": rn, "sys_caption": cap, "sys_tier": tier,
                    "gold_caption": g["caption"], "gold_tier": C.classify_freetext(g["caption"])["tier"],
                })
        done += 1
        if done % 20 == 0:
            print(f"  {done}/{len(game_ids)} games, {n} moves matched", flush=True)

    print(f"\n=== FRESH RE-RENDER ({done} games, {n} moves) ===")
    print(f"system TEACHES (fresh caption): {sys_teach} ({sys_teach*100//max(1,n)}%)   gold teaches: {gold_teach} ({gold_teach*100//max(1,n)}%)")
    print(f"TRUE MISS (system silent, gold teaches): {miss} ({miss*100//max(1,n)}%)")
    print(f"empty R_FALLBACK_no_primary captions: {fallback_sil} ({fallback_sil*100//max(1,n)}%)")
    print(f"miss split: {dict(miss_by)}")
    print("opp miss by type:")
    for k, v in miss_opp.most_common(10): print(f"  {v:4} {k}")
    print("user miss by type:")
    for k, v in miss_user.most_common(10): print(f"  {v:4} {k}")
    print("miss by rule_name (the silent paths):")
    for k, v in miss_rule.most_common(12): print(f"  {v:4} {k}")
    with open("/app/backend/scripts/_silence_detail.jsonl", "w", encoding="utf-8") as f:
        for d in detail:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"WROTE _silence_detail.jsonl ({len(detail)} miss rows)")


if __name__ == "__main__":
    asyncio.run(main())
