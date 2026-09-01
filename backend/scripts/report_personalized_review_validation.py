"""Read-only Phase 6 Game Review validation summary.

Run inside the backend container so Mongo credentials stay in its environment::

    python scripts/report_personalized_review_validation.py
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import os
from typing import Any, Dict, Iterable, Mapping


def summarize(documents: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    rows = list(documents)
    by_mode = Counter(str(row.get("presentation_mode") or "unknown") for row in rows)
    critical = Counter(
        str(row.get("presentation_mode") or "unknown")
        for row in rows
        if row.get("critical_truth_failure") is True
    )
    rubric_counts = defaultdict(lambda: defaultdict(Counter))
    pair_modes = defaultdict(set)
    for row in rows:
        mode = str(row.get("presentation_mode") or "unknown")
        pair_modes[(row.get("reviewer_user_id"), row.get("game_id"))].add(mode)
        for dimension, option in (row.get("ratings") or {}).items():
            rubric_counts[mode][str(dimension)][str(option)] += 1

    paired = sum(
        1
        for modes in pair_modes.values()
        if {"legacy", "personalized"}.issubset(modes)
    )
    return {
        "submissions": len(rows),
        "reviewers": len({row.get("reviewer_user_id") for row in rows}),
        "games": len({row.get("game_id") for row in rows}),
        "submissions_by_mode": dict(sorted(by_mode.items())),
        "paired_reviewer_games": paired,
        "unpaired_reviewer_games": len(pair_modes) - paired,
        "critical_truth_failures_by_mode": dict(sorted(critical.items())),
        "rubric_counts_by_mode": {
            mode: {
                dimension: dict(sorted(options.items()))
                for dimension, options in sorted(dimensions.items())
            }
            for mode, dimensions in sorted(rubric_counts.items())
        },
    }


def main() -> int:
    from pymongo import MongoClient

    mongo_url = os.environ.get("MONGO_URL")
    database_name = os.environ.get("DB_NAME")
    if not mongo_url or not database_name:
        raise SystemExit("MONGO_URL and DB_NAME must come from the environment")
    db = MongoClient(mongo_url)[database_name]
    rows = db.game_review_validation_reviews.find(
        {},
        {
            "_id": 0,
            "reviewer_user_id": 1,
            "game_id": 1,
            "presentation_mode": 1,
            "ratings": 1,
            "critical_truth_failure": 1,
        },
    )
    print(json.dumps(summarize(rows), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
