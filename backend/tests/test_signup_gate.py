"""Invite-only signup gate.

The rule that must never break: CREATION is gated, AUTHENTICATION is not.
~120 existing users plus Farhan sign in through the same Google callback, and
they never reach the gate because the callback matches them on email first.

See docs/invite_only_signup_scope.md.
"""
import os

import pytest

from services import signup_gate


class _FakeCollection:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    async def find_one(self, query, projection=None):
        for row in self.rows:
            if all(row.get(k) == v for k, v in query.items()):
                return dict(row)
        return None

    async def update_one(self, query, update):
        for row in self.rows:
            if all(row.get(k) == v for k, v in query.items()):
                row.update(update.get("$set", {}))
                return type("R", (), {"matched_count": 1})()
        return type("R", (), {"matched_count": 0})()

    async def insert_one(self, doc):
        self.rows.append(dict(doc))


class _FakeDB:
    def __init__(self, rows=None):
        self._c = _FakeCollection(rows)

    def __getitem__(self, name):
        return self._c


@pytest.fixture(autouse=True)
def _closed_by_default(monkeypatch):
    monkeypatch.delenv("SIGNUPS_OPEN", raising=False)


def test_signups_are_closed_by_default():
    """Fail CLOSED. This ships while Mohit posts publicly; an accidentally
    open gate is the one failure we cannot have."""
    assert signup_gate.signups_open() is False


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_signups_open_flag(monkeypatch, value):
    monkeypatch.setenv("SIGNUPS_OPEN", value)
    assert signup_gate.signups_open() is True


@pytest.mark.parametrize("value", ["false", "0", "no", "", "maybe"])
def test_anything_else_keeps_it_closed(monkeypatch, value):
    monkeypatch.setenv("SIGNUPS_OPEN", value)
    assert signup_gate.signups_open() is False


@pytest.mark.asyncio
async def test_uninvited_email_cannot_sign_up():
    db = _FakeDB([])
    assert await signup_gate.signup_allowed(db, "stranger@example.com") is False


@pytest.mark.asyncio
async def test_invited_email_can_sign_up():
    db = _FakeDB([{"email": "friend@example.com", "status": "invited"}])
    assert await signup_gate.signup_allowed(db, "friend@example.com") is True


@pytest.mark.asyncio
async def test_pending_request_is_not_an_invite():
    """Asking is not being let in."""
    db = _FakeDB([{"email": "eager@example.com", "status": "pending"}])
    assert await signup_gate.signup_allowed(db, "eager@example.com") is False


@pytest.mark.asyncio
async def test_email_matching_ignores_case_and_spaces():
    db = _FakeDB([{"email": "friend@example.com", "status": "invited"}])
    assert await signup_gate.signup_allowed(db, "  Friend@Example.COM ") is True


@pytest.mark.asyncio
async def test_open_signups_let_anyone_in(monkeypatch):
    monkeypatch.setenv("SIGNUPS_OPEN", "true")
    db = _FakeDB([])
    assert await signup_gate.signup_allowed(db, "anyone@example.com") is True


@pytest.mark.asyncio
async def test_empty_email_is_never_allowed():
    db = _FakeDB([])
    for value in (None, "", "   "):
        assert await signup_gate.signup_allowed(db, value) is False


@pytest.mark.asyncio
async def test_requesting_twice_does_not_downgrade_an_invite():
    """Someone already invited who fills the form again must stay invited."""
    db = _FakeDB([{"email": "friend@example.com", "status": "invited", "name": "F"}])
    await signup_gate.record_request(db, "friend@example.com", name="F again")
    assert await signup_gate.signup_allowed(db, "friend@example.com") is True


@pytest.mark.asyncio
async def test_a_new_request_starts_pending():
    db = _FakeDB([])
    out = await signup_gate.record_request(db, "New@Example.com", name="New")
    assert out["status"] == "pending"
    assert out["email"] == "new@example.com"
    assert await signup_gate.signup_allowed(db, "new@example.com") is False
