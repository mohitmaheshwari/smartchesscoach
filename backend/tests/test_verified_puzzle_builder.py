from __future__ import annotations

from types import SimpleNamespace

from services import verified_puzzle_builder as builder_module
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_admission import DetectorProof, VerifierProof
from services.verified_puzzle_builder import (
    build_imported_game_verdict,
    build_position_verdict,
    source_ply_for_move,
)


PGN = """[Event "Builder test"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 *
"""


def test_source_ply_respects_player_colour():
    assert source_ply_for_move(1, "white") == 0
    assert source_ply_for_move(1, "black") == 1
    assert source_ply_for_move(12, "white") == 22
    assert source_ply_for_move(12, "black") == 23


def test_unverified_legacy_opening_label_becomes_generic():
    verdict = build_imported_game_verdict(
        game={"game_id": "g", "user_color": "white", "pgn": PGN},
        move_evaluation={
            "move_number": 1,
            "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "move": "e4",
            "best_move": "e4",
            "cp_loss": 0,
        },
        broad_category="opening_knowledge",
    )

    assert verdict.status == AdmissionStatus.GENERIC
    assert verdict.played_move_uci == "e2e4"
    assert verdict.acceptable_moves_uci == ("e2e4",)


def test_black_imported_move_reconstructs_correct_half_move():
    verdict = build_imported_game_verdict(
        game={"game_id": "g", "user_color": "black", "pgn": PGN},
        move_evaluation={
            "move_number": 1,
            "fen_before": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            "move": "e5",
            "best_move": "e5",
            "cp_loss": 0,
        },
        broad_category="opening_knowledge",
    )

    assert verdict.status == AdmissionStatus.GENERIC
    assert verdict.played_move_uci == "e7e5"


def test_exact_fen_and_played_move_recover_wrong_legacy_move_number():
    verdict = build_imported_game_verdict(
        game={"game_id": "g", "user_color": "white", "pgn": PGN},
        move_evaluation={
            # Legacy row says move 1, but this is the position before 2.Nf3.
            "move_number": 1,
            "fen_before": (
                "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/"
                "PPPP1PPP/RNBQKBNR w KQkq - 0 2"
            ),
            "move": "Nf3",
            "best_move": "Nf3",
            "cp_loss": 0,
        },
        broad_category="opening_knowledge",
    )

    assert verdict.status == AdmissionStatus.GENERIC
    assert verdict.played_move_uci == "g1f3"


def test_source_move_mismatch_quarantines_imported_row():
    verdict = build_imported_game_verdict(
        game={"game_id": "g", "user_color": "white", "pgn": PGN},
        move_evaluation={
            "move_number": 1,
            "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "move": "d4",
            "best_move": "e4",
            "cp_loss": 30,
        },
        broad_category="opening_knowledge",
    )

    assert verdict.status == AdmissionStatus.QUARANTINE


def test_trusted_coach_position_uses_same_legal_answer_contract():
    verdict = build_position_verdict(
        source_kind="coach_session",
        source_ref="session:0",
        move_evaluation={
            "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "move": "d4",
            "best_move": "e4",
            "cp_loss": 120,
        },
        broad_category=None,
    )

    assert verdict.status == AdmissionStatus.GENERIC
    assert verdict.played_move_uci == "d2d4"
    assert verdict.acceptable_moves_uci == ("e2e4",)


def test_trusted_coach_position_quarantines_illegal_stored_answer():
    verdict = build_position_verdict(
        source_kind="coach_session",
        source_ref="session:0",
        move_evaluation={
            "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "move": "d4",
            "best_move": "e5",
            "cp_loss": 120,
        },
        broad_category=None,
    )

    assert verdict.status == AdmissionStatus.QUARANTINE


def test_exact_destination_safety_position_is_specific_and_plan_authorized():
    verdict = build_position_verdict(
        source_kind="coach_session",
        source_ref="destination-safety",
        move_evaluation={
            "fen_before": "3rk3/8/8/8/8/8/8/3QK3 w - - 0 1",
            "move": "Qd5",
            "move_uci": "d1d5",
            "best_move": "d1a4",
            "cp_loss": 500,
            "pv_after_played": ["Rxd5"],
        },
        broad_category="piece_safety",
    )

    assert verdict.status == AdmissionStatus.SPECIFIC
    assert verdict.quality_id == "gap:piece_safety:destination_safety_exact"
    assert verdict.concept_id == "piece_safety.destination_safety_exact"
    assert verdict.acceptable_moves_uci == ("d1a4",)


def test_failed_high_priority_candidate_cannot_mask_verified_lower_proof(monkeypatch):
    invalid_fork = SimpleNamespace(
        detector=DetectorProof(
            concept_id="tactic.fork",
            family="tactics",
            detector_id="fork_candidate",
            detector_version="test",
            calculation_id="candidate",
            acceptable_moves=("e2e4",),
        ),
        verifier=VerifierProof(
            concept_id="tactic.fork",
            verifier_id="fork_verifier",
            verifier_version="test",
            calculation_id="independent",
            verified=False,
        ),
        quality_id="tactic:fork_with_stored_payoff",
    )
    verified_piece = SimpleNamespace(
        detector=DetectorProof(
            concept_id="piece_safety.simple_hang",
            family="piece_safety",
            detector_id="piece_candidate",
            detector_version="test",
            calculation_id="candidate",
            acceptable_moves=("e2e4",),
        ),
        verifier=VerifierProof(
            concept_id="piece_safety.simple_hang",
            verifier_id="piece_verifier",
            verifier_version="test",
            calculation_id="independent",
            verified=True,
            acceptable_moves=("e2e4",),
        ),
        quality_id="gap:piece_safety:simple_hang",
    )
    monkeypatch.setattr(builder_module, "build_exact_line_proofs", lambda **_kwargs: ())
    monkeypatch.setattr(builder_module, "build_exact_endgame_proof", lambda *_args: None)
    monkeypatch.setattr(builder_module, "build_forced_mate_proof", lambda *_args: None)
    monkeypatch.setattr(builder_module, "build_free_piece_proof", lambda *_args: None)
    monkeypatch.setattr(builder_module, "build_fork_proof", lambda *_args: invalid_fork)
    monkeypatch.setattr(builder_module, "build_aligned_tactic_proof", lambda *_args: None)
    monkeypatch.setattr(builder_module, "build_removal_defender_proof", lambda *_args: None)
    monkeypatch.setattr(builder_module, "build_piece_safety_proof", lambda *_args: verified_piece)

    verdict = build_position_verdict(
        source_kind="precedence_test",
        source_ref="verified-lower",
        move_evaluation={
            "fen_before": (
                "rnbqkbnr/pppppppp/8/8/8/8/"
                "PPPPPPPP/RNBQKBNR w KQkq - 0 1"
            ),
            "move": "d4",
            "best_move": "e4",
            "cp_loss": 120,
        },
        broad_category=None,
    )
    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.concept_id is None
    assert verdict.broad_category == "piece_safety"
