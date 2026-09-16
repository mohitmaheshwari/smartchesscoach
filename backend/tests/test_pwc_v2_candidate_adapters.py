import chess
import pytest

from coach_play.v2.candidate_adapters import (
    CURRICULUM_ADAPTER_VERSION,
    CURRICULUM_PROOF_AUTHORITY,
    curriculum_candidates_from_turn,
)
from coach_play.v2.contracts import CandidateFocus, CandidateNovelty


def _fen_after_san(*moves: str) -> str:
    board = chess.Board()
    for san in moves:
        board.push_san(san)
    return board.fen()


def test_exact_trap_position_becomes_an_independently_verified_candidate():
    fen = _fen_after_san("e4", "e5", "Bc4", "Nc6", "Qh5")
    candidates = curriculum_candidates_from_turn(
        turn_id="5:g8f6",
        fen_before=fen,
        played_uci="g8f6",
        engine_evidence={
            "eval_valid": True,
            "best_move": "Qe7",
            "cp_loss": 300,
        },
        coaching_context={
            "primary_focus": {"topic_key": "opening_knowledge"},
            "supporting_focuses": [],
        },
    )

    trap = next(
        candidate
        for candidate in candidates
        if candidate.source == "canonical_curriculum_trap"
    )
    assert trap.admitted is True
    assert trap.concept_key == "trap:italian-game/scholar-s-mate-danger"
    assert trap.focus_relevance == CandidateFocus.PRIMARY
    assert trap.novelty == CandidateNovelty.UNKNOWN
    assert trap.proof_authority == CURRICULUM_PROOF_AUTHORITY
    assert trap.evidence["source_version"] == CURRICULUM_ADAPTER_VERSION
    assert trap.evidence["best_move_uci"] == "d8e7"
    assert trap.evidence["acceptable_moves"] == ["d8e7"]
    assert "Scholar's Mate Danger" in trap.claim
    assert trap.transferable_instruction
    assert trap.visual["arrows"] == [["d8", "e7", "green"]]


def test_invalid_engine_evidence_and_wrong_position_fail_closed():
    fen = _fen_after_san("e4", "e5", "Bc4", "Nc6", "Qh5")
    common = {
        "turn_id": "5:g8f6",
        "fen_before": fen,
        "played_uci": "g8f6",
    }

    assert (
        curriculum_candidates_from_turn(
            **common,
            engine_evidence={
                "eval_valid": False,
                "best_move": "Qe7",
                "cp_loss": 300,
            },
        )
        == ()
    )
    assert (
        curriculum_candidates_from_turn(
            **common,
            engine_evidence={
                "eval_valid": True,
                "best_move": "Nb4",
                "cp_loss": 300,
            },
        )
        == ()
    )


def test_exact_endgame_position_reuses_committed_objective_proof():
    fen = "7k/8/8/8/8/8/4K3/3Q4 w - - 0 1"
    candidates = curriculum_candidates_from_turn(
        turn_id="1:d1d2",
        fen_before=fen,
        played_uci="d1d2",
        engine_evidence={
            "eval_valid": True,
            "best_move": "Qd7",
            "cp_loss": 100,
        },
        coaching_context={
            "primary_focus": {"topic_key": "piece_safety"},
            "supporting_focuses": [
                {"topic_key": "endgame_technique"},
            ],
        },
    )

    assert len(candidates) == 1
    endgame = candidates[0]
    assert endgame.source == "canonical_curriculum_endgame"
    assert endgame.concept_key == "endgame:basic_mates/queen_mate"
    assert endgame.focus_relevance == CandidateFocus.SUPPORTING
    assert endgame.admitted is True
    assert endgame.evidence["verifier_calculation_id"] in {
        "committed_syzygy_wdl_preservation",
        "pinned_stockfish_evidence_match",
    }
    assert endgame.transferable_instruction.startswith("Qd7 controls")


@pytest.mark.parametrize(
    ("moves", "played_uci", "best_san", "expected_source", "concept_prefix"),
    (
        (
            ("d4", "Nf6", "Bf4", "d5"),
            "b1c3",
            "e3",
            "canonical_curriculum_opening",
            "opening:london_system",
        ),
        (
            ("d4", "d5", "c4", "Nf6"),
            "b1c3",
            "cxd5",
            "canonical_curriculum_opening_plan",
            "opening_plan:queens-gambit/",
        ),
    ),
)
def test_exact_opening_families_use_the_same_verified_adapter(
    moves,
    played_uci,
    best_san,
    expected_source,
    concept_prefix,
):
    candidates = curriculum_candidates_from_turn(
        turn_id=f"opening:{played_uci}",
        fen_before=_fen_after_san(*moves),
        played_uci=played_uci,
        engine_evidence={
            "eval_valid": True,
            "best_move": best_san,
            "cp_loss": 100,
        },
    )

    candidate = next(item for item in candidates if item.source == expected_source)
    assert candidate.admitted is True
    assert candidate.concept_key.startswith(concept_prefix)
    assert candidate.category == "opening_knowledge"
    assert candidate.transferable_instruction


def test_played_best_move_cannot_be_reframed_as_a_missed_lesson():
    fen = "7k/8/8/8/8/8/4K3/3Q4 w - - 0 1"
    assert (
        curriculum_candidates_from_turn(
            turn_id="1:d1d7",
            fen_before=fen,
            played_uci="d1d7",
            engine_evidence={
                "eval_valid": True,
                "best_move": "Qd7",
                "cp_loss": 100,
            },
        )
        == ()
    )
