"""Gold and adversarial tests for the shared Review/PWC cause contract."""
from __future__ import annotations

import chess

from services.caption_facts import (
    build_legal_material_loss_cause,
    build_verified_line_cause,
)
from services.caption_pipeline import (
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
    inject_socratic_user_facts,
)
from services.stored_line_verifier import replay_stored_line


BH6_FEN = "2r3k1/ppN1Qp1p/6p1/2N3B1/8/8/PPn1B1PP/R4K1R w - - 3 25"


def test_bh6_builds_the_exact_measured_cause():
    cause = build_legal_material_loss_cause(
        fen_before=BH6_FEN,
        played_san="Bh6",
        best_move_san="Rd1",
        minimum_gain_cp=150,
    )
    assert cause is not None
    assert cause.contract_dict() == {
        "schema_version": "legal_material_loss_cause.v2",
        "kind": "legal_material_loss",
        "affected": {"piece": "rook", "square": "a1"},
        "attacker": {"piece": "knight", "square": "c2"},
        "punishment_san": "Nxa1",
        "material_loss_cp": 500,
        "best_move_san": "Rd1",
        "best_move_purpose": "moves_affected_piece",
        "best_move_purpose_verified": True,
        "best_move_from": "a1",
        "best_move_to": "d1",
        "played_capture": None,
        "played_purposes": ["pressures_king_ring"],
        "proof": {
            "authority": "caption_facts.legally_hanging_pieces",
            "version": "legal_material_loss_cause.v2",
        },
        "fingerprint": cause.fingerprint,
    }
    assert len(cause.fingerprint) == 64


def test_exact_attacker_capture_is_the_only_named_remove_attacker_purpose():
    cause = build_legal_material_loss_cause(
        fen_before="6k1/8/8/8/8/8/2n4P/R1Q3K1 w - - 0 1",
        played_san="h3",
        best_move_san="Qxc2",
        minimum_gain_cp=150,
    )
    assert cause is not None
    assert cause.affected.contract_dict() == {"piece": "rook", "square": "a1"}
    assert cause.attacker.contract_dict() == {"piece": "knight", "square": "c2"}
    assert cause.best_move_purpose == "removes_attacker"


def test_exact_new_defender_can_be_named_without_guessing():
    cause = build_legal_material_loss_cause(
        fen_before="r5k1/8/8/8/8/8/2Q4P/R5K1 w - - 0 1",
        played_san="h3",
        best_move_san="Qb1",
        minimum_gain_cp=150,
    )
    assert cause is not None
    assert cause.affected.contract_dict() == {"piece": "rook", "square": "a1"}
    assert cause.attacker.contract_dict() == {"piece": "rook", "square": "a8"}
    assert cause.best_move_purpose == "adds_defender"


def test_no_legal_material_loss_abstains():
    assert build_legal_material_loss_cause(
        fen_before="6k1/8/8/8/8/8/7P/R5K1 w - - 0 1",
        played_san="h3",
        best_move_san="Kh2",
        minimum_gain_cp=150,
    ) is None


def test_invalid_or_mismatched_move_abstains():
    assert build_legal_material_loss_cause(
        fen_before=BH6_FEN,
        played_san="not-san",
        best_move_san="Rd1",
        minimum_gain_cp=150,
    ) is None


def test_shared_move_decision_carries_the_same_cause_object():
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=BH6_FEN,
            played_san="Bh6",
            mover_is_user=True,
            mover_is_white=True,
            user_color="white",
            full_move_number=25,
            move_history_san=[],
            best_move_san="Rd1",
            eval_before_cp=9999,
            eval_after_cp=1298,
            cp_loss=8701,
            pv_after_played=["Nxa1", "Nd3", "Nc2", "Qd7"],
            pv_after_best=["Ne3+", "Bxe3", "h6", "Nd7"],
        ),
        CrossMoveState(),
    )
    assert decision.cause is not None
    assert decision.cause.affected.square == "a1"
    assert decision.cause.attacker.square == "c2"
    assert decision.cause.best_move_purpose == "moves_affected_piece"


