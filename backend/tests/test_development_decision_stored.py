"""Every derived move row carries concept:coached_development's verdict.

The position is a real production move (2026-11-10): White has played the
queen three times with the b1 knight and c1 bishop at home; the engine wants
Nc3 and the player played Qg3.
"""
from services.move_observation_deriver import _development_decision

FEN = "rnb1kb1r/ppp2ppp/8/3qp3/8/4Q3/PP1P1PPP/RNB1KBNR w KQkq - 0 7"


def row(move_uci, move, cp_loss):
    return {"fen_before": FEN, "move_uci": move_uci, "move": move, "move_number": 7,
            "best_move": "Nc3", "best_move_uci": "b1c3", "cp_loss": cp_loss}


def test_queen_move_instead_of_development_is_missed():
    assert _development_decision(row("e3g3", "Qg3", 123), "white") == "missed"


def test_playing_the_developing_move_is_applied():
    assert _development_decision(row("b1c3", "Nc3", 0), "white") == "applied"


def test_another_development_is_not_called_missed():
    # Nf3 is a development too: the lesson would be the square, not development.
    assert _development_decision(row("g1f3", "Nf3", 40), "white") != "missed"


def test_late_moves_and_missing_data_are_silent():
    assert _development_decision({**row("e3g3", "Qg3", 123), "move_number": 22}, "white") is None
    assert _development_decision({"fen_before": FEN}, "white") is None
