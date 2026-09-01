"""Contract tests for the canonical piece_safety.d_live.v1 observation fact."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.move_observation_deriver import (
    DERIVER_SEMANTIC_VERSION,
    D_LIVE_FACT_VERSION,
    SCHEMA_VERSION,
    _derive_d_live_fact,
    current_deriver_identity,
    derive_observations_for_game,
)


HANG_FEN = "4k3/8/4p2p/8/8/5N2/8/4K3 w - - 0 1"
SAFE_EXCHANGE_FEN = "4k3/8/7q/8/7P/5N2/8/4K3 w - - 0 1"


def _move(fen, uci, cp_loss):
    return {
        "fen_before": fen,
        "move_uci": uci,
        "move_number": 1,
        "move": "Ng5",
        "cp_loss": cp_loss,
        "evaluation": "mistake" if cp_loss >= 150 else "good",
        "cognitive_gap": "piece_safety" if cp_loss >= 150 else None,
    }


def test_schema_bumps_for_additive_d_live_fact():
    assert SCHEMA_VERSION == 17


def test_legally_capturable_losing_piece_is_miss_when_both_gates_pass():
    fact = _derive_d_live_fact(_move(HANG_FEN, "f3g5", 200))

    assert fact["version"] == D_LIVE_FACT_VERSION
    assert fact["eligible"] is True
    assert fact["legal_destination_captures"] == 1
    assert fact["destination_see_cp"] >= 150
    assert fact["stockfish_cp_loss"] == 200
    assert fact["outcome"] == "miss"


def test_same_exchange_is_handled_when_stockfish_gate_does_not_pass():
    fact = _derive_d_live_fact(_move(HANG_FEN, "f3g5", 100))

    assert fact["eligible"] is True
    assert fact["destination_see_cp"] >= 150
    assert fact["outcome"] == "handled"


def test_legal_capture_with_unfavorable_exchange_is_handled():
    fact = _derive_d_live_fact(_move(SAFE_EXCHANGE_FEN, "f3g5", 200))

    assert fact["eligible"] is True
    assert fact["legal_destination_captures"] == 1
    assert fact["destination_see_cp"] < 150
    assert fact["outcome"] == "handled"


def test_pawn_move_is_not_an_eligible_d_live_decision():
    fact = _derive_d_live_fact(
        _move("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1", "e2e4", 200)
    )

    assert fact["eligible"] is False
    assert fact["reason"] == "piece_not_eligible"
    assert fact["outcome"] == "not_eligible"


def test_invalid_position_is_unavailable_not_handled():
    fact = _derive_d_live_fact(_move("", "f3g5", 200))

    assert fact["derivation_status"] == "unavailable"
    assert fact["eligible"] is False
    assert fact["outcome"] == "not_eligible"


def test_game_derivation_embeds_exact_versioned_fact():
    observations = derive_observations_for_game(
        {"move_evaluations": [_move(HANG_FEN, "f3g5", 200)]},
        game_id="game-1",
        user_id="user-1",
        user_color="white",
    )

    assert len(observations) == 1
    assert observations[0]["schema_version"] == 17
    assert observations[0]["deriver_identity"] == current_deriver_identity()
    assert observations[0]["piece_safety_decision"]["version"] == D_LIVE_FACT_VERSION
    assert observations[0]["piece_safety_decision"]["outcome"] == "miss"


def test_deriver_identity_is_deterministic_complete_and_defensively_copied():
    first = current_deriver_identity()
    second = current_deriver_identity()

    assert first == second
    assert first is not second
    assert first["semantic_version"] == DERIVER_SEMANTIC_VERSION
    assert first["schema_version"] == SCHEMA_VERSION
    assert len(first["manifest_sha256"]) == 64
    assert set(first["dependencies"]) == {
        "move_observation_deriver",
        "material_safety",
        "opponent_threat",
    }
    assert all(
        len(item["sha256"]) == 64
        for item in first["dependencies"].values()
    )
    first["manifest_sha256"] = "mutated"
    assert current_deriver_identity()["manifest_sha256"] != "mutated"
