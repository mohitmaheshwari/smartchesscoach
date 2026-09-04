import json
from pathlib import Path

import chess

from services.caption_facts import (
    BOARD_TRANSFORMATION_CAUSAL_PROOF_VERSION,
    BOARD_TRANSFORMATION_CAUSAL_QUALITY_ID,
    ENDGAME_GEOMETRY_CAUSAL_PROOF_VERSION,
    ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID,
    FORCING_TEMPO_CAUSAL_PROOF_VERSION,
    FORCING_TEMPO_CAUSAL_QUALITY_ID,
    TARGET_LINE_CAUSAL_QUALITY_ID,
    TARGET_LINE_CAUSAL_PROOF_VERSION,
    TARGET_LINE_MIN_PAYOFF_CP,
    VERIFIED_LINE_CAUSAL_EVIDENCE_VERSION,
    VERIFIED_LINE_CAUSE_VERSION,
    build_board_transformation_opportunity_proof,
    build_endgame_geometry_opportunity_proof,
    build_forcing_tempo_opportunity_proof,
    build_target_line_opportunity_proof,
    build_verified_branch_evidence,
    build_verified_line_cause,
)
from services.detector_quality import (
    QualityGrade,
    QualitySurface,
    get_authorization,
    is_authorized,
)
from services.stored_line_verifier import (
    STORED_LINE_VERIFIER_VERSION,
    replay_stored_line,
)


def test_stored_trace_records_exact_move_events_and_terminal_truth():
    fen = "6k1/5ppp/8/8/8/8/5PPP/R6K w - - 0 1"
    replay = replay_stored_line(
        chess.Board(fen),
        "Kg1",
        ("Kh8", "Ra8#"),
        include_events=True,
        resolve_ambiguous_continuation=True,
    )

    assert replay.complete is True
    assert replay.checkmate is True
    assert tuple(event.actor for event in replay.events) == (
        "initiator",
        "opponent",
        "initiator",
    )
    assert replay.events[-1].move_san == "Ra8#"
    assert replay.events[-1].gave_check is True
    assert replay.events[-1].checkmate is True
    assert replay.events[-1].legal_reply_count == 0
    assert replay.events[-1].fen_before != replay.events[-1].fen_after
    assert replay.contract_dict()["schema_version"] == (
        STORED_LINE_VERIFIER_VERSION
    )
    assert replay.contract_dict()["fingerprint"] == replay.fingerprint


def test_stored_trace_records_promotion_and_branch_owned_actor():
    replay = replay_stored_line(
        chess.Board("8/2k5/5RP1/pp2p3/1P6/5BK1/r7/8 w - - 0 39"),
        "g7",
        ("Rd2", "g8=Q", "e4", "Bxe4"),
        include_events=True,
        resolve_ambiguous_continuation=True,
    )

    promotion = replay.events[2]
    assert promotion.actor == "initiator"
    assert promotion.move_san.startswith("g8=Q")
    assert promotion.promotion_piece == "queen"
    assert promotion.origin == "g7"
    assert promotion.destination == "g8"
    assert replay.events[0].moving_piece_id == promotion.moving_piece_id


def test_stored_trace_keeps_piece_identity_and_empty_pawn_control_squares():
    replay = replay_stored_line(
        chess.Board("7k/8/8/8/3P4/8/8/K7 w - - 0 1"),
        "d5",
        (),
        include_events=True,
        resolve_ambiguous_continuation=True,
    )

    event = replay.events[0]
    pawn_state = next(
        change.after
        for change in event.relation_changes
        if change.after is not None
        and change.after.piece_id == event.moving_piece_id
    )
    assert pawn_state.piece == "pawn"
    assert pawn_state.square == "d5"
    assert pawn_state.attack_squares == ("c6", "e6")
    assert event.moving_piece_id == "white:pawn:d4"


def test_stored_trace_records_exact_relation_and_opened_line_changes():
    replay = replay_stored_line(
        chess.Board("r6k/8/8/8/8/8/B7/R6K w - - 0 1"),
        "Bb3",
        (),
        include_events=True,
        resolve_ambiguous_continuation=True,
    )

    assert replay.complete is True
    event = replay.events[0]
    rook_openings = [
        change
        for change in event.line_geometry_changes
        if (
            change.kind == "opened"
            and change.piece == "rook"
            and change.slider_square == "a1"
        )
    ]
    assert len(rook_openings) == 1
    assert "a2" in rook_openings[0].changed_squares
    assert any(
        change.square == "a8"
        and change.before is not None
        and change.after is not None
        and "a1" not in change.before.enemy_attackers
        and "a1" in change.after.enemy_attackers
        for change in event.relation_changes
    )


def _material_opportunity_cause(*, include_branch_evidence: bool):
    return build_verified_line_cause(
        fen_before=(
            "r3kbnr/pp1npp1p/2p5/8/3qB3/5Q2/"
            "PP1B1PPP/R3K1NR w KQkq - 0 13"
        ),
        played_san="Bf5",
        best_move_san="Bc3",
        pv_after_played=("e6", "Ne2", "Qxb2", "Bc3"),
        pv_after_best=("Qa4", "Bxh8", "Ngf6", "Bxf6"),
        cp_loss=468,
        include_branch_evidence=include_branch_evidence,
    )


