"""It was already hanging and you did not hold it.

Found by reasoning over a stratified sample of cards the framework could not
explain -- Mohit's idea: work the cases the way the Nc3 and c5 cases were
worked, and let the mechanisms fall out. Two of eleven sampled cards were the
same story, and nothing in the system could see it:

    Rae1 (best Rfd1, 188cp)   d4 loose before AND after; Rfd1 defends d4
    Rf1  (best Rc1,  313cp)   c3 loose before AND after; Rc1 defends c3

Measured over 500 games: 1,874 cards carry a loose man, the better move holds
what the played move leaves on 520, and 493 of those were silent -- more than
the entire framework explained at the time.

Requiring that the man is actually TAKEN costs reach, 267 of 493, and buys the
difference between a cost and a risk. This repo has called the second the
first often enough.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.contrastive_reasoner import CAUSE, q_left_it_loose  # noqa: E402

# Real card: d4 is loose, Rae1 ignores it, Rfd1 holds it.
RAE1 = "r2qk2r/5ppp/p1p1pb2/3p4/3P4/2N2Q1P/PPP2PP1/R4RK1 w kq - 0 13"

# Constructed, because the recapture clause is nearly unreachable in real play:
# a man you can win back on its own square is normally a DEFENDED man, so not
# loose. It takes the capture itself to unblock the defender. Here Bh8 watches
# d4 through f6 and e5; the black bishop blocks it, so d4 hangs -- and the
# moment that bishop takes on d4 it stops blocking and Bxd4 answers.
UNBLOCKS = "4k2B/8/5b2/8/3P4/8/8/R4RK1 w - - 0 1"


def ctx(fen, played, best, pv_played, cp_loss=188):
    board = chess.Board(fen)
    after = board.copy()
    after.push(board.parse_san(played))
    return {"before": board, "after": after, "played_san": played,
            "best_san": best, "pv_best": [], "pv_played": list(pv_played),
            "cp_loss": cp_loss}


class TestTheBoardSaysWhatIClaim:
    def test_d4_is_ours_attacked_and_undefended(self):
        b = chess.Board(RAE1)
        p = b.piece_at(chess.D4)
        assert p and p.color == chess.WHITE
        assert b.attackers(chess.BLACK, chess.D4)
        assert not b.attackers(chess.WHITE, chess.D4)

    def test_the_played_move_does_not_hold_it(self):
        b = chess.Board(RAE1)
        b.push_san("Rae1")
        assert not b.attackers(chess.WHITE, chess.D4)

    def test_the_better_move_does(self):
        b = chess.Board(RAE1)
        b.push_san("Rfd1")
        assert chess.D1 in b.attackers(chess.WHITE, chess.D4)


class TestItFiresWhenTheManIsTaken:
    def test_it_answers(self):
        out = q_left_it_loose(ctx(RAE1, "Rae1", "Rfd1", ["Bxd4", "Rd1", "Qf6"]))
        assert out is not None
        assert out["square"] == "d4"
        assert out["loose"] == "pawn"
        assert out["tier"] == CAUSE

    def test_it_names_who_takes_it(self):
        out = q_left_it_loose(ctx(RAE1, "Rae1", "Rfd1", ["Bxd4", "Rd1", "Qf6"]))
        assert out["taken_san"] == "Bxd4"
        assert out["taken_by"] == "bishop"


class TestItStaysSilentWithoutTheWholeStory:
    def test_silence_when_they_never_take_it(self):
        """Loose and untaken is a risk, not a cost."""
        assert q_left_it_loose(
            ctx(RAE1, "Rae1", "Rfd1", ["Qa5", "Qe3", "O-O"])) is None

    def test_silence_when_the_better_move_does_not_fix_it_either(self):
        """Then it is a fact about the position, not about the choice. This
        is the differential, built into the question's own clauses.

        Rab1 is the right control here and Qe3 is not: the queen on e3
        guards d4 down the diagonal, so Qe3 cures it and the question
        SHOULD speak. Checked on the board, not by eye."""
        assert q_left_it_loose(
            ctx(RAE1, "Rae1", "Rab1", ["Bxd4", "Qd2"])) is None

    def test_silence_when_we_fixed_it_ourselves(self):
        assert q_left_it_loose(
            ctx(RAE1, "Rfd1", "Rfd1", ["Bxd4", "Rxd4"])) is None

    def test_silence_with_no_better_move_to_compare(self):
        assert q_left_it_loose(
            ctx(RAE1, "Rae1", "", ["Bxd4"])) is None

    def test_silence_when_we_win_it_straight_back(self):
        """Taken and recaptured on the same square is a trade."""
        assert q_left_it_loose(
            ctx(UNBLOCKS, "Ra2", "Rfd1", ["Bxd4", "Bxd4"])) is None

    def test_the_same_position_speaks_when_we_do_not_win_it_back(self):
        """The positive control for the clause above: one square, one line,
        and the only difference is whether we take back."""
        out = q_left_it_loose(ctx(UNBLOCKS, "Ra2", "Rfd1", ["Bxd4", "Kg2"]))
        assert out is not None and out["square"] == "d4"

    def test_nothing_loose_means_nothing_to_say(self):
        assert q_left_it_loose(
            ctx(chess.STARTING_FEN, "e4", "d4", ["e5", "Nf3"])) is None
