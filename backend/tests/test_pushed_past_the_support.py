"""A pawn push that runs past the only square that could hold your weak pawn.

Mohit's move-5 position, 2026-10-21. Every layer was silent on it and every
layer was right to be -- no move of the better line became illegal, and
nothing was guarding anything yet, so neither shipped question could see it.

The lesson is a square, and the cleanest counterfactual in chess proves it:
the SAME pawn, one square less.

    c6  +35    d5 defended by c6 and d8
    c5   +0    d5 defended by d8 alone

Black's e-pawn had already become the d5 pawn via exd5, so c7-c6 was the only
pawn support d5 could ever have. c5 goes past it, and afterwards no black pawn
can reach c6 or e6 at all.

It is NOT a development lesson, which is what the card said. d4 is a pawn move
at +57, level with Nf6 at +58, and h6 at +40 beats Nc6 at +29.

Measured over 500 games / 16,437 moves: fires 30 times, 13 of them on flagged
cards -- 0.23% of them. Rare. All 30 claims re-verified on the board
independently of the question.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.contrastive_reasoner import (  # noqa: E402
    CAUSE,
    _a_pawn_can_still_support,
    _support_squares,
    q_pushed_past_the_support,
)

FEN = "rnbqk1nr/ppp1bppp/8/3p4/8/2N2N2/PPPPQPPP/R1B1KB1R b KQkq - 3 5"


def ctx_for(fen, played, best="Nf6", pv_best=(), pv_played=(), cp_loss=48):
    board = chess.Board(fen)
    after = board.copy()
    after.push(board.parse_san(played))
    return {"before": board, "after": after, "played_san": played,
            "best_san": best, "pv_best": list(pv_best),
            "pv_played": list(pv_played), "cp_loss": cp_loss}


class TestTheBoardSaysWhatIClaim:
    """python-chess only. The question is not consulted."""

    def test_d5_is_a_black_pawn_under_attack(self):
        b = chess.Board(FEN)
        p = b.piece_at(chess.D5)
        assert p and p.piece_type == chess.PAWN and p.color == chess.BLACK
        assert b.attackers(chess.WHITE, chess.D5)

    def test_no_pawn_defends_it_yet(self):
        b = chess.Board(FEN)
        pawns = [s for s in b.attackers(chess.BLACK, chess.D5)
                 if b.piece_at(s).piece_type == chess.PAWN]
        assert not pawns

    def test_c6_is_one_of_its_two_support_squares(self):
        squares = _support_squares(chess.D5, chess.BLACK)
        assert chess.C6 in squares and chess.E6 in squares

    def test_a_pawn_could_support_it_before_the_push(self):
        assert _a_pawn_can_still_support(chess.Board(FEN), chess.D5, chess.BLACK)

    def test_and_cannot_after_it(self):
        b = chess.Board(FEN)
        b.push_san("c5")
        assert not _a_pawn_can_still_support(b, chess.D5, chess.BLACK)

    def test_because_the_e_pawn_is_already_gone(self):
        """It BECAME the d5 pawn via exd5, which is why c6 was the only one."""
        b = chess.Board(FEN)
        e_pawns = [s for s, p in b.piece_map().items()
                   if p.piece_type == chess.PAWN and p.color == chess.BLACK
                   and chess.square_file(s) == 4]
        assert not e_pawns


class TestItFiresOnTheCard:
    def test_it_answers(self):
        out = q_pushed_past_the_support(ctx_for(FEN, "c5"))
        assert out is not None

    def test_it_names_the_square_that_was_skipped(self):
        out = q_pushed_past_the_support(ctx_for(FEN, "c5"))
        assert out["skipped"] == "c6"
        assert out["short_push"] == "c6"

    def test_it_names_the_pawn_that_is_now_alone(self):
        out = q_pushed_past_the_support(ctx_for(FEN, "c5"))
        assert out["weak_pawn"] == "d5"

    def test_it_is_a_cause(self):
        assert q_pushed_past_the_support(ctx_for(FEN, "c5"))["tier"] == CAUSE


class TestItStaysSilentWithoutTheWholeStory:
    def test_the_short_push_itself_says_nothing(self):
        """c6 IS the support. The question must not fire on the good move."""
        assert q_pushed_past_the_support(ctx_for(FEN, "c6")) is None

    def test_a_single_push_is_never_this(self):
        assert q_pushed_past_the_support(ctx_for(FEN, "h6")) is None

    def test_a_piece_move_is_never_this(self):
        assert q_pushed_past_the_support(ctx_for(FEN, "Nf6")) is None

    def test_an_opening_double_push_with_nothing_to_support(self):
        """1.e4 skips e3, but there is no weak white pawn for e3 to hold."""
        assert q_pushed_past_the_support(
            ctx_for(chess.STARTING_FEN, "e4", best="d4")) is None

    def test_silence_when_the_weak_pawn_is_not_attacked(self):
        """Giving up a support that nothing is pressing is not a lesson."""
        b = chess.Board(FEN)
        # remove the only attacker of d5 and the claim should evaporate
        b.remove_piece_at(chess.C3)
        assert not b.attackers(chess.WHITE, chess.D5)
        after = b.copy(); after.push_san("c5")
        assert q_pushed_past_the_support({
            "before": b, "after": after, "played_san": "c5",
            "best_san": "Nf6", "pv_best": [], "pv_played": [],
            "cp_loss": 48}) is None

    def test_silence_when_another_pawn_can_still_support(self):
        """If the e-pawn were still home, c6 is not the only way in."""
        b = chess.Board(FEN)
        b.set_piece_at(chess.E7, chess.Piece(chess.PAWN, chess.BLACK))
        after = b.copy(); after.push_san("c5")
        assert _a_pawn_can_still_support(after, chess.D5, chess.BLACK)
        assert q_pushed_past_the_support({
            "before": b, "after": after, "played_san": "c5",
            "best_san": "Nf6", "pv_best": [], "pv_played": [],
            "cp_loss": 48}) is None
