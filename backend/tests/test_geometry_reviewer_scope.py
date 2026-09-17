"""A geometry reviewer reaches the review queue and nothing else.

Mohit 2026-09-17: "can you just give him access to this page only and not
anything else?" Admin is all-or-nothing across 49 endpoints, so the whole
point of the narrow gate is what it REFUSES. That is what this pins.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import HTTPException  # noqa: E402

from routes.admin import (  # noqa: E402
    require_admin,
    require_geometry_reviewer,
    require_super_admin,
)

REVIEWER = "farhan.coach@example.com"


class _User:
    def __init__(self, email, role="user"):
        self.email = email
        self.role = role
        self.user_id = "u_" + str(email or "anon").split("@")[0]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def _allowlist(monkeypatch):
    monkeypatch.setenv("GEOMETRY_REVIEWER_EMAILS", f" {REVIEWER.upper()} , other@x.com ")


def test_reviewer_reaches_the_geometry_queue():
    user = _User(REVIEWER)
    assert _run(require_geometry_reviewer(user)) is user


def test_reviewer_is_refused_every_other_admin_surface():
    user = _User(REVIEWER)
    for gate in (require_admin, require_super_admin):
        with pytest.raises(HTTPException) as caught:
            _run(gate(user))
        assert caught.value.status_code == 403


def test_promoting_the_reviewer_to_admin_still_does_not_open_admin():
    """The email allowlist is the second lock; a role alone must not suffice."""
    user = _User(REVIEWER, role="admin")
    with pytest.raises(HTTPException) as caught:
        _run(require_admin(user))
    assert caught.value.status_code == 403


def test_a_stranger_gets_nothing():
    user = _User("nobody@example.com")
    with pytest.raises(HTTPException) as caught:
        _run(require_geometry_reviewer(user))
    assert caught.value.status_code == 403


def test_owner_keeps_the_queue():
    owner = _User("bhutramohit@gmail.com", role="super_admin")
    assert _run(require_geometry_reviewer(owner)) is owner


def test_empty_allowlist_locks_everyone_out(monkeypatch):
    monkeypatch.setenv("GEOMETRY_REVIEWER_EMAILS", "")
    with pytest.raises(HTTPException):
        _run(require_geometry_reviewer(_User(REVIEWER)))


def test_a_blank_email_is_never_allowed(monkeypatch):
    """An empty env entry must not turn into a wildcard for empty emails."""
    monkeypatch.setenv("GEOMETRY_REVIEWER_EMAILS", " , ,")
    for email in ("", None, "   "):
        with pytest.raises(HTTPException):
            _run(require_geometry_reviewer(_User(email)))
