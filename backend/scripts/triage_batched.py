#!/usr/bin/env python3
"""
Triage feedbacks in parallel batches via Claude Gold LLM Exposer.
Splits 100 feedbacks into 5 batches of 20, runs concurrently.

Usage:
  docker exec -e LLM_EXPOSER_URL=http://host.docker.internal:8000 \
    -e LLM_EXPOSER_KEY=<key> \
    chess-coach-backend python scripts/triage_batched.py
"""

import os
import json
import requests
import time
from pymongo import MongoClient
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

EXPOSER_URL = os.environ.get("LLM_EXPOSER_URL", "http://host.docker.internal:8000")
EXPOSER_KEY = os.environ.get("LLM_EXPOSER_KEY", "")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

def fetch_feedbacks(limit=100):
    """Fetch pending feedbacks from MongoDB"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    # All 120 items from batches 1-2 (already triaged)
    already_collected = {
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
    feedbacks = list(db.move_feedback.find(
        {"status": "pending", "feedback_id": {"$nin": list(already_collected)}},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit))
    return feedbacks

def triage_batch(batch_num, feedbacks):
    """Triage one batch of feedbacks with FULL context"""
    headers = {
        "Authorization": f"Bearer {EXPOSER_KEY}",
        "Content-Type": "application/json"
    }

    # FULL context prompt for accurate classification
    prompt = f"Classify these {len(feedbacks)} feedback items. For each, determine if it's a user-proposed caption fix (AUTHORING), a valid tactical question (CLASS_B), incomplete context (CLASS_D), a valid move that shouldn't be silent (CLASS_A_SILENT), a below-band precision quibble (CLASS_A_BAND), or vague/off-topic (DISMISS).\n\n"

    for fb in feedbacks:
        d = fb.get("diagnostics", {})
        prompt += f"""
# Feedback {fb.get('feedback_id')}
- Coaching text: {fb.get('coaching_text', '(empty)')}
- User complaint: {fb.get('user_note', '(empty)')}
- Move: {fb.get('move_san')} (severity: {d.get('severity')}, cp_loss: {d.get('cp_loss')})
- FEN: {fb.get('fen', '(no FEN)')}
- Component: {d.get('component')} | Concept: {d.get('concept_id')}
- Suggested fix: {fb.get('suggested_caption') or '(user did not propose a fix)'}
"""

    prompt += "\nFor each feedback, output: id|class|reason (brief)"

    payload = {"question": prompt}

    print(f"[Batch {batch_num}] Sending {len(feedbacks)} items...")

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
            print(f"[Batch {batch_num}] Task queued: {task_id}")

            # Poll with longer timeout (up to 60 seconds for full context)
            for attempt in range(30):
                time.sleep(2)
                task_response = requests.get(
                    f"{EXPOSER_URL}/tasks/{task_id}",
                    headers=headers,
                    timeout=10
                )

                if task_response.status_code == 200:
                    task_result = task_response.json()
                    if task_result.get("status") == "completed":
                        print(f"[Batch {batch_num}] ✓ Complete!")
                        return {
                            "batch": batch_num,
                            "status": "success",
                            "result": task_result.get("response", ""),
                            "count": len(feedbacks)
                        }

            print(f"[Batch {batch_num}] Timeout after 60s polling")
            return {
                "batch": batch_num,
                "status": "timeout",
                "task_id": task_id,
                "count": len(feedbacks)
            }
        else:
            print(f"[Batch {batch_num}] Error: {response.status_code}")
            return {
                "batch": batch_num,
                "status": "error",
                "error": response.text[:200],
                "count": len(feedbacks)
            }

    except Exception as e:
        print(f"[Batch {batch_num}] Exception: {e}")
        return {
            "batch": batch_num,
            "status": "error",
            "error": str(e),
            "count": len(feedbacks)
        }

def main():
    print(f"\n{'='*100}")
    print(f"ChessGuru Feedback Triage - Batched Parallel Processing")
    print(f"{'='*100}\n")

    print(f"[{datetime.now()}] Fetching feedbacks...")
    feedbacks = fetch_feedbacks(100)
    print(f"[{datetime.now()}] Fetched {len(feedbacks)}")

    # Split into batches of 20
    batch_size = 20
    batches = [feedbacks[i:i+batch_size] for i in range(0, len(feedbacks), batch_size)]
    print(f"[{datetime.now()}] Split into {len(batches)} batches of {batch_size}")

    # Run batches in parallel
    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(triage_batch, i+1, batch): i+1
            for i, batch in enumerate(batches)
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"[{datetime.now()}] Batch {result['batch']} status: {result['status']}")

    # Summary
    print(f"\n{'='*100}")
    print(f"TRIAGE RESULTS")
    print(f"{'='*100}\n")

    for r in sorted(results, key=lambda x: x['batch']):
        status = r['status'].upper()
        count = r['count']
        print(f"Batch {r['batch']:2d}: {status:10} ({count:2d} items)", end="")
        if r['status'] == 'success':
            # Show first few lines of results
            lines = r['result'].split('\n')[:3]
            print(f" - {lines[0][:60]}")
        else:
            print()

    total_success = sum(1 for r in results if r['status'] == 'success')
    total_items = sum(r['count'] for r in results)
    print(f"\nTotal: {total_success}/{len(results)} batches successful ({total_items} items)")

if __name__ == "__main__":
    main()
