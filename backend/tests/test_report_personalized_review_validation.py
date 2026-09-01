"""Phase 6 validation-report aggregation tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "scripts"
    / "report_personalized_review_validation.py"
)
SPEC = importlib.util.spec_from_file_location("phase6_report", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_summary_counts_paired_modes_and_critical_failures_without_notes():
    rows = [
        {
            "reviewer_user_id": "r1",
            "game_id": "g1",
            "presentation_mode": "legacy",
            "ratings": {"chess_truth": "correct"},
            "critical_truth_failure": False,
            "notes": "must not be summarized",
        },
        {
            "reviewer_user_id": "r1",
            "game_id": "g1",
            "presentation_mode": "personalized",
            "ratings": {"chess_truth": "critical_false_claim"},
            "critical_truth_failure": True,
            "notes": "private",
        },
        {
            "reviewer_user_id": "r2",
            "game_id": "g2",
            "presentation_mode": "legacy",
            "ratings": {"chess_truth": "minor_issue"},
            "critical_truth_failure": False,
        },
    ]
    summary = MODULE.summarize(rows)
    assert summary["submissions"] == 3
    assert summary["reviewers"] == 2
    assert summary["games"] == 2
    assert summary["paired_reviewer_games"] == 1
    assert summary["unpaired_reviewer_games"] == 1
    assert summary["critical_truth_failures_by_mode"] == {"personalized": 1}
    assert summary["rubric_counts_by_mode"]["legacy"]["chess_truth"] == {
        "correct": 1,
        "minor_issue": 1,
    }
    assert "notes" not in str(summary).lower()


def test_report_is_read_only_and_credential_free():
    source = SCRIPT.read_text(encoding="utf-8").lower()
    assert "mongodb://" not in source
    assert "insert_one" not in source
    assert "update_one" not in source
    assert "delete" not in source
    assert 'os.environ.get("mongo_url")' in source
