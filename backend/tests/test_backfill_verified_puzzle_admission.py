from collections import OrderedDict
from types import SimpleNamespace
import asyncio

from scripts import backfill_verified_puzzle_admission as backfill
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_builder import build_position_verdict


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
        self.query = None

    def find(self, query):
        self.query = query
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
        broad_category="calculation_depth",
        quality_id=None,
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


def test_forced_mate_re_admission_validates_caption_before_targeted_write(monkeypatch):
    fen = "6k1/5ppp/8/8/8/8/5PPP/R6K w - - 0 1"
    evidence = {
        "fen_before": fen,
        "move": "Ra2",
        "best_move_san": "Kg1",
        "cp_loss": 300,
        "pv_after_best": ["Kg1", "Kh8", "Ra8#"],
    }
    verdict = build_position_verdict(
        source_kind="game",
        source_ref="mate-source",
        move_evaluation=evidence,
        broad_category="missed_tactic",
    )
    row = {
        "_id": "mate-row",
        "fen": fen,
        "verified_admission": {"quality_id": backfill.FORCED_MATE_QUALITY_ID},
    }
    collection = _Collection([row])

    async def fake_source(_db, _collection, _row, _caches):
        return verdict, evidence

    monkeypatch.setattr(backfill, "_source_verdict", fake_source)
    processed, counts = asyncio.run(backfill.process_rows(
        _Database({"community_puzzles": collection}),
        collections=("community_puzzles",),
        apply=True,
        quality_id=backfill.FORCED_MATE_QUALITY_ID,
    ))

    assert processed == 1
    assert collection.query == {
        "verified_admission.quality_id": backfill.FORCED_MATE_QUALITY_ID
    }
    assert counts[("all", "forced_mate_validated")] == 1
    assert counts[("all", "forced_mate_violations")] == 0
    assert counts[("all", "forced_mate_zero_violation_gate_passed")] == 1
    assert collection.batch_sizes == [1]


def test_forced_mate_re_admission_aborts_entire_batch_before_any_write(monkeypatch):
    row = {
        "_id": "bad-mate-row",
        "fen": "6k1/5ppp/8/8/8/8/5PPP/R6K w - - 0 1",
        "verified_admission": {"quality_id": backfill.FORCED_MATE_QUALITY_ID},
    }
    collection = _Collection([row])

    async def fake_source(_db, _collection, _row, _caches):
        return _verdict(AdmissionStatus.BROAD, ("a1a8",)), None

    monkeypatch.setattr(backfill, "_source_verdict", fake_source)
    monkeypatch.setattr(
        backfill,
        "_forced_mate_readmission_check",
        lambda *_args: ("violation", "independent_fact_mismatch"),
    )

    try:
        asyncio.run(backfill.process_rows(
            _Database({"community_puzzles": collection}),
            collections=("community_puzzles",),
            apply=True,
            quality_id=backfill.FORCED_MATE_QUALITY_ID,
        ))
    except RuntimeError as exc:
        assert "aborted before writes" in str(exc)
    else:
        raise AssertionError("unsafe forced-mate batch should not write")
    assert collection.batch_sizes == []


def test_quality_filter_remains_stable_across_collections(monkeypatch):
    first = _Collection([{
        "_id": "now-abstains",
        "fen": "8/8/8/8/8/2k5/8/K7 w - - 0 1",
        "verified_admission": {"quality_id": backfill.FORCED_MATE_QUALITY_ID},
    }])
    second = _Collection([])

    async def generic_source(_db, _collection, _row, _caches):
        return _verdict(AdmissionStatus.GENERIC, ("a1a2",)), None

    monkeypatch.setattr(backfill, "_source_verdict", generic_source)
    monkeypatch.setattr(
        backfill,
        "_forced_mate_readmission_check",
        lambda *_args: ("abstained", None),
    )
    asyncio.run(backfill.process_rows(
        _Database({
            "community_puzzles": first,
            "community_training_positions": second,
        }),
        collections=("community_puzzles", "community_training_positions"),
        quality_id=backfill.FORCED_MATE_QUALITY_ID,
    ))

    expected = {
        "verified_admission.quality_id": backfill.FORCED_MATE_QUALITY_ID
    }
    assert first.query == expected
    assert second.query == expected
