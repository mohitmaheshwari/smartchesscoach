"""Check first, take second.

Mohit 2026-11-06, 3628ebef move 32: "why is this a mistake?" Rxe7 and Re6+
both take the knight on e7. After Rxe7 the king on f6 takes back last
(Qxe7 Rxe7 Kxe7). After Re6+ the king has to step away, and the rook then
takes on e7 with the king out of reach. The family reads that off the two
lines and stays silent, naming the condition, on anything else.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess

from services.reasoning.check_first import check_first_claim

RXE7 = "8/pp2n1q1/5k2/4R3/2PP2p1/1P4P1/n4P2/4R1K1 w - - 2 32"
PLAYED = ["Rxe7", "Qxe7", "Rxe7", "Kxe7", "Kf1", "a5", "Ke1", "Nc1", "b4", "Nd3+", "Ke2", "Nxb4", "d5"]
BETTER = ["Re6+", "Kg5", "Rxe7", "Qxd4", "R1e5+", "Kf6", "R7e6+", "Kf7", "Re7+", "Kg6", "R7e6+", "Kg7", "Re7+"]


def claim(fen=RXE7, played=PLAYED, better=BETTER, mover_is_user=True):
    return check_first_claim(chess.Board(fen), played, better, mover_is_user=mover_is_user)


def test_rxe7_fires_and_names_the_king():
    out = claim()
    assert out["shape"] and out["fires"], out["why_not"]
    assert out["square"] == "e7" and out["piece"] == "knight"
    assert out["king_from"] == "f6" and out["king_to"] == "g5"
    assert out["king_last"] is True and out["check_forces_king"] is True
    assert out["capture_san"] == "Rxe7" and out["capture_ply"] == 2
    assert out["net_played_cp"] == 200 and out["net_better_cp"] == 300
    assert out["text"] == (
        "Both Rxe7 and Re6+ go for the knight on e7. "
        "After Rxe7, the pieces come off on e7 and their king on f6 takes back last. "
        "Re6+ first makes their king step away to g5. "
        "Then Rxe7 takes the knight and the king cannot take back.")
    assert out["consequence"]["mechanism"] == "CHECK_FIRST"


def test_the_opponents_card_says_your_king():
    text = claim(mover_is_user=False)["text"]
    assert "your king on f6 takes back last" in text
    assert "makes your king step away to g5" in text
    assert "their king" not in text


def test_silent_when_the_played_move_is_not_a_capture():
    out = claim(played=["Kg2", "Nc6"])
    assert not out["fires"] and out["why_not"] == "played_not_capture"


def test_silent_when_the_better_move_is_not_a_check():
    out = claim(better=["Kg2", "Nc6", "Rxe7"])
    assert not out["fires"] and out["why_not"] == "better_not_check"


def test_silent_when_the_better_line_never_takes_there():
    out = claim(better=["Re6+", "Kg5", "R1e5+", "Kh6", "Re3"])
    assert out["shape"] is False and out["why_not"] == "no_same_capture"


def test_silent_when_the_king_does_not_take_back_in_the_played_line():
    # The same shape, but the played line stops before the king's capture.
    out = claim(played=["Rxe7", "Qxe7", "Rxe7", "Nc3"])
    assert out["shape"] is True
    assert not out["fires"] and out["why_not"] == "no_king_recapture"


def test_silent_when_the_king_still_guards_the_square_after_the_check():
    # Kf7 stays next to e7; the capture then comes with check and the king
    # cannot take a defended rook, but the family's claim is "stepped away",
    # which is not what this line shows.
    out = claim(better=["Re6+", "Kf7", "Rxe7+", "Kg8", "Rxg7+", "Kxg7"])
    assert out["shape"] is True
    assert not out["fires"] and out["why_not"] == "king_still_guards"


def test_silent_when_something_else_takes_back_after_the_check():
    out = claim(better=["Re6+", "Kg5", "Rxe7", "Qxe7", "Rxe7"])
    assert not out["fires"] and out["why_not"] == "still_recaptured"


# ── what the first fire-rate pass and its hand grade changed ─────────────

def test_a_pawn_given_up_to_pull_the_king_away_is_said_as_a_cost():
    # f65a7b58 m28: e6+ Kxe6 Rxg8 wins a rook for a pawn; Rxg8 Kxg8 is a trade.
    out = claim("6r1/pb3k2/1p6/2ppP3/6R1/2P5/P4PPP/5RK1 w - - 4 28",
                ["Rxg8", "Kxg8", "Rb1", "Bc6", "f3"], ["e6+", "Kxe6", "Rxg8", "d4", "cxd4"])
    assert out["fires"], out["why_not"]
    assert out["sacrificed"] == "pawn"
    assert out["text"] == (
        "Both Rxg8 and e6+ go for the rook on g8. "
        "After Rxg8, their king on f7 takes back. "
        "e6+ gives up a pawn to pull their king away to e6. "
        "Then Rxg8 takes the rook and the king cannot take back.")
    assert out["consequence"]["payoff_cp"] == 400


def test_a_rook_given_up_to_win_a_rook_is_no_gain():
    # 6701f983 m24: Rh1+ Kxh1 Rxf1+ gives a rook on h1 for the rook on f1.
    out = claim("5rk1/ppp3p1/3p4/1P2p2r/2P1P3/P1NP4/4R1P1/5RK1 b - - 0 24",
                ["Rxf1+", "Kxf1", "Rh1+", "Kf2", "c6"], ["Rh1+", "Kxh1", "Rxf1+", "Kh2", "c6"])
    assert out["shape"] is True
    assert not out["fires"] and out["why_not"] == "no_gain_after_sacrifice"


def test_a_check_that_takes_something_is_a_different_story():
    # game_a84 m6: Qxd8+ Kxd8 Nxf7+ trades queens first.
    out = claim("rnbqkb1r/ppp2ppp/8/4N3/4n3/8/PPP2PPP/RNBQKB1R w KQkq - 0 6",
                ["Nxf7", "Qxd1+", "Kxd1", "Kxf7", "Bc4+"], ["Qxd8+", "Kxd8", "Nxf7+", "Ke8", "Nxh8"])
    assert not out["fires"] and out["why_not"] == "check_is_a_capture"


def test_a_capture_that_comes_after_a_second_check_is_not_this_family():
    # 32f3573f m38: R7h6+ Kg7 Rg6+ Kf8 Rxe5 takes on the fifth move of the line.
    out = claim("4B3/7R/5k2/1p2r2R/p7/P7/1PP5/1K6 w - - 2 38",
                ["Rxe5", "Kxe5", "Rd7", "Kf4", "Rd3"], ["R7h6+", "Kg7", "Rg6+", "Kf8", "Rxe5"])
    assert out["shape"] is False and out["why_not"] == "no_same_capture"


def test_a_clean_step_away_reads_as_before():
    # 02a77b98 m48: Qxf6+ Kxf6 loses the queen for a rook; f4+ Kg4 Qxf6 wins the rook.
    out = claim("8/8/2Q2r2/5bk1/8/4P3/PP3P2/2R1K3 w - - 0 48",
                ["Qxf6+", "Kxf6", "a4", "Be4", "a5"], ["f4+", "Kg4", "Qxf6", "Be4", "Rc3"])
    assert out["fires"], out["why_not"]
    assert out["sacrificed"] is None
    assert "f4+ first makes their king step away to g4." in out["text"]
    assert out["net_played_cp"] == -400 and out["net_better_cp"] == 500


def test_a_king_that_takes_the_piece_many_moves_later_is_not_taking_back():
    # d4b52618 m42: cxd3 a1=Q+ Kh2 ... and the king reaches d3 much later.
    out = claim("4Q3/3r4/3p2p1/2pkpp2/7r/2Pq3P/p1P3P1/6K1 w - - 0 42",
                ["cxd3", "a1=Q+", "Kh2", "Rg7", "Qf8", "Rf4", "Qb8", "Kd4", "Qb6", "Kxd3"],
                ["Qa8+", "Ke6", "cxd3", "Rh8", "Qxa2+", "Ke7"])
    assert out["shape"] is True
    assert not out["fires"] and out["why_not"] == "no_king_recapture"


def test_a_checking_piece_that_is_lost_two_moves_later_is_not_a_clean_gain():
    # bc7bb6bf m51: Nd8+ Kd5 Rxb7 Rxd8 -- the pawn is won and the knight goes.
    out = claim("Rr6/1P4pp/2K1n3/4p3/5k2/5P2/7P/8 b - - 10 51",
                ["Rxb7", "Kxb7", "Nd4", "Rf8+", "Ke3"], ["Nd8+", "Kd5", "Rxb7", "Rxd8", "Rf7"])
    assert out["shape"] is True
    assert not out["fires"] and out["why_not"] == "checker_lost_later"


def test_silent_on_missing_or_unplayable_lines():
    assert claim(played=[])["why_not"] == "no_line"
    assert claim(better=["Zz9"])["why_not"] == "unplayable"
    assert claim(better=PLAYED)["why_not"] == "unplayable"


def test_the_words_layer_knows_the_relation():
    from services.why_words import _CONVEYS, _RELATION
    assert "CHECK_FIRST" in _RELATION and "CHECK_FIRST" in _CONVEYS
    facts = claim()["facts"]
    assert facts["relation"] == _RELATION["CHECK_FIRST"]
    assert facts["the_square_both_moves_take_on"] == "e7"
