#!/usr/bin/env python3
"""
Collect and display all 5 batch results with summary stats
"""
import os
import json
import requests

EXPOSER_URL = os.environ.get("LLM_EXPOSER_URL", "http://host.docker.internal:8000")
EXPOSER_KEY = os.environ.get("LLM_EXPOSER_KEY", "")

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
print("COLLECTING BATCH 3 TRIAGE RESULTS (100 items, 5 batches)")
print("="*100 + "\n")

all_classifications = {}
classifications_summary = {
    "AUTHORING": 0,
    "CLASS_B": 0,
    "CLASS_D": 0,
    "CLASS_A_SILENT": 0,
    "CLASS_A_BAND": 0,
    "DISMISS": 0
}

for batch_num, task_id in sorted(task_ids.items()):
    response = requests.get(
        f"{EXPOSER_URL}/tasks/{task_id}",
        headers=headers,
        timeout=10
    )

    if response.status_code == 200:
        result = response.json()
        if result.get("status") in ["completed", "done"]:
            answer = result.get("answer", "")

            # Parse the CSV-like output
            print(f"[Batch {batch_num}] Parsing classifications...")

            for line in answer.split('\n'):
                if '|' in line and 'fb_' in line:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 2:
                        fb_id = parts[0]
                        cls = parts[1].upper()
                        reason = parts[2] if len(parts) > 2 else ""

                        all_classifications[fb_id] = {
                            "class": cls,
                            "reason": reason,
                            "batch": batch_num
                        }

                        if cls in classifications_summary:
                            classifications_summary[cls] += 1

            print(f"  ✓ Batch {batch_num}: {sum(1 for k,v in all_classifications.items() if v['batch']==batch_num)} items")

print(f"\n" + "="*100)
print("BATCH 3 CLASSIFICATION SUMMARY")
print("="*100 + "\n")

total = sum(classifications_summary.values())
for cls, count in sorted(classifications_summary.items(), key=lambda x: -x[1]):
    pct = f"{100*count/total:.1f}%" if total > 0 else "0%"
    print(f"  {cls:20} {count:3} items ({pct})")

print(f"\n  TOTAL: {total} items classified")

print(f"\n" + "="*100)
print("SAMPLE AUTHORING ITEMS (ready to ship)")
print("="*100 + "\n")

authoring_items = [
    (fb_id, info) for fb_id, info in all_classifications.items()
    if info['class'] == 'AUTHORING'
][:10]

for fb_id, info in authoring_items:
    print(f"  {fb_id}: {info['reason']}")

print(f"\n  ... and {len([x for x in all_classifications.values() if x['class']=='AUTHORING']) - len(authoring_items)} more AUTHORING items")

# Save results to file
results_file = "/app/backend/scripts/batch3_triage_results.json"
with open(results_file, 'w') as f:
    json.dump({
        "summary": classifications_summary,
        "total": total,
        "items": all_classifications
    }, f, indent=2)

print(f"\n✅ Results saved to {results_file}")
