from pathlib import Path
import sys

import chess
import chess.engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.run_sound_findable_bakeoff import (
    _safe_human_choice,
    _score_cp,
    _summarize,
    _wdl_outcome,
)


def test_score_is_normalized_to_root_side_to_move():
    info = {"score": chess.engine.PovScore(chess.engine.Cp(75), chess.WHITE)}
    assert _score_cp(info, chess.WHITE) == 75
    assert _score_cp(info, chess.BLACK) == -75


def test_human_policy_can_rank_only_inside_soundness_band():
    candidates = [
        {"move_uci": "e2e4", "loss_cp": 0, "rank": 1},
        {"move_uci": "d2d4", "loss_cp": 40, "rank": 2},
        {"move_uci": "g1f3", "loss_cp": 120, "rank": 3},
    ]
    probabilities = {"e2e4": 0.1, "d2d4": 0.4, "g1f3": 0.5}
    assert _safe_human_choice(candidates, probabilities, 50)["move_uci"] == "d2d4"
    assert _safe_human_choice(candidates, probabilities, 25)["move_uci"] == "e2e4"


def test_wdl_outcome_uses_largest_engine_probability_mass():
    assert _wdl_outcome((700, 200, 100)) == "win"
    assert _wdl_outcome((100, 800, 100)) == "draw"
    assert _wdl_outcome((100, 200, 700)) == "loss"


def test_summary_keeps_unknown_wdl_out_of_preservation_denominator():
    records = [{
        "rating_band": "600-999",
        "phase": "opening",
        "error_band": "cp_loss_200_plus",
        "concept_family": "piece_safety",
        "bands": {
            "50": {
                "safe_count": 2,
                "truncation_risk": False,
                "choice_differs": True,
                "selected_loss_cp": 40,
                "selected_model_rank": 1,
                "selected_probability": 0.4,
                "engine_best_probability": 0.1,
                "probability_uplift": 0.3,
                "wdl_outcome_preserved": None,
            }
        },
        "current_guard": {
            "candidate_count": 4,
            "moves_outside_probe_multipv": 0,
            "human_choice_available": True,
            "selected_loss_cp": 40,
            "wdl_outcome_preserved": None,
        },
    }]
    summary = _summarize(records, [50])
    assert summary["bands"]["50"]["engine_wdl_outcome_preserved_rate"] is None
    assert summary["bands"]["50"]["selected_loss_cp"]["median"] == 40
