"""Who may read a student's games for the coach board (routes/academy_games.py)."""
import asyncio
from types import SimpleNamespace

from routes.academy_games import staff_may_read_game


class _Coll:
    def __init__(self, rows):
        self.rows = rows

    async def find_one(self, query, projection=None):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items()):
                return r
        return None


def _db(consent="given", deleted=None):
    student = {"child_user_id": "kid1", "academy_id": "acad1", "deleted_at": deleted,
               "consent": {"status": consent}}
    return {
        "academy_students": _Coll([student]),
        "academy_staff": _Coll([{"academy_id": "acad1", "user_id": "coach1", "role": "coach"}]),
    }


def _user(uid, role="user"):
    return SimpleNamespace(user_id=uid, role=role)


def _run(coro):
    return asyncio.run(coro)


def test_coach_of_the_academy_may_read_after_consent():
    assert _run(staff_may_read_game(_db(), _user("coach1"), "kid1")) is True


def test_no_consent_no_read():
    assert _run(staff_may_read_game(_db(consent="pending"), _user("coach1"), "kid1")) is False


def test_a_coach_of_another_academy_may_not_read():
    assert _run(staff_may_read_game(_db(), _user("coach2"), "kid1")) is False


def test_a_game_that_is_not_a_students_is_not_opened():
    assert _run(staff_may_read_game(_db(), _user("coach1"), "someone_else")) is False


def test_deleted_child_is_not_read():
    assert _run(staff_may_read_game(_db(deleted="2026-11-01"), _user("coach1"), "kid1")) is False


def test_site_admin_may_read_after_consent():
    assert _run(staff_may_read_game(_db(), _user("adm", role="super_admin"), "kid1")) is True
