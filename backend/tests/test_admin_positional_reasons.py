from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

try:
    import bcrypt  # noqa: F401
except ModuleNotFoundError:
    bcrypt_stub = ModuleType("bcrypt")
    bcrypt_stub.__version__ = "test-stub"
    sys.modules["bcrypt"] = bcrypt_stub

try:
    from passlib.context import CryptContext  # noqa: F401
except ModuleNotFoundError:
    passlib_stub = ModuleType("passlib")
    passlib_context_stub = ModuleType("passlib.context")

    class _CryptContext:
        def __init__(self, *args, **kwargs):
            pass

    passlib_context_stub.CryptContext = _CryptContext
    sys.modules["passlib"] = passlib_stub
    sys.modules["passlib.context"] = passlib_context_stub

from routes import admin_positional_reasons as route


ROW = {
    "fen": "8/8/8/8/3k4/8/4K2R/8 w - - 2 40",
    "game_id": "g1",
    "move_number": 40,
    "side_to_move": "white",
    "played_san": "Rh1",
    "best_san": "Kf3",
    "played_uci": "h2h1",
    "best_uci": "e2f3",
    "cp_loss": 180,
    "bucket": "bare endgame",
    "already_explained_by": [],
    "priority": 0,
    "status": "pending",
}


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, *args, **kwargs):
        return self

    async def to_list(self, length=None):
        return [dict(row) for row in self.rows]


class _Collection:
    def __init__(self, rows=()):
        self.rows = [dict(row) for row in rows]
        self.indexes = []
        self.updates = []

    async def create_index(self, *args, **kwargs):
        self.indexes.append((args, kwargs))

    async def find_one(self, query, projection=None, sort=None):
        for row in self.rows:
            if all(row.get(key) == value for key, value in query.items()):
                return dict(row)
        return None

    def find(self, query, projection=None):
        return _Cursor(self.rows)

    async def update_one(self, query, update, upsert=False):
        self.updates.append((query, update, upsert))


class _Db:
    def __init__(self):
        self.positional_reason_queue = _Collection([ROW])
        self.positional_reason_submissions = _Collection()


@pytest.fixture
def fake_db(monkeypatch):
    db = _Db()
    monkeypatch.setattr(route, "db", db)
    monkeypatch.setattr(route, "_INDEXES_ENSURED", False)
    return db


@pytest.mark.asyncio
async def test_next_position_returns_structural_evidence_and_progress(fake_db):
    response = await route.next_position(user=None)
    assert response["structural_features"]["phase"] == "bare_endgame"
    assert len(response["structural_signature"]) == 64
    assert response["progress"] == {
        "resolved": 0,
        "pending": 1,
        "total": 1,
        "by_disposition": {},
    }
    fingerprint_index = fake_db.positional_reason_submissions.indexes[0]
    assert fingerprint_index[1]["unique"] is True
    assert fingerprint_index[1]["sparse"] is True


@pytest.mark.asyncio
async def test_ineligible_submission_resolves_queue_without_caption_authority(fake_db):
    response = await route.submit_reason(
        {"fen": ROW["fen"], "disposition": "not_mistake", "notes": "Reviewed."},
        SimpleNamespace(user_id="admin"),
    )
    assert response["saved"]["disposition"] == "not_mistake"
    assert response["saved"]["promotion"]["ready"] is False
    saved_update = fake_db.positional_reason_submissions.updates[0][1]["$set"]
    assert saved_update["caption_eligible"] is False
    assert saved_update["tracker_eligible"] is False
    queue_update = fake_db.positional_reason_queue.updates[0][1]["$set"]
    assert queue_update["status"] == "resolved"
    assert queue_update["disposition"] == "not_mistake"