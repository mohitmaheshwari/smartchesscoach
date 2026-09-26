"""Recompute the 557 `tempo_wasted_by_repeat` rows through the repaired gates.

That subtype claimed the player had "lost a tempo by moving the same piece
twice". The claim was vacuous (true of 557 of 557 fires, and never computed)
and the accusation was false in 43.1% of them, where the engine's own best
move moves that same piece. See
docs/opening_knowledge_promotion_finding_2026_09_26.md.

The rows are re-derived by the REAL classifier rather than by a copy of its
rules here, so this cannot drift from what the deriver would write today.
Expect roughly 154 to become `retreated_a_developed_piece` and the rest to
fall to `unverified_hint` or to nothing.

RUN THIS AFTER THE CODE IS DEPLOYED, never before. Writing a subtype the
running code does not recognise silently drops those rows out of every pool
that filters on authorized subtypes.

Only `subtype` is rewritten. `missed_pattern` is left alone, so the migration
stays narrow and reversible: the previous value is kept on each row as
`subtype_before_2026_09_26`.

    python scripts/rename_tempo_subtype_2026_09_26.py            # report only
    python scripts/rename_tempo_subtype_2026_09_26.py --apply
"""
import argparse
import asyncio
import collections
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.cognitive_gap_subtypes import classify_opening_knowledge  # noqa: E402

OLD_SUBTYPE = "tempo_wasted_by_repeat"


async def main_async(apply: bool) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]

    rows = await db.move_observations.find(
        {"missed_pattern": "opening_knowledge", "subtype": OLD_SUBTYPE},
        {"_id": 1, "game_id": 1, "fen_before": 1, "move_uci": 1,
         "move_san": 1, "cp_loss": 1, "move_number": 1},
    ).to_list(5000)
    print("rows carrying %s: %d" % (OLD_SUBTYPE, len(rows)))
    if not rows:
        print("nothing to do")
        return 0

    # The engine's best move is the gate, and it lives in game_analyses.
    # Joined on fen_before: move_evaluations has no usable ply, and its
    # move_number counts the USER's moves (1, 2, 3 for a black player's
    # first three), so joining on that would misalign every row silently.
    game_ids = list({r["game_id"] for r in rows if r.get("game_id")})
    best = {}
    async for doc in db.game_analyses.find(
        {"game_id": {"$in": game_ids}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ):
        for m in ((doc.get("stockfish_analysis") or {}).get(
                "move_evaluations") or []):
            if m.get("fen_before"):
                best[(doc["game_id"], m["fen_before"])] = m

    outcome = collections.Counter()
    plan = []
    for row in rows:
        mv = dict(best.get((row.get("game_id"), row.get("fen_before"))) or {})
        if not mv:
            # No engine row to re-derive from. Leave it exactly as it is
            # rather than guessing; it stays shadow either way.
            outcome["left_alone_no_engine_row"] += 1
            continue
        mv.setdefault("fen_before", row.get("fen_before"))
        mv.setdefault("move_uci", row.get("move_uci"))
        mv.setdefault("move", row.get("move_san"))
        mv.setdefault("cp_loss", row.get("cp_loss"))
        mv.setdefault("move_number", row.get("move_number"))
        new_subtype, _severity = classify_opening_knowledge(mv, None, None)
        outcome[str(new_subtype)] += 1
        plan.append((row["_id"], new_subtype))

    print("\nrecomputed:")
    for k, n in outcome.most_common():
        print("   %-34s %5d" % (k, n))

    if not apply:
        print("\nDry run. Re-run with --apply.")
        return 0

    changed = 0
    for _id, new_subtype in plan:
        await db.move_observations.update_one(
            {"_id": _id},
            {"$set": {"subtype": new_subtype,
                      "subtype_before_2026_09_26": OLD_SUBTYPE}},
        )
        changed += 1
    print("\nrewritten: %d" % changed)

    left = await db.move_observations.count_documents(
        {"missed_pattern": "opening_knowledge", "subtype": OLD_SUBTYPE})
    print("still carrying the old subtype: %d (expected: the no-engine-row rows)"
          % left)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return asyncio.run(main_async(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
