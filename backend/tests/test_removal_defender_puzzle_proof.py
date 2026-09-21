from pathlib import Path

import chess

from services.removal_defender_puzzle_proof import (
    REMOVAL_QUALITY_ID,
    build_removal_defender_proof,
)
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_builder import build_position_verdict


REMOVAL_FEN = "4k3/7p/4b3/8/2r5/1B6/8/4R2K w - - 0 1"
PAYOFF_LINE = ("Rxe6+", "Kf7", "Bxc4")


def test_sole_defender_removal_exposes_and_wins_exact_target():
    proof = build_removal_defender_proof(
        chess.Board(REMOVAL_FEN),
        "Rd1",
        "Rxe6+",
        PAYOFF_LINE,
        300,
    )
    assert proof is not None and proof.verifier.verified
    assert proof.detector.concept_id == "tactic.removal_of_defender"
    assert proof.verifier.facts[0]["defender_square"] == "e6"
    assert proof.verifier.facts[0]["target_square"] == "c4"


def test_removing_guard_without_capturing_exposed_target_is_not_enough():
    proof = build_removal_defender_proof(
        chess.Board(REMOVAL_FEN),
        "Rd1",
        "Rxe6+",
        ("Rxe6+", "Kf7"),
        300,
    )
    assert proof is not None
    assert proof.verifier.verified is False


def test_exposed_target_cannot_move_away_before_the_claimed_payoff():
    board = chess.Board("6k1/7p/4b3/8/2r5/1B6/8/4R2K w - - 0 1")
    proof = build_removal_defender_proof(
        board,
        "Rd1",
        "Rxe6",
        ("Rc5", "Kg2"),
        300,
    )
    assert proof is not None
    assert proof.verifier.verified is False


def test_shared_builder_keeps_verified_removal_broad_until_promotion():
    verdict = build_position_verdict(
        source_kind="removal_fixture",
        source_ref="sole-guard",
        move_evaluation={
            "fen_before": REMOVAL_FEN,
            "move": "Rd1",
            "best_move_san": "Rxe6+",
            "cp_loss": 300,
            "pv_after_best": list(PAYOFF_LINE),
        },
        broad_category="missed_tactic",
    )
    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == REMOVAL_QUALITY_ID
    assert verdict.concept_id is None
    assert "specific_proof_unauthorized" in verdict.reason_codes


def test_removal_proof_has_no_runtime_engine_llm_or_network_dependency():
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "removal_defender_puzzle_proof.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "StockfishEngine",
        "stockfish_service",
        "call_llm",
        "httpx",
        "requests.",
    )
    assert not any(token in source for token in forbidden)


# Positions below are Lichess puzzles carrying the `capturingDefender`
# theme, replayed here the way the site stores them: the FEN above is
# already the solver's turn, the stored line is the solution.


def test_sacrificing_for_the_guard_is_still_a_removal():
    """Rxc5 loses the exchange on c5 and that is the whole point.

    The knight on c5 is the only piece guarding the bishop on b7, and
    the b6 pawn that recaptures is the piece blocking the queen's path
    to b7. Both facts only settle after the recapture, so nothing read
    before the move can see them.
    """
    proof = build_removal_defender_proof(
        chess.Board("r4rk1/1bp2pb1/1p3qpp/p1nPp3/P3P3/1Q3N2/3N1PPP/1BR2RK1 w - - 2 22"),
        "Rc2",
        "Rxc5",
        ("bxc5", "Qxb7"),
        300,
    )
    assert proof is not None and proof.verifier.verified
    facts = proof.verifier.facts[0]
    assert facts["defender_square"] == "c5"
    assert facts["target_square"] == "b7"


def test_recapture_may_remove_the_targets_second_defender():
    """d7 has two defenders: the f6 knight and the d8 queen.

    Taking the knight pulls the queen to f6 to recapture, so by the
    time Rxd7 lands the bishop has nobody left.
    """
    proof = build_removal_defender_proof(
        chess.Board("r2q1rk1/pppb1ppp/1b3n2/4B3/2Q5/2N5/PPP3PP/2KR1B1R w - - 1 13"),
        "Bd4",
        "Bxf6",
        ("Qxf6", "Rxd7"),
        300,
    )
    assert proof is not None and proof.verifier.verified
    facts = proof.verifier.facts[0]
    assert facts["defender_square"] == "f6"
    assert facts["target_square"] == "d7"
    assert facts["defenders_before"] == ("d8", "f6")
    assert facts["defenders_at_payoff"] == ()


def test_one_piece_taking_twice_is_a_grab_not_a_removal():
    """Qxb2 then Qxc3 is the same queen helping herself.

    The b2 pawn did guard the knight, so every other condition holds.
    Naming this a removal is what used to put the proof on Lichess
    `fork` positions, so the collecting piece must be a different one.
    """
    proof = build_removal_defender_proof(
        chess.Board("rqr5/5ppk/p3p2p/8/7P/2N1BB2/PP3PP1/R3K2R b KQ - 0 21"),
        "Qb4",
        "Qxb2",
        ("O-O", "Qxc3"),
        300,
    )
    assert proof is not None
    assert proof.verifier.verified is False
