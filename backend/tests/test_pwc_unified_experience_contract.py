import pytest

from coach_play.coach_game_session import CoachGameSession, SessionStatus
from services.pwc_experience import (
    LEGACY_EXPERIENCE,
    UNIFIED_V1_EXPERIENCE,
    preferred_experience_version,
    resolve_requested_experience_version,
    unified_v1_eligible,
)


def test_unified_experience_defaults_off(monkeypatch):
    monkeypatch.delenv("PWC_UNIFIED_EXPERIENCE_V1_ENABLED", raising=False)
    assert unified_v1_eligible({"role": "super_admin"}) is False
    assert preferred_experience_version({"role": "super_admin"}) == LEGACY_EXPERIENCE


def test_unified_experience_uses_role_cohort(monkeypatch):
    monkeypatch.setenv("PWC_UNIFIED_EXPERIENCE_V1_ENABLED", "true")
    monkeypatch.setenv(
        "PWC_UNIFIED_EXPERIENCE_V1_ROLES",
        "admin,super_admin",
    )
    assert unified_v1_eligible({"role": "admin"}) is True
    assert unified_v1_eligible({"role": "user"}) is False


def test_explicit_user_flag_obeys_global_kill_switch(monkeypatch):
    user = {
        "role": "user",
        "feature_flags": {"pwc_unified_experience_v1": True},
    }
    monkeypatch.setenv("PWC_UNIFIED_EXPERIENCE_V1_ENABLED", "false")
    assert unified_v1_eligible(user) is False

    monkeypatch.setenv("PWC_UNIFIED_EXPERIENCE_V1_ENABLED", "true")
    assert unified_v1_eligible(user) is True


def test_explicit_false_opts_admin_out(monkeypatch):
    monkeypatch.setenv("PWC_UNIFIED_EXPERIENCE_V1_ENABLED", "true")
    user = {
        "role": "super_admin",
        "feature_flags": {"pwc_unified_experience_v1": False},
    }
    assert unified_v1_eligible(user) is False


def test_legacy_client_is_not_silently_switched(monkeypatch):
    monkeypatch.setenv("PWC_UNIFIED_EXPERIENCE_V1_ENABLED", "true")
    assert (
        resolve_requested_experience_version(None, {"role": "super_admin"})
        == LEGACY_EXPERIENCE
    )


def test_unified_start_requires_eligibility(monkeypatch):
    monkeypatch.setenv("PWC_UNIFIED_EXPERIENCE_V1_ENABLED", "true")
    with pytest.raises(PermissionError):
        resolve_requested_experience_version(
            UNIFIED_V1_EXPERIENCE,
            {"role": "user"},
        )


def test_session_round_trip_pins_experience_version():
    session = CoachGameSession(
        session_id="session-1",
        user_id="user-1",
        status=SessionStatus.ACTIVE,
        user_color="white",
        experience_version=UNIFIED_V1_EXPERIENCE,
    )
    restored = CoachGameSession.from_dict(session.to_dict())
    assert restored.experience_version == UNIFIED_V1_EXPERIENCE
