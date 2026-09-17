"""View-as lets an admin look. It must never let them act.

The feature exists because working out why a user's pages looked empty, while
sitting next to them, took nginx logs and three database queries. Being able
to open their view is worth a lot; being able to *change* their coaching
record from inside it would be worth less than nothing, because this product's
whole claim is that a player's coaching reflects that player's own moves.

So the rules that matter are the ones that say no, and they are what this
file pins:

  - any write, refused, whatever the endpoint
  - only a super admin, re-checked per request rather than at session start
  - a stolen or guessed cookie is not enough
  - a super admin is not a valid target
  - expiry is real

The write block lives in `get_current_user`, so a new endpoint inherits it
instead of opting in. `test_the_block_is_inherited_not_opted_into` is here so
nobody later "fixes" that by sprinkling checks per route.
"""
from __future__ import annotations

import asyncio
import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services import admin_view_as as view_as  # noqa: E402


class _Coll:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    async def find_one(self, query, projection=None):
        for row in self.rows:
            if all(row.get(k) == v for k, v in query.items()):
                return dict(row)
        return None

    async def insert_one(self, doc):
        self.rows.append(dict(doc))

    async def update_many(self, query, update):
        n = 0
        for row in self.rows:
            if all(row.get(k) == v for k, v in query.items()):
                row.update(update.get("$set") or {})
                n += 1
        return type("R", (), {"modified_count": n})()

    def find(self, query, projection=None):
        # Honour an exclusion projection, because that is exactly what the
        # audit view relies on to keep tokens out of the response. A fake
        # that ignored it would let the leak through and still pass.
        drop = {k for k, v in (projection or {}).items() if not v}
        rows = [{k: v for k, v in row.items() if k not in drop}
                for row in self.rows]

        class _Cur:
            def sort(self, *a, **k):
                return self

            async def to_list(self, n):
                return rows[:n]

        return _Cur()


class _DB:
    def __init__(self, users):
        self.users = _Coll(users)
        self._view = _Coll()

    def __getitem__(self, name):
        assert name == view_as.COLLECTION
        return self._view


class _U:
    def __init__(self, user_id, email, role):
        self.user_id, self.email, self.role = user_id, email, role


ADMIN = _U("admin_1", "boss@chessguru.ai", "super_admin")
NOT_ADMIN = _U("user_9", "someone@example.com", "user")
OTHER_ADMIN = _U("admin_2", "second@chessguru.ai", "super_admin")

USERS = [
    {"user_id": "admin_1", "email": "boss@chessguru.ai", "role": "super_admin"},
    {"user_id": "admin_2", "email": "second@chessguru.ai", "role": "super_admin"},
    {"user_id": "target_1", "email": "farhan@example.com", "name": "Farhan",
     "role": "user"},
]


def allow_all(email):
    return True


def allow_none(email):
    return False


def _db():
    return _DB(USERS)


def _start(db, admin=ADMIN, target="target_1"):
    return asyncio.run(view_as.start(db, admin=admin, target_user_id=target))


# ---------------------------------------------------------------- writes

def test_every_unsafe_method_is_a_write():
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert view_as.is_write(method, "/api/training/puzzle-attempt"), method


def test_reads_are_not_writes():
    for method in ("GET", "HEAD", "OPTIONS", "get"):
        assert not view_as.is_write(method, "/api/home/dashboard-v2"), method


def test_the_exit_is_the_only_write_allowed():
    """Otherwise the admin is locked inside the session they opened."""
    assert not view_as.is_write("DELETE", "/api/admin/view-as")
    assert not view_as.is_write("DELETE", "/api/admin/view-as/")
    # And nothing that merely looks like it.
    assert view_as.is_write("DELETE", "/api/admin/view-as/audit")
    assert view_as.is_write("POST", "/api/admin/users/x/view-as")


def test_the_block_is_inherited_not_opted_into():
    """It lives in the dependency every authenticated route already uses.

    Per-route checks would mean a route added next year is unprotected until
    somebody remembers. There is nothing to remember here.
    """
    src = io.open(BACKEND / "routes" / "auth.py", encoding="utf-8").read()
    assert "async def _resolve_view_as" in src
    assert "view_as.is_write(request.method, request.url.path)" in src
    assert "_resolve_view_as(request, real_user)" in src, (
        "get_current_user must route through it, or nothing is enforced"
    )


