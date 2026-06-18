#!/usr/bin/env python3
"""
Feedback Self-Improvement Status Dashboard
===========================================

Real-time visibility into the feedback loop:
- Pending feedbacks count
- Authoring submissions ready to ship
- Patterns identified for filing
- Improvement metrics

Run: python scripts/feedback_status_dashboard.py
"""

import os
from pymongo import MongoClient
from datetime import datetime, timezone
from collections import defaultdict

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

def get_dashboard():
    """Generate feedback status dashboard"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    # Already processed from batches 1 & 2
    PROCESSED = {
        "fb_98343d604432", "fb_7251f794280d", "fb_11ae459a0bec", "fb_7f4ffe2507ba",
        "fb_a4303de63623", "fb_d41484b57a71", "fb_1b5beaf4324a", "fb_74bb4e444050",
        "fb_d218fd24e502", "fb_9dc516d84c6b", "fb_74fea9cccb40", "fb_20af82c03136",
        "fb_eb608850a035", "fb_5212760634a5", "fb_675df9cf1ff3", "fb_f610d5566f40",
        "fb_36f2776bcfa1", "fb_ba2347a3bf3c", "fb_01ddccca8235", "fb_e653dd85f63a",
        "fb_88e2930b64db", "fb_9eb0d495f31d", "fb_ed1465fd1431", "fb_ca9e14e589f9",
        "fb_c8a0ca402fcd", "fb_c2bbff95a415", "fb_c7d01e8e48ff", "fb_1559fbc85486",
        "fb_730b490361e0", "fb_457a7b70c6ce", "fb_581c20ddbe13", "fb_d741075d4b31",
        "fb_dd2c42c3f6d7", "fb_37bb36fc570b", "fb_934ea318b431", "fb_177afa712c7a",
        "fb_a112a9ceefe6", "fb_2d8b33f59ab0", "fb_b8a23dd50b32", "fb_c041db1af460",
        "fb_67578e0eab52", "fb_7f2fddf523b0", "fb_19699019e264", "fb_c947d16854ea",
        "fb_029d2196f312", "fb_a32cdaee5acb", "fb_285b21b9bd0c", "fb_ffbd771bad33",
        "fb_370bbe3bb460", "fb_a59c8497fa88", "fb_b5c94f09541a", "fb_b552fe112987",
        "fb_5a53f3f8d1b0", "fb_7e5510f021db", "fb_56b8b22824c5", "fb_0ce96a984fb6",
        "fb_bbfe9b9510ab", "fb_78a839dd8931", "fb_4c4187178e98", "fb_971847cddbde",
        "fb_896762a9722b", "fb_6e0179b65e5c", "fb_69096be0ece2", "fb_2c031a627fb3",
        "fb_f64573d24a1b", "fb_b68bbeb1bf25", "fb_e89cbb8975b5", "fb_0c7cc1e31c73",
        "fb_d524596d3894", "fb_eb62358ce3b3", "fb_4c0fc096db40", "fb_faad0de42207",
        "fb_c5c580a1d2fb", "fb_4d5adb240365", "fb_9f8b0aa03409", "fb_b8c98a2d1b26",
        "fb_9f984e9753fc", "fb_6785172554ab", "fb_2e4a04c0d7bf", "fb_5c610a607f2f",
        "fb_2f95f27a8f57", "fb_d9952f1a46e0", "fb_b117fa87fa34", "fb_f6486d4b20d4",
        "fb_185c73536a69", "fb_064a94d98146", "fb_3568dd575452", "fb_494f71eb3913",
        "fb_6ec158e3a291", "fb_f1b46420da5a", "fb_3280cebef2e5", "fb_457d742bcc4b",
        "fb_f4daba662227", "fb_3efccdbbf15e", "fb_1cd7562468d1", "fb_f62567c759f9",
        "fb_c2a4885bbc70", "fb_c84288e3e17e", "fb_219125b27dda", "fb_a957e395ca79",
        "fb_5591f942c9c1", "fb_107482eebc89", "fb_e0a1432b46ab", "fb_988e0b233b57",
        "fb_405dad440391", "fb_0a418f516db7", "fb_cf6365050a3e", "fb_ea8c1a30de7a",
        "fb_b554778710ba", "fb_541f1f71cbe2", "fb_ca395200c663", "fb_02df8d0a0d12",
        "fb_9150afff1d69", "fb_695eed210334", "fb_e8b798e6055e", "fb_448995f4d1c3",
        "fb_aa681e12768d", "fb_66c5d8d15cf2", "fb_b7ef8ff39f30", "fb_d8fdf5865ea7"
    }

    print(f"\n{'='*100}")
    print(f"FEEDBACK SELF-IMPROVEMENT STATUS DASHBOARD — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'='*100}\n")

    # 1. Pending feedback count
    total_pending = db.move_feedback.count_documents({"status": "pending"})
    new_pending = db.move_feedback.count_documents({
        "status": "pending",
        "feedback_id": {"$nin": list(PROCESSED)}
    })

    print(f"PENDING FEEDBACKS:")
    print(f"  Total:    {total_pending}")
    print(f"  New:      {new_pending} (since last triage)")
    print(f"  Processed: {len(PROCESSED)} (from batches 1-2)\n")

    # 2. Authoring submissions ready to ship
    authoring_ready = db.move_feedback.count_documents({
        "is_authoring_submission": True,
        "suggested_caption": {"$ne": None},
        "status": "pending"
    })

    authoring_shipped = db.move_feedback.count_documents({
        "status": "shipped"
    })

    print(f"AUTHORING SUBMISSIONS:")
    print(f"  Ready to ship: {authoring_ready}")
    print(f"  Already shipped: {authoring_shipped}\n")

    # 3. Already shipped captions
    shipped_captions = db.authored_caption_overrides.count_documents({})
    print(f"CAPTIONS IN PRODUCTION:")
    print(f"  Live: {shipped_captions}\n")

    # 4. Classification breakdown (from triage)
    classifications = defaultdict(int)
    cursor = db.move_feedback.find(
        {"status": "pending", "feedback_id": {"$nin": list(PROCESSED)}},
        {"diagnostics": 1}
    ).limit(250)

    for doc in cursor:
        diag = doc.get("diagnostics", {})
        severity = diag.get("severity", "unknown")
        classifications[severity] += 1

    print(f"NEW FEEDBACK BREAKDOWN (sample):")
    for key, count in sorted(classifications.items(), key=lambda x: -x[1]):
        key_str = str(key) if key else "unknown"
        print(f"  {key_str:20} {count:3} items")
    print()

    # 5. App improvement metrics
    print(f"APP IMPROVEMENT PIPELINE:")
    print(f"  Authoring submissions shipped: {authoring_shipped}")
    print(f"  Templates with overrides: {shipped_captions}")
    print(f"  Average feedback quality: 52.5% actionable (from batch 2)\n")

    # 6. Next steps
    print(f"RECOMMENDED ACTIONS:")
    print(f"  1. Run /triage-feedback on {new_pending} new feedbacks")
    print(f"  2. Ship {authoring_ready} pending authoring submissions")
    print(f"  3. File patterns in CAPTION_BACKLOG")
    print(f"  4. Deploy fixes to production\n")

    print(f"{'='*100}\n")

if __name__ == "__main__":
    get_dashboard()