def test_missed_forced_mate_is_proved_by_the_complete_best_line():
    cause = build_verified_line_cause(
        fen_before="r5nr/pp4pp/n2N4/3N3k/7b/4BP2/PPP5/6RK w - - 2 26",
        played_san="Rg4",
        best_move_san="Nf4+",
        pv_after_played=("Rf8", "Rxg7", "Rxf3", "Kg2"),
        pv_after_best=("Kh6", "Nf5#"),
        cp_loss=10173,
    )
    assert cause is not None
    assert cause.lesson_kind == "missed_forced_mate"
    assert cause.mate_in == 2
    assert cause.best_line_san == ("Nf4+", "Kh6", "Nf5#")
    assert cause.best_net_material_gain_cp == 0


def test_allowed_mate_is_proved_by_the_complete_played_line():
    cause = build_verified_line_cause(
        fen_before="8/p1p2p1p/6p1/6Pk/2Q5/P6P/KPP2q2/3r4 b - - 4 30",
        played_san="Rd2",
        best_move_san="Qf3",
        pv_after_played=("Qg4#",),
        pv_after_best=("Qxc7", "Rf1", "Qc4", "Rf2"),
        cp_loss=10608,
    )
    assert cause is not None
    assert cause.lesson_kind == "allowed_forced_mate"
    assert cause.mate_in == 1
    assert cause.reply_san == "Qg4#"
    assert cause.reply_from == "c4"
    assert cause.reply_to == "g4"


def test_exchange_sequence_reports_the_net_pawn_loss_not_a_lost_knight():
    cause = build_verified_line_cause(
        fen_before="r2r2k1/pbq2pbp/1p1ppnp1/8/4PB2/1PN4N/1P3PPP/2RQ1RK1 w - - 4 17",
        played_san="Qc2",
        best_move_san="Nd5",
        pv_after_played=("Nxe4", "f3", "Nxc3", "bxc3"),
        pv_after_best=("Qb8", "Nc7", "Bxe4", "f3"),
        cp_loss=209,
    )
    assert cause is not None
    assert cause.lesson_kind == "exchange_sequence"
    assert cause.played_net_material_gain_cp == -100
    assert tuple(item.move_san for item in cause.played_captures) == (
        "Nxe4",
        "Nxc3",
        "bxc3",
    )


def test_equal_exchange_is_not_mislabelled_as_a_free_piece_loss():
    cause = build_verified_line_cause(
        fen_before="r1bqk2r/pppp1ppp/2n5/2b1p3/2B1P1n1/2NP1N2/PPP2PPP/R1BQ1RK1 b kq - 2 6",
        played_san="Nxf2",
        best_move_san="h6",
        pv_after_played=("Rxf2", "Bxf2+", "Kxf2", "d6"),
        pv_after_best=("h3", "Nf6", "Be3", "Bb6"),
        cp_loss=226,
    )
    assert cause is None


def test_equal_immediate_recapture_abstains_instead_of_calling_a_trade_a_hang():
    cause = build_legal_material_loss_cause(
        fen_before="r1bq1rk1/ppp2ppp/8/2bQp1N1/2B5/3P4/PPn2PPP/RNB2RK1 w - - 0 10",
        played_san="Qxd8",
        best_move_san="Qxc5",
        minimum_gain_cp=150,
    )
    assert cause is None


def test_losing_immediate_recapture_names_both_sides_of_the_exchange():
    cause = build_legal_material_loss_cause(
        fen_before="R1q1nk2/5ppp/8/3Q4/1Pr5/2P5/5PPP/1N4K1 b - - 2 23",
        played_san="Qxa8",
        best_move_san="Rxb4",
        minimum_gain_cp=150,
    )
    assert cause is not None
    assert cause.played_capture is not None
    assert cause.played_capture.contract_dict() == {
        "piece": "rook",
        "square": "a8",
    }
    assert cause.affected.contract_dict() == {
        "piece": "queen",
        "square": "a8",
    }
    assert cause.material_loss_cp == 400


def test_verified_mate_takes_precedence_over_a_secondary_loose_piece():
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before="1rbk1N2/p1p3B1/3p4/2b1p2Q/4P3/8/PPp2PPP/RN2K2R w KQ - 3 16",
            played_san="Qf7",
            mover_is_user=True,
            mover_is_white=True,
            user_color="white",
            full_move_number=16,
            move_history_san=[],
            best_move_san="Bf6#",
            eval_before_cp=9999,
            eval_after_cp=0,
            cp_loss=9999,
            pv_after_played=[],
            pv_after_best=[],
            allow_fresh_engine_verification=False,
        ),
        CrossMoveState(),
    )
    assert decision.cause is not None
    assert decision.cause.lesson_kind == "missed_forced_mate"