def test_branch_evidence_is_opt_in_and_default_contract_stays_v1():
    cause = _material_opportunity_cause(include_branch_evidence=False)

    assert cause is not None
    assert cause.branch_evidence is None
    assert cause.proof_version == VERIFIED_LINE_CAUSE_VERSION
    assert "branch_evidence" not in cause.contract_dict()

    replay = replay_stored_line(
        chess.Board("6k1/5ppp/8/8/8/8/5PPP/R6K w - - 0 1"),
        "Kg1",
        ("Kh8", "Ra8#"),
    )
    assert replay.events == ()


def test_opt_in_branch_evidence_contains_complete_differential_traces():
    cause = _material_opportunity_cause(include_branch_evidence=True)

    assert cause is not None
    assert cause.proof_version == VERIFIED_LINE_CAUSAL_EVIDENCE_VERSION
    evidence = cause.branch_evidence
    assert evidence is not None
    assert evidence.played_trace.complete is True
    assert evidence.best_trace.complete is True
    assert evidence.played_trace.events[0].move_san == "Bf5"
    assert evidence.best_trace.events[0].move_san == "Bc3"
    assert evidence.difference.net_material_edge_cp == 900
    assert tuple(
        item.move_san for item in evidence.difference.played_only_captures
    ) == ("Qxb2",)
    assert tuple(
        item.move_san for item in evidence.difference.best_only_captures
    ) == ("Bxh8", "Bxf6")

    payload = cause.contract_dict()
    assert payload["schema_version"] == VERIFIED_LINE_CAUSAL_EVIDENCE_VERSION
    assert payload["branch_evidence"]["played"]["complete"] is True
    assert payload["branch_evidence"]["best"]["complete"] is True
    assert (
        payload["branch_evidence"]["difference"][
            "played_trace_fingerprint"
        ]
        == evidence.played_trace.fingerprint
    )


def test_branch_evidence_fingerprint_is_deterministic():
    first = _material_opportunity_cause(include_branch_evidence=True)
    second = _material_opportunity_cause(include_branch_evidence=True)

    assert first is not None and second is not None
    assert first.fingerprint == second.fingerprint
    assert (
        first.branch_evidence.played_trace.fingerprint
        == second.branch_evidence.played_trace.fingerprint
    )
    assert (
        first.branch_evidence.best_trace.fingerprint
        == second.branch_evidence.best_trace.fingerprint
    )


def test_standalone_branch_evidence_handles_same_san_reply_without_selecting_lesson():
    evidence = build_verified_branch_evidence(
        fen_before=(
            "2RBk3/3r1pK1/1p2p3/p1p1P3/"
            "2P5/8/P1P5/8 b - - 0 44"
        ),
        played_san="Rxd8",
        best_move_san="f5+",
        pv_after_played=("Rxd8+", "Kxd8", "Kxf7", "b5"),
        pv_after_best=("Kf6", "Rxd8", "Rc6", "f4"),
    )

    assert evidence is not None
    assert evidence.played_trace.replayed_san[:2] == (
        "Rxd8",
        "Rxd8+",
    )
    assert evidence.best_trace.replayed_san[0] == "f5+"
    assert evidence.difference.net_material_edge_cp == 100


def test_incomplete_branch_still_fails_closed_when_evidence_is_requested():
    cause = build_verified_line_cause(
        fen_before=(
            "r3kbnr/pp1npp1p/2p5/8/3qB3/5Q2/"
            "PP1B1PPP/R3K1NR w KQkq - 0 13"
        ),
        played_san="Bf5",
        best_move_san="Bc3",
        pv_after_played=("not-a-move",),
        pv_after_best=("Qa4", "Bxh8"),
        cp_loss=468,
        include_branch_evidence=True,
    )

    assert cause is None


_BACKEND = Path(__file__).resolve().parents[1]
_OPPORTUNITY_PACKET = _BACKEND / (
    "data/corpus_snapshots/"
    "hidden_opportunities_chess_gold_v1_2026-09-02.json"
)
_OPPORTUNITY_ANNOTATIONS = _BACKEND / (
    "data/corpus_snapshots/"
    "hidden_opportunities_chess_gold_annotations_v1_2026-09-03.json"
)
_OPPORTUNITY_FAMILY_LOCK = _BACKEND / (
    "data/corpus_snapshots/"
    "hidden_opportunities_phase3a_proof_family_lock_v1_2026-09-03.json"
)


def _locked_opportunity_rows():
    packet = json.loads(_OPPORTUNITY_PACKET.read_text(encoding="utf-8"))
    annotations = json.loads(
        _OPPORTUNITY_ANNOTATIONS.read_text(encoding="utf-8")
    )
    family_lock = json.loads(
        _OPPORTUNITY_FAMILY_LOCK.read_text(encoding="utf-8")
    )
    return (
        {row["position_id"]: row for row in packet["positions"]},
        {
            row["position_id"]: row
            for row in annotations["annotations"]
        },
        set(family_lock["proof_family_order"][0]["position_ids"]),
    )


