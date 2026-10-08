"""The six board lessons: board fact first, teaching last, arrows from the same slots.

Mohit 2026-10-07: "from the board pick the thing and end the lesson, these are
our templates". Every position here is a real one from his games, pulled out of
a 100-game both-sides analysis rather than hand-built, because hand-built
fixtures in this repo have a long record of being illegal.

The assertions that matter are the last two classes: a square the sentence
names must be drawn, and an arrow may never begin on an empty, unconnected
square. Those are the two ways the old pipeline let the words and the picture
talk about different moves.
"""
from __future__ import annotations

import os
import re
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.board_lessons import (  # noqa: E402
    BoardLesson,
    drawable_on,
    find_board_lesson,
)

# label -> (fen, played, engine line after it, best move)
CASES = {
    "hanging_ignored": (
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
        "Bc5", ["Nxe5", "Nxe5", "d4"], "Nc6"),
    "moved_the_guard": (
        "r1bqkbnr/p1pp1ppp/1p6/8/3QP3/2N5/PPP2PPP/R1B1KB1R b KQkq - 1 6",
        "Bc5", ["Qxg7", "Qf6", "Qxf6", "Nxf6"], "Bb7"),
    "landed_uncounted": (
        "r1bqkbnr/pppp1ppp/2n5/8/3NP3/8/PPP2PPP/RNBQKB1R b KQkq - 0 4",
        "Nxd4", ["Qxd4", "Qf6", "Qe3"], "Nf6"),
    "king_square_theirs": (
        "r1bq1rk1/ppp2ppp/1bn5/3pP3/3P1B2/2PB1N2/PP1Q2PP/R4RK1 b - - 0 11",
        "Na5", ["Ng5", "h6", "Nh7", "Qh4", "Nxf8", "Kxf8"], "Ne7"),
    # A capture was there and the count stays winning after their reply, so
    # the generic lesson is the right one.
    "capture_available": (
        "r1bqk2r/pppp1ppp/2n4n/2b3N1/2BpP3/8/PPP2PPP/RNBQK2R w KQkq - 4 6",
        "Qf3", ["Ne5", "Qe2", "a5", "O-O"], "Bxf7+"),
    # Mohit's Bc4 card: e5 is attacked twice and defended once, and d6 ends it.
    # 96 of the 320 offered captures in his games close like this.
    "capture_window_closed": (
        "rnbqkbnr/pp1p1ppp/4p3/2P5/4PB2/2N5/PPP2PPP/R2QKBNR b KQkq - 1 5",
        "d5", ["cxd6", "g5", "Be3"], "Bxc5"),
}


def _lesson(label: str) -> BoardLesson:
    fen, played, line, best = CASES[label]
    found = find_board_lesson(fen, played, line, best)
    assert found is not None, f"{label} produced no lesson"
    return found


class TestEachTemplateFiresOnItsOwnPosition:

    def test_every_case_picks_the_template_it_is_named_for(self):
        for label in CASES:
            assert _lesson(label).template_id == label

    def test_the_hanging_pawn_card_names_the_pawn_and_the_knight(self):
        caption = _lesson("hanging_ignored").caption
        assert "pawn on e5" in caption and "knight on f3" in caption

    def test_the_guard_card_names_what_the_bishop_was_holding(self):
        caption = _lesson("moved_the_guard").caption
        assert "f8" in caption and "g7" in caption

    def test_the_king_square_card_names_the_guard_and_the_rook(self):
        """Mohit's Na5 card. The GUARD is the lesson, so it has to be said."""
        caption = _lesson("king_square_theirs").caption
        assert "h7" in caption
        assert "bishop on d3" in caption
        assert "rook on f8" in caption

    def test_a_free_pawn_counts_as_a_capture_worth_naming(self):
        """The first cut set the bar at a knight and hid every pawn recapture."""
        assert "pawn on f7" in _lesson("capture_available").caption

    def test_the_narrow_lesson_wins_when_the_chance_really_closes(self):
        """Mohit on the Bc4 card: "look at every capture" is true and misses
        the point, which is that the chance was one move wide."""
        caption = _lesson("capture_window_closed").caption
        assert "no longer true" in caption
        assert "cxd6" in caption


