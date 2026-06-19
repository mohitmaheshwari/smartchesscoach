"""P3 check: fresh-render the corpus, count + show the cross-move XMOVE captions
(recurrence / finally), and verify each on the board.

Env: PMONGO. Usage: python scripts/p3_check.py
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
    counts = collections.Counter(); examples = []; viol = 0
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
            if "XMOVE" not in rn:
                continue
            tag = "FINALLY" if "FINALLY" in rn else "AGAIN"
            counts[tag] += 1
            facts = {"move_san": m.get("move_san"), "fen_before": m.get("fen_before"),
                     "fen_after": m.get("fen_after"), "is_user_move": True,
                     "cp_loss": abs(int(m.get("cp_loss") or 0)), "best_move_san": m.get("best_move_san"),
                     "pv_after_played": m.get("pv_after_played") or [], "pv_after_best": m.get("pv_after_best") or []}
            if verify_caption((m.get("caption") or ""), facts):
                viol += 1
            if len(examples) < 14:
                examples.append((tag, m.get("move_san"), (m.get("caption") or "")[:90]))
        done += 1
    print(f"games {done} | XMOVE captions: {dict(counts)} | verifier violations: {viol}")
    for tag, san, cap in examples:
        print(f"  [{tag} {san}] {cap}")
    import os as _os
    print("DONE"); _os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