def _target_line_proof(row, **overrides):
    values = {
        "fen_before": row["fen"],
        "played_san": row["played_move"]["san"],
        "best_move_san": row["best_move"]["san"],
        "pv_after_played": tuple(
            row["stored_four_ply"]["after_played"]
        ),
        "pv_after_best": tuple(row["stored_four_ply"]["after_best"]),
        "cp_loss": row["cp_loss"],
    }
    values.update(overrides)
    return build_target_line_opportunity_proof(**values)


def test_target_line_family_recalls_all_provable_locked_gold_cases():
    rows, _, first_family = _locked_opportunity_rows()

    proofs = {
        position_id: _target_line_proof(rows[position_id])
        for position_id in first_family
    }

    assert len(proofs) == 9
    assert sum(proof is not None for proof in proofs.values()) == 7
    assert proofs["00906363fd88603401ce"] is None
    # The stored line wins a queen only until a different-square recovery;
    # it remains a gold learning opportunity, but not this material-payoff fact.
    assert proofs["001d12f6e8e923e5d08d"] is None
    for proof in (proof for proof in proofs.values() if proof is not None):
        assert proof.quality_id == TARGET_LINE_CAUSAL_QUALITY_ID
        assert proof.proof_version == TARGET_LINE_CAUSAL_PROOF_VERSION
        assert proof.payoff.target_value_cp >= TARGET_LINE_MIN_PAYOFF_CP
        assert proof.setup.role == "setup"
        assert proof.constraint.role == "constraint"
        assert proof.payoff.role == "payoff"
        assert proof.branch_evidence.difference.net_material_edge_cp > 0
        payload = proof.contract_dict()
        assert payload["fingerprint"] == proof.fingerprint
        assert payload["payoff"]["target_value_cp"] >= 300
        assert payload["settled_material_gain_cp"] >= 300


def test_target_line_family_has_no_false_fires_on_locked_non_opportunities():
    rows, annotations, _ = _locked_opportunity_rows()

    false_fires = [
        position_id
        for position_id, annotation in annotations.items()
        if annotation["surface_grade"] != "hidden_opportunity"
        and _target_line_proof(rows[position_id]) is not None
    ]

    assert len(annotations) == 100
    assert sum(
        annotation["surface_grade"] != "hidden_opportunity"
        for annotation in annotations.values()
    ) == 76
    assert false_fires == []


def test_target_line_family_rejects_locked_false_friends_explicitly():
    rows, _, _ = _locked_opportunity_rows()

    for position_id in (
        "00323795d9ac962c1fa4",  # both moves recapture the same knight
        "005fe5333ac566baf660",  # equal-looking liquidation
        "00657dbc2b625024c664",  # apparent fork is immediately captured
        "0093c7dfa97e300cf68c",  # pressure ends in only a pawn capture
    ):
        assert _target_line_proof(rows[position_id]) is None


def test_target_line_family_rejects_branch_reversal_and_broken_horizon():
    rows, _, first_family = _locked_opportunity_rows()

    for position_id in first_family:
        row = rows[position_id]
        assert _target_line_proof(
            row,
            played_san=row["best_move"]["san"],
            best_move_san=row["played_move"]["san"],
            pv_after_played=tuple(
                row["stored_four_ply"]["after_best"]
            ),
            pv_after_best=tuple(
                row["stored_four_ply"]["after_played"]
            ),
        ) is None

    one_row = rows[next(iter(first_family))]
    assert _target_line_proof(
        one_row,
        pv_after_best=("not-a-legal-stored-move",),
    ) is None


def test_target_line_rejects_equal_trade_recaptured_inside_stored_line():
    proof = build_target_line_opportunity_proof(
        fen_before=(
            "2r1r1k1/2q2pp1/3b1n1p/pp1pNQ2/3P4/"
            "P4N1P/1P2RPP1/4R1K1 w - - 0 22"
        ),
        played_san="Nd3",
        best_move_san="Ng4",
        pv_after_played=("Re4", "Nfe5", "Rxd4", "Rc1"),
        pv_after_best=("Rxe2", "Nxf6+", "gxf6", "Rxe2"),
        cp_loss=247,
    )

    assert proof is None


def test_target_line_rejects_final_capture_with_equal_legal_recapture():
    proof = build_target_line_opportunity_proof(
        fen_before=(
            "r2qk2r/pp1nbp2/2p2p1p/3p1b2/3P2P1/"
            "2N2N1P/PPP1QP2/2KR1B1R b kq - 0 11"
        ),
        played_san="Bg6",
        best_move_san="Be6",
        pv_after_played=("Nh4", "Qc7", "Qe3", "Qd6"),
        pv_after_best=("Nh4", "f5", "Nxf5", "Bxf5"),
        cp_loss=98,
    )

    assert proof is None


def test_target_line_rejects_exchange_below_the_full_minor_piece_claim():
    proof = build_target_line_opportunity_proof(
        fen_before=(
            "4r1k1/5bp1/ppp4p/5R2/1P1pPR2/"
            "P2P4/3K4/8 b - - 1 35"
        ),
        played_san="Re7",
        best_move_san="Bg6",
        pv_after_played=("Rf1", "Be8", "a4", "h5"),
        pv_after_best=("Ke2", "Bxf5", "Rxf5", "Re6"),
        cp_loss=464,
    )

    assert proof is None


