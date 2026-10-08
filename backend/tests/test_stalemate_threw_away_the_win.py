"""Stalemating from a winning position is the lesson, not a footnote.

Farhan wrote this by hand twice while reviewing geometry gaps, because nothing
computed it: "Rd1 is a checkmate winning the game on spot while playing f4
results in a stalemate (draw)".

Measured over 249,311 stored move records: 562 positions had a stalemating move
on the board while the mover was winning, and 44 players played it. One of those
44 was told "Your opponent tidys up the king, keeping it safe."

Every fixture here is a real position out of that 44, or a mirror of one. The
first draft of this test used two hand-built FENs and both were wrong -- one
move was not even legal. Fixtures get verified against `board.is_stalemate()`
in the test itself, never by eye.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_facts import extract_facts  # noqa: E402

# Game 131bc0ce, move 80. Black is a queen up against a bare king and played
# Kc6. Eight of the 25 legal moves here stalemate, which is why someone walked
# into it. eval_before was -9970 (white-POV: black is mating).
REAL_FEN = "K7/8/1q6/2k5/8/8/8/8 b - - 25 80"
REAL_STALEMATES = "Kc6"
REAL_KEEPS_PLAYING = "Qb7+"

# The same position mirrored, so the white-to-move branch of the sign test runs
# against a derived board rather than one invented by hand.
MIRROR_FEN = chess.Board(REAL_FEN).mirror().fen()
MIRROR_STALEMATES = "Qc2"


def _facts(fen, played, eval_cp):
    return extract_facts(fen_before=fen, played_san=played, mover_is_user=True,
                         eval_before_cp=eval_cp, cp_loss=900)


class TestTheFixtures:
    """If these fail, every assertion below is meaningless."""

    def test_the_real_move_stalemates(self):
        b = chess.Board(REAL_FEN)
        b.push_san(REAL_STALEMATES)
        assert b.is_stalemate()

    def test_the_control_move_does_not_stalemate(self):
        b = chess.Board(REAL_FEN)
        b.push_san(REAL_KEEPS_PLAYING)
        assert not b.is_stalemate()

    def test_the_mirror_is_white_to_move_and_stalemates(self):
        b = chess.Board(MIRROR_FEN)
        assert b.turn is chess.WHITE
        b.push_san(MIRROR_STALEMATES)
        assert b.is_stalemate()


class TestTheFact:
    def test_stalemate_from_a_winning_position_is_flagged(self):
        f = _facts(REAL_FEN, REAL_STALEMATES, -9970)
        assert f["played_is_stalemate"] is True
        assert f["played_stalemate_threw_away_win"] is True

    def test_a_move_that_keeps_playing_is_not_flagged(self):
        f = _facts(REAL_FEN, REAL_KEEPS_PLAYING, -9970)
        assert f["played_is_stalemate"] is False
        assert f["played_stalemate_threw_away_win"] is False


class TestTheWinningQualifier:
    def test_stalemate_without_a_winning_eval_is_not_the_same_lesson(self):
        """Stalemating a dead position saves half a point. Only giving a win
        away is the blunder, so the two facts stay separate."""
        f = _facts(REAL_FEN, REAL_STALEMATES, 0)
        assert f["played_is_stalemate"] is True
        assert f["played_stalemate_threw_away_win"] is False

    def test_a_losing_mover_who_stalemates_is_not_blamed(self):
        """Black here is winning, so a POSITIVE white-POV eval would mean black
        is lost. Stalemate is then a rescue, not a mistake."""
        f = _facts(REAL_FEN, REAL_STALEMATES, 9970)
        assert f["played_is_stalemate"] is True
        assert f["played_stalemate_threw_away_win"] is False

    def test_the_eval_is_read_from_the_movers_side_not_whites(self):
        """eval_before_cp is white-POV. Both signs must resolve to "the mover
        was winning" -- reading it wrong silently misses one whole colour.
        44 of the 44 real cases are black-to-move, so the white branch has no
        natural coverage and is only protected here."""
        black = _facts(REAL_FEN, REAL_STALEMATES, -9970)
        white = _facts(MIRROR_FEN, MIRROR_STALEMATES, 9970)
        assert black["played_stalemate_threw_away_win"] is True
        assert white["played_stalemate_threw_away_win"] is True

    def test_no_eval_means_no_claim(self):
        f = _facts(REAL_FEN, REAL_STALEMATES, None)
        assert f["played_is_stalemate"] is True
        assert f["played_stalemate_threw_away_win"] is False


# ── The sentence ───────────────────────────────────────────────────────────
from services.caption_pipeline import (  # noqa: E402
    CrossMoveState,
    MoveInputs,
    _lead_with_the_stalemate,
    _names_the_move,
    build_move_teaching_decision,
)

TAIL_WITH_BEST = "You played Kc6; Qb7+ was the stronger move here."
TAIL_FLOOR = "Your opponent tidys up the king, keeping it safe."


class TestTheSentence:
    def test_the_user_who_gave_the_win_away_is_told_so(self):
        out = _lead_with_the_stalemate(
            TAIL_FLOOR, played_san="Kc6", mover_is_user=True,
            threw_away_win=True, best_move_san="Qb7+")
        assert out.startswith("You had this won.")
        assert "draw by stalemate" in out

    def test_the_user_who_escaped_is_told_so_not_blamed(self):
        out = _lead_with_the_stalemate(
            TAIL_FLOOR, played_san="Kc6", mover_is_user=False,
            threw_away_win=True, best_move_san=None)
        assert out.startswith("Your opponent was winning.")
        assert "draw by stalemate" in out
        assert "You had this won" not in out

    def test_floor_text_is_dropped_because_it_reads_as_praise(self):
        """"tidys up the king, keeping it safe" on the move that ended the
        game is the caption that started this work. It must not survive."""
        out = _lead_with_the_stalemate(
            TAIL_FLOOR, played_san="Kc6", mover_is_user=False,
            threw_away_win=True, best_move_san=None)
        assert "tidys up the king" not in out

    def test_a_tail_naming_the_better_move_is_kept(self):
        out = _lead_with_the_stalemate(
            TAIL_WITH_BEST, played_san="Kc6", mover_is_user=True,
            threw_away_win=True, best_move_san="Qb7+")
        assert TAIL_WITH_BEST in out

    def test_the_played_move_is_named_once_not_twice(self):
        """All 68 user-side tails open with the played move, so naming it in
        the lead as well said it twice."""
        out = _lead_with_the_stalemate(
            TAIL_WITH_BEST, played_san="Kc6", mover_is_user=True,
            threw_away_win=True, best_move_san="Qb7+")
        assert out.count("Kc6") == 1

    def test_the_move_is_named_when_no_tail_will_name_it(self):
        out = _lead_with_the_stalemate(
            TAIL_FLOOR, played_san="Kc6", mover_is_user=False,
            threw_away_win=True, best_move_san=None)
        assert "Kc6" in out

    def test_a_stalemate_that_cost_nothing_gets_no_blame_and_no_principle(self):
        out = _lead_with_the_stalemate(
            "", played_san="Kc6", mover_is_user=True,
            threw_away_win=False, best_move_san=None)
        assert "draw by stalemate" in out
        assert "You had this won" not in out
        assert "check your opponent has a move" not in out

    def test_it_stays_inside_the_word_cap(self):
        out = _lead_with_the_stalemate(
            TAIL_WITH_BEST, played_san="Kc6", mover_is_user=True,
            threw_away_win=True, best_move_san="Qb7+")
        assert len(out.split()) <= 60


class TestTheTokenCheck:
    """A SAN carries +, # and =, which word-boundary classes split in the
    wrong places. The scan is explicit for that reason."""

    def test_a_checking_move_is_matched(self):
        assert _names_the_move("Qb7+ was better.", "Qb7+")

    def test_a_mating_move_is_matched(self):
        assert _names_the_move("Rd1# was the move.", "Rd1#")

    def test_a_longer_san_is_not_matched_by_its_prefix(self):
        assert not _names_the_move("Qb7+ was better.", "Qb7")
        assert not _names_the_move("Nxa5 grabs the pawn.", "Na5")

    def test_a_san_inside_a_word_is_not_a_match(self):
        assert not _names_the_move("the b7-pawn", "b7")
        assert not _names_the_move("rooks on the e-file", "e4")

    def test_castling_does_not_match_the_longer_castle(self):
        assert _names_the_move("O-O was better.", "O-O")
        assert not _names_the_move("O-O-O was better.", "O-O")


class TestTheWholeCard:
    """Through the real entry point, no engine."""

    def _decide(self, mover_is_user):
        return build_move_teaching_decision(
            MoveInputs(
                fen_before=REAL_FEN, played_san=REAL_STALEMATES,
                mover_is_user=mover_is_user, mover_is_white=False,
                user_color=("black" if mover_is_user else "white"),
                full_move_number=80, move_history_san=[],
                best_move_san="Qb7+", eval_before_cp=-9970, eval_after_cp=0,
                cp_loss=(9970 if mover_is_user else 0),
                pv_after_played=[], pv_after_best=["Qb7+"],
                allow_fresh_engine_verification=False,
            ),
            CrossMoveState(),
        )

    def test_the_card_says_the_game_is_drawn(self):
        for mover_is_user in (True, False):
            d = self._decide(mover_is_user)
            assert "draw by stalemate" in d.text.caption, mover_is_user
            assert "STALEMATE_LEAD" in (d.text.rule_name or ""), mover_is_user

    def test_the_card_still_passes_the_truth_check(self):
        """The sentence goes in above the final verify on purpose, so it is
        held to the same check as every other caption."""
        for mover_is_user in (True, False):
            d = self._decide(mover_is_user)
            assert d.explanation.final_verified is True, mover_is_user

    def test_no_claim_survives_about_what_follows_the_move(self):
        for mover_is_user in (True, False):
            d = self._decide(mover_is_user)
            assert "allows mate in" not in d.text.caption, mover_is_user


class TestWhyNoMateGuardHere:
    """13 stored cards read "allows mate in N" about a move after which there
    are no moves. A guard in the forced-mate block was written, measured, and
    removed: it moved 0 of 132, because a stalemating move has no engine line
    to read a mate out of. Recorded so it is not added back on the strength of
    the stored captions alone -- those came from code that no longer exists,
    and only a re-render clears them."""

    def test_a_stalemating_move_has_no_continuation_to_read(self):
        b = chess.Board(REAL_FEN)
        b.push_san(REAL_STALEMATES)
        assert b.is_game_over()
        assert list(b.legal_moves) == []

    def test_the_card_makes_no_mate_claim_about_the_played_move(self):
        d = build_move_teaching_decision(
            MoveInputs(
                fen_before=REAL_FEN, played_san=REAL_STALEMATES,
                mover_is_user=True, mover_is_white=False, user_color="black",
                full_move_number=80, move_history_san=[],
                best_move_san="Qb7+", eval_before_cp=-9970, eval_after_cp=0,
                cp_loss=9970, pv_after_played=[], pv_after_best=["Qb7+"],
                allow_fresh_engine_verification=False,
            ),
            CrossMoveState(),
        )
        assert d.debug_facts.get("allows_forced_mate") is not True
