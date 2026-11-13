"""Plan outcomes: rating before the plan vs each plan week, and work done."""
import asyncio
from datetime import datetime, timedelta, timezone

from services import plan_outcomes as po


def _match(doc, query):
    for k, v in query.items():
        val = doc.get(k)
        if isinstance(v, dict):
            if "$lt" in v and not (val is not None and val < v["$lt"]):
                return False
            if "$gte" in v and not (val is not None and val >= v["$gte"]):
                return False
        elif val != v:
            return False
    return True


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, key, direction=1):
        self.rows = sorted(self.rows, key=lambda r: r.get(key), reverse=direction == -1)
        return self

    def limit(self, n):
        self.rows = self.rows[:n]
        return self

    async def to_list(self, n=None):
        return list(self.rows)

    def __aiter__(self):
        self._it = iter(self.rows)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _Coll:
    def __init__(self, rows):
        self.rows = rows

    def find(self, query, projection=None):
        return _Cursor([dict(r) for r in self.rows if _match(r, query)])

    async def distinct(self, key):
        return sorted({r[key] for r in self.rows})


class _Db:
    def __init__(self, **colls):
        for k, v in colls.items():
            setattr(self, k, _Coll(v))


def test_outcome_compares_each_plan_week_with_the_rating_before_it():
    start = datetime(2026, 11, 9, tzinfo=timezone.utc)
    games = [{"user_id": "u", "game_id": f"b{i}", "user_color": "white", "white_rating": 1300,
              "played_at_utc": start - timedelta(days=i + 1)} for i in range(5)]
    games += [{"user_id": "u", "game_id": f"w{i}", "user_color": "white", "white_rating": 1340,
               "played_at_utc": start + timedelta(days=i)} for i in range(3)]
    db = _Db(player_plan_weeks=[{"user_id": "u", "week_start": "2026-11-09", "step": {"title": "Step"}, "step_key": "k"}],
             games=games,
             plan_activity=[{"user_id": "u", "week_start": "2026-11-09", "action": "find"}])
    out = asyncio.run(po.player_outcome(db, "u"))
    assert out["baseline_rating"] == 1300
    week = out["weeks"][0]
    assert week["games"] == 3 and week["rating"] == 1340 and week["change"] == 40 and week["did_work"]
    assert out["change_now"] == 40 and out["weeks_with_work"] == 1
    summary = asyncio.run(po.all_outcomes(db))["summary"]
    assert summary["followed"] == 1 and summary["followed_median_change"] == 40
