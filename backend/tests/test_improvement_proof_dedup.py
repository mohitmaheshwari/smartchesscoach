"""
GET /progress/improvement-proof built its `training_causal` list by looping
every qualifying prescription with no dedup by cognitive_gap. A gap that was
prescribed twice (trained, completed, then re-prescribed after it recurred
in real games — a routine scenario, not an edge case) produced two
identical "proof" cards on the Progress page. Reported live 2026-09-09 as
two duplicate "Piece Safety" cards under "What is beginning to change".

Fix: sort prescriptions most-recent-first and keep only the newest
qualifying entry per cognitive_gap.
"""
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import routes.player as player


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_args, **_kw):
        return self

    async def __aiter__(self):
        for doc in self._docs:
            yield doc


class FakeCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, *_a, **_kw):
        return FakeCursor(self._docs)


class FakeDB:
    def __init__(self, prescriptions):
        self.user_coaching_prescriptions = FakeCollection(prescriptions)


def _prescription(pres_id, cognitive_gap, started_at, status="completed"):
    return {
        "id": pres_id,
        "user_id": "u1",
        "issue_detected": cognitive_gap,
        "status": status,
        "started_at": started_at,
    }


def _progress_for(pres):
    """A qualifying, improving result keyed off the fixture's pres id, so
    the test can tell which prescription's numbers made it through."""
    return {
        "cognitive_gap": pres["issue_detected"],
        "baseline_avg": 2.0,
        "baseline_games": 5,
        "current_avg": 0.5,
        "current_games": 5,
        "improvement": 0.75,
        "eligible": True,
        "reason": None,
        "_pres_id": pres["id"],
    }


async def _run():
    prescriptions = [
        _prescription("old", "piece_safety", "2026-06-01T00:00:00Z"),
        _prescription("new", "piece_safety", "2026-08-20T00:00:00Z"),
        _prescription("other", "king_safety", "2026-07-01T00:00:00Z"),
    ]
    fake_db = FakeDB(prescriptions)
    player.set_db(fake_db)

    fake_user = types.SimpleNamespace(user_id="u1")

    async def fake_compute_progress(_db, pres):
        return _progress_for(pres)

    with patch(
        "services.improvement_proof_engine.compute_improvement_proof",
        new=AsyncMock(return_value={}),
    ), patch(
        "services.prescription_tracking_service.compute_prescription_progress",
        new=fake_compute_progress,
    ):
        result = await player.get_improvement_proof(user=fake_user)

    causal = result["training_causal"]
    gaps = [c["cognitive_gap"] for c in causal]

    assert gaps.count("piece_safety") == 1, (
        f"expected exactly one piece_safety card, got {gaps.count('piece_safety')}: {causal}"
    )
    assert "king_safety" in gaps
    assert len(causal) == 2


def test_duplicate_prescriptions_for_the_same_gap_collapse_to_one_card():
    import asyncio
    asyncio.run(_run())
