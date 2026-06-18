#!/usr/bin/env python3
"""
Fetch and display triage results from completed LLM Exposer tasks
"""
import os
import json
import requests

EXPOSER_URL = os.environ.get("LLM_EXPOSER_URL", "http://host.docker.internal:8000")
EXPOSER_KEY = os.environ.get("LLM_EXPOSER_KEY", "")

# Task IDs from recent triage run
task_ids = {
    1: "t_d3f0f4aed305",
    2: "t_c14a3778279f",
    3: "t_fb9a0ca04b86",
    4: "t_619d43d630c9",
    5: "t_1cb224b0ed19"
}

headers = {
    "Authorization": f"Bearer {EXPOSER_KEY}",
    "Content-Type": "application/json"
}

print("\n" + "="*100)
print("FETCHING TRIAGE RESULTS")
print("="*100 + "\n")

for batch_num, task_id in sorted(task_ids.items()):
    print(f"[Batch {batch_num}] {task_id}...", end=" ", flush=True)

    response = requests.get(
        f"{EXPOSER_URL}/tasks/{task_id}",
        headers=headers,
        timeout=10
    )

    if response.status_code == 200:
        result = response.json()
        status = result.get("status")
        print(f"{status}")

        if status == "completed":
            print(f"\n--- BATCH {batch_num} RESULTS ---\n")
            print(result.get("response", "(no response text)"))
            print()
    else:
        print(f"ERROR {response.status_code}")

print("\n" + "="*100)