def test_target_line_rejects_payoff_below_full_minor_piece_after_settlement():
    proof = build_target_line_opportunity_proof(
        fen_before=(
            "r3k2r/ppp2pp1/2nb4/3p2Bp/3Pn1b1/"
            "5B2/PPP2PPP/RN1QNR1K b kq - 0 12"
        ),
        played_san="Bxf3",
        best_move_san="Nxg5",
        pv_after_played=("Nxf3", "f6", "Nbd2", "O-O-O"),
        pv_after_best=("Be2", "Ne4", "Nc3", "O-O-O"),
        cp_loss=179,
    )

    # The frozen independent review settles this at +200: a real edge, but less
    # than the full-minor-piece threshold required for this claim family.
    assert proof is None


def test_target_line_rejects_delayed_final_position_recapture():
    proof = build_target_line_opportunity_proof(
        fen_before=(
            "b4rk1/3n2pn/7p/2p5/1pP1PN1q/"
            "1P1P4/1B1Q2BP/5RK1 w - - 1 25"
        ),
        played_san="Nd5",
        best_move_san="Bh3",
        pv_after_played=("Bxd5", "exd5", "Rxf1+", "Bxf1"),
        pv_after_best=("Ng5", "Bxd7", "Rf7", "Ng6"),
        cp_loss=197,
    )

    assert proof is None


def test_remove_future_attacker_keeps_branch_differential_exchange_story():
    proof = build_target_line_opportunity_proof(
        fen_before=(
            "2kr1bnr/ppp5/2n1bp1p/4P3/4pB2/"
            "1B6/PPP1NPPP/RN2K2R w - - 0 11"
        ),
        played_san="Nbc3",
        best_move_san="Bxe6+",
        pv_after_played=("Bxb3", "axb3", "fxe5", "Be3"),
        pv_after_best=("Kb8", "Nbc3", "Nge7", "Rd1"),
        cp_loss=450,
    )

    assert proof is not None
    assert proof.mechanism == "remove_future_attacker"


def test_low_value_chain_does_not_mask_later_eligible_causal_proof():
    proof = build_target_line_opportunity_proof(
        fen_before=(
            "7r/1p2kp1p/1q3p2/p2r4/2p1b3/"
            "2P1PQ2/PP3PPP/2KR1B1R w - - 0 20"
        ),
        played_san="Rxd5",
        best_move_san="Qxe4+",
        pv_after_played=("Bxf3", "gxf3", "Qc6", "Rf5"),
        pv_after_best=("Re5", "Qxc4", "Rg8", "Rd2"),
        cp_loss=999,
    )

    assert proof is not None
    assert proof.mechanism == "remove_future_attacker"
    assert proof.payoff.target_piece == "queen"
    assert proof.payoff.target_value_cp == 900


def test_target_line_rejects_equal_queen_liquidation_as_positive_payoff():
    # Review case 36b1869b3d33c98a5f2d. The g-pawn captures Black's queen,
    # but only after White gives up its own queen on f4: the sequence is equal.
    proof = build_target_line_opportunity_proof(
        fen_before="8/2Q5/2p2nkp/p1b5/Ppq5/8/1P3PPP/6K1 w - - 2 35",
        played_san="Qg3+",
        best_move_san="g3",
        pv_after_played=("Ng4", "Qxg4+", "Qxg4", "h4"),
        pv_after_best=("Qd4", "Qf4", "Qxf4", "gxf4"),
        cp_loss=8994,
    )

    assert proof is None


def test_target_line_rejects_payoff_recovered_just_beyond_stored_horizon():
    # Review case cf719f12e48abde9dfe9. Qxc5 bxc5 is an equal queen trade;
    # fxe5 then wins the knight for a real positive sequence payoff.
    proof = build_target_line_opportunity_proof(
        fen_before=(
            "4r1k1/p5pp/1p6/q2pn3/P7/2P1Q3/"
            "5PPP/R5K1 w - - 2 25"
        ),
        played_san="g3",
        best_move_san="f4",
        pv_after_played=("Qc5", "a5", "Qxe3", "fxe3"),
        pv_after_best=("Qc5", "Qxc5", "bxc5", "fxe5"),
        cp_loss=408,
    )

    assert proof is None


def test_target_line_rejects_same_target_capture_with_horizon_refutation():
    # Review case fd82eb68e8c3c17b9bdf. Qf3 Ng4+ Qxg4 appears to win the
    # knight, but after the stored line ...Bxg4 is a legal exchange that loses
    # the queen. The original blinded review missed this horizon refutation.
    proof = build_target_line_opportunity_proof(
        fen_before=(
            "3q1rk1/1p1b1pbp/p1r2np1/3Np1B1/2PpP3/"
            "1P1P2PP/P5BK/R2Q1R2 w - - 2 17"
        ),
        played_san="Nxf6+",
        best_move_san="Qf3",
        pv_after_played=("Bxf6", "Rxf6", "Rxf6", "Qd2"),
        pv_after_best=("Ng4+", "Qxg4", "f6", "Bxf6"),
        cp_loss=236,
    )

    assert proof is None


