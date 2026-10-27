"""The LLM is only let near the cards it is measurably good at.

Mohit 2026-10-27: "straight up blunders and all are easy to capture with
templates and we are already doing that, but positions which don't make
sense, why something was an inaccuracy, endgames, where captions and
templates can't justify stockfish, i need my engine and LLM to work
there."

Measured over 316 user mistake cards from 55 games, every caption scored
by narrator_claim_verifier.verify_caption(strict_v2=True):

    cause        cp band    n    LLM clean   added a new square
    quiet        100-199   141        95%           23%
    quiet        200-299    33       100%           18%
    quiet        300+       59        81%           15%
    mechanical   100-199    36        87%           19%
    mechanical   200-299    16        69%            6%
    mechanical   300+       31        48%           10%

The gate is `quiet AND under 300cp` -- 96% clean on 174 of the 316
cards. Two clauses, because quiet-and-300+ falls to 81%, below the
95-100% of the band it admits.

What the gate is protecting against is NOT verbose prose. The model's
extra violations on mechanical cards are `piece_on_square` and
`free_when_defended`: a piece claimed on a square it does not occupy, a
defended piece called free. Invented board fact is the one failure a
better prompt cannot reach, which is why it is gated rather than
rewritten.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.v5_llm_polish import llm_may_write, BLUNDER_CP  # noqa: E402

# 1.e4 e5 2.Nf3 Nc6 3.Bb5 -- after 3...a6 White has quiet moves (Ba4, O-O)
# and captures (Bxc6). One position, so the cause is the only thing that
# changes between the cases below.
FEN = "r1bqkbnr/1ppp1ppp/p1n5/4p3/B3P3/5N2/PPPP1PPP/RNBQK2R b kq - 1 4"
# Black to move: Nf6 is quiet, Nxe4 is a capture, and after 4...Nd4 there
# is no check available, so a checking case needs its own position.
CHECK_FEN = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2"
# Black to move: Qh4 is check (and not a capture).


class TestOnlyQuietPositions:
    def test_a_quiet_best_move_under_the_bar_is_admitted(self):
        assert llm_may_write(best_move_san="Nf6", fen_before=FEN,
                             cp_loss=150) is True

    def test_a_capture_is_refused_however_small_the_loss(self):
        """Mechanical cards are template territory: the model is 48% clean
        on mechanical blunders and templates are already good there."""
        assert llm_may_write(best_move_san="Nxe4", fen_before=FEN,
                             cp_loss=120) is False

    def test_a_check_is_refused(self):
        assert llm_may_write(best_move_san="Qh4+", fen_before=CHECK_FEN,
                             cp_loss=120) is False


class TestTheBlunderBar:
    def test_a_quiet_blunder_is_refused(self):
        """Quiet AND 300+ measured 81% clean, below the band admitted."""
        assert llm_may_write(best_move_san="Nf6", fen_before=FEN,
                             cp_loss=300) is False
        assert llm_may_write(best_move_san="Nf6", fen_before=FEN,
                             cp_loss=900) is False

    def test_the_bar_is_exclusive_at_its_edge(self):
        assert llm_may_write(best_move_san="Nf6", fen_before=FEN,
                             cp_loss=BLUNDER_CP - 1) is True
        assert llm_may_write(best_move_san="Nf6", fen_before=FEN,
                             cp_loss=BLUNDER_CP) is False

    def test_the_mate_sentinel_cannot_slip_through(self):
        """cp_loss carries a sentinel on mate rows -- 9148 appears in real
        data. It is far above the bar, so it is refused like any blunder."""
        assert llm_may_write(best_move_san="Nf6", fen_before=FEN,
                             cp_loss=9148) is False


class TestItFailsClosed:
    def test_no_cp_loss_is_refused(self):
        assert llm_may_write(best_move_san="Nf6", fen_before=FEN,
                             cp_loss=None) is False

    def test_a_missing_position_is_refused(self):
        assert llm_may_write(best_move_san="Nf6", fen_before=None,
                             cp_loss=150) is False
        assert llm_may_write(best_move_san="Nf6", fen_before="",
                             cp_loss=150) is False

    def test_a_missing_best_move_is_refused(self):
        assert llm_may_write(best_move_san=None, fen_before=FEN,
                             cp_loss=150) is False
        assert llm_may_write(best_move_san="", fen_before=FEN,
                             cp_loss=150) is False

    def test_an_unparseable_position_is_refused_not_admitted(self):
        """The expensive mistake is polishing a mechanical card, so an
        unreadable position must refuse rather than fall through."""
        assert llm_may_write(best_move_san="Nf6", fen_before="not a fen",
                             cp_loss=150) is False

    def test_a_move_illegal_in_the_position_is_refused(self):
        assert llm_may_write(best_move_san="Qxh7", fen_before=FEN,
                             cp_loss=150) is False

    def test_a_non_numeric_cp_loss_is_refused(self):
        assert llm_may_write(best_move_san="Nf6", fen_before=FEN,
                             cp_loss="lots") is False
