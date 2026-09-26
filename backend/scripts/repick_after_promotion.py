"""Retire focuses picked under the one-topic regime, so promotion can land.

Mohit approved promoting three detectors on 2026-09-26. It reached ZERO
users: 52 of 52 active weakness focuses still held piece_safety, none picked
after the promotion. pick_next_focus returns None at gate 1 while an active
focus exists, so the widened menu was never shown to anybody holding a plate.

The time box in close_focus stops this recurring. It does not help the 52 who
are already stuck, because their next outcome check is up to 28 days away.
This is the one-off that clears them.

Retire, then re-pick, in that order -- pick_next_focus refuses while an
active focus exists, which is the whole problem. Modelled on
repair_unplannable_focuses.py, which does the same dance for a different
reason.

WHAT IT WILL NOT DO. If the dry run shows nobody moves to a different topic,
it applies nothing and says so. That result would mean the promotion bought
nothing real, which is worth knowing rather than papering over with 52
rewritten rows that all say piece_safety again.

    python scripts/repick_after_promotion.py            # report only
    python scripts/repick_after_promotion.py --apply
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

RETIRE_REASON = "superseded_by_detector_promotion_2026_09_26"


async def _proposed_topic(db, user_id):
    """What the picker would choose if the slot were free.

    The active-focus gate is neutralised for the duration of the question
    only. Nothing is written, and the real gate is restored immediately.
    """
    original = pk._get_active_focus

    async def _free(*_args, **_kwargs):
        return None

    pk._get_active_focus = _free
    try:
        return await pk.pick_next_focus(db, user_id)
    except Exception:
        # Deliberately re-raised rather than swallowed. An earlier version
        # returned None here, and a working picker looked like a broken one
        # for an hour. A swallowed exception in a diagnostic is worse than a
        # crash, because it answers the question wrongly instead of failing.
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

    plan = []
    for focus in active:
        user_id = focus.get("user_id")
        current = str(focus.get("topic_key") or "")
        proposed = await _proposed_topic(db, user_id)
        # The winner dict from pick_next_focus keys the topic as "topic".
        # Reading "topic_key" here (the STORED row's key) silently returned
        # None for every user and made a working picker look broken.
        new_topic = str((proposed or {}).get("topic")
                        or (proposed or {}).get("topic_key") or "")
        plan.append((focus, current, new_topic))

    movers = [p for p in plan if p[2] and p[2] != p[1]]
    same = [p for p in plan if p[2] and p[2] == p[1]]
    nothing = [p for p in plan if not p[2]]

    print("would move to a new topic : %d" % len(movers))
    print("would keep the same topic : %d" % len(same))
    print("picker offers nothing     : %d" % len(nothing))
    moves = {}
    for _f, cur, new in movers:
        moves[(cur, new)] = moves.get((cur, new), 0) + 1
    for (cur, new), n in sorted(moves.items(), key=lambda kv: -kv[1]):
        print("   %-20s -> %-20s %d" % (cur, new, n))

    if not movers:
        print("\nNobody moves. Applying would rewrite 52 rows to the same "
              "topic and change nothing a user sees, so this stops here. "
              "Promotion did not buy a different focus for anyone.")
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
                # Kept so this is reversible and auditable: what they held,
                # and that a human did not choose to abandon it.
                "retired_from_topic": current,
                "retired_by": "repick_after_promotion.py",
            }},
        )
        retired += 1
        if await pk.assign_focus(db, focus.get("user_id")):
            repicked += 1

    print("\nretired: %d   re-picked: %d" % (retired, repicked))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return asyncio.run(main_async(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