def test_target_line_rejects_all_six_proved_critical_horizon_leaks():
    cases = (
        (
            "r2q1rk1/1b4p1/4pbPp/p2p4/Np1Bn3/3Q1B2/PPP2P2/1K1R3R w - - 0 21",
            "Bxf6", "Bc5", ("Qxf6", "Bxe4", "dxe4", "Qb5"),
            ("Qe8", "Bxf8", "Nxf2", "Qe2"), 95,
        ),
        (
            "rnbqkbnr/ppp2ppp/8/3pp3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3",
            "Bc4", "exd5", ("dxc4", "d4", "exd4", "O-O"),
            ("e4", "Qe2", "Nf6", "d3"), 572,
        ),
        (
            "r1b2rk1/p1q1bppp/5n2/3Np3/8/3B1Q1P/PPPB1PP1/R4RK1 b - - 0 15",
            "Bb7", "Nxd5", ("Nxc7", "Bxf3", "Nxa8", "Bxa8"),
            ("Qxd5", "Be6", "Qa5", "Qxa5"), 332,
        ),
        (
            "rn1qk2r/p3ppbp/1pp1bnp1/3p4/2PP1B2/1QN1PN2/PP3PPP/R3KB1R w KQkq - 0 8",
            "cxd5", "Ng5", ("Nxd5", "Nxd5", "Qxd5", "Qa3"),
            ("dxc4", "Nxe6", "cxb3", "Nxd8"), 107,
        ),
        (
            "r3r1k1/3q1ppp/2pb1n2/ppP5/8/1PN2N1b/PBQ2PP1/RB3RK1 b - - 0 19",
            "Bc7", "Qg4", ("gxh3", "a4", "Qf5", "Re6"),
            ("Nh4", "Qxh4", "cxd6", "Bxg2"), 731,
        ),
        (
            "r1b2rk1/ppQ2ppp/3p4/3Bp3/4P3/4b3/PP3PqP/R3KR2 w Q - 0 13",
            "Qxd6", "fxe3", ("Bh3", "Ke2", "Bf4", "Qa3"),
            ("Bg4", "Qc4", "Qxb2", "Qd3"), 193,
        ),
    )

    for fen, played, best, played_pv, best_pv, cp_loss in cases:
        assert build_target_line_opportunity_proof(
            fen_before=fen,
            played_san=played,
            best_move_san=best,
            pv_after_played=played_pv,
            pv_after_best=best_pv,
            cp_loss=cp_loss,
        ) is None


def test_target_line_rejects_quiet_check_horizon_refutation():
    proof = build_target_line_opportunity_proof(
        fen_before="8/3R2kp/6p1/p3rp2/2Q1n3/P1P5/6PP/5K2 b - - 0 31",
        played_san="Kf6",
        best_move_san="Kh6",
        pv_after_played=("Rf7+", "Kg5", "Qd4", "h6"),
        pv_after_best=("Qd4", "Re6", "Rxh7+", "Kxh7"),
        cp_loss=175,
    )

    assert proof is None


def test_target_line_rejects_three_review_overcalls():
    equal_knight_exchange = build_target_line_opportunity_proof(
        fen_before=(
            "r1b1k2r/ppppnppp/2n2q2/2b1p3/2B1P3/"
            "2N2N2/PPPP1PPP/R1BQ1RK1 w kq - 8 6"
        ),
        played_san="Nb5",
        best_move_san="Nd5",
        pv_after_played=("Bb6", "d4", "exd4", "Bg5"),
        pv_after_best=("Nxd5", "exd5", "e4", "Qe2"),
        cp_loss=150,
    )
    queen_won_in_both_branches = build_target_line_opportunity_proof(
        fen_before=(
            "2r5/4q2k/3b2p1/Q2Rp1Pp/Pp1n4/"
            "1P5P/1BP2r2/1K1R4 b - - 0 31"
        ),
        played_san="Rfxc2",
        best_move_san="Rcxc2",
        pv_after_played=("Qb6", "R2c6", "Bxd4", "Rxb6"),
        pv_after_best=("Bc3", "bxc3", "Qxc3", "Rxc3"),
        cp_loss=366,
    )
    direct_capture_owned_by_another_family = (
        build_target_line_opportunity_proof(
            fen_before=(
                "8/1p6/p2P2p1/2P2k1p/1P2Rb2/"
                "P7/6K1/7R w - - 1 37"
            ),
            played_san="d7",
            best_move_san="Rxf4+",
            pv_after_played=("Bc7", "Rd4", "Kf6", "Kf3"),
            pv_after_best=("Ke6", "Re1+", "Kd7", "Rf7+"),
            cp_loss=9129,
        )
    )

    assert equal_knight_exchange is None
    assert queen_won_in_both_branches is None
    assert direct_capture_owned_by_another_family is None


