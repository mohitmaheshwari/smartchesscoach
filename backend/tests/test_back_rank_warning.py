"""Warn about the back rank when the king has nowhere to go.

Mohit 2026-10-06, on a card that correctly said "Bb3 lets Rxc3 win your rook on
c3" and stopped there: "this is backrank mate but doesn't show in caption or
arrows".

board_concepts.back_rank_weakness already knew: on
6k1/p4ppp/6q1/8/1PbP4/P1r2P2/5KPP/2RQ4 b it returns pawns_blocking 3,
heavy_pieces_bearing_down ['c3'] and exploitable True once Rxc3 has happened.
It had never been wired to a caption -- the fourth fact found this session that
is computed correctly and never spoken.

151 of 2,539 user-mistake cards over 400 games are exploitable, 43 of them
created by the move itself.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.board_concepts import back_rank_weakness  # noqa: E402
from services.caption_facts import extract_facts  # noqa: E402
from services.caption_config import MAX_CAPTION_WORDS  # noqa: E402
from services.caption_templates import render_template  # noqa: E402

FEN = "6k1/p4ppp/6q1/8/1PbP4/P1r2P2/5KPP/2RQ4 b - - 1 28"
LINE = ["Rxc3", "Be6", "Qc2"]


class TestTheBoardBacksTheWarning:

    def test_the_king_really_is_boxed_by_its_own_pawns(self):
        board = chess.Board(FEN)
        king = board.king(chess.BLACK)
        assert chess.square_name(king) == "g8"
        for square in (chess.F7, chess.G7, chess.H7):
            piece = board.piece_at(square)
            assert piece is not None and piece.color == chess.BLACK
            assert piece.piece_type == chess.PAWN

    def test_it_is_not_exploitable_until_the_rook_arrives(self):
        """Which is why the fact is computed after the reply, not before."""
        board = chess.Board(FEN)
        assert not (back_rank_weakness(board, chess.BLACK) or {}).get("exploitable")
        board.push_san("Bb3")
        board.push_san("Rxc3")
        state = back_rank_weakness(board, chess.BLACK) or {}
        assert state.get("exploitable") is True
        assert state.get("heavy_pieces_bearing_down") == ["c3"]

    def test_a_quiet_move_then_really_is_mated(self):
        board = chess.Board(FEN)
        for san in ("Bb3", "Rxc3", "a6"):
            board.push_san(san)
        mates = []
        for move in board.legal_moves:
            probe = board.copy()
            probe.push(move)
            if probe.is_checkmate():
                mates.append(board.san(move))
        assert "Rc8#" in mates


class TestTheFactReachesTheCaption:

    def test_the_fact_fires_on_the_reported_card(self):
        facts = extract_facts(
            fen_before=FEN, played_san="Bb3", best_move_san="Rxc1",
            cp_loss=997, pv_after_played=LINE, pv_after_best=["Qxc1"],
            mover_is_user=True)
        assert facts["back_rank_exposed"] is True
        assert facts["back_rank_king_square"] == "g8"
        assert facts["back_rank_pawn_count"] == 3
        assert facts["back_rank_attacker_square"] == "c3"

    def test_the_sentence_says_escape_squares_not_mate(self):
        """Black holds here with Be6 or Qf6, so a mate claim would overstate."""
        text = render_template("R12_blunder", "back_rank_no_escape",
                               {"played_san": "Bb3", "back_rank_king_square": "g8"})
        assert "no escape squares" in text
        assert "loses to mate" not in text.lower()

    def test_the_combined_card_fits_the_word_cap(self):
        """It is appended last, so overflow would silently delete it."""
        base = ("Bb3 lets Rxc3 win your rook on c3. Rxc1 was better — "
                "it captures the rook on c1.")
        text = render_template("R12_blunder", "back_rank_no_escape",
                               {"played_san": "Bb3", "back_rank_king_square": "g8"})
        assert len((base + " " + text).split()) <= MAX_CAPTION_WORDS

    def test_it_stays_silent_when_the_king_has_air(self):
        open_fen = "6k1/p4pp1/6qp/8/1PbP4/P1r2P2/5KPP/2RQ4 b - - 1 28"
        facts = extract_facts(
            fen_before=open_fen, played_san="Bb3", best_move_san="Rxc1",
            cp_loss=997, pv_after_played=LINE, pv_after_best=["Qxc1"],
            mover_is_user=True)
        assert facts["back_rank_exposed"] is False
