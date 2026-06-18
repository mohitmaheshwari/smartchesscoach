#!/usr/bin/env python3
"""
Save batch 3 triage results to database and ship AUTHORING items
"""
import os
import json
import sys
import asyncio
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

# Batch 3 results (100 items, 5 batches of 20 each)
# Generated from LLM Exposer with FULL CONTEXT
BATCH3_RESULTS = {
    "summary": {
        "AUTHORING": 40,
        "CLASS_B": 27,
        "CLASS_A_SILENT": 19,
        "CLASS_D": 7,
        "CLASS_A_BAND": 4,
        "DISMISS": 3
    },
    "total": 100,
    "note": "Batch 3 triage completed 2026-06-13 with full feedback context"
}

async def main():
    """Save results and optionally ship"""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    print(f"\n{'='*100}")
    print(f"BATCH 3 TRIAGE COMPLETION")
    print(f"{'='*100}\n")

    # Save summary to a collection for audit trail
    triage_summary = {
        "batch": 3,
        "total_items": 100,
        "classifications": BATCH3_RESULTS["summary"],
        "completed_at": "2026-06-13T08:50:00Z",
        "task_ids": [
            "t_d3f0f4aed305",
            "t_c14a3778279f",
            "t_fb9a0ca04b86",
            "t_619d43d630c9",
            "t_1cb224b0ed19"
        ]
    }

    result = await db.triage_batches.insert_one(triage_summary)
    print(f"✅ Saved triage summary: {triage_summary['classifications']}")

    # Now count actual AUTHORING items in database with suggested_caption
    authoring_in_db = await db.move_feedback.count_documents({
        "is_authoring_submission": True,
        "status": "pending",
        "suggested_caption": {"$exists": True, "$ne": None}
    })

    print(f"✅ User-submitted captions in DB: {authoring_in_db}")

    # Get the count of already-shipped captions
    shipped = await db.authored_caption_overrides.count_documents({})
    print(f"✅ Captions already shipped: {shipped}")

    print(f"\n{'='*100}")
    print(f"NEXT STEPS:")
    print(f"{'='*100}\n")
    print(f"  1. Run backend/scripts/ship_authoring_submissions.py to ship captions")
    print(f"  2. Run /audit-triage-quality to verify results before filing patterns")
    print(f"  3. File CLASS_B/CLASS_D patterns in CAPTION_BACKLOG")
    print(f"  4. Deploy continuous feedback loop")

    client.close()

asyncio.run(main())
