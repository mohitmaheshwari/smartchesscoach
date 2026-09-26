"""Re-pick the focuses that recency would name differently.

Part A made the picker rank by what a player is doing lately. It reaches nobody
on its own: `pick_next_focus` returns None at gate 1 while an active focus
exists, and all 53 active focuses were chosen under the lifetime rule. The same
thing happened this morning when three detectors were promoted and reached zero
users -- `scripts/repick_after_promotion.py` is the one-off that cleared it, and
this is the same dance for the same reason.

The 28-day time box would eventually free them, but that is up to four weeks of
coaching a pattern the player has stopped showing.

Retire, then re-pick, in that order -- the picker refuses while an active focus
exists, which is the whole problem.

WHAT IT WILL NOT DO. Only users whose proposed topic DIFFERS from the one they
hold are touched. Rewriting a row to the same topic changes nothing a player
sees and would throw away their lock and progress for no reason.

    python scripts/repick_for_recency_2026_09_26.py            # report only
    python scripts/repick_for_recency_2026_09_26.py --apply
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

import services.primary_weakness_picker as pk  # noqa: E402

RETIRE_REASON = "superseded_by_recency_ranking_2026_09_26"


async def _proposed_topic(db, user_id):
    """What the picker would choose if the slot were free.

    The active-focus gate is neutralised for the duration of the question only.
    Nothing is written and the real gate is restored immediately.
    """
    original = pk._get_active_focus

    async def _free(*_args, **_kwargs):
        return None

    pk._get_active_focus = _free
    try:
        return await pk.pick_next_focus(db, user_id)
    except Exception:
        # Deliberately re-raised. An earlier script in this family returned
        # None here and a working picker looked broken for an hour: a swallowed
        # exception in a diagnostic answers the question wrongly instead of
        # failing.
        raise
    finally:
        pk._get_active_focus = original


async def main_async(apply: bool) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]

    active = await db[pk.COLLECTION].find(
        {"status": "active", "type": {"$ne": "strength"}}
    ).to_list(1000)
    print("active weakness focuses: %d" % len(active))

    movers, same, nothing = [], [], []
    for focus in active:
        current = str(focus.get("topic_key") or "")
        proposed = await _proposed_topic(db, focus.get("user_id"))
        # The winner dict keys the topic as "topic"; the STORED row keys it
        # "topic_key". Reading the wrong one here returned None for every user
        # in an earlier script and made a working picker look broken.
        new_topic = str((proposed or {}).get("topic") or "")
        if not new_topic:
            nothing.append((focus, current, new_topic))
        elif new_topic != current:
            movers.append((focus, current, new_topic))
        else:
            same.append((focus, current, new_topic))

    print("would move to a new topic : %d" % len(movers))
    print("would keep the same topic : %d" % len(same))
    print("picker offers nothing     : %d" % len(nothing))
    swaps = {}
    for _f, cur, new in movers:
        swaps[(cur, new)] = swaps.get((cur, new), 0) + 1
    for (cur, new), n in sorted(swaps.items(), key=lambda kv: -kv[1]):
        print("   %-20s -> %-20s %d" % (cur, new, n))

    if not movers:
        print("\nNobody moves, so nothing is applied. That would mean recency "
              "agrees with the lifetime ranking for every active focus, which "
              "is worth knowing rather than papering over with rewritten rows.")
        return 0
    if not apply:
        print("\nDry run. Re-run with --apply to retire the movers and re-pick.")
        return 0

    now = datetime.now(timezone.utc)
    retired = repicked = 0
    for focus, current, _new in movers:
        await db[pk.COLLECTION].update_one(
            {"_id": focus["_id"]},
            {"$set": {
                "status": RETIRE_REASON,
                "closed_at": now,
                "resolution": RETIRE_REASON,
                # Kept so this is auditable and reversible: what they held, and
                # that no human chose to abandon it.
                "retired_from_topic": current,
                "retired_by": "repick_for_recency_2026_09_26.py",
            }},
        )
        retired += 1
        if await pk.assign_focus(db, focus.get("user_id")):
            repicked += 1

    print("\nretired: %d   re-picked: %d" % (retired, repicked))
    if repicked != retired:
        print("NOTE: %d retired without a replacement. Those users now have no "
              "active focus; assign_focus declined them." % (retired - repicked))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return asyncio.run(main_async(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
