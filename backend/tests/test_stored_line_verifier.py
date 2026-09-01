import chess

from services.stored_line_verifier import replay_stored_line


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
