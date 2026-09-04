import base64
import json

import pytest

from scripts.export_full_game_chess_fact_audit import (
    actor_rating,
    assert_private,
    hidden_opportunity_candidates_for_game,
    load_target_line_excluded_signatures,
    select_target_line_candidates,
    target_line_position,
)
from scripts.run_target_line_population_export import prior_evidence_signatures


def _candidate(index, phase):
    return {
        "source_game_id": f"private-game-{index}",
        "position_signature": f"signature-{index}",
        "rank": f"{index:04d}",
        "position": {"phase": phase, "marker": index},
    }


def test_target_line_position_normalizes_both_stored_branches_to_san():
    position = target_line_position(
        {
            "fen_before": (
                "rnbqkbnr/pppppppp/8/8/8/8/"
                "PPPPPPPP/RNBQKBNR w KQkq - 0 1"
            ),
            "move": "e4",
            "best_move": "d4",
            "pv_after_played": ["e5", "Nf3", "Nc6", "Bb5"],
            "pv_after_best": ["d5", "c4", "e6", "Nc3"],
            "cp_loss": 150,
        },
        "900-1199",
    )

    assert position["played_san"] == "e4"
    assert position["best_move_san"] == "d4"
    assert position["pv_after_played"] == ["e5", "Nf3", "Nc6", "Bb5"]
    assert position["pv_after_best"] == ["d5", "c4", "e6", "Nc3"]
    assert position["side_to_move"] == "white"
    assert set(position) == {
        "rating_band",
        "phase",
        "fen_before",
        "side_to_move",
        "played_san",
        "best_move_san",
        "pv_after_played",
        "pv_after_best",
        "cp_loss",
    }


def test_target_line_position_skips_repeated_first_move_across_notations():
    position = target_line_position(
        {
            "fen_before": (
                "rnbqkbnr/pppppppp/8/8/8/8/"
                "PPPPPPPP/RNBQKBNR w KQkq - 0 1"
            ),
            "move_uci": "e2e4",
            "best_move_uci": "d2d4",
            "pv_after_played": ["e4", "e5", "Nf3", "Nc6", "Bb5"],
            "pv_after_best": ["d4", "d5", "c4", "e6", "Nc3"],
            "cp_loss": 150,
        },
        "900-1199",
    )

    assert position["pv_after_played"] == ["e5", "Nf3", "Nc6", "Bb5"]
    assert position["pv_after_best"] == ["d5", "c4", "e6", "Nc3"]


def test_target_line_selection_covers_phases_and_uses_distinct_games():
    candidates = []
    index = 0
    for phase in ("opening", "middlegame", "endgame"):
        for _ in range(4):
            candidates.append(_candidate(index, phase))
            index += 1

    selected = select_target_line_candidates(
        candidates, total=9, phase_minimum=2
    )

    assert len(selected) == 9
    assert len({row["source_game_id"] for row in selected}) == 9
    assert len({row["position_signature"] for row in selected}) == 9
    assert all(
        sum(row["position"]["phase"] == phase for row in selected) >= 2
        for phase in ("opening", "middlegame", "endgame")
    )


def test_target_line_selection_rejects_thin_phase_cells():
    candidates = [_candidate(index, "opening") for index in range(10)]

    with pytest.raises(ValueError, match="thin target-line phase"):
        select_target_line_candidates(
            candidates, total=6, phase_minimum=2
        )


def test_export_privacy_guard_rejects_identity_keys_and_values():
    with pytest.raises(ValueError, match="forbidden output key"):
        assert_private({"game_id": "secret-game"}, {"secret-game"})

    with pytest.raises(ValueError, match="source identifier"):
        assert_private({"value": "secret-game"}, {"secret-game"})


def test_target_line_exclusion_payload_is_strict_and_content_only(monkeypatch):
    signature = "a" * 64
    encoded = base64.b64encode(json.dumps([signature]).encode()).decode()
    monkeypatch.setenv("TARGET_LINE_EXCLUDED_SIGNATURES_B64", encoded)
    assert load_target_line_excluded_signatures() == {signature}

    malformed = base64.b64encode(json.dumps(["not-a-hash"]).encode()).decode()
    monkeypatch.setenv("TARGET_LINE_EXCLUDED_SIGNATURES_B64", malformed)
    with pytest.raises(ValueError, match="invalid target-line exclusion"):
        load_target_line_excluded_signatures()


def test_second_population_export_excludes_every_first_export_position():
    original_exclusions = prior_evidence_signatures()
    holdout_exclusions = prior_evidence_signatures(
        include_original_population=True
    )
    newly_excluded = holdout_exclusions - original_exclusions

    assert len(original_exclusions) == 664
    assert len(newly_excluded) == 1500
    assert len(holdout_exclusions) == 2164


def _exact_target_line_item():
    packet_path = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "data/corpus_snapshots/hidden_opportunities_chess_gold_v1_2026-09-02.json"
    )
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    row = next(
        item
        for item in packet["positions"]
        if item["position_id"] == "00d2ea0ceda1a2e6ef83"
    )
    return {
        "fen_before": row["fen"],
        "move_uci": row["played_move"]["uci"],
        "best_move_uci": row["best_move"]["uci"],
        "pv_after_played": row["stored_four_ply"]["after_played"],
        "pv_after_best": row["stored_four_ply"]["after_best"],
        "cp_loss": row["cp_loss"],
        "is_critical": True,
        "eval_before": 0,
        "eval_after": -500,
    }


def test_actor_rating_uses_actual_side_to_move():
    white_to_move = _exact_target_line_item()
    game = {
        "user_color": "black",
        "user_rating": 1300,
        "opponent_rating": 1190,
        "white_rating": 1210,
        "black_rating": 1310,
    }

    assert actor_rating(game, white_to_move) == 1210


def test_hidden_opportunity_candidates_cover_opponent_and_deduplicate():
    item = _exact_target_line_item()
    game = {
        "user_color": "black",
        "user_rating": 1300,
        "opponent_rating": 1210,
        "white_rating": 1210,
        "black_rating": 1300,
    }
    analysis = {
        "stockfish_analysis": {
            "move_evaluations": [item],
            "opponent_move_evaluations": [dict(item)],
        }
    }

    candidates = hidden_opportunity_candidates_for_game(game, analysis)

    assert len(candidates) == 1
    assert candidates[0]["actor"] == "opponent"
    assert candidates[0]["actor_rating_band"] == "1200-1499"
    assert candidates[0]["proof"]["family"] == (
        "target_and_line_geometry_with_payoff"
    )
