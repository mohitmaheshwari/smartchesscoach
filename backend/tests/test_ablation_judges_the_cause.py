"""The ablation judge, tested with a stub evaluator and no engine.

`evaluate` is injected, so every number below is chosen by the test and the
module's arithmetic is what is under examination -- not Stockfish's opinion. The
real evaluator gets one process per probe, which these tests do not need and
could not afford.

The fixture is Mohit's own position and the numbers are the ones measured there
at depth 18:

    after Na6 (engine's choice)   -94
    after Nc6 (played)           -158      cost 64
    knight teleported c6 -> a6    -89      recovers 69   <- 100%+ of the cost
    knight teleported c6 -> e7   -160      recovers  0
    knight teleported c6 -> c5    -24      recovers 137

The share above 1.0 is deliberate and kept: the probe position really is better
than the engine's own best move, and clamping it would hide that.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ablation import (  # noqa: E402
    apply_hypothesis,
    attribute,
    pass_instead,
    remove_piece,
    teleport,
)

FEN = "rn3rk1/1ppq1pp1/3pb2p/p3p3/P1B1P2B/N1PP3P/1P3KP1/R2Q2N1 b - - 5 14"
PLAYED, BEST = "Nc6", "Na6"

# measured at depth 18, keyed by where the knight ends up
EVALS = {chess.A6: -89, chess.E7: -160, chess.C5: -24}
AFTER_PLAYED, AFTER_BEST, PASSED = -158, -94, -171


def _stub(board: chess.Board):
    """Returns the measured eval for each probe position, by knight square."""
    if board.piece_at(chess.A6) and board.piece_at(chess.A6).piece_type == chess.KNIGHT \
            and board.piece_at(chess.A6).color == chess.BLACK \
            and not board.piece_at(chess.B8):
        # could be the engine's Na6 or the teleport; they differ in side to move
        return AFTER_BEST if board.turn == chess.WHITE and board.piece_at(chess.C6) is None \
            and _is_after_best(board) else EVALS[chess.A6]
    for sq, cp in EVALS.items():
        pc = board.piece_at(sq)
        if pc and pc.piece_type == chess.KNIGHT and pc.color == chess.BLACK:
            return cp
    if board.piece_at(chess.C6) and board.piece_at(chess.C6).piece_type == chess.KNIGHT:
        return AFTER_PLAYED
    if board.piece_at(chess.B8) and board.piece_at(chess.B8).piece_type == chess.KNIGHT:
        return PASSED
    return 0


def _is_after_best(board):
    """The real Na6 position: reached by pushing the move, so the move stack
    distinguishes it from a teleport, which clears the stack."""
    return bool(board.move_stack)


class TestItAttributesTheCostToTheRightSquare:
    def _run(self):
        return attribute(FEN, PLAYED, BEST,
                         [teleport(chess.C6, chess.A6, "belongs on a6"),
                          teleport(chess.C6, chess.E7, "belongs on e7"),
                          teleport(chess.C6, chess.C5, "belongs on c5")],
                         _stub)

    def test_the_cost_is_the_gap_between_best_and_played(self):
        r = self._run()
        assert r.cost_cp == AFTER_BEST - AFTER_PLAYED == 64

    def test_a6_is_skipped_because_it_rebuilds_the_best_move(self):
        """This assertion used to read "a6 recovers 69, share > 1.0", which was
        the number I quoted as proof the method works. The played move is
        Nb8-c6 and the best is Nb8-a6, so that probe reconstructs the best
        move's position and recovers the cost by construction."""
        r = self._run()
        a6 = next(a for a in r.attributions if a.hypothesis.to_square == chess.A6)
        assert a6.recovered_cp is None
        assert "best move" in (a6.skipped or "")

    def test_e7_recovers_nothing(self):
        r = self._run()
        e7 = next(a for a in r.attributions if a.hypothesis.to_square == chess.E7)
        assert e7.recovered_cp == -2

    def test_the_leader_is_the_largest_recovery_not_the_first_listed(self):
        r = self._run()
        assert r.leader.hypothesis.to_square == chess.C5
        assert r.leader.recovered_cp == 134

    def test_a_share_above_one_is_kept_not_clamped(self):
        """Clamping would hide that the probe beats the engine's own best."""
        r = self._run()
        assert max(a.share for a in r.attributions if a.share) > 1.0


class TestTheNullProbe:
    def test_it_measures_the_move_against_not_moving(self):
        r = attribute(FEN, PLAYED, BEST, [pass_instead()], _stub)
        a = r.attributions[0]
        assert a.recovered_cp == PASSED - AFTER_PLAYED == -13

    def test_it_is_measured_on_the_position_before_the_move(self):
        """A null probe asks what the position was worth WITHOUT the move, so
        applying it to the post-move board would answer a different question."""
        board = chess.Board(FEN)
        assert apply_hypothesis(board, pass_instead()) is None


