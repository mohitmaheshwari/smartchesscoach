#!/usr/bin/env python3
"""
Direct detector audit for a batch of feedback items.
Takes JSON feedback items and sends to LLM Exposer for audit.
"""

import json
import requests
import time
import os

EXPOSER_URL = os.environ.get("LLM_API_BASE", "http://host.docker.internal:8000")
EXPOSER_KEY = os.environ.get("LLM_API_KEY", "")

# Sample feedback items (same structure as triage-feedback skill receives)
SAMPLE_FEEDBACK = [
    {
        "feedback_id": "fb_176e0c2f7ef4",
        "move_san": "Qxa7",
        "severity": "mistake",
        "cp_loss": 111,
        "issue": "doing nothing means?",
        "coaching_text": "Qxa7 is a serious mistake. Your queen on a7 is the only piece doing anything.",
        "game_id": "b04d121d-3442-4844-a966-07255a662e69",
        "move_number": 25
    },
    {
        "feedback_id": "fb_ffec325a9488",
        "move_san": "Rxf4",
        "severity": "blunder",
        "cp_loss": 8774,
        "issue": "doesn't sound right",
        "coaching_text": "Rxf4. Your queen on c7 is the only piece doing anything.",
        "game_id": "2d7ade57-e064-4089-94ab-8cb690c022a8",
        "move_number": 31
    },
    {
        "feedback_id": "fb_0f74b8a30d24",
        "move_san": "Nf4",
        "severity": "mistake",
        "cp_loss": 194,
        "issue": "knight on f4 is not under attack, because queen is attacking knight but it's defended by bishop",
        "coaching_text": "Nf4 is an inaccuracy. Be3 was better. After Qxd4, your knight on f4 is under attack.",
        "game_id": "2d7ade57-e064-4089-94ab-8cb690c022a8",
        "move_number": 6
    },
]

def audit_batch(feedbacks):
    """Send batch to LLM Exposer for detector audit"""
    headers = {
        "Authorization": f"Bearer {EXPOSER_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""Analyze {len(feedbacks)} chess coaching feedback items for detector bottlenecks.

For EACH item, identify:
1. Root cause: detector not firing | gate blocking | template sparse | wrong_template | confabulation | suppressed
2. Fix type: new_detector | fix_gate | rewrite_template | fix_confusion | suppress_rule | no_action
3. Confidence: high | medium | low
4. Specific issue if present (e.g., "caption says queen on c7 but it's on f6")

Items:
"""

    for fb in feedbacks:
        prompt += f"\n[{fb['feedback_id']}] {fb['move_san']}@{fb['severity']} (cp_loss={fb['cp_loss']}cp)"
        prompt += f"\n  Issue: {fb['issue']}"
        prompt += f"\n  Caption: {fb['coaching_text']}\n"

    prompt += """
Respond with JSON array:
[
  {"feedback_id": "fb_xxx", "root_cause": "...", "fix_type": "...", "confidence": "high|medium|low", "detail": "..."}
]
"""

    print(f"Sending {len(feedbacks)} items for detector audit...")
    print(f"LLM_API_BASE: {EXPOSER_URL}")
    print()

    try:
        response = requests.post(
            f"{EXPOSER_URL}/ask",
            json={"question": prompt},
            headers=headers,
            timeout=30
        )

        if response.status_code == 202:
            result = response.json()
            task_id = result.get("task_id")
            print(f"Task queued: {task_id}")
            print("Polling for completion...")

            # Poll with 180s timeout
            for attempt in range(90):
                time.sleep(2)
                task_response = requests.get(
                    f"{EXPOSER_URL}/tasks/{task_id}",
                    headers=headers,
                    timeout=10
                )

                if task_response.status_code == 200:
                    task_result = task_response.json()
                    if task_result.get("status") == "completed":
                        print("✓ Audit complete!")
                        response_text = task_result.get("response", "")

                        # Parse JSON from response
                        if "```json" in response_text:
                            json_part = response_text.split("```json")[1].split("```")[0]
                        elif "[" in response_text:
                            json_part = response_text[response_text.find("["):response_text.rfind("]")+1]
                        else:
                            json_part = response_text

                        audits = json.loads(json_part)

                        print("\n" + "="*100)
                        print("DETECTOR AUDIT RESULTS")
                        print("="*100)
                        print(f"\n{'ID':<20} {'Bottleneck':<30} {'Fix':<25} {'Conf':<8}")
                        print("-"*100)

                        for audit in audits:
                            fb_id = audit.get('feedback_id', 'unknown')[:20]
                            root = audit.get('root_cause', 'unknown')[:30]
                            fix = audit.get('fix_type', 'unknown')[:25]
                            conf = audit.get('confidence', 'unknown')[:8]
                            print(f"{fb_id:<20} {root:<30} {fix:<25} {conf:<8}")
                            if audit.get('detail'):
                                print(f"  → {audit['detail']}")

                        print("\n" + "="*100)
                        return audits

            print("ERROR: Timeout after 180s polling")
            return None
        else:
            print(f"ERROR: {response.status_code}")
            print(response.text)
            return None

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    results = audit_batch(SAMPLE_FEEDBACK)
    if results:
        print("\nFull results:")
        print(json.dumps(results, indent=2))
