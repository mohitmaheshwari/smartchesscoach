"""
Unit tests for the pure classification logic in
backend/scripts/pwc_first_session_funnel.py.

Added 2026-08-07 per external review of the Sprint 1 work: the funnel's
age-bucketing (is a session a real leak, or just still being played?)
had no direct test coverage, only a live DB run. These tests don't touch
Mongo at all -- is_unresolved() / classify_unresolved_age() /
is_stale_bucket() are pure functions extracted specifically so they can
be tested this way.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from pwc_first_session_funnel import (  # noqa: E402
    _is_real,
    classify_unresolved_age,
    is_stale_bucket,
    is_unresolved,
)


class TestIsUnresolved:
    def test_active_no_result_no_ended_at_is_unresolved(self):
        assert is_unresolved({"status": "active", "result": None, "ended_at": None}) is True

    def test_active_with_result_is_not_unresolved(self):
        assert is_unresolved({"status": "active", "result": "win", "ended_at": None}) is False

    def test_active_with_ended_at_is_not_unresolved(self):
        # A session can be status="active" in a stale doc but still have
        # an ended_at from an earlier write path -- must not double-count.
        assert is_unresolved({"status": "active", "result": None, "ended_at": "2026-08-01T00:00:00Z"}) is False

    def test_non_active_status_is_not_unresolved(self):
        assert is_unresolved({"status": "completed", "result": None, "ended_at": None}) is False

    def test_missing_fields_defaults_safely(self):
        # A malformed/legacy doc missing result and ended_at entirely --
        # should behave the same as them being explicitly None/falsy.
        assert is_unresolved({"status": "active"}) is True


class TestClassifyUnresolvedAge:
    def test_zero_hours_is_recent(self):
        assert classify_unresolved_age(0.0) == "unresolved_recent_under_2h"

    def test_just_under_two_hours_is_recent(self):
        assert classify_unresolved_age(1.99) == "unresolved_recent_under_2h"

    def test_exactly_two_hours_is_not_recent(self):
        # Boundary is a half-open interval [2, 24) -- exactly 2.0 must
        # NOT still count as "recent," or the boundary silently shifts.
        assert classify_unresolved_age(2.0) == "unresolved_2h_to_24h"

    def test_twelve_hours_is_2h_to_24h(self):
        assert classify_unresolved_age(12.0) == "unresolved_2h_to_24h"

    def test_exactly_24_hours_is_not_2h_to_24h(self):
        assert classify_unresolved_age(24.0) == "unresolved_1d_to_7d"

    def test_three_days_is_1d_to_7d(self):
        assert classify_unresolved_age(24 * 3) == "unresolved_1d_to_7d"

    def test_exactly_seven_days_is_over_7d(self):
        assert classify_unresolved_age(24 * 7) == "unresolved_over_7d"

    def test_real_production_minimum_lands_over_7d(self):
        # The real minimum age observed across 60 real signups' flagged
        # sessions (2026-08-07 run) was 244 hours -- regression-locks
        # that this specific real value still lands where the residency
        # doc says it does.
        assert classify_unresolved_age(244.0) == "unresolved_over_7d"

    def test_real_production_maximum_lands_over_7d(self):
        assert classify_unresolved_age(2612.8) == "unresolved_over_7d"

    def test_none_age_treated_conservatively_as_stalest(self):
        # No parseable created_at -- must not silently vanish from the
        # count. Conservative choice: treat as the stalest bucket.
        assert classify_unresolved_age(None) == "unresolved_over_7d"


class TestIsStaleBucket:
    def test_recent_bucket_is_not_stale(self):
        assert is_stale_bucket("unresolved_recent_under_2h") is False

    def test_every_other_bucket_is_stale(self):
        for bucket in ("unresolved_2h_to_24h", "unresolved_1d_to_7d", "unresolved_over_7d"):
            assert is_stale_bucket(bucket) is True


class TestIsReal:
    def test_real_user_passes(self):
        assert _is_real("user_8b599930d7ef", "someone@example.com") is True

    def test_test_marker_in_email_is_excluded(self):
        assert _is_real("user_abc123", "test@example.com") is False

    def test_demo_prefix_in_user_id_is_excluded(self):
        assert _is_real("demo_user_1", "someone@example.com") is False

    def test_dev_user_local_is_excluded(self):
        assert _is_real("dev_user_local", "dev@local") is False

    def test_none_email_does_not_crash(self):
        assert _is_real("user_8b599930d7ef", None) is True