class TestItRefusesProbesItCannotMake:
    def test_an_occupied_destination_is_skipped_not_scored(self):
        r = attribute(FEN, PLAYED, BEST,
                      [teleport(chess.C6, chess.D7, "onto our own queen")],
                      _stub)
        assert r.attributions[0].recovered_cp is None
        assert r.attributions[0].skipped

    def test_an_empty_origin_is_skipped(self):
        r = attribute(FEN, PLAYED, BEST,
                      [teleport(chess.H5, chess.H4, "nothing there")], _stub)
        assert r.attributions[0].skipped

    def test_a_king_is_never_teleported(self):
        """Moving a king changes legality wholesale, so the probe would differ
        from the original in more than one way."""
        r = attribute(FEN, PLAYED, BEST,
                      [teleport(chess.G8, chess.H8, "king elsewhere")], _stub)
        assert r.attributions[0].skipped

    def test_a_king_is_never_removed(self):
        r = attribute(FEN, PLAYED, BEST, [remove_piece(chess.G8)], _stub)
        assert r.attributions[0].skipped

    def test_an_illegal_played_move_returns_nothing_measurable(self):
        r = attribute(FEN, "Qh1", BEST, [pass_instead()], _stub)
        assert r.cost_cp is None and r.attributions == []


class TestTheEnPassantTrap:
    """Placing a pawn on the ep target square makes the position illegal, and
    the first real run of this reported every probe "invalid" for that reason
    alone -- an experiment that silently did not happen."""

    EP_FEN = "rnbqk2r/pppp1ppp/5n2/2b1p3/2P5/2N3P1/PP1PPP1P/R1BQKBNR w KQkq - 1 4"

    def test_a_pawn_can_be_teleported_back_after_a_double_push(self):
        board = chess.Board(self.EP_FEN)
        after = board.copy(stack=False)
        after.push(after.parse_san("e4"))
        assert after.ep_square == chess.E3, "fixture must set the ep square"
        probe = apply_hypothesis(after, teleport(chess.E4, chess.E3))
        assert probe is not None, "the ep square was not cleared"
        assert probe.piece_at(chess.E3).piece_type == chess.PAWN
        assert probe.ep_square is None

    def test_the_probe_keeps_the_side_to_move(self):
        board = chess.Board(self.EP_FEN)
        after = board.copy(stack=False)
        after.push(after.parse_san("e4"))
        probe = apply_hypothesis(after, teleport(chess.E4, chess.E3))
        assert probe.turn == after.turn

    def test_the_probe_keeps_castling_rights(self):
        board = chess.Board(self.EP_FEN)
        after = board.copy(stack=False)
        after.push(after.parse_san("e4"))
        probe = apply_hypothesis(after, teleport(chess.E4, chess.E3))
        assert probe.castling_rights == after.castling_rights


class TestWithoutABestMoveThereIsNoCost:
    def test_shares_are_none_but_recoveries_still_measured(self):
        """A recovery is meaningful on its own; a share needs something to be a
        share OF, and inventing one would be the kind of number that looks like
        evidence and is not."""
        r = attribute(FEN, PLAYED, None,
                      [teleport(chess.C6, chess.A6)], _stub)
        assert r.cost_cp is None
        assert r.attributions[0].recovered_cp == 69
        assert r.attributions[0].share is None


class TestAProbeThatRebuildsTheBestMoveTeachesNothing:
    """The played move is Nb8-c6 and the engine's best is Nb8-a6, so
    teleporting the knight from c6 to a6 reconstructs the position after the
    best move. It recovers exactly the cost every time, by construction.

    That 100% was quoted twice as evidence the method works. It proves only
    that the best move scores what the best move scores, and a number that
    cannot come out any other way is not a measurement.
    """

    def test_the_tautological_probe_is_skipped(self):
        r = attribute(FEN, PLAYED, BEST,
                      [teleport(chess.C6, chess.A6, "belongs on a6")], _stub)
        a = r.attributions[0]
        assert a.recovered_cp is None
        assert "best move" in (a.skipped or "")

    def test_the_informative_probes_survive(self):
        """c5 is not where the best move goes, so it still measures something
        -- and it is the square that actually matters in that position."""
        r = attribute(FEN, PLAYED, BEST,
                      [teleport(chess.C6, chess.A6),
                       teleport(chess.C6, chess.C5),
                       teleport(chess.C6, chess.E7)], _stub)
        scored = [a for a in r.attributions if a.recovered_cp is not None]
        assert {a.hypothesis.to_square for a in scored} == {chess.C5, chess.E7}
        assert r.leader.hypothesis.to_square == chess.C5

    def test_with_no_best_move_nothing_is_called_tautological(self):
        """Without a best move there is nothing for a probe to duplicate."""
        r = attribute(FEN, PLAYED, None,
                      [teleport(chess.C6, chess.A6)], _stub)
        assert r.attributions[0].recovered_cp == 69

    def test_the_comparison_ignores_move_counters(self):
        """Written first as "the FENs differ in their counters, so comparing
        FENs would miss it" -- and on this fixture the FENs are IDENTICAL,
        because Nc6 and Na6 are both quiet knight moves and leave the clocks
        in the same place. The property still has to hold where they do differ,
        so it is tested directly instead of through a fixture that happened not
        to exercise it."""
        from services.ablation import _same_position
        board = chess.Board(FEN)
        pushed = board.copy(stack=False)
        pushed.push(pushed.parse_san("Na6"))
        other = pushed.copy(stack=False)
        other.halfmove_clock += 7
        other.fullmove_number += 3
        assert other.fen() != pushed.fen()
        assert _same_position(other, pushed) is True

    def test_the_comparison_still_separates_different_boards(self):
        """The negative control: a guard that returned True for everything
        would silence every probe and look like caution."""
        from services.ablation import _same_position
        board = chess.Board(FEN)
        a = board.copy(stack=False); a.push(a.parse_san("Na6"))
        b = board.copy(stack=False); b.push(b.parse_san("Nc6"))
        assert _same_position(a, b) is False
