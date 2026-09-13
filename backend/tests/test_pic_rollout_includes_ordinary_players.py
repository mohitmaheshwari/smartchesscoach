"""An absent role means an ordinary player, so PIC evidence must reach them.

games.pic_evidence existed on ONE game out of 14,905. Two causes compounded:

  1. PERSONAL_IMPROVEMENT_CYCLE_ROLES defaulted to "admin,super_admin", so the
     evidence chain that backs "we measured your improvement" was written for
     admins only -- and admins barely play.
  2. 123 of 126 production accounts store role: None, so even after adding
     "user" to the allowlist nothing changed: a bare `in` test never matches
     None.

Every admin-EXCLUSION check already normalises an absent role to "user"
(capture_phase8_baselines, configure_phase8_pilot,
migrate_destination_safety_focus, report_phase8_release). This inclusion check
was the one place that did not, so absent-role players could be excluded from a
feature but never included in one.
"""
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services import focus_bridge  # noqa: E402


@pytest.fixture
def roles_include_user(monkeypatch):
    monkeypatch.setenv("PERSONAL_IMPROVEMENT_CYCLE_ROLES", "admin,super_admin,user")
    monkeypatch.setattr(focus_bridge, "_pic_flag_enabled", lambda: True)


@pytest.mark.parametrize("role", [None, "", "   ", "user", "USER", " User "])
def test_ordinary_players_are_eligible(roles_include_user, role):
    """None is the shape 123 of 126 real accounts actually have."""
    assert focus_bridge._pic_fields_eligible(role) is True


@pytest.mark.parametrize("role", ["admin", "super_admin"])
def test_privileged_roles_remain_eligible(roles_include_user, role):
    assert focus_bridge._pic_fields_eligible(role) is True


def test_a_role_outside_the_allowlist_is_refused(monkeypatch):
    monkeypatch.setenv("PERSONAL_IMPROVEMENT_CYCLE_ROLES", "admin,super_admin")
    monkeypatch.setattr(focus_bridge, "_pic_flag_enabled", lambda: True)
    assert focus_bridge._pic_fields_eligible(None) is False, (
        "with 'user' absent from the allowlist an ordinary player stays out -- "
        "the allowlist must still mean something"
    )
    assert focus_bridge._pic_fields_eligible("admin") is True


def test_the_flag_is_still_an_absolute_kill_switch(monkeypatch):
    monkeypatch.setenv("PERSONAL_IMPROVEMENT_CYCLE_ROLES", "admin,super_admin,user")
    monkeypatch.setattr(focus_bridge, "_pic_flag_enabled", lambda: False)
    for role in (None, "user", "admin", "super_admin"):
        assert focus_bridge._pic_fields_eligible(role) is False


def test_the_normalisation_matches_the_exclusion_checks(monkeypatch):
    """The inconsistency this fixes: exclusion normalised, inclusion did not."""
    monkeypatch.setenv("PERSONAL_IMPROVEMENT_CYCLE_ROLES", "user")
    monkeypatch.setattr(focus_bridge, "_pic_flag_enabled", lambda: True)
    # the same expression the exclusion checks use
    assert str(None or "user").strip().lower() == "user"
    assert focus_bridge._pic_fields_eligible(None) is True
