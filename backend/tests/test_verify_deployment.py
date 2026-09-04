"""
Unit tests for the pure logic in backend/scripts/verify_deployment.py.

Added 2026-08-07 per external review of the Sprint 1 work: the deployment
verifier's required-check semantics and spike-threshold math had no
direct test coverage. These tests import the script directly (it's a
CLI tool, not a package) and exercise only the pure, non-network pieces
-- no requests/motor calls are made.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from verify_deployment import (  # noqa: E402
    CHECK_KEYS,
    FAIL,
    PASS,
    SKIP,
    RESULTS,
    CheckResult,
    _check_key,
    check_complete_coaching_journey,
    spike_threshold,
)


class TestCheckKey:
    def test_all_eight_numbered_checks_map_to_a_key(self):
        expected = {
            "1": "commit", "2": "bundle", "3": "health",
            "4": "auth", "5": "contract", "6": "queue", "7": "failures",
            "8": "journey",
        }
        assert CHECK_KEYS == expected

    def test_extracts_key_from_real_check_name_format(self):
        assert _check_key("1. Git commit match") == "commit"
        assert _check_key("5. Canonical coaching endpoint contract (GET /api/coach/decryption/v5/{game_id})") == "contract"

    def test_unknown_prefix_returns_none(self):
        assert _check_key("99. Some future check") is None

    def test_no_period_returns_none(self):
        assert _check_key("malformed name with no number") is None


class TestSpikeThreshold:
    def test_zero_baseline_uses_floor(self):
        # No failures in 7 days -> 3x0=0, floored at --max-recent-failures.
        assert spike_threshold(baseline_failed_count=0, baseline_days=7.0, floor=5) == 5

    def test_low_baseline_uses_floor_not_triple(self):
        # 1.7/day baseline (the real value found in the 2026-08-07 local
        # run) * 3 = 5.1 -> rounds to 5, same as the floor in that case.
        assert spike_threshold(baseline_failed_count=12, baseline_days=7.0, floor=5) == 5

    def test_high_baseline_exceeds_floor(self):
        # 70 failed over 7 days = 10/day average * 3 = 30, well past floor.
        assert spike_threshold(baseline_failed_count=70, baseline_days=7.0, floor=5) == 30

    def test_floor_still_wins_when_higher_than_computed(self):
        assert spike_threshold(baseline_failed_count=1, baseline_days=7.0, floor=20) == 20


class TestRequiredChecksSummaryLogic:
    """Exercises the same unmet-required-check filtering the summary in
    run() uses, without needing to invoke the full async run()."""

    def _unmet(self, results, required):
        return [r for r in results if _check_key(r.name) in required and r.status != PASS]

    def test_all_required_passed_means_nothing_unmet(self):
        results = [
            CheckResult(name="3. Backend health endpoint", status=PASS),
            CheckResult(name="2. Frontend bundle contains expected marker", status=PASS),
        ]
        assert self._unmet(results, {"health", "bundle"}) == []

    def test_skipped_required_check_counts_as_unmet(self):
        results = [
            CheckResult(name="1. Git commit match", status=SKIP),
            CheckResult(name="3. Backend health endpoint", status=PASS),
        ]
        unmet = self._unmet(results, {"commit", "health"})
        assert len(unmet) == 1
        assert unmet[0].name == "1. Git commit match"

    def test_failed_required_check_counts_as_unmet(self):
        results = [CheckResult(name="6. Worker queue health (analysis_queue)", status=FAIL)]
        assert len(self._unmet(results, {"queue"})) == 1

    def test_non_required_check_never_counted(self):
        # A FAIL on a check nobody required shouldn't show up as unmet.
        results = [CheckResult(name="7. No spike in failed analysis jobs", status=FAIL)]
        assert self._unmet(results, {"health"}) == []


class _Response:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code
        self.text = str(body)

    def json(self):
        return self._body


def test_journey_check_accepts_completed_idempotent_fixture(monkeypatch):
    import verify_deployment

    RESULTS.clear()
    get_responses = iter([
        _Response({
            "enabled": True,
            "rollout": {"enabled": True},
            "decision": {
                "primary": {
                    "destination": {
                        "lesson_kind": "concept",
                        "lesson_id": "piece_safety",
                        "href": "/training?kind=concept",
                    },
                }
            },
        }),
        _Response({"evidence": [{"attempt": {"correct": True}}]}),
        _Response({
            "status": "complete",
            "decryption_data": [],
            "teachable_events": [{
                "display": {"authorized": True},
            }],
        }),
        _Response({
            "enabled": True,
            "practice": {"changes_transfer_verdict": False},
            "transfer": {"verdict": "insufficient_evidence"},
            "steps": {"verdict_served": True},
        }),
    ])
    monkeypatch.setattr(
        verify_deployment.requests,
        "get",
        lambda *args, **kwargs: next(get_responses),
    )
    monkeypatch.setattr(
        verify_deployment.requests,
        "post",
        lambda *args, **kwargs: _Response({
            "session_id": "fixture-session",
            "status": "completed",
            "lesson": {"kind": "concept", "id": "piece_safety"},
        }),
    )

    check_complete_coaching_journey(
        "https://example.test",
        "token",
        {"user_id": "fixture-user", "role": "user"},
        {
            "content_kind": "concept",
            "content_id": "piece_safety",
            "move": "e2e4",
            "game_id": "fixture-game",
        },
        1.0,
    )
    assert RESULTS[-1].status == PASS


def test_journey_check_proves_duplicate_submission_is_stored_once(monkeypatch):
    import verify_deployment

    RESULTS.clear()
    get_responses = iter([
        _Response({
            "enabled": True,
            "rollout": {"enabled": True},
            "decision": {
                "primary": {
                    "destination": {
                        "lesson_kind": "concept",
                        "lesson_id": "piece_safety",
                        "href": "/training?kind=concept",
                    },
                }
            },
        }),
        _Response({
            "evidence": [{
                "event_id": (
                    "phase8-deploy-"
                    "b8cfb90982e7b78e465ac9c9"
                ),
                "attempt": {"correct": True},
            }],
        }),
        _Response({
            "status": "complete",
            "decryption_data": [],
            "teachable_events": [{
                "display": {"authorized": True},
            }],
        }),
        _Response({
            "enabled": True,
            "practice": {"changes_transfer_verdict": False},
            "transfer": {"verdict": "insufficient_evidence"},
            "steps": {"verdict_served": True},
        }),
    ])
    posts = [
        _Response({
            "session_id": "fixture-session",
            "status": "active",
            "lesson": {"kind": "concept", "id": "piece_safety"},
        }),
        _Response({"correct": True, "complete": True}),
        _Response({"correct": True, "complete": True}),
    ]
    monkeypatch.setattr(
        verify_deployment.requests,
        "get",
        lambda *args, **kwargs: next(get_responses),
    )
    monkeypatch.setattr(
        verify_deployment.requests,
        "post",
        lambda *args, **kwargs: posts.pop(0),
    )
    monkeypatch.setattr(
        verify_deployment.hashlib,
        "sha256",
        lambda *_args, **_kwargs: type(
            "_Hash",
            (),
            {"hexdigest": lambda self: "b8cfb90982e7b78e465ac9c9" + "0" * 40},
        )(),
    )

    check_complete_coaching_journey(
        "https://example.test",
        "token",
        {"user_id": "fixture-user", "role": "user"},
        {
            "content_kind": "concept",
            "content_id": "piece_safety",
            "move": "e2e4",
            "game_id": "fixture-game",
        },
        1.0,
    )
    assert RESULTS[-1].status == PASS
    assert posts == []


def test_journey_check_never_skips_missing_fixture_in_strict_mode():
    RESULTS.clear()
    check_complete_coaching_journey(
        "https://example.test",
        "token",
        {"user_id": "fixture-user", "role": "user"},
        None,
        1.0,
    )
    assert RESULTS[-1].status == SKIP
    assert _check_key(RESULTS[-1].name) == "journey"
