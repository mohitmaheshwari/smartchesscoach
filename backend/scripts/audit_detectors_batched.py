#!/usr/bin/env python3
"""
Detector Audit via Claude LLM Exposer.
Fetches pending feedback items and runs detector pipeline audits in parallel.

For each feedback item, asks Claude:
1. What facts SHOULD be set by detectors?
2. What facts ARE being set?
3. Where is the pipeline breaking? (detector, gate, template, suppression?)
4. What's the root cause?
5. What's the fix?

Usage:
  docker exec -e LLM_EXPOSER_URL=http://host.docker.internal:8000 \
    -e LLM_EXPOSER_KEY=<key> \
    chess-coach-backend python scripts/audit_detectors_batched.py \
      --pattern "Pattern #1" --limit 10
"""

import os
import json
import requests
import time
import sys
from pymongo import MongoClient
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

EXPOSER_URL = os.environ.get("LLM_EXPOSER_URL", "http://host.docker.internal:8000")
EXPOSER_KEY = os.environ.get("LLM_EXPOSER_KEY", "")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

def fetch_feedbacks(pattern=None, limit=20):
    """Fetch pending feedbacks from MongoDB"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    query = {"status": "pending"}

    if pattern:
        query["classification"] = pattern

    feedbacks = list(db.move_feedback.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit))

    return feedbacks

def audit_batch(batch_num, feedbacks):
    """Audit one batch of feedbacks for detector issues"""
    headers = {
        "Authorization": f"Bearer {EXPOSER_KEY}",
        "Content-Type": "application/json"
    }

    # Detector audit prompt
    prompt = f"""Analyze these {len(feedbacks)} feedback items to find detector pipeline issues.

For EACH feedback item, determine:
1. What facts SHOULD be set by the caption_facts detectors for this position?
2. What facts ARE actually being set (from diagnostics)?
3. WHERE is the pipeline breaking?
   - Is the detector not firing? (check logic)
   - Is a gate blocking the caption? (check suppression rules)
   - Is the template wrong? (check variant rendering)
   - Is the caption being suppressed? (check why_clause absence)
4. ROOT CAUSE: Which component is broken?
5. FIX: What's the minimal fix? (new detector, fix gate, rewrite template, suppress rule change)
6. CONFIDENCE: High/Medium/Low

Focus on PATTERN #1 items (coach says move is bad but no explanation of WHY).

Format output as JSON array with one object per feedback_id.

"""

    for fb in feedbacks:
        d = fb.get("diagnostics", {})
        prompt += f"""
## Feedback {fb.get('feedback_id')}
- User complaint: {fb.get('user_note', '(empty)')}
- Coaching text: {fb.get('coaching_text', '(empty)')}
- Move: {fb.get('move_san')} (severity: {d.get('severity')}, cp_loss: {d.get('cp_loss')}cp)
- Component: {d.get('component')} | Concept: {d.get('concept_id')}
- FEN: {fb.get('fen', '(no FEN)')}
"""

    prompt += """

Return JSON:
[
  {
    "feedback_id": "fb_xxx",
    "expected_facts": ["fact1", "fact2"],
    "missing_facts": ["fact_not_set"],
    "bottleneck": "detector_not_firing | gate_blocking | template_empty | suppressed",
    "root_cause": "brief explanation",
    "fix_type": "new_detector | fix_gate | rewrite_template | suppress_rule",
    "fix_description": "what to change",
    "confidence": "high|medium|low"
  }
]
"""

    payload = {"question": prompt}

    print(f"[Batch {batch_num}] Sending {len(feedbacks)} items for detector audit...")

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

            # Poll with longer timeout (up to 60 seconds)
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", default="Pattern #1", help="Pattern to audit (e.g., 'Pattern #1')")
    parser.add_argument("--limit", type=int, default=20, help="Max feedbacks to audit")
    parser.add_argument("--batch-size", type=int, default=5, help="Feedbacks per batch")
    args = parser.parse_args()

    print("="*80)
    print("DETECTOR AUDIT VIA LLM EXPOSER")
    print("="*80)
    print(f"Pattern: {args.pattern}")
    print(f"Batch size: {args.batch_size}")
    print()

    # Fetch feedbacks
    feedbacks = fetch_feedbacks(pattern=args.pattern, limit=args.limit)
    print(f"Fetched {len(feedbacks)} pending feedback items")
    print()

    if not feedbacks:
        print("No pending feedbacks found.")
        return

    # Split into batches
    batches = [feedbacks[i:i+args.batch_size] for i in range(0, len(feedbacks), args.batch_size)]
    print(f"Split into {len(batches)} batches of {args.batch_size}")
    print()

    # Run audits in parallel
    results = []
    with ThreadPoolExecutor(max_workers=min(5, len(batches))) as executor:
        futures = {
            executor.submit(audit_batch, i+1, batch): i+1
            for i, batch in enumerate(batches)
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print()

    # Print summary
    print("="*80)
    print("RESULTS SUMMARY")
    print("="*80)

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] in ("error", "timeout"))
    total_audited = sum(r["count"] for r in results if r["status"] == "success")

    print(f"Batches: {success_count} success, {error_count} failed")
    print(f"Items audited: {total_audited}")
    print()

    # Save results to file
    output_file = f"/tmp/detector_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Full results saved to: {output_file}")
    print()

    # Print audit findings
    print("="*80)
    print("AUDIT FINDINGS")
    print("="*80)

    for result in results:
        if result["status"] == "success":
            print(f"\n[Batch {result['batch']}]")
            try:
                # Try to parse JSON from response
                response_text = result["result"]
                if "```json" in response_text:
                    json_part = response_text.split("```json")[1].split("```")[0]
                elif "[" in response_text:
                    json_part = response_text[response_text.find("["):response_text.rfind("]")+1]
                else:
                    json_part = response_text

                audits = json.loads(json_part)

                # Print summary table
                print(f"\n{'ID':<20} {'Bottleneck':<25} {'Root Cause':<30} {'Fix':<20}")
                print("-"*95)

                for audit in audits:
                    fb_id = audit.get('feedback_id', 'unknown')[:20]
                    bottleneck = audit.get('bottleneck', 'unknown')[:25]
                    root_cause = audit.get('root_cause', 'unknown')[:30]
                    fix_type = audit.get('fix_type', 'unknown')[:20]

                    print(f"{fb_id:<20} {bottleneck:<25} {root_cause:<30} {fix_type:<20}")

            except Exception as e:
                print(f"Could not parse batch results: {e}")
                print(f"Raw response: {result['result'][:500]}")
        else:
            print(f"\n[Batch {result['batch']}] {result['status'].upper()}")
            if "error" in result:
                print(f"  Error: {result['error']}")

if __name__ == "__main__":
    main()
