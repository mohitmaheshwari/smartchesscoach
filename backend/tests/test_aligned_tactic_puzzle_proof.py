from pathlib import Path

import chess

from services.aligned_tactic_puzzle_proof import (
    ALIGNED_QUALITY_ID,
    build_aligned_tactic_proof,
)
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_builder import build_position_verdict


PIN_FEN = "7k/3q3p/2r5/8/2B5/8/8/7K w - - 0 1"
PIN_LINE = ("Bb5", "h6", "Bxc6", "Qxc6")
SKEWER_FEN = "7k/3r3p/2q5/8/2B5/8/8/K7 w - - 0 1"
SKEWER_LINE = ("Bb5", "Qc8", "Bxd7", "Qxd7")


def test_new_pin_must_win_the_exact_front_piece_in_stored_line():
    proof = build_aligned_tactic_proof(
        chess.Board(PIN_FEN), "Bd3", "Bb5", PIN_LINE, 200
    )
    assert proof is not None and proof.verifier.verified
    assert proof.detector.concept_id == "tactic.pin"
    assert proof.verifier.facts[0] == {
        "kind": "pin",
        "creation_mode": "direct",
        "attacker_piece": "bishop",
        "attacker_square": "b5",
        "front_piece": "rook",
        "front_square": "c6",
        "rear_piece": "queen",
        "rear_square": "d7",
        "net_material_gain_cp": 200,
        "replayed_uci": ("c4b5", "h7h6", "b5c6", "d7c6"),
    }


def test_new_skewer_requires_front_move_then_rear_capture():
    proof = build_aligned_tactic_proof(
        chess.Board(SKEWER_FEN), "Bd3", "Bb5", SKEWER_LINE, 200
    )
    assert proof is not None and proof.verifier.verified
    assert proof.detector.concept_id == "tactic.skewer"
    assert proof.verifier.facts[0]["creation_mode"] == "direct"
    assert proof.verifier.facts[0]["attacker_piece"] == "bishop"
    assert proof.verifier.facts[0]["front_piece"] == "queen"
    assert proof.verifier.facts[0]["rear_square"] == "d7"
    assert proof.verifier.facts[0]["rear_piece"] == "rook"


def test_hollow_pin_geometry_without_target_payoff_stays_unverified():
    proof = build_aligned_tactic_proof(
        chess.Board(PIN_FEN), "Bd3", "Bb5", ("Bb5", "h6"), 200
    )
    assert proof is not None
    assert proof.verifier.verified is False


def test_relative_pin_target_moving_cannot_be_relabelled_as_pin_payoff():
    proof = build_aligned_tactic_proof(
        chess.Board(PIN_FEN),
        "Bd3",
        "Bb5",
        ("Bb5", "Rc8", "Bxd7"),
        200,
    )
    assert proof is not None
    assert proof.verifier.verified is False


def test_shared_builder_uses_verified_skewer_as_caption_only():
    verdict = build_position_verdict(
        source_kind="aligned_fixture",
        source_ref="skewer",
        move_evaluation={
            "fen_before": SKEWER_FEN,
            "move": "Bd3",
            "best_move_san": "Bb5",
            "cp_loss": 200,
            "pv_after_best": list(SKEWER_LINE),
        },
        broad_category="missed_tactic",
    )
    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == ALIGNED_QUALITY_ID
    assert verdict.concept_id is None
    assert verdict.caption_concept_id == "tactic.skewer"
    assert verdict.reason_codes == (
        "caption_proof_verified",
        "broad_category_verified",
    )


def test_aligned_proof_has_no_runtime_engine_llm_or_network_dependency():
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "aligned_tactic_puzzle_proof.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "StockfishEngine",
        "stockfish_service",
        "call_llm",
        "httpx",
        "requests.",
    )
    assert not any(token in source for token in forbidden)
