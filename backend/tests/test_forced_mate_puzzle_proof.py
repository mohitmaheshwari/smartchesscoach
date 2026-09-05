from pathlib import Path

import chess

from services.forced_mate_puzzle_proof import (
    FORCED_MATE_QUALITY_ID,
    build_forced_mate_proof,
)
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_builder import build_position_verdict
from services.verified_puzzle_feedback import build_verified_puzzle_feedback


MATE_BOARD = "6k1/5ppp/8/8/8/8/5PPP/R6K w - - 0 1"


def test_mate_in_one_is_independently_replayed():
    proof = build_forced_mate_proof(
        chess.Board(MATE_BOARD), "Kg1", "Ra8", (), 500
    )
    assert proof is not None
    assert proof.verifier.verified is True
    assert proof.detector.concept_id == "tactic.mate_in_one"
    fact = proof.verifier.facts[0]
    assert fact["mating_move_san"] == "Ra8#"
    assert fact["mating_piece"] == "rook"
    assert fact["mating_square"] == "a8"
    assert fact["king_square"] == "g8"
    assert fact["terminal_legal_replies"] == 0
    assert fact["claim_strength"] == "mate_in_one"


def test_same_played_and_best_move_is_not_a_missed_mate():
    proof = build_forced_mate_proof(
        chess.Board(MATE_BOARD), "Ra8", "Ra8", (), 500
    )
    assert proof is None


def test_forced_mate_pv_may_include_or_omit_best_move():
    board = chess.Board(MATE_BOARD)
    included = build_forced_mate_proof(
        board, "Ra2", "Kg1", ("Kg1", "Kh8", "Ra8#"), 300
    )
    omitted = build_forced_mate_proof(
        board, "Ra2", "Kg1", ("Kh8", "Ra8#"), 300
    )
    assert included is not None and included.verifier.verified
    assert omitted is not None and omitted.verifier.verified
    assert included.detector.concept_id == "tactic.forced_mate"
    assert included.verifier.facts[0]["claim_strength"] == (
        "verified_stored_continuation"
    )
    assert included.verifier.facts[0]["mating_move_san"] == "Ra8#"


def test_marker_free_uci_line_is_recognized_only_by_terminal_mate():
    proof = build_forced_mate_proof(
        chess.Board(MATE_BOARD),
        "a1a2",
        "h1g1",
        ("g8h8", "a1a8"),
        300,
    )
    assert proof is not None
    assert proof.verifier.verified is True
    assert proof.detector.concept_id == "tactic.forced_mate"


def test_mate_marker_with_illegal_line_fails_independent_verification():
    proof = build_forced_mate_proof(
        chess.Board(MATE_BOARD), "Ra2", "Kg1", ("Kg1", "Qa5", "Ra8#"), 300
    )
    assert proof is not None
    assert proof.verifier.verified is False


def test_shared_builder_exposes_only_caption_identity_after_promotion():
    non_back_rank_mate = "7k/8/5KQ1/8/8/8/8/8 w - - 0 1"
    verdict = build_position_verdict(
        source_kind="mate_fixture",
        source_ref="mate-1",
        move_evaluation={
            "fen_before": non_back_rank_mate,
            "move": "Qg5",
            "best_move_san": "Qg7#",
            "cp_loss": 500,
            "pv_after_best": [],
        },
        broad_category="missed_tactic",
    )
    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == FORCED_MATE_QUALITY_ID
    assert verdict.concept_id is None
    assert verdict.caption_concept_id == "tactic.mate_in_one"
    assert "caption_proof_verified" in verdict.reason_codes

    feedback = build_verified_puzzle_feedback(
        {
            "fen": non_back_rank_mate,
            "best_move_uci": "g6g7",
            "verified_admission": verdict.to_document(),
        },
        "g6g5",
        correct=False,
    )
    assert feedback["why"] == (
        "Qg7# puts your queen on g7 with checkmate. "
        "The king on h8 has no legal reply."
    )


