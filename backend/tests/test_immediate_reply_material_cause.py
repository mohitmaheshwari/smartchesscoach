from services.caption_facts import (
    VERIFIED_LINE_CAUSAL_EVIDENCE_VERSION,
    build_verified_line_cause,
)


def _cause(*, fen, played, best, played_pv, best_pv, cp_loss):
    return build_verified_line_cause(
        fen_before=fen,
        played_san=played,
        best_move_san=best,
        pv_after_played=played_pv,
        pv_after_best=best_pv,
        cp_loss=cp_loss,
        include_branch_evidence=True,
    )


def test_next_reply_material_loss_is_kept_only_after_settlement():
    cause = _cause(
        fen="r2qk2r/ppp1bppp/2n2n2/4p2b/2B1P3/2N2N1P/PPPP2P1/R1BQ1RK1 w kq - 0 9",
        played="Qe1",
        best="Kh1",
        played_pv=("Bxf3", "d3", "Bh5", "Nd5"),
        best_pv=("Nd4", "g4", "Bg6", "d3"),
        cp_loss=420,
    )

    assert cause is not None
    assert cause.lesson_kind == "immediate_material_loss"
    assert cause.reply_san == "Bxf3"
    assert cause.immediate_reply_capture is not None
    assert cause.immediate_reply_capture.captured_piece == "knight"
    assert cause.immediate_reply_capture.captured_square == "f3"
    assert cause.immediate_reply_net_loss_cp == 300
    assert cause.played_settled_material_gain_cp == -300
    assert cause.best_settled_material_gain_cp == 0
    assert cause.proof_version == VERIFIED_LINE_CAUSAL_EVIDENCE_VERSION


def test_recapture_after_the_stored_horizon_blocks_immediate_loss_claim():
    cause = _cause(
        fen="r3k2r/ppp2ppp/2n1pn2/1N1p1b2/3P4/2PBPN2/Pq3PPP/R2QK2R w KQkq - 0 10",
        played="Qc1",
        best="Rb1",
        played_pv=("Qxc1+", "Rxc1", "Bxd3", "Nxc7+"),
        best_pv=("Qxa2", "Nxc7+", "Kd7", "Nxa8"),
        cp_loss=745,
    )

    assert cause is None or cause.lesson_kind != "immediate_material_loss"


def test_same_material_loss_in_both_branches_blocks_attribution():
    cause = _cause(
        fen="r1b5/2nnkpb1/p1p1p1pp/4P1N1/2p5/P1N4P/1PB2PP1/3R1RK1 w - - 0 21",
        played="Nh7",
        best="Nf3",
        played_pv=("Nxe5", "f4", "Nd7", "g4"),
        best_pv=("Nxe5", "Nxe5", "Bxe5", "Rfe1"),
        cp_loss=289,
    )

    assert cause is None or cause.lesson_kind != "immediate_material_loss"
