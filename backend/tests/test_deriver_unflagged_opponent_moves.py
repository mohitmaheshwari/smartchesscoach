"""Some Play-with-Coach analyses list both sides' moves with no is_opponent_move
flag (257 games, April-September 2026). The deriver stored the opponent's moves
as the child's. The side to move in fen_before decides whose move it is.
"""
import chess

from services.move_observation_deriver import derive_observations_for_game, is_users_move


def both_sides(sans):
    board = chess.Board()
    out = []
    for i, san in enumerate(sans):
        mv = board.parse_san(san)
        out.append({"move_number": i // 2 + 1, "move": san, "move_uci": mv.uci(),
                    "fen_before": board.fen(), "cp_loss": 0, "evaluation": "good",
                    "eval_before": 0.2, "eval_after": 0.2, "best_move": san})
        board.push(mv)
    return out


MOVES = both_sides(["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"])


def derive(color):
    return derive_observations_for_game({"move_evaluations": MOVES}, game_id="coach_t",
                                        user_id="u", user_color=color)


def test_white_child_gets_only_white_moves():
    obs = derive("white")
    assert [o["move_san"] for o in obs] == ["e4", "Nf3", "Bc4"]


def test_black_child_gets_only_black_moves():
    obs = derive("black")
    assert [o["move_san"] for o in obs] == ["e5", "Nc6", "Bc5"]


def test_flag_still_wins_and_missing_board_keeps_the_move():
    assert not is_users_move({**MOVES[0], "is_opponent_move": True}, "white")
    assert is_users_move({"move": "e4"}, "white")
    assert is_users_move({"move": "e4", "fen_before": "not a fen"}, "black")
