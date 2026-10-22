"""Absolute game facts: read off the moves and headers, never judged.

The mate positions are real final positions from production games, checked
by eye on 2026-10-22.
"""
import chess
import pytest

from services.game_facts import game_facts, mate_pattern, time_control_category


@pytest.mark.parametrize("header, expected", [
    ("60+0", "bullet"), ("180+2", "blitz"), ("600+0", "rapid"), ("900+10", "rapid"),
    ("1800+0", "classical"), ("1/86400", "daily"), ("-", None), (None, None),
])
def test_time_control_category(header, expected):
    assert time_control_category(header) == expected


@pytest.mark.parametrize("fen, pattern", [
    # Queen on e8 along the back rank; g7 and h7 are Black's own pawns.
    ("4Q2k/6pp/1p3p2/p1p3q1/8/2N3P1/5PKP/8 b - - 0 30", "back_rank_mate"),
    # Knight on f7; every square round the h8 king is Black's own piece.
    ("r1b3rk/pp3Npp/1q6/2b1pp2/8/7P/PPP2PP1/RNB2RK1 b - - 1 18", "smothered_mate"),
    ("2r2k1r/ppqN2pp/4Q3/8/2n5/8/PPP3PP/3R1R1K b - - 1 20", "double_check_mate"),
    # Rook mate on the back rank, but h7 is empty and covered by the queen,
    # so it is not a back-rank mate.
    ("5R1k/6p1/2q4p/p7/8/B1P3P1/2Q4P/2R3K1 b - - 1 41", "rook_mate"),
])
def test_mate_patterns(fen, pattern):
    board = chess.Board(fen)
    assert board.is_checkmate()
    assert mate_pattern(board) == pattern


def test_not_mate_is_no_pattern():
    assert mate_pattern(chess.Board()) is None


def game(pgn, colour="white", termination="checkmate", **kw):
    return {"pgn": pgn, "user_color": colour, "termination": termination, **kw}


SCHOLARS = '[TimeControl "180+0"]\n\n1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0'


def test_scholars_mate_from_both_sides():
    won = game_facts(game(SCHOLARS), "win")
    assert {"ended_win_by_checkmate", "user_delivered_queen_mate",
            "user_won_miniature", "time_control_blitz"} <= set(won)
    assert won["user_delivered_queen_mate"] == [{"move_number": 4, "san": "Qxf7#", "side": "you"}]
    lost = game_facts(game(SCHOLARS, colour="black"), "loss")
    assert {"user_suffered_queen_mate", "user_lost_miniature"} <= set(lost)


def test_castling_en_passant_and_clock():
    pgn = ('[TimeControl "600+0"]\n\n'
           '1. e4 {[%clk 0:10:00]} d5 2. e5 {[%clk 0:09:00]} f5 3. exf6 {[%clk 0:00:20]} Nxf6 '
           '4. Nf3 {[%clk 0:00:08]} e6 5. Be2 {[%clk 0:00:07]} Be7 6. O-O {[%clk 0:00:06]} O-O 1/2-1/2')
    facts = game_facts(game(pgn, termination="draw_agreement"), "draw")
    assert facts["user_captured_en_passant"] == [{"move_number": 3, "san": "exf6", "side": "you"}]
    assert facts["user_castled_kingside"] == [{"move_number": 6, "san": "O-O", "side": "you"}]
    # The first move at or under max(10 s, 5% of the 600 s start = 30 s):
    # 20 seconds left after exf6.
    assert facts["user_in_time_scramble"] == [{"move_number": 3, "san": "exf6", "side": "you"}]
    assert "ended_draw_by_draw_agreement" in facts
    assert "opposite_side_castling" not in facts


def test_underpromotion():
    pgn = '[SetUp "1"]\n[FEN "8/P7/8/8/8/8/8/k6K w - - 0 1"]\n\n1. a8=N *'
    facts = game_facts(game(pgn, termination="unknown"), None)
    assert {"user_promoted_a_pawn", "user_underpromoted"} <= set(facts)


def test_a_stalemate_thrown_away():
    pgn = '[SetUp "1"]\n[FEN "7k/4Q3/6K1/8/8/8/8/8 w - - 0 1"]\n\n1. Qf7 1/2-1/2'
    facts = game_facts(game(pgn, termination="stalemate"), "draw")
    assert "user_stalemated_while_ahead" in facts
    assert "ended_draw_by_stalemate" in facts


def test_rating_gap():
    facts = game_facts(game(SCHOLARS, user_rating=900, opponent_rating=1100), "win")
    assert "user_beat_higher_rated" in facts
    facts = game_facts(game(SCHOLARS, colour="black", user_rating=1100, opponent_rating=900), "loss")
    assert "user_lost_to_lower_rated" in facts


def test_named_mistakes_need_the_quality_gate():
    from services.game_tags import derive_game_tags
    ledger = {"events": [], "outcome": "loss", "opening": {}}
    allowed = {"subtype": "missed_fork", "missed_pattern": "missed_tactic",
               "move_number": 12, "move_san": "Nf3"}
    shadow = {"subtype": "missed_generic_tactic", "missed_pattern": "missed_tactic",
              "move_number": 14, "move_san": "a3"}
    tags = derive_game_tags(ledger, observations=[allowed, shadow])
    assert "user_missed_fork" in tags["ids"]
    assert tags["moves"]["user_missed_fork"] == [{"move_number": 12, "san": "Nf3", "side": "you"}]
    assert "user_missed_generic_tactic" not in tags["ids"]
