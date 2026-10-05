"""Precompute each player's tactical-eye reading into `user_tactical_eye`.

The opportunity gate runs shape detectors over every position, at roughly a
millisecond each, so a player with twenty thousand observed moves would wait
twenty seconds for a page. This does the work in batch; the endpoint reads what
it stores and says "not measured yet" when there is none.

Safe by default: prints what it would write and writes nothing without --apply.
Idempotent -- re-running overwrites by user_id, so it can be re-run after the
gate or the cuts change. It MUST be re-run after either, because the cuts are
quartiles of the population the gate produced.

    python scripts/compute_tactical_eye.py                 # report only
    python scripts/compute_tactical_eye.py --apply
    python scripts/compute_tactical_eye.py --user-id user_x --apply
"""
import argparse
import asyncio
import collections
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.opportunity_gate import GATE_VERSION  # noqa: E402
from services.two_layer_diagnosis import (  # noqa: E402
    CACHE_COLLECTION,
    CALIBRATED_FOR_GATE,
    compute_for_user,
    diagnose,
)


async def main_async(apply: bool, only_user: str | None) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]

    # The stored cuts only mean anything against the gate that produced them.
    if CALIBRATED_FOR_GATE != GATE_VERSION:
        print("REFUSING: the diagnosis is calibrated for %s but the gate is %s."
              % (CALIBRATED_FOR_GATE, GATE_VERSION))
        print("Re-measure the cuts against the new gate before computing.")
        return 1

    if only_user:
        users = [only_user]
    else:
        users = await db.move_observations.distinct("user_id")
    print("players to compute: %d" % len(users))

    verdicts = collections.Counter()
    drills = collections.Counter()
    written = 0
    for user_id in users:
        try:
            reading = await compute_for_user(db, user_id)
        except Exception as exc:
            verdicts["failed: %s" % type(exc).__name__] += 1
            continue
        if not reading.get("measured"):
            verdicts["no observed moves"] += 1
            continue
        verdict = diagnose(reading["pooled"], reading.get("thinks_long_share"))
        verdicts[verdict["layer"]] += 1
        if verdict["layer"] in ("knowledge", "attention"):
            drills[reading.get("drill_pattern") or "none"] += 1
        if not apply:
            continue
        await db[CACHE_COLLECTION].update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "computed_at": datetime.now(timezone.utc),
                "gate_version": GATE_VERSION,
                "layer": verdict["layer"],
                "because": verdict.get("because"),
                "prescription": verdict.get("prescription"),
                "drill_pattern": reading.get("drill_pattern"),
                "chances": reading["pooled"].get("chances"),
                "judgeable": reading["pooled"].get("judgeable"),
                # `pooled_knowledge` has always returned these and this script
                # has always dropped them, so the chances reading had to
                # recompute a twenty-second scan to learn what was already
                # known. docs/chances_not_games_scope.md
                "took": reading["pooled"].get("took"),
                "by_pattern": reading["pooled"].get("by_pattern"),
            }},
            upsert=True,
        )
        written += 1

    print("\nverdicts:")
    for key, count in verdicts.most_common():
        print("   %-22s %d" % (key, count))
    if drills:
        print("\ndrill chosen: %s" % dict(drills))
    print("\nwritten: %d%s" % (written, "" if apply else "  (dry run)"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--user-id", default=None)
    args = parser.parse_args()
    return asyncio.run(main_async(args.apply, args.user_id))


if __name__ == "__main__":
    raise SystemExit(main())
