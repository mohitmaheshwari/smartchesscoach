"""A sacrifice is a move that LOSES material once the exchange is played out.

Mohit 2026-10-02: "find out position where engine suggests sacrificing... when
you give your bigger piece for a smaller piece but engine recommends that."

The fact already existed. Its test did not: "attacker worth more than the
target AND something defends the square afterwards", using board.attackers(),
which is pseudo-legal and never plays the trade out. Measured over 400 games it
fired on 422 recommended captures and 247 of them (58%) actually WIN material --
so "it sacrifices your bishop to open up a strong attack, the attack is worth
more than the pawn" was being said about moves that simply win a piece.

Every assertion computes material from the board.
"""
import chess

from services.caption_facts import legal_exchange_gain
from services.caption_pipeline import (
    CrossMoveState, MoveInputs, build_move_teaching_decision,
)


def _facts(fen, played, best, *, cp_loss=300, eval_before=0, eval_after=0, pv=()):
    board = chess.Board(fen)
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=fen, played_san=played, mover_is_user=True,
            mover_is_white=(board.turn == chess.WHITE),
            user_color="white" if board.turn == chess.WHITE else "black",
            full_move_number=board.fullmove_number, move_history_san=[],
            best_move_san=best, best_move_uci=board.parse_san(best).uci(),
            eval_before_cp=eval_before, eval_after_cp=eval_after,
            cp_loss=cp_loss, opp_cp_loss=0,
            pv_after_played=[], pv_after_best=list(pv),
        ),
        CrossMoveState(),
    )
    return decision.debug_facts


class TestTheOldTestWasWrong:
    """A big piece landing on a "defended" square is not automatically a sac.

    board.attackers() is PSEUDO-legal. Here the f6 knight appears to defend d5
    and is absolutely pinned to its king, so it can never recapture -- Rxd5
    simply wins a pawn.
    """

    FEN = "3k4/8/5n2/3p4/7B/8/8/3RK3 w - - 0 1"

    def test_the_square_looks_defended_to_the_old_test(self):
        board = chess.Board(self.FEN)
        board.push(board.parse_san("Rxd5"))
        assert {chess.square_name(s) for s in board.attackers(chess.BLACK, chess.D5)} == {"f6"}

    def test_but_nothing_can_legally_recapture(self):
        board = chess.Board(self.FEN)
        board.push(board.parse_san("Rxd5"))
        assert not [m for m in board.legal_moves if m.to_square == chess.D5]

    def test_so_the_exchange_wins_material(self):
        board = chess.Board(self.FEN)
        move = board.parse_san("Rxd5")
        assert legal_exchange_gain(board, chess.D5, chess.WHITE, first_move=move) > 0

    def test_and_it_is_not_flagged_as_a_sacrifice(self):
        facts = _facts(self.FEN, "Ke2", "Rxd5")
        assert not facts.get("best_move_is_sacrifice")


class TestARealSacrificeIsStillFound:
    # f7 is guarded only by the king, so Bxf7+ loses the bishop for a pawn.
    FEN = "rnbqkbnr/2p1pppp/p7/1p6/2BP4/2N5/PPP2PPP/R1BQK1NR w KQkq - 0 6"

    def test_the_exchange_really_loses_material(self):
        board = chess.Board(self.FEN)
        move = board.parse_san("Bxf7+")
        assert legal_exchange_gain(board, chess.F7, chess.WHITE, first_move=move) < 0

    def test_it_is_flagged(self):
        facts = _facts(self.FEN, "Nf3", "Bxf7+")
        assert facts.get("best_move_is_sacrifice") is True
        assert facts.get("best_move_sac_attacker_piece") == "bishop"


class TestNotFromALostPosition:
    """"The attack is worth more than the piece you lose" is false when the
    engine is only picking the best of bad options. 54 of 176 true sacrifices
    (31%) are played from a mover eval at or below -300."""

    FEN = "rnbqkbnr/2p1pppp/p7/1p6/2BP4/2N5/PPP2PPP/R1BQK1NR w KQkq - 0 6"

    def test_flagged_when_the_game_is_still_alive(self):
        facts = _facts(self.FEN, "Nf3", "Bxf7+", eval_before=0, eval_after=0)
        assert facts.get("best_move_is_sacrifice") is True

    def test_not_flagged_when_the_mover_is_already_lost(self):
        facts = _facts(self.FEN, "Nf3", "Bxf7+",
                       eval_before=-900, eval_after=-900)
        assert facts.get("user_is_losing") is True
        assert not facts.get("best_move_is_sacrifice")


class TestEvalSignIsWhiteRelative:
    """Reading eval_before's sign directly mis-signs every black-to-move card.

    Measured over the corpus: the stored eval agrees with White's material in
    97% of lopsided positions, and with the mover's in 44%.
    """

    def test_a_black_mover_who_is_winning_is_not_treated_as_losing(self):
        # Black to move, White's eval is -900, i.e. BLACK is winning.
        fen = "rnbqkbnr/2p1pppp/p7/1p6/2BP4/2N5/PPP2PPP/R1BQK1NR b KQkq - 0 6"
        board = chess.Board(fen)
        decision = build_move_teaching_decision(
            MoveInputs(
                fen_before=fen, played_san="c6", mover_is_user=True,
                mover_is_white=False, user_color="black",
                full_move_number=6, move_history_san=[],
                best_move_san="bxc4", best_move_uci=board.parse_san("bxc4").uci(),
                eval_before_cp=-900, eval_after_cp=-900,
                cp_loss=300, opp_cp_loss=0,
                pv_after_played=[], pv_after_best=[],
            ),
            CrossMoveState(),
        )
        assert not decision.debug_facts.get("user_is_losing"), (
            "a black mover at -900 (white-relative) is winning, not losing"
        )
