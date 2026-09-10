"""No-dark-window and single-source guards for the exact detector v2 rollout."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from scripts import backfill_verified_puzzle_admission as backfill
from services.destination_safety_detector import (
    FACT_VERSION,
    LEGACY_FACT_VERSION,
    QUALITY_ID,
    is_destination_safety_fact_version,
)
from services.destination_safety_puzzle_proof import (
    LEGACY_PROOF_VERSION,
    PROOF_VERSION,
)
from services.focus_bridge import DESTINATION_SAFETY_FACT_VERSION
from services.verified_puzzle_admission import (
    _stable_hash,
    stored_verdict_is_structurally_current,
)
from services.verified_puzzle_builder import build_position_verdict


FEN = "3rk3/8/8/3p4/8/8/8/3QK3 w - - 0 1"
EVIDENCE = {
    "fen_before": FEN,
    "move": "Qxd5",
    "best_move_san": "Qa1",
    "cp_loss": 800,
    "pv_after_played": ["Rxd5"],
    "pv_after_best": ["Kf7"],
}


def _current_verdict():
    verdict = build_position_verdict(
        source_kind="test",
        source_ref="destination-v2",
        move_evaluation=EVIDENCE,
        broad_category="piece_safety",
    )
    assert verdict.quality_id == QUALITY_ID
    return verdict


def _with_versions(document, detector_version, verifier_version):
    changed = dict(document)
    changed["detector_version"] = detector_version
    changed["verifier_version"] = verifier_version
    changed.pop("verdict_fingerprint", None)
    changed["verdict_fingerprint"] = _stable_hash(changed)
    return changed


def test_matched_v1_and_v2_pairs_remain_readable_during_regrade():
    current = _current_verdict().to_document()
    legacy = _with_versions(current, LEGACY_FACT_VERSION, LEGACY_PROOF_VERSION)

    assert stored_verdict_is_structurally_current({
        "fen": FEN,
        "best_move_san": "Qa1",
        "verified_admission": current,
    })
    assert stored_verdict_is_structurally_current({
        "fen": FEN,
        "best_move_san": "Qa1",
        "verified_admission": legacy,
    })


@pytest.mark.parametrize("detector_version,verifier_version", [
    (LEGACY_FACT_VERSION, PROOF_VERSION),
    (FACT_VERSION, LEGACY_PROOF_VERSION),
    ("piece_safety.destination_safety_exact.v0", LEGACY_PROOF_VERSION),
])
def test_cross_or_unknown_version_pairs_fail_closed(
    detector_version, verifier_version
):
    changed = _with_versions(
        _current_verdict().to_document(), detector_version, verifier_version
    )
    assert not stored_verdict_is_structurally_current({
        "fen": FEN,
        "best_move_san": "Qa1",
        "verified_admission": changed,
    })


def test_focus_provenance_reads_the_canonical_current_version():
    assert DESTINATION_SAFETY_FACT_VERSION == FACT_VERSION
    assert is_destination_safety_fact_version(LEGACY_FACT_VERSION)
    assert is_destination_safety_fact_version(FACT_VERSION)
    assert not is_destination_safety_fact_version("unknown")


def test_runtime_consumers_do_not_copy_the_legacy_version_literal():
    backend = Path(__file__).resolve().parent.parent
    consumers = (
        "services/focus_bridge.py",
        "services/focus_game_service.py",
        "services/analysis_completion_evidence.py",
        "services/review_learning_adapter.py",
        "services/personal_curriculum.py",
        "services/concept_mastery_service.py",
        "services/primary_weakness_picker.py",
        "services/teaching_engine.py",
    )
    offenders = [
        path
        for path in consumers
        if LEGACY_FACT_VERSION in (backend / path).read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_destination_regrade_apply_requires_explicit_confirmation():
    with pytest.raises(ValueError, match=backfill.DESTINATION_SAFETY_CONFIRM):
        backfill.validate_apply_confirmation(
            apply=True,
            quality_id=QUALITY_ID,
            confirm=None,
            expected_rows=1,
        )
    backfill.validate_apply_confirmation(
        apply=True,
        quality_id=QUALITY_ID,
        confirm=backfill.DESTINATION_SAFETY_CONFIRM,
        expected_rows=1,
    )


@pytest.mark.parametrize("kwargs,match", [
    ({"limit": 10, "expected_rows": 10}, "does not permit --limit"),
    ({"collections": ("community_puzzles",), "expected_rows": 10}, "both puzzle pools"),
    ({"expected_rows": None}, "--expect-rows"),
])
def test_destination_apply_rejects_partial_or_unbound_runs(kwargs, match):
    with pytest.raises(ValueError, match=match):
        backfill.validate_apply_confirmation(
            apply=True,
            quality_id=QUALITY_ID,
            confirm=backfill.DESTINATION_SAFETY_CONFIRM,
            **kwargs,
        )


class _Cursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self):
        if self._index >= len(self.rows):
            raise StopAsyncIteration
        row = self.rows[self._index]
        self._index += 1
        return row


class _Collection:
    def __init__(self, rows):
        self.rows = list(rows)
        self.query = None
        self.operations = []

    def find(self, query):
        self.query = query
        return _Cursor(self.rows)

    async def bulk_write(self, operations, ordered=False):
        assert ordered is False
        self.operations.extend(operations)


class _DB:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, _name):
        return self.collection


def test_targeted_regrade_stages_only_current_v2_or_reclassified_verdicts(
    monkeypatch,
):
    current = _current_verdict()
    legacy_document = _with_versions(
        current.to_document(), LEGACY_FACT_VERSION, LEGACY_PROOF_VERSION
    )
    row = {
        "_id": "legacy-row",
        "fen": FEN,
        "approved": True,
        "verified_admission": legacy_document,
    }
    collection = _Collection([row])

    async def source_verdict(_db, _collection, _row, _caches):
        return current, EVIDENCE

    monkeypatch.setattr(backfill, "_source_verdict", source_verdict)
    processed, counts = asyncio.run(backfill.process_rows(
        _DB(collection),
        collections=("community_puzzles",),
        apply=True,
        quality_id=QUALITY_ID,
        expected_rows=1,
    ))

    assert processed == 1
    assert counts[("all", "destination_v2_regrade_gate_passed")] == 1
    assert counts[("all", "destination_v2_row_count_matches")] == 1
    assert counts[("community_puzzles", "destination_v2_current")] == 1
    assert len(collection.operations) == 1
    written = collection.operations[0]._doc["$set"]["verified_admission"]
    assert written["detector_version"] == FACT_VERSION
    assert written["verifier_version"] == PROOF_VERSION


def test_targeted_regrade_aborts_before_writes_if_dry_run_count_changed(
    monkeypatch,
):
    current = _current_verdict()
    legacy_document = _with_versions(
        current.to_document(), LEGACY_FACT_VERSION, LEGACY_PROOF_VERSION
    )
    collection = _Collection([{
        "_id": "legacy-row",
        "fen": FEN,
        "approved": True,
        "verified_admission": legacy_document,
    }])

    async def source_verdict(_db, _collection, _row, _caches):
        return current, EVIDENCE

    monkeypatch.setattr(backfill, "_source_verdict", source_verdict)
    with pytest.raises(RuntimeError, match="expected_rows=2"):
        asyncio.run(backfill.process_rows(
            _DB(collection),
            collections=("community_puzzles",),
            apply=True,
            quality_id=QUALITY_ID,
            expected_rows=2,
        ))
    assert collection.operations == []
