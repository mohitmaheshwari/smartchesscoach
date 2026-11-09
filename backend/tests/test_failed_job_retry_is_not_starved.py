"""The failed-job auto-retry must reach the rows it can retry.

It read `.find(failed).limit(25)` and then skipped rows whose game was
already analysed. On production 2026-11-09 the first 25 failed rows in scan
order were all such games, so every pass skipped the same 25 and the 396
unanalysed games behind them were never retried -- 367 of them failed in one
outage on 2026-08-28/29 and sat there for ten weeks.

A failure whose exception had no message also recorded nothing: those 396
rows have last_error "" and analysis_error "".
"""
import asyncio

import analysis_worker


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def __iter__(self):
        return iter(self._rows)


class Queue:
    def __init__(self, rows):
        self.rows = rows
        self.updates = []

    def find(self, query=None, *_a, **_kw):
        wanted = (query or {}).get("status")
        return FakeCursor(r for r in self.rows if r.get("status") == wanted)

    def update_one(self, selector, update, **_kw):
        self.updates.append((selector, update))


class Games:
    def __init__(self, games):
        self.games = games
        self.updates = []

    def aggregate(self, pipeline, **_kw):
        ids = set(pipeline[0]["$match"]["game_id"]["$in"])
        return iter({"game_id": g["game_id"], "is_analyzed": g.get("is_analyzed"),
                     "analysis_error": g.get("analysis_error"), "pgn": bool(g.get("pgn"))}
                    for g in self.games if g["game_id"] in ids)

    def find_one(self, query, *_a, **_kw):
        return next((g for g in self.games if g["game_id"] == query.get("game_id")), None)

    def update_one(self, selector, update, **_kw):
        self.updates.append((selector, update))


class FakeDB:
    def __init__(self, rows, games):
        self.analysis_queue = Queue(rows)
        self.games = Games(games)


def failed(i):
    return {"_id": f"q{i}", "game_id": f"g{i}", "status": "failed", "retry_count": 1,
            "failure_reason": "analysis_error", "last_error": ""}


def production_shape(already_analysed=25, waiting=5):
    rows, games = [], []
    for i in range(already_analysed):
        rows.append(failed(i))
        games.append({"game_id": f"g{i}", "is_analyzed": True, "pgn": "1. e4"})
    for i in range(already_analysed, already_analysed + waiting):
        rows.append(failed(i))
        games.append({"game_id": f"g{i}", "is_analyzed": False, "pgn": "1. e4", "analysis_error": ""})
    return rows, games


def retried(db):
    return [s["_id"] for s, u in db.analysis_queue.updates
            if u.get("$set", {}).get("status") == "pending"]


def test_rows_behind_a_full_batch_of_skips_are_retried():
    rows, games = production_shape(already_analysed=analysis_worker.FAILED_RETRY_BATCH, waiting=5)
    db = FakeDB(rows, games)
    analysis_worker.cleanup_stuck_jobs(db)
    assert sorted(retried(db)) == sorted(f"q{i}" for i in range(25, 30)), (
        "the retry read only the first batch of rows, all already analysed, "
        "and never reached the games still waiting")


def test_the_cap_is_on_retries_made():
    rows, games = production_shape(already_analysed=3, waiting=analysis_worker.FAILED_RETRY_BATCH + 10)
    db = FakeDB(rows, games)
    analysis_worker.cleanup_stuck_jobs(db)
    assert len(retried(db)) == analysis_worker.FAILED_RETRY_BATCH


def test_a_permanent_failure_is_still_not_retried():
    rows, games = production_shape(already_analysed=0, waiting=1)
    games[0]["analysis_error"] = "Too few moves analyzed (4)"
    db = FakeDB(rows, games)
    analysis_worker.cleanup_stuck_jobs(db)
    assert retried(db) == []


def test_a_failure_with_an_empty_message_records_its_type():
    assert analysis_worker._error_text(asyncio.TimeoutError()) == "TimeoutError"
    assert analysis_worker._error_text(ValueError("no pgn")) == "no pgn"
