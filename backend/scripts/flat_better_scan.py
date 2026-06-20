"""Scan: how many shipped MISTAKE captions name a better move but give NO why
('... was better.' / '... was the stronger move here.') AND have a best_move_principle
we could append. Grounds the R12-path principle-why integration (option 2).

Env: PMONGO. Usage: python scripts/flat_better_scan.py
"""
import os, sys, json, re, asyncio, collections
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient

# "names a better move but stops" — ends right after the better-move phrase, no why
_FLAT = re.compile(
    r"(was better|was the stronger move( here)?|was stronger( here)?|"
    r"was much stronger|was sharper|was the move)\s*\.?\s*$", re.I)


async def main():
    from services import game_decryption_v5_service as v5_mod
    from services.game_decryption_v5_service import generate_game_decryption_v5
    async def _noop(*_a, **_kw): return []
    v5_mod._get_stockfish_candidates = _noop

    recs = [json.loads(l) for l in open("/app/backend/scripts/_gold_records_wg.jsonl", encoding="utf-8")]
    game_ids = list({r["game"] for r in recs})
    db = AsyncIOMotorClient(os.environ["PMONGO"])["chess_coach"]
    flat = 0; flat_with_principle = 0; by_rule = collections.Counter(); exs = []
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
            cap = (m.get("caption") or "").strip()
            if not cap or not _FLAT.search(cap):
                continue
            flat += 1
            rn = (m.get("rule_name") or "").split("→")[0]
            by_rule[rn] += 1
            bp = m.get("best_move_principle")
            if bp:
                flat_with_principle += 1
                if len(exs) < 12:
                    exs.append((bp, cap[:80]))
        done += 1
    print(f"games {done}")
    print(f"FLAT better-move captions (name a move, no why): {flat}")
    print(f"  of those, with a best_move_principle to append: {flat_with_principle}")
    print("by rule:", dict(by_rule))
    print("examples (principle | caption):")
    for bp, cap in exs:
        print(f"  [{bp}] {cap}")
    import os as _os
    print("DONE"); _os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
