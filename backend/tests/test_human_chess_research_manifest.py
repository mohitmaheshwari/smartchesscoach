"""Stage 0 manifest is deterministic, privacy-minimized, and leakage-aware."""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_human_chess_research_manifest import (  # noqa: E402
    MANIFEST_SCHEMA_VERSION,
    build_game_record,
    build_manifest,
)


def pgn(*, missing_black_clock: bool = False, variation_clock: bool = False) -> str:
    black_one = "" if missing_black_clock else " {[%clk 0:09:59]}"
    variation = " (1... c5 {[%clk 0:09:58]})" if variation_clock else ""
    return (
        '[Event "Rated Rapid game"]\n'
        '[White "alice"]\n[Black "bob"]\n'
        '[WhiteElo "1200"]\n[BlackElo "1300"]\n'
        '[TimeControl "600+0"]\n\n'
        f'1. e4 {{[%clk 0:09:58]}} e5{black_one}{variation} '
        '2. Nf3 {[%clk 0:09:51]} Nc6 {[%clk 0:09:50]} *'
    )


def game(index: int, **overrides):
    value = {
        "game_id": f"g{index}",
        "user_id": "u1",
        "platform": "chess.com",
        "pgn": pgn(),
        "user_color": "white",
        "user_rating": 1200,
        "opponent_rating": 1300,
        "date_played": f"2026.08.{index:02d}",
        "date_played_iso": f"2026-08-{index:02d}",
        "time_control": "600+0",
        "time_control_category": "rapid",
        "human_model": {
            "player_elo": 1200,
            "opponent_elo": 1300,
            "clocks_s": [598, 599, 591, 590],
            "clock_ply_count": 4,
            "schema_version": "human_model_prereq.v1",
        },
    }
    value.update(overrides)
    return value


def test_complete_mainline_clock_series_is_qualified_and_reproducible():
    record, reason = build_game_record(game(1), {"g1"})
    assert reason is None
    assert record["mainline_ply_count"] == 4
    assert record["clock_annotated_ply_count"] == 4
    assert record["clock_complete"] is True
    assert record["clock_matches_v1"] is True
    assert record["clock_qualified"] is True
    assert record["stored_prerequisite_status"] == "match"
    assert record["stored_prerequisite_matches_producer"] is True


def test_missing_clock_keeps_game_but_disqualifies_clock_track():
    row = game(1, pgn=pgn(missing_black_clock=True), human_model={})
    record, reason = build_game_record(row, {"g1"})
    assert reason is None
    assert record["mainline_ply_count"] == 4
    assert record["clock_annotated_ply_count"] == 3
    assert record["clock_complete"] is False
    assert record["clock_qualified"] is False
    assert record["stored_prerequisite_status"] == "missing"


def test_variation_clock_cannot_shift_the_v1_series_silently():
    row = game(1, pgn=pgn(variation_clock=True), human_model={})
    record, reason = build_game_record(row, {"g1"})
    assert reason is None
    assert record["clock_complete"] is True
    assert record["clock_matches_v1"] is False
    assert record["clock_qualified"] is False


def test_coach_games_and_games_without_stored_analysis_are_excluded():
    _, reason = build_game_record(game(1, platform="coach"), {"g1"})
    assert reason == "non_external_platform"
    _, reason = build_game_record(game(1), set())
    assert reason == "missing_stored_analysis"


def test_target_rating_and_trusted_date_are_hard_eligibility_contracts():
    _, reason = build_game_record(game(1, user_rating=1700, human_model={}), {"g1"})
    assert reason == "outside_target_rating"
    _, reason = build_game_record(
        game(1, date_played=None, date_played_iso=None), {"g1"}
    )
    assert reason == "missing_trusted_play_date"


def test_manifest_is_deterministic_and_records_split_cutoffs_without_copying_pgn():
    games = []
    for index in range(1, 9):
        row = game(index)
        # Exact PGN text is intentionally varied without changing chess content,
        # preventing the fixture from looking like duplicate imported games.
        row["pgn"] = row["pgn"].replace('[Event "Rated Rapid game"]', f'[Event "game {index}"]')
        row["human_model"] = {}
        games.append(row)
    analyzed = {row["game_id"] for row in games}

    first = build_manifest(
        reversed(games),
        analyzed,
        generated_at="2026-08-31T00:00:00+00:00",
        source_revision="abc123",
    )
    second = build_manifest(
        games,
        analyzed,
        generated_at="2026-08-31T00:00:00+00:00",
        source_revision="abc123",
    )

    assert first["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert first["hashes"] == second["hashes"]
    assert first["counts"]["eligible_games"] == 8
    assert first["split_candidates"]["min_history_5_future_3"]["eligible_users"] == 1
    cut = first["users"][0]["split_cutoffs"]["min_history_5_future_3"]
    assert cut == {
        "history_end_exclusive": 5,
        "evaluation_start_inclusive": 5,
        "evaluation_end_exclusive": 8,
    }
    assert "pgn" not in first["games"][0]
    assert "alice" not in str(first)
    assert "bob" not in str(first)


def test_exact_duplicate_pgn_is_removed_even_when_game_id_changes():
    first = game(1)
    second = deepcopy(first)
    second["game_id"] = "g2"
    second["date_played"] = "2026.08.02"
    second["date_played_iso"] = "2026-08-02"
    manifest = build_manifest(
        [first, second],
        {"g1", "g2"},
        generated_at="2026-08-31T00:00:00+00:00",
        source_revision="abc123",
    )
    assert manifest["counts"]["eligible_games"] == 1
    assert manifest["counts"]["exclusions"]["duplicate_pgn"] == 1
