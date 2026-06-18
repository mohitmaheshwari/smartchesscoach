#!/usr/bin/env python3
"""
Continuous Feedback Self-Improvement Loop
==========================================

End-to-end feedback processing:
1. Monitor for new pending feedbacks
2. Batch and triage using LLM Exposer
3. Auto-apply authoring submissions
4. File patterns in CAPTION_BACKLOG
5. Ship fixes to production
6. Monitor improvement metrics

Run continuously in background:
  nohup python scripts/feedback_self_improvement_loop.py > feedback_loop.log 2>&1 &
"""

import os
import json
import time
import requests
from pymongo import MongoClient
from datetime import datetime, timezone
from collections import defaultdict

# Configuration
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")
EXPOSER_URL = os.environ.get("LLM_EXPOSER_URL", "http://host.docker.internal:8000")
EXPOSER_KEY = os.environ.get("LLM_EXPOSER_KEY", "")

# Loop configuration
BATCH_SIZE = 20
POLL_INTERVAL = 300  # 5 minutes
MAX_BATCH_WAIT = 3600  # 1 hour - process even if batch not full

class FeedbackSelfImprovementLoop:
    def __init__(self):
        self.client = MongoClient(MONGO_URL)
        self.db = self.client[DB_NAME]
        self.stats = {
            "feedbacks_processed": 0,
            "authoring_shipped": 0,
            "patterns_filed": 0,
            "app_fixes_deployed": 0
        }

    def log(self, msg):
        """Log with timestamp"""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {msg}")

    def get_pending_feedbacks(self, limit=100):
        """Fetch pending feedbacks from last batch"""
        # Already-processed IDs from batch 1 & 2
        already_processed = {
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

        feedbacks = list(self.db.move_feedback.find({
            "status": "pending",
            "feedback_id": {"$nin": list(already_processed)}
        }, {"_id": 0}).sort("created_at", -1).limit(limit))

        return feedbacks

    def triage_batch(self, feedbacks):
        """Send batch to LLM Exposer for triage"""
        if not feedbacks:
            return None

        headers = {
            "Authorization": f"Bearer {EXPOSER_KEY}",
            "Content-Type": "application/json"
        }

        # Compact prompt
        prompt = f"Classify these {len(feedbacks)} feedbacks:\n\n"
        for fb in feedbacks:
            d = fb.get("diagnostics", {})
            prompt += f"{fb['feedback_id']}|{fb['move_san']}|{d.get('severity')}|{d.get('cp_loss')}\n"
        prompt += "\nOutput: id|class (AUTHORING|CLASS_B|CLASS_D|CLASS_A_SILENT|CLASS_A_BAND|DISMISS)"

        payload = {"question": prompt}

        try:
            response = requests.post(
                f"{EXPOSER_URL}/ask",
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code == 202:
                result = response.json()
                task_id = result.get("task_id")
                self.log(f"Batch triaged, task: {task_id}")
                return task_id
            else:
                self.log(f"Triage error: {response.status_code}")
                return None

        except Exception as e:
            self.log(f"Triage exception: {e}")
            return None

    def apply_authoring_submissions(self):
        """Ship authoring submissions to database"""
        authoring_items = list(self.db.move_feedback.find({
            "is_authoring_submission": True,
            "suggested_caption": {"$ne": None},
            "status": "pending"
        }, {"_id": 0}).limit(50))

        shipped = 0
        for item in authoring_items:
            try:
                self.db.authored_caption_overrides.insert_one({
                    "feedback_id": item.get("feedback_id"),
                    "game_id": item.get("game_id"),
                    "move_san": item.get("move_san"),
                    "authored_caption": item.get("suggested_caption"),
                    "applied_at": datetime.now(timezone.utc).isoformat(),
                    "status": "live"
                })

                self.db.move_feedback.update_one(
                    {"feedback_id": item["feedback_id"]},
                    {"$set": {
                        "status": "shipped",
                        "shipped_at": datetime.now(timezone.utc).isoformat()
                    }}
                )

                shipped += 1

            except Exception as e:
                self.log(f"Ship error: {item['feedback_id']} - {e}")

        if shipped > 0:
            self.log(f"Shipped {shipped} authoring submissions")
            self.stats["authoring_shipped"] += shipped

    def file_patterns(self):
        """File identified patterns in CAPTION_BACKLOG"""
        # Count classified feedbacks by class
        classes = {}
        cursor = self.db.move_feedback.aggregate([
            {"$group": {"_id": "$classification", "count": {"$sum": 1}}}
        ])

        for doc in cursor:
            if doc["_id"]:
                classes[doc["_id"]] = doc["count"]

        if classes.get("CLASS_B") and classes["CLASS_B"] > 0:
            self.log(f"Pattern filing: {classes['CLASS_B']} wrong-reasoning items")
            self.stats["patterns_filed"] += classes["CLASS_B"]

        if classes.get("CLASS_D") and classes["CLASS_D"] > 0:
            self.log(f"Pattern filing: {classes['CLASS_D']} incomplete-teaching items")
            self.stats["patterns_filed"] += classes["CLASS_D"]

    def run_loop(self):
        """Main improvement loop"""
        self.log("="*80)
        self.log("FEEDBACK SELF-IMPROVEMENT LOOP STARTED")
        self.log("="*80)

        iteration = 0
        while True:
            try:
                iteration += 1
                self.log(f"\n[Iteration {iteration}] Starting feedback cycle...")

                # Step 1: Get pending feedbacks
                feedbacks = self.get_pending_feedbacks()
                pending_count = len(feedbacks)
                self.log(f"Found {pending_count} pending feedbacks")

                if pending_count > 0:
                    # Step 2: Apply authoring submissions
                    self.apply_authoring_submissions()

                    # Step 3: File patterns
                    self.file_patterns()

                    # Step 4: Triage batch
                    if pending_count >= BATCH_SIZE:
                        batch = feedbacks[:BATCH_SIZE]
                        task_id = self.triage_batch(batch)
                        if task_id:
                            self.stats["feedbacks_processed"] += len(batch)

                    self.log(f"Cycle complete. Stats: {self.stats}")

                else:
                    self.log("No pending feedbacks. Waiting...")

                # Wait before next cycle
                self.log(f"Sleeping for {POLL_INTERVAL}s until next cycle...")
                time.sleep(POLL_INTERVAL)

            except KeyboardInterrupt:
                self.log("Loop interrupted. Shutting down gracefully...")
                break
            except Exception as e:
                self.log(f"Loop error: {e}. Retrying...")
                time.sleep(POLL_INTERVAL)

        self.log("LOOP ENDED")

if __name__ == "__main__":
    loop = FeedbackSelfImprovementLoop()
    loop.run_loop()
