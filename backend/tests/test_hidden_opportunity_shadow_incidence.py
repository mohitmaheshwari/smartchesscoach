import inspect
import json

from scripts.report_hidden_opportunity_shadow_incidence import (
    build_incidence_report,
)
from services.game_review_shadow_runtime import (
    evaluate_hidden_opportunity_stored_row,
)


def test_incidence_report_is_aggregate_only(monkeypatch):
    candidate = {
        "status": "candidate",
        "candidate": {
            "selection_features": {"actor": "opponent"},
            "proof": {"family": "forcing_tempo_and_move_order"},
        },
    }
    monkeypatch.setattr(
        "scripts.report_hidden_opportunity_shadow_incidence."
        "evaluate_hidden_opportunity_stored_row",
        lambda **_: candidate,
    )
    report = build_incidence_report(
        games=[{
            "game_id": "secret-game",
            "user_color": "white",
            "white_rating": 1200,
            "black_rating": 1250,
            "email": "never@example.com",
        }],
        analyses=[{
            "game_id": "secret-game",
            "stockfish_analysis": {
                "move_evaluations": [{
                    "fen_before": "fen",
                    "move": "e2e4",
                    "best_move": "d2d4",
                }],
                "opponent_move_evaluations": [{
                    "fen_before": "fen",
                    "move": "e2e4",
                    "best_move": "d2d4",
                }],
            },
        }],
    )
    assert report["coverage"]["candidate_count"] == 1
    assert report["coverage"]["duplicate_positions_skipped"] == 1
    assert report["coverage"]["candidate_actor_counts"] == {"opponent": 1}
    encoded = json.dumps(report).lower()
    assert "secret-game" not in encoded
    assert "never@example.com" not in encoded
    assert "fen_before" not in encoded


def test_incidence_script_is_read_only_and_uses_canonical_runtime():
    import scripts.report_hidden_opportunity_shadow_incidence as module

    source = inspect.getsource(module).lower()
    assert "evaluate_hidden_opportunity_stored_row" in source
    assert "insert_one" not in source
    assert "update_one" not in source
    assert "replace_one" not in source
    assert "delete_" not in source
    assert "chess.engine" not in source
    assert "openai" not in source
    assert "anthropic" not in source
    assert evaluate_hidden_opportunity_stored_row is not None
