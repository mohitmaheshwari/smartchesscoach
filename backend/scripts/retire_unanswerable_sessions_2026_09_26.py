"""Close lesson sessions pinned on a position nobody can answer.

The lesson prints "play a move that leaves nothing of yours hanging", and
correctness is exactly
`grade_destination_safety_candidate(fen, move).status == "pass"`. That grader
returns `piece_not_eligible` for every pawn and king move, so a position whose
only legal replies are pawn or king moves cannot be answered correctly by
anyone. Measured 2026-09-26: 92 of 3,000 positions in the served pool, 3.1%.

`personalized_lesson_adapter` now refuses to BUILD a lesson around one. That
does nothing for a session that already holds one, because a session resumes
while its status is active or paused -- the adapter is never asked again. So
the learner stays pinned on a question they cannot answer, for good. This is
the one-off that releases them.

Retiring the session is the whole repair: the next start builds a fresh one
through the filter. Nothing about the learner's history is touched.

    python scripts/retire_unanswerable_sessions_2026_09_26.py            # report
    python scripts/retire_unanswerable_sessions_2026_09_26.py --apply
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import chess  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.destination_safety_detector import (  # noqa: E402
    grade_destination_safety_candidate,
)
from services.lesson_question_spec import ANY_SAFE  # noqa: E402

RETIRED_STATUS = "retired_unanswerable_item_2026_09_26"


def _current_item(session):
    """The item the learner is actually looking at.

    Items live inside `descriptor`, not in a top-level `items` field. Reading
    the top-level one returns an empty list for every personalized session,
    which would report a clean zero and repair nobody.
    """
    descriptor = session.get("descriptor") or {}
    items = descriptor.get("items") or []
    index = int(session.get("current_index") or 0)
    return items[index] if 0 <= index < len(items) else None


def _is_unanswerable(item):
    if not item:
        return False
    if str(item.get("accepts") or item.get("_accepts") or "") != ANY_SAFE:
        return False
    fen = item.get("fen")
    if not fen:
        return False
    try:
        board = chess.Board(fen)
    except Exception:
        return False
    for move in board.legal_moves:
        try:
            if str(grade_destination_safety_candidate(
                    fen, move.uci()).get("status")) == "pass":
                return False
        except Exception:
            continue
    return True


async def main_async(apply: bool) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]

    sessions = await db.learning_sessions.find(
        {"status": {"$in": ["active", "paused"]}}
    ).to_list(5000)
    print("resumable lesson sessions: %d" % len(sessions))

    with_item = 0
    stuck = []
    for session in sessions:
        item = _current_item(session)
        if item and item.get("fen"):
            with_item += 1
        if _is_unanswerable(item):
            stuck.append(session)

    print("holding a position         : %d" % with_item)
    print("PINNED on an unanswerable one: %d" % len(stuck))
    print("distinct users             : %d"
          % len({s.get("user_id") for s in stuck}))
    for session in stuck[:20]:
        item = _current_item(session) or {}
        print("   %-22s %s" % (session.get("user_id"), item.get("fen")))

    if not stuck:
        print("\nNobody is pinned. Nothing to do.")
        return 0
    if not apply:
        print("\nDry run. Re-run with --apply to retire these sessions.")
        return 0

    now = datetime.now(timezone.utc)
    for session in stuck:
        await db.learning_sessions.update_one(
            {"_id": session["_id"]},
            {"$set": {
                "status": RETIRED_STATUS,
                "updated_at": now,
                # Kept so this is auditable and reversible: what they were
                # stuck on, and that no human chose to abandon it.
                "retired_reason": "printed question admitted no correct answer",
                "retired_by": "retire_unanswerable_sessions_2026_09_26.py",
            }},
        )
    print("\nretired: %d   (the next start builds a fresh, filtered lesson)"
          % len(stuck))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return asyncio.run(main_async(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
