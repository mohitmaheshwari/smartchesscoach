"""The principles, and the selector that only speaks when they separate.

Mohit's position is the whole fixture, because it is where the four principles
came from and because the engine's own ordering there is measured, with a fresh
engine process per move so the numbers do not depend on the order they were
asked for:

    Nf3 0   Bg2 6   d3 20  |  a3 38   e3 45   Na4 50   h3 53   e4 72
    ------- good -------      ------------- inaccuracy -------------
                              (30cp is the inaccuracy floor in services.severity)

The point of the design is the selector, not the principles. Five positional
mechanisms died on 2026-10-29 because each was a property of one move and the
engine's own best move shared it. So the tests that matter here are the ones
proving a shared fact CANNOT be selected -- TestAFactSharedWithAGoodMoveIsNotAReason
and TestNaFourCannotBeRecommended. The rest check the arithmetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.move_principles import (  # noqa: E402
    buries_own_piece,
    develops_a_minor,
    facts_for,
    frees_a_buried_minor,
    sells_a_square_forever,
    separating_themes,
)

# White has played c4, Nc3, g3. Black has e5, Bc5, Nf6. White to move.
FEN = "rnbqk2r/pppp1ppp/5n2/2b1p3/2P5/2N3P1/PP1PPP1P/R1BQKBNR w KQkq - 1 4"
GOOD = ("Nf3", "Bg2", "d3")          # 0, 6, 20 cp
BAD = ("a3", "e3", "Na4", "h3", "e4")  # 38, 45, 50, 53, 72 cp


def _mv(san):
    return chess.Board(FEN), chess.Board(FEN).parse_san(san)


class TestDevelopsAMinor:
    def test_it_fires_on_the_two_developing_moves(self):
        for san in ("Nf3", "Bg2"):
            board, mv = _mv(san)
            assert develops_a_minor(board, mv) is not None, san

    def test_it_declines_every_other_move_in_the_position(self):
        for san in ("d3", "a3", "e3", "h3", "e4"):
            board, mv = _mv(san)
            assert develops_a_minor(board, mv) is None, san

    def test_a_knight_already_out_is_not_development(self):
        """Nc3 is already developed, so Na4 moves it sideways."""
        board, mv = _mv("Na4")
        assert develops_a_minor(board, mv) is None


class TestFreesABuriedMinor:
    def test_d3_frees_the_bishop_that_had_nowhere_to_go(self):
        board, mv = _mv("d3")
        fact = frees_a_buried_minor(board, mv)
        assert fact is not None
        assert fact.subject == "c1"

    def test_the_bishop_really_was_buried_and_really_is_free(self):
        """The fixture has to mean what the test claims."""
        board = chess.Board(FEN)
        assert not [m for m in board.legal_moves if m.from_square == chess.C1]
        after = board.copy(stack=False)
        after.push(after.parse_san("d3"))
        after.turn = chess.WHITE
        assert len([m for m in after.legal_moves
                    if m.from_square == chess.C1]) == 5

    def test_e3_and_e4_do_not_count_as_freeing(self):
        """Both vacate e2 and hand the g1 knight one more square while leaving
        the c1 bishop buried. A total-squares count scored both as freeing
        moves; zero-to-non-zero per piece is what separates d3 from them."""
        for san in ("e3", "e4"):
            board, mv = _mv(san)
            assert frees_a_buried_minor(board, mv) is None, san

    def test_one_e4_frees_the_f1_bishop_from_the_starting_position(self):
        """Written as a decline case first, on the assumption that nothing is
        buried at the start. That is wrong: at move one BOTH bishops have zero
        squares, and 1.e4 really does open the f1 bishop's diagonal, 0 -> 5. So
        this is the principle's positive control on the most familiar position
        there is -- and a reminder that the fixture gets checked, not assumed."""
        board = chess.Board()
        assert not [m for m in board.legal_moves if m.from_square == chess.F1]
        fact = frees_a_buried_minor(board, board.parse_san("e4"))
        assert fact is not None
        assert fact.subject == "f1"

    def test_it_declines_when_no_minor_is_buried(self):
        """No pawns, so the knight on g1 is not shut in by anything."""
        board = chess.Board("4k3/8/8/8/8/8/8/4K1N1 w - - 0 1")
        assert frees_a_buried_minor(board, board.parse_san("Kd1")) is None


class TestSellsASquareForever:
    def test_e4_gives_up_d4(self):
        board, mv = _mv("e4")
        fact = sells_a_square_forever(board, mv)
        assert fact is not None
        assert fact.subject == "d4"

    def test_e3_sells_nothing(self):
        """A single push stops nowhere, so it skips no guarding square."""
        board, mv = _mv("e3")
        assert sells_a_square_forever(board, mv) is None

    def test_f4_is_not_sold_because_the_g3_pawn_guards_it(self):
        """e2-e4 skips e3, which would have guarded BOTH d4 and f4. The test
        has to discriminate inside one move, not just between moves."""
        board, mv = _mv("e4")
        fact = sells_a_square_forever(board, mv)
        assert fact.subject != "f4"

    def test_the_pawn_geometry_is_what_the_claim_says(self):
        board = chess.Board(FEN)
        after = board.copy(stack=False)
        after.push(after.parse_san("e4"))
        # before: the e-pawn could still come to e3 and guard d4
        assert chess.E2 in board.pieces(chess.PAWN, chess.WHITE)
        # after: both candidate files have marched past their guarding ranks
        for sq in (chess.C4, chess.E4):
            assert after.piece_at(sq).piece_type == chess.PAWN

    def test_the_opening_double_push_from_the_start_sells_nothing_permanent(self):
        """1.e4 skips e3, which guards d4 and f4 -- but the d- and f-pawns are
        both still home, so nothing is given up for good."""
        board = chess.Board()
        assert sells_a_square_forever(
            board, board.parse_san("e4")) is None


class TestBuriesOwnPiece:
    def test_it_declines_on_this_position(self):
        """The c1 bishop is already buried, so nothing is newly buried -- a
        piece that had nowhere to go cannot be given nowhere to go."""
        for san in GOOD + BAD:
            board, mv = _mv(san)
            assert buries_own_piece(board, mv) is None, san


class TestTheSelectorOnMohitsPosition:
    def test_development_separates_the_good_moves_from_e4(self):
        out = separating_themes(FEN, "e4", GOOD, phase="opening")
        themes = {s.theme: s for s in out}
        assert "development" in themes
        assert themes["development"].direction == "missed"

    def test_it_also_says_what_e4_itself_did(self):
        out = separating_themes(FEN, "e4", GOOD, phase="opening")
        themes = {s.theme: s for s in out}
        assert "square_control" in themes
        assert themes["square_control"].direction == "received"
        assert themes["square_control"].facts[0].subject == "d4"

    def test_both_answers_come_back_at_once(self):
        """Mohit: "we have 2 answers here" -- one per direction."""
        out = separating_themes(FEN, "e4", GOOD, phase="opening")
        assert {s.direction for s in out} == {"missed", "received"}

    def test_every_inaccuracy_in_the_position_gets_the_development_answer(self):
        for san in BAD:
            out = separating_themes(FEN, san, GOOD, phase="opening")
            assert any(s.theme == "development" and s.direction == "missed"
                       for s in out), san

    def test_e3_does_not_get_the_d4_answer(self):
        """e3 is an inaccuracy too, at 45cp, but it keeps the square. The
        reason must distinguish them -- that is the 27cp between them."""
        out = separating_themes(FEN, "e3", GOOD, phase="opening")
        assert not any(s.theme == "square_control" for s in out)


class TestAFactSharedWithAGoodMoveIsNotAReason:
    """The design claim. This is the test the five dead families would fail."""

    def test_a_good_move_is_never_faulted_against_the_others(self):
        for san in GOOD:
            others = tuple(s for s in GOOD if s != san)
            out = separating_themes(FEN, san, others, phase="opening")
            assert not any(s.direction == "received" for s in out), (
                "%s was faulted against %s" % (san, others))

    def test_development_cannot_be_the_missed_answer_against_a_developing_move(self):
        """Nf3 develops, so "you should have developed" separates nothing."""
        out = separating_themes(FEN, "Nf3", ("Bg2",), phase="opening")
        assert not any(s.theme == "development" for s in out)

    def test_a_theme_true_of_only_some_good_moves_is_not_returned(self):
        """develops_a_minor holds for Nf3 and Bg2 but not d3. At the PRINCIPLE
        level that is a split decision; the theme is what covers all three, and
        a theme that covered only two must not be offered."""
        board = chess.Board(FEN)
        per_move = {san: {f.principle for f in facts_for(
            board, board.parse_san(san), "opening")} for san in GOOD}
        assert per_move["d3"] == {"frees_a_buried_minor"}
        assert per_move["Nf3"] == {"develops_a_minor"}
        # ...and the theme still separates, which is the point of grouping.
        out = separating_themes(FEN, "e4", GOOD, phase="opening")
        assert any(s.theme == "development" for s in out)


class TestNaFourCannotBeRecommended:
    """The live failure this replaces.

    Asked about e4 today, the real why button answers "Na4 chases their
    bishop" -- the engine's SIXTH choice at -15, fifty centipawns below best,
    picked because it is the first move with a nameable mechanism. The
    selector cannot do that: Na4 is not among the engine's good moves, and if
    it were, it separates nothing.
    """

    def test_na4_is_not_offered_as_the_good_move(self):
        out = separating_themes(FEN, "e4", GOOD, phase="opening")
        for sep in out:
            assert "Na4" not in sep.good_moves

    def test_na4_separates_nothing_even_if_someone_passes_it_in(self):
        out = separating_themes(FEN, "e4", ("Na4",), phase="opening")
        assert not any(s.direction == "missed" for s in out)


class TestTheGates:
    def test_development_is_silent_outside_the_opening(self):
        """"Get your minors out" in a four-piece endgame talks nonsense."""
        out = separating_themes(FEN, "e4", GOOD, phase="endgame")
        assert not any(s.theme == "development" for s in out)

    def test_no_phase_given_means_no_gate(self):
        out = separating_themes(FEN, "e4", GOOD, phase=None)
        assert any(s.theme == "development" for s in out)

    def test_nothing_to_compare_against_returns_nothing(self):
        assert separating_themes(FEN, "e4", (), phase="opening") == []

    def test_an_illegal_played_move_returns_nothing(self):
        assert separating_themes(FEN, "Qh5", GOOD, phase="opening") == []

    def test_a_broken_fen_returns_nothing(self):
        assert separating_themes("not a fen", "e4", GOOD) == []

    def test_comparing_a_move_against_itself_returns_nothing(self):
        assert separating_themes(FEN, "e4", ("e4",), phase="opening") == []


class TestPolarityDecidesTheDirection:
    """A virtue the played move HAS and the alternatives lack is a real
    asymmetry and not a fault.

    Measured before this gate existed: over 12 positions the selector faulted
    2 of 33 engine-APPROVED moves, both `received/development` -- "your move
    brought a piece out and the alternatives did not", said as an accusation.
    Separation alone is not enough; the direction has to mean something.
    """

    # Black's Nf6 here develops; the other approved moves do not.
    DEVELOPING_IS_FINE = "rnbqkbnr/ppp1pppp/8/3P4/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2"

    def test_a_developing_move_is_never_faulted_for_developing(self):
        board = chess.Board(self.DEVELOPING_IS_FINE)
        others = [board.san(m) for m in list(board.legal_moves)[:3]
                  if board.san(m) != "Nf6"]
        out = separating_themes(self.DEVELOPING_IS_FINE, "Nf6", others,
                                phase="opening")
        assert not any(s.theme == "development" and s.direction == "received"
                       for s in out)

    def test_development_is_declared_a_virtue(self):
        board = chess.Board(FEN)
        for san in ("Nf3", "d3"):
            facts = facts_for(board, board.parse_san(san), "opening")
            assert facts and all(f.polarity == "virtue" for f in facts), san

    def test_giving_a_square_away_is_declared_a_fault(self):
        board = chess.Board(FEN)
        facts = [f for f in facts_for(board, board.parse_san("e4"), "opening")
                 if f.theme == "square_control"]
        assert facts and facts[0].polarity == "fault"

    def test_the_two_answers_on_mohits_position_still_come_back(self):
        """The gate must not cost us the real pair."""
        out = separating_themes(FEN, "e4", GOOD, phase="opening")
        assert {(s.direction, s.theme) for s in out} == {
            ("missed", "development"), ("received", "square_control")}