def test_target_line_family_remains_shadow_on_every_player_surface():
    authorization = get_authorization(TARGET_LINE_CAUSAL_QUALITY_ID)

    assert authorization.grade == QualityGrade.SHADOW
    assert is_authorized(
        TARGET_LINE_CAUSAL_QUALITY_ID, QualitySurface.DIAGNOSTIC
    )
    assert all(
        not is_authorized(TARGET_LINE_CAUSAL_QUALITY_ID, surface)
        for surface in (
            QualitySurface.CAPTION,
            QualitySurface.PROMPT,
            QualitySurface.PLAN,
            QualitySurface.MASTERY,
        )
    )


def _forcing_tempo_proof(row, **overrides):
    values = {
        "fen_before": row["fen"],
        "played_san": row["played_move"]["san"],
        "best_move_san": row["best_move"]["san"],
        "pv_after_played": tuple(row["stored_four_ply"]["after_played"]),
        "pv_after_best": tuple(row["stored_four_ply"]["after_best"]),
        "cp_loss": row["cp_loss"],
    }
    values.update(overrides)
    return build_forcing_tempo_opportunity_proof(**values)


def test_forcing_tempo_family_composes_to_cover_all_eight_locked_cases():
    rows, annotations, _ = _locked_opportunity_rows()
    family_lock = json.loads(_OPPORTUNITY_FAMILY_LOCK.read_text(encoding="utf-8"))
    forcing_ids = set(family_lock["proof_family_order"][1]["position_ids"])
    # v5 suppresses 03eccd1b as a target-line material claim, so the already
    # valid forcing-tempo family becomes its canonical owner.
    expected_new_ids = forcing_ids - {"039bd832a639d9c2f8ab"}

    new_proofs = {
        position_id: _forcing_tempo_proof(rows[position_id])
        for position_id in forcing_ids
    }
    target_proofs = {
        position_id: _target_line_proof(rows[position_id])
        for position_id in forcing_ids
    }

    assert {
        position_id for position_id, proof in new_proofs.items() if proof
    } == expected_new_ids
    assert all(
        new_proofs[position_id] is not None
        or target_proofs[position_id] is not None
        for position_id in forcing_ids
    )
    assert all(
        annotations[position_id]["surface_grade"] == "hidden_opportunity"
        for position_id in forcing_ids
    )
    for proof in (proof for proof in new_proofs.values() if proof):
        assert proof.quality_id == FORCING_TEMPO_CAUSAL_QUALITY_ID
        assert proof.proof_version == FORCING_TEMPO_CAUSAL_PROOF_VERSION
        assert proof.material_payoff_cp > 0
        assert proof.branch_evidence.difference.net_material_edge_cp > 0
        assert proof.contract_dict()["fingerprint"] == proof.fingerprint


def test_forcing_tempo_family_has_no_false_fires_on_locked_non_opportunities():
    rows, annotations, _ = _locked_opportunity_rows()

    false_fires = [
        position_id
        for position_id, annotation in annotations.items()
        if annotation["surface_grade"] != "hidden_opportunity"
        and _forcing_tempo_proof(rows[position_id]) is not None
    ]

    assert false_fires == []


def test_forcing_tempo_family_rejects_reversed_and_incomplete_branches():
    rows, _, _ = _locked_opportunity_rows()
    family_lock = json.loads(_OPPORTUNITY_FAMILY_LOCK.read_text(encoding="utf-8"))
    forcing_ids = set(family_lock["proof_family_order"][1]["position_ids"])

    for position_id in forcing_ids:
        row = rows[position_id]
        proof = _forcing_tempo_proof(row)
        if proof is None:
            continue
        assert _forcing_tempo_proof(
            row,
            played_san=row["best_move"]["san"],
            best_move_san=row["played_move"]["san"],
            pv_after_played=tuple(row["stored_four_ply"]["after_best"]),
            pv_after_best=tuple(row["stored_four_ply"]["after_played"]),
        ) is None
        assert _forcing_tempo_proof(
            row, pv_after_best=("not-a-legal-stored-move",)
        ) is None


def test_forcing_tempo_rejects_escape_with_legal_horizon_recapture():
    proof = build_forcing_tempo_opportunity_proof(
        fen_before="4k3/8/8/8/6b1/8/P3R3/K7 w - - 0 1",
        played_san="a3",
        best_move_san="Re7+",
        pv_after_played=("Bxe2", "Kb1"),
        pv_after_best=("Kf8", "a3"),
        cp_loss=500,
    )

    # The stored line stops immediately before ...Kxe7. It therefore cannot
    # prove that Re7+ saved the rook, even though no capture appears in the PV.
    assert proof is None


def test_forcing_tempo_family_remains_shadow_on_player_surfaces():
    authorization = get_authorization(FORCING_TEMPO_CAUSAL_QUALITY_ID)

    assert authorization.grade == QualityGrade.SHADOW
    assert is_authorized(
        FORCING_TEMPO_CAUSAL_QUALITY_ID, QualitySurface.DIAGNOSTIC
    )


def _endgame_geometry_proof(row, **overrides):
    values = {
        "fen_before": row["fen"],
        "played_san": row["played_move"]["san"],
        "best_move_san": row["best_move"]["san"],
        "pv_after_played": tuple(row["stored_four_ply"]["after_played"]),
        "pv_after_best": tuple(row["stored_four_ply"]["after_best"]),
        "cp_loss": row["cp_loss"],
    }
    values.update(overrides)
    return build_endgame_geometry_opportunity_proof(**values)


