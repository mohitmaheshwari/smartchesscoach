"""Your own mistakes get the sequence picture, not just the first move.

Mohit 2026-10-07, on move 17 of game 043d6b9c -- "Be6 loses to Bxh7+", drawn
as a single arrow from d3 to h7: "i want arrow to show up complete posisoin
and i don't undresatnd why arrow missed this one... it just showed the first
Bxh7+, why it stopped building further arrows?"

Because `_punishment_arrows` returns after the first move of the refutation
when that move is a capture, and Bxh7+ is a capture. It was built in September
to stop the picture CONTRADICTING the sentence beside it, which it does well.
It was never built to tell a story.

`_line_sequence_arrows` was, and it already knew this exact shape -- its
sacrifice branch carries Mohit's own 2026-10-02 and 2026-10-06 notes. It was
only ever wired on OPPONENT cards.

Measured over 4,000 real user-mistake cards when it was wired on ours too:
834 (20.9%) went from one arrow or none to the full sequence, 1 changed shape,
and all 2,255 added arrows are moves in Stockfish's own stored line.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_pipeline import (  # noqa: E402
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
)

# Game 043d6b9c, move 17. Black has just played Be6. White's bishop on d3 can
# take on h7; the king recaptures, Ng5+ drives it back, and Nxe6 forks the
# queen on d8 and the rook on f8. The fork is the whole point and it is the
# FIFTH ply.
FEN = "r1bq1rk1/pp4pp/1b6/3pP3/2n2B2/3B1NQ1/PP4PP/1R3R1K b - - 0 17"
STORED_PV = ["Bxh7+", "Kxh7", "Ng5+", "Kg8"]            # what the card holds
FULL_PV = STORED_PV + ["Nxe6", "Qe7", "Nxf8", "Rxf8"]   # what 12 plies gives


def _arrows(pv, *, played="Be6", cp_loss=219, mover_is_user=True):
    d = build_move_teaching_decision(
        MoveInputs(
            fen_before=FEN, played_san=played,
            mover_is_user=mover_is_user, mover_is_white=False,
            user_color="black", full_move_number=17, move_history_san=[],
            best_move_san="Bf5", eval_before_cp=239, eval_after_cp=458,
            cp_loss=cp_loss, pv_after_played=list(pv),
            pv_after_best=["Ng5", "Be3", "Bxc4", "Bxf4"],
            allow_fresh_engine_verification=False,
        ),
        CrossMoveState(),
    )
    return [(a["from"], a["to"], a.get("color")) for a in (d.visual.arrows or [])]


class TestTheSequenceIsDrawn:
    def test_a_mistake_of_ours_no_longer_stops_at_the_first_move(self):
        assert len(_arrows(STORED_PV)) > 1

    def test_the_refutation_opens_the_picture(self):
        assert ("d3", "h7", "blue") in _arrows(STORED_PV)

    def test_their_forced_reply_is_drawn_so_it_reads_as_an_order_of_events(self):
        assert ("g8", "h7", "palegrey") in _arrows(STORED_PV)


class TestTheLineHasToBeLongEnough:
    """Mohit 2026-10-07: "first we neeed to store the 8 moves not just 4pl".
    He is right, and this is the test that holds the two apart: the walk is
    correct either way, but it cannot find a payoff that was never stored."""

    def test_a_four_ply_line_cannot_reach_the_fork(self):
        arrows = _arrows(STORED_PV)
        assert ("g5", "e6", "green") not in arrows
        # It settles for the check instead -- true, and not the point.
        assert ("f3", "g5", "green") in arrows

    def test_the_full_line_lands_the_payoff_on_the_fork(self):
        arrows = _arrows(FULL_PV)
        assert ("g5", "e6", "green") in arrows

    def test_the_full_line_draws_the_whole_story(self):
        assert _arrows(FULL_PV)[:5] == [
            ("d3", "h7", "blue"),       # the sacrifice
            ("g8", "h7", "palegrey"),   # forced recapture
            ("f3", "g5", "blue"),       # the check that drives the king back
            ("h7", "g8", "palegrey"),   # forced retreat
            ("g5", "e6", "green"),      # the fork -- what it was all for
        ]

    def test_only_one_arrow_is_ever_the_payoff(self):
        for pv in (STORED_PV, FULL_PV):
            assert sum(1 for a in _arrows(pv) if a[2] == "green") == 1, pv


class TestItStaysOffEverythingElse:
    def test_a_quiet_move_draws_no_sequence(self):
        """Same gate as _punishment_arrows: our move, and a real loss. Without
        it this would start drawing stories on moves that cost nothing."""
        assert _arrows(STORED_PV, cp_loss=20) == []

    def test_every_arrow_is_a_move_in_the_engines_own_line(self):
        """Verified by replaying the line, not by trusting the builder."""
        for pv in (STORED_PV, FULL_PV):
            board = chess.Board(FEN)
            board.push_san("Be6")
            legal = []
            for san in pv:
                mv = board.parse_san(san)
                legal.append((chess.square_name(mv.from_square),
                              chess.square_name(mv.to_square)))
                board.push(mv)
            for frm, to, _colour in _arrows(pv):
                assert (frm, to) in legal, (frm, to, pv)


class TestAPlanWhosePointIsOffScreenIsNotDrawn:
    """Mohit 2026-10-07, on move 5 of 413fcce2 -- opponent castles, the engine
    answers d4 Be7 Re1 d6 h3, and the card drew all five of those quiet moves
    with nothing at the end of them: "what is this arrow??"

    The payoff in that line is cxd4 at step 8 and the budget is 5 arrows, so
    the walk drew its first five steps and never reached the green. The note
    inside the sacrifice branch describes this failure already -- "truncated
    mid-line and ended on THEIR move with no payoff at all" -- but the guard
    it added only covered sacrifices.

    It stayed invisible while 85% of stored lines were 4 plies: a payoff at
    step 8 was never FOUND, so the builder returned nothing and the
    single-move builders drew instead. Re-analysing at 12 plies made it live.
    Measured over 3,000 stored long-line cards: 610 drew five arrows with no
    green, and 985 reached their payoff and are untouched.
    """

    # Opponent has just castled. The engine's reply is a slow positional plan
    # and the first capture of ours is cxd4, the NINTH step.
    QUIET_FEN = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2P2N2/PP1P1PPP/RNBQ1RK1 b kq - 0 5"
    QUIET_PV = ["d4", "Be7", "Re1", "d6", "h3", "a5", "Bb3",
                "exd4", "cxd4", "d5", "e5", "Ne4"]

    def _board(self):
        b = chess.Board(self.QUIET_FEN)
        b.push_san("O-O")
        return b

    def test_the_payoff_really_is_past_the_budget(self):
        """If this stops being true the test below proves nothing."""
        from services.caption_pipeline import _line_sequence_arrows
        full = _line_sequence_arrows(self._board(), self.QUIET_PV, max_arrows=99)
        assert len(full) > 5

    def test_nothing_is_drawn_when_the_payoff_cannot_be_reached(self):
        from services.caption_pipeline import _line_sequence_arrows
        assert _line_sequence_arrows(self._board(), self.QUIET_PV) == []

    def test_the_short_line_drew_nothing_either_so_this_is_not_a_loss(self):
        """Before the lines were lengthened this card drew no sequence at all,
        because a payoff at step 8 was never found. The guard restores that."""
        from services.caption_pipeline import _line_sequence_arrows
        assert _line_sequence_arrows(self._board(), self.QUIET_PV[:4]) == []

    def test_a_line_whose_payoff_fits_is_still_drawn(self):
        """The guard must not silence the cards this builder exists for."""
        arrows = _arrows(FULL_PV)
        assert len(arrows) == 5
        assert arrows[-1] == ("g5", "e6", "green")

    def test_every_drawn_sequence_ends_on_the_payoff(self):
        """The invariant the guard buys: if a sequence is drawn at all, its
        last arrow is the green one. No more five-arrow plans with no point."""
        from services.caption_pipeline import _line_sequence_arrows
        for fen, played, pv in (
            (FEN, "Be6", FULL_PV),
            (self.QUIET_FEN, "O-O", self.QUIET_PV),
        ):
            b = chess.Board(fen)
            b.push_san(played)
            arrows = _line_sequence_arrows(b, pv)
            if arrows:
                assert arrows[-1]["color"] == "green", (fen, played)
