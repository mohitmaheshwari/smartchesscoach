from pathlib import Path

import pytest

from coach_play.coach_game_session import CoachGameSession, SessionStatus
from services.pwc_experience import (
    LEGACY_EXPERIENCE,
    PWC_V2_SHADOW_FEATURE_KEY,
    UNIFIED_V1_EXPERIENCE,
    preferred_experience_version,
    pwc_v2_shadow_eligible,
    resolve_requested_experience_version,
    unified_v1_eligible,
)


def test_unified_experience_defaults_off(monkeypatch):
    monkeypatch.delenv("PWC_UNIFIED_EXPERIENCE_V1_ENABLED", raising=False)
    assert unified_v1_eligible({"role": "super_admin"}) is False
    assert preferred_experience_version({"role": "super_admin"}) == LEGACY_EXPERIENCE


def test_v2_shadow_defaults_off_and_cannot_select_an_experience(monkeypatch):
    monkeypatch.delenv("PWC_V2_SHADOW_ENABLED", raising=False)
    user = {"role": "super_admin"}
    assert pwc_v2_shadow_eligible(user) is False
    assert preferred_experience_version(user) == LEGACY_EXPERIENCE


def test_v2_shadow_uses_fail_closed_role_and_user_flags(monkeypatch):
    monkeypatch.setenv("PWC_V2_SHADOW_ENABLED", "true")
    monkeypatch.setenv("PWC_V2_SHADOW_ROLES", "admin,super_admin")
    assert pwc_v2_shadow_eligible({"role": "admin"}) is True
    assert pwc_v2_shadow_eligible({"role": "user"}) is False
    assert pwc_v2_shadow_eligible({
        "role": "user",
        "feature_flags": {PWC_V2_SHADOW_FEATURE_KEY: True},
    }) is True
    assert pwc_v2_shadow_eligible({
        "role": "super_admin",
        "feature_flags": {PWC_V2_SHADOW_FEATURE_KEY: False},
    }) is False


def test_v2_shadow_user_flag_obeys_global_kill_switch(monkeypatch):
    monkeypatch.setenv("PWC_V2_SHADOW_ENABLED", "false")
    assert pwc_v2_shadow_eligible({
        "role": "user",
        "feature_flags": {PWC_V2_SHADOW_FEATURE_KEY: True},
    }) is False


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
    monkeypatch.setenv(
        "PWC_UNIFIED_EXPERIENCE_V1_ROLES",
        "admin,super_admin",
    )
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


def test_session_round_trip_pins_v2_shadow_without_changing_experience():
    session = CoachGameSession(
        session_id="session-shadow",
        user_id="user-1",
        status=SessionStatus.ACTIVE,
        user_color="white",
        experience_version=UNIFIED_V1_EXPERIENCE,
        pwc_v2_shadow_enabled=True,
        coaching_decisions=[{
            "move_key": "1:e2e4",
            "text": "Visible V1 decision",
            "pwc_v2_shadow": {"player_visible": False},
        }],
    )
    restored = CoachGameSession.from_dict(session.to_dict())
    assert restored.experience_version == UNIFIED_V1_EXPERIENCE
    assert restored.pwc_v2_shadow_enabled is True
    public = restored.to_public_dict()
    assert "pwc_v2_shadow_enabled" not in public
    assert "pwc_v2_shadow" not in public["coaching_decisions"][0]
    assert public["coaching_decisions"][0]["text"] == "Visible V1 decision"


def test_docker_services_receive_unified_rollout_flags():
    repo_root = Path(__file__).resolve().parents[2]
    expected = {
        "PWC_UNIFIED_EXPERIENCE_V1_ENABLED=${PWC_UNIFIED_EXPERIENCE_V1_ENABLED:-false}",
        "PWC_UNIFIED_EXPERIENCE_V1_ROLES=${PWC_UNIFIED_EXPERIENCE_V1_ROLES:-admin,super_admin}",
        "PWC_V2_SHADOW_ENABLED=${PWC_V2_SHADOW_ENABLED:-false}",
        "PWC_V2_SHADOW_ROLES=${PWC_V2_SHADOW_ROLES:-admin,super_admin}",
    }

    for compose_name in ("docker-compose.yml", "docker-compose.prod.yml"):
        compose_text = (repo_root / compose_name).read_text(encoding="utf-8")
        for declaration in expected:
            assert declaration in compose_text, (
                f"{compose_name} does not pass {declaration.split('=', 1)[0]} "
                "to its backend service"
            )

    production_text = (repo_root / "docker-compose.prod.yml").read_text(
        encoding="utf-8"
    )
    assert (
        "COACHING_CONTEXT_V1_ENABLED=${COACHING_CONTEXT_V1_ENABLED:-false}"
        in production_text
    )
    assert (
        "COACHING_CONTEXT_V1_ROLES=${COACHING_CONTEXT_V1_ROLES:-admin,super_admin}"
        in production_text
    )


def test_production_override_disables_only_services_defined_by_the_base_compose():
    repo_root = Path(__file__).resolve().parents[2]
    base_text = (repo_root / "docker-compose.yml").read_text(encoding="utf-8")
    production_text = (repo_root / "docker-compose.prod.yml").read_text(
        encoding="utf-8"
    )
    production_services = production_text.split("\nvolumes:", 1)[0]

    assert "\n  frontend-builder:\n" in base_text
    assert "\n  frontend-builder:\n" in production_services
    assert "\n  frontend:\n" not in production_services
