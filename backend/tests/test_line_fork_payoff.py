"""A fork becomes a caption only when the line pays for it.

Mohit 2026-10-28, on the card for his Nxe4 fork trick: "does it also show
arrow?" The arrow was computed and stored and drawn for nobody, and so was
the lesson. describe_line_steps had already worked the fork out -- "d5. It
forks the bishop and the knight." -- and put it in line_steps.best on every
card, where it renders only behind ?show_facts=1. The caption said "dxe4
wins the knight on e4": the move that cashes the fork in, never the move
that makes it.

The narrator's fork test is a double attack, which is the right bar for
describing a line and the wrong bar for claiming a reason. Graded against
the engine's own lines over 300 of Mohit's games -- 263 forks by the side
the card is about -- only 124 (47.1%) end with the mover up 100cp, 96 of
those keep the forking piece, and 75 of those land by ply 2. So 188 of the
263 fork sentences we already compute would be a lesson the board refuses.

Each gate below has a real position that trips it, taken from the same
corpus the gate was measured on, because a gate with no negative control
is a gate nobody has tested.
"""
import os
import sys

import chess


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.caption_facts import (  # noqa: E402
    FORK_PLY_LIMIT,
    _line_fork_payoff,
    _recommended_move_why,
    forked_pair,
)


def fact(fen, best_san, pv):
    board = chess.Board(fen)
    # pv passed through as it comes, so a missing line is tested as a
    # missing line rather than as a TypeError in this helper.
    return _line_fork_payoff(board, board.parse_san(best_san), pv)


# ── the cards the fix was written for ────────────────────────────────

# Mohit's own card. Nxe4 hands the knight over, White recaptures, and d5
# hits the bishop on c4 and the knight on e4 at once; the line ends a pawn
# up for Black.
HIS_FEN = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R b KQkq - 5 4"
HIS_BEST = "Nxe4"
HIS_PV = ["Nxe4", "d5", "Bd3", "dxe4", "Bxe4", "Bd6", "d4", "exd4",
          "O-O", "O-O", "Bxc6", "bxc6"]


def test_the_fork_trick_names_the_move_that_makes_the_fork():
    assert fact(HIS_FEN, HIS_BEST, HIS_PV) == ("d5", "bishop", "knight", 2)


def test_his_caption_why_leads_with_the_fork_not_the_cash_in():
    board = chess.Board(HIS_FEN)
    why = _recommended_move_why(board, board.parse_san(HIS_BEST), True, HIS_PV)
    assert why == (
        "gives up material, then d5 hits the bishop and the knight at once, "
        "and dxe4 wins the knight on e4"
    )
    # The move that earns it comes before the move that collects it.
    assert why.index("d5") < why.index("dxe4")


# ── one negative control per gate ────────────────────────────────────

def test_a_fork_the_line_never_pays_for_is_refused():
    """Rf7 forks the knight and the knight, and the line nets nothing.

    game_74fdbd74c468 m34. The narrator prints this sentence today; it is a
    true double attack and a false reason, because the material never comes.
    """
    fen = "6k1/1p2N3/2p1pr1p/p5p1/P3P3/2P1QNPK/1q6/8 b - - 3 34"
    pv = ["e5", "Rf7", "Nc8", "Qa1", "Nh2", "Qa2", "Nd6", "Rf2",
          "Nf3", "Qe2", "Qxe2", "Rxe2"]
    assert fact(fen, "Kg7", pv) is None


def test_a_fork_whose_forking_piece_can_just_be_taken_is_refused():
    """Qc6 forks the rook and the knight and loses the queen doing it.

    game_4177951c757f m29. 28 of the 124 material-winning forks are this
    shape, and a player told to fork with a piece that gets captured has
    learned the wrong move.
    """
    fen = "Q7/p3R1pk/1p3n1p/1P6/8/3P4/5PKP/1qr5 w - - 6 29"
    pv = ["Rg1+", "Kf3", "Qd1+", "Re2", "Qxd3+", "Re3", "Qf5+", "Ke2",
          "Nd5", "Rg3", "Qh5+", "Rf3"]
    assert fact(fen, "Qc6", pv) is None


