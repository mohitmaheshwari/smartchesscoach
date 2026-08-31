from pathlib import Path

import chess

from services.canonical_curriculum_puzzle_proof import (
    ENDGAME_QUALITY_ID,
    OPENING_QUALITY_ID,
    OPENING_PLAN_QUALITY_ID,
    OPENING_POSITION_QUALITY_ID,
    TRAP_QUALITY_ID,
    TRAP_POSITION_QUALITY_ID,
    build_exact_endgame_proof,
    build_exact_line_proofs,
    build_exact_opening_trap_position_proofs,
)
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_builder import (
    build_imported_game_verdict,
    build_position_verdict,
)


def _fen_after(*moves: str) -> str:
    board = chess.Board()
    for uci in moves:
        board.push_uci(uci)
    return board.fen()


def test_exact_scholars_mate_defense_is_verified_from_full_history():
    pgn = "1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6"
    verdict = build_imported_game_verdict(
        game={"game_id": "scholar", "user_color": "black", "pgn": pgn},
        move_evaluation={
            "move_number": 3,
            "move": "Nf6",
            "best_move_uci": "d8e7",
            "cp_loss": 300,
            "fen_before": _fen_after(
                "e2e4", "e7e5", "f1c4", "b8c6", "d1h5"
            ),
        },
        broad_category="opening_knowledge",
    )

    # The exact proof exists, but Shadow authorization deliberately keeps the
    # player-facing puzzle broad until blind review promotes this family.
    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == TRAP_QUALITY_ID
    assert verdict.concept_id is None
    assert verdict.acceptable_moves_uci == ("d8e7",)


def test_low_loss_exact_trap_history_does_not_become_failure_claim():
    proofs = build_exact_line_proofs(
        source_pgn="1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6",
        source_ply=5,
        best_move_uci="d8e7",
        cp_loss=50,
    )
    assert proofs == ()


def test_opponent_side_decision_cannot_name_the_players_opening_lesson():
    pgn = "1. e4 Nf6 2. e5 Nd5 3. Nf3"
    verdict = build_imported_game_verdict(
        game={"game_id": "alekhine", "user_color": "white", "pgn": pgn},
        move_evaluation={
            "move_number": 3,
            "move": "Nf3",
            "best_move_uci": "d2d4",
            "cp_loss": 90,
            "fen_before": _fen_after("e2e4", "g8f6", "e4e5", "f6d5"),
        },
        broad_category="opening_knowledge",
    )

    assert verdict.status == AdmissionStatus.GENERIC
    assert verdict.concept_id is None


def test_curriculum_owner_side_decision_can_name_the_opening():
    verdict = build_imported_game_verdict(
        game={"game_id": "alekhine-black", "user_color": "black", "pgn": "1. e4 e6"},
        move_evaluation={
            "move_number": 1,
            "move": "e6",
            "best_move_uci": "g8f6",
            "cp_loss": 90,
            "fen_before": _fen_after("e2e4"),
        },
        broad_category="opening_knowledge",
    )

    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == OPENING_QUALITY_ID
    assert verdict.concept_id is None


def test_exact_opening_plan_decision_is_available_to_puzzle_admission():
    verdict = build_imported_game_verdict(
        game={
            "game_id": "marshall-plan",
            "user_color": "white",
            "pgn": "1. d4 d5 2. c4 Nf6 3. Nc3",
        },
        move_evaluation={
            "move_number": 3,
            "move": "Nc3",
            "best_move_uci": "c4d5",
            "cp_loss": 100,
            "fen_before": _fen_after("d2d4", "d7d5", "c2c4", "g8f6"),
        },
        broad_category="opening_knowledge",
    )

    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == OPENING_PLAN_QUALITY_ID
    assert verdict.concept_id is None
    assert verdict.acceptable_moves_uci == ("c4d5",)


def test_exact_position_recognizes_a_legal_opening_transposition():
    board = chess.Board()
    for san in ("d4", "Nf6", "Bf4", "d5"):
        board.push_san(san)

    # The authored London line reaches the same position through
    # 1.d4 d5 2.Bf4 Nf6.  The position proof must not require that exact
    # historical move order.
    verdict = build_position_verdict(
        source_kind="transposition_test",
        source_ref="london-transposition",
        move_evaluation={
            "fen_before": board.fen(),
            "move": "Nc3",
            "best_move_uci": "e2e3",
            "cp_loss": 100,
        },
        broad_category="opening_knowledge",
    )

    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == OPENING_POSITION_QUALITY_ID
    assert verdict.concept_id is None


def test_exact_trap_position_can_be_proved_without_source_history():
    board = chess.Board()
    for san in ("e4", "e5", "Bc4", "Nc6", "Qh5"):
        board.push_san(san)

    proofs = build_exact_opening_trap_position_proofs(
        board_before=board,
        best_move_uci="d8e7",
        cp_loss=300,
    )

    trap = next(proof for proof in proofs if proof.quality_id == TRAP_POSITION_QUALITY_ID)
    assert trap.detector.concept_id == "trap:italian-game/scholar-s-mate-danger"
    assert trap.verifier.verified is True
    assert trap.acceptable_moves == ("d8e7",)


def test_ambiguous_first_opening_move_is_not_given_a_name():
    verdict = build_imported_game_verdict(
        game={"game_id": "ambiguous", "user_color": "white", "pgn": "1. Nf3"},
        move_evaluation={
            "move_number": 1,
            "move": "Nf3",
            "best_move_uci": "d2d4",
            "cp_loss": 100,
            "fen_before": chess.STARTING_FEN,
        },
        broad_category="opening_knowledge",
    )

    assert verdict.status == AdmissionStatus.GENERIC
    assert verdict.concept_id is None


def test_exact_endgame_accepts_only_the_authored_lesson_move():
    fen = "7k/8/8/8/8/8/4K3/3Q4 w - - 0 1"
    proof = build_exact_endgame_proof(chess.Board(fen), "d1d2", "d1d7", 100)
    assert proof is not None
    assert proof.quality_id == ENDGAME_QUALITY_ID
    assert proof.detector.concept_id == "endgame:basic_mates/queen_mate"
    assert proof.acceptable_moves == ("d1d7",)

    verdict = build_position_verdict(
        source_kind="canonical_test",
        source_ref="queen-mate-0",
        move_evaluation={
            "fen_before": fen,
            "move": "d1d2",
            "best_move_uci": "d1d7",
            "cp_loss": 100,
        },
        broad_category="endgame_technique",
    )
    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == ENDGAME_QUALITY_ID
    assert verdict.concept_id is None
    assert verdict.acceptable_moves_uci == ("d1d7",)


def test_wrong_endgame_best_move_cannot_claim_the_lesson():
    fen = "7k/8/8/8/8/8/4K3/3Q4 w - - 0 1"
    assert build_exact_endgame_proof(
        chess.Board(fen), "d1d2", "d1g1", 100
    ) is None


def test_clean_endgame_move_does_not_create_a_failure_lesson():
    fen = "7k/8/8/8/8/8/4K3/3Q4 w - - 0 1"
    assert build_exact_endgame_proof(
        chess.Board(fen), "d1d7", "d1d7", 0
    ) is None


def test_curriculum_proof_module_has_no_runtime_engine_llm_or_network_dependency():
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "canonical_curriculum_puzzle_proof.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "StockfishEngine",
        "stockfish_service",
        "call_llm",
        "httpx",
        "requests.",
    )
    assert not any(token in source for token in forbidden)
