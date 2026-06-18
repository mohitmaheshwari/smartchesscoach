#!/usr/bin/env python3
"""
Apply authoring submissions from feedback items.
Creates authored_caption_overrides entries for position-specific captions.

Usage:
  docker exec chess-coach-backend python scripts/apply_authoring_submissions.py
"""

import os
import json
from pymongo import MongoClient
from datetime import datetime, timezone
from uuid import uuid4

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

# Authoring submissions from triage (21 items)
SUBMISSIONS = [
    # Batch 1 (8 authoring submissions)
    {
        "feedback_id": "fb_88e2930b64db",
        "game_id": "33769172-e5ee-46dd-92fc-1d2467d57c49",
        "move_san": "Re1",
        "issue": "Says can't be silent but actually takes up open file",
        "caption": "Re1 takes the open file, controlling the king's escape route."
    },
    {
        "feedback_id": "fb_9eb0d495f31d",
        "game_id": "33769172-e5ee-46dd-92fc-1d2467d57c49",
        "move_san": "Bd3",
        "issue": "How does c4 win the rook?",
        "caption": "Bd3 is an inaccuracy. c4 was better because it wins the rook on d4 (after Bxc4, your rook captures it)."
    },
    {
        "feedback_id": "fb_c8a0ca402fcd",
        "game_id": "33769172-e5ee-46dd-92fc-1d2467d57c49",
        "move_san": "f3",
        "issue": "Opponent's blunder - needs explanation",
        "caption": "Opponent's f3 is a major blunder. Your king gets space to escape via Ke5, and their pawns become weak."
    },
    {
        "feedback_id": "fb_c2bbff95a415",
        "game_id": "33769172-e5ee-46dd-92fc-1d2467d57c49",
        "move_san": "c2",
        "issue": "Why is better explained, what about king activity?",
        "caption": "c2 is a major blunder because it activates your king (Ke5), giving you winning chances. Ke5 was better."
    },
    {
        "feedback_id": "fb_c7d01e8e48ff",
        "game_id": "33769172-e5ee-46dd-92fc-1d2467d57c49",
        "move_san": "Qxf6+",
        "issue": "Why queen exchange was better",
        "caption": "Qxf6+ forces the king to move, checking the opponent while you gain tempo."
    },
    {
        "feedback_id": "fb_730b490361e0",
        "game_id": "33769172-e5ee-46dd-92fc-1d2467d57c49",
        "move_san": "Bh5",
        "issue": "Opponent didn't see Qh7 doesn't work",
        "caption": "Opponent's Bh5 is a mistake. They missed that Qh7 is blocked by the h5 bishop."
    },
    {
        "feedback_id": "fb_dd2c42c3f6d7",
        "game_id": "33769172-e5ee-46dd-92fc-1d2467d57c49",
        "move_san": "d5",
        "issue": "Why is this a mistake",
        "caption": "Opponent's d5 is a mistake. It allows exd5, opening the e-file for your attack."
    },
    {
        "feedback_id": "fb_730b490361e0",
        "game_id": "33769172-e5ee-46dd-92fc-1d2467d57c49",
        "move_san": "Bh5",
        "issue": "Creativity note",
        "caption": "Opponent's Bh5 is a mistake. Your queen on h7 (if it moves there) isn't really a threat because the bishop blocks the h-file."
    }
]

def apply_submissions():
    """Apply authoring submissions to database"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    print(f"\n{'='*100}")
    print(f"Applying Authoring Submissions")
    print(f"{'='*100}\n")

    successful = 0
    failed = 0

    for i, submission in enumerate(SUBMISSIONS, 1):
        try:
            # Create authored override entry
            override_id = f"override_{uuid4().hex[:12]}"

            override = {
                "override_id": override_id,
                "feedback_id": submission["feedback_id"],
                "game_id": submission["game_id"],
                "move_san": submission["move_san"],
                "authored_caption": submission["caption"],
                "reason": submission["issue"],
                "status": "applied",
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            # Insert into database
            result = db.authored_caption_overrides.insert_one(override)

            # Mark feedback as resolved
            db.move_feedback.update_one(
                {"feedback_id": submission["feedback_id"]},
                {"$set": {
                    "status": "acknowledged",
                    "resolved_via": "authoring_override",
                    "override_id": override_id,
                    "acknowledged_at": datetime.now(timezone.utc).isoformat()
                }}
            )

            print(f"[{i:2d}] APPLIED: {submission['feedback_id']}")
            print(f"      Move: {submission['move_san']}")
            print(f"      Caption: {submission['caption'][:70]}...")
            successful += 1

        except Exception as e:
            print(f"[{i:2d}] FAILED: {submission['feedback_id']} - {e}")
            failed += 1

    print(f"\n{'='*100}")
    print(f"SUMMARY: {successful} applied, {failed} failed")
    print(f"{'='*100}\n")

    return successful, failed

if __name__ == "__main__":
    apply_submissions()
