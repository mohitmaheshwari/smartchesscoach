"""
Analyze the "same" bucket from regen_diff.json — bugs whose new caption
matches the original byte-for-byte. These can't be addressed by filter
work; they need template/generation enrichment.

For each same-bucket bug, prints:
  - feedback_id, move, severity
  - The flagged caption (what users currently see)
  - Parth's issue note (what he says is wrong with it)
  - Heuristic grouping (missing consequence / alternative / pattern / prompt)

Heuristics on Parth's issue text:
  - "why" / "explain" / "doesn't" / "fails to" / "obvious" → missing_explanation
  - "should have" / "better" / "alternative" / "instead" → missing_alternative
  - "blunder" / "mistake" / "this is" / "type of" → missing_severity_label
  - "next time" / "look for" / "watch for" / "remember" → missing_thinking_prompt

Usage:
    python scripts/analyze_same_bucket.py \\
        --regen-diff /tmp/regen_diff.json \\
        --bug-file /tmp/parth_full_with_fen.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


_GROUP_KEYWORDS = {
    "missing_explanation": [
        "why", "explain", "explanation", "doesn't", "doesn't say",
        "fails to", "obvious", "useful", "clarify", "without explaining",
        "doesn't tell", "no reason", "not useful",
    ],
    "missing_alternative": [
        "should have", "better move", "better was", "alternative",
        "instead", "stronger move", "should be", "could have",
        "what should", "right move",
    ],
    "missing_severity_label": [
        "blunder", "this is mistake", "this is blunder", "this is a blunder",
        "this is a mistake", "should be flagged", "should have been flagged",
        "miss this", "tool miss",
    ],
    "missing_thinking_prompt": [
        "next time", "look for", "watch for", "remember to",
        "think about", "should think", "ask yourself",
    ],
}


def classify_issue(issue: str) -> List[str]:
    """Return the groups whose keywords appear in the issue text. A bug
    can belong to multiple groups."""
    if not issue:
        return ["uncategorized"]
    lo = issue.lower()
    matched = [g for g, kws in _GROUP_KEYWORDS.items()
               if any(kw in lo for kw in kws)]
    return matched or ["uncategorized"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--regen-diff", default="/tmp/regen_diff.json")
    p.add_argument("--bug-file", default="/tmp/parth_full_with_fen.json")
    args = p.parse_args()

    diff = json.loads(Path(args.regen_diff).read_text(encoding="utf-8"))
    bug_data = json.loads(Path(args.bug_file).read_text(encoding="utf-8"))
    bugs = bug_data.get("feedback") or []

    bugs_by_id: Dict[str, Dict] = {b.get("feedback_id"): b for b in bugs}

    same_records = [r for r in diff.get("results", []) if r.get("verdict") == "same"]
    print(f"Found {len(same_records)} bugs in 'same' bucket\n")

    by_group: Dict[str, List[Dict]] = defaultdict(list)
    for rec in same_records:
        fid = rec.get("feedback_id")
        bug = bugs_by_id.get(fid, {})
        issue = (bug.get("issue") or "").strip()
        groups = classify_issue(issue)
        enriched = {
            **rec,
            "issue": issue,
            "groups": groups,
            "page": bug.get("page"),
            "severity_stored": bug.get("severity"),
        }
        for g in groups:
            by_group[g].append(enriched)

    # Print per-group summary
    print("=" * 78)
    print("GROUPING — bugs may appear in multiple groups")
    print("=" * 78)
    for group in (
        "missing_explanation",
        "missing_alternative",
        "missing_severity_label",
        "missing_thinking_prompt",
        "uncategorized",
    ):
        items = by_group.get(group, [])
        if not items:
            continue
        print(f"\n--- {group.upper()} ({len(items)}) ---")
        for r in items:
            print(f"\n  {r['feedback_id']}  move {r['move_number']} {r['move_san']}  "
                  f"sev={r['severity_stored']}")
            print(f"    flagged: {r['flagged']}")
            print(f"    issue  : {r['issue'][:300]}")

    # Print group counts at the bottom
    print()
    print("=" * 78)
    print("COUNTS")
    print("=" * 78)
    for group in (
        "missing_explanation",
        "missing_alternative",
        "missing_severity_label",
        "missing_thinking_prompt",
        "uncategorized",
    ):
        n = len(by_group.get(group, []))
        if n:
            print(f"  {group:30s}  {n}")


if __name__ == "__main__":
    main()