def test_a_fork_too_deep_to_teach_is_refused():
    """Nxd4 forks at ply 6, wins material, keeps the knight -- and is still
    refused.

    game_85bd0169aa4f m9. Everything about it is true; what it needs is the
    opponent playing six more engine moves. Ply 4 and 6 are 21 of the 96
    surviving forks, and FORK_PLY_LIMIT is where the distribution falls off.
    """
    fen = ("r2qk2r/ppp2ppp/2n2n2/2b1p3/1PP3b1/P1N2N2/3PBPPP/R1BQ1RK1 "
           "b kq - 0 9")
    pv = ["Ra2", "Be6", "Nb5", "a5", "Nbxd4", "Nxd4", "Nxd4", "exd4",
          "d3", "axb4", "Qc2", "O-O"]
    assert fact(fen, "Bd4", pv) is None
    assert FORK_PLY_LIMIT == 2


def test_no_line_means_no_claim():
    assert fact(HIS_FEN, HIS_BEST, []) is None
    assert fact(HIS_FEN, HIS_BEST, None) is None


def test_the_why_falls_back_when_the_fork_is_refused():
    """With no line to stand on, the sentence is the one it was before."""
    board = chess.Board(HIS_FEN)
    why = _recommended_move_why(board, board.parse_san(HIS_BEST), True, [])
    assert "hits the" not in why
    assert why == "moves into the middle, where it takes squares away from their pieces"


# ── the shared predicate ─────────────────────────────────────────────

def test_forked_pair_names_the_two_targets_and_their_squares():
    """The names feed the sentence; the squares feed the arrows.

    Both come from the same call so the picture and the words cannot
    disagree -- the whole reason the fork was described and never drawn.
    """
    board = chess.Board(
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R b KQkq - 5 4")
    for san in ["Nxe4", "Nxe4", "d5"]:
        board.push(board.parse_san(san))
    assert forked_pair(board, chess.D5) == (("bishop", "c4"), ("knight", "e4"))


def test_the_narrator_hands_the_fork_squares_to_the_board():
    """describe_line_steps carries fork_targets on the ply the fork happens,
    and on no other, so the card can draw it on the right frame."""
    from services.caption_pipeline import describe_line_steps
    steps = describe_line_steps(HIS_FEN, HIS_BEST, HIS_PV)
    assert steps[2]["san"] == "d5"
    assert steps[2]["fork_targets"] == ["c4", "e4"]
    assert steps[2]["from"] == "d7" and steps[2]["to"] == "d5"
    # the plies around it claim no fork
    assert steps[0]["fork_targets"] == []
    assert steps[1]["fork_targets"] == []
    assert steps[3]["fork_targets"] == []


def test_two_pawns_are_not_a_fork():
    """A target has to be worth a knight or more, or every advanced pawn
    reads as a fork."""
    board = chess.Board("4k3/8/8/3p1p2/4N3/8/8/4K3 w - - 0 1")
    assert forked_pair(board, chess.E4) is None


def test_the_king_is_not_one_of_the_two():
    """A knight checking the king and hitting one rook is a check, named by
    the check branch. Counting the king here would call every check a fork."""
    board = chess.Board("4k3/8/5N2/8/8/8/8/4K3 w - - 0 1")
    assert forked_pair(board, chess.F6) is None


def test_forked_pair_reads_the_side_off_the_board():
    """It serves a move by either player, so the narrator can use it for the
    opponent's plies too -- an empty square names nobody."""
    board = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    assert forked_pair(board, chess.D4) is None


def test_the_narrator_and_the_why_cannot_disagree():
    """One definition, two callers. If describe_line_steps grew its own copy
    of the test again, the two answers could drift apart."""
    from services import caption_pipeline
    assert caption_pipeline.forked_pair is forked_pair