def test_best_move_cannot_defend_a_piece_that_exists_only_in_played_branch():
    cause = build_legal_material_loss_cause(
        fen_before="1r4nr/ppk3p1/2p2pQ1/7p/1B1p2bP/3P4/PP4P1/R2QR1K1 w - - 1 23",
        played_san="Qdxg4",
        best_move_san="Qxg7+",
        minimum_gain_cp=150,
    )
    assert cause is not None
    assert cause.affected.contract_dict() == {
        "piece": "queen",
        "square": "g4",
    }
    assert cause.played_capture.contract_dict() == {
        "piece": "bishop",
        "square": "g4",
    }
    assert cause.best_move_purpose is None


def test_favorable_played_exchange_does_not_claim_to_explain_the_error():
    fen = "r1b3nr/pp3kp1/2p2pq1/3NP2p/3p3P/3P4/PP1B2P1/R2QR1K1 w - - 0 17"
    board = chess.Board(fen)
    replay = replay_stored_line(
        board,
        "Nc7",
        ("Qg4", "Nxa8", "fxe5", "Rxe5"),
    )
    assert replay.complete is True
    assert replay.net_material_gain_cp > 0
    assert len(replay.captures) >= 3
    assert {capture.actor for capture in replay.captures} == {
        "initiator",
        "opponent",
    }
    cause = build_verified_line_cause(
        fen_before=fen,
        played_san="Nc7",
        best_move_san="Nf4",
        pv_after_played=("Qg4", "Nxa8", "fxe5", "Rxe5"),
        pv_after_best=("Qf5", "Qb3+", "Ke7", "exf6+"),
        cp_loss=246,
    )
    assert cause is None


def test_best_line_material_opportunity_uses_the_stored_legal_capture_line():
    cause = build_verified_line_cause(
        fen_before="r3kbnr/pp1npp1p/2p5/8/3qB3/5Q2/PP1B1PPP/R3K1NR w KQkq - 0 13",
        played_san="Bf5",
        best_move_san="Bc3",
        pv_after_played=("e6", "Ne2", "Qxb2", "Bc3"),
        pv_after_best=("Qa4", "Bxh8", "Ngf6", "Bxf6"),
        cp_loss=468,
    )
    assert cause is not None
    assert cause.lesson_kind == "missed_material_opportunity"
    assert cause.best_net_material_gain_cp == 800
    assert cause.first_best_capture.move_san == "Bxh8"
    assert cause.first_best_capture.captured_piece == "rook"


def test_pawn_ending_route_remains_generic_but_names_the_exact_payoff():
    cause = build_verified_line_cause(
        fen_before="8/p6p/3k2p1/2p2p2/P3p3/1PPK2P1/5P1P/8 w - - 0 31",
        played_san="Ke3",
        best_move_san="Kc4",
        pv_after_played=("Ke5", "h4", "a5", "Kd2"),
        pv_after_best=("Ke5", "b4", "Kd6", "bxc5+"),
        cp_loss=409,
    )
    assert cause is not None
    assert cause.lesson_kind == "missed_material_opportunity"
    assert cause.phase == "endgame"
    assert cause.position_kind == "pawn_ending"
    assert cause.best_net_material_gain_cp == 100
    assert cause.first_best_capture.captured_square == "c5"


def test_incomplete_or_illegal_lines_fail_closed():
    assert build_verified_line_cause(
        fen_before=BH6_FEN,
        played_san="Bh6",
        best_move_san="Rd1",
        pv_after_played=("not-a-move",),
        pv_after_best=("Ne3+",),
        cp_loss=8701,
    ) is None


def test_stored_evidence_audit_can_disable_fresh_engine_verification(
    monkeypatch,
):
    calls = []

    def forbidden_engine_start():
        calls.append("started")
        raise AssertionError("fresh engine must not start")

    monkeypatch.setattr(
        "services.threat_verifier._get_singleton_engine",
        forbidden_engine_start,
    )
    board = chess.Board()
    move = board.parse_san("e4")
    facts = {}
    inject_socratic_user_facts(
        facts,
        board_before=board,
        move=move,
        user_color="white",
        cp_loss=300,
        pv_after_played=["e5"],
        move_history_san=None,
        user_rating=1200,
        socratic_context={
            "severity": "blunder",
            "fundamental_violated": "calculate",
            "coach_intent": None,
            "phase": "opening",
        },
        allow_fresh_engine_verification=False,
    )
    assert calls == []
