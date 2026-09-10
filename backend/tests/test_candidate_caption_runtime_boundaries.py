"""Last-wire contracts for candidate-aware captions."""
from __future__ import annotations

import ast
import inspect
import sys
import textwrap

import pytest

from scripts import backfill_candidate_caption_evidence as backfill
from services.game_decryption_v5_service import generate_game_decryption_v5


def _called_names(function):
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_v5_render_never_calls_fresh_candidate_tablebase_or_human_model():
    calls = _called_names(generate_game_decryption_v5)
    assert "_get_stockfish_candidates" not in calls
    assert "probe_configured_fathom" not in calls
    assert "_derive_human_policy_evidence" not in calls
    source = inspect.getsource(generate_game_decryption_v5)
    assert "_candidate_comparison_visible_for_user" not in source
    assert '"candidate_comparison"\n                    ] = _comparison.public_dict()' in source


def test_backfill_is_bounded_and_apply_requires_prior_plan(monkeypatch):
    assert backfill.MAX_GAMES == 10
    monkeypatch.setattr(sys, "argv", [
        "backfill_candidate_caption_evidence.py",
        "--user-id", "u1",
        "--apply",
    ])
    with pytest.raises(SystemExit):
        backfill.parse_args()


def test_backfill_guard_binds_version_and_each_changed_source_row():
    analysis = {
        "_id": "analysis-1",
        "decryption_v5_version": 149,
        "stockfish_analysis": {
            "move_evaluations": [
                {"fen_before": "fen-1", "move_uci": "a1a2", "cp_loss": 100},
                {"fen_before": "fen-2", "move_uci": "b1b2", "cp_loss": 200},
            ],
        },
    }
    guard = backfill._update_guard(analysis, [1])
    assert guard == {
        "_id": "analysis-1",
        "decryption_v5_version": 149,
        "stockfish_analysis.move_evaluations.1.fen_before": "fen-2",
        "stockfish_analysis.move_evaluations.1.move_uci": "b1b2",
        "stockfish_analysis.move_evaluations.1.cp_loss": 200,
    }


def test_candidate_flags_are_declared_default_off_in_both_compose_files():
    root = backfill.Path(__file__).resolve().parents[2]
    for filename in ("docker-compose.yml", "docker-compose.prod.yml"):
        text = (root / filename).read_text(encoding="utf-8")
        for name in (
            "CANDIDATE_CAPTION_ENRICHMENT_ENABLED",
            "CANDIDATE_CAUSAL_CAPTIONS_ENABLED",
            "CANDIDATE_LESSON_REASONS_ENABLED",
        ):
            assert f"{name}=${{{name}:-false}}" in text
