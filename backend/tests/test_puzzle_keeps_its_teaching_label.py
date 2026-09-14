"""A rebuilt puzzle keeps the label that says what it teaches.

`_resolve_pool_row` has two exits. When the row came from an imported game it
rebuilds the puzzle from the current analysis -- which is right, because a
stale board must never be graded -- and then returned only that rebuild plus
`puzzle_id` and `source`. The curated row's `issue_type` and `difficulty` were
dropped on the floor.

The diagnostic copies `issue_type` straight out of that dict into the attempt
record, so every attempt stored null. That emptied `per_category`, which
emptied `growth_areas`, which made `_worst_issue_type` return None, which made
`apply_diagnosis_to_training` return before writing anything at all.

Observed end to end on 2026-09-14 (user_ed32375808ad): twenty positions
answered, twenty attempts recorded with `issue_type: null`, a stored diagnosis
with `per_category: []` and `growth_areas: []`, no player_profiles document,
no `coach_memory.learning.current_focus`, and an admin panel reading
"Focus: -- / Current focus: (none set)". The source puzzles themselves were
perfectly labelled: piece_safety 5, missed_tactic 5, calculation_depth 5,
opening_knowledge 5.

One dropped field emptied the whole diagnosis.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import services.verified_puzzle_runtime as runtime


ROW = {
    "position_id": "pos-1",
    "source_game_id": "game-1",
    "move_number": 24,
    "fen": "8/8/8/8/8/8/8/K6k w - - 0 1",
    "issue_type": "piece_safety",
    "difficulty": "intermediate",
    "opening_name": "Italian Game",
}

REBUILT = {
    "puzzle_id": "game-1_m24",
    "fen": "8/8/8/8/8/8/8/K6k w - - 0 1",
    "best_move_san": "Ka2",
    "best_move_uci": "a1a2",
    "pattern_type": "calculation_depth",
    "verified_admission": {"status": "admitted"},
    "source": "imported_game",
}


def _resolve(row, rebuilt, monkeypatch):
    async def fake_imported(db, **kwargs):
        return dict(rebuilt) if rebuilt else None

    monkeypatch.setattr(runtime, "_resolve_imported", fake_imported)
    return asyncio.run(runtime._resolve_pool_row(None, dict(row), user_id=None))


def test_the_curated_label_survives_the_rebuild(monkeypatch):
    puzzle = _resolve(ROW, REBUILT, monkeypatch)
    assert puzzle["issue_type"] == "piece_safety", (
        "the diagnostic records this field verbatim; null here empties the "
        "entire diagnosis"
    )
    assert puzzle["difficulty"] == "intermediate"


def test_the_rebuild_still_owns_the_board(monkeypatch):
    # The whole point of rebuilding is that a stale board is never graded.
    # Carrying labels across must not carry a stale position with them.
    stale = dict(ROW, fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                 best_move_san="e4")
    puzzle = _resolve(stale, REBUILT, monkeypatch)
    assert puzzle["fen"] == REBUILT["fen"]
    assert puzzle["best_move_san"] == REBUILT["best_move_san"]
    assert puzzle["verified_admission"] == REBUILT["verified_admission"]


def test_a_row_with_no_label_falls_back_to_the_rebuilds_category(monkeypatch):
    # Same taxonomy family, so this classifies rather than recording null.
    unlabelled = {k: v for k, v in ROW.items() if k != "issue_type"}
    puzzle = _resolve(unlabelled, REBUILT, monkeypatch)
    assert puzzle["issue_type"] == "calculation_depth"


def test_an_explicit_null_label_is_still_replaced(monkeypatch):
    puzzle = _resolve(dict(ROW, issue_type=None), REBUILT, monkeypatch)
    assert puzzle["issue_type"] == "calculation_depth"


def test_a_label_the_rebuild_already_carries_is_not_overwritten(monkeypatch):
    rebuilt = dict(REBUILT, issue_type="king_safety")
    puzzle = _resolve(ROW, rebuilt, monkeypatch)
    assert puzzle["issue_type"] == "king_safety"


def test_scoring_produces_a_focus_once_the_label_is_present():
    # The consequence the field exists for: with labels, the scorer fills
    # per_category and the diagnosis can name where to start.
    from services.diagnostic_service import score_diagnostic

    attempts = [
        {"issue_type": "piece_safety", "difficulty": "intermediate",
         "is_correct": False},
        {"issue_type": "piece_safety", "difficulty": "intermediate",
         "is_correct": False},
        {"issue_type": "missed_tactic", "difficulty": "intermediate",
         "is_correct": True},
        {"issue_type": "missed_tactic", "difficulty": "intermediate",
         "is_correct": True},
    ]
    scored = score_diagnostic(attempts)
    assert scored["per_category"], "labelled attempts must produce categories"
    assert scored["growth_areas"], "and a place to start"

    nulls = [dict(a, issue_type=None) for a in attempts]
    assert not score_diagnostic(nulls)["per_category"], (
        "this is what the player actually got: twenty answers, nothing to say"
    )