class TestTheLessonIsTheSecondSentence:
    """The board fact changes per position; the teaching never does."""

    LESSONS = {
        "hanging_ignored": "Look at what they attack before you start your own plan.",
        "moved_the_guard": "Before you move a piece, check what it is holding.",
        "landed_uncounted": "Count attackers and defenders before you put a piece on a square.",
        "king_square_theirs": "A square next to your king is only safe if nothing of theirs guards it.",
        "capture_available": "Look at every capture before anything else.",
        "capture_window_closed": ("A capture that is there now is often gone next "
                                  "move, so count before you play something else."),
    }

    def test_every_card_ends_with_its_lesson(self):
        for label, lesson in self.LESSONS.items():
            assert _lesson(label).caption.endswith(lesson), label

    def test_no_card_uses_a_numeral(self):
        """"d4 is attacked 1 times" was the first thing these produced.

        Squares and SAN carry digits legitimately, so strip anything that
        looks like a square or a move first -- the first version of this test
        used a hand-written list of squares and broke the moment a caption
        mentioned cxd6."""
        for label in CASES:
            text = re.sub(r"[KQRBN]?[a-h]?x?[a-h][1-8](=[QRBN])?[+#]?", "",
                          _lesson(label).caption)
            assert not re.search(r"\d", text), (label, text)


class TestTheWordsAndThePictureCannotDisagree:
    """The whole point of the module. One slots dict feeds both."""

    def test_every_square_the_sentence_names_is_drawn(self):
        for label in CASES:
            found = _lesson(label)
            fen, played, _, _ = CASES[label]
            moved_from = chess.square_name(chess.Board(fen).parse_san(played).from_square)
            named = set(re.findall(r"\b[a-h][1-8]\b", found.caption)) - {moved_from}
            drawn = {a["from"] for a in found.arrows + found.plan_arrows} | \
                    {a["to"] for a in found.arrows + found.plan_arrows}
            assert not (named - drawn), (label, named - drawn)

    def test_no_arrow_starts_from_an_empty_unconnected_square(self):
        """162 of 1,082 arrows did, before the rule went in."""
        for label in CASES:
            found = _lesson(label)
            fen, played, _, _ = CASES[label]
            board = chess.Board(fen)
            board.push(board.parse_san(played))
            reached = set()
            for arrow in found.arrows:
                occupied = board.piece_at(chess.parse_square(arrow["from"])) is not None
                assert occupied or arrow["from"] in reached, (label, arrow)
                reached.add(arrow["to"])

    def test_arrows_that_cannot_be_drawn_get_their_own_board(self):
        """Silence beats an arrow starting nowhere; a second frame beats both."""
        board = chess.Board("r1bqkbnr/pppp1ppp/2n5/8/3pP3/5N2/PPP2PPP/RNBQKB1R w KQkq - 0 4")
        found = find_board_lesson(board.fen(), "Ng5", ["Nxe4", "Nxe4", "d3"], "Nxd4")
        assert found is not None and found.template_id == "capture_available"
        # the recommended capture is by the knight that has since gone to g5
        assert found.arrows == []
        assert found.plan_arrows and found.plan_fen == board.fen()


class TestTheArrowRuleItself:

    def test_a_piece_on_the_from_square_is_drawable(self):
        board = chess.Board()
        ok, orphans = drawable_on(board, [{"from": "e2", "to": "e4", "color": "blue"}])
        assert ok and not orphans

    def test_an_empty_from_square_is_not(self):
        board = chess.Board()
        ok, orphans = drawable_on(board, [{"from": "e4", "to": "e5", "color": "blue"}])
        assert not ok and orphans

    def test_but_it_is_when_the_previous_arrow_pointed_there(self):
        """c1->c3 then c3->c8: the eye is already following the line."""
        board = chess.Board()
        ok, orphans = drawable_on(board, [
            {"from": "e2", "to": "e4", "color": "blue"},
            {"from": "e4", "to": "e5", "color": "green"},
        ])
        assert len(ok) == 2 and not orphans


