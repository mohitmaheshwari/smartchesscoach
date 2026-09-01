import pytest
import asyncio
from types import SimpleNamespace

from services.personal_curriculum import (
    ContractViolation,
    _home_replay_diagnostic_projection,
    derive_home_diagnostic_result,
)


def _attempt(target, *, sound="sound", helped=False, reason=True):
    return {
        "target_result": target,
        "soundness": {"status": sound},
        "substantive_help": helped,
        "reasoning_consistent": reason,
    }


def test_two_independent_passes_with_matching_reasons_show_controlled_transfer():
    result = derive_home_diagnostic_result((
        _attempt("pass"),
        _attempt("pass"),
    )).public_dict()
    assert result["conclusion"] == "controlled_transfer"
    assert result["next_action"] == "quiet_coached_application"
    assert result["real_game_evidence"] == "not_measured"


def test_second_position_failure_means_familiar_position_only():
    result = derive_home_diagnostic_result((
        _attempt("pass"),
        _attempt("fail", reason=False),
    ))
    assert result.conclusion.value == "familiar_position_only"


def test_substantive_help_caps_result_at_prompted_recognition():
    result = derive_home_diagnostic_result((
        _attempt("pass", helped=True),
        _attempt("pass"),
    ))
    assert result.conclusion.value == "prompted_recognition"


def test_two_failed_target_checks_are_current_learning_need():
    result = derive_home_diagnostic_result((
        _attempt("fail", reason=False),
        _attempt("fail", reason=False),
    ))
    assert result.conclusion.value == "current_learning_need"


def test_separate_soundness_problem_does_not_erase_target_transfer():
    result = derive_home_diagnostic_result((
        _attempt("pass", sound="serious_problem"),
        _attempt("pass"),
    ))
    assert result.conclusion.value == "controlled_transfer"
    assert result.separate_soundness_issue is True


def test_unmeasured_proof_fails_closed_to_no_conclusion():
    result = derive_home_diagnostic_result((
        _attempt("pass"),
        _attempt("unmeasured", sound="unmeasured", reason=None),
    ))
    assert result.conclusion.value == "no_conclusion"


def test_contract_rejects_anything_other_than_exactly_two_attempts():
    with pytest.raises(ContractViolation):
        derive_home_diagnostic_result((_attempt("pass"),))


class _OneCollection:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, query, projection=None, sort=None):
        return self.doc


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, length=None):
        return list(self.rows)


class _FindCollection:
    def __init__(self, rows):
        self.rows = rows
        self.query = None

    def find(self, query, projection=None):
        self.query = query
        return _Cursor(self.rows)


def test_home_projection_requires_enrollment_and_returns_redacted_session():
    descriptor = {
        "kind": "concept",
        "id": "piece_safety",
        "title": "SECRET LESSON TITLE",
        "rule": "SECRET RULE",
        "items": [{
            "item_id": "diagnostic-position-1",
            "fen": "8/8/8/8/8/8/4K3/7k w - - 0 1",
            "orientation": "white",
            "stage": "diagnose",
            "source": "own_game",
            "source_ref": "SECRET GAME ID",
            "_expected_uci": "e2f3",
        }],
    }
    session = {
        "session_id": "s1",
        "user_id": "u1",
        "lesson_type": "personalized_curriculum",
        "delivery_mode": "blind_diagnostic",
        "status": "active",
        "current_index": 0,
        "descriptor": descriptor,
        "events": [],
    }
    db = SimpleNamespace(
        users=_OneCollection({
            "feature_flags": {"home_replay_diagnostic": {"enabled": True}}
        }),
        learning_sessions=_OneCollection(session),
    )
    primary = SimpleNamespace(
        detector_quality_id="gap:piece_safety:destination_safety_exact"
    )

    result = asyncio.run(_home_replay_diagnostic_projection(
        db,
        "u1",
        primary,
        env={"HOME_REPLAY_DIAGNOSTIC_ENABLED": "true"},
    ))
    rendered = str(result)
    assert result["state"] == "active"
    assert "lesson" not in result["session"]
    assert "SECRET LESSON TITLE" not in rendered
    assert "SECRET RULE" not in rendered
    assert "SECRET GAME ID" not in rendered


def test_home_projection_is_absent_when_user_is_not_enrolled():
    db = SimpleNamespace(
        users=_OneCollection({"feature_flags": {}}),
        learning_sessions=_OneCollection(None),
    )
    primary = SimpleNamespace(
        detector_quality_id="gap:piece_safety:destination_safety_exact"
    )
    result = asyncio.run(_home_replay_diagnostic_projection(
        db,
        "u1",
        primary,
        env={"HOME_REPLAY_DIAGNOSTIC_ENABLED": "true"},
    ))
    assert result is None


def test_completed_diagnostic_reports_only_a_verified_later_miss():
    session = {
        "session_id": "s2",
        "user_id": "u1",
        "lesson_type": "personalized_curriculum",
        "delivery_mode": "blind_diagnostic",
        "status": "completed",
        "completed_at": "2026-09-02T10:00:00+00:00",
        "current_index": 2,
        "descriptor": {"items": []},
        "events": [],
        "diagnostic_result": {
            "conclusion": "controlled_transfer",
            "real_game_evidence": "not_measured",
        },
    }
    observations = _FindCollection([{"game_id": "g-new"}])
    games = _FindCollection([{
        "game_id": "g-new",
        "date_played": "2026.09.03",
    }])
    db = SimpleNamespace(
        users=_OneCollection({
            "feature_flags": {"home_replay_diagnostic": {"enabled": True}}
        }),
        learning_sessions=_OneCollection(session),
        move_observations=observations,
        games=games,
    )
    primary = SimpleNamespace(
        detector_quality_id="gap:piece_safety:destination_safety_exact"
    )

    result = asyncio.run(_home_replay_diagnostic_projection(
        db,
        "u1",
        primary,
        env={"HOME_REPLAY_DIAGNOSTIC_ENABLED": "true"},
    ))
    assert result["state"] == "later_miss"
    assert result["session"]["diagnostic_result"]["real_game_evidence"] == "missed"
    assert observations.query["destination_safety_exact.fires"] is True


def test_reprocessed_old_game_is_not_reported_as_a_later_miss():
    session = {
        "session_id": "s3",
        "user_id": "u1",
        "lesson_type": "personalized_curriculum",
        "delivery_mode": "blind_diagnostic",
        "status": "completed",
        "completed_at": "2026-09-02T10:00:00+00:00",
        "current_index": 2,
        "descriptor": {"items": []},
        "events": [],
        "diagnostic_result": {
            "conclusion": "controlled_transfer",
            "real_game_evidence": "not_measured",
        },
    }
    db = SimpleNamespace(
        users=_OneCollection({
            "feature_flags": {"home_replay_diagnostic": {"enabled": True}}
        }),
        learning_sessions=_OneCollection(session),
        move_observations=_FindCollection([{"game_id": "g-old"}]),
        games=_FindCollection([{
            "game_id": "g-old",
            "date_played": "2026.08.29",
        }]),
    )
    primary = SimpleNamespace(
        detector_quality_id="gap:piece_safety:destination_safety_exact"
    )

    result = asyncio.run(_home_replay_diagnostic_projection(
        db,
        "u1",
        primary,
        env={"HOME_REPLAY_DIAGNOSTIC_ENABLED": "true"},
    ))
    assert result["state"] == "result"
    assert result["session"]["diagnostic_result"]["real_game_evidence"] == "not_measured"
