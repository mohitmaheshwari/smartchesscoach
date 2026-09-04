from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.run_puzzle_stage3_shadow_bakeoff import spearman, summarize


def test_spearman_handles_ties_and_direction():
    assert round(spearman([1, 2, 3], [10, 20, 30]), 6) == 1.0
    assert round(spearman([1, 2, 3], [30, 20, 10]), 6) == -1.0
    assert spearman([1, 1, 1], [2, 3, 4]) is None


def test_summary_reports_shadow_probability_and_engine_verified_distractor():
    records = [{
        "pool": "community_puzzles",
        "difficulty": "easy",
        "admission_status": "broad",
        "concept_family": "tactics",
        "cp_loss": 400,
        "ratings": {
            "800": {
                "target_probability": 0.2,
                "best_acceptable_rank": 2,
                "distractor_probability": 0.3,
                "distractor_loss_cp": 180,
                "distractor_changes_wdl": True,
                "acceptable_preserves_wdl": True,
            },
            "1200": {
                "target_probability": 0.4,
                "best_acceptable_rank": 1,
                "distractor_probability": 0.2,
                "distractor_loss_cp": 180,
                "distractor_changes_wdl": True,
                "acceptable_preserves_wdl": True,
            },
        },
    }]
    result = summarize(records, [800, 1200])
    assert result["ratings"]["800"]["target_probability"]["median"] == 0.2
    assert result["ratings"]["800"]["top_wrong_loss_at_least_cp"]["150"] == 1.0
    assert result["target_probability_non_decreasing_with_rating_rate"] == 1.0
