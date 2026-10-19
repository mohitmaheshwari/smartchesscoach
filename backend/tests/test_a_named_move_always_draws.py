"""A card that names a move always draws that move.

Mohit 2026-10-18, asked whether the recommended move should draw its own blue
arrow when there is nothing else drawable: "yes, it should always draw it's own
blue arrow".

This was already the written intent on the `neither` branch of the arrow
selector -- "The recommended move is drawn, because the caption names it, and
nothing more is claimed" -- and the code did not deliver it, because
_reply_attack_arrows emits the blue move arrow only ALONGSIDE a target, a check
or a winning capture. A card reading "Play Qd3" with nothing concrete to
threaten rendered over a bare board, and v222 made that visible on 42 more
cards by dropping the false payoff arrows that had been carrying the blue one.

Two things these tests guard, and the second is the one that matters:

  1. _named_move_arrow draws the move, and only when it is legal on the board
     the card renders.
  2. The PLACEMENT. The floor is called last in the selector, not from inside
     _reply_attack_arrows, because two fallbacks above it are gated on
     `not _teach_arrows` -- a builder that always returned something would
     shadow the five-move plan and the punishment picture with one arrow.
     TestTheBuilderBelowItStillDeclines fails if anyone moves it back up.

End-to-end behaviour is verified on the real render path through
generate_game_decryption_v5, not from a hand-rolled MoveInputs -- that harness
has produced a different caption than the live card before.
"""
import sys
from pathlib import Path

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_pipeline import (  # noqa: E402
    _named_move_arrow,
    _reply_attack_arrows,
)

# Mohit's Rac8 board: Black plays Rac8, the card recommends Qd3.
BEFORE = "r4rk1/1bq1nppp/1p2pn2/1B1p2N1/PB1P4/8/2P2PPP/R2QR1K1 b - - 0 1"


def _after_rac8():
    board = chess.Board(BEFORE)
    board.push_san("Rac8")
    return board


class TestItDrawsTheMoveTheCardNames:
    def test_the_rac8_card_now_draws_qd3(self):
        arrows = _named_move_arrow(_after_rac8(), "Qd3")
        assert arrows == [{
            "from": "d1", "to": "d3", "color": "blue", "teach": True,
        }]

    def test_one_arrow_and_only_one(self):
        """The floor restates the sentence; it never adds a payoff claim."""
        arrows = _named_move_arrow(_after_rac8(), "Qd3")
        assert len(arrows) == 1
        assert arrows[0]["color"] == "blue"

    def test_it_is_tagged_so_the_suppression_filter_keeps_it(self):
        """Untagged arrows are stripped downstream -- a picture that another
        rule had drawn once came out as no arrows at all that way."""
        assert all(a.get("teach") is True
                   for a in _named_move_arrow(_after_rac8(), "Qd3"))


class TestItNeverDrawsAMoveThatIsNotThere:
    """The arrow cannot be false, because the move is parsed on the board the
    card renders rather than taken from the words."""

    def test_an_illegal_move_draws_nothing(self):
        assert _named_move_arrow(_after_rac8(), "Qh8") == []

    def test_a_move_from_the_wrong_position_draws_nothing(self):
        """Rac8 has already been played, so it is not available again."""
        assert _named_move_arrow(_after_rac8(), "Rac8") == []

    @pytest.mark.parametrize(
        "bad", [None, "", "  ", "not a move", "Qxz9", "0-0-0-0", "e9"]
    )
    def test_unreadable_input_draws_nothing(self, bad):
        assert _named_move_arrow(_after_rac8(), bad) == []

    def test_no_board_draws_nothing(self):
        assert _named_move_arrow(None, "Qd3") == []

    def test_every_arrow_it_returns_is_a_legal_move(self):
        """Swept over a real game rather than one position."""
        board = chess.Board()
        for san in ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6",
                    "O-O", "Be7", "Re1", "b5", "Bb3", "d6", "c3", "O-O"]:
            legal_sans = []
            for mv in board.legal_moves:
                try:
                    legal_sans.append(board.san(mv))
                except Exception:
                    pass
            for cand in legal_sans[:12]:
                arrows = _named_move_arrow(board, cand)
                assert len(arrows) == 1, f"{cand} on {board.fen()}"
                a = arrows[0]
                assert any(
                    m.from_square == chess.parse_square(a["from"])
                    and m.to_square == chess.parse_square(a["to"])
                    for m in board.legal_moves
                )
            board.push_san(san)


class TestTheBuilderBelowItStillDeclines:
    """The floor is NOT inside _reply_attack_arrows. If it ever is, the
    fallbacks gated on `not _teach_arrows` become unreachable and a card that
    deserves a five-move plan gets one blue arrow instead."""

    def test_reply_attack_arrows_still_returns_nothing_without_a_payoff(self):
        board = chess.Board(BEFORE)
        played = board.parse_san("Rac8")
        assert _reply_attack_arrows(board, played, "Qd3") == []
