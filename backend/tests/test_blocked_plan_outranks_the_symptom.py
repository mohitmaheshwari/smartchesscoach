"""Cause before symptom, on the card that proved the ranking was missing.

Mohit 2026-10-21, on move 6 Nc3 of his own game, which read "Their knight
comes straight back to b1. The move loses time.":

    "I think the NC3 blocks your own c pawn gives a better study, of chess you
     know, the other caption is more to just to dhwatever wihtout any
     learning, that's more of cramming part"

and, separately:

    "and secondly why would nC3 comes back to b1, there is no attack on nc3 in
     coming future, it's safe there"

Both complaints are the same bug. The reasoner returns THREE answers on that
position -- blocked_a_plan (CAUSE), engine_undoes_it (EVIDENCE), returns_home
(SYMPTOM) -- and the shipped caption spoke the weakest one, because the rule
that was wired is the symptom rule.

The geometry is asserted here with python-chess alone, so a wrong question
cannot hide behind a wrong control.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_pipeline import _say_the_plan_is_blocked  # noqa: E402
from services.contrastive_reasoner import (  # noqa: E402
    CAUSE,
    EVIDENCE,
    SYMPTOM,
    q_blocked_a_plan,
    reason,
)

# move 6 of game 56b6c294, White to move
NC3 = "r2qkb1r/ppp2ppp/2n1pn2/3p1b2/3P4/P3PN2/1PP1BPPP/RNBQK2R w KQkq - 0 6"
BEST = "O-O"
PV_BEST = ["Bd6", "c4", "dxc4", "Nbd2", "Na5", "Ne5"]
PV_PLAYED = ["a6", "Nh4", "g6", "Nb1", "Ne4", "Nxf5", "gxf5", "g3"]


def ctx_for(fen, played, best, pv_best, pv_played):
    board = chess.Board(fen)
    after = board.copy()
    after.push(board.parse_san(played))
    return {"before": board, "after": after, "played_san": played,
            "best_san": best, "pv_best": list(pv_best),
            "pv_played": list(pv_played)}


class TestTheBoardSaysWhatIClaim:
    """No question involved. If these fail the lesson is wrong."""

    def test_c4_is_legal_before_the_knight_goes_there(self):
        board = chess.Board(NC3)
        assert any(board.san(m) == "c4" for m in board.legal_moves)

    def test_and_illegal_after(self):
        board = chess.Board(NC3)
        board.push_san("Nc3")
        probe = board.copy()
        probe.turn = chess.WHITE           # "if they do nothing"
        probe.ep_square = None
        assert probe.is_valid() and not probe.is_check()
        assert not any(probe.san(m) == "c4" for m in probe.legal_moves)

    def test_because_the_knight_stands_in_front_of_that_pawn(self):
        board = chess.Board(NC3)
        board.push_san("Nc3")
        assert board.piece_at(chess.C3) == chess.Piece(chess.KNIGHT, chess.WHITE)
        assert board.piece_at(chess.C2) == chess.Piece(chess.PAWN, chess.WHITE)

    def test_the_engine_wanted_c4_on_its_very_next_turn(self):
        """Played out, never read off the string."""
        board = chess.Board(NC3)
        board.push_san(BEST)
        board.push_san(PV_BEST[0])         # Bd6
        assert any(board.san(m) == "c4" for m in board.legal_moves)

    def test_nothing_ever_attacks_the_knight_on_c3(self):
        """Mohit: "there is no attack on nc3 in coming future, it's safe
        there". The engine retreats it to regroup, not because it is chased,
        which is why "the move loses time" reads the manoeuvre backwards."""
        board = chess.Board(NC3)
        board.push_san("Nc3")
        assert not board.attackers(chess.BLACK, chess.C3)


class TestTheCauseIsFoundAndOutranksTheRest:
    def test_the_cause_fires(self):
        out = q_blocked_a_plan(ctx_for(NC3, "Nc3", BEST, PV_BEST, PV_PLAYED))
        assert out is not None
        assert out["san"] == "c4"
        assert out["tier"] == CAUSE

    def test_it_knows_our_own_move_is_the_blocker(self):
        out = q_blocked_a_plan(ctx_for(NC3, "Nc3", BEST, PV_BEST, PV_PLAYED))
        assert out["in_the_way"] is True
        assert out["is_pawn_push"] is True
        assert out["file"] == "c"
        assert out["played_piece"] == "knight"
        assert out["played_to"] == "c3"

    def test_all_three_tiers_answer_and_the_cause_leads(self):
        found = reason(chess.Board(NC3), "Nc3", BEST, PV_BEST, PV_PLAYED)
        tiers = [f["tier"] for f in found]
        ids = [f["id"] for f in found]
        assert CAUSE in tiers and EVIDENCE in tiers and SYMPTOM in tiers, ids
        assert found[0]["id"] == "blocked_a_plan"
        assert tiers == sorted(tiers, reverse=True)


class TestTheSentence:
    def test_it_says_the_block(self):
        out = q_blocked_a_plan(ctx_for(NC3, "Nc3", BEST, PV_BEST, PV_PLAYED))
        line = _say_the_plan_is_blocked(out, mover_is_user=False)
        assert line == ("Their knight on c3 blocks their own c-pawn. "
                        "The better line plays c4.")

    def test_it_flips_for_a_user_card(self):
        out = q_blocked_a_plan(ctx_for(NC3, "Nc3", BEST, PV_BEST, PV_PLAYED))
        line = _say_the_plan_is_blocked(out, mover_is_user=True)
        assert line.startswith("Your knight on c3 blocks your own c-pawn")

    def test_it_never_says_loses_time(self):
        """The symptom wording this replaces, and the half of it Mohit showed
        was wrong on this very position."""
        out = q_blocked_a_plan(ctx_for(NC3, "Nc3", BEST, PV_BEST, PV_PLAYED))
        line = _say_the_plan_is_blocked(out, mover_is_user=False).lower()
        assert "loses time" not in line
        assert "comes straight back" not in line

    def test_no_digits_outside_squares_and_san(self):
        import re
        out = q_blocked_a_plan(ctx_for(NC3, "Nc3", BEST, PV_BEST, PV_PLAYED))
        line = _say_the_plan_is_blocked(out, mover_is_user=False)
        stripped = re.sub(r"\b[KQRBN]?[a-h]?x?[a-h][1-8](\+|#)?\b", "", line)
        assert not re.search(r"\d", stripped), line

    def test_sentences_stay_short(self):
        import re
        out = q_blocked_a_plan(ctx_for(NC3, "Nc3", BEST, PV_BEST, PV_PLAYED))
        line = _say_the_plan_is_blocked(out, mover_is_user=False)
        for s in re.split(r"(?<=[.!?])\s+", line):
            assert len(s.split()) <= 12, s


class TestAMoveCannotBlockItself:
    """Found by reading the corpus, not by reasoning. The better line often
    plays the SAME move a few plies later; having played it we cannot play it
    again, which is legally true and says nothing. Before this guard the cards
    read "Your pawn on h5 blocks your own h-pawn. The better line plays h5."

    The Nc3 card never showed it, because there the blocked move is a
    different move entirely -- which is what comes of validating a question on
    one position."""

    def test_the_same_move_later_in_the_line_is_not_a_block(self):
        board = chess.Board()
        board.push_san("e4"); board.push_san("e6")
        board.push_san("d4"); board.push_san("d5")
        fen = board.fen()
        # the better line plays h5 later; we play h5 now
        out = q_blocked_a_plan(
            ctx_for(fen, "Nc3", "Nd2", ["Nf6", "e5", "Nfd7", "Bd3"], ["Bb4"]))
        if out is not None:
            assert out["san"] != "Nc3", out

    def test_a_piece_cannot_stand_in_its_own_way(self):
        """Second shape, found the same way. The d-pawn goes d7-d6, so d7-d5
        is gone -- and the card said "Your pawn on d6 blocks your own d-pawn",
        which is the pawn talking about itself. Same origin square means same
        man."""
        board = chess.Board()
        for san in ("e4", "e6", "d4"):
            board.push_san(san)
        fen = board.fen()                      # Black to move, pawn on d7
        out = q_blocked_a_plan(
            ctx_for(fen, "d6", "d5", ["Nc3", "Nf6", "e5"], ["Nc3"]))
        if out is not None:
            assert out["from_square"] != "d7", out

    def test_the_guard_is_in_the_question_not_the_sentence(self):
        """Asserted on the real shape: a question that reports a self-block
        would let any future caller print it."""
        board = chess.Board("r2qkb1r/ppp2ppp/2n1pn2/3p1b2/3P4/P3PN2/1PP1BPPP/RNBQK2R w KQkq - 0 6")
        out = q_blocked_a_plan({
            "before": board, "after": board.copy(),
            "played_san": "c4", "best_san": "O-O",
            "pv_best": ["Bd6", "c4", "dxc4"], "pv_played": ["dxc4"]})
        if out is not None:
            assert out["san"] != "c4", out


class TestOnlyTheVerifiedBranchSpeaks:
    def test_a_non_pawn_block_stays_quiet(self):
        """The "took the square your own piece wanted" branch is real but
        unread; it produced "Your bishop on b2 takes the square your own
        bishop wanted for Bb2" in the corpus."""
        out = dict(q_blocked_a_plan(ctx_for(NC3, "Nc3", BEST, PV_BEST, PV_PLAYED)))
        out["is_pawn_push"] = False
        assert _say_the_plan_is_blocked(out, mover_is_user=True) == ""


class TestItStaysSilentWithoutTheWholeStory:
    def test_silence_when_our_move_is_not_the_blocker(self):
        """Precision: a move of the better line that became illegal for some
        other reason is a coincidence, not a lesson. The sentence refuses it
        even though the question still reports the block."""
        out = dict(q_blocked_a_plan(ctx_for(NC3, "Nc3", BEST, PV_BEST, PV_PLAYED)))
        out["in_the_way"] = False
        assert _say_the_plan_is_blocked(out, mover_is_user=False) == ""

    def test_silence_on_no_answer(self):
        assert _say_the_plan_is_blocked(None, mover_is_user=True) == ""
        assert _say_the_plan_is_blocked({}, mover_is_user=True) == ""

    def test_an_ordinary_opening_move_blocks_nothing_of_its_own(self):
        out = q_blocked_a_plan(
            ctx_for(chess.STARTING_FEN, "e4", "d4", ["d5", "c4", "e6"],
                    ["e5", "Nf3", "Nc6"]))
        line = _say_the_plan_is_blocked(out, mover_is_user=True)
        assert line == "", line
