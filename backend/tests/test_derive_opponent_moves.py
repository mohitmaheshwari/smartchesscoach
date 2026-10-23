"""The opponent's moves, reconstructed without an engine.

Mohit: "we need to keep every opponent moves too, like we keep user moves,
that's really really required" -- and then, on the 34 hours of Stockfish it
would take to backfill 1,354 games on a box whose database was being
OOM-killed that afternoon: "40 hours on this machine??"

The derivation reads the opponent's evals off the reader's own stored moves.
These tests pin the two things that make it trustworthy rather than merely
plausible:

  * it REFUSES a game it cannot align, instead of attributing evals to the
    wrong move and looking fine
  * a repeated SAN goes to the right ply

and the one thing that makes it honest: it does not claim a quality label
it cannot derive.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_spec = importlib.util.spec_from_file_location(
    "derive_opponent_moves", BACKEND / "scripts" / "derive_opponent_moves.py")
dom = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dom)


def _pgn(moves: str) -> str:
    return '[Event "t"]\n[Result "*"]\n\n' + moves + " *"


def _user_records(moves, evals):
    """(move, eval_before, eval_after) triples as the analyser stores them."""
    return [{"move": m, "eval_before": b, "eval_after": a}
            for m, (b, a) in zip(moves, evals)]


class TestItRefusesWhatItCannotAlign:
    def test_a_user_record_count_that_does_not_match_the_pgn(self):
        merged, why, n = dom.derive_for_game(
            _pgn("1. e4 e5 2. Nf3 Nc6"), "white",
            _user_records(["e4"], [(30, 25)]),   # pgn has TWO user plies
            [])
        assert merged is None
        assert "stored 1 user records" in why

    def test_a_user_move_that_is_not_the_pgn_s_move(self):
        merged, why, n = dom.derive_for_game(
            _pgn("1. e4 e5 2. Nf3 Nc6"), "white",
            _user_records(["e4", "Bc4"], [(30, 25), (25, 20)]),
            [])
        assert merged is None
        assert "user move mismatch" in why

    def test_an_opponent_record_from_another_game(self):
        merged, why, n = dom.derive_for_game(
            _pgn("1. e4 e5 2. Nf3 Nc6"), "white",
            _user_records(["e4", "Nf3"], [(30, 25), (25, 20)]),
            [{"move": "Qh4", "move_number": 2}])     # never played here
        assert merged is None
        assert "do not align" in why

    def test_refusing_writes_nothing(self):
        """A refusal must not return a partial list. The whole point is that
        a misaligned game is left alone rather than filled with evals that
        belong to other moves."""
        for bad in ([], [{"move": "Qh4", "move_number": 9}]):
            merged, _, n = dom.derive_for_game(
                _pgn("1. e4 e5"), "white",
                _user_records(["e4", "Nf3"], [(30, 25), (25, 20)]), bad)
            assert merged is None
            assert n == 0


class TestARepeatedSanGoesToTheRightPly:
    """The bug this class exists for: an engine record for Qf6 on move 26 was
    placed on an earlier Qf6 on move 11, because the first version of the
    matcher walked forwards to the next SAN that matched. The merged list
    then ran 10, 26, 12, 13 and every eval after it described another move.
    """

    PGN = _pgn("1. Nf3 Nf6 2. Ng1 Ng8 3. Nf3 Nf6")
    USER = ["Nf3", "Ng1", "Nf3"]
    EVALS = [(20, 18), (18, 10), (10, 14)]

    def test_the_engine_record_lands_on_its_own_move_number(self):
        engine = {"move": "Nf6", "move_number": 3, "cp_loss": 120,
                  "best_move": "e5", "eval_before": 14, "eval_after": 90}
        merged, why, n = dom.derive_for_game(
            self.PGN, "white",
            _user_records(self.USER, self.EVALS), [engine])
        assert merged is not None, why
        # Nf6 is played on move 1 and move 3; the engine record is move 3.
        assert [m["move"] for m in merged] == ["Nf6", "Ng8", "Nf6"]
        assert merged[0].get("derived") == dom.DERIVED
        assert merged[2] is engine, (
            "the move-3 engine record was placed on the move-1 Nf6")

    def test_the_list_runs_forwards(self):
        engine = {"move": "Nf6", "move_number": 3, "cp_loss": 120,
                  "best_move": "e5"}
        merged, why, _ = dom.derive_for_game(
            self.PGN, "white",
            _user_records(self.USER, self.EVALS), [engine])
        assert merged is not None, why
        numbers = [m["move_number"] for m in merged]
        assert numbers == sorted(numbers), numbers


class TestTheEvalsComeFromTheRightNeighbours:
    """their eval_before is the reader's previous eval_after; their
    eval_after is the reader's next eval_before."""

    def test_white_reader(self):
        merged, why, _ = dom.derive_for_game(
            _pgn("1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5"), "white",
            _user_records(["e4", "Nf3", "Bc4"],
                          [(30, 25), (128, 120), (75, 70)]),
            [])
        assert merged is not None, why
        e5 = merged[0]
        assert e5["eval_before"] == 25, "the reader's e4 ended at +25"
        assert e5["eval_after"] == 128, "the reader's Nf3 started at +128"
        # white-relative evals rising is BAD for the black mover
        assert e5["cp_loss"] == 128 - 25

    def test_black_reader_flips_the_sign(self):
        merged, why, _ = dom.derive_for_game(
            _pgn("1. e4 e5 2. Nf3 Nc6"), "black",
            _user_records(["e5", "Nc6"], [(35, 30), (-20, -25)]),
            [])
        assert merged is not None, why
        e4 = merged[0]
        assert e4["move"] == "e4"
        # eval_before is None (no reader move precedes white's first), so no
        # cp_loss can be derived -- and none must be invented.
        assert "cp_loss" not in e4
        nf3 = merged[1]
        assert nf3["move"] == "Nf3"
        assert nf3["eval_before"] == 30 and nf3["eval_after"] == -20
        # the white mover's eval FELL from +30 to -20, so white lost 50
        assert nf3["cp_loss"] == 50

    def test_a_clamped_eval_produces_no_cp_loss(self):
        """|eval| over 900 is the mate sentinel, not a centipawn score.
        Differencing it yields nonsense, so nothing is claimed."""
        merged, why, _ = dom.derive_for_game(
            _pgn("1. e4 e5 2. Nf3 Nc6"), "white",
            _user_records(["e4", "Nf3"], [(30, 9998), (9998, 9998)]),
            [])
        assert merged is not None, why
        assert "cp_loss" not in merged[0]
        assert "eval_before" in merged[0], (
            "the eval itself is still recorded; only the difference is withheld")

    def test_cp_loss_is_never_negative(self):
        """A move that IMPROVES the mover's eval has not lost anything.
        cp_loss is defined as a loss and the review page compares it to
        thresholds, so a negative would read as a brilliant move."""
        merged, why, _ = dom.derive_for_game(
            _pgn("1. e4 e5 2. Nf3 Nc6"), "white",
            _user_records(["e4", "Nf3"], [(30, 25), (-200, -210)]),
            [])
        assert merged is not None, why
        assert merged[0]["cp_loss"] == 0


