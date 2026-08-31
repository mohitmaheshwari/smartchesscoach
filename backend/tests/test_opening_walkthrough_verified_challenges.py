from services.opening_walkthrough_service import _verified_challenge


START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def test_walkthrough_challenge_exposes_identity_not_answer():
    game = {
        "game_id": "g1",
        "user_id": "u1",
        "user_color": "white",
        "pgn": '[Result "*"]\n\n1. d4 d5 *',
    }
    move = {
        "move_number": 1,
        "fen_before": START,
        "move": "d4",
        "best_move": "e4",
        "best_move_uci": "e2e4",
        "cp_loss": 180,
    }

    payload = _verified_challenge(game, move)

    assert payload == {"puzzle_id": "g1_m1"}
    assert not any("move" in key or "answer" in key for key in payload)


def test_walkthrough_challenge_fails_closed_on_inconsistent_evidence():
    game = {
        "game_id": "g1",
        "user_id": "u1",
        "user_color": "white",
        "pgn": '[Result "*"]\n\n1. d4 d5 *',
    }
    move = {
        "move_number": 1,
        "fen_before": START,
        "move": "d4",
        "best_move": "e5",
        "best_move_uci": "e7e5",
        "cp_loss": 180,
    }

    assert _verified_challenge(game, move) is None