def test_endgame_geometry_family_covers_all_four_locked_cases():
    rows, annotations, _ = _locked_opportunity_rows()
    family_lock = json.loads(_OPPORTUNITY_FAMILY_LOCK.read_text(encoding="utf-8"))
    family_ids = set(family_lock["proof_family_order"][2]["position_ids"])
    proofs = {
        position_id: _endgame_geometry_proof(rows[position_id])
        for position_id in family_ids
    }

    assert all(proofs.values())
    assert all(
        annotations[position_id]["surface_grade"] == "hidden_opportunity"
        for position_id in family_ids
    )
    assert {
        proof.mechanism for proof in proofs.values() if proof is not None
    } == {
        "king_route_reaches_pawn",
        "immediate_pawn_push_promotes",
        "king_move_preserves_rook_exchange",
        "alternate_rook_preserves_promotion_capture",
    }
    for proof in proofs.values():
        assert proof is not None
        assert proof.quality_id == ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID
        assert proof.proof_version == ENDGAME_GEOMETRY_CAUSAL_PROOF_VERSION
        assert proof.payoff_value_cp > 0
        assert proof.branch_evidence.difference.net_material_edge_cp > 0
        assert proof.contract_dict()["fingerprint"] == proof.fingerprint


def test_endgame_geometry_distinguishes_exchange_from_material_win():
    rows, _, _ = _locked_opportunity_rows()

    exchange = _endgame_geometry_proof(rows["00bb6cd1492bc5b6f355"])
    promotion = _endgame_geometry_proof(rows["0046fdd1299037467b31"])
    alternate_rook = _endgame_geometry_proof(rows["055d9f8521e114e4d995"])

    assert exchange is not None
    assert exchange.payoff_kind == "checking_rook_exchange"
    assert exchange.payoff.target_piece == "rook"
    assert exchange.payoff.fact_kind == "preserved_rook_exchanges_checking_rook"
    assert "material_payoff_cp" not in exchange.contract_dict()
    assert promotion is not None
    assert promotion.payoff_kind == "promotion"
    assert promotion.promotion_piece == "queen"
    assert alternate_rook is not None
    assert alternate_rook.payoff_kind == "promoted_piece_capture"
    assert alternate_rook.payoff.target_piece == "queen"


def test_endgame_geometry_has_no_false_fires_on_locked_non_opportunities():
    rows, annotations, _ = _locked_opportunity_rows()

    false_fires = [
        position_id
        for position_id, annotation in annotations.items()
        if annotation["surface_grade"] != "hidden_opportunity"
        and _endgame_geometry_proof(rows[position_id]) is not None
    ]

    assert false_fires == []


def test_endgame_geometry_rejects_reversed_and_incomplete_branches():
    rows, _, _ = _locked_opportunity_rows()
    family_lock = json.loads(_OPPORTUNITY_FAMILY_LOCK.read_text(encoding="utf-8"))
    family_ids = set(family_lock["proof_family_order"][2]["position_ids"])

    for position_id in family_ids:
        row = rows[position_id]
        assert _endgame_geometry_proof(
            row,
            played_san=row["best_move"]["san"],
            best_move_san=row["played_move"]["san"],
            pv_after_played=tuple(row["stored_four_ply"]["after_best"]),
            pv_after_best=tuple(row["stored_four_ply"]["after_played"]),
        ) is None
        assert _endgame_geometry_proof(
            row, pv_after_best=("not-a-legal-stored-move",)
        ) is None


def test_endgame_geometry_remains_shadow_on_player_surfaces():
    authorization = get_authorization(ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID)

    assert authorization.grade == QualityGrade.SHADOW
    assert is_authorized(
        ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID, QualitySurface.DIAGNOSTIC
    )
    assert all(
        not is_authorized(ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID, surface)
        for surface in (
            QualitySurface.CAPTION,
            QualitySurface.PROMPT,
            QualitySurface.PLAN,
            QualitySurface.MASTERY,
        )
    )
    assert all(
        not is_authorized(FORCING_TEMPO_CAUSAL_QUALITY_ID, surface)
        for surface in (
            QualitySurface.CAPTION,
            QualitySurface.PROMPT,
            QualitySurface.PLAN,
            QualitySurface.MASTERY,
        )
    )


def _board_transformation_proof(row, **overrides):
    values = {
        "fen_before": row["fen"],
        "played_san": row["played_move"]["san"],
        "best_move_san": row["best_move"]["san"],
        "pv_after_played": tuple(row["stored_four_ply"]["after_played"]),
        "pv_after_best": tuple(row["stored_four_ply"]["after_best"]),
        "cp_loss": row["cp_loss"],
    }
    values.update(overrides)
    return build_board_transformation_opportunity_proof(**values)