class TestItClaimsOnlyWhatItKnows:
    def test_no_quality_label_is_written(self):
        """Measured on 6,436 user moves where the engine's own label is
        stored: labelling from the derived cp_loss agrees 75.7% and calls a
        move WORSE than it was on 16.7%, 469 of them by two levels. Shaving
        10cp first still overstates 227. So the label is withheld -- a wrong
        severity is a false fact about how bad the move was."""
        merged, why, _ = dom.derive_for_game(
            _pgn("1. e4 e5 2. Nf3 Nc6"), "white",
            _user_records(["e4", "Nf3"], [(30, 25), (128, 120)]),
            [])
        assert merged is not None, why
        for m in merged:
            if m.get("derived"):
                assert "evaluation" not in m

    def test_no_best_move_or_engine_line_is_invented(self):
        merged, why, _ = dom.derive_for_game(
            _pgn("1. e4 e5 2. Nf3 Nc6"), "white",
            _user_records(["e4", "Nf3"], [(30, 25), (128, 120)]),
            [])
        assert merged is not None, why
        for m in merged:
            if m.get("derived"):
                for field in ("best_move", "pv_after_best",
                              "pv_after_played", "eval_line_played"):
                    assert field not in m, field

    def test_every_derived_record_is_stamped(self):
        merged, why, n = dom.derive_for_game(
            _pgn("1. e4 e5 2. Nf3 Nc6"), "white",
            _user_records(["e4", "Nf3"], [(30, 25), (128, 120)]),
            [])
        assert merged is not None, why
        assert n == 2
        assert all(m["derived"] == dom.DERIVED for m in merged)
        assert all(m["is_opponent_move"] is True for m in merged)

    def test_an_engine_record_is_returned_untouched(self):
        engine = {"move": "e5", "move_number": 1, "cp_loss": 300,
                  "best_move": "c5", "eval_line_played": ["a", "b"],
                  "evaluation": "blunder"}
        merged, why, n = dom.derive_for_game(
            _pgn("1. e4 e5 2. Nf3 Nc6"), "white",
            _user_records(["e4", "Nf3"], [(30, 25), (128, 120)]),
            [engine])
        assert merged is not None, why
        assert merged[0] is engine
        assert n == 1, "only the move WITHOUT an engine record is derived"

    def test_a_previously_derived_record_is_rebuilt_not_kept(self):
        """Re-running must not stack derived records on derived records.
        The first run of this script wrote a misaligned list; the repair was
        simply to run it again, which only works if the old derived rows are
        discarded."""
        stale = {"move": "e5", "move_number": 1, "derived": dom.DERIVED,
                 "cp_loss": 999}
        merged, why, n = dom.derive_for_game(
            _pgn("1. e4 e5 2. Nf3 Nc6"), "white",
            _user_records(["e4", "Nf3"], [(30, 25), (128, 120)]),
            [stale])
        assert merged is not None, why
        assert len(merged) == 2
        assert merged[0] is not stale
        assert merged[0]["cp_loss"] == 103


