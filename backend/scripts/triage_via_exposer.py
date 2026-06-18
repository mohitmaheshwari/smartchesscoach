#!/usr/bin/env python3
"""
Triage 100 pending feedbacks via Claude Gold LLM Exposer (terminal gateway).
Sends feedback batch to LLM_EXPOSER_URL and outputs structured triage results.

Usage:
  docker exec -e LLM_EXPOSER_URL=http://host.docker.internal:8000 \
    -e LLM_EXPOSER_KEY=<key> \
    chess-coach-backend bash -lc "cd /app/backend && python scripts/triage_via_exposer.py"
"""

import os
import json
import requests
from pymongo import MongoClient
from datetime import datetime

# LLM Exposer config
EXPOSER_URL = os.environ.get("LLM_EXPOSER_URL", "http://host.docker.internal:8000")
EXPOSER_KEY = os.environ.get("LLM_EXPOSER_KEY", "")

# MongoDB config
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

def fetch_feedbacks(limit=100):
    """Fetch pending feedbacks from MongoDB"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    # IDs we already triaged in batch 1
    already_collected = {
        "fb_98343d604432", "fb_7251f794280d", "fb_11ae459a0bec", "fb_7f4ffe2507ba",
        "fb_a4303de63623", "fb_d41484b57a71", "fb_1b5beaf4324a", "fb_74bb4e444050",
        "fb_d218fd24e502", "fb_9dc516d84c6b", "fb_74fea9cccb40", "fb_20af82c03136",
        "fb_eb608850a035", "fb_5212760634a5", "fb_675df9cf1ff3", "fb_f610d5566f40",
        "fb_36f2776bcfa1", "fb_ba2347a3bf3c", "fb_01ddccca8235", "fb_e653dd85f63a"
    }

    feedbacks = list(db.move_feedback.find(
        {"status": "pending", "feedback_id": {"$nin": list(already_collected)}},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit))

    return feedbacks

def triage_via_exposer(feedbacks):
    """Send feedbacks to Claude Gold LLM Exposer for triage analysis"""

    # Prepare triage prompt
    prompt = f"""You are a feedback triage expert for ChessGuru. Analyze these {len(feedbacks)} feedback items and provide a CSV classification report.

For EACH item, classify as ONE of:
- AUTHORING: User submitted improved caption (is_authoring_submission=true)
- CLASS_B: Wrong reasoning (coaching explanation is factually incorrect)
- CLASS_D: Incomplete/terse (generic coaching, no position-specific WHY)
- CLASS_E: Confabulation (mentions pieces/moves not in position)
- CLASS_A_SILENT: Empty coaching or very terse
- CLASS_A_BAND: Below-band (cp_loss < 50, severity=good, but coach flagged)
- DISMISS: Off-topic or already-resolved
- INVESTIGATE: Needs engine cross-check

For each item, output ONE CSV line (no header):
feedback_id|class|severity|cp_loss|game_id|move_san|recommendation

FEEDBACK BATCH (latest 100 pending):

"""

    # Add feedback items to prompt
    for fb in feedbacks:
        diag = fb.get("diagnostics", {})
        prompt += f"\nID: {fb['feedback_id']} | game: {fb['game_id']} | move: {fb['move_san']} | severity: {diag.get('severity')} | cp_loss: {diag.get('cp_loss')} | coaching: {fb['coaching_text'][:80] if fb.get('coaching_text') else 'EMPTY'} | user_note: {fb.get('user_note', '')[:100]}"

    prompt += "\n\nOutput ONLY CSV lines (one per feedback), no explanation text."

    # Send to LLM Exposer
    headers = {
        "Authorization": f"Bearer {EXPOSER_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "question": prompt,
    }

    print(f"[{datetime.now()}] Sending {len(feedbacks)} feedbacks to LLM Exposer...")
    print(f"[{datetime.now()}] Endpoint: {EXPOSER_URL}/ask")

    try:
        response = requests.post(
            f"{EXPOSER_URL}/ask",
            json=payload,
            headers=headers,
            timeout=120
        )

        if response.status_code in [200, 202]:
            # If 202, task is queued; we need to poll for results
            if response.status_code == 202:
                result = response.json()
                task_id = result.get("task_id")
                print(f"[{datetime.now()}] Task queued: {task_id}")
                print(f"[{datetime.now()}] Waiting for results...")

                # Poll for results
                import time
                max_wait = 300  # 5 minutes
                start = time.time()
                while time.time() - start < max_wait:
                    time.sleep(5)
                    task_response = requests.get(
                        f"{EXPOSER_URL}/tasks/{task_id}",
                        headers=headers,
                        timeout=30
                    )
                    if task_response.status_code == 200:
                        task_result = task_response.json()
                        if task_result.get("status") == "completed":
                            result = task_result
                            print(f"[{datetime.now()}] Task completed!")
                            break
                        elif task_result.get("status") == "failed":
                            print(f"[{datetime.now()}] Task failed: {task_result.get('error')}")
                            return None
                        else:
                            print(f"[{datetime.now()}] Status: {task_result.get('status')}...")
                    else:
                        print(f"[{datetime.now()}] Poll error: {task_response.status_code}")
            else:
                result = response.json()

        if response.status_code in [200, 202]:
            result = response.json()
            print(f"\n[{datetime.now()}] ✓ Triage complete!\n")
            print("=" * 120)
            print("TRIAGE RESULTS:")
            print("=" * 120)
            # Extract the response content
            response_text = result.get("response", "") or result.get("answer", "") or result.get("output", "") or json.dumps(result)
            print(response_text)

            # Parse and summarize
            lines = response_text.strip().split("\n")
            classes = {}
            for line in lines:
                if "|" in line:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        cls = parts[1].strip()
                        classes[cls] = classes.get(cls, 0) + 1

            print("\n" + "=" * 120)
            print("CLASSIFICATION SUMMARY:")
            print("=" * 120)
            for cls, count in sorted(classes.items(), key=lambda x: -x[1]):
                pct = (count / len(feedbacks)) * 100 if feedbacks else 0
                print(f"  {cls:25} {count:3} items ({pct:5.1f}%)")

            return result
        else:
            print(f"[{datetime.now()}] ✗ Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return None

    except Exception as e:
        print(f"[{datetime.now()}] ✗ Exception: {e}")
        return None

def main():
    """Main entry point"""
    print(f"\n{'='*120}")
    print(f"ChessGuru Feedback Triage via Claude Gold LLM Exposer")
    print(f"{'='*120}\n")

    # Fetch feedbacks
    print(f"[{datetime.now()}] Fetching pending feedbacks from MongoDB...")
    feedbacks = fetch_feedbacks(limit=100)
    print(f"[{datetime.now()}] Fetched {len(feedbacks)} feedbacks")

    if not feedbacks:
        print("No pending feedbacks found!")
        return

    # Triage via exposer
    triage_via_exposer(feedbacks)

if __name__ == "__main__":
    main()
