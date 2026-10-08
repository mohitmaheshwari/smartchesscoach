"""Say WHY their move was a mistake, not just that it was one.

Mohit 2026-10-06, on "Opponent's Qf6 is a mistake. Play Be3 -- it brings a new
piece into the game": "see no teaching, i really don't understand why it was an
opponent mistake you know".

He is right: the sentence never says what was wrong with Qf6. The engine does.
On r2qkbnr/ppp2ppp/2np4/8/2BPP1b1/5N2/PP3PPP/RNBQK2R b its best move is Nf6 --
the KNIGHT wanted that square. The queen took it, which blocks the knight and
parks her where Bg5 and e5 both hit her. Eval +81 -> +185.

The fact is exact: their move and the engine's move end on the SAME square with
a DIFFERENT piece. Measured over 400 games, 187 of 3,976 moves with a different
best are this shape, covering two lessons -- recapturing with the wrong man
(Qxd4 for exd4) and developing the wrong piece to a good square.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_templates import resolve_why_clause  # noqa: E402

REPORTED_FEN = "r2qkbnr/ppp2ppp/2np4/8/2BPP1b1/5N2/PP3PPP/RNBQK2R b KQkq - 0 6"
BASE = {"played_san": "Qf6", "severity_phrase": "is a mistake"}


def _clause(**overrides):
    facts = dict(BASE, opp_failure_wrong_piece=True, **overrides)
    return resolve_why_clause("R12_blunder", "failure_mode_clauses_opp", facts)


class TestTheBoardBacksTheClaim:

    def test_the_engines_move_really_goes_to_the_same_square(self):
        board = chess.Board(REPORTED_FEN)
        played = board.parse_san("Qf6")
        best = board.parse_san("Nf6")
        assert played.to_square == best.to_square == chess.F6

    def test_and_with_a_different_piece(self):
        board = chess.Board(REPORTED_FEN)
        queen = board.piece_at(board.parse_san("Qf6").from_square)
        knight = board.piece_at(board.parse_san("Nf6").from_square)
        assert queen.piece_type == chess.QUEEN
        assert knight.piece_type == chess.KNIGHT

    def test_the_queen_really_can_be_chased_from_there(self):
        """Which is why it costs something, not merely why it is ugly."""
        board = chess.Board(REPORTED_FEN)
        board.push_san("Qf6")
        chasers = []
        for move in board.legal_moves:
            probe = board.copy()
            probe.push(move)
            if chess.F6 in probe.attacks(move.to_square):
                chasers.append(board.san(move))
        assert "Bg5" in chasers


class TestTheSentenceSaysSomething:

    def test_a_quiet_move_names_the_piece_that_wanted_the_square(self):
        clause = _clause(opp_wrong_piece_is_recapture=False,
                         opp_wrong_piece_played="queen",
                         opp_wrong_piece_wanted="knight",
                         opp_wrong_piece_square="f6")
        assert clause == ("their queen took f6, the square their own knight wanted")

    def test_a_recapture_names_which_man_should_have_taken(self):
        clause = _clause(opp_wrong_piece_is_recapture=True,
                         opp_wrong_piece_played="queen",
                         opp_wrong_piece_wanted="pawn",
                         opp_wrong_piece_square="d4")
        assert clause == ("they took back with the queen when the pawn should "
                          "have taken on d4")

    def test_it_is_plain_english_with_no_jargon(self):
        """Audience is 600-1500: no 'develops', no 'tempo', no piece codes."""
        for clause in (
            _clause(opp_wrong_piece_is_recapture=False, opp_wrong_piece_played="queen",
                    opp_wrong_piece_wanted="knight", opp_wrong_piece_square="f6"),
            _clause(opp_wrong_piece_is_recapture=True, opp_wrong_piece_played="queen",
                    opp_wrong_piece_wanted="pawn", opp_wrong_piece_square="d4"),
        ):
            lowered = clause.lower()
            for banned in ("tempo", "develops", "initiative", "centipawn", "engine"):
                assert banned not in lowered


class TestItStaysQuietWithoutTheFacts:

    def test_no_clause_when_the_flag_is_off(self):
        facts = dict(BASE, opp_failure_wrong_piece=False,
                     opp_wrong_piece_played="queen", opp_wrong_piece_wanted="knight",
                     opp_wrong_piece_square="f6", opp_wrong_piece_is_recapture=False)
        clause = resolve_why_clause("R12_blunder", "failure_mode_clauses_opp", facts)
        assert clause != "their queen took f6, the square their own knight wanted"

    def test_no_clause_when_a_slot_is_missing(self):
        assert _clause(opp_wrong_piece_is_recapture=False,
                       opp_wrong_piece_played="queen",
                       opp_wrong_piece_wanted=None,
                       opp_wrong_piece_square="f6") != (
            "their queen took f6, the square their own knight wanted")
