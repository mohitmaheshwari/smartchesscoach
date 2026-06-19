"""Run the per-FEN claim verifier on every Tier-2/3 (R_TIER*) fallback caption the
current pipeline renders across the corpus. Defense-in-depth: the rendered TEXT must
verify on the board, not just trust the facts it was built from (right-or-silent).

Env: PMONGO. Usage: python scripts/verify_tier_captions.py [--skip-stockfish-candidates]
"""
import os, sys, json, asyncio, collections
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
from services.narrator_claim_verifier import verify_caption


async def main():
    from services import game_decryption_v5_service as v5_mod
    from services.game_decryption_v5_service import generate_game_decryption_v5
    async def _noop(*_a, **_kw): return []
    v5_mod._get_stockfish_candidates = _noop

    recs = [json.loads(l) for l in open("/app/backend/scripts/_gold_records_wg.jsonl", encoding="utf-8")]
    game_ids = list({r["game"] for r in recs})
    db = AsyncIOMotorClient(os.environ["PMONGO"])["chess_coach"]

    n_tier = 0
    viol = []
    rule_counts = collections.Counter()
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
            rn = m.get("rule_name") or ""
            if "R_TIER" not in rn:
                continue
            n_tier += 1
            rule_counts[rn.split("→")[-1]] += 1
            cap = (m.get("caption") or "").strip()
            facts = {
                "move_san": m.get("move_san"), "fen_before": m.get("fen_before"),
                "fen_after": m.get("fen_after"), "is_user_move": bool(m.get("is_user_move")),
                "cp_loss": abs(int(m.get("cp_loss") or 0)), "best_move_san": m.get("best_move_san"),
                "pv_after_played": m.get("pv_after_played") or [], "pv_after_best": m.get("pv_after_best") or [],
            }
            try:
                v = verify_caption(cap, facts)
            except Exception as exc:
                v = [{"check": "verifier_error", "detail": str(exc)}]
            if v:
                viol.append((gid, m.get("move_number"), m.get("move_san"), rn.split("→")[-1], cap, v))
        done += 1
        if done % 20 == 0:
            print(f"  {done}/{len(game_ids)} games, {n_tier} tier captions, {len(viol)} violations", flush=True)

    print(f"\n=== VERIFIER on Tier captions ===")
    print(f"tier captions checked: {n_tier}")
    print(f"VIOLATIONS: {len(viol)} ({len(viol)*100//max(1,n_tier)}%)")
    print("by rule:", dict(rule_counts))
    print("\nviolation samples:")
    for gid, mn, san, rule, cap, v in viol[:25]:
        print(f"  [{rule} {san}] {v[0].get('check')}: {cap[:70]}")
        print(f"     -> {v[0].get('detail','')[:90]}")
    import os as _os
    print("DONE", flush=True)
    _os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
