"""One-time cleanup: un-tag community_puzzles mislabeled as endgame_rule_of_square.

Generic endgame_technique mistakes were being tagged as the rule-of-the-square
skill, so the drill served rook/queen/knight endings and multi-pawn messes.
This uses the engine-validated is_rule_of_square_relevant() (concept-accurate:
the king's square must be what decides the pawn's fate) to KEEP only genuine
rule-of-square positions and $unset skill_id on the rest — they remain as
generic community puzzles, just not in this skill drill.

Run (inside the backend container):
  python scripts/cleanup_rule_of_square_pool.py            # dry-run (no writes)
  python scripts/cleanup_rule_of_square_pool.py --apply    # perform the un-tag
"""
import os
import sys
import asyncio
import shutil

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
import chess.engine  # noqa: E402
from services.endgame_detectors.rule_of_square_detector import is_rule_of_square_relevant  # noqa: E402

SKILL = "endgame_rule_of_square"


def _open_engine():
    sf = os.environ.get("STOCKFISH_PATH") or shutil.which("stockfish") or "/usr/games/stockfish"
    return chess.engine.SimpleEngine.popen_uci(sf)


async def main(apply: bool):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"]).get_database(
        os.environ.get("DB_NAME", "chess_coach"))
    rows = await db.community_puzzles.find(
        {"skill_id": SKILL}, {"fen": 1}).to_list(length=10000)

    eng = _open_engine()
    keep_ids, drop_ids, keep_fens = [], [], []
    try:
        for r in rows:
            fen = r.get("fen", "")
            if is_rule_of_square_relevant(fen, eng):
                keep_ids.append(r["_id"])
                keep_fens.append(fen)
            else:
                drop_ids.append(r["_id"])
    finally:
        eng.quit()

    print(f"total tagged {SKILL}: {len(rows)}")
    print(f"  KEEP (genuine rule-of-square): {len(keep_ids)}")
    print(f"  DROP (mislabeled):             {len(drop_ids)}")
    print("  sample KEEP fens:")
    for f in keep_fens[:8]:
        print(f"     {f}")

    if not apply:
        print("\nDRY RUN — no changes written. Re-run with --apply to un-tag the DROP rows.")
        return

    if drop_ids:
        res = await db.community_puzzles.update_many(
            {"_id": {"$in": drop_ids}}, {"$unset": {"skill_id": ""}})
        print(f"\nAPPLIED: un-tagged {res.modified_count} mislabeled rows.")
    remaining = await db.community_puzzles.count_documents({"skill_id": SKILL})
    print(f"remaining tagged {SKILL}: {remaining}")


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