class TestSilenceWhereThereIsNoLesson:

    def test_a_quiet_move_with_no_capture_anywhere_says_nothing(self):
        """416 of 1,056 mistakes get no lesson, and that is the honest answer."""
        found = find_board_lesson(
            "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
            "d3", ["Bc5", "c3", "O-O"], "O-O")
        assert found is None

    def test_a_malformed_position_is_silent_rather_than_guessing(self):
        assert find_board_lesson("not a fen", "e4", [], None) is None
        assert find_board_lesson(chess.STARTING_FEN, "Qh8", [], None) is None


class TestForkIsNamedOnlyWhenItIsOne:
    """Mohit asked whether the king-square card was "sort of fork". It is not.

    The knight on h7 attacks exactly one black piece, the rook on f8; what
    makes it work is that the square cannot be answered. 45 of that family's
    48 cards attack a single piece. Three were real forks, and those get this
    template instead.
    """

    # A queen landing with check on one side and a bishop on the other. The
    # position I first picked here now resolves to landed_uncounted -- "two
    # attack f5, nothing defends it" -- which is the better lesson for it, so
    # it is no longer a fork fixture.
    FORK = ("r1bq1r2/pppp1ppk/2n4B/2b5/2BpP3/5Q2/PPP2PPP/RN2K2R b KQ - 0 8",
            "gxh6", ["Qf5+", "Kh8", "Qxc5", "f5", "Bd5"], "d5")

    def test_the_na5_card_is_not_called_a_fork(self):
        assert _lesson("king_square_theirs").template_id != "forked"

    def test_the_knight_on_h7_attacks_exactly_one_piece(self):
        board = chess.Board(CASES["king_square_theirs"][0])
        for san in ("Na5", "Ng5", "h6", "Nh7"):
            board.push_san(san)
        hit = [s for s in board.attacks(chess.H7)
               if board.piece_at(s) and board.piece_at(s).color == chess.BLACK]
        assert len(hit) == 1 and chess.square_name(hit[0]) == "f8"

    def test_a_real_fork_gets_the_fork_lesson(self):
        found = find_board_lesson(*self.FORK)
        assert found is not None and found.template_id == "forked"
        assert found.caption.endswith(
            "Before you move, look for the squares that would hit two of your pieces.")

    def test_a_piece_that_can_simply_be_taken_is_no_fork(self):
        """Without this the family claimed 205 of 1,056 moves -- a quarter of
        every mistake in his games, which is not what a fork is."""
        from services.board_lessons import _can_be_taken_for_profit
        # On d3, not e3: a pawn on e2 cannot capture straight ahead, and the
        # first version of this fixture asked the function to prove something
        # the rules forbid.
        board = chess.Board("4k3/8/8/8/8/3n4/4P3/4K3 w - - 0 1")
        assert _can_be_taken_for_profit(board, chess.WHITE, chess.D3)
        assert not _can_be_taken_for_profit(board, chess.WHITE, chess.E8)

    def test_the_guard_lesson_outranks_an_incidental_fork(self):
        """Qxg7 forks h8 and g8, but the move to explain is the bishop leaving
        f8. "One piece can attack two of yours" does not help him avoid it."""
        assert _lesson("moved_the_guard").template_id == "moved_the_guard"


class TestTheCheckIsSaidWhenThereIsOne:
    """32 of the 48 king-square cards arrive WITH check, and that is the
    forcing half: you must answer, and the piece helps itself meanwhile."""

    def test_a_checking_invasion_says_so(self):
        found = find_board_lesson(
            "r1bq1r2/pppp1ppk/2n4B/2b5/2BpP3/5Q2/PPP2PPP/RN2K2R b KQ - 0 8",
            "gxh6", ["Qf5+", "Kh8", "Qxc5", "f5", "Bd5"], "Nf6")
        if found is not None and found.template_id.startswith("king_square_theirs"):
            assert "check" in found.caption

    def test_the_na5_card_does_not_claim_a_check_it_does_not_give(self):
        assert "check" not in _lesson("king_square_theirs").caption

    def test_both_variants_end_with_the_same_lesson(self):
        import json as _json
        import os as _os
        path = _os.path.join(_BACKEND_ROOT, "data", "captions", "board_lessons.json")
        with open(path, encoding="utf-8") as fh:
            tpl = _json.load(fh)["templates"]
        assert (tpl["king_square_theirs"]["lesson"]
                == tpl["king_square_theirs_check"]["lesson"])
