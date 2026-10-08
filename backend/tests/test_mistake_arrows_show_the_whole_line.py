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
    """UPDATED 2026-10-08. These first asserted the sequence drew on the
    STORED 4-ply line. It no longer does, and that is a fix rather than a
    regression: over four plies this position reads +2 for the mover -- the
    bishop has been given and taken back, the fork has not landed -- so the
    verdict is `neither`, and a card with no story may not draw a plan. The
    sequence is now gated on `punishment` on our side as it already was on
    theirs. Mohit found the ungated version twice, as arrows under words that
    explained one of them."""

    def test_four_plies_cannot_establish_a_punishment(self):
        from services.caption_pipeline import classify_move_story
        story, detail = classify_move_story(
            FEN, "Be6", STORED_PV, ["Ng5", "Be3", "Bxc4", "Bxf4"], "Bf5")
        assert story == "neither"
        assert detail["played_material_swing"] == 2   # the sac is already repaid

    def test_so_the_short_line_draws_no_plan(self):
        assert _arrows(STORED_PV) == []

    def test_the_full_line_does_establish_it_and_draws(self):
        from services.caption_pipeline import classify_move_story
        assert classify_move_story(
            FEN, "Be6", FULL_PV, ["Ng5", "Be3", "Bxc4", "Bxf4"], "Bf5")[0] == "punishment"
        assert len(_arrows(FULL_PV)) > 1

    def test_the_refutation_opens_the_picture(self):
        assert ("d3", "h7", "blue") in _arrows(FULL_PV)

    def test_their_forced_reply_is_drawn_so_it_reads_as_an_order_of_events(self):
        assert ("g8", "h7", "palegrey") in _arrows(FULL_PV)


class TestTheLineHasToBeLongEnough:
    """Mohit 2026-10-07: "first we neeed to store the 8 moves not just 4pl".
    He is right, and this is the test that holds the two apart: the walk is
    correct either way, but it cannot find a payoff that was never stored."""

    def test_a_four_ply_line_cannot_reach_the_fork(self):
        """It used to settle for the check and call that the payoff. Now it
        draws nothing at all, because four plies cannot even establish that
        there IS a punishment -- see TestTheSequenceIsDrawn."""
        assert ("g5", "e6", "green") not in _arrows(STORED_PV)
        assert _arrows(STORED_PV) == []

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
        """Where a sequence is drawn at all, exactly one arrow is green."""
        assert sum(1 for a in _arrows(FULL_PV) if a[2] == "green") == 1
        assert _arrows(STORED_PV) == []


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


class TestTheMoveTheyMissed:
    """Mohit 2026-10-07 on move 5 of 413fcce2, after the five-arrow picture was
    dropped and the card drew nothing: "you already saw a knight could take the
    pawn and then there is no action, so there is no recapture, so obviously it
    was winning, in that case there should have only been one arrow, correct?"

    Nothing recaptures on e4, so the idea is complete in one move. One arrow.
    """

    OPP_FEN = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2P2N2/PP1P1PPP/RNBQ1RK1 b kq - 0 5"
    CAPTION = ("Opponent's O-O is a mistake — they had Nxe4, grabbing your "
               "pawn on e4 for free.")
    FACTS = {"opp_missed_capture_san": "Nxe4"}

    def _boards(self, played="O-O"):
        before = chess.Board(self.OPP_FEN)
        after = before.copy()
        after.push_san(played)
        return before, after

    def test_the_pawn_really_is_free(self):
        """The premise. If something recaptured, a single arrow would be a lie
        and the card would need a line instead."""
        before, _ = self._boards()
        after_nxe4 = before.copy()
        after_nxe4.push_san("Nxe4")
        assert not after_nxe4.attackers(chess.WHITE, chess.parse_square("e4"))

    def test_one_arrow_for_the_move_they_missed(self):
        from services.caption_pipeline import _missed_move_arrow
        before, after = self._boards()
        arrows = _missed_move_arrow(before, after, self.FACTS, self.CAPTION)
        assert [(a["from"], a["to"]) for a in arrows] == [("f6", "e4")]

    def test_the_whole_card_draws_exactly_that(self):
        d = build_move_teaching_decision(
            MoveInputs(
                fen_before=self.OPP_FEN, played_san="O-O", mover_is_user=False,
                mover_is_white=False, user_color="white", full_move_number=5,
                move_history_san=[], best_move_san="Nxe4",
                eval_before_cp=-10, eval_after_cp=115, cp_loss=125,
                pv_after_played=["d4", "Be7", "Re1", "d6", "h3", "a5", "Bb3",
                                 "exd4", "cxd4", "d5", "e5", "Ne4"],
                pv_after_best=[], allow_fresh_engine_verification=False,
            ),
            CrossMoveState(),
        )
        assert [(a["from"], a["to"]) for a in (d.visual.arrows or [])] == [("f6", "e4")]

    def test_the_move_comes_from_the_fact_never_from_the_sentence(self):
        """The first attempt read the SAN out of the caption text. Over 3,311
        opponent cards that drew g1->f3 for "Bishop out before Nf3 keeps the f4
        option open", and drew THEIR king castling for "Play O-O -- it tucks
        your king away", which is an instruction to US. A string match cannot
        license a claim about the board."""
        from services.caption_pipeline import _missed_move_arrow
        before, after = self._boards()
        assert _missed_move_arrow(before, after, {},
                                  "Bishop out before Nf3 keeps the f4 option open.") == []

    def test_the_words_must_still_explain_the_arrow(self):
        """42 of 230 cards carrying the fact rendered a variant that never
        mentions the move. An arrow nobody explained is where this started."""
        from services.caption_pipeline import _missed_move_arrow
        before, after = self._boards()
        assert _missed_move_arrow(before, after, self.FACTS,
                                  "Opponent castles.") == []

    def test_nothing_is_drawn_once_the_board_has_moved_on(self):
        """The standing rule -- never draw their better move -- exists because
        it is legal before their move, not on the board the card renders. That
        is right when the played move disturbed the squares and too blunt when
        it did not. Castling moved e8->g8 and h8->f8; the knight is still on f6
        and the pawn still on e4."""
        from services.caption_pipeline import _missed_move_arrow
        before, _ = self._boards()
        moved_on = before.copy()
        moved_on.push_san("Nxe4")          # the knight is no longer on f6
        assert _missed_move_arrow(before, moved_on, self.FACTS, self.CAPTION) == []

    def test_the_squares_the_arrow_uses_are_the_ones_on_screen(self):
        _before, after = self._boards()
        assert after.piece_at(chess.parse_square("f6")).symbol() == "n"
        assert after.piece_at(chess.parse_square("e4")).symbol() == "P"
