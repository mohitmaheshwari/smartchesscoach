"""Exposure measurement (docs/coaching_intelligence_scope.md, 1a)."""
import asyncio
from datetime import datetime, timezone

from services import player_coach_file as pcf


class _Coll:
    def __init__(self):
        self.ops = []

    async def update_one(self, q, u, upsert=False):
        self.ops.append((q, u, upsert))


class _DB(dict):
    def __getitem__(self, k):
        return self.setdefault(k, _Coll())


def test_a_visit_records_first_and_last_seen_days_and_surface():
    db = _DB()
    now = datetime(2026, 11, 18, 10, tzinfo=timezone.utc)
    asyncio.run(pcf.record_visit(db, "u1", "day_card", now=now))
    q, u, upsert = db[pcf.VISITS_COLLECTION].ops[0]
    assert q == {"user_id": "u1"} and upsert
    assert u["$setOnInsert"]["first_seen_at"] == now and u["$set"]["last_seen_at"] == now
    assert u["$addToSet"] == {"days": "2026-11-18", "surfaces": "day_card"}


def test_plan_weeks_are_written_only_for_players_who_can_see_the_plan(monkeypatch):
    calls = []
    import services.player_plan_week as ppw

    monkeypatch.setattr(ppw, "ensure_week_sync", lambda *a, **k: calls.append(a[1]) or None)
    monkeypatch.setattr(pcf, "build_file", lambda *a, **k: {"plan": None, "habit": None})

    class _Cur(list):
        def sort(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

    class _C:
        def find(self, *a, **k):
            return _Cur()

        def aggregate(self, *a, **k):
            return []

        def find_one(self, *a, **k):
            return None

        def update_one(self, *a, **k):
            return None

    class _SyncDB(dict):
        def __getattr__(self, k):
            return _C()

        def __getitem__(self, k):
            return _C()

    monkeypatch.setenv(pcf.FLAG_ENV, "seen")
    pcf.build_and_store_sync(_SyncDB(), "unseen")
    pcf.build_and_store_sync(_SyncDB(), "seen")
    assert calls == ["seen"]
