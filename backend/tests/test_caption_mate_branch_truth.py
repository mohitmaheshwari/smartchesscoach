from __future__ import annotations

import chess
import pytest

from services.caption_claim_verifier import verify as verify_structured_claim
from services.caption_facts import extract_facts
from services.caption_pipeline import (
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
)
from services.narrator_claim_verifier import verify_caption


MISSED_MATE_CASES = (
    {
        "fen": "r7/P3R2p/5pk1/R7/5Pp1/6P1/7P/2B3K1 w - - 7 36",
        "played": "Kg2",
        "best": "f5+",
        "eval_before": 9980,
        "eval_after": 994,
        "cp_loss": 8986,
        "pv_played": ("h6", "Kg1", "Rc8", "Re1"),
        "pv_best": ("Kh5", "Rxh7#"),
        "move_number": 36,
    },
    {
        "fen": "3r1k1r/p7/1pQ2p1p/2P4q/8/2B3bp/PP3P2/3RR1K1 w - - 0 26",
        "played": "fxg3",
        "best": "Qxf6+",
        "eval_before": 9980,
        "eval_after": 852,
        "cp_loss": 9128,
        "pv_played": ("Rd4", "Qxf6+", "Kg8", "Qxd4"),
        "pv_best": ("Qf7", "Rxd8#"),
        "move_number": 26,
    },
)


def _facts(case):
    return extract_facts(
        fen_before=case["fen"],
        played_san=case["played"],
        best_move_san=case["best"],
        eval_before_cp=case["eval_before"],
        eval_after_cp=case["eval_after"],
        cp_loss=case["cp_loss"],
        pv_after_played=list(case["pv_played"]),
        pv_after_best=list(case["pv_best"]),
        full_move_number=case["move_number"],
        mover_is_user=True,
    )


def _decision(case):
    return build_move_teaching_decision(
        MoveInputs(
            fen_before=case["fen"],
            played_san=case["played"],
            mover_is_user=True,
            mover_is_white=True,
            user_color="white",
            full_move_number=case["move_number"],
            move_history_san=[],
            best_move_san=case["best"],
            eval_before_cp=case["eval_before"],
            eval_after_cp=case["eval_after"],
            cp_loss=case["cp_loss"],
            pv_after_played=list(case["pv_played"]),
            pv_after_best=list(case["pv_best"]),
            allow_fresh_engine_verification=False,
        ),
        CrossMoveState(),
    )


@pytest.mark.parametrize("case", MISSED_MATE_CASES)
def test_audited_best_branch_mates_are_never_framed_as_allowed_mate(case):
    decision = _decision(case)

    assert decision.cause is not None
    assert decision.cause.lesson_kind == "missed_forced_mate"
    assert "misses mate in 2" in decision.text.caption
    assert "allows mate" not in decision.text.caption
    assert decision.explanation.final_verified is True


@pytest.mark.parametrize("case", MISSED_MATE_CASES)
def test_mate_fact_owns_played_and_best_branch_results(case):
    facts = _facts(case)
    evidence = facts["mate_threat_evidence"]

    assert evidence["transition"] == "missed"
    assert evidence["played_branch"]["has_forced_mate"] is False
    assert evidence["best_branch"]["has_forced_mate"] is True
    assert evidence["best_branch"]["side_delivering_mate"] == "white"
    assert evidence["best_branch"]["ply_to_mate"] == 3
    assert verify_structured_claim(facts, facts["primary_reason"])[0] is True


def test_rendered_verifier_rejects_allowed_language_for_a_missed_mate():
    case = MISSED_MATE_CASES[0]
    facts = _facts(case)
    violations = verify_caption(
        "Kg2 allows mate in 2.",
        {
            "move_san": case["played"],
            "fen_before": case["fen"],
            "best_move_san": case["best"],
            "pv_after_played": list(case["pv_played"]),
            "pv_after_best": list(case["pv_best"]),
            "mate_threat_evidence": facts["mate_threat_evidence"],
            "is_user_move": True,
        },
        strict_v2=True,
    )

    assert any(item["check"] == "mate_direction" for item in violations)


def test_allowed_mate_from_played_branch_remains_allowed():
    case = {
        "fen": "8/p1p2p1p/6p1/6Pk/2Q5/P6P/KPP2q2/3r4 b - - 4 30",
        "played": "Rd2",
        "best": "Qf3",
        "eval_before": -52,
        "eval_after": 9999,
        "cp_loss": 10608,
        "pv_played": ("Qg4#",),
        "pv_best": ("Qxc7", "Rf1", "Qc4", "Rf2"),
        "move_number": 30,
    }
    facts = extract_facts(
        fen_before=case["fen"],
        played_san=case["played"],
        best_move_san=case["best"],
        eval_before_cp=case["eval_before"],
        eval_after_cp=case["eval_after"],
        cp_loss=case["cp_loss"],
        pv_after_played=list(case["pv_played"]),
        pv_after_best=list(case["pv_best"]),
        full_move_number=case["move_number"],
        mover_is_user=True,
    )

    assert facts["mate_threat_evidence"]["transition"] == "allowed"


def test_final_truth_boundary_fails_closed_when_verifier_raises(monkeypatch):
    import services.narrator_claim_verifier as verifier

    def explode(*args, **kwargs):
        raise RuntimeError("verifier unavailable")

    monkeypatch.setattr(verifier, "verify_caption", explode)
    decision = _decision(MISSED_MATE_CASES[0])

    assert decision.text.caption == ""
    assert decision.explanation.final_verified is False
    assert "FINAL_VERIFY_SILENT" in decision.text.rule_name


def test_sacrifice_claim_can_be_proved_by_a_legal_immediate_recapture():
    violations = verify_caption(
        "Bxc5 sacrifices your bishop to open the position.",
        {
            "fen_before": "r2qkb1r/ppp2ppp/2n2n2/2Pp1b2/3P4/P1N5/1P3PPP/R1BQKBNR b KQkq - 0 7",
            "move_san": "a6",
            "best_move_san": "Bxc5",
            "pv_after_best": [],
            "is_user_move": True,
            "cp_loss": 146,
        },
        strict_v2=True,
    )

    assert not any(item["check"] == "false_sacrifice" for item in violations)


def test_sacrifice_claim_without_recapture_or_stored_line_fails_closed():
    violations = verify_caption(
        "Nf3 sacrifices your knight to open the position.",
        {
            "fen_before": chess.STARTING_FEN,
            "move_san": "a3",
            "best_move_san": "Nf3",
            "pv_after_best": [],
            "is_user_move": True,
            "cp_loss": 146,
        },
        strict_v2=True,
    )

    assert any(item["check"] == "false_sacrifice" for item in violations)
