"""Forgot password, change password, delete account. Found missing on 2026-11-07."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import BackgroundTasks, HTTPException, Response
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes import auth  # noqa: E402


class _Me:
    user_id = "u1"


class _Request:
    class state:
        view_as = None


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def db(monkeypatch):
    database = AsyncMongoMockClient().db
    monkeypatch.setattr(auth, "db", database)
    return database


def _account(db, **extra):
    doc = {"user_id": "u1", "email": "asha@example.com", "name": "Asha",
           "password_hash": auth.pwd_context.hash("old-password"), **extra}
    run(_insert(db, doc))


async def _insert(db, doc):
    await db.users.insert_one(doc)


@pytest.fixture
def mail(monkeypatch):
    sent = []

    async def fake(to, subject, html):
        sent.append((to, subject, html))
        return True

    import services.digest_email_service as digest
    monkeypatch.setattr(digest, "_send_smtp", fake)
    return sent


def _token_from(mail):
    html = mail[-1][2]
    return html.split("code=")[1].split('"')[0]


def test_the_answer_is_the_same_for_an_unknown_email(db, mail):
    _account(db)
    tasks = BackgroundTasks()
    known = run(auth.forgot_password(auth.ForgotPasswordRequest(email="ASHA@example.com"), tasks))
    assert len(tasks.tasks) == 1
    tasks = BackgroundTasks()
    unknown = run(auth.forgot_password(auth.ForgotPasswordRequest(email="nobody@example.com"), tasks))
    assert known == unknown == {"ok": True}
    assert not tasks.tasks


def test_a_reset_link_works_once_and_signs_everyone_out(db, mail):
    _account(db)
    user = run(db.users.find_one({"user_id": "u1"}))
    run(auth._send_password_help(user, "asha@example.com"))
    token = _token_from(mail)
    run(db.user_sessions.insert_one({"user_id": "u1", "session_token": "s"}))
    assert run(auth.reset_password(auth.ResetPasswordRequest(token=token, password="new-password")))["ok"]
    user = run(db.users.find_one({"user_id": "u1"}))
    assert auth.pwd_context.verify("new-password", user["password_hash"])
    assert run(db.user_sessions.count_documents({"user_id": "u1"})) == 0
    with pytest.raises(HTTPException) as e:
        run(auth.reset_password(auth.ResetPasswordRequest(token=token, password="another-password")))
    assert e.value.status_code == 400


def test_the_token_itself_is_not_stored(db, mail):
    _account(db)
    user = run(db.users.find_one({"user_id": "u1"}))
    run(auth._send_password_help(user, "asha@example.com"))
    row = run(db.password_resets.find_one({}))
    assert _token_from(mail) not in str(row)


def test_an_expired_link_does_not_work(db, mail):
    _account(db)
    user = run(db.users.find_one({"user_id": "u1"}))
    run(auth._send_password_help(user, "asha@example.com"))
    run(db.password_resets.update_one({}, {"$set": {
        "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)}}))
    with pytest.raises(HTTPException):
        run(auth.reset_password(auth.ResetPasswordRequest(token=_token_from(mail), password="new-password")))


def test_reset_mail_is_limited_each_hour(db, mail):
    _account(db)
    user = run(db.users.find_one({"user_id": "u1"}))
    for _ in range(auth.MAX_RESETS_PER_HOUR + 2):
        run(auth._send_password_help(user, "asha@example.com"))
    assert len(mail) == auth.MAX_RESETS_PER_HOUR


def test_a_google_account_is_pointed_to_google(db, mail):
    run(db.users.insert_one({"user_id": "u1", "email": "g@example.com"}))
    user = run(db.users.find_one({"user_id": "u1"}))
    run(auth._send_password_help(user, "g@example.com"))
    assert "Google" in mail[0][2] and "code=" not in mail[0][2]
    assert run(db.password_resets.count_documents({})) == 0


def test_a_short_password_is_refused(db, mail):
    with pytest.raises(HTTPException) as e:
        run(auth.reset_password(auth.ResetPasswordRequest(token="x", password="short")))
    assert "8 characters" in e.value.detail


def test_change_password_needs_the_current_one(db):
    _account(db)
    with pytest.raises(HTTPException) as e:
        run(auth.change_password(auth.ChangePasswordRequest(current_password="wrong", new_password="new-password"),
                                 Response(), _Me()))
    assert e.value.status_code == 400
    assert run(auth.change_password(auth.ChangePasswordRequest(
        current_password="old-password", new_password="new-password"), Response(), _Me()))["ok"]
    user = run(db.users.find_one({"user_id": "u1"}))
    assert auth.pwd_context.verify("new-password", user["password_hash"])


def test_change_password_tells_a_google_user_why_not(db):
    run(db.users.insert_one({"user_id": "u1", "email": "g@example.com"}))
    with pytest.raises(HTTPException) as e:
        run(auth.change_password(auth.ChangePasswordRequest(current_password="", new_password="new-password"),
                                 Response(), _Me()))
    assert e.value.status_code == 409 and "Google" in e.value.detail


def _delete(email="asha@example.com", password="old-password", request=_Request):
    return run(auth.delete_account(auth.DeleteAccountRequest(confirm_email=email, password=password),
                                   request, Response(), _Me()))


def test_delete_needs_the_email_and_the_password(db):
    _account(db)
    for email, password in (("other@example.com", "old-password"), ("asha@example.com", "wrong")):
        with pytest.raises(HTTPException) as e:
            _delete(email, password)
        assert e.value.status_code == 400
    assert run(db.users.count_documents({})) == 1


def test_delete_removes_the_person_and_only_them(db):
    _account(db)
    run(db.users.insert_one({"user_id": "u2", "email": "x@example.com"}))
    run(db.games.insert_many([{"user_id": "u1", "game_id": "g1"}, {"user_id": "u2", "game_id": "g2"}]))
    run(db.game_analyses.insert_many([{"user_id": "u1", "game_id": "g1"}, {"user_id": "u2", "game_id": "g2"}]))
    run(db.user_sessions.insert_one({"user_id": "u1", "session_token": "s"}))
    run(db.community_puzzles.insert_many([{"shared_by": "u1"}, {"shared_by": "u2"}]))
    run(db.payment_intents.insert_one({"user_id": "u1", "amount": 1}))
    assert _delete()["ok"]
    assert run(db.users.count_documents({})) == 1
    assert run(db.games.count_documents({})) == 1
    assert run(db.game_analyses.count_documents({})) == 1
    assert run(db.user_sessions.count_documents({})) == 0
    assert run(db.community_puzzles.count_documents({})) == 1
    assert run(db.payment_intents.count_documents({})) == 1  # tax record, see the privacy page


def test_an_academy_owner_must_remove_the_children_first(db):
    _account(db)
    run(db.academy_staff.insert_one({"user_id": "u1", "academy_id": "a1", "role": "owner"}))
    run(db.academies.insert_one({"academy_id": "a1"}))
    run(db.academy_students.insert_one({"academy_id": "a1", "deleted_at": None}))
    with pytest.raises(HTTPException) as e:
        _delete()
    assert e.value.status_code == 409 and "children" in e.value.detail
    run(db.academy_students.update_one({}, {"$set": {"deleted_at": "now"}}))
    assert _delete()["ok"]
    assert run(db.academies.count_documents({})) == 0


def test_an_admin_and_a_view_as_session_cannot_delete(db):
    _account(db, role="admin")
    with pytest.raises(HTTPException) as e:
        _delete()
    assert e.value.status_code == 409

    class Viewing:
        class state:
            view_as = {"admin_user_id": "boss"}

    with pytest.raises(HTTPException) as e:
        _delete(request=Viewing)
    assert e.value.status_code == 403
