"""A sacrifice is a situation of its own, and the lesson is what it buys.

Mohit, 2026-10-22, on move 25 of game 73b06bdd. White played Bd6+ when Qxg8
was winning, and the shipped card said:

    "Bd6+ is a major blunder - it drops the bishop after Qxd6. Qxg8 was
     better - it sacrifices your queen to open up a strong attack - the
     attack is worth more than the rook here."

Two things wrong. "Drops the bishop" is contradicted by the engine's own
line, where White wins the rook back and ends +2 pawns (fixed separately in
test_a_drop_must_survive_the_line). And "a strong attack" is vague because
`best_move_is_sacrifice` was the ONLY fact available -- the distilled layer
had six situations and none of them covered sacrifices, so 9,111 cards
(5.05% of the corpus) fell through to the hand-authored R12 cascade.

The fact nobody computed is what happens if the sacrifice is ACCEPTED. On
this card it is mate in one, which is the sharpest sentence available
anywhere in the set. Measured over the corpus: 171 of the 9,111 end in mate
when accepted. A small slice, and worth saying exactly where it is true.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.distilled_caption_service import (  # noqa: E402
    _missed_free,
    _missed_sacrifice,
)

# White to move. Qxg8 offers the queen; g8 is defended by the queen on d8.
BD6 = "rk1q2r1/pp3Q2/2b2p2/4p3/1BPb4/7B/P1P2P1P/R3K2R w KQ - 1 25"


class TestTheBoardSaysWhatIClaim:
    def test_g8_holds_a_rook_and_is_defended(self):
        b = chess.Board(BD6)
        r = b.piece_at(chess.G8)
        assert r and r.piece_type == chess.ROOK and r.color == chess.BLACK
        assert chess.D8 in b.attackers(chess.BLACK, chess.G8), (
            "the d8 queen defends g8 -- that is what makes it a sacrifice")

    def test_taking_it_really_is_mate(self):
        b = chess.Board(BD6)
        b.push(b.parse_san("Qxg8"))
        b.push(b.parse_san("Qxg8"))
        b.push(b.parse_san("Bd6#"))
        assert b.is_checkmate()


class TestItIsClassifiedAsASacrifice:
    def test_mohit_s_card_is_a_missed_sacrifice(self):
        f = _missed_sacrifice(BD6, "Bd6+", "Qxg8")
        assert f is not None
        assert f["sac_piece"] == "queen"
        assert f["sac_takes"] == "rook"
        assert f["sac_square"] == "g8"

    def test_and_it_carries_the_refutation(self):
        """The fact that was missing. Without it the caption can only say
        'a strong attack'."""
        f = _missed_sacrifice(BD6, "Bd6+", "Qxg8")
        assert f["accept_san"] == "Qxg8"
        assert f["mate_san"] == "Bd6#"

    def test_the_free_capture_mirror_does_not_claim_it(self):
        """_missed_free requires the square be UNDEFENDED. If both fired, a
        sacrifice would be described as taking something for free."""
        assert _missed_free(BD6, "Bd6+", "Qxg8") is False


class TestItDoesNotOverreach:
    def test_taking_a_bigger_piece_with_a_smaller_one_is_not_a_sacrifice(self):
        """Pawn takes queen on a defended square is a winning exchange, not a
        sacrifice, however defended the square is."""
        fen = "rnb1kbnr/pppp1ppp/8/4p3/3q4/2P5/PP1PPPPP/RNBQKBNR w KQkq - 0 1"
        b = chess.Board(fen)
        assert b.piece_at(chess.D4).piece_type == chess.QUEEN
        assert _missed_sacrifice(fen, "a3", "cxd4") is None

    def test_a_quiet_best_move_is_not_a_sacrifice(self):
        assert _missed_sacrifice(BD6, "Bd6+", "Rd1") is None

    def test_playing_it_ourselves_is_not_missing_it(self):
        assert _missed_sacrifice(BD6, "Qxg8", "Qxg8") is None

    def test_an_illegal_best_move_is_refused_quietly(self):
        assert _missed_sacrifice(BD6, "Bd6+", "Qxz9") is None


class TestTheCaptionItProduces:
    def _render(self, facts, played="Bd6+"):
        import json
        store = json.load(open(
            Path(__file__).resolve().parents[1] / "data"
            / "distilled_templates.json", encoding="utf-8"))["templates"]
        key = "missed_sacrifice_mate" if "mate_san" in facts else "missed_sacrifice"
        return store[key].format(played_san=played, **facts)

    def test_it_names_the_mate_rather_than_a_strong_attack(self):
        text = self._render(_missed_sacrifice(BD6, "Bd6+", "Qxg8"))
        assert "Bd6#" in text
        assert "mate" in text.lower()
        assert "strong attack" not in text.lower(), (
            "the whole point is to stop saying this")

    def test_it_stays_inside_the_word_cap(self):
        """caption_config.json caps captions at 60 words."""
        text = self._render(_missed_sacrifice(BD6, "Bd6+", "Qxg8"))
        assert len(text.split()) <= 60, len(text.split())

    def test_the_plain_variant_still_says_what_is_given_and_got(self):
        facts = dict(_missed_sacrifice(BD6, "Bd6+", "Qxg8"))
        facts.pop("accept_san", None)
        facts.pop("mate_san", None)
        text = self._render(facts)
        assert "queen" in text and "rook" in text
