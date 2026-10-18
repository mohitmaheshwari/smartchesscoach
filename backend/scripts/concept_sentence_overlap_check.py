"""Does the concept sentence repeat what the caption already said?

`good_rook_open_file` and `good_luft` already exist in the distilled caption
corpus, and concept_rook_open_file was promoted this morning. If both land on
the same move the player reads one idea twice -- the same redundancy the home
page had, and the thing the single-source-of-truth rule exists to prevent.

Renders real reviews and reports, for every move carrying a concept sentence,
which rule wrote the main caption.
"""
import asyncio
import collections
import os
import sys

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient

from services.game_decryption_v5_service import generate_game_decryption_v5

N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
# Caption rules that say the same thing one of the promoted detectors says.
# Independent of the guard on purpose. The first version of this script
# shared its needle list WITH the guard, so "0 clashes" only proved the guard
# covered what the detector looked for. These are the concept keys the gold
# caption corpus actually authors, so a clash is found whether or not the
# guard knows about it.
CORPUS_CONCEPT_KEYS = (
    "good_develop", "good_castle", "good_centralize", "good_rook_open_file",
    "good_rook_activity", "good_luft", "good_pawn", "good_space",
    "good_capture_free", "good_queen_safety", "good_trade", "good_other",
    "center", "centre", "develop", "castl", "centrali", "rook", "pawn_break",
)
SAME_IDEA = {}


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
    games = []
    async for g in db.games.aggregate([
        {"$match": {"is_analyzed": True, "pgn": {"$nin": [None, ""]}}},
        {"$sample": {"size": N}},
        {"$project": {"_id": 0, "game_id": 1, "user_id": 1, "pgn": 1, "user_color": 1}},
    ]):
        games.append(g)

    rules = collections.Counter()
    clashes = []
    total = 0
    for g in games:
        a = await db.game_analyses.find_one(
            {"game_id": g["game_id"]},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1})
        evs = ((a or {}).get("stockfish_analysis") or {}).get("move_evaluations") or []
        if not evs:
            continue
        try:
            out = await generate_game_decryption_v5(
                g["pgn"], g.get("user_color") or "white", evs,
                g.get("user_id") or "u", db, game_id=g["game_id"],
                persist_learning_side_effects=False, allow_llm_polish=False)
        except Exception:
            continue
        moves = out if isinstance(out, list) else ((out or {}).get("moves") or [])
        for m in moves:
            if not isinstance(m, dict):
                continue
            cs = m.get("concept_sentence")
            if not cs:
                continue
            total += 1
            rule = str(m.get("rule_name") or "(none)")
            rules[rule] += 1
            low = rule.lower()
            if any(n in low for n in CORPUS_CONCEPT_KEYS):
                if len(clashes) < 8:
                    clashes.append((g["game_id"][:10], m.get("move_number"),
                                    m.get("move_san") or m.get("move"), rule,
                                    cs["skill_id"], (m.get("caption") or "")[:110],
                                    cs["text"][:110]))

    print("moves carrying a concept sentence: %d\n" % total)
    print("the rule that wrote the MAIN caption on those moves:")
    for r, n in rules.most_common(14):
        print("   %-44s %d" % (r, n))
    print("\nSAME IDEA SAID TWICE: %d" % len(clashes))
    for gid, mn, san, rule, sid, cap, txt in clashes:
        print("   %s m%s %s   rule=%s + %s" % (gid, mn, san, rule, sid))
        print("      caption : %s" % cap)
        print("      concept : %s" % txt)


asyncio.run(main())