class TestTheWholeOpponentSideIsCovered:
    def test_every_opponent_ply_gets_a_record(self):
        merged, why, _ = dom.derive_for_game(
            _pgn("1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. d3 d6"), "white",
            _user_records(["e4", "Nf3", "Bc4", "d3"],
                          [(30, 25), (28, 26), (26, 24), (24, 22)]),
            [])
        assert merged is not None, why
        assert [m["move"] for m in merged] == ["e5", "Nc6", "Bc5", "d6"]

    def test_an_already_complete_game_is_left_alone(self):
        engine = [{"move": "e5", "move_number": 1, "best_move": "e5"},
                  {"move": "Nc6", "move_number": 2, "best_move": "Nc6"}]
        merged, why, n = dom.derive_for_game(
            _pgn("1. e4 e5 2. Nf3 Nc6"), "white",
            _user_records(["e4", "Nf3"], [(30, 25), (128, 120)]),
            engine)
        assert merged is None
        assert why == "already complete"
        assert n == 0


class TestTheClassifierIsNotDuplicated:
    def test_it_returns_the_value_not_the_enum_repr(self):
        """MoveClassification is a (str, Enum) and str() on one yields
        'MoveClassification.BEST'. Writing that would be a label nothing
        else in the repo matches -- it read as 0 of 57 labels agreeing when
        every one of them did."""
        assert dom._classify(0, 30) == "best"
        assert "MoveClassification" not in dom._classify(0, 30)

    def test_it_is_the_repo_s_own_classifier(self):
        from stockfish_service import StockfishEngine
        for cp in (0, 5, 25, 60, 150, 400):
            mine = dom._classify(cp, 30)
            theirs = StockfishEngine.classify_move(None, cp, False, 30)
            assert mine == getattr(theirs, "value", str(theirs)), cp
