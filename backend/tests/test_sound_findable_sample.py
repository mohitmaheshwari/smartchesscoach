from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.build_sound_findable_sample import (
    _primary_strata_counts,
    _selection_summary,
    build_candidates,
    select_balanced_sample,
)


def _row(game_id, ply, rating, phase, error, concept):
    return {
        "game_id": game_id,
        "ply": ply,
        "rating_band": rating,
        "phase": phase,
        "error_band": error,
        "concept_family": concept,
    }


def test_balanced_sample_is_deterministic_and_reaches_primary_strata():
    rows = [
        _row("a", 1, "600-999", "opening", "cp_loss_100_149", "piece_safety"),
        _row("b", 2, "600-999", "opening", "cp_loss_100_149", "king_safety"),
        _row("c", 3, "1000-1399", "endgame", "cp_loss_200_plus", "endgame_technique"),
        _row("d", 4, "1000-1399", "endgame", "cp_loss_200_plus", "piece_safety"),
    ]
    first = select_balanced_sample(rows, limit=2, seed="fixed")
    second = select_balanced_sample(list(reversed(rows)), limit=2, seed="fixed")
    assert first == second
    assert {row["rating_band"] for row in first} == {"600-999", "1000-1399"}


def test_concept_round_robin_prevents_one_family_from_filling_a_stratum():
    rows = [
        _row(f"p{i}", i, "600-999", "opening", "cp_loss_200_plus", "piece_safety")
        for i in range(10)
    ] + [
        _row("k", 99, "600-999", "opening", "cp_loss_200_plus", "king_safety")
    ]
    selected = select_balanced_sample(rows, limit=2, seed="fixed")
    assert {row["concept_family"] for row in selected} == {"piece_safety", "king_safety"}


def test_candidate_builder_deduplicates_positions_and_exports_no_board():
    observations = [
        {
            "game_id": "g1",
            "ply": 1,
            "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "move_uci": "e2e4",
            "phase": "opening",
            "cp_loss": 120,
            "missed_pattern": "piece_safety",
        },
        {
            "game_id": "g2",
            "ply": 3,
            "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 5 9",
            "move_uci": "d2d4",
            "phase": "opening",
            "cp_loss": 220,
        },
    ]
    candidates, counts = build_candidates(observations, {"g1": 900, "g2": 1100})
    assert len(candidates) == 1
    assert counts["duplicate_positions_removed"] == 1
    assert "fen_before" not in candidates[0]
    assert "move_uci" not in candidates[0]


def test_selection_summary_exposes_intersection_coverage_without_board_data():
    rows = [
        _row("a", 1, "600-999", "opening", "cp_loss_100_149", "piece_safety"),
        _row("b", 2, "600-999", "opening", "cp_loss_100_149", "unnamed"),
        _row("c", 3, "1000-1399", "endgame", "cp_loss_200_plus", "endgame_technique"),
    ]
    counts = _primary_strata_counts(rows)
    summary = _selection_summary(rows)
    assert counts == {
        "1000-1399|endgame|cp_loss_200_plus": 1,
        "600-999|opening|cp_loss_100_149": 2,
    }
    assert summary["populated_primary_strata"] == 2
    assert summary["primary_stratum_size"] == {
        "minimum": 1,
        "median": 1.5,
        "maximum": 2,
    }
    assert summary["named_count"] == 2
    assert summary["unnamed_count"] == 1
