"""A draw with the player's rook or queen against a lone king gets its own
headline and a link to the mate lesson. First case: game 181687cf, which
ended drawn after 69.Ke6 with White's king and rook against a lone king."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.game_coach_summary import compute_game_summary, unconverted_basic_win  # noqa: E402


def _row(fen_before, fen_after, move="Ke6", eval_before=9900, eval_after=9900, move_number=69):
    return {"fen_before": fen_before, "fen_after": fen_after, "move": move,
            "move_number": move_number, "eval_before": eval_before,
            "eval_after": eval_after, "cp_loss": 0, "best_move": move}


# 181687cf: 68...Kg6 69.Ke6, drawn by repetition.
GAME_181687CF_END = _row("8/8/6k1/4K3/8/8/8/5R2 w - - 13 69", "8/8/4K1k1/8/8/8/8/5R2 b - - 14 69")


def test_the_game_that_found_it():
    assert unconverted_basic_win([GAME_181687CF_END], "white") == "rook"
    summary = compute_game_summary([GAME_181687CF_END], "1/2-1/2", "white")
    assert summary["root_cause"] == "You had king and rook against a lone king, and it ended in a draw."
    assert summary["lesson"] == {"label": "Learn the rook mate", "href": "/endgames/basic_mates/rook_mate"}
    assert "could have won" not in summary["root_cause"]


def test_black_player_with_a_queen():
    row = _row("8/8/8/4k3/8/8/7q/K7 b - - 0 60", "8/8/8/4k3/8/7q/8/K7 w - - 1 61", move="Qh3")
    assert unconverted_basic_win([row], "black") == "queen"
    # Positive control the other way: Qb2 next to the white king is just taken.
    taken = _row("8/8/8/4k3/8/8/2q5/K7 b - - 0 60", "8/8/8/4k3/8/8/1q6/K7 w - - 1 61", move="Qb2")
    assert unconverted_basic_win([taken], "black") is None


def test_a_rook_the_lone_king_can_take_does_not_count():
    # Black king on f2 can take the undefended rook on g2.
    row = _row("4K3/8/8/8/8/8/5k2/6R1 w - - 0 50", "4K3/8/8/8/8/8/5kR1/8 b - - 1 50", move="Rg2")
    assert unconverted_basic_win([row], "white") is None


def test_a_defended_rook_next_to_the_king_still_counts():
    # Rook g2 is defended by the king on h3, so Kxg2 is illegal.
    row = _row("8/8/8/8/8/7K/5k2/6R1 w - - 0 50", "8/8/8/8/8/7K/5kR1/8 b - - 1 50", move="Rg2")
    assert unconverted_basic_win([row], "white") == "rook"


def test_opponent_with_a_pawn_is_not_a_lone_king():
    row = _row("8/8/6k1/4K2p/8/8/8/5R2 w - - 0 60", "8/8/4K1k1/7p/8/8/8/5R2 b - - 1 60")
    assert unconverted_basic_win([row], "white") is None


def test_no_rook_or_queen_does_not_count():
    # King and bishop against a lone king is a draw anyway.
    row = _row("8/8/6k1/4K3/8/8/8/5B2 w - - 0 60", "8/8/4K1k1/8/8/8/8/5B2 b - - 1 60")
    assert unconverted_basic_win([row], "white") is None


def test_a_plain_draw_keeps_the_old_headline():
    row = _row("8/8/6k1/4K3/8/8/8/5n2 w - - 0 60", "8/8/4K1k1/8/8/8/8/5n2 b - - 1 60",
               eval_before=0, eval_after=0)
    summary = compute_game_summary([row], "1/2-1/2", "white")
    assert "lesson" not in summary
    assert summary["root_cause"] == "Drawn."


def test_a_win_is_untouched():
    summary = compute_game_summary([GAME_181687CF_END], "1-0", "white")
    assert "lesson" not in summary
