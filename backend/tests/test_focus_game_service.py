"""PIC Focus Game commitment and evidence-envelope contract tests."""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.focus_game_service import (
    claim_pending_focus_game_sync,
    record_pic_game_evidence_sync,
    summarize_pic_observations,
)


EXACT_QUALITY_ID = "gap:piece_safety:destination_safety_exact"
EXACT_FACT_VERSION = "piece_safety.destination_safety_exact.v1"


def _observation(schema=17, version="piece_safety.d_live.v1", outcome="miss"):
    return {
        "schema_version": schema,
        "missed_pattern": "piece_safety",
        "subtype": "simple_hang",
        "piece_safety_decision": {
            "version": version,
            "derivation_status": "ok",
            "eligible": True,
            "outcome": outcome,
        },
    }


def _exact_observation(outcome="miss", *, fires=True):
    return {
        "schema_version": 18,
        "missed_pattern": "piece_safety" if fires else None,
        "subtype": "destination_safety_exact" if fires else None,
        "destination_safety_exact": {
            "version": EXACT_FACT_VERSION,
            "derivation_status": "ok",
            "eligible": True,
            "outcome": outcome,
            "fires": fires,
        },
    }


def _exact_focus(**extra):
    return {
        "_id": "f1",
        "focus_kind": "piece_safety/destination_safety_exact",
        "detector_quality_id": EXACT_QUALITY_ID,
        **extra,
    }


class _Collection:
    def __init__(self, doc=None):
        self.doc = doc
        self.last_update = None

    def find_one(self, query, projection=None):
        return self.doc

    def update_one(self, query, update):
        self.last_update = (query, update)
        if self.doc is not None and "$set" in update:
            for dotted, value in update["$set"].items():
                target = self.doc
                parts = dotted.split(".")
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = value
        return type("Result", (), {"modified_count": 1})()

    def find_one_and_update(self, query, update, return_document=None):
        self.update_one(query, update)
        return self.doc


class _DB:
    def __init__(self, focus, role="admin"):
        self.focus = _Collection(focus)
        self.users = _Collection({"role": role})
        self.games = _Collection({"game_id": "g1"})

    def __getitem__(self, name):
        if name == "user_active_focus":
            return self.focus
        raise KeyError(name)


def test_summary_hard_excludes_pre_see_and_wrong_fact_version():
    summary = summarize_pic_observations([
        _observation(schema=15),
        _observation(version="piece_safety.d_live.experimental"),
        _observation(outcome="handled"),
        _observation(outcome="miss"),
    ])
    assert summary == {
        "decisions": 2,
        "misses": 1,
        "handled": 1,
        "positive_piece_safety_diagnoses": 3,
        # The wrong-version v17 observation remains a valid positive diagnosis;
        # the pre-SEE record does not.
        "positive_simple_hang_diagnoses": 3,
    }


def test_exact_summary_uses_only_v18_destination_safety_fact():
    summary = summarize_pic_observations(
        [
            _observation(outcome="miss"),
            _exact_observation(outcome="handled", fires=False),
            _exact_observation(outcome="miss"),
        ],
        proof_detector_id=EXACT_FACT_VERSION,
    )
    assert summary == {
        "decisions": 2,
        "misses": 1,
        "handled": 1,
        "positive_piece_safety_diagnoses": 1,
        "positive_destination_safety_diagnoses": 1,
    }


def test_commitment_must_predate_import_to_be_claimed():
    committed = datetime.now(timezone.utc)
    focus = _exact_focus(**{
        "pending_focus_game": {
            "commitment_id": "c1",
            "status": "waiting",
            "committed_at": committed,
        },
    })
    db = _DB(focus)
    assert claim_pending_focus_game_sync(
        db, "u1", "g1", committed - timedelta(seconds=1)
    ) is None
    assert focus["pending_focus_game"]["status"] == "waiting"

    claimed = claim_pending_focus_game_sync(
        db, "u1", "g1", committed + timedelta(seconds=1)
    )
    assert claimed["pending_focus_game"]["status"] == "claimed"
    assert claimed["pending_focus_game"]["game_id"] == "g1"


def test_flag_off_records_no_evidence(monkeypatch):
    monkeypatch.delenv("PERSONAL_IMPROVEMENT_CYCLE_ENABLED", raising=False)
    db = _DB({"_id": "f1"})
    assert record_pic_game_evidence_sync(
        db, "u1", {"game_id": "g1"}, [_observation()]
    ) is None
    assert db.games.last_update is None


def test_claimed_game_gets_deterministic_external_evidence(monkeypatch):
    monkeypatch.setenv("PERSONAL_IMPROVEMENT_CYCLE_ENABLED", "true")
    committed = datetime.now(timezone.utc) - timedelta(minutes=5)
    focus = _exact_focus(**{
        "instruction_id": "inst1",
        "pending_focus_game": {
            "commitment_id": "c1",
            "status": "waiting",
            "committed_at": committed,
        },
    })
    db = _DB(focus)
    game = {
        "game_id": "g1",
        "imported_at": datetime.now(timezone.utc),
    }
    envelope = record_pic_game_evidence_sync(
        db, "u1", game, [_exact_observation(outcome="miss")]
    )

    assert envelope["evidence_mode"] == "external_focus_game"
    assert envelope["pre_committed"] is True
    assert envelope["verdict"] == "measurement_pending"
    assert envelope["summary"]["misses"] == 1
    assert envelope["proof_detector_id"] == EXACT_FACT_VERSION
    assert envelope["idempotency_key"] == "pic:f1:g1:move-observation-v18"
    assert db.games.last_update[1]["$set"]["pic_evidence"] == envelope
