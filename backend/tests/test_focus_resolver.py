"""
Tests for focus_resolver — the single source of truth for "what to work on".

Uses a fake async DB so tests run without MongoDB.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.focus_resolver import (
    get_active_focus,
    reorder_top_problems_by_focus,
    FOCUS_TO_GAP,
    FOCUS_TO_CATEGORY,
    CATEGORY_TO_GAP,
    _parse_prefix_focus,
)


# ─── FAKE DB ──────────────────────────────────────────────────────────


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_args, **_kw):
        return self

    async def to_list(self, _n):
        return self._docs


class FakeCollection:
    def __init__(self, docs=None):
        self._docs = docs or []

    async def find_one(self, query, projection=None, **kw):
        # Find first doc matching user_id (enough for these tests)
        sort = kw.get("sort")
        uid = query.get("user_id")
        focus = query.get("coach_prescription")
        candidates = [
            d for d in self._docs
            if (uid is None or d.get("user_id") == uid)
            and (focus is None or d.get("coach_prescription") == focus)
        ]
        if sort:
            key, direction = sort[0]
            candidates.sort(key=lambda d: d.get(key, ""), reverse=(direction == -1))
        return candidates[0] if candidates else None

    def find(self, *_a, **_kw):
        return FakeCursor(self._docs)


class FakeDB:
    def __init__(self, coach_memory=None, postgame_analyses=None):
        self.coach_memory = FakeCollection(coach_memory or [])
        self.postgame_analyses = FakeCollection(postgame_analyses or [])


# ─── UNIT TESTS ───────────────────────────────────────────────────────


def test_prefix_parsing():
    assert _parse_prefix_focus("hanging_piece") is None
    p = _parse_prefix_focus("trap:italian_gambit")
    assert p and p["focus_kind"] == "trap" and p["category"] == "opening_disaster"
    p = _parse_prefix_focus("opening:sicilian_najdorf")
    assert p and p["focus_kind"] == "opening"
    p = _parse_prefix_focus("endgame:k_and_p_vs_k")
    assert p and p["focus_kind"] == "endgame"


def test_reorder_moves_focus_to_front():
    top = [
        {"category": "tactical_miss", "count": 5, "label": "A"},
        {"category": "one_move_blunder", "count": 3, "label": "B"},
    ]
    r = reorder_top_problems_by_focus(top, "one_move_blunder")
    assert r[0]["category"] == "one_move_blunder"
    assert len(r) == 2


def test_reorder_synthetic_prepend_when_focus_not_in_aggregate():
    top = [{"category": "tactical_miss", "count": 5, "label": "A"}]
    r = reorder_top_problems_by_focus(top, "opening_disaster")
    assert r[0]["category"] == "opening_disaster"
    assert r[0].get("_from_brain") is True
    assert len(r) == 2


def test_reorder_with_empty():
    assert reorder_top_problems_by_focus([], "anything") == []
    assert reorder_top_problems_by_focus([{"category": "X"}], None) == [{"category": "X"}]


async def _run_async_test(coro):
    return await coro


def test_no_brain_no_aggregate_returns_none():
    db = FakeDB()
    result = asyncio.run(get_active_focus(db, "user_x", top_problems=None))
    assert result["source"] == "none"
    assert result["focus"] is None


def test_aggregate_fallback_when_no_brain():
    db = FakeDB()
    top = [{"category": "one_move_blunder", "label": "Left a piece hanging", "count": 5}]
    result = asyncio.run(get_active_focus(db, "user_x", top))
    assert result["source"] == "aggregate"
    assert result["focus"] == "one_move_blunder"
    assert result["gap"] == "piece_safety"
    assert "5" in result["reason"]


def test_brain_focus_used_when_set():
    db = FakeDB(
        coach_memory=[{"user_id": "u1", "learning": {"current_focus": "hanging_piece"}}],
        postgame_analyses=[{
            "user_id": "u1",
            "coach_prescription": "hanging_piece",
            "prescription_reason": "This happened 3 times.",
            "prescription_type": "pattern_drill",
            "created_at": "2025-01-01",
        }],
    )
    top = [{"category": "tactical_miss", "label": "X", "count": 2}]
    result = asyncio.run(get_active_focus(db, "u1", top))
    assert result["source"] == "brain"
    assert result["focus"] == "hanging_piece"
    assert result["gap"] == "piece_safety"
    assert result["category"] == "one_move_blunder"
    assert result["reason"] == "This happened 3 times."


def test_aggregate_overrides_stuck_brain():
    """Brain picks hanging_piece; aggregate says opening_disaster is 3x+ more common."""
    db = FakeDB(
        coach_memory=[{"user_id": "u1", "learning": {"current_focus": "hanging_piece"}}],
        postgame_analyses=[{
            "user_id": "u1",
            "coach_prescription": "hanging_piece",
            "prescription_reason": "R",
            "prescription_type": "pattern_drill",
        }],
    )
    # Opening disaster dominates 9 vs hanging's 1 → sanity override
    top = [
        {"category": "opening_disaster", "label": "Opening", "count": 9},
        {"category": "one_move_blunder", "label": "Hanging", "count": 1},
    ]
    result = asyncio.run(get_active_focus(db, "u1", top))
    assert result["source"] == "aggregate", f"Expected aggregate override, got {result}"
    assert result["focus"] == "opening_disaster"


def test_brain_wins_when_aggregate_doesnt_dominate():
    """If brain says X and aggregate agrees or is close, brain wins."""
    db = FakeDB(
        coach_memory=[{"user_id": "u1", "learning": {"current_focus": "hanging_piece"}}],
        postgame_analyses=[],
    )
    top = [
        {"category": "one_move_blunder", "label": "H", "count": 4},
        {"category": "tactical_miss", "label": "T", "count": 3},
    ]
    result = asyncio.run(get_active_focus(db, "u1", top))
    assert result["source"] == "brain"
    assert result["focus"] == "hanging_piece"


def test_prefix_focus_trap():
    db = FakeDB(
        coach_memory=[{"user_id": "u1", "learning": {"current_focus": "trap:italian_game:bishop_trap"}}],
        postgame_analyses=[{
            "user_id": "u1",
            "coach_prescription": "trap:italian_game:bishop_trap",
            "prescription_reason": "Learn this trap.",
            "prescription_type": "trap_lesson",
        }],
    )
    result = asyncio.run(get_active_focus(db, "u1", None))
    assert result["source"] == "brain"
    assert result["focus"].startswith("trap:")
    assert result["category"] == "opening_disaster"
    assert result["gap"] == "opening_knowledge"
    assert result["type"] == "trap_lesson"


def test_focus_to_gap_mapping_complete():
    """Every prescription type in _pick_prescription has a gap mapping."""
    expected = {
        "hanging_piece", "missed_fork", "missed_pin", "missed_skewer",
        "missed_discovery", "missed_overload", "king_safety", "tactical_error",
    }
    assert expected <= set(FOCUS_TO_GAP.keys())
    assert expected <= set(FOCUS_TO_CATEGORY.keys())


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