def test_board_transformation_family_covers_all_three_locked_cases():
    rows, annotations, _ = _locked_opportunity_rows()
    family_lock = json.loads(_OPPORTUNITY_FAMILY_LOCK.read_text(encoding="utf-8"))
    family_ids = set(family_lock["proof_family_order"][3]["position_ids"])
    proofs = {
        position_id: _board_transformation_proof(rows[position_id])
        for position_id in family_ids
    }

    assert all(proofs.values())
    assert all(
        annotations[position_id]["surface_grade"] == "hidden_opportunity"
        for position_id in family_ids
    )
    assert {
        proof.mechanism for proof in proofs.values() if proof is not None
    } == {
        "intermediate_exchange_preserves_rook",
        "forced_king_capture_then_queen_capture",
        "sacrifice_opens_rook_capture_route",
    }
    assert {
        position_id: proof.line_net_material_gain_cp
        for position_id, proof in proofs.items()
        if proof is not None
    } == {
        "009165b2ba85628b33b8": 100,
        "017a76d6a153237ced25": 400,
        # The stored line is +200, but ...Qxe5 Rxe5 Rxe5 wins 100 back.
        "0092ee3966f8cb299628": 100,
    }
    for proof in proofs.values():
        assert proof is not None
        assert proof.quality_id == BOARD_TRANSFORMATION_CAUSAL_QUALITY_ID
        assert proof.proof_version == BOARD_TRANSFORMATION_CAUSAL_PROOF_VERSION
        assert len(proof.transformation_steps) == 3
        assert proof.contract_dict()["fingerprint"] == proof.fingerprint


def test_board_transformation_contract_retains_every_intervening_move():
    rows, _, _ = _locked_opportunity_rows()
    expected = {
        "009165b2ba85628b33b8": (
            "Nxd5", ("cxd5", "Rad1", "Be6"), "Qxd4"
        ),
        "017a76d6a153237ced25": (
            "Rh8+", ("Kxh8", "Qh2+", "Qh4"), "Qxh4+"
        ),
        "0092ee3966f8cb299628": (
            "Bxf5", ("gxf5", "Rxf5+", "Rf6"), "Rfxe5"
        ),
    }

    for position_id, (setup, middle, payoff) in expected.items():
        proof = _board_transformation_proof(rows[position_id])
        assert proof is not None
        assert proof.setup.move_san == setup
        assert tuple(
            step.move_san for step in proof.transformation_steps
        ) == middle
        assert proof.payoff.move_san == payoff


def test_board_transformation_has_no_false_fires_on_locked_non_opportunities():
    rows, annotations, _ = _locked_opportunity_rows()

    false_fires = [
        position_id
        for position_id, annotation in annotations.items()
        if annotation["surface_grade"] != "hidden_opportunity"
        and _board_transformation_proof(rows[position_id]) is not None
    ]

    assert false_fires == []


def test_board_transformation_rejects_reversed_and_incomplete_branches():
    rows, _, _ = _locked_opportunity_rows()
    family_lock = json.loads(_OPPORTUNITY_FAMILY_LOCK.read_text(encoding="utf-8"))
    family_ids = set(family_lock["proof_family_order"][3]["position_ids"])

    for position_id in family_ids:
        row = rows[position_id]
        assert _board_transformation_proof(
            row,
            played_san=row["best_move"]["san"],
            best_move_san=row["played_move"]["san"],
            pv_after_played=tuple(row["stored_four_ply"]["after_best"]),
            pv_after_best=tuple(row["stored_four_ply"]["after_played"]),
        ) is None
        assert _board_transformation_proof(
            row, pv_after_best=("not-a-legal-stored-move",)
        ) is None


def test_board_transformation_remains_shadow_on_player_surfaces():
    authorization = get_authorization(BOARD_TRANSFORMATION_CAUSAL_QUALITY_ID)

    assert authorization.grade == QualityGrade.SHADOW
    assert is_authorized(
        BOARD_TRANSFORMATION_CAUSAL_QUALITY_ID,
        QualitySurface.DIAGNOSTIC,
    )
    assert all(
        not is_authorized(BOARD_TRANSFORMATION_CAUSAL_QUALITY_ID, surface)
        for surface in (
            QualitySurface.CAPTION,
            QualitySurface.PROMPT,
            QualitySurface.PLAN,
            QualitySurface.MASTERY,
        )
    )


def test_all_phase3a2_authorizations_point_to_matching_passing_snapshots():
    expected = {
        TARGET_LINE_CAUSAL_QUALITY_ID: TARGET_LINE_CAUSAL_PROOF_VERSION,
        FORCING_TEMPO_CAUSAL_QUALITY_ID: FORCING_TEMPO_CAUSAL_PROOF_VERSION,
        ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID: ENDGAME_GEOMETRY_CAUSAL_PROOF_VERSION,
        BOARD_TRANSFORMATION_CAUSAL_QUALITY_ID: (
            BOARD_TRANSFORMATION_CAUSAL_PROOF_VERSION
        ),
    }
    repository = _BACKEND.parent

    for quality_id, proof_version in expected.items():
        authorization = get_authorization(quality_id)
        snapshot_path = repository / authorization.evidence_ref
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        assert snapshot["passed"] is True
        assert snapshot["proof_version"] == proof_version
        assert snapshot["authorization_grade"] == "shadow"
        assert snapshot["protected_surface_authorizations"] == []
