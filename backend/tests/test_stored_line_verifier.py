import chess

from services.stored_line_verifier import (
    STORED_LINE_MATERIAL_SETTLEMENT_PLIES,
    replay_stored_line,
    settled_material_gain_cp,
)


MATE_FEN = "6k1/5ppp/8/8/8/8/5PPP/R6K w - - 0 1"


def test_include_or_omit_leading_move_normalizes_to_same_legal_line():
    board = chess.Board(MATE_FEN)
    included = replay_stored_line(
        board, "Kg1", ("Kg1", "Kh8", "Ra8#")
    )
    omitted = replay_stored_line(board, "Kg1", ("Kh8", "Ra8#"))
    assert included.complete and omitted.complete
    assert included.replayed_uci == omitted.replayed_uci
    assert included.checkmate and omitted.checkmate


def test_illegal_continuation_fails_closed():
    replay = replay_stored_line(
        chess.Board(MATE_FEN), "Kg1", ("Qa5", "Ra8#")
    )
    assert replay.complete is False
    assert replay.checkmate is False


def test_tokens_after_checkmate_make_line_incomplete():
    replay = replay_stored_line(
        chess.Board(MATE_FEN),
        "Kg1",
        ("Kh8", "Ra8#", "Kh7"),
    )
    assert replay.checkmate is True
    assert replay.complete is False


def test_material_payoff_is_from_initiator_perspective():
    fen = (
        "rnb1k2r/pp3ppp/2pqpn2/3p4/3PP3/2PB1N2/"
        "P1P2PPP/1RBQ1RK1 w kq - 3 9"
    )
    replay = replay_stored_line(
        chess.Board(fen), "e5", ("Qd7", "exf6")
    )
    assert replay.complete is True
    assert replay.net_material_gain_cp == 300
    assert replay.replayed_san == ("e5", "Qd7", "exf6")
    assert [item.contract_dict() for item in replay.captures] == [
        {
            "ply": 3,
            "actor": "initiator",
            "move_san": "exf6",
            "origin": "e5",
            "destination": "f6",
            "capturing_piece": "pawn",
            "captured_piece": "knight",
            "captured_square": "f6",
            "captured_value_cp": 300,
        }
    ]


def test_capture_ledger_keeps_every_recapture_in_order():
    replay = replay_stored_line(
        chess.Board("r1bqk2r/pppp1ppp/2n5/2b1p3/2B1P1n1/2NP1N2/PPP2PPP/R1BQ1RK1 b kq - 2 6"),
        "Nxf2",
        ("Rxf2", "Bxf2+", "Kxf2", "d6"),
    )
    assert replay.complete is True
    assert replay.net_material_gain_cp == 0
    assert tuple(item.move_san for item in replay.captures) == (
        "Nxf2",
        "Rxf2",
        "Bxf2+",
        "Kxf2",
    )
    assert tuple(item.actor for item in replay.captures) == (
        "initiator",
        "opponent",
        "initiator",
        "opponent",
    )


def test_same_san_opponent_reply_is_not_mistaken_for_leading_move():
    replay = replay_stored_line(
        chess.Board(
            "2RBk3/3r1pK1/1p2p3/p1p1P3/"
            "2P5/8/P1P5/8 b - - 0 44"
        ),
        "Rxd8",
        ("Rxd8+", "Kxd8", "Kxf7", "b5"),
        include_events=True,
        resolve_ambiguous_continuation=True,
    )

    assert replay.complete is True
    assert replay.replayed_san == (
        "Rxd8",
        "Rxd8+",
        "Kxd8",
        "Kxf7",
        "b5",
    )
    assert tuple(event.actor for event in replay.events) == (
        "initiator",
        "opponent",
        "initiator",
        "opponent",
        "initiator",
    )


def test_whole_branch_settlement_finds_recapture_on_different_square():
    replay = replay_stored_line(
        chess.Board(
            "r1b2rk1/p1q1bppp/5n2/3Np3/8/3B1Q1P/"
            "PPPB1PP1/R4RK1 b - - 0 15"
        ),
        "Nxd5",
        ("Qxd5", "Be6", "Qa5", "Qxa5"),
    )

    assert replay.complete is True
    assert replay.net_material_gain_cp == 900
    # Bxa5 removes the apparent queen win. The longer forcing-check settlement
    # finds the remaining liquidation too, leaving no net material payoff.
    assert settled_material_gain_cp(replay) == 0


def test_whole_branch_settlement_sees_forked_rook_beyond_stored_line():
    replay = replay_stored_line(
        chess.Board(
            "r2q1rk1/1b4p1/4pbPp/p2p4/Np1Bn3/3Q1B2/"
            "PPP2P2/1K1R3R w - - 0 21"
        ),
        "Bc5",
        ("Qe8", "Bxf8", "Nxf2", "Qe2"),
    )

    assert replay.complete is True
    assert replay.net_material_gain_cp == 400
    # The forked rook is recoverable immediately. The longer forcing-check
    # settlement resolves the remaining exchange to no net material payoff.
    assert settled_material_gain_cp(replay) == 0


def test_whole_branch_settlement_finds_quiet_check_then_rook_capture():
    replay = replay_stored_line(
        chess.Board("8/3R2kp/6p1/p3rp2/2Q1n3/P1P5/6PP/5K2 b - - 0 31"),
        "Kh6",
        ("Qd4", "Re6", "Rxh7+", "Kxh7"),
    )

    assert replay.complete is True
    assert STORED_LINE_MATERIAL_SETTLEMENT_PLIES == 4
    # Qd7+ is a non-capturing check. Every legal reply allows Qxe6, so the
    # apparent +400 stored payoff does not survive the forcing-check horizon.
    assert settled_material_gain_cp(replay) == 0


def test_whole_branch_settlement_counts_promotion_material():
    replay = replay_stored_line(
        chess.Board("7k/P7/8/8/8/8/8/7K b - - 0 1"),
        "Kg7",
        (),
    )

    assert replay.complete is True
    assert settled_material_gain_cp(replay) == -800


def test_whole_branch_settlement_counts_en_passant_capture():
    replay = replay_stored_line(
        chess.Board("7k/3p4/8/4P3/8/8/8/7K b - - 0 1"),
        "d5",
        (),
    )

    assert replay.complete is True
    assert settled_material_gain_cp(replay) == -100
