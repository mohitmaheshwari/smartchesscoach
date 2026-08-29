from datetime import datetime, timezone
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.product_loop_census import _as_utc, _counter, _recent_summary


def test_as_utc_accepts_bson_datetime_and_iso_strings():
    expected = datetime(2026, 8, 28, 3, 0, tzinfo=timezone.utc)

    assert _as_utc(expected) == expected
    assert _as_utc("2026-08-28T03:00:00+00:00") == expected
    assert _as_utc("2026-08-28T03:00:00Z") == expected


def test_as_utc_rejects_missing_and_malformed_values():
    assert _as_utc(None) is None
    assert _as_utc(123) is None
    assert _as_utc("not-a-date") is None


def test_recent_summary_counts_records_and_distinct_users_without_returning_ids():
    rows = [
        {"user_id": "u1", "at": "2026-08-27T10:00:00Z"},
        {"user_id": "u1", "at": datetime(2026, 8, 28, tzinfo=timezone.utc)},
        {"user_id": "u2", "at": "2026-08-01T10:00:00Z"},
        {"user_id": "u3", "at": "bad"},
    ]

    result = _recent_summary(rows, "at", datetime(2026, 8, 20, tzinfo=timezone.utc))

    assert result == {"records": 2, "users": 1}
    assert "u1" not in result


def test_counter_uses_stable_null_bucket():
    assert _counter(["active", None, "active", "closed"]) == {
        "active": 2,
        "closed": 1,
        "null": 1,
    }

