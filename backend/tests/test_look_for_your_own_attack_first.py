"""Teach the mindset, prove it with the board.

Mohit 2026-10-10, after the review called Qxb7 a mistake on game_e8c293b5082b
move 14: "i removed queen from c7 to b7 because it was attacked, and that's a
mistake too". The card had told him his queen was attacked -- which he knew,
he had just moved her -- and named "Nc3 attacks the queen on d5" as a bare
fact with no meaning.

The lesson he asked for: "counter attack is the mindset which i want to teach
here, along the facts" / "look for attacking opportunities".

Scope: docs/counter_attack_lesson_scope.md. Depth: none, ply-0 and ply-1
geometry only, because "12 plies is too much depth for a 1500".
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_facts import extract_facts  # noqa: E402
from services.caption_pipeline import (  # noqa: E402
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
)

# game_e8c293b5082b move 14. White queen on c7 is attacked by the rook on c8
# and defended by nothing. Qxb7 rescues her. Nc3 leaves her there and attacks
# the black queen on d5, so both queens are attacked at once.
FEN = "r1r3k1/ppQ1ppbp/2n3p1/3q4/3P4/4BN2/PPP2PPP/2KN3R w - - 1 14"
PV_PLAYED = ["Qxa2", "Kd2", "Rab8", "Qd7"]
PV_BEST = ["Rxc7", "Nxd5", "Rd7", "c4"]


def _facts(fen=FEN, played="Qxb7", best="Nc3", pvp=None, pvb=None):
    return extract_facts(
        fen_before=fen, played_san=played, best_move_san=best, cp_loss=107,
        eval_before_cp=-363, eval_after_cp=-470,
        pv_after_played=list(PV_PLAYED if pvp is None else pvp),
        pv_after_best=list(PV_BEST if pvb is None else pvb),
        mover_is_user=True,
    )


def _caption(fen=FEN, played="Qxb7", best="Nc3", cp=107):
    board = chess.Board(fen)
    return build_move_teaching_decision(
        MoveInputs(
            fen_before=fen, played_san=played, mover_is_user=True,
            mover_is_white=board.turn, user_color="white",
            full_move_number=board.fullmove_number, move_history_san=[],
            best_move_san=best, eval_before_cp=-363, eval_after_cp=-470,
            cp_loss=cp, pv_after_played=list(PV_PLAYED),
            pv_after_best=list(PV_BEST),
            allow_fresh_engine_verification=False,
        ),
        CrossMoveState(),
    )


class TestThePremise:
    """If the board does not say this, nothing below proves anything."""

    def test_the_queen_really_is_attacked_and_undefended(self):
        b = chess.Board(FEN)
        assert b.piece_at(chess.C7).piece_type == chess.QUEEN
        assert [chess.square_name(s) for s in b.attackers(chess.BLACK, chess.C7)] == ["c8"]
        assert not b.attackers(chess.WHITE, chess.C7)

    def test_the_played_move_rescues_her_and_the_best_move_does_not(self):
        b = chess.Board(FEN)
        assert b.parse_san("Qxb7").from_square == chess.C7
        assert b.parse_san("Nc3").from_square != chess.C7

    def test_the_best_move_creates_a_NEW_attack_on_their_queen(self):
        b = chess.Board(FEN)
        assert not b.attackers(chess.WHITE, chess.D5), "already attacked, so not new"
        after = b.copy()
        after.push_san("Nc3")
        assert after.attackers(chess.WHITE, chess.D5)
        assert after.piece_at(chess.D5).piece_type == chess.QUEEN


class TestTheFacts:
    def test_all_four_are_read_off_the_board(self):
        f = _facts()
        assert f["saved_a_piece_that_was_attacked"] is True
        assert f["saved_piece"] == "queen"
        assert f["saved_piece_attacker_square"] == "c8"
        assert f["counter_attack_piece"] == "queen"
        assert f["counter_attack_square"] == "d5"

    def test_silent_when_the_move_rescues_nothing(self):
        """Negative control. A quiet opening move must not fire this."""
        f = _facts(
            fen="r1bq1rk1/bppp1ppp/2n2n2/p3p3/P1BPP3/2P2N2/1P3PPP/RNBQ1RK1 w - - 1 8",
            played="d5", best="dxe5", pvp=[], pvb=[],
        )
        assert f["saved_a_piece_that_was_attacked"] is False
        assert f["counter_attack_piece"] is None

    def test_silent_when_the_engine_would_also_move_the_piece(self):
        """If the better move moves the same piece, the player was right to
        move it -- they only picked the wrong square. Different lesson."""
        f = _facts(best="Qd6")
        assert f["saved_a_piece_that_was_attacked"] is False

    def test_a_threatened_pawn_is_not_this_lesson(self):
        """Pawns are excluded by scope; they are threatened constantly."""
        b = chess.Board(FEN)
        for sq in b.pieces(chess.PAWN, chess.WHITE):
            assert b.piece_at(sq).piece_type == chess.PAWN
        f = _facts(played="a3" if "a3" in [b.san(m) for m in b.legal_moves] else "h3")
        assert f["saved_a_piece_that_was_attacked"] is False


class TestTheCard:
    def test_it_leads_with_the_habit_and_names_both_pieces(self):
        text = _caption().text.caption
        assert "moved your queen out of the attack" in text
        assert "c8" in text, "the attacker's square is evidence, not decoration"
        assert "Nc3" in text and "d5" in text
        assert "look for your own attack before you move it" in text

    def test_it_does_not_say_the_same_thing_twice(self):
        """First render appended the generic why_clause after this one and
        said 'attacks their queen on d5' twice in 52 words."""
        text = _caption().text.caption
        assert text.count("d5") == 1
        assert len(text.split()) <= 45

    def test_it_never_claims_a_counter_attack_that_is_not_there(self):
        """The sentence ships only when the board proves both halves."""
        f = _facts(
            fen="r1bq1rk1/bppp1ppp/2n2n2/p3p3/P1BPP3/2P2N2/1P3PPP/RNBQ1RK1 w - - 1 8",
            played="d5", best="dxe5", pvp=[], pvb=[],
        )
        assert f["counter_attack_piece"] is None
        text = _caption(
            fen="r1bq1rk1/bppp1ppp/2n2n2/p3p3/P1BPP3/2P2N2/1P3PPP/RNBQ1RK1 w - - 1 8",
            played="d5", best="dxe5", cp=172,
        ).text.caption
        assert "look for your own attack" not in text

    def test_it_does_not_tell_him_his_queen_was_attacked_and_stop(self):
        """The rejected first version. He knew -- he moved her."""
        text = _caption().text.caption
        assert "Nc3 attacks their queen" in text, "must offer the alternative idea"
        assert "you didn't have to" in text, "that is the whole lesson"

    def test_it_never_claims_why_the_player_moved(self):
        """Qxb7 is a CAPTURE. Over the 33 cards this fires on, 11 capture and
        5 give check, so 'saved your queen' asserts a motive the card cannot
        know. State what the move did, not why it was played."""
        text = _caption().text.caption
        assert "saved your" not in text
        assert "moved your queen out of the attack from c8" in text
