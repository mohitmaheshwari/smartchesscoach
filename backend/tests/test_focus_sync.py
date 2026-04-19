"""
Tests for the sibling-system sync paths:
  - focus_engine.sync_focus_with_brain  → users.focus.cluster
  - mistake_streak_service.sync_streak_focus_with_brain  → user_streaks.current_focus_mistake

These ensure every surface in the product agrees with coach_memory.learning.current_focus.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.focus_engine import (
    cluster_from_brain_focus,
    sync_focus_with_brain,
)
from services.mistake_streak_service import (
    streak_focus_from_brain,
    sync_streak_focus_with_brain,
)


# ─── FAKE DB ──────────────────────────────────────────────────────────


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_a, **_kw):
        return self

    async def to_list(self, _n):
        return self._docs


class FakeColl:
    def __init__(self, docs=None):
        self._docs = docs if docs is not None else []

    async def find_one(self, query, projection=None, **kw):
        uid = query.get("user_id")
        for d in self._docs:
            if uid is None or d.get("user_id") == uid:
                return d
        return None

    def find(self, *_a, **_kw):
        return FakeCursor(self._docs)

    async def update_one(self, query, update, upsert=False):
        uid = query.get("user_id")
        target = None
        for d in self._docs:
            if d.get("user_id") == uid:
                target = d
                break
        if target is None:
            if not upsert:
                return
            target = {"user_id": uid}
            self._docs.append(target)
        set_fields = update.get("$set", {})
        for k, v in set_fields.items():
            if "." in k:
                parts = k.split(".")
                cursor = target
                for p in parts[:-1]:
                    cursor = cursor.setdefault(p, {})
                cursor[parts[-1]] = v
            else:
                target[k] = v

    async def delete_one(self, query):
        uid = query.get("user_id")
        self._docs[:] = [d for d in self._docs if d.get("user_id") != uid]


class FakeDB:
    def __init__(self):
        self.users = FakeColl()
        self.user_streaks = FakeColl()
        self.coach_memory = FakeColl()
        self.coaching_cache = FakeColl()


# ─── MAPPING TESTS ────────────────────────────────────────────────────


def test_cluster_mapping():
    assert cluster_from_brain_focus("hanging_piece") == "threat_awareness"
    assert cluster_from_brain_focus("missed_fork") == "threat_awareness"
    assert cluster_from_brain_focus("tactical_error") == "calculation"
    assert cluster_from_brain_focus("trap:italian_game") == "planning"
    assert cluster_from_brain_focus("opening:sicilian") == "planning"
    assert cluster_from_brain_focus("endgame:king_pawn") == "calculation"
    assert cluster_from_brain_focus("some_unknown_key") is None
    assert cluster_from_brain_focus(None) is None


def test_streak_focus_mapping():
    assert streak_focus_from_brain("hanging_piece") == "HANGING_PIECE"
    assert streak_focus_from_brain("missed_fork") == "TACTICAL_MISS"
    assert streak_focus_from_brain("missed_pin") == "TACTICAL_MISS"
    assert streak_focus_from_brain("king_safety") == "THREAT_VERIFICATION"
    assert streak_focus_from_brain("tactical_error") == "STOPPED_CALCULATION_EARLY"
    # Prefix forms don't map — leave the streak unchanged
    assert streak_focus_from_brain("trap:italian") is None
    assert streak_focus_from_brain("opening:xxx") is None
    assert streak_focus_from_brain(None) is None


# ─── SYNC TESTS (focus_engine) ───────────────────────────────────────


def test_sync_focus_creates_fresh_doc():
    db = FakeDB()
    result = asyncio.run(sync_focus_with_brain(db, "u1", "hanging_piece"))
    assert result["cluster"] == "threat_awareness"
    assert result["brain_focus"] == "hanging_piece"
    assert result["game_results"] == []
    # users doc has the focus field
    assert db.users._docs[0]["focus"]["cluster"] == "threat_awareness"


def test_sync_focus_preserves_progress_when_cluster_unchanged():
    db = FakeDB()
    db.users._docs.append({
        "user_id": "u1",
        "focus": {
            "cluster": "threat_awareness",
            "name": "Old Name",
            "game_results": [{"clean": True, "game_id": "g1"}],
        },
    })
    result = asyncio.run(sync_focus_with_brain(db, "u1", "missed_fork"))
    # missed_fork → threat_awareness (same cluster)
    assert result["cluster"] == "threat_awareness"
    assert len(result["game_results"]) == 1  # Progress preserved
    assert result["name"] == "Threat Awareness"  # Refreshed from rule config


def test_sync_focus_resets_when_cluster_changes():
    db = FakeDB()
    db.users._docs.append({
        "user_id": "u1",
        "focus": {
            "cluster": "threat_awareness",
            "game_results": [{"clean": True}, {"clean": True}],
        },
    })
    result = asyncio.run(sync_focus_with_brain(db, "u1", "tactical_error"))
    # tactical_error → calculation (different cluster)
    assert result["cluster"] == "calculation"
    assert result["game_results"] == []  # Reset


def test_sync_focus_returns_none_for_unknown():
    db = FakeDB()
    result = asyncio.run(sync_focus_with_brain(db, "u1", "some_weird_focus"))
    assert result is None
    assert not db.users._docs  # Nothing written


# ─── SYNC TESTS (mistake_streak) ─────────────────────────────────────


def test_sync_streak_creates_fresh_doc():
    db = FakeDB()
    result = asyncio.run(sync_streak_focus_with_brain(db, "u1", "hanging_piece"))
    assert result == "HANGING_PIECE"
    doc = db.user_streaks._docs[0]
    assert doc["streak_data"]["current_focus_mistake"] == "HANGING_PIECE"
    assert doc["streak_data"]["mistake_streak"]["current"] == 0


def test_sync_streak_preserves_when_type_unchanged():
    db = FakeDB()
    db.user_streaks._docs.append({
        "user_id": "u1",
        "streak_data": {
            "current_focus_mistake": "HANGING_PIECE",
            "mistake_streak": {"current": 3, "best": 5},
        },
    })
    result = asyncio.run(sync_streak_focus_with_brain(db, "u1", "hanging_piece"))
    assert result == "HANGING_PIECE"
    # Streak untouched because type matched
    assert db.user_streaks._docs[0]["streak_data"]["mistake_streak"]["current"] == 3


def test_sync_streak_resets_current_when_type_changes():
    db = FakeDB()
    db.user_streaks._docs.append({
        "user_id": "u1",
        "streak_data": {
            "current_focus_mistake": "HANGING_PIECE",
            "mistake_streak": {"current": 3, "best": 5},
        },
    })
    result = asyncio.run(sync_streak_focus_with_brain(db, "u1", "missed_fork"))
    assert result == "TACTICAL_MISS"
    streak = db.user_streaks._docs[0]["streak_data"]["mistake_streak"]
    assert streak["current"] == 0  # Reset
    assert streak["best"] == 5  # Preserved


def test_sync_streak_returns_none_for_prefix_focus():
    db = FakeDB()
    db.user_streaks._docs.append({
        "user_id": "u1",
        "streak_data": {
            "current_focus_mistake": "HANGING_PIECE",
            "mistake_streak": {"current": 3, "best": 5},
        },
    })
    result = asyncio.run(sync_streak_focus_with_brain(db, "u1", "trap:italian_game"))
    assert result is None
    # Existing streak untouched
    assert db.user_streaks._docs[0]["streak_data"]["current_focus_mistake"] == "HANGING_PIECE"
    assert db.user_streaks._docs[0]["streak_data"]["mistake_streak"]["current"] == 3


# ─── SMOKE RUNNER ─────────────────────────────────────────────────────


def _smoke():
    passed = 0
    failed = []
    tests = [n for n in globals() if n.startswith("test_")]
    for name in tests:
        try:
            globals()[name]()
            passed += 1
            print(f"  PASS: {name}")
        except AssertionError as e:
            failed.append((name, str(e)))
            print(f"  FAIL: {name} — {e}")
        except Exception as e:
            failed.append((name, f"{type(e).__name__}: {e}"))
            print(f"  ERROR: {name} — {type(e).__name__}: {e}")
    print()
    print(f"Results: {passed}/{len(tests)} passed, {len(failed)} failed")
    for n, e in failed:
        print(f"  - {n}: {e}")
    return len(failed) == 0


if __name__ == "__main__":
    sys.exit(0 if _smoke() else 1)
