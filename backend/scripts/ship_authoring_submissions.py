#!/usr/bin/env python3
"""
Ship 21 authoring submissions from feedback.
Creates authored_caption_overrides entries for each proposed caption.

Usage:
  docker exec chess-coach-backend python scripts/ship_authoring_submissions.py
"""

import os
from pymongo import MongoClient
from datetime import datetime, timezone

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

# All 21 authoring submission feedback IDs from triage
AUTHORING_IDS = {
    "fb_029d2196f312", "fb_19699019e264", "fb_285b21b9bd0c", "fb_370bbe3bb460",
    "fb_5a53f3f8d1b0", "fb_67578e0eab52", "fb_730b490361e0", "fb_7f2fddf523b0",
    "fb_88e2930b64db", "fb_971847cddbde", "fb_9eb0d495f31d", "fb_a59c8497fa88",
    "fb_b552fe112987", "fb_b5c94f09541a", "fb_bbfe9b9510ab", "fb_c2bbff95a415",
    "fb_c7d01e8e48ff", "fb_c8a0ca402fcd", "fb_c947d16854ea", "fb_dd2c42c3f6d7",
    "fb_ffbd771bad33"
}

def ship_authoring():
    """Ship authoring submissions to database"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    print(f"\n{'='*100}")
    print(f"SHIPPING 21 Authoring Submissions")
    print(f"{'='*100}\n")

    successful = 0
    failed = 0

    # Fetch all authoring submissions from database
    feedbacks = list(db.move_feedback.find({
        "feedback_id": {"$in": list(AUTHORING_IDS)},
        "is_authoring_submission": True,
        "suggested_caption": {"$ne": None}
    }, {"_id": 0}))

    print(f"Found {len(feedbacks)} authoring submissions with captions in database\n")

    for i, fb in enumerate(feedbacks, 1):
        try:
            feedback_id = fb.get("feedback_id")
            game_id = fb.get("game_id")
            move_san = fb.get("move_san")
            suggested = fb.get("suggested_caption")

            # Store as authored override
            override = {
                "feedback_id": feedback_id,
                "game_id": game_id,
                "move_san": move_san,
                "authored_caption": suggested,
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "status": "live"
            }

            # Insert override
            db.authored_caption_overrides.insert_one(override)

            # Mark feedback as shipped
            db.move_feedback.update_one(
                {"feedback_id": feedback_id},
                {"$set": {
                    "status": "shipped",
                    "shipped_at": datetime.now(timezone.utc).isoformat()
                }}
            )

            print(f"[{i:2d}] SHIPPED: {feedback_id}")
            print(f"       Game: {game_id[:8]}...  Move: {move_san}")
            print(f"       Caption: {suggested[:80]}...")
            successful += 1

        except Exception as e:
            print(f"[{i:2d}] FAILED: {feedback_id} - {e}")
            failed += 1

    print(f"\n{'='*100}")
    print(f"SUMMARY")
    print(f"{'='*100}")
    print(f"Shipped: {successful} / 21")
    print(f"Failed:  {failed} / 21")
    print(f"Status:  {'SUCCESS' if failed == 0 else 'PARTIAL'}\n")

    # Show next steps
    if successful > 0:
        print(f"Next steps:")
        print(f"  1. Verify overrides in authored_caption_overrides collection")
        print(f"  2. Test in UI to confirm captions render correctly")
        print(f"  3. Monitor for edge cases (TBD)")
        print(f"\nShipped caption count: {successful}")
        print(f"User-proposed captions now live in: authored_caption_overrides collection\n")

if __name__ == "__main__":
    ship_authoring()