# ---------------------------------------------------------------- who

def test_a_non_admin_cannot_resolve_a_session_even_holding_the_token():
    db = _db()
    started = _start(db)
    stolen = started["token"]
    assert asyncio.run(view_as.resolve(db, stolen, NOT_ADMIN, allow_all)) is None


def test_another_admins_token_does_not_work():
    """Possession is not authority; the session is bound to who opened it."""
    db = _db()
    token = _start(db)["token"]
    assert asyncio.run(view_as.resolve(db, token, OTHER_ADMIN, allow_all)) is None


def test_losing_the_email_allowlist_ends_it_on_the_next_request():
    db = _db()
    token = _start(db)["token"]
    assert asyncio.run(view_as.resolve(db, token, ADMIN, allow_all)) is not None
    assert asyncio.run(view_as.resolve(db, token, ADMIN, allow_none)) is None


def test_losing_the_role_ends_it_on_the_next_request():
    db = _db()
    token = _start(db)["token"]
    demoted = _U("admin_1", "boss@chessguru.ai", "admin")
    assert asyncio.run(view_as.resolve(db, token, demoted, allow_all)) is None


def test_may_view_as_wants_both_conditions():
    assert view_as.may_view_as(ADMIN, allow_all)
    assert not view_as.may_view_as(ADMIN, allow_none)
    assert not view_as.may_view_as(NOT_ADMIN, allow_all)


# ---------------------------------------------------------------- targets

def test_a_super_admin_is_not_a_valid_target():
    """Nothing here should reach further than the caller already could."""
    db = _db()
    try:
        _start(db, target="admin_2")
        raise AssertionError("should have refused")
    except ValueError as exc:
        assert "super admin" in str(exc).lower()


def test_an_unknown_user_is_refused():
    db = _db()
    for target in ("nobody", "", "   "):
        try:
            _start(db, target=target)
            raise AssertionError(f"should have refused {target!r}")
        except ValueError:
            pass


# ---------------------------------------------------------------- lifetime

def test_a_fresh_session_resolves_to_the_target():
    db = _db()
    token = _start(db)["token"]
    session = asyncio.run(view_as.resolve(db, token, ADMIN, allow_all))
    assert session["target_user_id"] == "target_1"
    assert session["read_only"] is True


def test_an_expired_session_stops_resolving():
    db = _db()
    token = _start(db)["token"]
    for row in db._view.rows:
        row["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert asyncio.run(view_as.resolve(db, token, ADMIN, allow_all)) is None


def test_exiting_ends_it_immediately():
    db = _db()
    token = _start(db)["token"]
    assert asyncio.run(view_as.end(db, token)) is True
    assert asyncio.run(view_as.resolve(db, token, ADMIN, allow_all)) is None


def test_opening_a_second_session_retires_the_first():
    """Otherwise the first token keeps working, unseen, until it expires."""
    db = _db()
    first = _start(db)["token"]
    _start(db)
    assert asyncio.run(view_as.resolve(db, first, ADMIN, allow_all)) is None


def test_no_token_resolves_to_nothing():
    db = _db()
    for token in ("", None, "made-up"):
        assert asyncio.run(view_as.resolve(db, token, ADMIN, allow_all)) is None


# ---------------------------------------------------------------- audit

def test_the_target_session_token_is_never_touched():
    """The admin gets a fresh token. Nobody's real credential is read."""
    src = io.open(
        BACKEND / "services" / "admin_view_as.py", encoding="utf-8"
    ).read()
    assert "user_sessions" not in src, (
        "view-as must not read or mint real login sessions"
    )
    assert "secrets.token_urlsafe" in src


def test_the_trail_survives_the_session():
    db = _db()
    token = _start(db)["token"]
    asyncio.run(view_as.end(db, token))
    rows = asyncio.run(view_as.recent(db))
    assert len(rows) == 1
    assert rows[0]["admin_user_id"] == "admin_1"
    assert rows[0]["target_user_id"] == "target_1"
    assert rows[0]["ended_at"] is not None
    assert "view_token" not in rows[0], "the audit view must not leak tokens"
