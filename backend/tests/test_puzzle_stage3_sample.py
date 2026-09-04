from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.build_puzzle_stage3_sample import (
    build_candidates,
    normalize_difficulty,
    select_balanced,
)


def _puzzle(identifier, fen, answers, difficulty, status="broad", concept="piece_safety"):
    return {
        "_id": identifier,
        "position_id": identifier,
        "fen": fen,
        "difficulty": difficulty,
        "issue_type": concept,
        "verified_admission": {
            "status": status,
            "acceptable_moves_uci": answers,
            "concept_id": concept,
        },
    }


def test_difficulty_normalization_uses_existing_labels_only():
    assert normalize_difficulty("beginner") == "easy"
    assert normalize_difficulty("intermediate") == "medium"
    assert normalize_difficulty("advanced") == "hard"
    assert normalize_difficulty("mystery") == "unknown"


def test_builder_excludes_quarantine_and_conflicting_cross_pool_answers():
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    community = [
        _puzzle("same", fen, ["e2e4"], "beginner"),
        _puzzle("quarantine", "8/8/8/8/8/8/4K3/7k w - - 0 1", ["e2e3"], "hard", "quarantine"),
    ]
    training = [_puzzle("other", fen, ["d2d4"], "easy")]
    candidates, counts = build_candidates(community, training)
    assert candidates == []
    assert counts["quarantined"] == 1
    assert counts["conflicting_positions_removed"] == 1


def test_balanced_selection_reaches_each_primary_stratum():
    rows = [
        {
            "pool": pool,
            "puzzle_ref": f"{pool}-{difficulty}",
            "difficulty": difficulty,
            "admission_status": "broad",
            "concept_family": "piece_safety",
        }
        for pool in ("community_puzzles", "community_training_positions")
        for difficulty in ("easy", "hard")
    ]
    selected = select_balanced(rows, limit=4, seed="fixed")
    assert len({
        (row["pool"], row["difficulty"], row["admission_status"])
        for row in selected
    }) == 4
