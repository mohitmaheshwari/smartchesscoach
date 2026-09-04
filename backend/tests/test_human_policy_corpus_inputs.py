"""Clock semantics, position keys, and frozen split joins are explicit."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.human_chess_intelligence.corpus_inputs import (  # noqa: E402
    build_user_trajectory,
    match_observations_to_trajectory,
    normalized_position_key,
    numeric_time_control,
    split_game_records,
)


PGN = '''[Event "test"]
[White "A"]
[Black "B"]
[Result "*"]
[TimeControl "300+5"]

1. e4 {[%clk 0:05:04]} e5 {[%clk 0:05:01]} 2. Nf3 {[%clk 0:05:08]} Nc6 {[%clk 0:04:53]} *
'''


def test_clock_before_move_uses_previous_own_clock_not_current_annotation():
    black = build_user_trajectory(PGN, "black")
    assert [entry.move_uci for entry in black] == ["e7e5", "b8c6"]
    assert black[0].clock_fraction == 1.0
    # Increment can exceed base, but the model contract requires a fraction in [0, 1].
    assert black[1].clock_fraction == 1.0
    assert black[1].history_moves == ("e2e4", "e7e5", "g1f3")


def test_missing_annotation_is_not_filled_for_the_next_move():
    missing = PGN.replace("e5 {[%clk 0:05:01]}", "e5")
    black = build_user_trajectory(missing, "black")
    assert black[0].clock_fraction == 1.0
    assert black[1].clock_fraction is None


def test_numeric_time_control_rejects_categories_instead_of_inventing_seconds():
    assert numeric_time_control("300+5") == ("300+5", 300, 5)
    assert numeric_time_control("600") == ("600+0", 600, 0)
    assert numeric_time_control("blitz") is None
    assert numeric_time_control("daily") is None


def test_observations_join_by_legal_state_and_move_not_row_order():
    trajectory = build_user_trajectory(PGN, "white")
    observations = [
        {"ply": 3, "fen_before": trajectory[1].fen, "move_uci": "g1f3"},
        {"ply": 1, "fen_before": trajectory[0].fen, "move_uci": "e2e4"},
    ]
    matched, failures = match_observations_to_trajectory(observations, trajectory)
    assert failures == 0
    assert [entry.move_uci for _, entry in matched] == ["e2e4", "g1f3"]
    assert normalized_position_key(trajectory[0].fen).endswith("w KQkq -")


def test_manifest_cutoffs_select_history_and_future_without_overlap():
    games = [
        {"user_id": "u1", "game_id": f"g{i}", "played_date": f"2026-01-{i + 1:02d}"}
        for i in range(4)
    ]
    manifest = {
        "games": games,
        "users": [{
            "user_id": "u1",
            "split_cutoffs": {
                "chosen": {"evaluation_start_inclusive": 2, "evaluation_end_exclusive": 4}
            },
        }],
    }
    history, evaluation = split_game_records(manifest, "chosen")
    assert [row["game_id"] for row in history] == ["g0", "g1"]
    assert [row["game_id"] for row in evaluation] == ["g2", "g3"]
    assert {row["game_id"] for row in history}.isdisjoint(row["game_id"] for row in evaluation)
