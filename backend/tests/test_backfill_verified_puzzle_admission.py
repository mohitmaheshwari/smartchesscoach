from collections import OrderedDict
from types import SimpleNamespace
import asyncio

from scripts import backfill_verified_puzzle_admission as backfill
from services.verified_puzzle_admission import AdmissionStatus


class _Cursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.index = 0

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.rows):
            raise StopAsyncIteration
        row = self.rows[self.index]
        self.index += 1
        return row


class _Collection:
    def __init__(self, rows):
        self.rows = rows
        self.batch_sizes = []

    def find(self, _query):
        return _Cursor(self.rows)

    async def bulk_write(self, operations, ordered=False):
        assert ordered is False
        self.batch_sizes.append(len(operations))


class _Database:
    def __init__(self, collections):
        self.collections = collections

    def __getitem__(self, name):
        return self.collections[name]


def _verdict(status, answers):
    return SimpleNamespace(
        status=status,
        reason_codes=(f"reason_{status.value}",),
        acceptable_moves_uci=tuple(answers),
        to_document=lambda: {
            "status": status.value,
            "acceptable_moves_uci": list(answers),
        },
    )


def test_source_cache_is_bounded():
    cache = OrderedDict()
    for index in range(backfill.CACHE_LIMIT + 20):
        backfill._remember(cache, str(index), {"index": index})
    assert len(cache) == backfill.CACHE_LIMIT
    assert "0" not in cache


def test_dry_run_quarantines_each_conflicting_source_answer(monkeypatch):
    fen = "8/8/8/8/8/2k5/8/K7 w - - 0 1"
    collections = {
        "community_puzzles": _Collection([
            {"_id": "a", "fen": fen, "answer": "a1a2"},
        ]),
        "community_training_positions": _Collection([
            {"_id": "b", "fen": fen, "answer": "a1b1"},
        ]),
    }

    async def fake_source(_db, _collection, row, _caches):
        return _verdict(AdmissionStatus.GENERIC, (row["answer"],)), None

    monkeypatch.setattr(backfill, "_source_verdict", fake_source)
    monkeypatch.setattr(
        backfill,
        "_set_fields",
        lambda _collection, _row, verdict, _source: {
            "verified_admission": verdict.to_document(),
            "approved": True,
        },
    )
    processed, counts = asyncio.run(
        backfill.process_rows(
            _Database(collections),
            collections=tuple(collections),
            apply=False,
        )
    )

    assert processed == 2
    assert counts[("all", "cross_pool_conflict_positions")] == 1
    assert counts[("all", "cross_pool_conflict_rows")] == 2
    assert counts[("community_puzzles", "generic")] == 0
    assert counts[("community_puzzles", "quarantine")] == 1
    assert counts[(
        "community_puzzles",
        "reason:cross_pool_answer_conflict",
    )] == 1
    assert collections["community_puzzles"].batch_sizes == []


def test_existing_quality_rejection_is_preserved(monkeypatch):
    row = {"_id": "rejected", "fen": "8/8/8/8/8/2k5/8/K7 w - - 0 1", "approved": False}

    async def fake_source(_db, _collection, _row, _caches):
        return _verdict(AdmissionStatus.GENERIC, ("a1a2",)), None

    monkeypatch.setattr(backfill, "_source_verdict", fake_source)
    fields = backfill._set_fields(
        "community_puzzles",
        row,
        _verdict(AdmissionStatus.GENERIC, ("a1a2",)),
        None,
    )

    assert fields["approved"] is False


def test_apply_writes_in_bounded_batches(monkeypatch):
    fen = "8/8/8/8/8/2k5/8/K7 w - - 0 1"
    rows = [
        {"_id": index, "fen": fen, "answer": "a1a2"}
        for index in range(backfill.BATCH_SIZE + 1)
    ]
    collection = _Collection(rows)

    async def fake_source(_db, _collection, row, _caches):
        return _verdict(AdmissionStatus.GENERIC, (row["answer"],)), None

    monkeypatch.setattr(backfill, "_source_verdict", fake_source)
    monkeypatch.setattr(
        backfill,
        "_set_fields",
        lambda _collection, _row, verdict, _source: {
            "verified_admission": verdict.to_document(),
            "approved": True,
        },
    )
    processed, counts = asyncio.run(
        backfill.process_rows(
            _Database({"community_puzzles": collection}),
            collections=("community_puzzles",),
            apply=True,
        )
    )

    assert processed == backfill.BATCH_SIZE + 1
    assert counts[("all", "cross_pool_conflict_rows")] == 0
    assert collection.batch_sizes == [backfill.BATCH_SIZE, 1]
