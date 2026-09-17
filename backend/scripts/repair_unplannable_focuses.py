"""Retire active focuses nothing can act on, and re-pick.

Measured on production 2026-09-17: of 54 active weakness focuses, 11 were
refused by the plan-surface gate. Every one of those 11 accounts had analysed
games, and every one was being shown the Home page for a player the coach has
never seen -- "I'm still learning how you play. Play a game or two" -- to
people with between 12 and 731 analysed games.

Two ways a row gets into that state, and both are here:

  unstamped   Written before the picker stamped detector_quality_id (which
              landed 2026-08-29). `focus_document_is_authorized` sees no
              quality id and, with enforcement on, refuses. 10 rows.

  shadow      Stamped correctly, but the detector behind the topic is graded
              `shadow`, not `plan`. The picker chose a topic it was not
              allowed to coach from. 1 row, `gap:threat_awareness:*`. The
              cause is fixed in primary_weakness_picker (it now filters
              candidates through detector_quality.topic_can_be_planned); this
              script clears the rows that predate that fix.

Retire, then re-pick, in that order: `pick_next_focus` refuses while an
active focus exists, so the old row has to be closed first. A user with no
plannable evidence gets no new focus and is reported, rather than being left
with a broken one.

    python scripts/repair_unplannable_focuses.py            # report only
    python scripts/repair_unplannable_focuses.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

RETIRED_STATUS = "closed_detector_not_plannable"


async def main(apply: bool) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")
    ]
    from services.detector_quality import (
        focus_document_is_authorized,
        quality_id_for_focus_document,
    )
    from services.focus_bridge import ACTIVE_WEAKNESS_FILTER, COLLECTION
    from services.primary_weakness_picker import assign_focus

    rows = await db[COLLECTION].find(ACTIVE_WEAKNESS_FILTER, {"_id": 0}).to_list(5000)
    broken = [r for r in rows if not focus_document_is_authorized(r)]
    print(f"active weakness focuses: {len(rows)}")
    print(f"  refused by the plan gate: {len(broken)}")
    if not broken:
        return 0

    repaired, stranded, failed = [], [], []
    for row in broken:
        user_id = row["user_id"]
        games = await db.games.count_documents(
            {"user_id": user_id, "is_analyzed": True}
        )
        reason = "unstamped" if not quality_id_for_focus_document(row) else "shadow"
        print(f"\n  {user_id}  topic={row.get('topic_key')}  games={games}  ({reason})")

        if not apply:
            print("    would retire and re-pick")
            continue

        # Retire first: the picker will not assign while one is active.
        result = await db[COLLECTION].update_one(
            {"user_id": user_id, "topic_key": row.get("topic_key"),
             "status": "active"},
            {"$set": {
                "status": RETIRED_STATUS,
                "resolution": "detector_not_authorized_for_plan",
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        if not result.modified_count:
            print("    SKIPPED: row changed under us")
            failed.append(user_id)
            continue

        try:
            fresh = await assign_focus(db, user_id)
        except Exception as exc:
            print(f"    re-pick FAILED: {type(exc).__name__}: {exc}")
            failed.append(user_id)
            continue

        if not fresh:
            print("    retired; no plannable focus available yet")
            stranded.append(user_id)
            continue

        ok = focus_document_is_authorized(fresh)
        print(f"    -> {fresh.get('topic_key')} "
              f"({fresh.get('detector_quality_grade')}) authorized={ok}")
        (repaired if ok else failed).append(user_id)

    print(f"\nrepaired {len(repaired)}  stranded {len(stranded)}  failed {len(failed)}")
    if stranded:
        print("  stranded users have no plan-graded evidence yet; the Home page "
              "must not tell them the coach has never seen them play.")
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.apply)))
