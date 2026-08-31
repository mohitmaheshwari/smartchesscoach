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
