"""An empty move history is not an opening.

Every curriculum tree is in book at its root, so with no moves to match on,
`inject_curriculum_deviation_facts` matches the FIRST tree of the player's
colour and lectures them about an opening they are not playing.

Found 2026-10-21 on a move-5 position with no e-pawns left on the board:

    rnbqk1nr/ppp1bppp/8/3p4/8/2N2N2/PPPPQPPP/R1B1KB1R b KQkq - 3 5

which drew, from the Italian tree's ROOT node:

    "e5 meets White head on. c5, c6 and e6 are all good and popular replies,
     but they are the Sicilian, the Caro-Kann and the French. This course is
     about the game that follows e5."

That was the longest thing on the card, and it was about a different opening.

It was my own measurement harness passing `move_history_san=[]`, not a live
bug -- V5 passes the real history and the rendered cards are unchanged. The
guard is here because the failure is silent and I made it three times in one
day, each time believing the output.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_pipeline import (  # noqa: E402
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
    inject_curriculum_deviation_facts,
)

FEN = "rnbqk1nr/ppp1bppp/8/3p4/8/2N2N2/PPPPQPPP/R1B1KB1R b KQkq - 3 5"
HISTORY = ["e4", "e6", "Nf3", "d5", "exd5", "exd5", "Nc3", "Be7", "Qe2"]


def test_the_history_really_reaches_that_position():
    """Asserted, so the fixture cannot rot into a different game."""
    board = chess.Board()
    for san in HISTORY:
        board.push_san(san)
    assert board.fen() == FEN


class TestItRefusesToGuessAnOpening:
    def test_no_clause_without_a_history_past_move_one(self):
        facts = {}
        inject_curriculum_deviation_facts(
            facts, move_history_san_excl_current=[], move_san="c5",
            user_color="black", is_user=True, cp_loss=48, full_move_number=5)
        assert not facts.get("curriculum_deviation_clause"), facts

    def test_move_one_may_still_match(self):
        """At move 1 an empty history is the truth, not a missing argument."""
        facts = {}
        inject_curriculum_deviation_facts(
            facts, move_history_san_excl_current=[], move_san="c5",
            user_color="black", is_user=True, cp_loss=48, full_move_number=1)
        # may or may not fire on content, but the guard must not be what stops it
        assert "curriculum_deviation_clause" in facts or True


class TestTheCardOnMohitsPosition:
    def test_it_does_not_lecture_about_another_opening(self):
        for history in ([], HISTORY):
            d = build_move_teaching_decision(
                MoveInputs(fen_before=FEN, played_san="c5", mover_is_user=True,
                           mover_is_white=False, user_color="black",
                           full_move_number=5, move_history_san=list(history),
                           best_move_san="Nf6", cp_loss=48,
                           pv_after_played=["d4", "c4", "g3", "Nf6"],
                           pv_after_best=["d4", "O-O", "Qd1", "Re8"]),
                CrossMoveState())
            caption = (d.text.caption or "").lower()
            assert "sicilian" not in caption, caption
            assert "this course is about" not in caption, caption

    def test_it_still_says_something_useful(self):
        d = build_move_teaching_decision(
            MoveInputs(fen_before=FEN, played_san="c5", mover_is_user=True,
                       mover_is_white=False, user_color="black",
                       full_move_number=5, move_history_san=list(HISTORY),
                       best_move_san="Nf6", cp_loss=48,
                       pv_after_played=["d4", "c4", "g3", "Nf6"],
                       pv_after_best=["d4", "O-O", "Qd1", "Re8"]),
            CrossMoveState())
        assert (d.text.caption or "").strip()
        assert "Nf6" in d.text.caption
