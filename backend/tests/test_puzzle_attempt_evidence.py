from datetime import datetime, timezone
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.puzzle_attempt_evidence import build_puzzle_attempt_evidence


def _build(prior_attempts=0, **request):
    return build_puzzle_attempt_evidence(
        request={"puzzle_id": "p1", "correct": False, **request},
        user_id="u1",
        prior_attempts=prior_attempts,
        rating_evidence={
            "rating": 1175,
            "source": "users.detected_rating",
            "measured": True,
        },
        created_at=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
    )


def test_first_unassisted_attempt_is_independent_with_provenance():
    row = _build(
        support_level="none",
        outcome="incorrect",
        time_taken_ms=4512.9,
        moves_tried=["e2e4"],
        surface="prescribed_training",
    )
    assert row["attempt_schema_version"] == "puzzle_attempt.v2"
    assert row["attempt_ordinal"] == 1
    assert row["is_first_attempt"] is True
    assert row["counts_as_independent_attempt"] is True
    assert row["solver_rating"] == 1175
    assert row["solver_rating_source"] == "users.detected_rating"
    assert row["solver_rating_measured"] is True
    assert row["time_taken_ms"] == 4512


def test_retry_never_counts_as_independent_attempt():
    row = _build(prior_attempts=1, support_level="none")
    assert row["attempt_ordinal"] == 2
    assert row["is_first_attempt"] is False
    assert row["counts_as_independent_attempt"] is False


def test_unknown_support_and_invalid_time_fail_closed():
    row = _build(support_level="unexpected", time_taken_ms=-3, moves_tried="e2e4")
    assert row["support_level"] == "unknown"
    assert row["counts_as_independent_attempt"] is False
    assert row["time_taken_ms"] is None
    assert row["moves_tried"] == []