def test_longer_line_caption_names_verified_finish_without_forced_claim():
    verdict = build_position_verdict(
        source_kind="mate_fixture",
        source_ref="mate-2",
        move_evaluation={
            "fen_before": MATE_BOARD,
            "move": "Ra2",
            "best_move_san": "Kg1",
            "cp_loss": 300,
            "pv_after_best": ["Kg1", "Kh8", "Ra8#"],
        },
        broad_category="missed_tactic",
    )
    assert verdict.caption_concept_id == "tactic.forced_mate"

    feedback = build_verified_puzzle_feedback(
        {
            "fen": MATE_BOARD,
            "best_move_uci": "h1g1",
            "verified_admission": verdict.to_document(),
        },
        "a1a2",
        correct=False,
    )
    why = feedback["why"]
    # The whole line is shown, so the player can follow and check it.
    assert "Kg1 Kh8 Ra8#" in why
    assert "king on h8 has no legal reply" in why
    # The proof replays ONE stored line and never enumerates the
    # opponent's alternatives, so the caption must not read as a forced
    # mate -- not through the word "forced", and not through wording that
    # asserts the outcome regardless of how the opponent answers.
    assert "The opponent can defend differently" in why
    for banned in (
        "forced",
        "unavoidable",
        "only move",
        "every defence",
        "no defence",
        "cannot stop",
        "has no answer",
        "must play",
        "inevitable",
    ):
        assert banned not in why.lower(), banned
    # Internal pipeline vocabulary must not reach a 600-1500 reader.
    assert "verified continuation" not in why.lower()


def test_forced_mate_proof_has_no_runtime_engine_llm_or_network_dependency():
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "forced_mate_puzzle_proof.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "StockfishEngine",
        "stockfish_service",
        "call_llm",
        "httpx",
        "requests.",
    )
    assert not any(token in source for token in forbidden)


PROMOTION_MATE_BOARD = "8/2P5/8/8/8/3R4/8/K1k5 w - - 0 1"


def test_promotion_mate_names_the_promoted_piece_not_the_pawn():
    """A promotion mate is delivered by the promoted piece.

    Reading the piece off the from-square reports "pawn", and the caption
    then tells the player a pawn gave mate on the back rank. The measure
    script carried the same defect, so gold and production agreed while
    both were wrong.
    """
    for promotion_uci, expected in (
        ("c7c8q", "queen"),
        ("c7c8r", "rook"),
        ("c7c8b", "bishop"),
        ("c7c8n", "knight"),
    ):
        board = chess.Board(PROMOTION_MATE_BOARD)
        after = board.copy(stack=False)
        after.push(chess.Move.from_uci(promotion_uci))
        if not after.is_checkmate():
            continue
        proof = build_forced_mate_proof(
            board, "Rd4", promotion_uci, (), 500
        )
        assert proof is not None, promotion_uci
        facts = proof.verifier.facts[0]
        assert facts["mating_piece"] == expected, promotion_uci
        assert facts["mating_piece"] != "pawn"
        assert facts["mating_square"] == "c8"


def test_promotion_mate_caption_does_not_claim_a_pawn_gave_mate():
    verdict = build_position_verdict(
        source_kind="mate_fixture",
        source_ref="promotion-mate",
        move_evaluation={
            "fen_before": PROMOTION_MATE_BOARD,
            "move": "Rd4",
            "best_move_san": "c8=Q#",
            "cp_loss": 500,
            "pv_after_best": ["c8=Q#"],
        },
        broad_category="missed_tactic",
    )
    feedback = build_verified_puzzle_feedback(
        {
            "fen": PROMOTION_MATE_BOARD,
            "best_move_uci": "c7c8q",
            "verified_admission": verdict.to_document(),
        },
        "d3d4",
        correct=False,
    )
    why = feedback["why"]
    assert "queen on c8" in why
    assert "pawn on c8" not in why
